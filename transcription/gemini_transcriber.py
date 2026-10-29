"""
transcription/gemini_transcriber.py

Cloud-based audio transcription using Google AI Studio Gemini API (gemini-3.1-flash-lite).
Supports single-file transcription for short lectures (<18 mins) and automated parallel
FFmpeg chunking for long lectures (18–120+ mins). The model writes one compact
"[MM:SS] text" line per sentence (see parse_compact_transcript).
"""

import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from config import (
    MODEL_NAME,
    NORAI_AUDIO_CHUNK_MINUTES,
)
from backend.gemini_client import get_client, invoke_with_policy
from backend.usage_ledger import record_generate_usage
from transcription.transcribe import (
    load_metadata,
    save_txt_transcript,
    save_json_transcript,
)

logger = logging.getLogger(__name__)


# ── Compact line format ──────────────────────────────────────────────────────
# JSON segments spent most output tokens on keys, ids and end times (11.3k
# output tokens for ~3.9k tokens of speech on a 17-min lecture), and their
# float-seconds timestamps drifted by up to a minute. The compact format is one
# "[MM:SS] text" line per sentence (-60% output tokens, median error 0.4 s
# against YouTube captions); end = next line's start.

_COMPACT_LINE = re.compile(r"^\s*\[(\d+(?::\d{1,2}){0,2}(?:\.\d+)?)\]\s*(.*)$")
# A sentence ends no later than this after it starts (words x seconds + slack),
# so a long silence before the next line doesn't stretch its end time.
_SECONDS_PER_WORD = 0.6


def _parse_ts(raw: str) -> float:
    """'83.4', '1:23.4' or '1:01:23' → seconds."""
    total = 0.0
    for part in raw.split(":"):
        total = total * 60 + float(part)
    return total


def parse_compact_transcript(text: str, duration: float) -> list[dict[str, Any]]:
    """Parse "[start] text" lines into segments relative to the clip start.

    Untimed lines continue the previous segment; timestamps are clamped to
    [0, duration] and forced non-decreasing.
    """
    rows: list[list] = []  # [start, text]
    for line in text.splitlines():
        m = _COMPACT_LINE.match(line)
        if m:
            start = min(max(_parse_ts(m.group(1)), 0.0), duration)
            if rows:
                start = max(start, rows[-1][0])
            if m.group(2).strip():
                rows.append([start, m.group(2).strip()])
        elif line.strip() and rows:
            rows[-1][1] += " " + line.strip()

    segments = []
    for i, (start, body) in enumerate(rows):
        next_start = rows[i + 1][0] if i + 1 < len(rows) else duration
        end = min(next_start, start + 1.0 + _SECONDS_PER_WORD * len(body.split()))
        end = max(end, start)
        segments.append({"start": round(start, 2), "end": round(end, 2), "text": body})
    return segments


# ── Gemini Client Helper ─────────────────────────────────────────────────────

def _get_gemini_client() -> genai.Client:
    return get_client()


# ── Audio Slicing Helper ─────────────────────────────────────────────────────

def slice_audio_for_transcription(
    audio_path: str,
    total_duration_sec: float,
    chunk_minutes: int = NORAI_AUDIO_CHUNK_MINUTES,
    temp_dir: str | Path = "outputs/audio_slices",
) -> list[dict[str, Any]]:
    """
    Split audio file into sequential chunks using ffmpeg stream copy.
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    chunk_duration_sec = chunk_minutes * 60
    slices = []
    current_start = 0.0
    slice_idx = 0

    while current_start < total_duration_sec:
        current_end = min(current_start + chunk_duration_sec, total_duration_sec)
        dur = current_end - current_start
        stem = Path(audio_path).stem
        slice_path = temp_dir / f"{stem}_slice_{slice_idx}_{int(current_start)}_{int(current_end)}.mp3"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(current_start),
            "-t", str(dur),
            "-i", audio_path,
            "-c", "copy",
            str(slice_path),
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            logger.warning(f"Fast audio slice copy failed, trying full encode: {e}")
            cmd_fallback = [
                "ffmpeg", "-y",
                "-ss", str(current_start),
                "-t", str(dur),
                "-i", audio_path,
                "-ar", "16000", "-ac", "1", "-b:a", "64k",
                str(slice_path),
            ]
            subprocess.run(cmd_fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        slices.append({
            "index": slice_idx,
            "start_offset": current_start,
            "end_offset": current_end,
            "duration": dur,
            "file_path": str(slice_path),
        })
        current_start = current_end
        slice_idx += 1

    return slices


# ── Single Slice Transcription Worker ────────────────────────────────────────

def _transcribe_audio_slice(
    client: genai.Client,
    slice_info: dict[str, Any],
    model_name: str = MODEL_NAME,
) -> list[dict[str, Any]]:
    """
    Upload one audio chunk to Gemini File API, request a compact "[MM:SS] text"
    transcription, and adjust segment timestamps with start_offset.
    """
    slice_idx = slice_info["index"]
    start_offset = slice_info["start_offset"]
    file_path = slice_info["file_path"]
    duration = slice_info["duration"]

    logger.info(
        f"Uploading audio slice {slice_idx+1} ({start_offset/60:.1f}m - {slice_info['end_offset']/60:.1f}m, "
        f"{os.path.getsize(file_path)/1024/1024:.2f} MB)..."
    )
    t0 = time.perf_counter()
    audio_upload = client.files.upload(file=file_path)
    t_upload = time.perf_counter() - t0
    logger.info(f"Audio slice {slice_idx+1} uploaded in {t_upload:.2f}s: {audio_upload.name}")

    prompt = (
        f"Transcribe the attached audio clip (~{duration:.0f} seconds) verbatim, from start to finish.\n"
        f"Output plain text only: one line per sentence, each line starting with the time the "
        f"sentence begins, as [MM:SS] (minutes:seconds from the start of the clip). Example:\n"
        f"[00:00] Hello everyone.\n[00:03] Today we look at dynamic programming.\n"
        f"[01:12] The first idea is overlapping subproblems.\n"
        f"Rules: no headings, speaker labels or commentary; transcribe technical terms, acronyms, "
        f"math and code accurately; do not summarize or stop early."
    )
    config = types.GenerateContentConfig(temperature=0.1, max_output_tokens=65536)

    contents_payload: Any = [audio_upload, prompt]

    def _generate_once() -> Any:
        response = client.models.generate_content(
            model=model_name,
            contents=contents_payload,
            config=config,
        )
        record_generate_usage("transcription", model_name, response)
        return response

    # Shared retry/RPM policy (backend.gemini_client): RPM-gated attempts,
    # exponential backoff + jitter, ValueError treated as terminal.
    response = invoke_with_policy(_generate_once, node=f"Audio slice {slice_idx+1}")

    # Clean up uploaded file from Gemini Files API
    try:
        if audio_upload and audio_upload.name:
            client.files.delete(name=audio_upload.name)
    except Exception as e:
        logger.warning(f"Failed to delete uploaded file {audio_upload.name if audio_upload else 'unknown'}: {e}")

    if not response or not response.text:
        raise RuntimeError(f"Transcription failed for audio slice {slice_idx+1}")

    raw_segments = parse_compact_transcript(response.text, duration)

    adjusted_segments = []
    for s in raw_segments:
        adjusted_segments.append({
            "segment_id": s.get("segment_id", 0),
            "start": round(start_offset + float(s.get("start", 0.0)), 2),
            "end": round(start_offset + float(s.get("end", 0.0)), 2),
            "duration": round(float(s.get("end", 0.0)) - float(s.get("start", 0.0)), 2),
            "text": str(s.get("text", "")).strip(),
        })

    return adjusted_segments


# ── Main Entry Point ─────────────────────────────────────────────────────────

def transcribe_with_gemini(
    audio_path: str,
    metadata_path: str,
    output_dir: str,
    model_name: str = MODEL_NAME,
    chunk_minutes: int = NORAI_AUDIO_CHUNK_MINUTES,
) -> dict[str, Any]:
    """
    Transcribe audio via Google AI Studio Gemini API.
    Splits audio into parallel chunks if duration > chunk_minutes.
    Produces identical JSON and TXT transcript files matching Faster-Whisper output format.
    """
    logger.info(f"Starting Gemini transcription for: {audio_path} using {model_name}")
    t_start = time.perf_counter()

    metadata = load_metadata(metadata_path)
    duration = float(metadata.get("duration", 0.0))

    if duration <= 0:
        # Fallback: probe with ffmpeg if metadata missing duration
        try:
            import ffmpeg
            probe = ffmpeg.probe(audio_path)
            duration = float(probe["format"]["duration"])
            metadata["duration"] = duration
        except Exception as e:
            logger.warning(f"Could not probe audio duration, defaulting to single-call: {e}")
            duration = chunk_minutes * 60.0

    client = _get_gemini_client()
    chunk_duration_sec = chunk_minutes * 60

    if duration <= chunk_duration_sec:
        # Single slice transcription
        logger.info(f"Audio duration ({duration:.1f}s) <= {chunk_duration_sec}s; running single-call transcription.")
        slice_info = {
            "index": 0,
            "start_offset": 0.0,
            "end_offset": duration,
            "duration": duration,
            "file_path": audio_path,
        }
        all_segments = _transcribe_audio_slice(client, slice_info, model_name=model_name)
    else:
        # Parallel chunked transcription
        temp_slice_dir = Path(output_dir) / "audio_slices"
        slices = slice_audio_for_transcription(
            audio_path=audio_path,
            total_duration_sec=duration,
            chunk_minutes=chunk_minutes,
            temp_dir=temp_slice_dir,
        )
        logger.info(f"Audio split into {len(slices)} slices ({chunk_minutes} min each). Transcribing concurrently...")

        slice_results: list[tuple[int, list[dict[str, Any]]]] = []
        max_workers = min(len(slices), 6)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(_transcribe_audio_slice, client, s, model_name): s["index"]
                for s in slices
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                segs = future.result()
                slice_results.append((idx, segs))

        # Sort by slice index and flatten
        slice_results.sort(key=lambda x: x[0])
        all_segments = []
        for _, segs in slice_results:
            all_segments.extend(segs)

        # Cleanup local slice files
        for s in slices:
            try:
                os.remove(s["file_path"])
            except Exception:
                pass
        try:
            if temp_slice_dir.exists():
                temp_slice_dir.rmdir()
        except Exception:
            pass

    # Normalize segment IDs sequentially
    for seg_id, seg in enumerate(all_segments):
        seg["segment_id"] = seg_id

    # Save output artifacts
    transcript_dir = Path(output_dir) / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(audio_path).stem

    transcript_txt_path = transcript_dir / f"{filename}.txt"
    transcript_json_path = transcript_dir / f"{filename}.json"

    save_txt_transcript(all_segments, str(transcript_txt_path))
    save_json_transcript(
        metadata=metadata,
        segments=all_segments,
        transcript_json_path=str(transcript_json_path),
        language="en",
        language_probability=0.999,
    )

    t_elapsed = time.perf_counter() - t_start
    logger.info(
        f"Gemini transcription completed in {t_elapsed:.2f}s "
        f"({len(all_segments)} segments saved to {transcript_json_path})"
    )

    return {
        "transcript_txt_path": str(transcript_txt_path),
        "transcript_json_path": str(transcript_json_path),
        "num_segments": len(all_segments),
        "duration": duration,
        "language": "en",
        "language_probability": 0.999,
    }
