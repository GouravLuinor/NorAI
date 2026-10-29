"""
test_generate_nonempty.py — empty-reply retries in backend/gemini_client.py.

No API calls: fake responses stand in for generate_content.
Run directly: venv/bin/python backend/test_generate_nonempty.py
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.gemini_client import empty_reason, generate_nonempty  # noqa: E402


def _resp(text, finish="STOP"):
    return SimpleNamespace(text=text, prompt_feedback=None,
                           candidates=[SimpleNamespace(finish_reason=finish)])


def _calls(*responses):
    it = iter(responses)
    calls = []

    def fn():
        calls.append(1)
        return next(it)
    return fn, calls


def test_empty_then_text_is_retried():
    fn, calls = _calls(_resp(None, "OTHER"), _resp('{"ok": 1}'))
    assert generate_nonempty(fn, node="t").text == '{"ok": 1}'
    assert len(calls) == 2, calls


def test_persistent_empty_raises_with_reason():
    fn, calls = _calls(*[_resp(None, "RECITATION")] * 3)
    try:
        generate_nonempty(fn, node="t", attempts=3)
    except ValueError as e:
        assert "RECITATION" in str(e), e
    else:
        raise AssertionError("expected ValueError")
    assert len(calls) == 3, calls


def test_empty_reason_variants():
    assert empty_reason(None) == "no response"
    assert empty_reason(SimpleNamespace(prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
                                        candidates=None)) == "prompt blocked: SAFETY"
    assert empty_reason(SimpleNamespace(prompt_feedback=None, candidates=[])) == "no candidates"


if __name__ == "__main__":
    test_empty_then_text_is_retried()
    test_persistent_empty_raises_with_reason()
    test_empty_reason_variants()
    print("test_generate_nonempty: 3/3 passed")
