"""
Standalone test: /static allowlist resolution (P0.3).
Run directly: venv/bin/python backend/test_static_allowlist.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException

from backend.main import resolve_static_path

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


def setup_base(tmp: Path) -> Path:
    base = tmp / "outputs"
    (base / "lec1" / "screenshots" / "keyframes").mkdir(parents=True)
    (base / "lec1" / "tutor" / "chroma").mkdir(parents=True)
    (base / "lec1" / "transcripts").mkdir(parents=True)
    (base / "lec1" / "assessment").mkdir(parents=True)
    (base / "lec1" / "screenshots" / "keyframes" / "frame_1.jpg").write_bytes(b"\xff\xd8\xff")
    (base / "lec1" / "tutor" / "checkpoints.sqlite").write_bytes(b"sqlite-bytes")
    (base / "lec1" / "transcripts" / "lecture.txt").write_text("secret transcript")
    (base / "lec1" / "assessment" / "assessment.json").write_text('{"questions":[]}')
    return base


def test_allowlist():
    with tempfile.TemporaryDirectory() as d:
        base = setup_base(Path(d))
        img = resolve_static_path("lec1/screenshots/keyframes/frame_1.jpg", base)
        check("real image resolves to file", img.is_file())

        for path, label in [
            ("lec1/tutor/checkpoints.sqlite", "checkpoints.sqlite blocked"),
            ("lec1/transcripts/lecture.txt", "transcript .txt blocked"),
            ("lec1/assessment/assessment.json", "answer key .json blocked"),
        ]:
            try:
                resolve_static_path(path, base)
                check(label, False)
            except HTTPException as e:
                check(label, e.status_code == 404)

        try:
            resolve_static_path("../../etc/passwd", base)
            check("traversal blocked", False)
        except HTTPException as e:
            check("traversal blocked", e.status_code == 404)

        try:
            resolve_static_path("lec1/screenshots/keyframes/missing.jpg", base)
            check("missing file 404", False)
        except HTTPException as e:
            check("missing file 404", e.status_code == 404)


if __name__ == "__main__":
    test_allowlist()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
