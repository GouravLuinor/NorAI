"""
Offline tests for document intake (documents/): type sniffing, the PDF /
DOCX / PPTX / text extractors, the transcript adapter, the SSRF guard and link
rewriting, document-aware prompts / chapters / tutor context / citations, and
one document run through the content stages and tutor index with a fake Gemini.

    venv/bin/python documents/test_documents.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GEMINI_API_KEY", "test-offline-key-dummy")

from documents.adapter import Block, WORDS_PER_MINUTE, blocks_to_segments, quota_minutes  # noqa: E402
from documents.extract import DocumentError, extract_file, markdown_blocks, sniff  # noqa: E402
from documents.fetch import FetchError, check_url, is_public_ip, resolve_public, rewrite_link  # noqa: E402
from documents.kind import DOCUMENT, VIDEO, lecture_source_kind  # noqa: E402

WORDS = ("gradient descent updates each weight by a small step against the slope of the "
         "loss so the model slowly improves its predictions over many rounds").split()


def _text(n: int, seed: int = 0) -> str:
    return " ".join(WORDS[(i + seed) % len(WORDS)] for i in range(n)) + "."


def make_pdf(path: Path, pages: list[str]) -> None:
    """A minimal PDF with a Helvetica text layer (pdfium repairs the xref)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font_id = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        words = text.split()
        lines = [" ".join(words[j:j + 10]) for j in range(0, len(words), 10)]
        stream = "BT /F1 11 Tf 14 TL 50 750 Td " + " ".join(f"({ln}) Tj T*" for ln in lines) + " ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    body = "%PDF-1.4\n" + "".join(f"{n} 0 obj\n{o}\nendobj\n" for n, o in enumerate(objs, 1))
    path.write_bytes((body + "trailer\n<< /Root 1 0 R >>\n%%EOF\n").encode("latin-1"))


def make_docx(path: Path) -> None:
    import docx
    d = docx.Document()
    d.add_heading("Optimisation Basics", level=0)
    d.add_heading("Gradient descent", level=1)
    d.add_paragraph(_text(80))
    d.add_heading("Learning rate", level=1)
    d.add_paragraph(_text(70, 3))
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "rate", "effect"
    t.cell(1, 0).text, t.cell(1, 1).text = "0.1", "fast"
    d.save(str(path))


def make_pptx(path: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Neural Networks 101"
    s1.placeholders[1].text = _text(40)
    s1.notes_slide.notes_text_frame.text = "Remember to explain the slope intuition."
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    s2.shapes.title.text = "Backpropagation"
    box = s2.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(3))
    box.text_frame.text = _text(50, 5)
    prs.save(str(path))


# ── tests ─────────────────────────────────────────────────────────────────────

def test_adapter_segments_and_quota():
    blocks = [Block(_text(100), "p. 1"), Block(_text(30), "p. 2")]
    segs = blocks_to_segments(blocks)
    assert all(len(s["text"].split()) <= 60 for s in segs)
    assert [s["segment_id"] for s in segs] == list(range(len(segs)))
    assert segs[0]["start"] == 0 and segs[-1]["loc"] == "p. 2"
    words = sum(len(s["text"].split()) for s in segs)
    assert words == 130
    assert abs(segs[-1]["end"] - words * 60 / WORDS_PER_MINUTE) < 0.05
    for a, b in zip(segs, segs[1:]):
        assert a["end"] == b["start"]
    assert quota_minutes(6000) == 40 and quota_minutes(1) == 1


def test_sniff_and_extract_formats():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pdf, dx, px = td / "a.pdf", td / "b.docx", td / "c.pptx"
        make_pdf(pdf, [_text(60), _text(60, 2)])
        make_docx(dx)
        make_pptx(px)
        assert sniff(pdf) == "pdf" and sniff(dx) == "docx" and sniff(px) == "pptx"

        ex = extract_file(pdf, "pdf")
        assert ex.pages == 2 and [b.loc for b in ex.blocks] == ["p. 1", "p. 2"]
        assert "gradient descent" in ex.blocks[0].text

        ex = extract_file(dx, "docx")
        assert ex.title == "Optimisation Basics"
        locs = [b.loc for b in ex.blocks]
        assert "Gradient descent" in locs and "Learning rate" in locs
        assert any("0.1 | fast" in b.text for b in ex.blocks)

        ex = extract_file(px, "pptx")
        assert ex.pages == 2 and ex.title == "Neural Networks 101"
        assert [b.loc for b in ex.blocks] == ["Slide 1", "Slide 2"]
        assert "Speaker notes: Remember" in ex.blocks[0].text

        md = td / "n.md"
        md.write_text("# Title Here\n\n" + _text(30) + "\n\n## Part two\n\n" + _text(30), encoding="utf-8")
        assert sniff(md) == "md"
        ex = extract_file(md, "md")
        assert ex.title == "Title Here" and ex.blocks[-1].loc == "Part two"

        (td / "old.doc").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
        try:
            sniff(td / "old.doc")
            raise AssertionError("legacy .doc accepted")
        except DocumentError as e:
            assert ".docx" in str(e)
        (td / "bin.dat").write_bytes(b"\x00\x01\x02garbage")
        try:
            sniff(td / "bin.dat")
            raise AssertionError("binary accepted")
        except DocumentError:
            pass
        (td / "v.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
        assert sniff(td / "v.mp4") == "video"


def test_scanned_pdf_no_ocr_in_estimates():
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "scan.pdf"
        make_pdf(pdf, ["", "", "x"])
        ex = extract_file(pdf, "pdf", ocr=False)
        assert ex.scanned and ex.blocks == [] and ex.pages == 3


def test_markdown_blocks_without_headings():
    blocks, title = markdown_blocks("just text\n\nmore text")
    assert title == "" and [b.loc for b in blocks] == ["Start", "Start"]


def test_web_page_back_matter_and_title():
    from documents.extract import extract_html
    body = "\n".join(f"<p>{_text(80, i)}</p>" for i in range(4))
    html = (
        "<html><head><title>Bubble sort - Wikipedia</title></head><body><article>"
        "<h1>Bubble sort</h1>" + body +
        "<h2>History [edit]</h2>" + body +
        "<h2>References</h2><ul><li>Knuth, D. (1998). The Art of Computer Programming.</li></ul>"
        "<h2>External links</h2><p>Animated sorting algorithms, an archived page.</p>"
        "</article></body></html>")
    ex = extract_html(html)
    locs = {b.loc for b in ex.blocks}
    assert ex.title == "Bubble sort", ex.title
    assert "References" not in locs and "External links" not in locs, locs
    assert "History" in locs, locs
    assert not any("[edit]" in b.text for b in ex.blocks)


def test_ssrf_guard():
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "100.64.1.1",
               "::1", "fe80::1", "::ffff:127.0.0.1", "0.0.0.0", "224.0.0.1"):
        assert not is_public_ip(ip), ip
    assert is_public_ip("8.8.8.8") and is_public_ip("2606:4700:4700::1111")
    for bad in ("ftp://x.com/a", "file:///etc/passwd", "http://user:pw@x.com/", "http://x.com:8080/",
                "javascript:alert(1)", "http:///nohost"):
        try:
            check_url(bad)
            raise AssertionError(f"accepted {bad}")
        except FetchError:
            pass
    assert check_url("https://example.com/a") == ("https", "example.com", 443)
    try:
        resolve_public("localhost", 80)
        raise AssertionError("localhost resolved as public")
    except FetchError as e:
        assert "private or local" in str(e)


def test_redirect_to_private_address_is_blocked():
    import httpx
    import documents.fetch as fetch

    calls = []

    def fake_send(self, request, stream=False):
        calls.append((str(request.url), request.headers.get("host")))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"},
                              request=request)

    orig_send, orig_resolve = httpx.Client.send, fetch.resolve_public
    httpx.Client.send = fake_send
    fetch.resolve_public = lambda host, port: "93.184.215.14" if host == "public.example" else orig_resolve(host, port)
    try:
        with tempfile.TemporaryDirectory() as td:
            try:
                fetch.safe_download("https://public.example/start", td)
                raise AssertionError("followed a redirect to a private address")
            except FetchError as e:
                assert "private or local" in str(e)
    finally:
        httpx.Client.send, fetch.resolve_public = orig_send, orig_resolve
    # The first hop went to the checked IP, with the real Host header.
    assert calls == [("https://93.184.215.14/start", "public.example")]


def test_rewrite_links():
    assert rewrite_link("https://docs.google.com/document/d/1AbCdEfGhIjK/edit?usp=sharing") == \
        "https://docs.google.com/document/d/1AbCdEfGhIjK/export?format=docx"
    assert rewrite_link("https://docs.google.com/presentation/d/1AbCdEfGhIjK/edit#slide=id.p") == \
        "https://docs.google.com/presentation/d/1AbCdEfGhIjK/export?format=pptx"
    assert "dl=1" in rewrite_link("https://www.dropbox.com/s/abc/notes.pdf?dl=0")
    assert rewrite_link("https://example.com/a.pdf") == "https://example.com/a.pdf"


def test_prompts_have_no_video_words_for_documents():
    from lean.chapters import _PROMPT, prompt_fields
    from tutor.prompts import build_context_block, build_system_prompt

    kw = dict(n=1, total=2, lecture_title="T", title="C", summary="S", concepts="a", neighbours="",
              transcript="[p. 1] hi", words=300, transcript_words=500, sections=3)
    doc = _PROMPT.format(**prompt_fields(DOCUMENT, 0), **kw).lower()
    vid = _PROMPT.format(**prompt_fields(VIDEO, 4), **kw).lower()
    for w in ("lecture", "transcript", "frame", "video", "timestamp"):
        assert w not in doc, w
    assert "frames: exactly 4 entries" in vid
    for mode in ("default", "socratic"):
        p = build_system_prompt("T", mode, DOCUMENT).lower()
        for w in ("lecture", "transcript", "timestamp", "video"):
            assert w not in p, (mode, w)
    block = build_context_block([{"kind": "transcript", "start": 0, "end": 9, "text": "x", "loc": "Slide 3"}],
                                source_kind=DOCUMENT)
    assert "[Slide 3] x" in block and "lecture" not in block.lower()


def test_chapter_section_loc_and_tags():
    from lean.chapters import section_loc, transcript_lines
    from lean.structure import tagged_transcript

    segs = [{"segment_id": 0, "start": 0.0, "end": 10.0, "text": "a", "loc": "p. 3"},
            {"segment_id": 1, "start": 10.0, "end": 20.0, "text": "b", "loc": "p. 4"},
            {"segment_id": 2, "start": 20.0, "end": 30.0, "text": "c", "loc": "Learning rate schedules"}]
    assert transcript_lines(segs).splitlines()[1] == "[p. 4] b"
    assert section_loc("p. 4", segs) == (10.0, "p. 4")
    assert section_loc("[Page 4]", segs) == (10.0, "p. 4")
    assert section_loc("Learning rate", segs) == (20.0, "Learning rate schedules")
    assert section_loc("p. 99", segs) is None
    assert tagged_transcript([{"chunk_id": 0, "start": 0, "text": "x", "loc": "Slide 2"}]).startswith("[chunk 0 | Slide 2]")
    assert tagged_transcript([{"chunk_id": 0, "start": 65, "text": "x"}]).startswith("[chunk 0 | 1:05]")


def test_document_sections_reading_order():
    from lean.chapters import place_document_sections

    segs = [{"start": 10.0, "loc": "p. 1"}, {"start": 20.0, "loc": "p. 2"}]
    secs = [
        {"title": "B", "start_sec": 20.0, "loc": "p. 2"},
        {"title": "A", "start_sec": 10.0, "loc": "p. 1"},
        {"title": "Out", "start_sec": None, "loc": None},      # cites p. 99: after A
        {"title": "C", "start_sec": 20.0, "loc": "p. 2"},
    ]
    out = place_document_sections(secs, segs)
    assert [s["title"] for s in out] == ["A", "Out", "B", "C"]
    assert all(s["start_sec"] is not None for s in out)
    out_sec = next(s for s in out if s["title"] == "Out")
    assert out_sec["loc"] is None and out_sec["start_sec"] == 10.0
    # a leading unplaceable section takes the chapter's first segment
    lead = place_document_sections([{"title": "X", "start_sec": None, "loc": None}], segs)
    assert lead[0]["start_sec"] == 10.0
    assert place_document_sections([], segs) == []


def test_document_citations():
    from tutor.citations import verified_citations

    chunks = [{"kind": "transcript", "loc": "p. 4–5", "locs": ["p. 4", "p. 5"], "start": 10, "end": 30, "chunk_id": "a"},
              {"kind": "notes", "heading_path": "Ch > Learning rate", "heading": "Learning rate", "chunk_id": "n"}]
    ans = "x\n\n**Sources**\n• p. 5 — step size\n• Page 4: definition\n• Learning rate\n• p. 9 — invented"
    got = {c["section"]: c["chunk_id"] for c in verified_citations(ans, chunks)}
    assert got == {"p. 5 — step size": "a", "Page 4: definition": "a", "Learning rate": "n"}
    # Video lectures keep timestamp matching.
    vid = [{"kind": "transcript", "start": 100.0, "end": 140.0, "chunk_id": "t"}]
    assert verified_citations("y\n**Sources**\n• 1:50 — thing", vid)[0]["chunk_id"] == "t"


def _fake_chapter(n_sections_start: str):
    return {
        "study_notes_title": "Chapter",
        "study_notes_sections": [
            {"section_type": "prose", "title": "One", "content_markdown": "Body", "start": n_sections_start},
            {"section_type": "list", "title": "Two", "content_markdown": "- a", "start": "nowhere"},
        ],
        "revision_summary": ["r1", "r2", "r3"],
        "core_concepts_breakdown": [{"concept": "c", "explanation": "e"}],
        "assessment_questions": [
            {"question_id": 1, "chapter_id": 1, "type": "MCQ", "difficulty": "Easy", "concepts": ["c"],
             "question": "Which?", "options": ["A", "B", "C", "D"], "answer": "B",
             "flashcard_front": "Which?", "flashcard_back": "B"},
        ],
    }


def test_document_end_to_end_with_fake_gemini():
    import lean.chapters as lc
    import lean.structure as ls
    from documents.intake import prepare_source
    from lean.pipeline import run_content_stages
    from tutor.indexing import build_lecture_index
    from tutor.vector_store import VectorStore, index_dir

    prompts: list[str] = []

    class _Models:
        def generate_content(self, model, contents, config):
            text = contents if isinstance(contents, str) else contents[0]
            prompts.append(text)
            if "Divide the document" in text:
                body = {"lecture_title": "Optimisation Basics", "chapters": [
                    {"title": "Descent", "start_chunk": 0, "end_chunk": 0, "focus_concepts": ["slope"], "summary": "s"},
                    {"title": "Rates", "start_chunk": 1, "end_chunk": 99, "focus_concepts": ["rate"], "summary": "s"},
                ]}
            else:
                body = _fake_chapter("Learning rate" if "Rates" in text else "Gradient descent")
            return SimpleNamespace(text=json.dumps(body), usage_metadata=None)

    fake = lambda: SimpleNamespace(models=_Models())  # noqa: E731
    orig = (lc.get_client, lc.record_generate_usage, ls.get_client, ls.record_generate_usage)
    lc.get_client = ls.get_client = fake
    lc.record_generate_usage = ls.record_generate_usage = lambda *a, **k: None
    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "upload_lecture.docx"
            make_docx(src)
            # Enough text for two chunks (15 segments of ~40 words each).
            import docx
            d = docx.Document(str(src))
            for i in range(20):
                d.add_paragraph(_text(45, i))
            d.save(str(src))
            out = td / "lec"
            out.mkdir()
            prep = prepare_source("upload", str(out), file_path=str(src))
            assert prep.kind == DOCUMENT and prep.doc_type == "docx" and prep.words > 900
            assert lecture_source_kind(out) == DOCUMENT
            result = run_content_stages(str(out), prep.transcript_path, None, source_title=prep.title,
                                        duration_sec=prep.duration_sec, source_kind=DOCUMENT)
            assert result["num_chapters"] == 2 and result["degraded"] == 0
            assert all("lecture" not in p.lower().replace("lecture_title", "") for p in prompts), \
                "video wording leaked into a document prompt"
            assert all("frames" not in p for p in prompts[1:])
            ch2 = json.loads((out / "notes" / "chapter_2.json").read_text())
            assert ch2["sections"][0]["loc"] == "Learning rate" and ch2["sections"][0]["start_sec"] is not None
            assert ch2["sections"][1]["loc"] is None
            assert not (out / "screenshots" / "selected" / "chapter_1_screenshots.json").exists() or \
                json.loads((out / "screenshots" / "selected" / "chapter_1_screenshots.json").read_text())["screenshots"] == []

            class _Embed:
                model = "fake-embed"

                def __call__(self, docs):
                    return [[float(len(t) % 7 + 1)] + [0.5] * 767 for t in docs]

            build_lecture_index(out, embed=_Embed())
            store = VectorStore.open(index_dir(out))
            tx = [m for m in store.metas if m.get("kind") == "transcript"]
            assert tx and all(m.get("loc") for m in tx)
            assert tx[0]["heading"] == tx[0]["loc"]
    finally:
        lc.get_client, lc.record_generate_usage, ls.get_client, ls.record_generate_usage = orig


def test_video_kind_default():
    with tempfile.TemporaryDirectory() as td:
        assert lecture_source_kind(td) == VIDEO
        assert lecture_source_kind(None) == VIDEO


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"FAIL {name}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
