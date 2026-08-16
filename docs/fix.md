# Chief Reviewer — Fix Log

Review of Antigravity's "content-adaptive dynamic scaling + screenshot selection + ingestion hardening" work (commits `5b31878`, `9ee9baa`, `f456020`, `a423c36`, `4601f46`, `13f5d07`, on branch `fix/threads-and-pdf`).

> Status: **ALL ITEMS FIXED** (2026-08-15). Verification: `scripts/run-tests.sh` → 38/38 PASS; `cd frontend && npm run test` → 73/73 PASS; oxlint clean; `npm run build` clean.

**Verdict: not shippable as-is.** Tests are green (38/38 backend, 73/73 frontend Vitest, oxlint, `tsc`/vite build) but the suites don't cover the two critical defects.

- **2 CRITICAL** — must fix before merge
- **5 HIGH** — should fix before merge
- **6 MEDIUM** — fix soon
- **9 LOW** — opportunistic / cleanup

---

## CRITICAL

### C1. Outline payload truncates `lecture_notes` to 5 characters — ✅ FIXED
- **Where:** `notes/outline_generator.py:303`
- **What:** `obj.get("lecture_notes", [])[:5]` — `lecture_notes` is a `str` (see `extract/models.py:10`), so `[:5]` slices to the first **5 characters**, not 5 entries. Verified empirically: a 951-char note produced a payload summary of `"The l"`. The outline LLM never sees the chunk content. `concepts[:10]` (`:302`) also still truncates the concept graph.
- **Impact:** Chapter titles/clustering quality silently degrades; the "zero-loss outline payload" claim in `COMMUNICATOR.md` is false.
- **Fix:** Pass the full string: `obj.get("lecture_notes", "")`. Drop the `[:10]` concept cap (or state the truncation explicitly). Remove the "zero-loss" wording from docs.
- **Applied:** both the `[:5]` string slice and the `concepts[:10]` cap removed — the proto-payload now carries the full `lecture_notes` string and full `concepts` list.

### C2. Webcam/talking-head frames can re-enter notes — ✅ FIXED
- **Where:** `visual/visual_extractor.py:731-741` (esp. `:735`)
- **What:** When the LLM returns `source_screenshots=[]` but `include_in_notes=True` (default) and `visual_type` is not in the decorative set, `informative_basenames` is empty, so `is_frame_slide` collapses to `is_chunk_informative` — blanket-assigning `vo.importance_score` / `vo.ocr_text` / `visual_type="slide"` to **every** frame in the chunk, including webcam frames.
- **Impact:** Reintroduces the exact bug `a423c36` was meant to fix; junk frames pass the selector's quality bar and reach the notes.
- **Fix:** When `informative_basenames` is empty, do not fall back to `is_chunk_informative`. Mark all chunk frames `importance_score=1` / `visual_type="talking_head"` / `include_in_notes=False`, or drop the chunk from analysis so Pass 1 re-scores it.
- **Applied (chosen option "Mark chunk frames decorative"):** the `is_chunk_informative` fallback is removed — an empty `informative_basenames` now scores every chunk frame as decorative (`importance=1`, `talking_head`, `include_in_notes=False`).

---

## HIGH

### H1. Non-monotonic importance normalization — ✅ FIXED
- **Where:** `notes/screenshot_selector.py:499-502`
- **What:** `imp = raw_imp * 2 if (0 < raw_imp <= 5) else raw_imp` — raw 5 → 10 while raw 6 → 6, so a mid-scored slide outranks a 6-9 slide in `content_density` (drives dedup survival and the quality bar). The `*2` stretch also assumes the extractor emits 1-5, but the extractor prompts explicitly instruct **1-10** (`visual/visual_prompts.py:41`, `visual/visual_extractor.py:676`); the selector's own Pass-2 prompt is 0-10 (`screenshot_selector.py:266`).
- **Fix:** Remove the `*2` normalization entirely (scores are already 1-10). If a stretch is still wanted, use a monotonic affine map (e.g. `imp = 1 + int(round(raw_imp * 0.9))`) — never against an already-1-10 scale.
- **Applied:** `imp = raw_imp` (raw score used as-is; comment updated).

### H2. Three divergent chapter-count formulas — ✅ FIXED
- **Where:** `notes/outline_generator.py:313`, `notes/outline_prompts.py:12`, `backend/estimator.py:186` (docstring `:28` matches none)
- **What:**
  - Generator caps at **8**: `target_chapters = max(3, min(8, max(3, total_chunks // 3)))`
  - Prompt asks for **8-14** chapters at 46+ chunks.
  - Estimator predicts up to **16**: `min(16, max(3, round(duration_min/8) if duration_min>=20 else ceil(chunks/2.5)))`
  - E.g. a 35-min / 26-45-chunk lecture: generator target = 8, prompt allows 9, estimator predicts round(35/8) = 4.
- **Fix:** Make the estimator formula and the prompt tiers consistent with the generator's cap (or lift the cap); fix the stale docstring at `estimator.py:28`.
- **Applied (chosen option "Honor LLM ranges, align to prompt"):** generator now uses the same tiered cap as the prompt (`≤12 chunks → 4`, `13-25 → 6`, `26-45 → 9`, `46+ → 14`); estimator mirrors it; stale docstring corrected.

### H3. LLM chapter clustering is discarded — ✅ FIXED
- **Where:** `notes/outline_generator.py:324-335`
- **What:** The LLM is explicitly asked for `start_chunk` / `end_chunk` / `chunk_ids` (`outline_prompts.py:16`), but the returned values are **thrown away** and chunk membership is reassigned as an even split: `per_chapter = max(1, total_chunks // num_chapters)`.
- **Impact:** "Clustering into meaningful transitions" is cosmetic; chunk→chapter membership is a flat partition.
- **Fix:** Honor the LLM's ranges (clamp/validate them) and only fall back to even split on missing/invalid values.
- **Applied:** new `_valid_chapter_ranges()` helper validates the LLM's ranges (complete, contiguous, non-overlapping partition of all chunks); valid ranges are used, otherwise even split. Edge case `num_chapters > total_chunks` clamped (also closes L7). Unit-checked against 7 cases.

### H4. Orchestrator passes the pre-merge objects dir to the outline generator — ✅ FIXED
- **Where:** `backend/orchestrator.py:263` (`generate_lecture_outline(objects_dir, out)`)
- **What:** The parameter is named `merged_objects_dir` (`notes/outline_generator.py:265`) and the standalone `main()` (`:350`) genuinely uses `outputs/merged_objects`, but the pipeline passes the **pre-merge** `objects/` dir (extracted, text-only) — and the call also happens before `merge_all_chunks` (`orchestrator.py:312`). The outline never sees `visual_notes` that merged objects carry.
- **Fix:** Rename the param to `objects_dir` + update docstring/`main()`, or call it after `merge_all_chunks` with the merged dir. Decide intent for H3 while here.
- **Applied (chosen option "Rename param (pre-merge OK)"):** param renamed to `objects_dir`, docstring + `main()` updated. No stage-order change.

### H5. `stripSources` truncates prose containing the word "sources" — ✅ FIXED
- **Where:** `frontend/src/lib/references.ts:189-190`
- **What:** The regex `/(\*\*Sources\*\*|\n\nSources\b|Sources\s*[:•]|Sources\b[\s\S]*$)[\s\S]*$/i` leftmost-matches a bare `\bSources\b` anywhere. Verified: `"The sources of variance are many."` → `"The"`. Applied on every stream chunk and to the committed `cleanAnswer` (`ChatArea.tsx:90,99`).
- **Impact:** Displayed/stored-frontend answers are silently cut; mismatch with the full backend-persisted answer can defeat the RC-FIX2 dedup guard at `ChatArea.tsx:120`.
- **Fix:** Require an appendix-shaped header — e.g. `/(?:\*\*Sources\*\*|\n[ \t]*Sources\s*[:•]|\n[ \t]*Sources\s*\n)[\s\S]*$/i` — and stop at the **last** such header, or only strip when `Sources` is near the end.
- **Applied:** regex now only matches appendix-shaped headers (`**Sources**` / newline `Sources:` / newline `Sources` line); cuts at the first appendix-shaped header (drops all appendix content). Verified 7/7 cases including the prose false-positive.

---

## MEDIUM

### M1. Risky VisualObjectItem defaults — ✅ FIXED
- **Where:** `visual/visual_extractor.py:586-593`
- **What:** `importance_score` defaults to `5` and `include_in_notes` to `True`. Omitted LLM fields silently become mid-importance + include=True, which H1's `*2` normalization then inflates to 10. The batch path (`model_dump()`) never runs the `validate_visual_object` guard (only the dead legacy path does).
- **Fix:** Default to `0` / `False`, or make the fields required so an unrated chunk can't silently become "essential".
- **Applied:** defaults now `importance_score=0` / `include_in_notes=False`; selector read-default updated to match (`screenshot_selector.py:504`).

### M2. `score_frames_batch` discards synthesized scores — ✅ FIXED
- **Where:** `notes/screenshot_selector.py:540-551`
- **What:** When `uploaded` is empty for the unanalyzed subset, the function returns `[]`, discarding already-synthesized `FrameQualityScore`s from visual analysis — a regression vs. the `return synthesized` on the retry-exhausted path (`:744`).
- **Fix:** `return synthesized` instead of `return []`.
- **Applied.**

### M3. Citation clicks do nothing on mobile — ✅ FIXED
- **Where:** `frontend/src/lib/cite.ts:12` + `ChatArea.tsx:177` + `Workspace.tsx:251`
- **What:** `findSectionCard` scopes to `document.querySelector('.doc-content')` (first match in DOM order). On mobile only one panel is mounted; when chat is open, the only `.doc-content` is ChatArea's message scroller (no `[id^="sec-"]` cards) → poll exhausts, `console.warn`, no feedback, chat never switches to the doc tab.
- **Fix:** Scope to the doc pane (`main .doc-content` / `DocPanel`) or skip the container when it's the chat scroller; on mobile, switch `mobileTab` to `'doc'`.
- **Applied:** `findSectionCard` now scans ALL `.doc-content` containers; `scrollToHeading` dispatches a `norai:show-doc` CustomEvent; `Workspace.tsx` listens and switches `mobileTab` to `'doc'` + closes the tablet AI drawer.

### M4. Citation poll cap too tight for async notes fetch — ✅ FIXED
- **Where:** `frontend/src/lib/cite.ts:76`
- **What:** 35 × 100 ms = 3.5 s cap. Chapter switch remounts `NotesView` (keyed) which then does a network `GET /notes/{id}` (`NotesView.tsx:226`); if the round-trip exceeds ~3.5 s the scroll silently fails.
- **Fix:** Raise `maxAttempts` (e.g. 100 → 10 s) and/or restart the poll once on the notes container's load transition.
- **Applied:** `maxAttempts` 35 → 100 (10 s poll).

### M5. Stale `completedStages` on retry re-run — ✅ FIXED
- **Where:** `frontend/src/pages/ProcessingPage.tsx:82-88`
- **What:** `completedStages` is append-only and never cleared. When the backend re-queues (stage `retrying`, `backend/jobs.py:316-322`) and the re-run restarts at `ingestion`, every stage up to the previous failure stays checkmarked ahead of the active stage and the bar drops backward.
- **Fix:** Track `maxSeenIdx` and reset the set (or drop entries with `idx > current idx`) whenever a re-run reports an earlier stage.
- **Applied:** if the incoming stage is at/below an already-completed stage, the set is cleared before re-adding up to the active stage.

### M6. `chapterFromChunkId` returns 0 for `ch0__` — ✅ FIXED
- **Where:** `frontend/src/lib/references.ts:47-48`
- **What:** No `> 0` guard → `chapterId: 0`, `section: "Ch 0"`, `chapterStart(0)` in ReferencesPanel.
- **Fix:** `const n = Number(m[1]); return n > 0 ? n : undefined`.
- **Applied.**

---

## LOW

### L1. `blur_level` ignored by the quality bar — ✅ FIXED
- **Where:** `notes/screenshot_selector.py:201-204` vs `823-835`
- **Applied:** added `MAX_BLUR_LEVEL = 6`; `passes_quality_bar` now rejects `blur_level > 6`.

### L2. `non_decorative` fallback ignores `instructor_occlusion` — ✅ FIXED
- **Where:** `notes/screenshot_selector.py:1010-1015`
- **Applied:** fallback now also requires `instructor_occlusion <= MAX_INSTRUCTOR_OCCLUSION` and `blur_level <= MAX_BLUR_LEVEL`.

### L3. Missing Pass-1 scores silently dropped — ✅ FIXED
- **Where:** `notes/screenshot_selector.py:680-708`
- **Applied:** missing Pass-1 scores now raise `ValueError` inside the retry loop so the batch is retried instead of returning partial scores.

### L4. Shared-frame path collision — ✅ FIXED
- **Where:** `visual/visual_extractor.py:736`
- **Applied:** `frames[norm_p]` entries are no longer overwritten — a frame already recorded is skipped.

### L5. `source_screenshots` fallback inconsistency — ✅ FIXED
- **Where:** `visual/visual_extractor.py:719` vs `731-735`
- **Applied:** resolved screenshots computed once per chunk (`resolved_by_chunk`) and used by both the saved object and the persisted frame analysis.

### L6. Negative `sec_per_call` in estimator — ✅ FIXED
- **Where:** `backend/estimator.py:110-118`
- **Applied:** `sec_per_call` clamped with `max(0.0, ...)`.

### L7. `num_chapters > total_chunks` edge case — ✅ FIXED
- **Where:** `notes/outline_generator.py:327-335`
- **Applied:** chapters clamped to `total_chunks` before range assignment (part of H3 rework).

### L8. Frontend citation nits — ✅ FIXED
- `frontend/src/lib/cite.ts:66` — title recovery against the leaf section name (weak last resort, left as-is — primary path resolves via chunk/store).
- `frontend/src/lib/cite.ts:77-94` — poll `setInterval` now cleared on a new citation click (module-scoped `activeInterval`).
- `frontend/src/lib/cite.ts:23` — exact slug equality checked before `includes` to avoid wrong-card matches.
- `frontend/src/components/chat/ReferencesPanel.tsx:57` — key now `` `${ref.type}-${ref.id}-${index}` `` (no collisions).

### L9. Redundant nesting / stale comment — ✅ FIXED
- `notes/outline_generator.py:313` — replaced by the tiered cap in H2.
- `backend/estimator.py:28` — docstring corrected in H2.

---

## Verified OK

- Notes depth scaling IS applied: `notes_generator.py:839` (4-8 sections, 1,000-2,200+ words) and `notes_prompt.py:45-47` (400-700 / 800-1,400 / 1,500-2,500 tiers). Note: `NOTES_PROMPT` feeds the now-unused `generate_study_notes` path; the live pipeline uses the inline merged prompt.
- Empty-response guard (`raise ValueError` on empty) correct at `notes_generator.py:435-436` and `:887-888`; `contents=prompt` (`:431`) is the correct google-genai parameter.
- `outputs_current(marker, outputs, *sources)` signature matches the call at `outline_generator.py:287`.
- `start`/`end` removal from `VisualObjectItem` in `f456020` is safe — re-injected post-`model_dump()` at save and present in `create_empty_visual_object` fallback.
- Citation flow: strict `^ch(\d+)__` match in `references.ts:23` (correct for real Chroma ids `ch1__slug__idx` from `build_index.py:55`); chapter switch + `setDocTab('notes')` happen before the DOM poll; `setChapter` guarded `> 0` at `cite.ts:70`; `handleReferenceClick` mapping correct (screenshots routed to `onScreenshotClick`, never to `scrollToHeading`).
- 13f5d07 retry-status wiring is complete: status endpoint returns `{"stage":"retrying",…}` (`main.py:2501-2505`), ProcessingPage:71-74 handles it and keeps polling; stage keys match the frontend `STAGES` list exactly.
- YouTube multi-client ingestion (retries=10, `fragment_retries=10`, `player_client ["ios","android","web"]`) sound.

---

## Suggested fix plan (priority order)

1. **C1** — `outline_generator.py:303`: pass full `lecture_notes`, drop `[:5]`/`[:10]`; update docs.
2. **C2** — `visual_extractor.py:719/735`: no chunk-level fallback when `informative_basenames` empty.
3. **H1** — `screenshot_selector.py:502`: remove non-monotonic `*2`.
4. **H2/H3** — align the three chapter-count sources; honor LLM ranges (clamp/validate) with even-split fallback.
5. **H4** — `orchestrator.py:263`: use merged dir or rename param.
6. **H5** — tighten `stripSources` regex to appendix-shaped headers.
7. **M1-M6 + L1-L9** — frontend mobile citation, poll cap/cleanup, `ch0` guard, `completedStages` reset, defaults, `return synthesized`, etc.
8. Re-run `scripts/run-tests.sh` + `cd frontend && npm run test && npm run lint && npm run build`.
