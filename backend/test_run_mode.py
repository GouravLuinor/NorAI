#!/usr/bin/env python3
"""
Standalone test: run mode + intake source allowlist (config.run_mode,
enabled_sources, dev_access) and the API gates built on them
(/system/config, /estimate + /process rejecting switched-off sources).

Run directly (no pytest):  venv/bin/python backend/test_run_mode.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP_DB = "/tmp/norai_test_run_mode.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "offline-run-mode-test"
for _k in ("NORAI_MODE", "NORAI_SOURCES", "NORAI_DEV_ACCESS", "NORAI_DEV_INSECURE_AUTH", "NORAI_ENV"):
    os.environ.pop(_k, None)

import config  # noqa: E402

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


def _env(**kv):
    for k, v in kv.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_config():
    _env(NORAI_MODE=None, NORAI_SOURCES=None, NORAI_DEV_ACCESS=None)
    check("default mode is hosted", config.run_mode() == "hosted")
    check("hosted: no dev access", not config.dev_access())
    check("hosted default leaves YouTube off", config.enabled_sources() == ("gdrive", "upload", "link"))

    _env(NORAI_MODE="local")
    check("local mode", config.run_mode() == "local" and config.is_local_mode())
    check("local mode implies dev access", config.dev_access())
    check("local default: every source", config.enabled_sources() == ("youtube", "gdrive", "upload", "link"))

    _env(NORAI_MODE="LOCAL ")
    check("mode is case/space tolerant", config.is_local_mode())
    _env(NORAI_MODE="banana")
    check("unknown mode falls back to hosted", config.run_mode() == "hosted")

    _env(NORAI_MODE=None, NORAI_SOURCES="upload, YouTube,nope")
    check("NORAI_SOURCES overrides, ordered, unknown dropped",
          config.enabled_sources() == ("youtube", "upload"))
    _env(NORAI_MODE="local", NORAI_SOURCES="upload")
    check("NORAI_SOURCES overrides local default too", config.enabled_sources() == ("upload",))

    _env(NORAI_MODE=None, NORAI_SOURCES=None, NORAI_DEV_ACCESS="1")
    check("NORAI_DEV_ACCESS still grants dev access", config.dev_access())
    _env(NORAI_DEV_ACCESS=None)


def test_api():
    _env(NORAI_MODE=None, NORAI_SOURCES=None, NORAI_DEV_ACCESS=None)
    from fastapi.testclient import TestClient
    from backend import main as main_mod

    client = TestClient(main_mod.app)  # no lifespan: no supervisor, no migrations needed

    r = client.get("/system/config")
    check("GET /system/config 200", r.status_code == 200)
    check("hosted config", r.json() == {"mode": "hosted", "sources": ["gdrive", "upload", "link"]})

    r = client.post("/estimate", data={"source_type": "youtube", "url": "https://youtu.be/dQw4w9WgXcQ"})
    check("hosted: YouTube estimate rejected 400", r.status_code == 400)
    check("rejection says to upload instead", "upload" in r.json().get("detail", "").lower())

    r = client.post("/estimate", data={"source_type": "ftp", "url": "x"})
    check("unknown source type still 400", r.status_code == 400 and "Unsupported" in r.json()["detail"])

    r = client.post("/estimate", data={"source_type": "upload", "duration": "12"})
    check("enabled source passes the gate", r.status_code != 400)

    _env(NORAI_MODE="local")
    r = client.get("/system/config")
    check("local config lists YouTube", r.json() == {"mode": "local", "sources": ["youtube", "gdrive", "upload", "link"]})
    # No plan applies locally, so a long lecture must not be flagged "over plan"
    # (the upload page disables Start on fits_plan=false).
    r = client.post("/estimate", data={"source_type": "upload", "duration": "300"})
    check("local: 300-min estimate fits", r.status_code == 200 and r.json().get("fits_plan") is True)
    _env(NORAI_MODE=None)


if __name__ == "__main__":
    test_config()
    test_api()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
