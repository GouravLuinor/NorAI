import json
import logging
import os
from pathlib import Path
from typing import Any

from config import NORAI_TRANSCRIPTION_BACKEND

# Logging Setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Constants
# Model size is config-driven via NORAI_WHISPER_MODEL (default "small" for
# better WER on technical lecture vocabulary). Models are cached per size so
# consecutive lectures don't pay a reload. See ROADMAP P1.7.

DEFAULT_MODEL_SIZE = os.environ.get("NORAI_WHISPER_MODEL", "small")
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"
# Speed vs. quality (P1.7 follow-up): VAD keeps whisper from decoding silence
# and beam_size=1 (greedy) is 2-5x faster than beam 5 on CPU with minimal
# quality loss on lecture audio. Both env-overridable like NORAI_WHISPER_MODEL.
DEFAULT_VAD_FILTER = os.environ.get("NORAI_WHISPER_VAD_FILTER", "true").lower() == "true"
DEFAULT_BEAM_SIZE = int(os.environ.get("NORAI_WHISPER_BEAM_SIZE", "1"))

# Module-level cache: model_size -> WhisperModel. WhisperModel.transcribe is
# thread-safe, so sharing one instance across concurrent pipelines is safe.
_MODEL_CACHE: dict[str, Any] = {}


# Metadata Loader


def load_metadata(
    metadata_path: str
) -> dict:

    logger.info(
        f"Loading metadata from: {metadata_path}"
    )

    try:

        with open(
            metadata_path,
            "r",
            encoding="utf-8"
        ) as f:

            metadata = json.load(f)

        return metadata

    except Exception as e:

        logger.error(
            f"Failed to load metadata: {e}"
        )
        raise


def load_whisper_model(
    model_size: str = DEFAULT_MODEL_SIZE
) -> Any:

    cached = _MODEL_CACHE.get(model_size)
    if cached is not None:
        logger.info(
            f"Reusing cached Faster-Whisper model: {model_size}"
        )
        return cached

    logger.info(
        f"Loading Faster-Whisper model: {model_size}"
    )

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is not installed. NorAI uses Gemini cloud transcription "
            "by default (NORAI_TRANSCRIPTION_BACKEND='gemini'). To use local offline Whisper, "
            "install faster-whisper separately: pip install faster-whisper"
        ) from exc

    try:
        model = WhisperModel(
            model_size,
            device=DEFAULT_DEVICE,
            compute_type=DEFAULT_COMPUTE_TYPE
        )

        _MODEL_CACHE[model_size] = model

        logger.info(
            "Model loaded successfully."
        )

        return model

    except Exception as e:
        logger.error(
            f"Failed to load model: {e}"
        )
        raise

def generate_segments(
    whisper_segments
) -> list:

    logger.info(
        "Generating structured segments..."
    )

    segments = []

    for segment_id, segment in enumerate(
        whisper_segments
    ):
        
        text = segment.text.strip()

        if not text:
            continue

        segments.append(
            {
                "segment_id": segment_id,

                "start": round(
                    segment.start,
                    3
                ),

                "end": round(
                    segment.end,
                    3
                ),

                "duration": round(
                    segment.end - segment.start,
                    3
                ),

                "text": segment.text.strip()
            }
        )

    logger.info(
        f"Generated {len(segments)} segments."
    )

    return segments


def format_timestamp(
    seconds: float
) -> str:
    """
    3725.8 -> 01:02:05
    """

    total_seconds = int(seconds)

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    secs = (
        total_seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}"
    )

def save_txt_transcript(
    segments: list,
    transcript_txt_path: str
) -> None:

    logger.info(
        f"Saving TXT transcript: {transcript_txt_path}"
    )

    Path(transcript_txt_path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        with open(
            transcript_txt_path,
            "w",
            encoding="utf-8"
        ) as f:

            for segment in segments:

                start_time = format_timestamp(
                    segment["start"]
                )

                end_time = format_timestamp(
                    segment["end"]
                )

                f.write(
                    f"[{start_time} - {end_time}]\n"
                )

                f.write(
                    f"{segment['text']}\n\n"
                )

        logger.info(
            "TXT transcript saved successfully."
        )

    except Exception as e:

        logger.error(
            f"Failed to save TXT transcript: {e}"
        )
        raise


def save_json_transcript(
    metadata: dict,
    segments: list,
    transcript_json_path: str,
    language: str,
    language_probability: float

) -> None:

    logger.info(
        f"Saving JSON transcript: {transcript_json_path}"
    )

    transcript_data = {
        "source": metadata,

    "transcription": {
        "language": language,
        "language_probability":
            language_probability
    },

        "segments": segments
    }

    Path(transcript_json_path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        with open(
            transcript_json_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                transcript_data,
                f,
                indent=4,
                ensure_ascii=False
            )

        logger.info(
            "JSON transcript saved successfully."
        )

    except Exception as e:

        logger.error(
            f"Failed to save JSON transcript: {e}"
        )
        raise


def transcribe_audio(
    audio_path: str,
    metadata_path: str,
    output_dir: str = "outputs",
    backend: str | None = None,
    model_size: str = DEFAULT_MODEL_SIZE,
    vad_filter: bool = DEFAULT_VAD_FILTER,
    beam_size: int = DEFAULT_BEAM_SIZE,
) -> dict:

    active_backend = (backend or NORAI_TRANSCRIPTION_BACKEND).lower().strip()
    logger.info(
        f"Starting transcription (backend={active_backend}): {audio_path}"
    )

    if active_backend in ("gemini", "api", "cloud"):
        from transcription.gemini_transcriber import transcribe_with_gemini
        return transcribe_with_gemini(
            audio_path=audio_path,
            metadata_path=metadata_path,
            output_dir=output_dir,
        )

    try:

        metadata = load_metadata(
            metadata_path
        )

        model = load_whisper_model(
            model_size
        )

        logger.info(
            "Running local Faster-Whisper transcription..."
        )

        whisper_segments, info = model.transcribe(
            audio_path,
            beam_size=beam_size,
            vad_filter=vad_filter
        )

        segments = generate_segments(
            whisper_segments
        )

        transcript_dir = Path(
            output_dir
        ) / "transcripts"

        transcript_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = Path(
            audio_path
        ).stem

        transcript_txt_path = (
            transcript_dir /
            f"{filename}.txt"
        )

        transcript_json_path = (
            transcript_dir /
            f"{filename}.json"
        )

        save_txt_transcript(
            segments,
            str(transcript_txt_path)
        )

        save_json_transcript(
            metadata=metadata,
            segments=segments,
            transcript_json_path=str(
                transcript_json_path
            ),
            language=info.language,
            language_probability= 
              info.language_probability
        )

        logger.info(
            "Transcription completed successfully."
        )

        return {
            "transcript_txt_path":
                str(transcript_txt_path),

            "transcript_json_path":
                str(transcript_json_path),

            "num_segments":
                len(segments),

            "duration":
                metadata.get("duration"),

            "language":
                info.language,

            "language_probability":
                round(
                    info.language_probability,
                    4
                )
        }

    except Exception as e:

        logger.error(
            f"Transcription failed: {e}"
        )

        raise


if __name__ == "__main__":

    audio_path = (
        "outputs/audio/"
        "ciHThtTVNto.mp3"
    )

    metadata_path = (
        "outputs/metadata/"
        "ciHThtTVNto.json"
    )

    result = transcribe_audio(
        audio_path=audio_path,
        metadata_path=metadata_path,
        model_size="base"
    )

    print(
        json.dumps(
            result,
            indent=4
        )
    )