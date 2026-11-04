#!/usr/bin/env python3
"""
Standalone test: gc_sweep only deletes orphaned lecture dirs that the CURRENT
database created (backend/db/database.py DB_MARKER_FILE).

Regression: booting against another DB (the offline tests' throwaway SQLite)
made every lecture older than 7 days look orphaned, and the sweep deleted real
lectures from outputs/ (2026-10-30, 2026-11-04). Runs in a temp dir; never
touches the repo's outputs/.

Run directly (no pytest):  venv/bin/python backend/test_gc_sweep.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/norai_test_gc_sweep.db"
os.environ.setdefault("GEMINI_API_KEY", "offline-gc-test")

from backend import jobs  # noqa: E402
from backend.db import database  # noqa: E402

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


def test_identity():
    a = database.database_identity("postgresql+asyncpg://u:secret1@db.example.com:5432/postgres")
    b = database.database_identity("postgresql+asyncpg://u:other$&;pw@db.example.com:5432/postgres")
    c = database.database_identity("sqlite+aiosqlite:///outputs/norai_main.db")
    check("identity ignores the password", a == b)
    check("different DBs differ", a != c)
    check("identity is short hex", len(c) == 16 and all(ch in "0123456789abcdef" for ch in c))


def test_sweep_only_own_orphans():
    old = time.time() - 30 * 86400
    ids = {
        "untagged": "11111111-1111-1111-1111-111111111111",
        "other_db": "22222222-2222-2222-2222-222222222222",
        "own_orphan": "33333333-3333-3333-3333-333333333333",
        "own_known": "44444444-4444-4444-4444-444444444444",
        "own_recent": "55555555-5555-5555-5555-555555555555",
    }
    cwd = os.getcwd()
    original_lister = jobs._all_lecture_ids
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            out = Path("outputs")
            for name, lid in ids.items():
                d = out / lid
                (d / "notes").mkdir(parents=True)
                if name == "other_db":
                    (d / database.DB_MARKER_FILE).write_text(
                        database.database_identity("postgresql+asyncpg://x@elsewhere/db") + "\n")
                elif name.startswith("own"):
                    database.mark_lecture_dir(d)
                if name != "own_recent":
                    os.utime(d, (old, old))

            async def _known():
                return {ids["own_known"]}

            jobs._all_lecture_ids = _known
            jobs.gc_sweep()

            left = {name for name, lid in ids.items() if (out / lid).exists()}
            check("untagged old dir kept", "untagged" in left)
            check("dir tagged by another DB kept", "other_db" in left)
            check("this DB's old orphan removed", "own_orphan" not in left)
            check("this DB's known lecture kept", "own_known" in left)
            check("this DB's recent orphan kept", "own_recent" in left)
        finally:
            jobs._all_lecture_ids = original_lister
            os.chdir(cwd)


if __name__ == "__main__":
    test_identity()
    test_sweep_only_own_orphans()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
