import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import time
import random
from visual.visual_prompts import (
    VISUAL_PROMPT
)
from visual.visual_models import VisualChunkKnowledgeModel
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
from pydantic import BaseModel, Field
from backend.ratelimit import rate_limiter as _limiter
from config import MODEL_NAME, DEFAULT_MAX_RETRIES
from cache_util import outputs_current, write_marker

logger = logging.getLogger(__name__)



# Gemini / Gemma Client

load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found."
    )
client = genai.Client(
    api_key=API_KEY
)


# Load Mapping


def load_mapping(
    mapping_path
):
    """
    Load chunk screenshot mapping.
    """

    with open(
        mapping_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



# Upload Images


def upload_images(
    image_paths
):
    """
    Upload screenshots concurrently to Google AI Studio Files API.
    """
    if not image_paths:
        return []

    def _upload(p):
        logger.info(f"Uploading: {p}")
        return client.files.upload(file=p)

    with ThreadPoolExecutor(max_workers=min(len(image_paths), 6)) as executor:
        return list(executor.map(_upload, image_paths))



# Visual Analysis


def analyze_chunk_images(
    image_paths
):
    """
    Analyze screenshots belonging
    to a single chunk.
    """

    uploaded_files = upload_images(
        image_paths
    )

    image_listing = []

    for idx, path in enumerate(
        image_paths
    ):

        image_listing.append(
            f"{idx}: "
            f"{Path(path).name}"
        )

    enhanced_prompt = (
        VISUAL_PROMPT
        + "\n\n"
        + "Screenshot Index Mapping:\n"
        + "\n".join(image_listing)
    )

    for attempt in range(DEFAULT_MAX_RETRIES):

        try:
            _limiter.wait()
            response = (
                client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        *uploaded_files,
                        enhanced_prompt
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=VisualChunkKnowledgeModel,
                    )
                )
            )

            return response.text

        except Exception as e:

            logger.warning(
                f"Attempt "
                f"{attempt + 1} failed: "
                f"{e}"
            )

            time.sleep(
                5 * (attempt + 1)
            )

    raise RuntimeError(
        f"Gemma failed after {DEFAULT_MAX_RETRIES} attempts."
    )

    return response.text



# JSON Cleanup


def parse_response(
    response_text
):
    """
    Parse model JSON safely.
    """

    response_text = (
        response_text
        .replace(
            "```json",
            ""
        )
        .replace(
            "```",
            ""
        )
        .strip()
    )


    response_text = (
        response_text
        .replace(
            "\\",
            "\\\\"
        )
    )

    try:

        visual_object = json.loads(
            response_text
        )

    except json.JSONDecodeError:

        logger.error(
            response_text
        )

        raise

    required_fields = {

        "visual_summary": "",

        "visual_notes": "",

        "ocr_text": "",

        "concepts": [],

        "note_worthy_concepts": [],

        "important_information": [],

        "formulas": [],

        "code_snippets": [],

        "visual_type": "",

        "teaching_stage": "",

        "importance_score": 0,

        "importance_reason": "",

        "include_in_notes": False,

        "selected_image_indices": []
    }

    for key, default in (
        required_fields.items()
    ):

        visual_object.setdefault(
            key,
            default
        )

    return visual_object


def validate_visual_object(
    visual_object
):
    """
    Validate and normalize
    visual object fields.
    """

    score = visual_object.get(
        "importance_score",
        0
    )

    if not isinstance(
        score,
        (int, float)
    ):
        score = 5

    score = max(
        1,
        min(
            int(score),
            10
        )
    )

    visual_object[
        "importance_score"
    ] = score

    return visual_object

# Extract Visual Object


def extract_visual_object(
    chunk_mapping
):
    """
    Create visual object for
    a single chunk.
    """

    screenshots = (
        chunk_mapping[
            "screenshots"
        ]
    )

    if not screenshots:

        logger.warning(
            f"Chunk "
            f"{chunk_mapping['chunk_id']} "
            f"has no screenshots."
        )

        return None

    image_paths = [

        screenshot[
            "image_path"
        ]

        for screenshot
        in screenshots
    ]

    screenshot_timestamps = [

        screenshot[
            "timestamp"
        ]

        for screenshot
        in screenshots
    ]

    MAX_ATTEMPTS = 5

    for attempt in range(
        MAX_ATTEMPTS
    ):

        try:

            logger.info(
                f"Chunk "
                f"{chunk_mapping['chunk_id']} "
                f"attempt "
                f"{attempt + 1}/"
                f"{MAX_ATTEMPTS}"
            )

            response_text = (
                analyze_chunk_images(
                    image_paths
                )
            )

            visual_object = (
                parse_response(
                    response_text
                )
            )

            visual_object = (
                validate_visual_object(
                    visual_object
                )
            )

            break

        except Exception as e:

            logger.warning(
                f"Chunk "
                f"{chunk_mapping['chunk_id']} "
                f"attempt "
                f"{attempt + 1} failed: "
                f"{e}"
            )

    else:

        raise RuntimeError(
            f"Chunk "
            f"{chunk_mapping['chunk_id']} "
            f"failed after "
            f"{MAX_ATTEMPTS} attempts."
        )

    visual_object = (
        validate_visual_object(
            visual_object
        )
    )
    

    # ----------------------------------
    # Source Data
    # ----------------------------------

    visual_object[
        "source_screenshots"
    ] = image_paths

    visual_object[
        "screenshot_timestamps"
    ] = screenshot_timestamps

    # ----------------------------------
    # Chunk Metadata
    # ----------------------------------

    visual_object[
        "chunk_id"
    ] = (
        chunk_mapping[
            "chunk_id"
        ]
    )

    visual_object[
        "start"
    ] = (
        chunk_mapping[
            "start"
        ]
    )

    visual_object[
        "end"
    ] = (
        chunk_mapping[
            "end"
        ]
    )

    visual_object[
        "screenshot_count"
    ] = len(
        screenshots
    )


    visual_object[
        "object_type"
    ] = (
        "visual_object"
    )

    visual_object[
        "generated_by"
    ] = (
        MODEL_NAME
    )

    return visual_object


def process_chunk(
    chunk_mapping,
    output_dir
):
    """
    Process one chunk.
    """

    chunk_id = chunk_mapping[
        "chunk_id"
    ]

    try:

        logger.info(
            f"Starting chunk "
            f"{chunk_id}"
        )

        output_file = (
            Path(output_dir)
            /
            f"chunk_{chunk_id}_visual.json"
        )

        if output_file.exists():

            logger.info(
                f"Skipping chunk "
                f"{chunk_id}"
            )

            return True
        
        time.sleep(
            random.uniform(
                0.5,
                2
            )
        )


        visual_object = (
            extract_visual_object(
                chunk_mapping
            )
        )

        if visual_object:

            save_visual_object(
                visual_object,
                output_dir
            )

        logger.info(
            f"Finished chunk "
            f"{chunk_id}"
        )

        return True

    except Exception as e:

        logger.error(
            f"Chunk {chunk_id} failed: "
            f"{e}"
        )

        return False

# Save


def save_visual_object(
    visual_object,
    output_dir
):
    """
    Save visual object.
    """

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    chunk_id = (
        visual_object[
            "chunk_id"
        ]
    )

    output_path = (
        output_dir /
        f"chunk_{chunk_id}_visual.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            visual_object,
            f,
            indent=4,
            ensure_ascii=False,
            sort_keys=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )

    return output_path


class VisualObjectItem(BaseModel):
    chunk_id: int
    start: float = 0.0
    end: float = 0.0
    visual_notes: str
    important_information: list[str]
    ocr_text: str
    visual_summary: str
    visual_type: str
    teaching_stage: str
    importance_score: int
    include_in_notes: bool
    source_screenshots: list[str] = []


class ChapterVisualKnowledgeModel(BaseModel):
    chapter_id: int
    incomplete: bool = Field(default=False)
    visual_objects: list[VisualObjectItem]


def create_empty_visual_object(chunk_mapping: dict) -> dict:
    """
    Create a valid fallback/empty visual object for a chunk with 0 screenshots or on batch failure.
    """
    return {
        "chunk_id": chunk_mapping.get("chunk_id", 0),
        "start": chunk_mapping.get("start", 0.0),
        "end": chunk_mapping.get("end", 0.0),
        "visual_notes": "",
        "important_information": [],
        "ocr_text": "",
        "visual_summary": "",
        "visual_type": "none",
        "teaching_stage": "none",
        "importance_score": 0,
        "include_in_notes": False,
        "source_screenshots": [],
        "screenshot_count": 0,
        "object_type": "visual_object",
        "generated_by": MODEL_NAME,
        "incomplete": False,
    }


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


def process_chapter_visual_batch(chapter_id: int, chapter_title: str, chapter_chunks: list[dict], output_dir: str):
    """
    Process candidate screenshots for a single chapter strictly within chapter boundaries.
    If call fails after retries, marks incomplete=True and saves empty fallback objects.
    """
    all_image_paths = []
    chunk_image_map = {}
    chunk_ids = [c["chunk_id"] for c in chapter_chunks]
    
    for c in chapter_chunks:
        c_id = c["chunk_id"]
        shots = [
            p for s in c.get("screenshots", [])
            if (p := (s.get("image_path") or s.get("path"))) and Path(p).exists()
        ]
        chunk_image_map[c_id] = shots
        all_image_paths.extend(shots)

    all_image_paths = dedup_paths(all_image_paths)

    if not all_image_paths:
        for c in chapter_chunks:
            fallback = create_empty_visual_object(c)
            save_visual_object(fallback, output_dir)
        return

    uploaded_files = upload_images(all_image_paths)
    
    prompt = f"""
Analyze the candidate screenshots for Chapter {chapter_id}: "{chapter_title}" covering chunks {chunk_ids}.
For each chunk with screenshots in this chapter, extract concise visual notes, OCR text, visual summary, and importance score.

Return a JSON matching ChapterVisualKnowledgeModel.
"""

    for attempt in range(DEFAULT_MAX_RETRIES):
        try:
            _limiter.wait()
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[*uploaded_files, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=ChapterVisualKnowledgeModel,
                )
            )
            if not response or not response.text:
                raise ValueError("Gemini returned empty or blocked response (response.text is None)")
            data = json.loads(response.text)
            batch_result = ChapterVisualKnowledgeModel(**data)
            
            # Save visual objects for each chunk in chapter
            processed_chunk_ids = set()
            chunk_times = {c["chunk_id"]: c for c in chapter_chunks}
            for vo in batch_result.visual_objects:
                obj_dict = vo.model_dump()
                obj_dict["start"] = chunk_times.get(vo.chunk_id, {}).get("start", 0.0)
                obj_dict["end"] = chunk_times.get(vo.chunk_id, {}).get("end", 0.0)
                obj_dict["source_screenshots"] = chunk_image_map.get(vo.chunk_id, [])
                obj_dict["object_type"] = "visual_object"
                obj_dict["generated_by"] = MODEL_NAME
                save_visual_object(obj_dict, output_dir)
                processed_chunk_ids.add(vo.chunk_id)

            # Persist per-frame analysis so screenshot selection (Stage 12)
            # can reuse it instead of re-uploading + re-scoring the same
            # keyframes. See ROADMAP P1.3. Only genuinely analyzed chunks get
            # entries; fallback chunks are left out so selection falls back to
            # its own Pass 1 LLM scoring for their frames.
            frames = {}
            for vo in batch_result.visual_objects:
                for path in chunk_image_map.get(vo.chunk_id, []):
                    frames[os.path.normpath(str(path))] = {
                        "ocr_text": vo.ocr_text,
                        "importance_score": vo.importance_score,
                        "visual_type": vo.visual_type,
                        "include_in_notes": vo.include_in_notes,
                    }
            if frames:
                analysis_path = Path(output_dir) / f"visual_analysis_ch{chapter_id}.json"
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump({"chapter_id": chapter_id, "frames": frames}, f, indent=2, ensure_ascii=False)
                logger.info(f"Chapter {chapter_id}: persisted analysis for {len(frames)} frame(s).")

            # Fallback for any chunks in chapter missing from LLM response
            for c in chapter_chunks:
                if c["chunk_id"] not in processed_chunk_ids:
                    fallback = create_empty_visual_object(c)
                    save_visual_object(fallback, output_dir)
            return
        except Exception as e:
            logger.warning(f"Chapter {chapter_id} visual batch attempt {attempt+1} failed: {e}")
            time.sleep(2 * (attempt + 1))

    # Graceful degradation on failure: write incomplete fallback objects for this chapter
    logger.error(f"Chapter {chapter_id} visual batch failed after 3 retries. Marking incomplete.")
    for c in chapter_chunks:
        fallback = create_empty_visual_object(c)
        fallback["incomplete"] = True
        save_visual_object(fallback, output_dir)


def process_all_chunks(
    mapping_path,
    output_dir,
    outline_path=None,
    max_workers=3
):
    """
    Process visual candidate images batched strictly within real chapter boundaries (1 call per chapter).

    Hash-of-inputs cache (ROADMAP P1.4): if the same mapping + outline already
    produced this stage's outputs (visual objects + per-frame analysis), the
    stage is skipped so re-runs cost ~0 API calls. The orchestrator preserves
    ``output_dir`` across runs for exactly this reason.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_outputs = sorted(
        list(output_dir.glob("chunk_*.json"))
        + list(output_dir.glob("visual_analysis_ch*.json"))
    )
    marker = output_dir / ".visual_extract.sha256"
    if outputs_current(marker, existing_outputs, mapping_path, outline_path):
        logger.info(
            f"Visual extraction for {output_dir.name}: up to date, skipping "
            f"({len(existing_outputs)} output file(s) reused)."
        )
        return

    mapping = load_mapping(mapping_path)
    chunk_map = {c["chunk_id"]: c for c in mapping}
    logger.info(f"Loaded {len(mapping)} chunks for chapter-aligned visual extraction.")

    # Locate lecture_outline.json to discover real chapter boundaries
    if not outline_path:
        possible_outline = Path(output_dir).parent / "notes" / "lecture_outline.json"
        if possible_outline.exists():
            outline_path = str(possible_outline)

    chapter_batches = []
    if outline_path and Path(outline_path).exists():
        with open(outline_path, "r", encoding="utf-8") as f:
            outline_data = json.load(f)
        for ch in outline_data.get("chapters", []):
            ch_id = ch["chapter_id"]
            ch_title = ch.get("title", f"Chapter {ch_id}")
            c_ids = ch.get("chunk_ids")
            if c_ids is None:
                s_chunk = ch.get("start_chunk", 0)
                e_chunk = ch.get("end_chunk", s_chunk)
                c_ids = list(range(s_chunk, e_chunk + 1))
            ch_chunks = [chunk_map[cid] for cid in c_ids if cid in chunk_map]
            if ch_chunks:
                chapter_batches.append((ch_id, ch_title, ch_chunks))
    else:
        # Fallback: if outline not found, group by 4-chunk boundaries
        batch_size = 4
        chunks_list = list(mapping)
        for idx, i in enumerate(range(0, len(chunks_list), batch_size)):
            b_chunks = chunks_list[i:i + batch_size]
            chapter_batches.append((idx + 1, f"Chapter Batch {idx+1}", b_chunks))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_chapter_visual_batch, ch_id, ch_title, ch_chunks, str(output_dir))
            for ch_id, ch_title, ch_chunks in chapter_batches
        ]
        for future in as_completed(futures):
            future.result()

    write_marker(marker, mapping_path, outline_path)
    logger.info(f"Chapter-aligned visual extraction complete ({len(chapter_batches)} chapters processed).")


def process_visual_chunks(mapping_path: str, output_dir: str, outline_path: str = None):
    """Alias for backend orchestrator compatibility."""
    return process_all_chunks(mapping_path, output_dir, outline_path=outline_path)


# Example Usage


if __name__ == "__main__":

    process_all_chunks(

        mapping_path=
        "outputs/mappings/"
        "chunk_screenshot_mapping.json",

        output_dir=
        "outputs/visual_objects",

        max_workers=7
    )