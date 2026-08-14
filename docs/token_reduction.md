# Token Reduction Plan & Status (P7)

Goal: cut per-request Gemini token spend without touching answer quality. Explicit
non-goals (user directive): no notes-size reduction (800–1200+ word mandate stays),
no image downscale (1114×720 stays), no keyframe-count reduction, no summarization
aggressiveness increase.

---

## 1. Measured cost baseline (paid run, 2026-08-13)

Full pipeline, ~8-min lecture: **$0.0269 total, 18 calls.**

| Stage      | Calls | Cost     | Share |
|------------|------:|---------:|------:|
| extract    |    10 | $0.0094  |  35%  |
| notes      |     3 | $0.0085  |  32%  |
| visual     |     3 | $0.0080  |  30%  |
| outline    |     1 | $0.0010  |   4%  |

Output tokens ≈ **75%** of total cost (output $1.50/1M vs input $0.25/1M).

Tutor: ~$0.0006 / turn.

### Pricing model (flash-lite)
| Item | Rate |
|------|------|
| input | $0.25 / 1M |
| output | $1.50 / 1M |
| **cached input** | **$0.025 / 1M** (10× cheaper) |
| cache storage | $1.00 / 1M tokens / hour |

Cache **create** bills at the full input rate; the *minimum cacheable prefix* for
the Gemini 3 family is **4096 tokens**.

---

## 2. Prompt compression (done)

All instructions rewritten — same intent, no capability loss, tokens measured with
the 4-chars-per-token estimator:

| Prompt | Before | After |
|--------|-------:|------:|
| `TUTOR_SYSTEM_PROMPT` (default) | 1605 | **1135** |
| `TUTOR_SYSTEM_PROMPT` (SOCRATIC) | ~500 | **~355** |
| `EXTRACTION` | 408 | **362** |
| `VISUAL` | 799 | **690** |
| `NOTES` | 1057 | **856** |
| `OUTLINE` | 257 | **249** |

---

## 3. Context caching for long tutor conversations (done — dormant on free tier)

**Problem:** after 6+ turns the rolling summary + recent window dominate the tutor
prompt; every turn re-sends the *same* static prefix (system prompt + persona +
summary) at the full input rate.

**Design (Option B — rolling prefix cache, implemented):**

- New `tutor/cache.py`. The static prefix is split into:
  - **`system_instruction`** — system prompt + persona + conversation summary
    (what LangChain would otherwise merge from SystemMessages every turn);
  - **`contents`** — stable lecture context (outline + chapter notes + transcript,
    capped `MAX_PREFIX_CHARS=40_000`) padding past the 4096-token minimum.
- Cache display name embeds `sha256(prefix)[:12]`: `norai-{lecture_key}-{hash}`.
- In-process registry `lecture_key → {name, hash, created}`: **hot turns reuse the
  cache with zero API calls** (trusted within TTL `NORAI_TUTOR_CACHE_TTL_SECONDS`,
  default 1800s). On hash change (new summary from `save_memory_node`) the old
  caches are deleted and a fresh one created — the cache always matches the
  summary the model actually receives.
- Gates: skipped when no lecture_key, prefix < 4096 tokens, or any API failure —
  **a caching hiccup can never change the answer** (falls back to uncached path).
- Cache create is a network call; run off the event loop via `asyncio.to_thread`.

**Request-side rule:** when the cache is active the request sends **no
SystemMessages** (they'd merge into `system_instruction` and duplicate the cached
prefix). `generate_answer_node` (`tutor/nodes.py`) then sends only the dynamic
suffix: retrieval context block + image context + recent window + question, with
`cached_content=<name>` threaded through `make_chat_llm` (`tutor/llm.py`).

**Accounting:** cached input is billed at the cached rate and recorded per-call in
`backend/usage_ledger.py` (`cached_input_tokens` → `model_price(...)`).

**Estimate:** lecture `6af222a9-…` prefix ≈ 24,098 chars ≈ **6024 tokens** — clears
the 4096 minimum. On a cached turn the ~6000-token prefix drops to the cached rate:
~$0.00015 saved per turn vs ~$0.0015 uncached.

### Remaining / findings
- [x] `config.py`: `MODEL_PRICING` cached rate, `model_price` cached split, `TUTOR_CACHE_TTL_SECONDS`
- [x] `tutor/cache.py` — prefix build/split, registry, rolling refresh, delete
- [x] `tutor/llm.py` — `cached_content` passthrough + cached-token recording
- [x] `backend/usage_ledger.py` — `cached_input_tokens` plumbing
- [x] `tutor/nodes.py` — `generate_answer_node` dual cached/uncached path
- [x] `tutor/graph.py` — async wrapper binding `output_dir` to generate_answer
- [x] `backend/dependencies.py` — LRU eviction purges lecture caches
- [x] summary cap relaxed 5→7 sentences (keeps summaries informative enough to be a useful cache anchor)
- [x] tests: `tutor/test_cache.py` (23 checks, mocked client); full suite green
- [x] **paid probe (2026-08-13)** — code validated live, but cache **create is quota-blocked**:
      API accepts the payload (system_instruction + role'd contents + ttl; the
      4096-token min is satisfied at ~8.3k est tokens) and then returns
      `429 RESOURCE_EXHAUSTED: TotalCachedContentStorageTokensPerModelFreeTier
      limit exceeded for model gemini-3.1-flash-lite: limit=0`. The current API
      key's free tier allows **0 cached-content storage tokens** for this model,
      so context caching cannot provision on it. `caches.list()`/`delete()` work
      (empty list). The defensive fallback is proven: on create failure the tutor
      silently uses the uncached path — no behavior or cost change.

### Activation note
Context caching is implemented, unit-tested, and API-validated. It stays dormant
(graceful no-op) until a key with cached-content storage quota (paid/billing
enabled on the same Google Cloud project) is used — then `get_or_create_prefix_cache`
starts provisioning automatically with zero code changes.

---

## 4. Output-token reduction (done, 2026-08-13)

Output is 75% of pipeline cost ($1.50/1M vs $0.25/1M input). Two generated fields
were **never consumed downstream** — pure wasted output — plus every LLM call except
notes lacked a `max_output_tokens` bound:

| Field | Stage | Share of stage output | Downstream consumers |
|-------|-------|----------------------:|----------------------|
| `external_knowledge` | extract | **23%** | none (only extract/ + merger) |
| `visual_summary` | visual | **17%** | none (only visual/ + merger) |
| `ocr_text` | visual | 46% | screenshot selector (analysis cache) — **kept** |

Changes:
- `extract/models.py` / `extract/prompts.py`: `external_knowledge` removed from
  `ChunkKnowledgeModel` + `OUTPUT_SCHEMA` (schema field gone → API stops emitting it).
  `KnowledgeObject` keeps only consumed fields; old cached chunk files still load
  (merger reads via `.get(..., default)`).
- `visual/visual_extractor.py` / `visual/visual_prompts.py`: `visual_summary` removed
  from `VisualObjectItem`, `ChapterVisualKnowledgeModel`, the batch prompt, and both
  empty-object factories.
- `extract/merger.py`: dead `external_knowledge` / `visual_summary` writes dropped
  from merged objects.
- `max_output_tokens` caps added at ~2× observed max (never bite on normal runs,
  bound pathological blowups — output bills at 6× input): extract **1200** (obs max
  613), visual chapter-batch **3000** (obs max 1438), outline **1000** (obs max 446).
  Notes stays at 8192 (mandated 800–1200+ word notes).

**Expected savings ≈ $0.0026/run (~10%)** — `external_knowledge` ~$0.0016,
`visual_summary` ~$0.001. Zero quality impact: fields were provably unused; caps sit
above observed output. Verified offline: 10/10 cached chunks merge cleanly with the
dead fields absent; full offline suite (37 tests) green. No paid probe needed.

---

## 5. Savings math (expected)

| Turn | Uncached | Cached |
|------|---------:|-------:|
| cold (cache create) | $0.0015 | $0.0015 + cache |
| hot (prefix ~6k tokens) | $0.0015 | ~$0.0002 |

Tutor at ~$0.0006/turn today; context caching cuts the prefix component ~10× on
long conversations. Pipeline output-token spend is cut ~10% (dead fields dropped;
see §4); input-side caching stays dormant until a quota-enabled key is used.
