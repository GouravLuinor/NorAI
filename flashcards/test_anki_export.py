"""
test_anki_export.py — Offline tests for the Anki `.apkg` package builder (P6.2).

Builds a package from fake card data and verifies the payload is a real,
openable Anki collection: zip layout (collection.anki2 + media), sqlite
integrity, note/card counts, tags, stable note guids across rebuilds, and that
degenerate (empty) cards are skipped.

Run:
    python flashcards/test_anki_export.py
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flashcards.anki import build_package  # noqa: E402

SAMPLE = [
    {
        "front": "What is a switch?",
        "back": "Forwards frames to the destination MAC only.",
        "explanation": "Unlike hubs, switches build a MAC address table.",
        "chapter_title": "Networking Basics",
        "chapter_id": 1,
    },
    {
        "front": "Line 1\nLine 2",
        "back": "Multi\nline\nback.",
        "explanation": "",
        "chapter_title": "Networking Basics",
        "chapter_id": 1,
    },
    {
        "front": "",  # degenerate — must be skipped
        "back": "no front",
        "explanation": "",
        "chapter_title": "Debris",
        "chapter_id": 99,
    },
]


def _open_package(data: bytes):
    """Unzip the package and return (zip reader, sqlite connection)."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    assert b"PK\x03\x04" in data[:4], "apkg must start with a zip header"
    names = zf.namelist()
    assert "collection.anki2" in names, names
    assert "media" in names, names
    media_lookup = {Path(n).name: n for n in names}
    tmpdir = tempfile.mkdtemp()
    dbfile = Path(tmpdir) / "collection.anki2"
    dbfile.write_bytes(zf.read("collection.anki2"))
    conn = sqlite3.connect(dbfile)
    return zf, conn


def test_package_is_valid_anki():
    data = build_package(SAMPLE, deck_name="NorAI · Demo", lecture_tag="lecture:demo")
    zf, conn = _open_package(data)

    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    n_notes = conn.execute("SELECT count(*) FROM notes").fetchone()[0]
    n_cards = conn.execute("SELECT count(*) FROM cards").fetchone()[0]
    assert n_notes == 2, f"expected 2 non-degenerate notes, got {n_notes}"
    assert n_cards == 2, f"one card per note expected, got {n_cards}"

    col = conn.execute("SELECT models, decks, dconf, conf, ver FROM col").fetchone()
    assert col is not None
    models = json.loads(col[0])
    assert any(m["name"] == "NorAI Basic Card" for m in models.values()), models
    decks = json.loads(col[1])
    assert any("NorAI · Demo" in d["name"] for d in decks.values()), decks

    note = conn.execute("SELECT tags FROM notes LIMIT 1").fetchone()[0]
    assert "chapter-1" in note, note
    assert "chapter:Networking_Basics" in note, note
    assert "lecture:demo" in note, note

    frames = conn.execute("SELECT flds FROM notes").fetchall()
    assert any("Multi<br/>line<br/>back" in str(f[0]) for f in frames), "newlines must render as <br/>"
    assert any('class="hint"' in str(f[0]) for f in frames), "explanation hint must be in the back field"

    media = json.loads(zf.read("media"))
    assert media == {}, "text-only deck must declare empty media"

    conn.close()
    print("PASS test_package_is_valid_anki")


def test_stable_guids_across_rebuilds():
    data_a = build_package(SAMPLE, deck_name="NorAI · Demo")
    data_b = build_package(SAMPLE, deck_name="NorAI · Demo")

    _, conn_a = _open_package(data_a)
    _, conn_b = _open_package(data_b)
    guids_a = sorted(r[0] for r in conn_a.execute("SELECT guid FROM notes"))
    guids_b = sorted(r[0] for r in conn_b.execute("SELECT guid FROM notes"))
    assert guids_a == guids_b, "note guids must be stable across rebuilds"
    assert len(set(guids_a)) == 2
    conn_a.close()
    conn_b.close()
    print("PASS test_stable_guids_across_rebuilds")


def test_empty_deck_builds_empty_package():
    data = build_package([], deck_name="NorAI")
    _, conn = _open_package(data)
    n_notes = conn.execute("SELECT count(*) FROM notes").fetchone()[0]
    assert n_notes == 0
    conn.close()
    print("PASS test_empty_deck_builds_empty_package")


if __name__ == "__main__":
    test_package_is_valid_anki()
    test_stable_guids_across_rebuilds()
    test_empty_deck_builds_empty_package()
    print("\nAll tests passed.")