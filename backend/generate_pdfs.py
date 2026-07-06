"""
generate_pdfs.py

Strategy: pre-fetch all chapter content here in Python (where network access
is reliable), then inject it into the page via window.__PRINT_DATA__ using
page.evaluate().  The React PrintPage reads from that global instead of
making its own fetch calls, so Playwright never has to wait for network
activity inside the headless browser.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

TYPES = ["study_notes", "revision", "assessment"]
OUTPUT_DIR = Path("outputs")
API_BASE = "http://localhost:8000"
NUM_CHAPTERS = 6

def get_num_chapters(lecture_id: str) -> int:
    """Read the actual chapter count from the lecture's outline."""
    try:
        url = f"{API_BASE}/outline?lecture_id={lecture_id}"
        data = json.loads(_get(url))
        chapters = data.get("chapters", [])
        return len(chapters)
    except Exception:
        return 6  # fallback
    
# ── Data fetching helpers ──────────────────────────────────────────────────

def _get(url: str) -> str:
    """Simple blocking GET; returns response body as str or raises."""
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode()


def fetch_notes(chapter: int, lecture_id: str) -> str:
    url = f"{API_BASE}/notes/{chapter}?lecture_id={lecture_id}"
    try:
        raw = _get(url)
        return json.loads(raw) if raw.startswith('"') else raw
    except Exception as exc:
        return f"# Chapter {chapter}\n\n*Failed to load: {exc}*"


def fetch_summary(chapter: int, lecture_id: str) -> str:
    url = f"{API_BASE}/summary?chapter_id={chapter}&lecture_id={lecture_id}"
    try:
        raw = _get(url)
        return json.loads(raw) if raw.startswith('"') else raw
    except Exception as exc:
        return f"# Chapter {chapter}\n\n*Failed to load: {exc}*"


def fetch_quiz(chapter: int, lecture_id: str) -> list:
    url = f"{API_BASE}/quiz/questions?chapter_id={chapter}&lecture_id={lecture_id}"
    try:
        return json.loads(_get(url))
    except Exception:
        return []


def build_print_data(doc_type: str, lecture_id: str) -> dict:
    """
    Returns a dict that exactly matches what PrintPage.tsx expects
    as window.__PRINT_DATA__.  Shape:

        {
          "type": "notes" | "revision" | "assessment",
          "chapters": ["markdown string", ...],      # notes / revision
          "assessmentChapters": [                    # assessment
              {"ch": 1, "questions": [...]},
              ...
          ]
        }
    """
    # Normalize to internal layout key (mirrors PrintPage.tsx logic)
    if "assessment" in doc_type:
        layout = "assessment"
    elif "revision" in doc_type or "summary" in doc_type:
        layout = "revision"
    else:
        layout = "notes"

    num_chapters = get_num_chapters(lecture_id)

    print(f"  Pre-fetching data for type={layout!r}, lecture_id={lecture_id!r} ({num_chapters} chapters)")

    if layout == "assessment":
        assessment_chapters = []
        for ch in range(1, num_chapters + 1):
            questions = fetch_quiz(ch, lecture_id)
            assessment_chapters.append({"ch": ch, "questions": questions})
            print(f"    chapter {ch}: {len(questions)} questions")
        return {"type": layout, "assessmentChapters": assessment_chapters}

    chapters = []
    for ch in range(1, num_chapters + 1):
        if layout == "revision":
            md = fetch_summary(ch, lecture_id)
        else:
            md = fetch_notes(ch, lecture_id)
        chapters.append(md)
        preview = md[:60].replace("\n", " ")
        print(f"    chapter {ch}: {len(md)} chars — {preview!r}…")

    return {"type": layout, "chapters": chapters}


# ── PDF generation ─────────────────────────────────────────────────────────

def generate_pdfs(lecture_id: str = "default", types: list[str] | None = None):
    from playwright.sync_api import sync_playwright

    if types is None:
        types = TYPES

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for doc_type in types:
            print(f"\n{'─'*60}")
            print(f"Generating: {doc_type}")

            # 1. Pre-fetch all data in Python
            print_data = build_print_data(doc_type, lecture_id)

            # 2. Open a blank page — we inject data BEFORE navigating
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: print(f"  [browser {m.type}] {m.text}"))
            page.on("pageerror", lambda e: print(f"  [browser ERROR] {e}"))

            # 3. Navigate; wait only for the HTML shell to load
            url = (
                f"http://localhost:5173/print"
                f"?type={doc_type}&lecture_id={lecture_id}"
            )
            print(f"  Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # 4. Inject the pre-fetched data so React can read it synchronously
            page.evaluate(
                "data => { window.__PRINT_DATA__ = data; }",
                print_data,
            )

            # 5. Trigger a re-render by dispatching a custom event React listens for
            page.evaluate(
                "() => window.dispatchEvent(new CustomEvent('printDataReady'))"
            )

            # 6. Wait for the rendered output
            print("  Waiting for .print-chapter…")
            page.wait_for_selector(".print-chapter", timeout=30_000)

            # Extra wait for images / screenshots to settle
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass  # networkidle is a nice-to-have; don't fail the whole run

            # 7. Export
            pdf_path = OUTPUT_DIR / "pdfs" / f"{doc_type}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            page.pdf(
                path=str(pdf_path),
                print_background=True,
                format="A4",
            )
            print(f"  ✓ Saved {pdf_path}")
            page.close()

        browser.close()


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "type",
        nargs="?",
        default=None,
        choices=TYPES,
        help="Generate a single type; omit to generate all.",
    )
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--lecture-id", type=str, default="default")
    args = parser.parse_args()

    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected = [args.type] if args.type else TYPES
    generate_pdfs(lecture_id=args.lecture_id, types=selected)