"""
tutor/cache.py — Gemini context caching for long tutor conversations (P7.x).

Why:
  Every tutor turn re-sends the same static prefix: the (compressed) system
  prompt, any persona instructions, and the rolling conversation summary.
  Gemini context caching bills that prefix at the cached rate ($0.025 / 1M
  for gemini-3.1-flash-lite vs $0.25 / 1M uncached — a 90% discount) as long
  as the cached content is a PREFIX of the prompt and is not re-sent in the
  request contents.

Constraints (Gemini 3 family):
  * Minimum cacheable token count: 4096. The prefix must bundle stable
    lecture context (outline + study-note corpus + transcript) with the system
    prompt to clear that bar, otherwise caching is skipped (no quality change).
  * Creating a cache bills its tokens at the standard input price; storage is
    billed per-token-hour (default TTL 30m, config-overridable). Savings
    accumulate only over longer conversations — exactly the target case.
  * Cached content is a prefix of the request contents. When a cache is
    active, the caller must NOT send the cached tokens again (they would be
    billed at full price and duplicated).

This module is defensive by design (mirrors the ledger posture): it never
raises, returns None instead of a cache name on any failure, and silently
falls back to the uncached path so a caching hiccup can never break a tutor
turn.

Cache identity:
  display_name = f"norai-{lecture_key}-{prefix_hash}". The prefix hash embeds
  the conversation summary, so a new summary (save_memory_node) produces a new
  display name, the old cache is deleted, and a fresh one is created — the
  rolling refresh. A module-level registry maps lecture_key -> cache name/hash
  so hot turns (same hash) make zero API calls.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from google import genai
from google.genai import types

from config import MODEL_NAME, TUTOR_CACHE_TTL_SECONDS, get_api_key

logger = logging.getLogger(__name__)

# ── Tunables (mirrored in config.py for env override) ─────────────────────────
MIN_CACHE_TOKENS = 4096          # Gemini 3 family minimum cacheable prefix
MAX_PREFIX_CHARS = 40_000        # hard cap on the padded prefix (safety)
DEFAULT_TTL_SECONDS = TUTOR_CACHE_TTL_SECONDS

# ── Module state ──────────────────────────────────────────────────────────────
# lecture_key -> {"name": resource name, "hash": prefix content hash,
#                 "created": epoch seconds}
_registry: dict[str, dict] = {}
_registry_lock = threading.Lock()
_client: genai.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> genai.Client:
    """Return a lazily-created, module-shared genai.Client (thread-safe)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = genai.Client(api_key=get_api_key())
        return _client


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token, English heuristic)."""
    return max(0, int(round(len(text or "") / 4)))


def reset_registry() -> None:
    """Clear the in-process cache registry (used by tests)."""
    with _registry_lock:
        _registry.clear()


# ── Prefix assembly ───────────────────────────────────────────────────────────

def _load_lecture_context(lecture_dir: str | Path | None) -> str:
    """Assemble stable, quality-neutral lecture context to pad the prefix past
    the 4096-token minimum.

    Order of preference (all stable per-lecture artifacts, never per-turn):
      1. lecture_outline.json — titles + focus concepts per chapter;
      2. chapter study notes (chapter_*.md) — the grounded note corpus;
      3. the merged transcript (.txt) — raw source, largest but still stable.

    Caching more than the minimum is harmless (the prefix is fixed across the
    rolling window, so it's paid at the cached rate) — but never beyond
    MAX_PREFIX_CHARS so a pathological lecture can't bloat every turn.
    """
    if not lecture_dir:
        return ""
    root = Path(lecture_dir)
    blocks: list[str] = []

    outline_path = root / "notes" / "lecture_outline.json"
    if outline_path.exists():
        try:
            outline = json.loads(outline_path.read_text(encoding="utf-8"))
            title = outline.get("lecture_title", "")
            chapters = outline.get("chapters", [])
            if title:
                blocks.append(f"Lecture title: {title}")
            for ch in chapters:
                line = f"Chapter {ch.get('chapter_id')}: {ch.get('title')}"
                focus = ch.get("focus_concepts") or []
                if focus:
                    line += " — focus: " + ", ".join(str(c) for c in focus)
                blocks.append(line)
        except Exception:  # noqa: BLE001
            logger.debug("cache: failed to load lecture outline", exc_info=True)

    for md in sorted((root / "notes").glob("chapter_*.md")):
        try:
            text = md.read_text(encoding="utf-8").strip()
            if text:
                blocks.append(text)
        except Exception:  # noqa: BLE001
            logger.debug("cache: failed to load chapter notes", exc_info=True)

    for txt in sorted((root / "transcripts").glob("*.txt")):
        try:
            text = txt.read_text(encoding="utf-8").strip()
            if text:
                blocks.append(text)
        except Exception:  # noqa: BLE001
            logger.debug("cache: failed to load transcript", exc_info=True)

    joined = "\n\n".join(blocks)
    if len(joined) > MAX_PREFIX_CHARS:
        joined = joined[:MAX_PREFIX_CHARS]
    return joined


def build_cache_parts(
    system_prompt: str,
    persona_instructions: str = "",
    summary_text: str = "",
    lecture_dir: str | Path | None = None,
) -> tuple[str, str]:
    """Assemble the (system_instruction, contents) parts that go in the cache.

    system_instruction — system prompt + persona + summary. This is what
    LangChain would otherwise merge from the SystemMessages every turn, so it
    lives in the cache's system_instruction slot and is NOT re-sent.

    contents — stable lecture context (outline + study notes + transcript),
    padding the cached prefix past the 4096-token minimum. Cached content must
    be a PREFIX of the prompt; the per-turn dynamic suffix (retrieval context,
    recent window, question) rides on top of it in the request.
    """
    system_parts: list[str] = [system_prompt.strip()]
    if persona_instructions and persona_instructions.strip():
        system_parts.append(persona_instructions.strip())
    if summary_text and summary_text.strip():
        system_parts.append(summary_text.strip())
    system_text = "\n\n".join(system_parts)

    contents_text = _load_lecture_context(lecture_dir)
    return system_text, contents_text


def build_prefix_text(
    system_prompt: str,
    persona_instructions: str = "",
    summary_text: str = "",
    lecture_dir: str | Path | None = None,
) -> str:
    """Full cached prefix text (system + contents) — used for token/hash math.

    Mirrors build_cache_parts but concatenates both parts so callers can
    estimate the total cached token count and hash the whole prefix.
    """
    system_text, contents_text = build_cache_parts(
        system_prompt, persona_instructions, summary_text, lecture_dir
    )
    return "\n\n".join(p for p in (system_text, contents_text) if p)


# ── Cache lifecycle ───────────────────────────────────────────────────────────

def _prefix_hash(prefix_text: str) -> str:
    """Short content hash of the prefix — identifies a specific prefix VERSION.

    The summary lives inside the prefix, so the hash changes whenever
    save_memory_node rolls the conversation summary. A cache built from an old
    summary is stale for the new one — callers detect this via the hash and
    recreate (that's the "rolling" refresh).
    """
    import hashlib

    return hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()[:12]


def _display_name(lecture_key: str, prefix_hash: str) -> str:
    return f"norai-{lecture_key}-{prefix_hash}"


def _find_lecture_caches(lecture_key: str) -> list[types.CachedContent]:
    """All cache resources whose display_name matches this lecture (any prefix
    version), via list() (API paging). Empty on failure."""
    try:
        client = _get_client()
        prefix = f"norai-{lecture_key}-"
        return [
            c for c in client.caches.list() if str(getattr(c, "display_name", "")).startswith(prefix)
        ]
    except Exception:  # noqa: BLE001
        logger.debug("cache: list() failed", exc_info=True)
        return []


def _create_cache(
    display_name: str,
    system_instruction: str,
    contents_text: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> types.CachedContent | None:
    """Create a CachedContent resource.

    The static instructions live in the cache's `system_instruction` slot (so
    LangChain's SystemMessage->system_instruction merge never competes with it
    on the request side), and the stable lecture context in `contents`. The
    caller must then send ONLY the dynamic suffix as request messages.
    """
    try:
        return _get_client().caches.create(
            model=MODEL_NAME,
            config=types.CreateCachedContentConfig(
                display_name=display_name,
                system_instruction=system_instruction,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=contents_text)],
                    )
                ]
                if contents_text
                else None,
                ttl=f"{ttl_seconds}s",
            ),
        )
    except Exception:  # noqa: BLE001
        logger.warning("cache: create failed, falling back to uncached", exc_info=True)
        return None


def delete_lecture_caches(lecture_key: str) -> None:
    """Delete every cache resource for a lecture (eviction / stale-summary path)."""
    for cache in _find_lecture_caches(lecture_key):
        name = getattr(cache, "name", None)
        if not name:
            continue
        try:
            _get_client().caches.delete(name=name)
        except Exception:  # noqa: BLE001
            logger.debug("cache: delete failed", exc_info=True)
    with _registry_lock:
        _registry.pop(lecture_key, None)


def get_or_create_prefix_cache(
    lecture_key: str,
    system_instruction: str,
    contents_text: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str | None:
    """Return a cache resource name for the given prefix, or None to skip.

    Skips caching entirely (returns None) when:
      * no lecture_key is provided (global default graph),
      * the prefix is below the Gemini 3 minimum cacheable size (4096 tokens),
      * the create/list calls fail.

    Rolling refresh: the display name embeds the combined prefix's content
    hash. If the registry already holds the SAME hash (same summary), the
    existing cache is reused with NO API call (hot turns stay fast). If the
    hash differs — the summary changed via save_memory_node — the old cache(s)
    for the lecture are deleted and a fresh one is created, so the cached
    prefix always matches the summary the model will actually be given this
    turn.
    """
    if not lecture_key:
        return None
    prefix_text = "\n\n".join(p for p in (system_instruction, contents_text) if p)
    tokens = estimate_tokens(prefix_text)
    if tokens < MIN_CACHE_TOKENS:
        logger.debug(
            "cache: prefix %d tokens < min %d, skipping",
            tokens,
            MIN_CACHE_TOKENS,
        )
        return None

    ph = _prefix_hash(prefix_text)

    with _registry_lock:
        entry = _registry.get(lecture_key)
        if entry and entry["hash"] == ph and entry["created"] >= time.time() - ttl_seconds:
            return entry["name"]

    # Different hash / expired / restart: (re)create. Delete stale versions
    # first so we never accumulate caches for old summaries.
    delete_lecture_caches(lecture_key)
    created = _create_cache(
        _display_name(lecture_key, ph), system_instruction, contents_text, ttl_seconds
    )
    name = getattr(created, "name", None) if created else None
    if name:
        with _registry_lock:
            _registry[lecture_key] = {"name": name, "hash": ph, "created": time.time()}
        return name
    return None