import os
import re
import json
import logging
from pathlib import Path
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

def is_youtube_url(url: str) -> bool:
    return (
        "youtube.com" in url
        or "youtu.be" in url
    )

def is_gdrive_url(url: str) -> bool:
    return (
        "drive.google.com" in url
    )

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
        downloaded_path,
        output_dir
    )

# -----------------------------
# YouTube Processing
# -----------------------------
def extract_from_youtube(url: str, output_dir: str) -> dict:
    """
    Download YouTube video + extract audio.

    Returns:
        dict containing paths and metadata.
    """

    logger.info(f"Downloading YouTube video: {url}")

    video_dir = os.path.join(output_dir, "videos")
    audio_dir = os.path.join(output_dir, "audio")
    metadata_dir = os.path.join(output_dir, "metadata")

    ydl_opts = {
"format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "outtmpl": os.path.join(video_dir, "%(id)s.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                url,
                download=True
            )
    except Exception as e:
        logger.error(
            f"YouTube download failed: {e}"
        )
        raise

    video_id = info["id"]

    video_path = os.path.join(video_dir, f"{video_id}.mp4")

    audio_path = os.path.join(audio_dir, f"{video_id}.mp3")

    logger.info("Extracting audio...")

    try :
        (
            ffmpeg
            .input(video_path)
            .output(
                audio_path,
                acodec="libmp3lame",
                audio_bitrate="192k"
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
        "source_url": info.get("webpage_url"),
        "uploader": info.get("uploader"),
        "video_path": video_path,
        "audio_path": audio_path
    }

    metadata_path = os.path.join(
        metadata_dir,
        f"{video_id}.json"
    )

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    return {
        "source_type": "youtube",
        "audio_path": audio_path,
        "video_path": video_path,
        "metadata_path": metadata_path,
        "metadata": metadata
    }


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

    try : 
        (
            ffmpeg
            .input(copied_video_path)
            .output(
                audio_path,
                acodec="libmp3lame",
                audio_bitrate="192k"
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

        elif is_gdrive_url(source):
            logger.info("Detected Google Drive URL")

        else:
            logger.info("Detected Local File")

        if is_youtube_url(source):
            return extract_from_youtube(
                source,
                output_dir
            )

        if is_gdrive_url(source):
            return extract_from_gdrive(
                source,
                output_dir
            )

        raise ValueError(
            "Unsupported URL source."
        )

    return extract_from_local(
        source,
        output_dir
    )


# -----------------------------
# Testing
# -----------------------------


if __name__ == "__main__":

    youtube_url = "https://www.youtube.com/watch?v=ciHThtTVNto"

    result = process_source(youtube_url)

    print(json.dumps(result, indent=4))


"""
if __name__ == "__main__":

    source = "/mnt/c/Users/gaura/Videos/2026-03-22 17-10-37.mp4"

    result = process_source(source)

    print(json.dumps(result, indent=4))

"""

"""
if __name__ == "__main__":

    source = "https://drive.google.com/file/d/1M-xW7jV9iOSIXfFqZJGAxxrHbEJTc_Wf/view?usp=sharing"

    result = process_source(source)

    print(json.dumps(result, indent=4))
"""