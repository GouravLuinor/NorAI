"""
documents/intake.py — turn any intake source into either a video ingest result
or a document transcript, for backend/orchestrator.run_pipeline.

    youtube                      → video (ingest/ingest.py)
    upload                       → sniffed: video file or document
    gdrive  Docs/Slides link     → exported docx/pptx → document
            Drive file           → gdown → sniffed: video or document
    link    any other http(s)    → SSRF-guarded fetch → web page, document
                                   or direct video file
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from documents.adapter import write_document_transcript
from documents.extract import (
    DocumentError, Extracted, VIDEO_EXTENSIONS, extract_file, extract_html, sniff,
)
from documents.fetch import FetchError, google_export_url, rewrite_link, safe_download
from documents.kind import DOCUMENT, VIDEO

logger = logging.getLogger(__name__)

MAX_DOCUMENT_WORDS = int(os.environ.get("NORAI_MAX_DOCUMENT_WORDS", "200000"))
MAX_VIDEO_LINK_BYTES = int(os.environ.get("NORAI_MAX_UPLOAD_BYTES", str(2 * 1024**3)))


@dataclass
class Prepared:
    kind: str                      # "video" | "document"
    ingest: dict | None = None     # video: ingest.process_source() result
    transcript_path: str | None = None
    duration_sec: float | None = None
    words: int | None = None
    title: str = ""
    doc_type: str | None = None
    pages: int | None = None


def _document(ex: Extracted, out: str, source_type: str, source_url: str | None) -> Prepared:
    words = sum(len(b.text.split()) for b in ex.blocks)
    if words > MAX_DOCUMENT_WORDS:
        raise DocumentError(f"This document has {words:,} words; the limit is {MAX_DOCUMENT_WORDS:,}. "
                            "Split it into parts and upload each one.")
    t = write_document_transcript(ex.blocks, out, title=ex.title, doc_type=ex.doc_type,
                                  source_type=source_type, source_url=source_url, pages=ex.pages)
    logger.info("Document %s: %s, %d words, %s pages → %.1f quota min",
                ex.title, ex.doc_type, t["words"], ex.pages, t["duration_sec"] / 60)
    return Prepared(DOCUMENT, transcript_path=t["transcript_path"], duration_sec=t["duration_sec"],
                    words=t["words"], title=ex.title, doc_type=ex.doc_type, pages=ex.pages)


def _video_file(path: Path, out: str) -> Prepared:
    from ingest.ingest import create_directories, extract_from_local

    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        # A sniffed video without a usable extension (direct links often lack one).
        with open(path, "rb") as f:
            head = f.read(16)
        ext = ".mkv" if head.startswith(b"\x1a\x45\xdf\xa3") else ".avi" if head.startswith(b"RIFF") else ".mp4"
        renamed = path.with_suffix(ext)
        path.rename(renamed)
        path = renamed
    create_directories(out)
    return Prepared(VIDEO, ingest=extract_from_local(str(path), out))


def _local_file(path: Path, out: str, source_type: str, source_url: str | None,
                name_hint: str = "", content_type: str = "") -> Prepared:
    kind = sniff(path, name_hint=name_hint, content_type=content_type)
    if kind == "video":
        return _video_file(path, out)
    if kind == "html":
        ex = extract_html(path.read_bytes(), url=source_url, fallback_title=Path(name_hint).stem)
    else:
        ex = extract_file(path, kind)
    return _document(ex, out, source_type, source_url)


def _gdrive_file(url: str, out: str) -> Prepared:
    import gdown
    from ingest.ingest import extract_gdrive_file_id

    dl_dir = Path(out) / "downloads"
    dl_dir.mkdir(parents=True, exist_ok=True)
    got = gdown.download(id=extract_gdrive_file_id(url), output=str(dl_dir) + os.sep, quiet=True)
    if not got:
        raise FetchError("Google Drive download failed. Make sure the file is shared as "
                         "\"Anyone with the link\".")
    path = Path(got)
    return _local_file(path, out, "gdrive", url, name_hint=path.name)


def prepare_source(source_type: str, out: str, *, url: str | None = None,
                   file_path: str | None = None) -> Prepared:
    from ingest.ingest import is_gdrive_url, is_youtube_url, process_source

    if source_type == "youtube":
        return Prepared(VIDEO, ingest=process_source(url or "", output_dir=out))

    if source_type == "upload":
        if not file_path:
            raise DocumentError("No file was uploaded.")
        path = Path(file_path)
        return _local_file(path, out, "upload", None, name_hint=path.name)

    if source_type == "gdrive":
        export = google_export_url(url or "")
        if export:
            f = safe_download(export, Path(out) / "downloads")
            return _local_file(f.path, out, "gdrive", url, name_hint=f.filename, content_type=f.content_type)
        return _gdrive_file(url or "", out)

    if source_type == "link":
        if not url:
            raise FetchError("No link was given.")
        if is_youtube_url(url):
            raise FetchError("That's a YouTube link; YouTube isn't available here.")
        if is_gdrive_url(url):
            return prepare_source("gdrive", out, url=url)
        f = safe_download(rewrite_link(url), Path(out) / "downloads", max_video_bytes=MAX_VIDEO_LINK_BYTES)
        return _local_file(f.path, out, "link", url, name_hint=f.filename, content_type=f.content_type)

    raise DocumentError(f"Unsupported source type {source_type!r}.")


def cleanup_downloads(out: str | Path) -> None:
    shutil.rmtree(Path(out) / "downloads", ignore_errors=True)
