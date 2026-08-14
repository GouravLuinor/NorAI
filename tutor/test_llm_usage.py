"""
Standalone test: P6.5 tutor LLM usage accounting.

Verifies UsageLoggingChatLLM reads LangChain's `usage_metadata` keys
(input_tokens/output_tokens) — the bug fixed for P6.5 was that the old code read
Gemini's key names (prompt_token_count/candidates_token_count) which
langchain-google-genai converts away, so tokens were always None — and that
recorded calls accumulate into the `tutor` ledger stage.

Does NOT make any real API calls.

Run directly: venv/bin/python tutor/test_llm_usage.py
"""

import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["GEMINI_API_KEY"] = "test-key"

from backend import usage_ledger as ul
from tutor.llm import UsageLoggingChatLLM, TUTOR_STAGE

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


def _llm(node: str) -> UsageLoggingChatLLM:
    # model is a required ChatGoogleGenerativeAI field; google_api_key is never
    # used because we only exercise _tokens_from/_record with fake responses.
    return UsageLoggingChatLLM(node=node, model="gemini-3.5-flash-lite", google_api_key="test-key")


def test_tokens_from_langchain_keys():
    llm = _llm("test")
    usage = {"input_tokens": 111, "output_tokens": 222, "total_tokens": 333}
    prompt, completion = llm._tokens_from(usage)
    check("reads input_tokens", prompt == 111)
    check("reads output_tokens", completion == 222)


def test_tokens_from_gemini_keys_fallback():
    llm = _llm("test")
    usage = {"prompt_token_count": 444, "candidates_token_count": 555}
    prompt, completion = llm._tokens_from(usage)
    check("falls back to prompt_token_count", prompt == 444)
    check("falls back to candidates_token_count", completion == 555)


def test_tokens_from_empty():
    llm = _llm("test")
    check("empty usage -> None,None", llm._tokens_from({}) == (None, None))
    check("None usage -> None,None", llm._tokens_from(None) == (None, None))


def test_record_accumulates_into_tutor_ledger():
    ul.reset_usage()
    llm = _llm("generate_answer_node")

    class _FakeResp:
        usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    llm._record(_FakeResp())
    llm._record(_FakeResp())

    full = ul.diff_usage({})
    tutor = next((d for d in full if d["stage"] == TUTOR_STAGE), None)
    check("two calls recorded", tutor and tutor["calls"] == 2)
    check("tokens summed", tutor and tutor["input_tokens"] == 200 and tutor["output_tokens"] == 100)
    check("cost > 0", tutor and tutor["cost_usd"] > 0)
    check("node attributed", tutor and tutor["stage"] == "tutor")
    ul.reset_usage()


def test_record_handles_missing_metadata():
    ul.reset_usage()
    llm = _llm("test")

    class _Empty:
        pass

    llm._record(_Empty())
    full = ul.diff_usage({})
    tutor = next((d for d in full if d["stage"] == TUTOR_STAGE), None)
    check("missing metadata still counts call", tutor and tutor["calls"] == 1 and tutor["cost_usd"] == 0)
    ul.reset_usage()


def test_astream_records_one_aggregated_row():
    from langchain_google_genai import ChatGoogleGenerativeAI

    ul.reset_usage()
    llm = _llm("generate_answer_node")

    async def _fake_parent_astream(self, input, config=None, **kwargs):
        # Middle chunk carries the aggregated usage; a trailing chunk repeats
        # 0/0 (both patterns seen live). Must collapse to ONE ledger row with
        # the max tokens.
        yield type("C", (), {"usage_metadata": {"input_tokens": 300, "output_tokens": 120}})()
        yield type("C", (), {"usage_metadata": {"input_tokens": 0, "output_tokens": 0}})()
        yield type("C", (), {})

    async def run():
        with patch.object(ChatGoogleGenerativeAI, "astream", _fake_parent_astream):
            async for _ in llm.astream("hi"):
                pass
        full = ul.diff_usage({})
        return next((d for d in full if d["stage"] == TUTOR_STAGE), None)

    tutor = asyncio.run(run())
    check("single call", tutor and tutor["calls"] == 1)
    check("max prompt tokens", tutor and tutor["input_tokens"] == 300)
    check("max completion tokens", tutor and tutor["output_tokens"] == 120)
    ul.reset_usage()


if __name__ == "__main__":
    test_tokens_from_langchain_keys()
    test_tokens_from_gemini_keys_fallback()
    test_tokens_from_empty()
    test_record_accumulates_into_tutor_ledger()
    test_record_handles_missing_metadata()
    test_astream_records_one_aggregated_row()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)