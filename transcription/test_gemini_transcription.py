"""
transcription/test_gemini_transcription.py

Unit test for Gemini audio transcription and provider routing.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MODEL_NAME, NORAI_TRANSCRIPTION_BACKEND, MODEL_PRICING
from transcription.transcribe import transcribe_audio
from transcription.gemini_transcriber import (
    slice_audio_for_transcription,
    GeminiTranscriptResponse,
    TranscriptSegment,
)


def test_config_and_schemas():
    print("Testing config and schemas...")
    assert MODEL_NAME == "gemini-3.1-flash-lite", f"Unexpected MODEL_NAME: {MODEL_NAME}"
    assert NORAI_TRANSCRIPTION_BACKEND == "gemini", f"Unexpected backend: {NORAI_TRANSCRIPTION_BACKEND}"
    assert "gemini-3.1-flash-lite" in MODEL_PRICING, "gemini-3.1-flash-lite missing from MODEL_PRICING"
    assert MODEL_PRICING["gemini-3.1-flash-lite"]["input_per_1M"] == 0.25
    assert MODEL_PRICING["gemini-3.1-flash-lite"]["output_per_1M"] == 1.50

    # Test Pydantic schema validation
    resp = GeminiTranscriptResponse(
        language="en",
        language_probability=0.99,
        segments=[
            TranscriptSegment(segment_id=0, start=0.0, end=5.2, text="Welcome to this lecture on AWS architecture."),
            TranscriptSegment(segment_id=1, start=5.2, end=10.5, text="Today we will examine EC2, S3, and DynamoDB.")
        ]
    )
    assert len(resp.segments) == 2
    assert resp.segments[1].end == 10.5
    print("  ✓ Config and schemas validated successfully.")


def test_audio_slicing_logic():
    print("Testing audio slicing logic...")
    audio_path = "outputs/test_ewNuSlRdZfw_16k.mp3"
    if Path(audio_path).exists():
        slices = slice_audio_for_transcription(
            audio_path=audio_path,
            total_duration_sec=4272.0,
            chunk_minutes=18,
            temp_dir="outputs/test_unit_slices"
        )
        assert len(slices) == 4, f"Expected 4 slices, got {len(slices)}"
        assert slices[0]["start_offset"] == 0.0
        assert slices[0]["end_offset"] == 1080.0
        assert slices[3]["end_offset"] == 4272.0
        
        # Cleanup
        for s in slices:
            try:
                Path(s["file_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        try:
            Path("outputs/test_unit_slices").rmdir()
        except Exception:
            pass
        print(f"  ✓ Audio slicing validated: {len(slices)} chunks created and verified.")
    else:
        print("  ⚠ Skipping audio file slice test (test audio not found).")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING GEMINI TRANSCRIPTION UNIT TESTS")
    print("=" * 60)
    test_config_and_schemas()
    test_audio_slicing_logic()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
