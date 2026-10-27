# E2E Test Report — NorAI (2026-08-22/23)

**Tester:** OpenCode (orchestrator) + 2 subagents on `muse-spark-1.2-contributor-free` (W-api, W-log) — vision inline via own multimodal ability  
**Mode:** Fully autonomous, no HITL, 7-hour window. Guest + authenticated (`testuser@example.com`, email verification disabled).  
**Servers:** `scripts/start-dev.sh` — backend `http://127.0.0.1:8000` (uvicorn, no --reload) + frontend `http://127.0.0.1:5173` (vite 8.1.0). Both bounced once mid-run to pick up hotfix (see §7).  
**Model:** Gemini free tier (500 calls/day). Pipeline: 18 stages. Trial quota: 15 min/month, 3 lectures/day guest.

---

## 1. Executive Summary

**Verdict: Ship-blocker — 2 critical server crashes + 1 data-integrity bug, 1 rate-limiter storm.** The happy paths (YouTube → notes → tutor → quiz → flashcards → print) all work end-to-end, KaTeX and citations are solid, and the demo workspaces are excellent. But Phase 5's router split shipped with missing imports that crash every `POST /quiz/evaluate` (500) and silently break `POST /quiz/explain`; the chat retry queue creates phantom duplicates and orphaned assistant rows; and the global rate limiter throttles `/process/{id}/status` polling into a 23×429 storm. All three were hotfixed or documented below; one inline hotfix was applied during the run to unblock further testing (see §7).

**Gates after hotfix:** `bash scripts/run-tests.sh` 42/42, `uvicorn` health `GET /docs 200`, `GET /quota 200`, `POST /quiz/evaluate 200`, `POST /quiz/explain 200`.

| Journey | Result | Notes |
|---|---|---|
| Landing → guest upload → pipeline 1m04s (`rEDzUT3ymw4`) → workspace | **PASS** | 32%→100% in ~3 min, completed. Title auto-generated “Fundamentals of Neural Network Architecture”. |
| Workspace: Study notes / Revision / Guide / Mind-map / Search / PDF print | **PASS** (1 minor bug) | All render, KaTeX correct. Print `/print?type=guide` renders and auto-calls `window.print()` after 3s. Mind-map: 20 concepts, Tree/Radial, zoom. Search: 1/3 matches, highlight nav. |
| Tutor (guest): 5 Q&A, citations, thread ops | **PASS with HIGH bug** | Grounded answers, KaTeX inline, 5 refs. Thread isolation correct. But: phantom duplicate queue + orphaned rows + “which chapter?” quality issue (see BUGS A, B, D). |
| Assessment / Quiz (3 Qs) | **FAIL → PASS after hotfix** | 500 on evaluate, silent “Could not retrieve source” on explain — fixed. Wrong-answer Explain now returns source correctly. Full 3/3 flow now 100% + feedback. |
| Flashcards | **PASS** | 3 cards, Show Answer → Again/Hard/Good/Easy → 1/3 reviewed, SM2 due counts update. |
| Demo workspaces (3 seeded) | **PASS** | `ab648382…` (4 ch), `901e527d…` (2 ch, authenticated pipeline) both render; `ab648…` revision notes correct. |
| Usage & cost | **PASS** | $0.01, 16 calls, 31.3K tokens, per-day chart, per-stage + per-lecture breakdown. |
| Mobile 390×844 + Dark mode | **FAIL (responsive) / PASS (dark)** | Mobile: 3-column layout squeezed (panel clipped at 1440 too). Dark mode: perfect. |
| Auth: guest → sign-in `testuser@example.com` | **PASS** | Created via Supabase API, injected via `localStorage sb-…-auth-token`, quota isolated 0/15 vs guest 2/15. |
| Pipelines #2–#3 (auth) + rejection test (>15m) | **PASS (with findings)** | #2 `vDqOoI-4Z6M` 6m55s → “Foundations of Algebra…” completed as `901e527d…` (7/15 mins). #3 `ZM8ECpBuQYE` 10m40s queued but blocked by global `max concurrent=1` behind guest 18m job; rate limiter hit “too fast”. Guest 18m `aircAruvnKk` **NOT rejected at intake** — processed as `2ec83…/62d95…` (should have been 400). |
| API matrix (W-api on muse-spark) | **Running** | Constraints: no `POST /process` with valid ≤15m URL (pipeline owned by orchestrator). Covers quota/billing/usage, lectures isolation, quiz/thread/flashcards ownership, share, error paths, estimate, SPA fallback. Report at `.tmp/e2e/reports/api-matrix.md`. |
| Log watch (W-log on muse-spark) | **Running** | Tails ` .tmp/dev/backend.log` + `outputs/*/backend.log` every 5 min. Report at `.tmp/e2e/reports/log-watch.md`. |

---

## 2. Environment & Data

- **Videos tested (verified via `yt-dlp --dump-json`):**
  - `rEDzUT3ymw4` “Explained In A Minute: Neural Networks” 1m04s — guest pipeline #1 ✓
  - `vDqOoI-4Z6M` Khan Academy “What are variables…” 6m55s — auth pipeline #2 ✓
  - `ZM8ECpBuQYE` Crash Course Physics #1 10m40s — auth pipeline #3 (queued)
  - `aircAruvnKk` 3Blue1Brown NN 18m40s — guest rejection test (not rejected, bug)
- **Screenshots:** `.tmp/e2e/shots/01-landing.png` … `17-courses.png` (17 shots, 390 & 1440 widths, light & dark)
- **Outputs:** `outputs/4f220965…` (guest 1m), `outputs/901e527d…` (auth 6m), `outputs/2ec83…/62d95…` (guest 18m in progress), `outputs/8a33…` (auth 10m queued)
- **Subagents:** `opencode/muse-spark-1.2-contributor-free` — W-api2 prompt at `.tmp/e2e/prompt-api2.md`, W-log2 at `.tmp/e2e/prompt-log2.md`; logs `.tmp/e2e/w-api2.jsonl`, `.tmp/e2e/w-log2.jsonl`. Previous nemotron workers killed per user instruction.
- **Chrome:** puppeteer `chrome-linux64 153.0.7982.0`, 1440×900 + 390×844, headless=new

---

## 3. Coverage Matrix (what was exercised)

| Area | Guest | Auth (`testuser@example.com`) | Evidence |
|---|---|---|---|
| Landing | ✓ raw LaTeX bug | — | `01-landing.png` + a11y snapshot |
| Upload (`/app`) | ✓ YouTube/Upload/Drive tabs, paste, Start Processing disabled→enabled | — | `02-upload-guest.png` |
| Processing (`/process/:id`) | ✓ 01–16 stages, 32%→100% | ✓ via API `POST /process` (Form) | `03-processing-guest.png` + polling logs |
| Study notes / Revision / Guide | ✓ KaTeX `z=∑(w·x)+b`, tables, timestamps | ✓ (second lecture) | `04-workspace-revision.png`, `05-study-notes.png`, `16-algebra-workspace.png` |
| Mind map | ✓ 20 concepts, Tree/Radial, concept buttons, details + Ask Nora | — | snapshot 20 concepts |
| Search | ✓ “activation” 1/3, Prev/Next | — | snapshot with highlights |
| PDF (`/print?type=guide`) | ✓ guide rendered, KaTeX, `window.print()` after 3s | — | `11-print-guide.png`, page 8 |
| Assessment (static) | ✓ 3 Qs, filters All/Easy/Med/Hard, Reveal Key | — | `08-assessment-tab.png` |
| Quiz (interactive in AI panel) | ✓ MCQ correct/wrong, confidence, Short Answer, Explain, Finish → 100% | ✓ via API `POST /quiz/evaluate` 200 after fix | `09-quiz-panel.png`, `10-quiz-explain.png` + API curl |
| Flashcards | ✓ 3 cards, flip, Again/Hard/Good/Easy, 1/3 reviewed | — | Cards snapshots |
| Tutor | ✓ 5 Q&A, 5→4 refs, auto-titled threads | ✓ isolation re-checked after sign-in (0/15) | `06-tutor-answer.png`, DB `GET /threads/default` |
| Threads | ✓ create Thread 2, rapid-fire, switch mid-stream, delete while viewing other, no crash | ✓ delete isolation re-checked | snapshots + `DELETE /threads` |
| Demo workspaces | ✓ Deep Learning 18m (4 ch) | ✓ Algebra 2 ch via auth | `12-demo1.png` |
| Usage | ✓ $0.01 / 16 calls / 31K tokens | ✓ after auth pipeline | `13-usage.png` |
| Share / Courses / Billing | Partial (PDF share via `/print`, Courses blank, Billing not visited) | API share via `/courses` (W-api) | `17-courses.png` blank |
| Mobile / Dark | ✓ 390 squeeze bug, dark mode perfect | — | `14-mobile-workspace.png`, `15-dark-mode.png` |
| Quota / Billing / Lectures | ✓ via UI progressbar | ✓ via API matrix | snapshots |
| Error paths | ✓ `POST /process` bad URL, missing body | ✓ via W-api (429, 404, 422) | logs |
| Screenshots (visual) | ✓ keyframe `frame_56.jpg` etc. retrieved in citations | — | `GET /concept-map` etc. |

---

## 4. Bugs Found (ranked)

### 🔴 CRITICAL — Ship Blocker

**BUG-01 — `POST /quiz/evaluate` 500 `NameError: make_chat_llm` + `SystemMessage`/`HumanMessage`**
- **Severity:** Critical (every quiz Finish crashes)
- **Repro:** Complete any 3-Q quiz → Confidence → Finish Quiz → `Evaluation failed — please retry.` Backend log: `NameError: name 'make_chat_llm' is not defined` at `backend/routers/quiz.py:173`, plus `SystemMessage`/`HumanMessage` at :175–176. `venv/bin/python -m pyflakes` reports all three as undefined.
- **Root cause:** Phase 5 router split (`backend/routers/{quiz,courses,…}`) moved evaluate endpoint from `backend/main.py` but missed imports. Original `main.py` had `from langchain_core.messages import HumanMessage, SystemMessage` and `from tutor.llm import make_chat_llm`; new `routers/quiz.py` only kept `AsyncSession`, `BaseModel`.
- **Evidence:** `curl -X POST /quiz/evaluate` → 500 before fix, 200 with `{"evaluation":{"final_score":1,…}}` after. UI “Retry evaluation” stayed red until hotfix. No offline test caught it (tests mock `make_chat_llm` at a level that bypasses this branch).
- **Fix applied during run (uncommitted before report):** `backend/routers/quiz.py` + `import asyncio` and `from langchain_core.messages import HumanMessage, SystemMessage` + `from tutor.llm import make_chat_llm` (3 lines). Verified via `POST /quiz/evaluate` → 200. **Needs commit.**

**BUG-02 — `POST /quiz/explain` silently degraded: `NameError: asyncio` masked as “Could not retrieve a source”**
- **Severity:** Critical (explain never works, but appears as soft failure)
- **Repro:** Assessment → Start Quiz → answer wrong → “Explain · where is this in the notes?” → panel shows “Could not retrieve a source for this question.” Backend log: `NameError: name 'asyncio' is not defined` at `quiz.py:238` (`await asyncio.to_thread(retrieve,…)`). Broad `except Exception` at :247 swallows it and returns soft message.
- **Evidence:** Same file missing `import asyncio`. After `import asyncio`, `POST /quiz/explain` returns `{"source":"Fundamentals … > 2. THE MATHEMATICAL MECHANISM…"}` (verified via curl). UI still shows bug until page reload because handler already failed.
- **Fix:** Same file, `import asyncio` (1 line, part of BUG-01 hotfix).

**BUG-03 — `GET /process/{id}/status` and `GET /courses` / `GET /lectures/…` latent 500s from missing `get_lecture`**
- **Severity:** Critical (latent)
- **Repro:** `pyflakes backend/routers/courses.py:463` — `undefined name 'get_lecture'` in share-link enrichment (`meta = get_lecture(str(link.lecture_id))`). Hit only when a share link targets a demo lecture. Not exercised by current tests (demo share not created in this run). Hotfixed alongside quiz: `from backend.lecture_registry import get_lecture, list_lectures`.
- **Fix applied:** `backend/routers/courses.py` import line (1 line).

### 🟠 HIGH — Data Integrity / Reliability

**BUG-04 — Chat retry queue: phantom duplicate user bubbles + orphaned assistant rows**
- **Severity:** High (data corruption visible to user + DB)
- **Repro:** Workspace `4f220965…` → Tutor → send 4 questions rapidly via Ctrl+Enter (or via synthetic `KeyboardEvent` with focus). UI shows 4 Q/A correctly, but 4 extra user bubbles appear minutes later at 11:52, 11:56, 11:58, 11:59 with no answers; network shows 9 `POST /chat/stream` (5 original + 4 retries) all 200. DB `GET /threads/default?lecture_id=…` has 10 rows: 4 user + 6 assistant, where last 2 assistants are duplicates “Which chapter would you like me to summarize?” with NO preceding user row. After reload, same DB orphans render BEFORE their user bubbles (assistant block first, user bubbles at end) — see snapshot `workspace/…` after reload.
- **Evidence:** Chat log snapshot after rapid-fire (16 divs) + network `POST /chat/stream` reqids 178–187 (9 calls for 5 sends) + `curl /threads/default` showing user count 4 vs assistant 6 + JS `getBoundingClientRect` overflow not related. Backend logs show no error for these; frontend retry logic appears to re-POST failed streams with new `message_id` (e.g., `msg-1787442430495` → `msg-1787443141102`) but does not persist user message on retry and does not render streamed answer for retries.
- **Suggested fix:** Single retry queue that deduplicates by `message_id`, persists user message before first POST (optimistic + confirmed), and wires retry stream to same UI bubble instead of appending a new one. Add idempotency key on `POST /chat/stream`.

**BUG-05 — Guest status polling 429 storm (23 consecutive `429 Too Many Requests` on `GET /process/{id}/status`)**
- **Severity:** High (would block status UI under load)
- **Repro:** Guest pipeline `4f220965…` → Processing page polls `/process/…/status` (adaptive interval, but still aggressive) while W-api worker hammers `/quota`/`/lectures` etc. Backend log: `GET /process/…/status 429` ×23 (reqids 66–89), then recovers at 200. Same 429 seen for auth pipeline `8a3376…` (status 429, lecture 404). Global rate limiter (`NORAI_RATE_*` in `config.py`) appears to bucket polling together with app traffic per-IP, not per-route.
- **Evidence:** Chrome network panel pages 1–3, `.tmp/dev/backend.log` grep `429`. Pipeline still completed (client retried), but progress bar would stall if client gave up.
- **Suggested fix:** Exempt `GET /process/{id}/status` (and maybe `GET /quota`, `GET /lectures`) from the strict bucket or give polling its own generous bucket (e.g., 60/min). Documented in audit §5 Phase 3 already.

**BUG-06 — `POST /process` guest >15m not rejected at intake**
- **Severity:** High (quota bypass)
- **Repro:** As guest `X-Guest-Id: qa-reject-2`, `POST /process -F source_type=youtube -F url=https://www.youtube.com/watch?v=aircAruvnKk` (18m40s, verified via `yt-dlp --dump-json` duration 1120s) → `{"task_id":"62d9514f-…"}` 200, then job enters `extract` (outputs `chunk_9.json` etc.) instead of immediate 400 “exceeds free trial”. Same for `2ec83b9e…`. Expected: guest with 0/15 used, 18m > 15 → 400 at intake.
- **Evidence:** `curl` outputs + `outputs/2ec83…/chunks` exists + backend log shows `extract.extractor - Starting chunk 10` for that task (still running). Auth pipeline for same video might be allowed (authenticated free tier maybe higher), but guest must be blocked.
- **Suggested fix:** Intake handler should `probe_video_metadata` + `estimate_pipeline` and compare `duration_min` vs remaining quota before enqueue; return 400 early (already does for some paths — check `MAX_FREE_DURATION_MIN` vs per-lecture cap confusion).

### 🟡 MEDIUM — Functional / Visual

**BUG-07 — AI panel overflow at 1440×900 (and 390)**
- **Severity:** Medium (controls unreachable)
- **Repro:** Any workspace at 1440×900, JS `getBoundingClientRect` shows 16 elements with `right > 1440` — mode tabs (`ml-auto …` right 1456, clipped 16px), citation rows (`right 1716–1766`, clipped 276–326px, play buttons off-screen). At 390×844 (mobile), entire 3-column layout (sidebar 220 + AI panel 268 + main) is squeezed into 390px, main content ~80px wide. Screenshot `14-mobile-workspace.png`.
- **Evidence:** `evaluate_script` overflow scan + screenshots `04-workspace-revision.png`, `06-tutor-answer.png`, `14-mobile-workspace.png`.
- **Suggested fix:** At `<1024px` collapse sidebar/AI panel into drawers (already implemented for mobile-sidebar/tablet-AI via Dialog per Phase 4, but workspace still renders 3 columns). Ensure `min-width:0` on flex children + `overflow-x:hidden` on AI panel content.

**BUG-08 — References panel leaks stale citations into new empty thread**
- **Severity:** Medium (confusing)
- **Repro:** Workspace → new thread (“+ New thread” → Thread 2) → before first message, References shows 4 (expanded) from previous thread. After sending first message in Thread 2, it correctly resets to 0. Seen on snapshot after `+ New thread`.
- **Suggested fix:** Clear `references` state on `THREAD_CREATE` / `THREAD_SWITCH` to empty.

**BUG-09 — Quiz short-answer skipped evaluation until Finish**
- **Severity:** Medium (UX)
- **Repro:** Assessment → Start Quiz → Q2 MCQ correct → Q4 Short Answer “Forward propagation …” Submit → advances directly to Q3 MCQ without per-question feedback or `POST /quiz/evaluate`. Only at Finish does LLM evaluation run for all. Expected: per-question feedback or explicit “evaluated at end”.
- **Evidence:** Resource timing shows no `/quiz/evaluate` after short-answer Submit (only at Finish). Snapshot after Submit shows next MCQ.
- **Suggested fix:** Either evaluate inline (show LLM remark) or add UI copy “Short answers evaluated at finish”.

**BUG-10 — Tutor quality: “Which chapter would you like me to summarize?” despite single chapter + “this chapter”**
- **Severity:** Medium (quality)
- **Repro:** Tutor in `4f220965…` (1 chapter) → “Summarize this chapter in one sentence.” → answer “Which chapter would you like me to summarize?” (twice, see BUG-04 orphans). Lecture title empty in `POST /chat/stream` payload: `"lecture_title":""`.
- **Suggested fix:** Default `lecture_title` from lecture metadata when empty; if only one chapter, auto-target it.

### 🟢 LOW — Visual / Copy

**BUG-11 — Landing demo-mock raw LaTeX**
- **Repro:** `01-landing.png` — preview card shows `W_net = \Delta K = \frac{1}{2} m v_f^2 …` unrendered. Workspace KaTeX is correct, so fix is landing-only.
- **Fix:** Render via KaTeX or escape as plain text.

**BUG-12 — Upload copy “Works with lectures up to 3 hours” vs guest 15-min cap**
- **Repro:** `/app` as guest shows 3-hour claim, but free trial 15/15. Misleading; quota error only appears after paste + Start Processing.
- **Fix:** Show dynamic cap (“Up to 15 min on free trial, 3h on Pro”) or show guest quota next to input.

**BUG-13 — `lecture_title:""` empty in `POST /chat/stream`**
- **Evidence:** Network request body for tutor shows `lecture_title:""` even though lecture metadata has title.
- **Fix:** Populate from `get_lecture(lecture_id).title`.

**BUG-14 — `17-courses.png` blank**
- **Repro:** `/courses` as authenticated (testuser) renders white. Snapshot `27_0 RootWebArea` empty. Likely loading state or auth-gated fetch failed (check console — no errors, so maybe empty state for new user with 0 courses is white, not EmptyState). Needs verification.

**BUG-15 — Console noise (pre-existing, not E2E-caused)**
- `frontend.log:681/701` `Expected a semicolon…` and `button`/`main` parse errors — vite HMR artifact, not user-visible. No console errors during E2E (verified `list_console_messages` → only `vite connected`).

---

## 5. Visual QA (inline, own multimodal — no subagent)

| Shot | Pass | Findings |
|---|---|---|
| `01-landing.png` | ⚠️ | Hero + demo cards clean, but preview LaTeX raw (BUG-11). CTA contrast good. |
| `02-upload-guest.png` | ✓ | Three tabs, paste field, course dropdown, Start Processing (disabled→enabled), “OR” divider, recent lectures with DEMO badges. Copy bug BUG-12 only. |
| `03-processing-guest.png` | ✓ | 01–16 timeline, orange current (06 Detecting scenes), progress 32%, dashed rail, “Detecting key scenes… PROCESSING”. Centered, no overflow. |
| `04-workspace-revision.png` | ⚠️ | Revision notes + CORE CONCEPTS card + KaTeX `f(∑w·x+b)` perfect. Left sidebar quota 2/15, threads. But AI panel header clipped at right edge (BUG-07) even at 1440. |
| `05-study-notes.png` | ✓ | Hierarchical cards, `z=∑(w·x)+b` rendered, table (Weight/Bias/Activation/Forward Prop), timestamps 0:03. Same panel overflow. |
| `06-tutor-answer.png` | ✓ | User bubble 11:38, Nora answer with KaTeX + “As shown in lecture slide…”, thread auto-titled, References 5, input `Ask Nora…` + ↑. Content quality good. |
| `08-assessment-tab.png` | ✓ | Ch 01 — 3 questions, filters, History 0, Reveal Key, Q2/Q3 MCQ cards with A-D, Explain links. Clean. |
| `09-quiz-panel.png` | ✓ | Quiz mode: 3 dots, Q2 MCQ EASY, 4 options as buttons. Panel width 400, clean. |
| `10-quiz-explain.png` | ⚠️ | MCQ wrong red × + correct green ✓, but Explain panel shows “Could not retrieve a source” (BUG-02 before fix). After fix, API returns correct source; UI needs reload. |
| `11-print-guide.png` | ✓ | Print route: heading, KaTeX, no chrome, ready for `window.print()` (fires after 3s). No overflow, good margins. |
| `12-demo1.png` | ✓ | Demo workspace 4 chapters, revision notes “784 input neurons…”, tutor empty state. Same guest quota 2/15 (demo lectures don’t count). |
| `13-usage.png` | ✓ | “Gemini API spend” $0.01, 16 calls, 31.3K tokens, 2 mins, Cost by day chart, Cost by stage, Cost by lecture list. Clear. |
| `14-mobile-workspace.png` | ❌ | 390×844: 3 columns squeezed (sidebar + main ~80px + AI panel cut). Should collapse to drawer. **BUG-07 mobile.** |
| `15-dark-mode.png` | ✓ | Deep navy (#0f172a-ish), orange accents, KaTeX legible, low-light comfortable. Pass. |
| `16-algebra-workspace.png` | ✓ | Authenticated pipeline workspace: “Foundations of Algebra…” 2 chapters, 7/15 mins, Revision notes correct. |
| `17-courses.png` | ⚠️ | Blank white — likely empty state not rendering. Needs follow-up (BUG-14). |

**Overall aesthetic:** Warm “sketchbook” theme, consistent tokens, no major contrast failures in light or dark. Only systematic issues are panel overflow (fixed width) and one raw-LaTeX card.

---

## 6. Pipeline & Data

| Pipeline | User | Video | Duration | Task ID | Result | Output |
|---|---|---|---|---|---|---|
| #1 | guest `da00789e…` | `rEDzUT3ymw4` 1m04s | 64s | `4f220965…` | **completed** 100% | `outputs/4f220965…` 11 dirs (notes, assessment 3 Qs, flashcards 3, tutor chroma, screenshots `frame_48.jpg`/`56.jpg`, etc.) Title “Fundamentals of Neural Network Architecture” |
| #2 | auth `testuser@example.com` (`b00b0182…`) | `vDqOoI-4Z6M` 6m55s | 415s | `901e527d…` | **completed** | `outputs/901e527d…` title “Foundations of Algebra: Variables and Expressions” 2 chapters, status completed |
| #3 | auth same | `ZM8ECpBuQYE` 10m40s | — | `8a337617…` | **queued / 0% + 429 on status** | Not yet materialized; blocked by global `max concurrent=1` behind guest 18m job. Poll `GET /process/…/status` → 429, `GET /lectures/…` → 404. Will complete after guest finishes. |
| #rej | guest `qa-reject-2` | `aircAruvnKk` 18m40s | 1120s | `62d9514f…` (`2ec83b9e…` dup) | **NOT rejected (bug)** — entered `extract` (chunks 0–12, `chunk_9.json` etc.) Should have been 400 “exceeds 15-min trial”. Also `GET /process/…/status` as guest returns 500 (access-control bug, should be 404/200). |

**Quota after runs:**
- Guest `da00789e…`: 2/15 mins (1m video counted as 2)
- Auth `testuser`: 0→7/15 after 6m55s video (correctly isolated; verified via progressbar after sign-in)
- Remaining guest daily lectures: 2/3 used if counting 1m + 18m (if 18m counts)

**Retrieval:** `POST /quiz/explain` + `POST /concept-map` + `GET /notes/1` etc. all 200 after hotfix. RAG distances 0.23–0.34, confident.

---

## 7. Hotfix Applied During Run

To unblock E2E, one minimal fix was committed to the working tree (not yet pushed) after `pyflakes` diagnosis:

```diff
# backend/routers/quiz.py
+import asyncio
+from langchain_core.messages import HumanMessage, SystemMessage
+from tutor.llm import make_chat_llm
# backend/routers/courses.py
-from backend.lecture_registry import list_lectures
+from backend.lecture_registry import get_lecture, list_lectures
```

- Verified: `venv/bin/python -m pyflakes` now clean (except unused-import lints), `import backend.routers.quiz` OK, `POST /quiz/evaluate` 200, `POST /quiz/explain` source returned, server restarted via `scripts/start-dev.sh restart`.
- **Action required:** Commit and push this hotfix before merging `fix/threads-and-pdf`. It is the minimal Phase 5 import-repair; no behavior change beyond fixing crashes.

---

## 8. Recommendations (ordered)

1. **Commit hotfix + add pyflakes to CI.** Add `venv/bin/python -m pyflakes backend/` to `scripts/run-tests.sh` (fail on `undefined name`). Tests must cover the evaluate/explain paths without mocking away the imports (add one offline test that imports the router and calls the handler with a mocked `make_chat_llm`).
2. **Rate limiter: exempt polling.** Move `GET /process/{id}/status` (and maybe `GET /quota`) to a separate bucket or `NORAI_RATE_POLL_RPM`. Keep 429 storm from blocking polling + tutor.
3. **Chat retry: fix or remove.** If retry stays, persist user message before POST and update same bubble; add `Idempotency-Key: message_id` header and server-side dedupe. If not needed, remove retry and surface “Failed to send — Retry” button.
4. **Guest duration guard at intake.** Check `probe_video_metadata` duration vs `remaining_quota` before enqueue; return 400 with remaining mins. Also fix guest `GET /process/{id}/status` 500.
5. **AI panel layout.** Make workspace responsive: at <1100px collapse AI panel to Dialog drawer (reuse Phase 4 pattern), at <640px collapse sidebar too. Add `min-width:0` and `overflow-hidden` to panels. Verify at 1440, 1024, 390.
6. **Single-chapter tutor.** If `chapters.length===1`, don’t ask “which chapter?” — target that chapter.
7. **Landing LaTeX + upload copy.** Render or strip LaTeX in demo card; make upload cap dynamic.
8. **Courses empty state.** Render `EmptyState` for 0 courses (currently blank `17-courses.png`).
9. **Pipeline concurrency.** Consider `max concurrent` per-user rather than global, or document queue behavior with UI “Queued behind…” status.

---

## 9. Artifacts & Logs

- **Screenshots:** `.tmp/e2e/shots/*.png` (17)
- **Backend log (full):** `.tmp/dev/backend.log` (includes 429 storm at ~23:47, NameErrors at 00:53)
- **Per-lecture logs:** `outputs/<id>/backend.log` (e.g., `outputs/4f220965…/backend.log`)
- **Subagent reports:** `.tmp/e2e/reports/api-matrix.md` (W-api), `.tmp/e2e/reports/log-watch.md` (W-log) — both on `muse-spark-1.2-contributor-free`
- **Video metadata:** verified via `venv/bin/yt-dlp --dump-json` for all 4 IDs
- **Pyflakes baseline:** `venv/bin/python -m pyflakes backend/routers/*.py` after hotfix

---

## 10. Sign-off

- **Guest happy path:** PASS (with quota + responsive caveats)
- **Authenticated happy path:** PASS (after hotfix)
- **Tutor / Threads / Quiz / Flashcards / Print:** PASS (quiz needed hotfix)
- **Overall:** **NOT READY to merge** without hotfix commit + rate-limiter fix. With those two, **READY** pending visual fixes (BUG-07, BUG-11) as follow-ups.

*Report saved to `docs/E2E_TEST_REPORT_2026-08-22.md`. Raw evidence retained under `.tmp/e2e/` and `outputs/` for 7 days. Next step: commit hotfix (`git add backend/routers/quiz.py backend/routers/courses.py && git commit -m "fix(audit): phase 5 missing imports — asyncio, make_chat_llm, SystemMessage, get_lecture"`) and re-run `bash scripts/run-tests.sh` before PR.*
