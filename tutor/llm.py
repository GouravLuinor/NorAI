"""
tutor/llm.py — ChatGoogleGenerativeAI factory (P5.1).

Central place to construct the tutor's chat LLM. Every LLM call goes through
`make_chat_llm(...)`, which returns a subclass that records Gemini usage
metadata (prompt/completion tokens) to `outputs/llm_calls.jsonl` — joined with
the bound log context (lecture_id / thread_id / request_id) when present.

Defensive by design: if usage metadata is absent (FakeLLMs in tests, older
responses) or the JSONL append fails, logging is a silent no-op — it must never
break a tutor turn.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from config import DEFAULT_MAX_RETRIES, MODEL_NAME, TEMPERATURE, get_api_key

logger = logging.getLogger(__name__)

LLM_CALLS_FILE = Path("outputs/llm_calls.jsonl")

_write_lock = threading.Lock()


def log_llm_call(
    node: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    **extra: Any,
) -> None:
    """Append one LLM-usage record to outputs/llm_calls.jsonl (thread-safe)."""
    try:
        from backend.logging_config import get_context

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        record.update(extra)
        record.update(get_context())
        LLM_CALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock, LLM_CALLS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        logger.debug("llm usage logging failed", exc_info=True)


class UsageLoggingChatLLM(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI that records per-call Gemini usage to JSONL."""

    def __init__(self, node: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._llm_node = node

    def _record(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None) or {}
        if not usage:
            return
        log_llm_call(
            node=self._llm_node,
            model=getattr(self, "model", MODEL_NAME),
            prompt_tokens=usage.get("prompt_token_count"),
            completion_tokens=usage.get("candidates_token_count"),
        )

    async def ainvoke(self, input, config=None, **kwargs: Any) -> Any:
        response = await super().ainvoke(input, config=config, **kwargs)
        try:
            self._record(response)
        except Exception:  # noqa: BLE001
            logger.debug("llm usage logging failed", exc_info=True)
        return response

    def invoke(self, input, config=None, **kwargs: Any) -> Any:
        response = super().invoke(input, config=config, **kwargs)
        try:
            self._record(response)
        except Exception:  # noqa: BLE001
            logger.debug("llm usage logging failed", exc_info=True)
        return response


def make_chat_llm(
    node: str,
    model: str = MODEL_NAME,
    temperature: float = TEMPERATURE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    **kwargs: Any,
) -> UsageLoggingChatLLM:
    """Build a usage-logging chat LLM for the given tutor node.

    Must be called from an async node (get_api_key may raise if the key is
    missing). Extra kwargs (e.g. google_api_key) are passed through.
    """
    return UsageLoggingChatLLM(
        node=node,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        google_api_key=get_api_key(),
        **kwargs,
    )
