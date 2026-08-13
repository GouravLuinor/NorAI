"""
Standalone test: P7.x Gemini context-cache module (tutor/cache.py).

Verifies the registry/hash/rolling-refresh logic and the system_instruction +
contents split WITHOUT any real API calls (the genai client is mocked).

Run directly: venv/bin/python tutor/test_cache.py
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["GEMINI_API_KEY"] = "test-key"

import google.genai.types as genai_types

from tutor import cache as tc

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


def _fake_cache(name: str, display_name: str) -> genai_types.CachedContent:
    cc = MagicMock(spec=genai_types.CachedContent)
    cc.name = name
    cc.display_name = display_name
    return cc


def test_estimate_tokens():
    check("4 chars ≈ 1 token", tc.estimate_tokens("abcd") == 1)
    check("empty -> 0", tc.estimate_tokens("") == 0)
    check("40k chars ≈ 10k tokens", tc.estimate_tokens("a" * 40000) == 10000)


def test_build_parts_splits_system_and_contents(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "lecture_outline.json").write_text('{"chapters": [{"title": "Intro"}]}')
    chapter = notes / "chapter_1.md"
    chapter.write_text("## Section\nlecture body text")

    system_text, contents_text = tc.build_cache_parts(
        "SYSTEM", "PERSONA", "SUMMARY", str(tmp_path)
    )
    check("system text has all three parts", "SYSTEM" in system_text and "PERSONA" in system_text and "SUMMARY" in system_text)
    check("contents holds lecture context", "lecture body text" in contents_text)
    check("system and contents disjoint", system_text != contents_text)


def test_build_parts_ignores_missing_lecture_dir():
    system_text, contents_text = tc.build_cache_parts("SYS", "", "", None)
    check("system text present", system_text == "SYS")
    check("no lecture dir -> empty contents", contents_text == "")


def test_prefix_hash_stable_and_sensitive():
    h1 = tc._prefix_hash("same prefix")
    h2 = tc._prefix_hash("same prefix")
    h3 = tc._prefix_hash("different")
    check("stable across calls", h1 == h2)
    check("12-char hash", len(h1) == 12)
    check("content-sensitive", h1 != h3)


def test_skips_below_min_tokens():
    tc.reset_registry()
    name = tc.get_or_create_prefix_cache("lect", "short", "also short")
    check("below min -> None", name is None)


def test_create_and_reuse_skips_network_on_hot_turn():
    tc.reset_registry()
    with patch.object(tc, "_get_client") as m:
        m.return_value.caches.create.side_effect = lambda **kw: _fake_cache(
            "caches/" + kw["config"].display_name, kw["config"].display_name
        )
        m.return_value.caches.list.return_value = []
        n1 = tc.get_or_create_prefix_cache("lect", "SYS " + "x" * 40000, "CONT " + "y" * 40000)
        check("created returns name", n1 == "caches/" + tc._display_name("lect", tc._prefix_hash("SYS " + "x" * 40000 + "\n\nCONT " + "y" * 40000)))
        # Hot turn: same hash -> registry hit, zero API calls.
        m.return_value.caches.create.reset_mock()
        m.return_value.caches.list.reset_mock()
        n2 = tc.get_or_create_prefix_cache("lect", "SYS " + "x" * 40000, "CONT " + "y" * 40000)
        check("hot turn reuses same name", n1 == n2)
        check("hot turn makes no create call", m.return_value.caches.create.call_count == 0)
        check("hot turn makes no list call", m.return_value.caches.list.call_count == 0)


def test_rolling_refresh_on_summary_change():
    tc.reset_registry()
    with patch.object(tc, "_get_client") as m:
        m.return_value.caches.create.side_effect = lambda **kw: _fake_cache(
            "caches/" + kw["config"].display_name, kw["config"].display_name
        )
        m.return_value.caches.list.return_value = []
        n1 = tc.get_or_create_prefix_cache("lect", "SYS " + "a" * 40000, "CONT " + "a" * 40000)
        m.return_value.caches.list.reset_mock()
        # Summary text changes -> new hash -> old cache deleted + new created.
        n2 = tc.get_or_create_prefix_cache("lect", "SYS " + "b" * 40000, "CONT " + "b" * 40000)
        check("new summary -> new cache name", n1 != n2 and n2 is not None)
        check("stale cache listed for deletion", m.return_value.caches.list.call_count >= 1)


def test_skips_without_lecture_key():
    tc.reset_registry()
    name = tc.get_or_create_prefix_cache("", "SYS " + "x" * 4000, "CONT")
    check("no lecture key -> None", name is None)


def test_delete_lecture_caches_clears_matching():
    tc.reset_registry()
    old = _fake_cache("caches/norai-lect-aaaaaaaaaaaa", "norai-lect-aaaaaaaaaaaa")
    other = _fake_cache("caches/norai-other-bbbbbbbbbb", "norai-other-bbbbbbbbbb")
    with patch.object(tc, "_get_client") as m:
        m.return_value.caches.list.return_value = [old, other]
        tc.delete_lecture_caches("lect")
        deleted = [c.kwargs.get("name") for c in m.return_value.caches.delete.call_args_list]
        check("deleted only lecture caches", deleted == ["caches/norai-lect-aaaaaaaaaaaa"])


def test_system_instruction_passed_to_create():
    tc.reset_registry()
    with patch.object(tc, "_get_client") as m:
        m.return_value.caches.create.side_effect = lambda **kw: _fake_cache(
            "caches/" + kw["config"].display_name, kw["config"].display_name
        )
        m.return_value.caches.list.return_value = []
        tc.get_or_create_prefix_cache("lect", "SYS_TEXT", "CONT_" + "y" * 40000)
        cfg = m.return_value.caches.create.call_args.kwargs["config"]
        check("system_instruction set on create config", cfg.system_instruction == "SYS_TEXT")
        check("contents carry the padding text", cfg.contents[0].parts[0].text == "CONT_" + "y" * 40000)


def test_create_failure_falls_back_to_none():
    tc.reset_registry()
    with patch.object(tc, "_get_client") as m:
        m.return_value.caches.create.side_effect = Exception("boom")
        m.return_value.caches.list.return_value = []
        name = tc.get_or_create_prefix_cache("lect", "SYS " + "x" * 40000, "CONT")
        check("create failure -> None (uncached fallback)", name is None)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_estimate_tokens()
        test_build_parts_splits_system_and_contents(Path(td))
        test_build_parts_ignores_missing_lecture_dir()
        test_prefix_hash_stable_and_sensitive()
        test_skips_below_min_tokens()
        test_create_and_reuse_skips_network_on_hot_turn()
        test_rolling_refresh_on_summary_change()
        test_skips_without_lecture_key()
        test_delete_lecture_caches_clears_matching()
        test_system_instruction_passed_to_create()
        test_create_failure_falls_back_to_none()
    print(f"\n{FAILED} failed / {PASSED} passed")
    sys.exit(1 if FAILED else 0)
