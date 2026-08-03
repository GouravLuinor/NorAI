# NorAI Frontend — Design Review & Implementation Roadmap

Status: Tier 0 complete. Roadmap approved. Next: Tier 1 implementation.

Scope: **App frontend only** (`frontend/src`) — the React 19 + Vite + Tailwind v4 three-panel workspace.

Direction (approved): **Refine the dark theme** — keep dark, apply premium principles (token cleanup, distinctive type, sharp geometry, one brand-owned accent). Not a redesign to light; not a visual reboot.

References used:
- `DESIGN.md` — Vercel design language (light achromatic, shadow-as-border, double-ring focus, 400/500/600 weights).
- `startup/NorAi_Ofiicial_Web/premium-site-reference.md` — what makes premium sites read as premium (mid-2026 findings).
- `frontend-design` skill (Anthropic) — distinctive, non-templated design.
- `web-design-guidelines` skill (vercel-labs) — Web Interface Guidelines compliance.
- `startup/NorAi_Ofiicial_Web` tokens — the brand's already-committed Obsidian Slate + Electric Viridian system.

---

## 0. Current State

- React 19 + TypeScript + Vite + Tailwind CSS v4, Zustand, Framer Motion, react-markdown, KaTeX.
- 3-panel workspace (Sidebar | DocPanel | AIPanel), custom resize system, dark `#0F0F0E` canvas, purple `#7C6FD4` accent, Inter typeface.
- Fully backend-wired (no mock data live). 36 source files, ~2,500 lines.
- Working light-theme override via `[data-theme="light"]` CSS-variable swap.

**What's already good (preserve):**
- Feature-oriented architecture; Zustand stores; SSE parser exists; abort controllers for stale responses; optimistic thread CRUD + localStorage persistence; centralized `@theme` tokens; search-highlight, print page, Lightbox, shimmer loaders.

---

## 1. Critique — Findings Summary

### 1.1 Premium design (frontend-design + premium-site-reference)

| # | Finding | Location |
|---|---|---|
| P1 | Dark + purple-glow is the AI-startup default and under-differentiated. Same "templated dark" the marketing site already rejected (`#030712` + blue glow). Needs one brand-owned accent + sharp geometry. | `index.css:24` `#7C6FD4` |
| P2 | No distinctive display typography — Inter everywhere at 9–14px. "Competent, not premium." | `index.css:10` |
| P3 | No signature element — the one memorable detail is missing (the marketing site has the Live Console Teaser). Closest: the tiny "Nora" avatar. | `AIPanel.tsx:41` |
| P4 | Tiny font sizes (`text-[9px]`, `text-[9.5px]`, `text-[10px]`, `text-[11px]`) in nearly every component — busy + readability risk. | `Sidebar.tsx:129`, `NotesView.tsx:123`, `assessment-cards.tsx:13` |
| P5 | Soft-shadow-everywhere (`shadow-sm/lg/2xl`) vs 2026 shift to sharp 1px borders + minimal radius. | throughout |
| P6 | Decorative gradient dividers instead of spacing/surface separation. | `Sidebar.tsx:175,212` |
| P7 | Consistent with premium reference: no autoplay hero, speed-conscious. Keep. | — |

### 1.2 DESIGN.md compliance

| # | Finding | Location |
|---|---|---|
| D1 | No double-ring focus pattern; effectively no `:focus-visible` styling anywhere. | `Sidebar.tsx:140`, `UploadPage.tsx:138` |
| D2 | Hardcoded `hover:bg-[#8E82E0]` duplicated in 6 files; doesn't adapt to light mode. | `UploadPage.tsx:150`, `ProcessingPage.tsx:158`, `InputZone.tsx:56`, `QuizPanel.tsx:138,272,304`, `AssessmentView.tsx:60`, `HighlightAsk.tsx:170` |
| D3 | Elevation tokens `--ev1/2/3` defined but never used; shadows hardcoded inline. | `index.css:220`, `assessment-cards.tsx:29,42,45,72,90` |
| D4 | `--radius` token is dead (needs `--radius-*` namespace in v4). | `index.css:47` |
| D5 | Status dots inconsistent (purple / `nt4` / raw colors); semantics not pinned. | `Sidebar.tsx:119,194`, `PrintPage.tsx:51,281` |
| D6 | Font-weight 700 present; DESIGN.md caps at 600. | misc |

### 1.3 Web Interface Guidelines (vercel-labs) violations

**Accessibility / keyboard (highest priority):**
- Clickable `<div>`/`<li>` with no keyboard path / `role` / `tabIndex`: `Sidebar.tsx:156-170` (chapters), `Sidebar.tsx:182-208` (threads), `assessment-cards.tsx:29` (MCQ), `assessment-cards.tsx:91` (answer key), `ReferencesPanel.tsx:21-23`, `FlashcardsPanel.tsx:88-90`, `ChapterScreenshots.tsx:60-65`.
- Icon-only buttons missing `aria-label`: `SearchBar.tsx:148-157`, `ShortcutsModal.tsx:35`.
- Modals not real dialogs (no `role="dialog"`/`aria-modal`/focus trap/focus restore): `ShortcutsModal.tsx:29-30`, `Lightbox.tsx:29-58`. Escape collision with Workspace (`Workspace.tsx:33-41`).
- Resize handles not keyboard-accessible (`Workspace.tsx:142-156`).
- No `aria-live`: ToastContainer, ChatArea streaming.
- Contrast: `nt3` ≈ 2.9:1, `nt4` ≈ 1.7:1, white-on-`np` ≈ 4.1:1 — all fail AA at tiny sizes.
- No `prefers-reduced-motion` handling anywhere.
- `ProcessingPage.tsx:80` hardcodes `http://localhost:8000` (breaks in prod, bypasses Vite proxy).
- Images missing explicit `width`/`height` (`NotesView.tsx:252`).
- Dates via custom `getRelativeTime` instead of `Intl.RelativeTimeFormat` (`UploadPage.tsx:15`); `...` not `…`.

### 1.4 Code quality / maintainability

- **Dead code:** 7 `mocks/*` files (~330 lines), `App.css` (184 lines), `EvidenceCard.tsx`, `sendChatMessageStream` + `streamingText` (never consumed), `fetchSummary` (`useQuizStore.ts:194`), unused `clsx`, unused `src/assets/*`.
- **Duplication:** 4 near-identical ReactMarkdown `Components` objects (`NotesView.tsx:208-265`, `RevisionView.tsx:218-254`, `PrintPage.tsx:80-98`, `MessageBubble.tsx:36-58`); `headingToId` ×5; primary-button + card classes ×15. No shared UI primitives.
- **Monoliths:** `useThreadStore.ts` (555), `NotesView.tsx` (431), `RevisionView.tsx` (422), `PrintPage.tsx` (399), `QuizPanel.tsx` (315).
- **34 `any` usages** at API seams.
- **`console.log` leftovers:** `DocPanel.tsx:17`, `ProcessingPage.tsx:81,83,89`, `HighlightAsk.tsx:95`.
- **No unified API layer** — fetches scattered; `API_BASE` defined twice.

---

## 2. Approved Design Direction

### 2.1 Accent — Electric Viridian `#0CCAB1`

Replace purple `#7C6FD4` with the marketing site's committed brand accent:
- Primary accent: **`#0CCAB1`** (Electric Viridian)
- Status/mono accent: **`#45F7D6`** (Phosphor Mint)
- Keep purple/blue/green/red/amber as **10px status dots only** (DESIGN.md semantics): `#398E4A`, `#FF990A`, `#E5484D`, `#0062D1`, `#7820BC`.

Rationale: purple-on-near-black is the AI-startup default the premium reference flags. The marketing site already ran the full premium review and landed on this as a deliberate brand choice. One accent across app + marketing = one cohesive NorAI brand. The premium reference cites singular teal/green as a differentiator in a category that defaults to blue/purple.

### 2.2 Typography — editorial serif display + mono metadata

| Role | Face | Usage |
|---|---|---|
| Display | **Newsreader** (editorial serif, built for long-form reading) | Chapter titles, document H1s, section headers in the reading pane, "Nora" identity |
| UI | **Inter** (keep) | Buttons, nav, inputs — the quiet shell |
| Mono | **JetBrains Mono** (keep) | Timestamps, "Ch 01", stage labels, code, metadata |

Self-host via Google Fonts with `font-display: swap` + `<link rel="preload">`; no layout shift.
Constraints from DESIGN.md: weights 400/500/600 only; aggressive negative letter-spacing on display sizes (-4% to -4.75%); letter-spacing returns to normal at body sizes.

### 2.3 Signature element

The one memorable detail: **the "Nora" AI identity** — editorial serif wordmark + live status dot (Phosphor Mint when active/idle, status colors for states). Additionally, a reading-surface typographic signature: Newsreader display headlines in the doc pane make the product instantly recognizable as an education/reading tool.

---

## 3. Implementation Roadmap

> **Tick off each item (`[x]`) as it's implemented.** A tier is only "complete" when its `QA` checkbox is ticked (build + lint green, Pass A review clean, Pass B Chrome MCP clean). Status legend: `[ ]` = not started, `[x]` = done.

### Tier 0 — Hygiene & correctness (no visual risk)

- [x] 1. Delete dead code: `src/mocks/*` (7 files, keep the `Reference` type import), `src/App.css`, `src/components/chat/EvidenceCard.tsx`, unused `src/assets/*`, remove unused `clsx` dependency if confirmed unused.
- [x] 2. Remove debug `console.log`s: `DocPanel.tsx:17`, `ProcessingPage.tsx:81,83,89`, `HighlightAsk.tsx:95`.
- [x] 3. Fix `ProcessingPage.tsx:80` hardcoded `http://localhost:8000` → `VITE_API_BASE_URL`/Vite proxy (relative path).
- [x] 4. Type tightening at API seams — replace the riskiest `any`s in store layer (`useThreadStore.ts`, `useQuizStore.ts`).
- [x] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean.

### Tier 1 — Design token overhaul (refine dark, stay dark)

- [ ] 5. Expand `@theme` in `index.css`:
   - [ ] `--color-nph` primary hover (fixes 6-file duplication + light-mode mismatch)
   - [ ] Elevation `--ev1/2/3` → proper tokens, wired into all shadow utilities
   - [ ] `--text-*` type ramp (replaces arbitrary `text-[9px]`…`text-[13px]` soup)
   - [ ] Focus-ring tokens (`--ds-focus-ring` double-ring)
   - [ ] Fix dead `--radius` → `--radius-*`
- [ ] 6. Replace all hardcoded `#8E82E0` and inline `rgba(…)` shadows with tokens.
- [ ] 7. Swap accent purple → viridian (`np/npb/npbr` = `#0CCAB1` + tints); pin status-dot palette per DESIGN.md.
- [ ] 8. Shadow-as-border (`0 0 0 1px rgba(0,0,0,0.08)`) for card boundaries; remove gradient dividers → surface color + spacing.
- [ ] 9. Add `color-scheme: dark`, `<meta name="theme-color">`, `prefers-reduced-motion` support (disable shimmer, x-slides, smooth scroll, scrollpulse).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean.

### Tier 2 — Component foundation (kill duplication)

- [ ] 10. Build `src/components/ui/` primitives: `Button`, `IconButton`, `Card`, `Input`, `SegmentedControl`, `Badge`. Migrate the ~15 copy-paste sites (primary button, ghost button, card container, section-label).
- [ ] 11. Extract a single shared markdown `components` object (`src/lib/markdown.tsx`) + `headingToId` util (dedupe 4× + 5×).
- [ ] 12. Wire real SSE streaming: `sendChatMessageStream` exists but is dead — `ChatArea` consumes it so the loading shimmer is honest.
- [ ] 13. Decompose monoliths: split `useThreadStore.ts` (chat API layer + store), `PrintPage.tsx` (error boundary, card classifier, markdown renderers, data fetching).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean.

### Tier 3 — Accessibility & Web Interface Guidelines compliance

- [ ] 14. Clickable `<div>`/`<li>` → `<button>`/`<Link>` with keyboard path: `Sidebar` (chapters/threads), `assessment-cards` (MCQ, answer key), `ReferencesPanel`, `FlashcardsPanel` (flip), `ChapterScreenshots` (zoom).
- [ ] 15. `:focus-visible` double-ring pattern app-wide; replace `outline-none`-only inputs.
- [ ] 16. Modals → `role="dialog"` + `aria-modal` + focus trap + focus restore (`ShortcutsModal`, `Lightbox`); fix Escape collision.
- [ ] 17. `aria-live` on ToastContainer + chat streaming; `aria-label` on all icon buttons (`SearchBar`, `ShortcutsModal`).
- [ ] 18. Contrast fixes: bump `nt3`/`nt4`, ensure primary-button text ≥ 4.5:1 AA.
- [ ] 19. Keyboard-resizable panels (`role="separator"`, `aria-valuenow`, arrow keys); `Intl.RelativeTimeFormat`; `…` not `...`; image `width`/`height`.
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean (incl. Lighthouse a11y).

### Tier 4 — Premium signature pass

- [ ] 20. Typography ramp: collapse tiny sizes into the real `--text-*` scale; Newsreader display + mono metadata + negative tracking on headlines.
- [ ] 21. Signature element: refined "Nora" identity in the AI panel (editorial serif wordmark + live status dot).
- [ ] 22. Consistent empty/loading/error states; fix quiz `finishQuiz` silent-failure (`QuizPanel.tsx:189-191`) and unconditional "Quiz started" toast (`AIPanel.tsx:59`); add `incomplete: true` warning badge (from tier2 plan Open Question 2).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean.

---

## 4. Verification Per Tier

After every tier, run the full QA protocol (§4.1) and confirm green before starting the next tier.

### 4.1 QA Protocol — Parallel Review + Browser Test

After each tier is implemented, run **two independent passes in parallel** (subagent fan-out):

**Pass A — Code Review (subagent, read-only)**
- Agent: `general` subagent (`--agent general`, pinned to `opencode/deepseek-v4-flash-free`).
- Scope: only the files changed during the tier (diff via `git diff` against pre-tier state).
- Checks: correctness, the tier's specific checklist items, regressions, dead code introduced, `any` usage, `console.log` leftovers, DESIGN.md / web-interface-guidelines compliance for new UI.
- Output: written to `.tmp/review-tier-N.md`, ends with a one-line verdict.

**Pass B — Browser Test (Chrome DevTools MCP)**
- Start the dev server (`npm run dev` on the frontend, backend running).
- Drive the real UI with Chrome MCP: load the app, switch themes (dark **and** light), exercise the tier's touched flows (workspace load, chapter switch, notes/revision/assessment render, tutor chat, quiz, flashcards, resize panels, print page), and capture:
  - a screenshot per key view (viewport + full-page where relevant)
  - console errors/warnings via `list_console_messages`
  - Lighthouse snapshot audit (accessibility/best practices) where a tier touches a11y
- Output: notes + screenshots in `.tmp/qa-tier-N/`.

**Orchestration**
- Dispatch both passes concurrently (one `opencode serve` + two attached `opencode run` workers, or the Task tool's general agents) so code review and browser testing overlap.
- On any failure: fix, re-run the affected pass, and only then proceed to the next tier.
- Kill the serve worker and keep `.tmp/` uncommitted after each tier.

### 4.2 Baseline Checks (both passes gate on)

- `npm run build` (tsc + vite) — no type errors
- `npm run lint` (oxlint) — no new warnings

---

## 5. Open Items / Decisions Log

- [ ] Confirm font loading approach (Google Fonts CSS vs self-hosted) at Tier 1.
- [ ] Confirm viridian hover tint value for `--color-nph` (derive from `#0CCAB1` HSL shift, matching marketing site methodology).
- [ ] Streaming: decide whether real SSE replaces non-streaming path or exists as fallback (Tier 2.12).
- [ ] `incomplete: true` badge design (subtle warning dot + text) — flag from tier2 Open Question 2.

---

## Progress Summary

Each tier gates on: build + lint green, Pass A code review verdict clean, Pass B Chrome MCP test clean (no console errors, screenshots verified, Lighthouse a11y where applicable).

- **Tier 0**: `[x]` **complete** — dead code deleted (mocks ×7, App.css, EvidenceCard, assets, clsx); console.logs removed; `/process` URL → relative via Vite proxy; store-layer `any` eliminated (liveReferences→`Reference[]`, typed `ChatResponse`/flashcards, removed dead `fetchSummary`); `Reference`/`RetrievedChunk`/`RetrievedImage`/`ChatResponse`/`ProcessEvent`/`Flashcard` moved to `src/types/index.ts`. Build ✓ lint ✓ Pass A ✓ Pass B ✓ (artifacts in `.tmp/review-tier-0.md`, `.tmp/qa-tier0/`).
- **Tier 1**: `[ ]` not started
- **Tier 2**: `[ ]` not started
- **Tier 3**: `[ ]` not started
- **Tier 4**: `[ ]` not started
