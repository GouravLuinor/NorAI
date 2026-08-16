import os
import re
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import gdown
import shutil
import yt_dlp
import ffmpeg


# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# -----------------------------
# Utility Functions
# -----------------------------
def is_url(string: str) -> bool:
    """Check whether a string is a valid URL."""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
GDRIVE_DOMAINS = {"drive.google.com", "docs.google.com"}

def is_youtube_url(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc in YOUTUBE_DOMAINS or any(netloc.endswith(f".{d}") for d in ["youtube.com"])
    except Exception:
        return False

def sanitize_youtube_url(url: str) -> str:
    """Extract canonical YouTube watch URL to strip tracking and session parameters."""
    if not url:
        return url
    match = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url

def is_gdrive_url(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc in GDRIVE_DOMAINS
    except Exception:
        return False

def extract_gdrive_file_id(url: str) -> str:
    """
    Extract Google Drive file ID from various URL formats.
    """
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    match = re.search(r"id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    raise ValueError(
        "Could not extract Google Drive file ID."
    )

def create_directories(base_output: str):
    """
    Create project output folders.

    outputs/
    ├── videos/
    ├── audio/
    ├── metadata/
    """
    os.makedirs(os.path.join(base_output, "videos"), exist_ok=True)
    os.makedirs(os.path.join(base_output, "audio"), exist_ok=True)
    os.makedirs(os.path.join(base_output, "metadata"), exist_ok=True)


# -----------------------------
# Gdrive Processing
# -----------------------------

def extract_from_gdrive(
    url: str,
    output_dir: str
) -> dict:
    """
    Download video from Google Drive
    and process exactly like a local file.
    """
    logger.info(
        f"Downloading Google Drive video: {url}"
    )

    video_dir = os.path.join(
        output_dir,
        "videos"
    )

    file_id = extract_gdrive_file_id(url)

    try:
        downloaded_path = gdown.download(
            id=file_id,
            output=video_dir,
            quiet=False
        )
    except Exception as e:
        logger.error(
            f"Google Drive download failed: {e}"
        )
        raise

    if downloaded_path is None:
        raise RuntimeError(
            "Google Drive download failed."
        )

    return extract_from_local(
        str(downloaded_path),
        output_dir
    )

# -----------------------------
# YouTube Processing
# -----------------------------

# Multi-tier fallback extraction strategies to prevent YouTube HTTP 403 Forbidden & bot-throttling errors.
# Note: 'ios' client is deliberately avoided because YouTube requires GVS PO Tokens for iOS streams.
YOUTUBE_FALLBACK_STRATEGIES = [
    {
        "name": "Android VR + Android (H.264 Preferred)",
        "player_client": ["android_vr", "android", "web"],
        "format": "bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720][vcodec^=avc]+bestaudio/bestvideo[height<=720][vcodec^=h264]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    },
    {
        "name": "Android + Web (Progressive Fallback)",
        "player_client": ["android", "web"],
        "format": "best[height<=720][vcodec^=avc1]/best[height<=720]/bestvideo[height<=720]+bestaudio/best",
    },
    {
        "name": "Web + MWeb (Standard Stream)",
        "player_client": ["mweb", "web"],
        "format": "bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best",
    },
    {
        "name": "Generic Direct Format (Emergency Fallback)",
        "player_client": ["web"],
        "format": "best",
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        },
    },
]


def extract_from_youtube(
    url: str,
    output_dir: str
) -> dict:
    """
    Download YouTube video with multi-tier fallback protection,
    convert/ensure H.264 MP4, and extract audio.
    """
    clean_url = sanitize_youtube_url(url)
    logger.info(
        f"Downloading YouTube video: {clean_url}"
    )

    video_dir = os.path.join(
        output_dir,
        "videos"
    )

    audio_dir = os.path.join(
        output_dir,
        "audio"
    )

    metadata_dir = os.path.join(
        output_dir,
        "metadata"
    )

    create_directories(output_dir)

    info = None
    last_error = None

    for strategy in YOUTUBE_FALLBACK_STRATEGIES:
        logger.info(f"Attempting YouTube download with strategy: {strategy['name']}")
        ydl_opts: dict[str, Any] = {
            "format": strategy["format"],
            "outtmpl": os.path.join(
                video_dir,
                "%(id)s.%(ext)s"
            ),
            "quiet": False,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "retries": 10,
            "fragment_retries": 10,
            "nocheckcertificate": True,
            "extractor_args": {
                "youtube": {
                    "player_client": strategy["player_client"],
                }
            },
        }

        if "http_headers" in strategy:
            ydl_opts["http_headers"] = strategy["http_headers"]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    clean_url,
                    download=True
                )
            if info and info.get("id"):
                logger.info(f"Download successful using strategy: {strategy['name']}")
                break
        except Exception as e:
            last_error = e
            logger.warning(
                f"YouTube download failed with '{strategy['name']}': {e}. Trying next strategy..."
            )

    if not info or not info.get("id"):
        raise RuntimeError(
            f"All YouTube download strategies failed for {url}. Last error: {last_error}"
        )

    video_id = info["id"]

    # Locate downloaded file in video_dir
    video_path = os.path.join(video_dir, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        candidates = list(Path(video_dir).glob(f"{video_id}.*"))
        if candidates:
            downloaded_file = str(candidates[0])
            if candidates[0].suffix.lower() == ".mp4":
                video_path = downloaded_file
            else:
                # Convert/remux non-mp4 format to mp4 for frontend and opencv compatibility
                logger.info(f"Remuxing {downloaded_file} to {video_path}...")
                try:
                    (
                        ffmpeg
                        .input(downloaded_file)
                        .output(video_path, vcodec="copy", acodec="copy")
                        .overwrite_output()
                        .run(quiet=True)
                    )
                except Exception:
                    # Fallback to full re-encode if copy fails
                    (
                        ffmpeg
                        .input(downloaded_file)
                        .output(video_path, vcodec="libx264", acodec="aac")
                        .overwrite_output()
                        .run(quiet=True)
                    )
        else:
            raise FileNotFoundError(f"Downloaded video file for ID {video_id} not found in {video_dir}")

    # Verify video codec: ensure standard H.264 so OpenCV & HTML5 player decode reliably
    try:
        probe = ffmpeg.probe(video_path)
        v_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
        v_codec = (v_stream.get("codec_name") or "").lower() if v_stream else ""
        if v_codec and v_codec not in ("h264", "avc1"):
            logger.info(f"Video stream codec is '{v_codec}'. Normalizing to H.264 MP4...")
            temp_trans = os.path.join(video_dir, f"{video_id}_h264.mp4")
            (
                ffmpeg
                .input(video_path)
                .output(temp_trans, vcodec="libx264", preset="ultrafast", crf=23, acodec="copy")
                .overwrite_output()
                .run(quiet=True)
            )
            if os.path.exists(temp_trans) and os.path.getsize(temp_trans) > 0:
                os.replace(temp_trans, video_path)
    except Exception as exc:
        logger.warning(f"Codec normalization skipped: {exc}")

    audio_path = os.path.join(
        audio_dir,
        f"{video_id}.mp3"
    )

    logger.info(
        "Extracting audio..."
    )

    try:
        (
            ffmpeg
            .input(
                video_path
            )
            .output(
                audio_path,
                acodec="libmp3lame",
                ar=16000,
                ac=1,
                audio_bitrate="64k"
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as e:
        logger.error(
            f"FFmpeg extraction failed: {e}"
        )
        raise

    metadata = {
        "video_id": video_id,
        "title": info.get("title"),
        "source_type": "youtube",
        "duration": info.get("duration"),
        "source_url": info.get("webpage_url") or clean_url,
        "uploader": info.get("uploader"),
        "video_path": video_path,
        "audio_path": audio_path
    }

    metadata_path = os.path.join(
        metadata_dir,
        f"{video_id}.json"
    )

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            metadata,
            f,
            indent=4,
            ensure_ascii=False
        )

    return {
        "source_type": "youtube",
        "audio_path": audio_path,
        "video_path": video_path,
        "metadata_path": metadata_path,
        "metadata": metadata
    }


# -----------------------------
# Metadata Probe (P1.8)
# -----------------------------

def probe_video_metadata(url: str) -> dict | None:
    """
    Cheap pre-flight metadata probe for the /estimate endpoint (P1.8).

    Uses yt-dlp with download=False so no media is fetched (~1-2s for YouTube).
    Returns {"duration_sec": float, "title": str} or None when the source
    can't be probed without downloading.
    """
    if not is_youtube_url(url):
        return None
    clean_url = sanitize_youtube_url(url)
    try:
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_vr", "android", "web"],
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
        if not info:
            return None
        duration = info.get("duration")
        if duration is None:
            return None
        return {
            "duration_sec": float(duration),
            "title": info.get("title"),
        }
    except Exception as e:
        logger.info(f"Metadata probe failed (trying fallback client): {e}")
        try:
            fallback_opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"],
                    }
                },
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
            if info and info.get("duration") is not None:
                return {
                    "duration_sec": float(info["duration"]),
                    "title": info.get("title"),
                }
        except Exception as e2:
            logger.info(f"Fallback probe also failed: {e2}")
        return None


# -----------------------------
# Local Video Processing
# -----------------------------
def extract_from_local(file_path: str, output_dir: str) -> dict:
    """
    Extract audio from local video file.
    """
    SUPPORTED_VIDEO_EXTENSIONS = {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm"
    }

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )
    
    extension = Path(file_path).suffix.lower()

    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    logger.info(f"Processing local file: {file_path}")

    video_dir = os.path.join(output_dir, "videos")
    audio_dir = os.path.join(output_dir, "audio")
    metadata_dir = os.path.join(output_dir, "metadata")

    filename = Path(file_path).stem

    copied_video_path = os.path.join(
        video_dir,
        f"{filename}{Path(file_path).suffix}"
    )

    audio_path = os.path.join(
        audio_dir,
        f"{filename}.mp3"
    )

    if os.path.abspath(file_path) != os.path.abspath(copied_video_path):
        shutil.copy2(
            file_path,
            copied_video_path
        )

    logger.info("Extracting audio...")

    try:
        (
            ffmpeg
            .input(copied_video_path)
            .output(
                audio_path,
                acodec="libmp3lame",
                ar=16000,
                ac=1,
                audio_bitrate="64k"
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as e:
        logger.error(
            f"FFmpeg extraction failed: {e}"
        )
        raise

    probe = ffmpeg.probe(copied_video_path)

    duration = float(
        probe["format"]["duration"]
    )

    metadata = {
        "title": filename,
        "source_type": "local",
        "duration": duration,
        "source_url": None,
        "video_path": copied_video_path,
        "audio_path": audio_path
    }

    metadata_path = os.path.join(
        metadata_dir,
        f"{filename}.json"
    )

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    return {
        "source_type": "local",
        "audio_path": audio_path,
        "video_path": copied_video_path,
        "metadata_path": metadata_path,
        "metadata": metadata
    }


# -----------------------------
# Main Entry Point
# -----------------------------
def process_source(
    source: str,
    output_dir: str = "outputs"
) -> dict:
    """
    Main routing function.

    Input:
        YouTube URL
        OR
        Local video path

    Output:
        Structured dictionary
    """
    create_directories(output_dir)

    if is_url(source):
        if is_youtube_url(source):
            logger.info("Detected YouTube URL")
            return extract_from_youtube(
                source,
                output_dir
            )
        elif is_gdrive_url(source):
            logger.info("Detected Google Drive URL")
            return extract_from_gdrive(
                source,
                output_dir
            )
        else:
            raise ValueError(
                "Unsupported URL source."
            )

    return extract_from_local(
        source,
        output_dir
    )