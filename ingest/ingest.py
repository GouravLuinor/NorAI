import os
import re
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import gdown
import shutil
import yt_dlp
import ffmpeg

import config


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

def _get_youtube_cookiefile() -> str | None:
    """Return path to a cookiefile if configured via env var or local file."""
    if cookie_path := os.environ.get("YOUTUBE_COOKIES_FILE"):
        if os.path.isfile(cookie_path):
            return cookie_path
    if os.path.isfile("cookies.txt"):
        return "cookies.txt"
    if raw_cookies := os.environ.get("YOUTUBE_COOKIES"):
        import tempfile
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", prefix="yt_cookies_")
        tmp.write(raw_cookies)
        tmp.close()
        return tmp.name
    if b64_cookies := os.environ.get("YOUTUBE_COOKIES_BASE64"):
        import base64, tempfile
        try:
            decoded = base64.b64decode(b64_cookies).decode("utf-8")
            tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", prefix="yt_cookies_")
            tmp.write(decoded)
            tmp.close()
            return tmp.name
        except Exception:
            pass
    return None


def _pot_server_url() -> str | None:
    """Return the POT provider base URL if the server is reachable, else None.

    The Docker image runs `bgutil-pot server` (bgutil-ytdlp-pot-provider-rs) on
    `NORAI_POT_SERVER_URL`. yt-dlp's `web` client then issues a proof-of-origin
    token through the `youtubepot-bgutilhttp` plugin. When the server is absent
    (local dev) we skip the extractor arg entirely so the fallback strategies
    behave exactly as before.
    """
    url = config.POT_SERVER_URL.strip().rstrip("/")
    if not url:
        return None
    try:
        with urllib.request.urlopen(f"{url}/ping", timeout=2) as resp:
            if resp.status == 200:
                return url
    except Exception:
        pass
    return None

# Principled download strategy tiers (P8.x). The old 5-guess chain swapped
# between ad-hoc client lists; with a PO-token provider installed (bgutil-pot in
# the Docker image) the `web` client becomes viable on datacenter IPs, so we
# keep exactly three tiers: web+POT (primary, most compatible), TV/embedded
# (datacenter-resilient), then Android (progressive last resort). yt-dlp
# auto-detects the installed POT plugin and issues tokens for the `web` client.
YOUTUBE_FALLBACK_STRATEGIES = [
    {
        "name": "Web + POT (Primary)",
        "player_client": ["web"],
        "format": "bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    },
    {
        "name": "Smart TV & Embedded (Datacenter-Resilient)",
        "player_client": ["tv_embedded", "tv", "web"],
        "format": "bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    },
    {
        "name": "Android (Progressive Fallback)",
        "player_client": ["android", "web"],
        "format": "best[height<=720][vcodec^=avc1]/best[height<=720]/bestvideo[height<=720]+bestaudio/best",
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
    cookiefile = _get_youtube_cookiefile()
    pot_url = _pot_server_url()

    for strategy in YOUTUBE_FALLBACK_STRATEGIES:
        logger.info(f"Attempting YouTube download with strategy: {strategy['name']}")
        extractor_args: dict[str, dict] = {
            "youtube": {
                "player_client": strategy["player_client"],
            }
        }
        if pot_url:
            extractor_args["youtubepot-bgutilhttp"] = {
                "base_url": pot_url,
            }
        ydl_opts: dict[str, Any] = {
            "format": strategy["format"],
            "outtmpl": os.path.join(
                video_dir,
                "%(id)s.%(ext)s"
            ),
            "quiet": False,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "retries": 5,
            "fragment_retries": 5,
            "nocheckcertificate": True,
            "socket_timeout": 15,
            "extractor_args": extractor_args,
        }

        if cookiefile:
            ydl_opts["cookiefile"] = cookiefile

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
        err_str = str(last_error) if last_error else ""
        if "Sign in to confirm you're not a bot" in err_str or "bot" in err_str.lower():
            raise RuntimeError(
                "YouTube requested bot verification for this video on the cloud server. "
                "Please upload the video directly via the 'Upload' tab, or configure YOUTUBE_COOKIES in server settings."
            )
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

    Uses YouTube official oEmbed API for instant zero-rate-limit title extraction,
    then queries yt-dlp with download=False across TV/mobile client strategies.
    """
    if not is_youtube_url(url):
        return None
    clean_url = sanitize_youtube_url(url)

    # 1. Fetch title via YouTube oEmbed API (guaranteed zero rate limit / no bot check)
    oembed_title = None
    try:
        import urllib.request
        import urllib.parse
        import json as json_mod
        oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url)}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "NorAI/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            if resp.status == 200:
                data = json_mod.loads(resp.read().decode("utf-8"))
                oembed_title = data.get("title")
    except Exception as e:
        logger.debug(f"oEmbed probe skipped: {e}")

    # 2. Extract exact duration with yt-dlp across client strategies (aligned
    #    with YOUTUBE_FALLBACK_STRATEGIES; POT is used when the server is up).
    cookiefile = _get_youtube_cookiefile()
    pot_url = _pot_server_url()
    for strategy in YOUTUBE_FALLBACK_STRATEGIES:
        clients = strategy["player_client"]
        try:
            extractor_args: dict[str, dict] = {
                "youtube": {
                    "player_client": clients,
                }
            }
            if pot_url:
                extractor_args["youtubepot-bgutilhttp"] = {
                    "base_url": pot_url,
                }
            ydl_opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 5,
                "extractor_args": extractor_args,
            }
            if cookiefile:
                ydl_opts["cookiefile"] = cookiefile

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
            if info and info.get("duration") is not None:
                return {
                    "duration_sec": float(info["duration"]),
                    "title": info.get("title") or oembed_title,
                }
        except Exception as err:
            logger.debug(f"yt-dlp probe with {clients} failed: {err}")
    # 3. If oEmbed retrieved title but duration was blocked on datacenter IP:
    if oembed_title:
        return {
            "duration_sec": 900.0,
            "title": oembed_title,
            "estimated": True,
        }

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