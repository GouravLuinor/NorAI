"""
backend/usage_ledger.py — P6.5 per-call Gemini usage accounting.

Every paid Gemini call (pipeline `generate_content` sites, tutor chat LLM,
embedding batches) records its token usage + estimated USD cost through this
module. Records are both appended to `outputs/llm_calls.jsonl` (one line per
call, debug log) and accumulated into a process-global, thread-safe per-stage
ledger.

Consumers:
  * the pipeline snapshots the ledger before a run and diffs after
    (`snapshot_usage` / `diff_usage`) so `backend.usage.record_pipeline_outcome`
    can write one UsageLog row per stage with real tokens + cost;
  * `/chat` + `/chat/stream` snapshot the `tutor` stage before a turn and diff
    after so `record_tutor_turn` can meter the turn's cost.

Defensive by design (mirrors the old `tutor.llm.log_llm_call` posture):
  * thread-safe — pipeline worker threads and the async tutor run on the same
    process;
  * never raises — a metering failure must never break a pipeline run or a
    tutor turn;
  * unknown models / missing usage metadata cost $0 (no fabricated money).
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import model_price

logger = logging.getLogger(__name__)

LLM_CALLS_FILE = Path("outputs/llm_calls.jsonl")

_write_lock = threading.Lock()
_stage_lock = threading.Lock()

# stage -> {"calls": int, "input_tokens": int, "output_tokens": int, "cost_usd": float, "model": str}
_STAGE_LEDGER: dict[str, dict[str, int | float | str]] = {}


def _append_jsonl(
    node: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cost_usd: float,
    cached_input_tokens: int | None = None,
    **extra: Any,
) -> None:
    try:
        from backend.logging_config import get_context

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_input_tokens": cached_input_tokens,
            "cost_usd": cost_usd,
        }
        record.update(extra)
        record.update(get_context())
        LLM_CALLS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _write_lock, LLM_CALLS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        logger.debug("llm usage logging failed", exc_info=True)


def _cost(
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cached_input_tokens: int | None = None,
) -> float:
    return model_price(
        model,
        input_tokens=prompt_tokens or 0,
        output_tokens=completion_tokens or 0,
        cached_input_tokens=cached_input_tokens or 0,
    )


def log_llm_call(
    node: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cached_input_tokens: int | None = None,
    **extra: Any,
) -> None:
    """Append one LLM-usage record to outputs/llm_calls.jsonl (thread-safe)."""
    _append_jsonl(
        node,
        model,
        prompt_tokens,
        completion_tokens,
        _cost(model, prompt_tokens, completion_tokens, cached_input_tokens),
        cached_input_tokens=cached_input_tokens,
        **extra,
    )


def record_llm_usage(
    stage: str,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    *,
    node_override: str | None = None,
    cached_input_tokens: int | None = None,
) -> None:
    """Log one call to JSONL AND accumulate it into the per-stage ledger."""
    cost = _cost(model, prompt_tokens, completion_tokens, cached_input_tokens)
    _append_jsonl(
        node_override or stage,
        model,
        prompt_tokens,
        completion_tokens,
        cost,
        cached_input_tokens=cached_input_tokens,
    )
    with _stage_lock:
        row = _STAGE_LEDGER.setdefault(
            stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "model": ""}
        )
        row["calls"] = int(row["calls"]) + 1
        row["input_tokens"] = int(row["input_tokens"]) + int(prompt_tokens or 0)
        row["output_tokens"] = int(row["output_tokens"]) + int(completion_tokens or 0)
        row["cost_usd"] = round(float(row["cost_usd"]) + cost, 6)
        row["model"] = model


def record_embed_usage(stage: str, model: str, billable_chars: int | None) -> None:
    """Estimate embedding token usage from billable characters.

    gemini-embedding-2 exposes `metadata.billable_character_count` only when the
    API returns it (the google-genai SDK leaves it None in practice). When it is
    unavailable, the caller passes the char count of the text actually sent.
    Tokens are estimated at ~4 chars/token (English heuristic) and the cost is
    labeled "estimated" in the UI.
    """
    tokens = max(0, int(round((billable_chars or 0) / 4)))
    record_llm_usage(stage, model, prompt_tokens=tokens, completion_tokens=0)


def _usage_from_response(response: Any) -> dict[str, Any]:
    """Normalize a raw Gemini GenerateContentResponse usage_metadata to a dict."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    # pydantic model from google-genai: pull the documented fields.
    out: dict[str, Any] = {}
    for key in (
        "prompt_token_count",
        "candidates_token_count",
        "thoughts_token_count",
        "total_token_count",
    ):
        value = getattr(meta, key, None)
        if value is not None:
            out[key] = value
    return out


def record_generate_usage(stage: str, model: str, response: Any) -> None:
    """Log one raw Gemini generate_content call to JSONL + the per-stage ledger.

    Reads `response.usage_metadata` (Gemini key names) directly; missing usage
    metadata is tolerated (the call is still counted, at $0 cost).
    """
    usage = _usage_from_response(response)
    record_llm_usage(
        stage,
        model,
        prompt_tokens=usage.get("prompt_token_count"),
        completion_tokens=usage.get("candidates_token_count"),
    )


def snapshot_usage() -> dict[str, dict[str, int | float | str]]:
    """Deep-copy of the current per-stage ledger (for pre-run snapshots)."""
    with _stage_lock:
        return {stage: dict(row) for stage, row in _STAGE_LEDGER.items()}


def reset_usage() -> None:
    """Clear the ledger (used by tests)."""
    with _stage_lock:
        _STAGE_LEDGER.clear()


def diff_usage(before: dict[str, dict[str, int | float | str]]) -> list[dict[str, Any]]:
    """Per-stage deltas between a pre-run snapshot and now (calls > 0 only)."""
    now = snapshot_usage()
    out: list[dict[str, Any]] = []
    for stage in set(before) | set(now):
        b = before.get(stage, {})
        n = now.get(stage, {})
        calls = int(n.get("calls", 0)) - int(b.get("calls", 0))
        if calls <= 0:
            continue
        out.append(
            {
                "stage": stage,
                "calls": calls,
                "input_tokens": int(n.get("input_tokens", 0)) - int(b.get("input_tokens", 0)),
                "output_tokens": int(n.get("output_tokens", 0)) - int(b.get("output_tokens", 0)),
                "cost_usd": round(
                    float(n.get("cost_usd", 0)) - float(b.get("cost_usd", 0)), 6
                ),
                "model": n.get("model") or b.get("model"),
            }
        )
    return out