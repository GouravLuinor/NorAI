#!/usr/bin/env python3
"""
Standalone test: the API side of document intake. /estimate counts a
document's words into quota minutes (no Gemini call), /process accepts
PDF/DOCX/PPTX/TXT/MD uploads whose bytes match their extension and rejects
fakes, the `link` source validates its URL, and /lectures/{id} reports a
document's source_kind.

Run directly (no pytest):  venv/bin/python backend/test_document_intake.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP_DB = "/tmp/norai_test_document_intake.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "offline-document-intake-test"
os.environ["NORAI_MODE"] = "local"  # no login, no plan: this tests intake only
for _k in ("NORAI_SOURCES", "NORAI_ENV"):
    os.environ.pop(_k, None)

from documents.test_documents import make_docx, make_pdf, _text  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, cond: bool):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"PASS  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


def main():
    import asyncio
    from fastapi.testclient import TestClient
    from backend import main as main_mod
    from backend.db.database import engine
    from backend.db.models import Base

    async def _tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_tables())
    client = TestClient(main_mod.app)
    td = Path(tempfile.mkdtemp())

    pdf = td / "notes.pdf"
    make_pdf(pdf, [_text(300), _text(300, 4)])
    with open(pdf, "rb") as f:
        r = client.post("/estimate", data={"source_type": "upload"},
                        files={"file": ("notes.pdf", f, "application/pdf")})
    body = r.json()
    check("estimate PDF 200", r.status_code == 200)
    check("estimate PDF counts words → minutes",
          body.get("available") and body.get("kind") == "document" and body.get("pages") == 2
          and body.get("minutes_needed") == 4 and body.get("words") == 600)
    check("estimate title doesn't leak the temp file name", "est-" not in (body.get("title") or ""))

    scan = td / "scan.pdf"
    make_pdf(scan, ["", ""])
    with open(scan, "rb") as f:
        r = client.post("/estimate", data={"source_type": "upload"}, files={"file": ("scan.pdf", f)})
    check("estimate scanned PDF: no estimate, no Gemini call",
          r.status_code == 200 and r.json().get("scanned") is True and not r.json().get("available"))

    dx = td / "w.docx"
    make_docx(dx)
    with open(dx, "rb") as f:
        r = client.post("/estimate", data={"source_type": "upload"}, files={"file": ("w.docx", f)})
    check("estimate DOCX", r.status_code == 200 and r.json().get("doc_type") == "docx")

    r = client.post("/estimate", data={"source_type": "link", "url": "ftp://x.com/a.pdf"})
    check("estimate link rejects non-http", r.status_code == 400)
    r = client.post("/estimate", data={"source_type": "link", "url": "http://localhost/a.pdf"})
    check("estimate link refuses a local address",
          r.status_code == 200 and "private or local" in (r.json().get("error") or ""))

    fake = td / "fake.pdf"
    fake.write_bytes(b"MZ\x90\x00 not a pdf at all")
    with open(fake, "rb") as f:
        r = client.post("/process", data={"source_type": "upload"}, files={"file": ("fake.pdf", f)})
    check("process rejects a fake PDF (415)", r.status_code == 415 and "document" in r.json()["detail"])

    with open(td / "x.doc", "wb") as f:
        f.write(b"\xd0\xcf\x11\xe0")
    with open(td / "x.doc", "rb") as f:
        r = client.post("/process", data={"source_type": "upload"}, files={"file": ("x.doc", f)})
    check("process rejects legacy .doc (415)", r.status_code == 415)

    with open(pdf, "rb") as f:
        r = client.post("/process", data={"source_type": "upload"}, files={"file": ("notes.pdf", f)})
    check("process accepts a real PDF", r.status_code == 200 and "task_id" in r.json())
    task = r.json().get("task_id")
    if task:
        for p in Path("outputs/uploads").glob(f"{task}_*"):
            p.unlink()

    r = client.post("/process", data={"source_type": "link", "url": "not a url"})
    check("process link rejects a non-URL", r.status_code == 400)

    # /lectures/{id} reports source_kind from the transcript (registry stubbed:
    # don't touch the real outputs/ registry).
    lid = "00000000-0000-4000-8000-00000000d0c5"
    out = td / lid
    import backend.access as access_mod
    stub = lambda _id: {"id": lid, "title": "Doc test", "output_dir": str(out)}  # noqa: E731
    main_mod.get_lecture = access_mod.get_lecture = stub
    (Path(out) / "transcripts").mkdir(parents=True, exist_ok=True)
    (Path(out) / "transcripts" / "document.json").write_text(json.dumps(
        {"source": {"source_kind": "document", "doc_type": "pdf", "pages": 3, "words": 900}, "segments": []}))
    r = client.get(f"/lectures/{lid}")
    check("lecture info says document",
          r.status_code == 200 and r.json().get("source_kind") == "document" and r.json().get("pages") == 3)


if __name__ == "__main__":
    main()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
