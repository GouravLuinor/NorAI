"""
tutor/llm.py — ChatGoogleGenerativeAI factory (P5.1 / P6.5).

Central place to construct the tutor's chat LLM. Every LLM call goes through
`make_chat_llm(...)`, which returns a subclass that records Gemini usage
metadata (prompt/completion tokens + estimated USD cost) via
`backend.usage_ledger` — appended to `outputs/llm_calls.jsonl` and accumulated
into the per-stage ledger that `/chat` + `/chat/stream` flush to UsageLog
(P6.5 cost dashboard).

Defensive by design: if usage metadata is absent (FakeLLMs in tests, older
responses) or the ledger append fails, logging is a silent no-op — it must never
break a tutor turn.
"""

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from config import DEFAULT_MAX_RETRIES, MODEL_NAME, TEMPERATURE, get_api_key
from backend.usage_ledger import record_llm_usage

# Tutor turns accumulate under this ledger stage so the chat handlers can diff
# it after a turn and write a single UsageLog row (stage="tutor").
TUTOR_STAGE = "tutor"


class UsageLoggingChatLLM(ChatGoogleGenerativeAI):
    """ChatGoogleGenerativeAI that records per-call Gemini usage.

    P6.1: also overrides `astream` so real token streaming (graph
    `astream_events`) still logs aggregated usage for the streamed call. Token
    chunks are passed through untouched — only the LAST chunk (which carries the
    response's usage_metadata) triggers a log write.

    P6.5: reads LangChain's `usage_metadata` keys (`input_tokens` /
    `output_tokens`) — langchain-google-genai converts Gemini's
    `prompt_token_count` / `candidates_token_count` to those keys
    (`chat_models.py:_convert`), so the old Gemini key names always read None.
    Falls back to the Gemini key names defensively.
    """

    def __init__(self, node: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._llm_node = node

    def _tokens_from(self, usage: dict[str, Any]) -> tuple[int | None, int | None]:
        """Extract (prompt, completion) tokens from a usage metadata dict."""
        if not usage:
            return None, None
        prompt = usage.get("input_tokens")
        completion = usage.get("output_tokens")
        if prompt is None or completion is None:
            # Defensive fallback to raw Gemini key names.
            prompt = usage.get("prompt_token_count", prompt)
            completion = usage.get("candidates_token_count", completion)
        return prompt, completion

    def _cached_tokens_from(self, usage: dict[str, Any]) -> int:
        """Extract cached-input tokens served from a context cache.

        P7.x: LangChain folds Gemini's `cached_content_token_count` into
        `usage_metadata.input_token_details.cache_read` (chat_models.py
        `_response_to_result`). The raw Gemini key is a defensive fallback.
        """
        if not usage:
            return 0
        details = usage.get("input_token_details") or {}
        cached = details.get("cache_read")
        if cached is None:
            cached = usage.get("cached_content_token_count")
        return int(cached or 0)

    def _record(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None) or {}
        prompt, completion = self._tokens_from(usage)
        cached = self._cached_tokens_from(usage)
        record_llm_usage(
            TUTOR_STAGE,
            model=getattr(self, "model", MODEL_NAME),
            prompt_tokens=prompt,
            completion_tokens=completion,
            cached_input_tokens=cached,
            node_override=self._llm_node,
        )

    async def ainvoke(self, input, config=None, **kwargs: Any) -> Any:
        response = await super().ainvoke(input, config=config, **kwargs)
        try:
            self._record(response)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("llm usage logging failed", exc_info=True)
        return response

    def invoke(self, input, config=None, **kwargs: Any) -> Any:
        response = super().invoke(input, config=config, **kwargs)
        try:
            self._record(response)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("llm usage logging failed", exc_info=True)
        return response

    async def astream(self, input, config=None, **kwargs: Any) -> Any:
        # The aggregated usage_metadata rides on a middle/last chunk (and the
        # trailing chunk often repeats 0/0), so record a SINGLE log write from
        # the max tokens seen across the stream once it completes.
        max_prompt = 0
        max_completion = 0
        max_cached = 0
        async for chunk in super().astream(input, config=config, **kwargs):
            try:
                usage = getattr(chunk, "usage_metadata", None) or {}
                prompt, completion = self._tokens_from(usage)
                max_prompt = max(max_prompt, prompt or 0)
                max_completion = max(max_completion, completion or 0)
                max_cached = max(max_cached, self._cached_tokens_from(usage))
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).debug("llm usage logging failed", exc_info=True)
            yield chunk
        if max_prompt or max_completion or max_cached:
            record_llm_usage(
                TUTOR_STAGE,
                model=getattr(self, "model", MODEL_NAME),
                prompt_tokens=max_prompt,
                completion_tokens=max_completion,
                cached_input_tokens=max_cached,
                node_override=self._llm_node,
            )


def make_chat_llm(
    node: str,
    model: str = MODEL_NAME,
    temperature: float = TEMPERATURE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    cached_content: str | None = None,
    **kwargs: Any,
) -> UsageLoggingChatLLM:
    """Build a usage-logging chat LLM for the given tutor node.

    Must be called from an async node (get_api_key may raise if the key is
    missing). Extra kwargs (e.g. google_api_key) are passed through.

    P7.x context caching: when `cached_content` names an existing Gemini cache,
    the request is served against that cache (cached input billed at the cached
    rate). The caller MUST NOT re-send the cached tokens as messages — the cache
    is the prefix; only the dynamic suffix belongs in the request.
    """
    return UsageLoggingChatLLM(
        node=node,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        google_api_key=get_api_key(),
        cached_content=cached_content,
        **kwargs,
    )