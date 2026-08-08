"""
Standalone test: SSRF gate predicates + upload allowlists (P0.5).
Run directly: venv/bin/python backend/test_upload_validation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.ingest import is_youtube_url, is_gdrive_url
from backend.main import ALLOWED_SOURCE_TYPES, ALLOWED_UPLOAD_EXTENSIONS

PASSED = 0
FAILED = 0


def check(label: str, cond: bool):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


def test_youtube_gate():
    check("youtube.com accepted", is_youtube_url("https://youtube.com/watch?v=dQw4w9WgXcQ"))
    check("youtu.be accepted", is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))
    check("m.youtube.com accepted", is_youtube_url("https://m.youtube.com/watch?v=x"))
    check("file:// rejected", not is_youtube_url("file:///etc/passwd"))
    check("internal host rejected", not is_youtube_url("http://169.254.169.254/latest/meta-data"))
    check("random https rejected", not is_youtube_url("https://example.com/video"))


def test_gdrive_gate():
    check("drive.google.com accepted", is_gdrive_url("https://drive.google.com/file/d/abc/view"))
    check("docs.google.com accepted", is_gdrive_url("https://docs.google.com/uc?id=abc"))
    check("file:// rejected", not is_gdrive_url("file:///etc/passwd"))
    check("gdrive-subdomain-lookalike rejected", not is_gdrive_url("https://drive.google.com.evil.com/x"))
    check("random host rejected", not is_gdrive_url("https://example.com/file/d/abc"))


def test_allowlists():
    check("valid source types", ALLOWED_SOURCE_TYPES == {"youtube", "gdrive", "upload"})
    for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
        check(f"video ext {ext} allowed", ext in ALLOWED_UPLOAD_EXTENSIONS)
    check(".exe not allowed", ".exe not in ALLOWED_UPLOAD_EXTENSIONS")
    check(".pdf not allowed", ".pdf not in ALLOWED_UPLOAD_EXTENSIONS")
    check(".mp3 not allowed", ".mp3 not in ALLOWED_UPLOAD_EXTENSIONS")


if __name__ == "__main__":
    test_youtube_gate()
    test_gdrive_gate()
    test_allowlists()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
