"""
test_cache_util.py — Unit tests for cache_util.py (ROADMAP P1.4).

Fully offline. Run:
    python test_cache_util.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cache_util import digest, outputs_current, write_marker  # noqa: E402


def _tmpfile(text: str) -> Path:
    fd, path = tempfile.mkstemp(prefix="cache_util_")
    with open(fd, "w") as f:
        f.write(text)
    return Path(path)


def test_digest_stable():
    p = _tmpfile("alpha")
    try:
        assert digest(p, "static input") == digest(p, "static input")
        print("PASS test_digest_stable")
    finally:
        p.unlink()


def test_digest_changes_with_file_content():
    p = _tmpfile("alpha")
    try:
        d1 = digest(p, "extra input")
        p.write_text("beta")
        d2 = digest(p, "extra input")
        assert d1 != d2, "digest must change when file content changes"
        print("PASS test_digest_changes_with_file_content")
    finally:
        p.unlink()


def test_digest_changes_with_literal_input():
    p = _tmpfile("alpha")
    try:
        assert digest(p, "a") != digest(p, "b")
        print("PASS test_digest_changes_with_literal_input")
    finally:
        p.unlink()


def test_digest_dict_order_insensitive():
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    print("PASS test_digest_dict_order_insensitive")


def test_outputs_current_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = _tmpfile("content")
        out = td / "out.json"
        marker = td / ".out.sha256"
        out.write_text("{}")
        assert outputs_current(marker, [out], src) is False
        write_marker(marker, src)
        assert outputs_current(marker, [out], src) is True
        src.write_text("changed")
        assert outputs_current(marker, [out], src) is False
        src.write_text("content")
        write_marker(marker, src)
        out.unlink()
        assert outputs_current(marker, [out], src) is False
        src.unlink()
        print("PASS test_outputs_current_roundtrip")


def test_write_marker_creates_parents():
    with tempfile.TemporaryDirectory() as td:
        nested = Path(td) / "a" / "b" / ".m.sha256"
        write_marker(nested, "x")
        assert nested.is_file()
        print("PASS test_write_marker_creates_parents")


if __name__ == "__main__":
    test_digest_stable()
    test_digest_changes_with_file_content()
    test_digest_changes_with_literal_input()
    test_digest_dict_order_insensitive()
    test_outputs_current_roundtrip()
    test_write_marker_creates_parents()
    print("\nAll tests passed.")
