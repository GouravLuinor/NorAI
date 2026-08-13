from __future__ import annotations
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)
import json
import logging
import os
import random
import time
from pathlib import Path

import imagehash
from PIL import Image as PILImage
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from backend.ratelimit import rate_limiter as _limiter
from backend.usage_ledger import record_generate_usage
from cache_util import outputs_current, write_marker

logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# constants

from config import MODEL_NAME, DEFAULT_MAX_RETRIES

MAX_RETRIES = DEFAULT_MAX_RETRIES

CHAPTER_DIR = Path(
        "outputs/chapters"
)

SCREENSHOTS_OUT_DIR = Path(
        "outputs/screenshots/selected"
)

MAX_WORKERS = 4

LECTURE_NOTES_PREVIEW_COUNT = 5

# Pass 1 quality bar. A frame must clear both of these to be
# eligible for Pass 2 selection at all.

MIN_CONTENT_DENSITY = 6

MAX_INSTRUCTOR_OCCLUSION = 5

# Two frames are considered near-duplicates if their perceptual
# hash distance is at or below this threshold. Lower means
# stricter (only near-identical frames are merged).

DEDUP_HASH_DISTANCE = 6

# Pass 1 batch size: how many frames to score in a single LLM
# call. The last batch in a chapter may be smaller.

PASS1_BATCH_SIZE = 10

# ── Reuse of visual-extractor analysis (ROADMAP P1.3) ─────────────────────────
# Keyframes that the visual-knowledge stage (Stage 9) already analyzed get
# their Pass 1 quality scores synthesized from that analysis instead of being
# re-uploaded + re-scored by the LLM. Loaded once per lecture.
#   normalized frame path -> {ocr_text, importance_score, visual_type,
#                             include_in_notes}
_VISUAL_ANALYSIS: dict = {}


def load_visual_analysis(lecture_dir) -> dict:
    """
    Load the per-frame analysis persisted by visual_extractor (Stage 9) from
    {lecture_dir}/visual_objects/visual_analysis_ch*.json. Returns a dict of
    normalized frame path -> analysis entry. Missing analysis files are fine
    (screenshot selection then falls back to its own Pass 1 LLM scoring).
    """
    global _VISUAL_ANALYSIS
    _VISUAL_ANALYSIS = {}
    analysis_dir = Path(lecture_dir) / "visual_objects"
    for f in sorted(analysis_dir.glob("visual_analysis_ch*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for path, entry in (data.get("frames") or {}).items():
                _VISUAL_ANALYSIS[os.path.normpath(str(path))] = entry
        except Exception as e:
            logger.warning(f"Failed to load visual analysis {f}: {e}")
    if _VISUAL_ANALYSIS:
        logger.info(f"Loaded visual analysis for {len(_VISUAL_ANALYSIS)} frame(s).")
    return _VISUAL_ANALYSIS


# LLM Setup


def load_llm():
    """
    Load Gemini model.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found."
        )

    client = genai.Client(
        api_key=api_key
    )

    return client


client = load_llm()


from google.genai import types


class FrameQualityScore(BaseModel):

    path: str = Field(description="The exact local file path of the attached frame as provided in the prompt list, e.g. outputs/.../frame_136.jpg")

    content_density: int

    instructor_occlusion: int

    blur_level: int

    is_transition_or_decorative: bool


class FrameQualityBatch(BaseModel):

    scores: list[FrameQualityScore]


# Models


class SelectedScreenshot(BaseModel):

    path: str = Field(description="The exact local file path of the attached frame as provided in the candidate list, e.g. outputs/.../frame_136.jpg")

    reason: str

    section: str

    importance: int


class ChapterScreenshots(BaseModel):

    chapter_id: int

    screenshots: list[SelectedScreenshot]


# Prompts


FRAME_QUALITY_PROMPT = """
You are evaluating a batch of video frames from a single
lecture chapter recording. You are NOT selecting any frame for
anything yet. You must score EACH frame independently, on its
own merits. Do not compare frames to each other, do not let
one frame's quality affect another frame's score, and do not
assume frames are similar just because they come from the same
chapter.

The images are attached in this exact order:
{screenshot_paths}

For EACH frame, in the same order as attached, score the
following, each as an integer 0-10:

1. content_density: how much teaching content (diagram,
   formula, code, written example, labeled illustration, slide text, or bullet points explaining concepts) is
   visible and legible in that frame.
   0 = no teaching content visible at all (blank screen, pure webcam, or logo).
   6-8 = clear, legible slide text, code, or bulleted lecture notes explaining concepts.
   9-10 = rich labeled diagrams, complex equations, or high-value visual illustrations.

2. instructor_occlusion: how much of that frame is taken up by
   the instructor's webcam/video feed rather than the
   whiteboard, slide, or code editor.
   0 = instructor is absent or a tiny corner overlay.
   10 = the instructor's video feed dominates the frame.

3. blur_level: how blurry, out of focus, or hard to read the
   content is, independent of occlusion.
   0 = perfectly sharp and legible.
   10 = illegible due to blur or motion.

Also determine is_transition_or_decorative for that frame: true
if it is a slide transition, a title card, a mostly blank
board, or a decorative moment with no real teaching content,
regardless of its content_density score.

Be honest and use the full range across the batch. Most frames
from a real lecture are mediocre. Do not default to high scores
for every frame.

Return JSON only: a list with exactly one object per attached
frame, in the same order as the frames were attached, matching
this schema exactly:

[
  {{
    "path": "...",
    "content_density": 0,
    "instructor_occlusion": 0,
    "blur_level": 0,
    "is_transition_or_decorative": false
  }}
]

The "path" field for each object must exactly match the
corresponding path from the attached order list above.
"""


SCREENSHOT_SELECTOR_PROMPT = """
You are building a study guide.

Below is a chapter from a lecture, along with its candidate
screenshots. These screenshots have already been pre-filtered
for quality, every one of them contains real teaching content
and is not just the instructor or a blank transition. Your job
now is to rank all of them by relevance to this chapter. Do
not decide how many to keep — rank every single one.

The images are attached in the same order as the paths listed
below.

Chapter title:
{title}

Focus concepts:
{focus_concepts}

Important information:
{important_information}

Lecture notes summary (first few notes, for context on what is
actually being explained):
{lecture_notes}

Candidate screenshot paths (in attached order):
{screenshot_paths}

Rank every candidate screenshot. For each one, provide:

1. path (must exactly match one of the candidate paths above)
2. reason
3. section where it should appear
4. importance, an integer from 1 to 10, where 10 means
   essential to understanding the chapter and 1 means
   marginally useful. Use the full range. Do not give every
   screenshot a high score by default. Screenshots that teach
   essentially the same thing should have noticeably different
   importance scores so they can be ranked apart.

You must return an entry for EVERY candidate path listed above.
Do not omit any.

Return JSON only.

Match this schema exactly:

{{
  "chapter_id": {chapter_id},
  "screenshots": [
    {{
      "path": "...",
      "reason": "...",
      "section": "...",
      "importance": 0
    }}
  ]
}}
"""


# Functions


def dedup_paths(paths: list[str]) -> list[str]:
    """
    Order-preserving path deduplication using normalized path strings.
    """
    seen = set()
    unique = []
    for p in paths:
        norm = os.path.normpath(str(p))
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def chunk_list(

    items,
    chunk_size

):
    """
    Split a list into successive chunks of at most chunk_size.
    The final chunk may be smaller than chunk_size.
    """

    for i in range(

        0,
        len(items),
        chunk_size

    ):

        yield items[i : i + chunk_size]


def compute_target_count(

    original_candidate_count

):
    """
    Return the number of screenshots to keep for a chapter,
    based on how many candidates it started with before any
    filtering. Uses a simple monotonic step function so the
    result is easy to reason about and adjust.

    original candidates    target final count
    ─────────────────────   ──────────────────
    1–8                     3
    9–16                    4
    17–28                   5
    29+                     6
    """

    n = original_candidate_count

    if n <= 8:
        return 3
    elif n <= 16:
        return 4
    elif n <= 28:
        return 5
    else:
        return 6


def load_chapter(

    path

):
    """
    Load a single chapter_N.json from disk.
    """

    with open(

        path,
        "r",
        encoding="utf-8"

    ) as f:

        return json.load(

            f

        )


def load_chapters(

    chapter_dir

):
    """
    Load all chapter_N.json files from chapter_dir.
    """

    chapter_paths = sorted(

        chapter_dir.glob(

            "chapter_*.json"

        )
    )

    chapters = []

    for path in chapter_paths:

        chapter = (

            load_chapter(

                path

            )
        )

        chapter["_source_path"] = str(

            path

        )

        chapters.append(

            chapter

        )

    return chapters


def upload_single_screenshot(

    path

):
    """
    Upload a single screenshot to the Gemini Files API.
    Returns the uploaded file, or None if upload fails or the
    path does not exist.
    """

    if not Path(

        path

    ).exists():

        logger.error(

            f"Screenshot not found, skipping: "
            f"{path}"
        )

        return None

    try:

        return client.files.upload(

            file=path

        )

    except Exception as e:

        logger.error(

            f"Failed to upload "
            f"{path}"
            f": "
            f"{e}"
        )

        return None


def score_frames_batch(

    screenshot_paths,
    chapter_id,
    batch_index

):
    """
    Score a single batch of frames (up to PASS1_BATCH_SIZE) in
    one LLM call. Each frame is scored on its own merits; the
    prompt explicitly tells the model not to compare frames.

    Returns a list of FrameQualityScore objects for frames that
    were successfully uploaded and scored. Frames that could
    not be uploaded or whose entries are malformed are silently
    dropped (errors are logged).
    """

    # ── Reuse visual-extractor analysis instead of re-scoring (ROADMAP P1.3)
    synthesized = []
    unanalyzed = []
    for p in screenshot_paths:
        entry = _VISUAL_ANALYSIS.get(os.path.normpath(str(p)))
        if entry:
            imp = max(0, min(10, int(entry.get("importance_score", 0) or 0)))
            vis_type = (entry.get("visual_type") or "").strip().lower()
            include_in_notes = bool(entry.get("include_in_notes", True))
            synthesized.append(
                FrameQualityScore(
                    path=p,
                    content_density=imp,
                    instructor_occlusion=0,
                    blur_level=0,
                    is_transition_or_decorative=(
                        vis_type in ("", "none") or not include_in_notes or imp <= 0
                    ),
                )
            )
        else:
            unanalyzed.append(p)

    if unanalyzed:
        logger.info(
            f"Chapter {chapter_id} batch {batch_index}: "
            f"{len(synthesized)} frame(s) reused from visual analysis, "
            f"{len(unanalyzed)} to score via LLM."
        )

    if not unanalyzed:
        return synthesized

    screenshot_paths = unanalyzed

    uploaded = upload_screenshots(

        screenshot_paths

    )

    if not uploaded:

        logger.error(

            f"Chapter "
            f"{chapter_id}"
            f" batch "
            f"{batch_index}"
            f": no frames could be uploaded."
        )

        return []

    valid_paths = [

        path
        for path, _ in uploaded

    ]

    paths_text = "\n".join(

        valid_paths

    )

    prompt = FRAME_QUALITY_PROMPT.format(

        screenshot_paths=paths_text

    )

    contents = [prompt] + [

        uploaded_file
        for _, uploaded_file in uploaded

    ]

    last_error = None

    for attempt in range(

        MAX_RETRIES

    ):

        try:
            _limiter.wait()
            response = (

                client.models.generate_content(

                    model=MODEL_NAME,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=FrameQualityBatch,
                    )
                )
            )
            record_generate_usage("screenshot_selection", MODEL_NAME, response)

            try:
                data = json.loads(response.text)
                if isinstance(data, dict) and "scores" in data:
                    raw_scores = data["scores"]
                elif isinstance(data, list):
                    raw_scores = data
                else:
                    raw_scores = []
            except Exception:
                raw_scores = []

            # PRECONDITION: valid_paths must be deduplicated by canonical path upstream (via dedup_paths)
            filename_to_path = {}
            collisions = []
            for p in valid_paths:
                name = Path(p).name
                if name in filename_to_path and filename_to_path[name] != p:
                    collisions.append((name, filename_to_path[name], p))
                filename_to_path[name] = p

            if collisions:
                logger.warning(f"Basename collisions in valid_paths — filename remap may be unsafe: {collisions}")

            scores = []

            for idx, entry in enumerate(raw_scores):

                try:

                    fq_score = FrameQualityScore(**entry)
                    p = fq_score.path
                    if p in valid_paths:
                        pass
                    elif Path(p).name in filename_to_path:
                        remapped = filename_to_path[Path(p).name]
                        logger.info(f"Chapter {chapter_id} Pass 1: Remapped path by filename '{p}' -> '{remapped}'.")
                        fq_score.path = remapped
                    elif idx < len(valid_paths):
                        logger.info(
                            f"Chapter {chapter_id} Pass 1: Remapped synthetic path '{p}' -> '{valid_paths[idx]}' by position."
                        )
                        fq_score.path = valid_paths[idx]

                    scores.append(fq_score)

                except Exception as entry_error:

                    logger.error(

                        f"Chapter "
                        f"{chapter_id}"
                        f" batch "
                        f"{batch_index}"
                        f": skipping malformed Pass 1 "
                        f"entry "
                        f"{entry}"
                        f": "
                        f"{entry_error}"
                    )

            valid_path_set = set(

                valid_paths

            )

            scored_path_set = {

                score.path
                for score in scores

            }

            missing_paths = (

                valid_path_set
                - scored_path_set
            )

            if missing_paths:

                logger.error(

                    f"Chapter "
                    f"{chapter_id}"
                    f" batch "
                    f"{batch_index}"
                    f": Pass 1 response missing scores for "
                    f"{len(missing_paths)}"
                    f" frame(s), treating as failed: "
                    f"{sorted(missing_paths)}"
                )
            scores = [

                score
                for score in scores

                if score.path in valid_path_set

            ]

            return scores + synthesized

        except Exception as e:

            last_error = e

            logger.error(

                f"Chapter "
                f"{chapter_id}"
                f" batch "
                f"{batch_index}"
                f" Pass 1 attempt "
                f"{attempt + 1}"
                f"/"
                f"{MAX_RETRIES}"
                f" failed: "
                f"{e}"
            )

            time.sleep(

                2 ** attempt

            )

    logger.error(

        f"Chapter "
        f"{chapter_id}"
        f" batch "
        f"{batch_index}"
        f": giving up on Pass 1 batch scoring: "
        f"{last_error}"
    )

    return synthesized


def score_all_frames(

    screenshot_paths,
    chapter_id

):
    """
    Pass 1: score every candidate frame for a chapter by
    splitting the paths into batches of PASS1_BATCH_SIZE and
    calling score_frames_batch once per batch. Results from all
    batches are aggregated and returned as a flat list of
    FrameQualityScore objects.

    Using batches of 5 keeps each call small so the model can
    score each frame independently, while avoiding one LLM call
    per frame across chapters that may have dozens of
    candidates.
    """

    all_scores = []

    batches = list(

        chunk_list(

            screenshot_paths,
            PASS1_BATCH_SIZE

        )
    )

    logger.info(

        f"Chapter "
        f"{chapter_id}"
        f": scoring "
        f"{len(screenshot_paths)}"
        f" frames across "
        f"{len(batches)}"
        f" batch(es)."
    )

    for batch_index, batch in enumerate(

        batches,
        start=1

    ):

        batch_scores = score_frames_batch(

            batch,
            chapter_id,
            batch_index

        )

        all_scores.extend(

            batch_scores

        )

    return all_scores


def passes_quality_bar(

    score

):
    """
    Decide whether a single frame's Pass 1 score clears the
    quality bar required to be eligible for selection.
    """

    if score.is_transition_or_decorative:

        return False

    if score.content_density < MIN_CONTENT_DENSITY:

        return False

    if score.instructor_occlusion > MAX_INSTRUCTOR_OCCLUSION:

        return False

    return True


def compute_image_hash(

    path

):
    """
    Compute a perceptual hash for an image on disk. Returns
    None if the image cannot be opened.
    """

    try:

        with PILImage.open(

            path

        ) as img:

            return imagehash.phash(

                img

            )

    except Exception as e:

        logger.error(

            f"Failed to hash image "
            f"{path}"
            f": "
            f"{e}"
        )

        return None


def deduplicate_frames(

    scores

):
    """
    Cluster near-duplicate frames using perceptual hashing and
    keep only the highest content_density frame from each
    cluster. Frames that fail to hash are kept as-is, since we
    cannot safely judge them as duplicates.

    This is a simple greedy clustering: each frame is compared
    against the representatives chosen so far, in descending
    content_density order, so the best frame in any duplicate
    cluster is always the one that survives.
    """

    ranked = sorted(

        scores,
        key=lambda s: s.content_density,
        reverse=True

    )

    kept = []

    kept_hashes = []

    for score in ranked:

        frame_hash = compute_image_hash(

            score.path

        )

        if frame_hash is None:

            kept.append(

                score

            )

            continue

        is_duplicate = False

        for existing_hash in kept_hashes:

            distance = (

                frame_hash
                - existing_hash
            )

            if distance <= DEDUP_HASH_DISTANCE:

                is_duplicate = True

                break

        if is_duplicate:

            logger.info(

                f"Dropping near-duplicate frame: "
                f"{score.path}"
            )

            continue

        kept.append(

            score

        )

        kept_hashes.append(

            frame_hash

        )

    return kept


def filter_candidates(

    screenshot_paths,
    chapter_id

):
    """
    Run the full Pass 1 pipeline for a chapter: score every
    candidate frame in batches, drop frames that fail the
    quality bar, then deduplicate near-identical survivors.

    Returns a tuple of:
      - surviving_paths: list of paths ranked by content_density
      - original_count: the total number of candidate frames
        before any filtering (used by compute_target_count)
    """

    original_count = len(

        screenshot_paths

    )

    scores = score_all_frames(

        screenshot_paths,
        chapter_id

    )

    if not scores:

        logger.error(

            f"Chapter "
            f"{chapter_id}"
            f": no frames could be scored."
        )

        return [], original_count

    eligible = [

        score
        for score in scores
        if passes_quality_bar(score)

    ]

    logger.info(

        f"Chapter "
        f"{chapter_id}"
        f": "
        f"{len(eligible)}"
        f"/"
        f"{len(scores)}"
        f" frames passed the quality bar."
    )

    if not eligible:

        return [], original_count

    deduplicated = deduplicate_frames(

        eligible

    )

    logger.info(

        f"Chapter "
        f"{chapter_id}"
        f": "
        f"{len(deduplicated)}"
        f"/"
        f"{len(eligible)}"
        f" survived deduplication."
    )

    ranked = sorted(

        deduplicated,
        key=lambda s: s.content_density,
        reverse=True

    )

    surviving_paths = [

        score.path
        for score in ranked

    ]

    return surviving_paths, original_count


def upload_screenshots(
    screenshot_paths
):
    """
    Upload each screenshot concurrently to the Gemini Files API.

    Returns a list of (path, uploaded_file) tuples in original order,
    skipping any paths that fail to upload or do not exist.
    """
    if not screenshot_paths:
        return []

    with ThreadPoolExecutor(max_workers=min(len(screenshot_paths), 6)) as executor:
        results = list(executor.map(upload_single_screenshot, screenshot_paths))

    uploaded = []
    for path, uploaded_file in zip(screenshot_paths, results):
        if uploaded_file is not None:
            uploaded.append((path, uploaded_file))

    return uploaded


def build_prompt(

    chapter,
    chapter_id,
    screenshot_paths

):
    """
    Build the screenshot ranking prompt for a given chapter.
    The model is asked to rank every survivor by importance;
    the target count is determined later in code.
    """

    focus_concepts = (

        json.dumps(

            chapter.get(
                "focus_concepts",
                []
            ),
            indent=2,
            ensure_ascii=False
        )
    )

    important_information = (

        json.dumps(

            chapter.get(
                "important_information",
                []
            ),
            indent=2,
            ensure_ascii=False
        )
    )

    lecture_notes = (

        json.dumps(

            chapter.get(
                "lecture_notes",
                []
            )[:LECTURE_NOTES_PREVIEW_COUNT],
            indent=2,
            ensure_ascii=False
        )
    )

    screenshot_paths_text = (

        "\n".join(

            screenshot_paths

        )
    )

    return SCREENSHOT_SELECTOR_PROMPT.format(

        title=chapter.get(
            "title",
            ""
        ),
        focus_concepts=focus_concepts,
        important_information=important_information,
        lecture_notes=lecture_notes,
        screenshot_paths=screenshot_paths_text,
        chapter_id=chapter_id
    )


def select_top_k(

    ranked_selection,
    target_count

):
    """
    Deterministically pick the top target_count screenshots
    from a ChapterScreenshots object by sorting on importance
    (descending) and slicing. The model ranked every survivor;
    this function does the final count-based cut in code so the
    LLM never has to decide how many to keep.

    Returns a new ChapterScreenshots with at most target_count
    screenshots.
    """

    sorted_screenshots = sorted(

        ranked_selection.screenshots,
        key=lambda s: s.importance,
        reverse=True

    )

    top_k = sorted_screenshots[:target_count]

    return ChapterScreenshots(

        chapter_id=ranked_selection.chapter_id,
        screenshots=top_k

    )


def generate_selection(

    chapter,
    chapter_id

):
    """
    Run Pass 1 quality filtering, then call the LLM with
    chapter context and the surviving screenshots for Pass 2
    ranking. Returns a tuple of (raw_response_text,
    original_candidate_count, valid_paths), or (None, original_count, [])
    if the chapter should be skipped.

    The caller is responsible for parsing the raw text and
    applying the deterministic top-K cut using
    compute_target_count(original_candidate_count).
    """

    screenshot_paths = dedup_paths(
        chapter.get(
            "screenshots",
            []
        )
    )

    if not screenshot_paths:

        logger.info(

            f"Chapter "
            f"{chapter_id}"
            f" has no screenshots, skipping."
        )

        return None, 0, []

    surviving_paths, original_count = filter_candidates(

        screenshot_paths,
        chapter_id

    )

    if not surviving_paths:

        logger.info(

            f"Chapter "
            f"{chapter_id}"
            f": no candidates survived Pass 1 filtering."
        )

        return None, original_count, []

    uploaded = (

        upload_screenshots(

            surviving_paths

        )
    )

    if not uploaded:

        logger.error(

            f"Chapter "
            f"{chapter_id}"
            f": no screenshots could be uploaded for Pass 2."
        )

        return None, original_count, []

    valid_paths = [

        path
        for path, _ in uploaded

    ]

    prompt = (

        build_prompt(

            chapter,
            chapter_id,
            valid_paths

        )
    )

    contents = [prompt] + [

        uploaded_file
        for _, uploaded_file in uploaded

    ]

    last_error = None

    for attempt in range(

        MAX_RETRIES

    ):

        try:
            _limiter.wait()
            response = (

                client.models.generate_content(

                    model=MODEL_NAME,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=ChapterScreenshots,
                    )
                )
            )
            record_generate_usage("screenshot_selection", MODEL_NAME, response)

            return response.text, original_count, valid_paths

        except Exception as e:

            last_error = e

            logger.error(

                f"Chapter "
                f"{chapter_id}"
                f" Pass 2 attempt "
                f"{attempt + 1}"
                f"/"
                f"{MAX_RETRIES}"
                f" failed: "
                f"{e}"
            )

            time.sleep(5 * (attempt + 1) + random.uniform(0.5, 3.0))

    raise RuntimeError(

        f"All retries failed for chapter "
        f"{chapter_id}"
        f": "
        f"{last_error}"
    )


def parse_selection(

    raw_text,
    chapter_id,
    valid_paths=None

):
    """
    Parse and validate the LLM response into ChapterScreenshots.
    """

    cleaned = (

        raw_text

        .strip()

        .removeprefix("```json")

        .removeprefix("```")

        .removesuffix("```")

        .strip()
    )

    data = json.loads(

        cleaned

    )

    data["chapter_id"] = chapter_id

    # PRECONDITION: valid_paths must be deduplicated by canonical path upstream (via dedup_paths)
    if valid_paths and "screenshots" in data and isinstance(data["screenshots"], list):
        filename_to_path = {}
        collisions = []
        for vp in valid_paths:
            name = Path(vp).name
            if name in filename_to_path and filename_to_path[name] != vp:
                collisions.append((name, filename_to_path[name], vp))
            filename_to_path[name] = vp

        if collisions:
            logger.warning(f"Pass 2: Basename collisions in valid_paths — filename remap may be unsafe: {collisions}")

        valid_set = set(valid_paths)
        for idx, shot in enumerate(data["screenshots"]):
            if isinstance(shot, dict):
                p = shot.get("path", "")
                if p in valid_set:
                    pass
                elif Path(p).name in filename_to_path:
                    remapped = filename_to_path[Path(p).name]
                    logger.info(f"Chapter {chapter_id} Pass 2: Remapped path by filename '{p}' -> '{remapped}'.")
                    shot["path"] = remapped
                elif idx < len(valid_paths):
                    logger.info(
                        f"Chapter {chapter_id} Pass 2: Remapped synthetic path '{p}' -> '{valid_paths[idx]}' by position."
                    )
                    shot["path"] = valid_paths[idx]

    return ChapterScreenshots(

        **data

    )


def save_selection(

    selection,
    chapter_id

):
    """
    Save the selection to
    outputs/screenshots/chapter_N_screenshots.json
    """

    SCREENSHOTS_OUT_DIR.mkdir(

        parents=True,
        exist_ok=True
    )

    out_path = (

        SCREENSHOTS_OUT_DIR
        / f"chapter_{chapter_id}_screenshots.json"
    )

    with open(

        out_path,
        "w",
        encoding="utf-8"

    ) as f:

        json.dump(

            selection.model_dump(),
            f,
            indent=2,
            ensure_ascii=False
        )

    logger.info(

        f"Saved selection to "
        f"{out_path}"
    )


def process_chapter(

    chapter,
    chapter_id

):
    """
    Run the full selection pipeline for a single chapter:
    Pass 1 (batched quality scoring + dedup) → Pass 2 (ranking)
    → deterministic top-K cut → save.
    """

    # ── Cache: skip if this chapter's selection already exists for the same
    # ── inputs (re-runs cost ~0 API calls). See ROADMAP P1.4.
    out_path = SCREENSHOTS_OUT_DIR / f"chapter_{chapter_id}_screenshots.json"
    marker = SCREENSHOTS_OUT_DIR / f".selection_ch{chapter_id}.sha256"
    if outputs_current(marker, [out_path], chapter, _VISUAL_ANALYSIS):
        logger.info(
            f"Chapter {chapter_id} screenshot selection: up to date, skipping"
        )
        return

    raw_text, original_count, valid_paths = (

        generate_selection(

            chapter,
            chapter_id

        )
    )

    if raw_text is None:

        return

    ranked_selection = (

        parse_selection(

            raw_text,
            chapter_id,
            valid_paths=valid_paths

        )
    )

    target_count = compute_target_count(

        original_count

    )

    logger.info(

        f"Chapter "
        f"{chapter_id}"
        f": original candidate count = "
        f"{original_count}"
        f", target final count = "
        f"{target_count}"
        f", ranked survivors = "
        f"{len(ranked_selection.screenshots)}"
    )

    final_selection = select_top_k(

        ranked_selection,
        target_count

    )

    save_selection(

        final_selection,
        chapter_id

    )

    write_marker(marker, chapter, _VISUAL_ANALYSIS)


def main():

    logger.info(

        f"Using model: "
        f"{MODEL_NAME}"
        )

    SCREENSHOTS_OUT_DIR.mkdir(

        parents=True,
        exist_ok=True
    )

    chapters = (

        load_chapters(

            CHAPTER_DIR

        )
    )

    with ThreadPoolExecutor(

        max_workers=
        MAX_WORKERS

    ) as executor:

        futures = {

            executor.submit(
                process_chapter,
                chapter,
                index + 1
            ): index + 1

            for index, chapter
            in enumerate(chapters)
        }

        completed = 0

        total = len(

            futures

        )

        for future in (

            as_completed(

                futures

            )
        ):

            chapter_id = futures[future]

            try:

                future.result()

            except Exception as e:

                logger.error(

                    f"Chapter "
                    f"{chapter_id}"
                    f" failed: "
                    f"{e}"
                )

            completed += 1

            logger.info(

                f"Progress: "
                f"{completed}"
                f"/"
                f"{total}"
            )

    logger.info(

        "Screenshot selection complete."
    )

def select_screenshots_for_lecture(
    chapters_dir: str,
    output_dir: str,
    max_workers: int = 7,
) -> dict:
    """
    Run the full screenshot selection pipeline for every chapter,
    writing results into {output_dir}/screenshots/selected/.

    Args:
        chapters_dir: directory containing chapter_*.json files.
        output_dir:   base lecture directory.
        max_workers:  number of parallel chapter workers.

    Returns:
        { "selections_dir": str, "num_chapters": int }
    """
    import notes.screenshot_selector as _sel
    _sel.CHAPTER_DIR = Path(chapters_dir)
    selections_dir = Path(output_dir) / "screenshots" / "selected"
    selections_dir.mkdir(parents=True, exist_ok=True)
    _sel.SCREENSHOTS_OUT_DIR = selections_dir

    # Reuse the visual-extractor's per-frame analysis (Stage 9) so Pass 1
    # doesn't re-upload/re-score the same keyframes (ROADMAP P1.3).
    _sel.load_visual_analysis(output_dir)

    chapters = _sel.load_chapters(_sel.CHAPTER_DIR)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_sel.process_chapter, ch, idx + 1): idx + 1
            for idx, ch in enumerate(chapters)
        }
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            chapter_id = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Chapter {chapter_id} failed: {e}")
            completed += 1
            logger.info(f"Screenshot selection progress: {completed}/{total}")

    return {
        "selections_dir": str(selections_dir),
        "num_chapters": len(chapters),
    }


if __name__ == "__main__":

    main()