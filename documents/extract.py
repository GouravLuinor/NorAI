"""
documents/extract.py — file → list[Block] (+ title, page count).

| Input       | Library      | loc                         |
|-------------|--------------|-----------------------------|
| PDF         | pypdfium2    | "p. N" (scanned → Gemini)   |
| DOCX        | python-docx  | nearest heading             |
| PPTX        | python-pptx  | "Slide N" (+ speaker notes) |
| HTML        | trafilatura  | nearest heading             |
| .txt / .md  | —            | nearest markdown heading    |

All permissive licences (PyMuPDF is AGPL, so not used). Legacy .doc/.ppt are
rejected with "save as .docx/.pptx": LibreOffice is too heavy for the box.
"""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from documents.adapter import Block

logger = logging.getLogger(__name__)

DOC_TYPES = ("pdf", "docx", "pptx", "txt", "md", "html")
DOC_EXTENSIONS = {".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".txt": "txt",
                  ".md": "md", ".markdown": "md", ".html": "html", ".htm": "html"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

# Below this many words per page a PDF has no usable text layer (scanned).
SCANNED_WORDS_PER_PAGE = 15
SCANNED_PAGES_PER_CALL = 10
MAX_SCANNED_PAGES = int(os.environ.get("NORAI_MAX_SCANNED_PAGES", "60"))
LOC_MAX_CHARS = 60


class DocumentError(ValueError):
    """A document we can't read, with a message fit to show the user."""


@dataclass
class Extracted:
    blocks: list[Block]
    title: str
    doc_type: str
    pages: int | None = None
    scanned: bool = False   # no text layer; blocks empty when read with ocr=False


# ── type detection ────────────────────────────────────────────────────────────

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def sniff(path: str | Path, name_hint: str = "", content_type: str = "") -> str:
    """Detect a file's type from its bytes, name and HTTP content type.
    Returns a DOC_TYPES entry or "video". Raises DocumentError otherwise."""
    path = Path(path)
    with open(path, "rb") as f:
        head = f.read(4096)
    ext = Path(name_hint or path.name).suffix.lower()
    ctype = (content_type or "").split(";")[0].strip().lower()

    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(_OLE_MAGIC):
        raise DocumentError("Old Office formats (.doc / .ppt) aren't supported. "
                            "Save the file as .docx or .pptx and upload that.")
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
        except zipfile.BadZipFile as e:
            raise DocumentError("This file looks damaged and can't be opened.") from e
        if any(n.startswith("word/") for n in names):
            return "docx"
        if any(n.startswith("ppt/") for n in names):
            return "pptx"
        if any(n.startswith("xl/") for n in names):
            raise DocumentError("Spreadsheets aren't supported yet. Upload a PDF, DOCX, PPTX or video.")
        raise DocumentError("Unsupported archive. Upload a PDF, DOCX, PPTX, text file or video.")
    if len(head) >= 8 and head[4:8] == b"ftyp" or head.startswith(b"\x1a\x45\xdf\xa3") \
            or (head.startswith(b"RIFF") and head[8:12] == b"AVI "):
        return "video"
    if ctype.startswith("video/") and ext in VIDEO_EXTENSIONS:
        return "video"
    if b"\x00" in head:
        raise DocumentError("Unsupported file type. Upload a PDF, DOCX, PPTX, text file or video.")
    low = head.lstrip().lower()
    if ctype in ("text/html", "application/xhtml+xml") or low.startswith((b"<!doctype html", b"<html")) \
            or ext in (".html", ".htm"):
        return "html"
    if ext in (".md", ".markdown") or ctype == "text/markdown":
        return "md"
    if ext == ".txt" or ctype.startswith("text/") or not ext:
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            # Only fail on a broken char that isn't just cut at the 4 KB edge.
            try:
                head[:-4].decode("utf-8")
            except UnicodeDecodeError as e:
                raise DocumentError("This text file isn't UTF-8 encoded.") from e
        return "txt"
    raise DocumentError("Unsupported file type. Upload a PDF, DOCX, PPTX, text file or video.")


# ── helpers ───────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # de-hyphenate line breaks
    return text


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= LOC_MAX_CHARS else text[: LOC_MAX_CHARS - 1].rstrip() + "…"


def _fallback_title(path: Path) -> str:
    # Uploads are saved as "<uuid>_<name>" (estimates: "est-<uuid>_<name>").
    return re.sub(r"^(?:est-)?[0-9a-f-]{36}_", "", path.stem).replace("_", " ").strip() or "Untitled document"


_MD_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


def markdown_blocks(text: str, default_loc: str = "Start") -> tuple[list[Block], str]:
    """Paragraph blocks under their nearest heading. Returns (blocks, first H1/H2)."""
    blocks: list[Block] = []
    loc, title = default_loc, ""
    para: list[str] = []

    def flush():
        if para:
            body = " ".join(" ".join(para).split())
            if body:
                blocks.append(Block(body, loc))
            para.clear()

    for line in _clean(text).split("\n"):
        m = _MD_HEADING.match(line)
        if m:
            flush()
            heading = re.sub(r"[*_`]", "", m.group(2)).strip()
            if heading:
                loc = _short(heading)
                title = title or (heading if len(m.group(1)) <= 2 else "")
                blocks.append(Block(heading, loc))
            continue
        if not line.strip():
            flush()
        else:
            para.append(line.strip())
    flush()
    return blocks, title


# ── PDF ───────────────────────────────────────────────────────────────────────

def extract_pdf(path: Path, ocr: bool = True) -> Extracted:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as e:
        raise DocumentError("This PDF can't be opened (damaged or password-protected).") from e
    try:
        n_pages = len(pdf)
        if n_pages == 0:
            raise DocumentError("This PDF has no pages.")
        title = (pdf.get_metadata_value("Title") or "").strip()
        blocks: list[Block] = []
        for i in range(n_pages):
            page = pdf[i]
            try:
                tp = page.get_textpage()
                text = _clean(tp.get_text_range())
                tp.close()
            finally:
                page.close()
            if text.strip():
                blocks.append(Block(" ".join(text.split()), f"p. {i + 1}"))
        words = sum(len(b.text.split()) for b in blocks)
        if words < SCANNED_WORDS_PER_PAGE * n_pages:
            logger.info("PDF %s: %d words over %d pages, treating as scanned", path.name, words, n_pages)
            if not ocr:  # estimates must never make a Gemini call
                return Extracted([], title or _fallback_title(path), "pdf", n_pages, scanned=True)
            blocks = _ocr_pdf_with_gemini(pdf, n_pages)
    finally:
        pdf.close()
    if not title and blocks:
        title = _short(blocks[0].text) if len(blocks[0].text) < 80 else ""
    return Extracted(blocks, title or _fallback_title(path), "pdf", n_pages)


def _ocr_pdf_with_gemini(pdf, n_pages: int) -> list[Block]:
    """Scanned PDF: send pages to Gemini natively (in batches) for their text."""
    import pypdfium2 as pdfium
    from google.genai import types
    from pydantic import BaseModel

    from backend.gemini_client import generate_nonempty, get_client
    from backend.usage_ledger import record_generate_usage
    from config import MODEL_NAME

    if n_pages > MAX_SCANNED_PAGES:
        raise DocumentError(
            f"This PDF is scanned (no text layer) and has {n_pages} pages; scanned PDFs "
            f"are limited to {MAX_SCANNED_PAGES} pages. Run OCR on it first or split it."
        )

    class PageText(BaseModel):
        page: int
        text: str

    class Pages(BaseModel):
        pages: list[PageText]

    blocks: list[Block] = []
    for a in range(0, n_pages, SCANNED_PAGES_PER_CALL):
        b = min(n_pages, a + SCANNED_PAGES_PER_CALL)
        part = pdfium.PdfDocument.new()
        part.import_pages(pdf, list(range(a, b)))
        buf = io.BytesIO()
        part.save(buf)
        part.close()
        prompt = (
            f"This PDF holds pages {a + 1} to {b} of a scanned document. Transcribe the "
            f"readable text of every page, in reading order, as plain text (equations "
            f"as LaTeX). Return one entry per page with page numbered {a + 1}..{b}. "
            "Do not summarise or add anything."
        )

        def _call(data=buf.getvalue(), prompt=prompt):
            resp = get_client().models.generate_content(
                model=MODEL_NAME,
                contents=[types.Part.from_bytes(data=data, mime_type="application/pdf"), prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, response_mime_type="application/json", response_schema=Pages,
                    max_output_tokens=32768,
                ),
            )
            record_generate_usage("transcription", MODEL_NAME, resp)
            return resp

        got = Pages.model_validate_json(generate_nonempty(_call, node="Scanned PDF").text)
        for p in sorted(got.pages, key=lambda p: p.page):
            if p.text.strip() and a + 1 <= p.page <= b:
                blocks.append(Block(" ".join(_clean(p.text).split()), f"p. {p.page}"))
    if not blocks:
        raise DocumentError("No readable text was found in this scanned PDF.")
    return blocks


# ── DOCX ──────────────────────────────────────────────────────────────────────

def extract_docx(path: Path) -> Extracted:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        d = docx.Document(str(path))
    except Exception as e:  # noqa: BLE001 — python-docx raises several types
        raise DocumentError("This Word file can't be opened (damaged or protected).") from e
    title = (d.core_properties.title or "").strip()
    blocks: list[Block] = []
    loc = "Start"
    for item in d.iter_inner_content():
        if isinstance(item, Paragraph):
            text = item.text.strip()
            if not text:
                continue
            style = (item.style.name if item.style is not None else "") or ""
            if style.startswith(("Heading", "Title")):
                loc = _short(text)
                if style == "Title" or (not title and style == "Heading 1"):
                    title = title or text
                blocks.append(Block(text, loc))
                continue
            blocks.append(Block(text, loc))
        elif isinstance(item, Table):
            rows = []
            for row in item.rows:
                cells = []
                for c in row.cells:
                    t = " ".join(c.text.split())
                    if t and (not cells or cells[-1] != t):  # merged cells repeat
                        cells.append(t)
                if cells:
                    rows.append(" | ".join(cells) + ".")
            if rows:
                blocks.append(Block(" ".join(rows), loc))
    if all(b.loc == "Start" for b in blocks):  # no headings: label stretches "Part N"
        blocks = _parts(blocks)
    return Extracted(blocks, title or _fallback_title(path), "docx")


def _parts(blocks: list[Block], words_per_part: int = 400) -> list[Block]:
    out, words = [], 0
    for b in blocks:
        out.append(Block(b.text, f"Part {words // words_per_part + 1}"))
        words += len(b.text.split())
    return out


# ── PPTX ──────────────────────────────────────────────────────────────────────

def extract_pptx(path: Path) -> Extracted:
    from pptx import Presentation

    try:
        prs = Presentation(str(path))
    except Exception as e:  # noqa: BLE001
        raise DocumentError("This PowerPoint file can't be opened (damaged or protected).") from e
    title = (prs.core_properties.title or "").strip()
    blocks: list[Block] = []

    def shape_text(shape) -> list[str]:
        out = []
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            for p in shape.text_frame.paragraphs:
                t = "".join(r.text for r in p.runs).strip()
                if t:
                    out.append(t if t[-1] in ".!?:;" else t + ".")
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                cells = [" ".join(c.text.split()) for c in row.cells if c.text.strip()]
                if cells:
                    out.append(" | ".join(cells) + ".")
        for sub in getattr(shape, "shapes", []) or []:  # groups
            out.extend(shape_text(sub))
        return out

    for n, slide in enumerate(prs.slides, 1):
        loc = f"Slide {n}"
        parts: list[str] = []
        heading = ""
        if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
            heading = slide.shapes.title.text_frame.text.strip()
        for shape in slide.shapes:
            parts.extend(shape_text(shape))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if notes:
                parts.append("Speaker notes: " + notes)
        if parts:
            blocks.append(Block(" ".join(parts), loc))
        if n == 1 and heading and not title:
            title = heading
    return Extracted(blocks, title or _fallback_title(path), "pptx", len(prs.slides))


# ── HTML / text ───────────────────────────────────────────────────────────────

def extract_html(html: str | bytes, url: str | None = None, fallback_title: str = "") -> Extracted:
    import trafilatura

    text = trafilatura.extract(html, url=url, output_format="markdown", include_comments=False,
                               include_tables=True, favor_recall=True)
    if not text or len(text.split()) < 50:
        raise DocumentError("Couldn't find the main text on this page. Pages that need JavaScript "
                            "or a login can't be read; save it as PDF and upload that instead.")
    meta = trafilatura.extract_metadata(html, default_url=url)
    blocks, md_title = markdown_blocks(text)
    title = ((meta.title if meta else "") or md_title or fallback_title or "Web page").strip()
    return Extracted(blocks, title, "html")


def extract_text(path: Path, doc_type: str) -> Extracted:
    raw = path.read_bytes().decode("utf-8", errors="replace")
    if doc_type == "html":
        return extract_html(raw, fallback_title=_fallback_title(path))
    blocks, md_title = markdown_blocks(raw)
    if all(b.loc == "Start" for b in blocks):
        blocks = _parts(blocks)
    return Extracted(blocks, md_title or _fallback_title(path), doc_type)


def extract_file(path: str | Path, doc_type: str, ocr: bool = True) -> Extracted:
    path = Path(path)
    if doc_type == "pdf":
        ex = extract_pdf(path, ocr=ocr)
        if ex.scanned and not ex.blocks:
            return ex
    elif doc_type == "docx":
        ex = extract_docx(path)
    elif doc_type == "pptx":
        ex = extract_pptx(path)
    elif doc_type in ("txt", "md", "html"):
        ex = extract_text(path, doc_type)
    else:
        raise DocumentError(f"Unsupported document type {doc_type!r}.")
    if not ex.blocks or sum(len(b.text.split()) for b in ex.blocks) < 20:
        raise DocumentError("This document has too little readable text to make study notes from.")
    return ex
