# Phase 2 report: before / after (2026-10-29)

Phase 2 ("trust + cost") replaced the 18-stage legacy pipeline with a 5-stage lean one, grounded the tutor on the transcript instead of the notes, and cut the local compute per lecture. This report compares the legacy pipeline that `master` runs with what `phase2` runs now. The detailed log is the Phase 2 entry in `docs/PROJECT_PROGRESS.md`.

## In one table

| | Before (legacy) | After (lean) |
|---|---|---|
| Pipeline | 18 stages, ~20–90 LLM calls | transcription ∥ keyframes → structure (1 call) → chapters (1 call each) → index |
| 17-min lecture, full run | 29 calls, $0.061, 242 s | 9 calls, **$0.0335 (−45 %)**, **142 s (−41 %)** |
| 8.7-min lecture (dp8) | 21–22 LLM calls, 169–251 s | 4 LLM calls + 3 embed batches, $0.0208, 114–116 s |
| 71-min lecture (aws71) | 87 LLM calls, 1,054 s | ~15 calls (estimator; no full run made) |
| Unsupported claims in notes (3.8-flash judge) | 2.5–19 % | 0–2.8 % |
| Transcript timestamps vs YouTube captions | drifted to −73 s by 16 min | median 0.4 s, p90 0.9 s |
| Tutor: detail-question accuracy | 0 / .56 / 1.0 | 1.0 / 1.0 / 1.0 |
| Tutor: citations that verify | .58–.66 | .98–1.0 |
| Tutor index on disk | 6.3–6.8 MB (Chroma) | 96–464 KB (NumPy) |
| Frame stage, 71-min 720p, 1 core | 88 s | 15 s |

Call counts come from the usage ledger (CLI runs, embeddings included) or the orchestrator's metrics file (UI/job runs, LLM calls only); each row says which. All costs are `gemini-3.1-flash-lite` + `gemini-embedding-2` list prices.

## Cost and speed

- **Where the legacy money went** (17-min calculus lecture, 29 calls, $0.061):
  - Transcription was 1 call but $0.023: Gemini wrote 11.3k JSON output tokens for ~3.9k tokens of speech.
  - Then came 11 extraction calls, 1 outline, 4 visual analysis, 4 screenshot selection (re-uploading frames), 4 notes and 4 embedding batches.
- **What lean does instead:**
  - **Compact transcription:** one `[MM:SS] text` line per sentence. That is 4,470 output tokens (−60 %) and $0.0131. It kept 2,948 of 2,949 words.
  - **Structure:** one call over the chunk-tagged transcript gives the title and chapter ranges.
  - **Chapters:** one multimodal call per chapter (transcript + ≤ 12 keyframes at low media resolution) writes notes, revision, quiz and screenshot picks together. Chapter calls run 3 at a time, so wall time scales with rounds, not chapters.
- **Per-lecture Gemini calls by length** (estimator): 4 / 6 / 11 / 15 / 18 for 9 / 17 / 30 / 60 / 120 min.

## Quality

Judged by `gemini-3.8-flash`. The 3.5-flash-lite judge proved too lenient and erratic, so only its tutor A/B is kept in the progress doc.

**Notes fidelity** (legacy → lean):

| Lecture | Notes words | Unsupported claims (rate) | Missing key points |
|---|---|---|---|
| dp8 (8.7 min) | 1,435 → 828 | 10 (.175) → 1 (.028) | 10 → 3 |
| calc17 (17 min) | 1,495 → 1,770 | 13 (.186) → 0 | 19 → 7 |
| aws71 (71 min) | 3,577 → 5,956 | 4 (.025) → 1 (.004) | 30 → 29 |

- Legacy's unsupported claims were textbook padding the lecturer never said: "calculus is the study of change", Riemann sums, invented DP steps, an O(n²) the transcript never mentions. They came from the extraction stage's `inferred_knowledge`.
- Lean's 2 flags are borderline: dp8's example array is on the slide (the judge only sees the transcript), and aws71's "4,500-employee firm" paraphrases "a 4,500 financial services company".

**Tutor** (66 transcript-grounded questions; baseline = Chroma, notes-only tutor; lean = transcript-grounded tutor on lean notes):

| Set (baseline → lean) | Detail accuracy | False "not covered" | Out-of-scope abstain | Unsupported claims | Citations verified |
|---|---|---|---|---|---|
| dp8 | 0 → 1.0 | .375 → .06 | 0 → .75 | .78 → .09 | .62 → 1.0 |
| calc17 | .56 → 1.0 | .07 → 0 | .25 → 1.0 | .20 → 0 | .66 → .98 |
| aws71 | 1.0 → 1.0 | 0 → 0 | 1.0 → 1.0 | .04 → 0 | .58 → 1.0 |

- Core accuracy and false-premise correction are 1.0 on every set.
- Latency per turn went from 5.5–7.1 s to 3.9–4.3 s (p50), and calls per turn from 3 to 2.
- Cost per turn is **≈ $0.0008**. The eval files say $0.00056; they were recorded before the streamed-output metering fix (`6d18dd9`), which adds ≈ $0.0002 per turn.

## Server load

Measured on 1 core, modelling the planned Hostinger KVM 1 box (1 vCPU / 4 GB / 50 GB):

| | Before | After |
|---|---|---|
| Local CPU per lecture-minute, 720p | ≈ 1.6 CPU-s | ≈ 0.28 CPU-s (frames + scenes) |
| Frame stage: calc17 / aws71 / dp8 | 14.8 / 88.0 / 1.6 s | 3.8 / 14.9 / 0.7 s |
| Keyframes kept: calc17 / aws71 / dp8 | 19 / 265 / 35 | 23 / 418 / 56 |
| Kept keyframe disk: aws71 | 33 MB | 22.5 MB |
| 1-vCPU load at peak hour, 10k users | 193 % | 54 % |

- The new decoder keeps every keyframe ≥ 1 s apart. Encoders place keyframes at scene cuts, so short slides (~4 s on screen) are caught that the old 8 s grid only hit by luck. Videos with sparse keyframes fall back to the old 8 s seeks.
- Backend RSS is ~200 MB in production (`import backend.main`); RAM is not the limit.
- **Sizing:** 100 users fit as-is on one free-tier key. At ~1k users, Gemini needs a paid tier (a peak day is 4.6× one key's daily quota), `NORAI_MAX_CONCURRENT_PIPELINES` should go to 2–3, and keyframes fill the 50 GB disk in ~3 months.

## Code and reliability

- **Deleted:** the legacy chain (`extract/`, visual analysis and mapping, outline / chapter-build / screenshot selection, the `NORAI_PIPELINE` switch, JSON transcription), about 6,500 lines in `f321768`. Readers for lectures it produced stay, so the demos and existing users' lectures keep working.
- **Dependencies removed:** `chromadb`, `pillow`, `imagehash`.
- **Fixed along the way:**
  - Orphaned jobs after a restart recover in ~90 s instead of 15 min (`8e4ecdd`).
  - Gemini 429s honour the server's retry-after hint (`c9c63fe`).
  - One invalid quiz question no longer fails a whole chapter; bad questions are dropped one by one.
  - Notes writing no longer mutates module globals, which was unsafe with concurrent pipelines.
  - Repeated slides are deduplicated, note citations seek to their section start, and streamed tutor output is metered correctly (`6d18dd9`).

## Verification

- **Offline:** `scripts/run-tests.sh` 41/41 + pyflakes, `backend/test_estimate.py` 44/44, vitest 86/86, oxlint 0, `tsc -b` clean.
- **Paid runs:**
  - 2026-10-28: the 17-min lecture via the CLI (9 calls, $0.0335), and the 8.7-min lecture through the UI and job queue (estimate matched the run: 4 calls, 2 chapters).
  - 2026-10-29, after the legacy deletion: the 8.7-min lecture via the CLI, from the YouTube URL (7 calls, $0.0208, 2 chapters, 0 degraded, 37 index docs).

## Not verified / still open

- **No full lean run on a long lecture.** aws71 (71 min) only went through `--reuse` (structure + chapters on the legacy transcript). Its 15-call figure is the estimator's.
- **Existing lectures aren't backfilled.** They keep their legacy notes and screenshot selections until re-run; their tutor index is built lazily on the first question.
- **Decisions before ~1k users:** a paid Gemini tier, `NORAI_MAX_CONCURRENT_PIPELINES` 2–3, and keyframe pruning or object storage.

## Merging into `master`

- `master` (`d27370b`, 2026-08-16) is an ancestor of `phase2`, so the merge is a fast-forward of **52 commits**.
- Those commits are not only Phase 2. They also bring the August audit fixes and all of Phase 1 (Razorpay passes, landing page, auth/chat fixes) from `fix/threads-and-pdf`. Phase 1's own gaps still apply: Supabase emails and a real Razorpay payment/webhook are unverified.
- Little of this is pushed. `origin/fix/threads-and-pdf` stops at `16a39ed` (the demo-thread isolation fix), so the 32 commits after it (all of Phase 1 and Phase 2) exist only locally.
