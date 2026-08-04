# NorAI Frontend — Design Review & Implementation Roadmap

Status: Tier 0 complete, Tier 1 complete. Roadmap amended for the **Architect's Sketchbook** reboot. Next: continue Tier 2 (primitives) → Tier 5 (Sketchbook layer).

Scope: **App frontend only** (`frontend/src`) — the React 19 + Vite + Tailwind v4 three-panel workspace.

Direction (approved — REBOOT): **"Architect's Sketchbook"** — Theme 1 research pick. A warm drafting-table / spec-sheet aesthetic: vellum-paper **light default** + Prussian-blue **dark**, ink linework, red-pencil annotations, visible grid + grain, two display voices (Space Grotesk chrome + Newsreader reading), hard-offset shadows, spec-section numbering. Goal: **humane, handcrafted, non-AI-garbage** — explicitly avoiding the dark+neon AI-startup default. The old viridian "Electric Viridian #0CCAB1 / keep dark / stay subtle" direction is **superseded**. App identity is independent of the (unfinalized) marketing site, so app ≠ marketing branding is no longer a constraint.

References used:
- `DESIGN.md` — Vercel design language (light achromatic, shadow-as-border, double-ring focus, 400/500/600 weights).
- `startup/NorAi_Ofiicial_Web/premium-site-reference.md` — what makes premium sites read as premium (mid-2026 findings).
- `frontend-design` skill (Anthropic) — distinctive, non-templated design.
- `web-design-guidelines` skill (vercel-labs) — Web Interface Guidelines compliance.
- `startup/NorAi_Ofiicial_Web` tokens — **obsolete for the frontend**; app identity decoupled from the (unfinalized) marketing site.
- Handmade-design research (nngroup.com "Handmade Designs: The New Trust Signal", 2026; neo-brutalism guides; blueprint/technical-drawing design systems). **Pick: Theme 1 — Architect's Sketchbook, drafting-table execution** (warm vellum light + Prussian dark, red-pencil annotations, grid + grain).

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

## 2. Approved Design Direction — "Architect's Sketchbook" (REBOOT)

Executed on the **drafting-table** half of the idiom (warm paper + ink + red-pencil annotations + visible grid), NOT the cold cyanotype. Rationale: blueprint = precision (AI-output credibility); sketchbook = humanity (anti-AI-garbage). A study platform = "a mind building understanding, visibly." Over-polish now reads as fake (nngroup 2026) — visible effort and "showing the process" are the new trust signals.

### 2.1 Two color systems (of one system) — default flips to light

**"Drafting Vellum" (light, DEFAULT):** canvas `#F6F2E7` aged paper / surface `#FBF8F1` / raised `#EFE9DA`; ink `#241F1A` / secondary `#5C524A` / faint `#8D8378`; hairline `rgba(36,31,26,0.14)`; grid `rgba(36,31,26,0.05)`.

**"Blueprint at Night" (dark):** canvas `#0A1628` Prussian / surface `#0D1F35` / raised `#132740`; ink `#E8ECF1` / secondary `#A9B6C6` / faint `#6E7F92`; hairline `rgba(232,236,241,0.10)`; grid `rgba(212,240,255,0.05)`.

Both themes: status dots stay pinned 10px semantics per DESIGN.md (`#398E4A`, `#FF990A`, `#E5484D`, `#0062D1`, `#7820BC`).

### 2.2 Accent — Red Pencil

- Light: **`#C2410C`** fill (white-text AA ≈5.2:1) / **`#D1552E`** hover / `rgba(194,65,12,0.10)` tint.
- Dark: **`#D1552E`** fill / **`#E85D2F`** hover / `rgba(209,85,46,0.14)` tint.

Rationale: brick-red is a deliberate break from the blue/purple/viridian/cyan AI-startup default; it reads as "a human annotated this." **Electric Viridian `#0CCAB1`/Phosphor Mint `#45F7D6` tokens are retired** (app ≠ marketing). Red appears as annotation/CTA/active voice only — never full-bleed.

### 2.3 Typography — two display voices + quiet shell + metadata

| Role | Face | Usage |
|---|---|---|
| Display (chrome) | **Space Grotesk** 500/600/700, tight tracking | Hero, panel/section headers, pipeline stage labels, "Nora" wordmark |
| Display (reading) | **Newsreader** (editorial serif, kept) | Chapter titles, document H1s in the reading pane |
| UI | **Inter** (keep) | Buttons, nav, inputs — the quiet shell |
| Mono | **JetBrains Mono** (keep) | Spec labels `01. INGEST`, timestamps, code, metadata — ALL-CAPS `tracking-[0.15em]` |

Self-host via Google Fonts with `font-display: swap` + `<link rel="preload">`; no layout shift. Weights 400/500/600 for shell; Space Grotesk may use 700 for display moments.

### 2.4 Structure & polish

- **Hard-offset shadows** (`--shadow-bp-*`: `3px 3px 0 0`, zero blur) for interactive/elevated elements; keep 1px shadow-as-border as base. Radii tighten toward `rounded-sm`/square for chrome (chips keep small radius).
- **Visible-but-quiet blueprint grid** (≤5–6% opacity, 8px-snapped) + **grain overlay** (~6%) on canvas.
- **Fold-marks / crosshair registration corners** on panels and cards.
- **Spec-section numbering** `01.`–`NN.` for stages, panels, chapters.
- **Red-pencil annotation utilities**: `NOTE:` callouts, dimension markers `←—[48px]—→`.
- **Signature micro-interactions**: self-drawing pipeline connectors (`stroke-dasharray`, framer-motion), press-down CTAs (`active:translate` + hard shadow). All gated by `prefers-reduced-motion`.
- Banned: gradients, glassmorphism, 3D, glow, emoji, pure `#000`/`#FFF` surfaces, neon/viridian accents, centered long-form text.

### 2.5 Signature element

**"Nora" wordmark** in Space Grotesk + live status dot (accent when active/idle, status colors for states). Second signature moment: the **self-drawing pipeline** on ProcessingPage ("we show our work"). Third: Newsreader display headlines in the reading pane.

---

## 3. Implementation Roadmap

> **Tick off each item (`[x]`) as it's implemented.** A tier is only "complete" when its `QA` checkbox is ticked (build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean). Status legend: `[ ]` = not started, `[x]` = done.

### Tier 0 — Hygiene & correctness (no visual risk)

- [x] 1. Delete dead code: `src/mocks/*` (7 files, keep the `Reference` type import), `src/App.css`, `src/components/chat/EvidenceCard.tsx`, unused `src/assets/*`, remove unused `clsx` dependency if confirmed unused.
- [x] 2. Remove debug `console.log`s: `DocPanel.tsx:17`, `ProcessingPage.tsx:81,83,89`, `HighlightAsk.tsx:95`.
- [x] 3. Fix `ProcessingPage.tsx:80` hardcoded `http://localhost:8000` → `VITE_API_BASE_URL`/Vite proxy (relative path).
- [x] 4. Type tightening at API seams — replace the riskiest `any`s in store layer (`useThreadStore.ts`, `useQuizStore.ts`).
- [x] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean.

### Tier 1 — Design token overhaul (pre-reboot; token *structure* retained, values re-tinted in Tier 5)

- [x] 5. Expand `@theme` in `index.css`:
   - [x] `--color-nph` primary hover (fixes 6-file duplication + light-mode mismatch)
   - [x] Elevation `--ev1/2/3` → proper tokens, wired into all shadow utilities
   - [x] `--text-*` type ramp (replaces arbitrary `text-[9px]`…`text-[13px]` soup)
   - [x] Focus-ring tokens (`--ds-focus-ring` double-ring)
   - [x] Fix dead `--radius` → `--radius-*`
- [x] 6. Replace all hardcoded `#8E82E0` and inline `rgba(…)` shadows with tokens.
- [x] 7. Swap accent purple → viridian (`np/npb/npbr` = `#0CCAB1` + tints); pin status-dot palette per DESIGN.md. **⚠ AMENDED by reboot §2.2 — re-tint to red-pencil** in Tier 5.
- [x] 8. Shadow-as-border (`0 0 0 1px rgba(0,0,0,0.08)`) for card boundaries; remove gradient dividers → surface color + spacing.
- [x] 9. Add `color-scheme`, `<meta name="theme-color">`, `prefers-reduced-motion` support (disable shimmer, x-slides, smooth scroll, scrollpulse). **⚠ default flips to light (vellum) in Tier 5.**
- [x] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean (artifacts in `.tmp/q-tier1/`).

### Tier 2 — Component foundation (kill duplication)

- [ ] 10. Build `src/components/ui/` primitives: `Button`, `IconButton`, `Card`, `Input`, `SegmentedControl`, `Badge`. Migrate the ~15 copy-paste sites (primary button, ghost button, card container, section-label). **Blueprint grammar:** hairline ink border + `--shadow-bp-*` hard shadow + optional fold-mark; icons at lucide `strokeWidth={1.5}`; section labels in mono ALL-CAPS.
- [ ] 11. Extract a single shared markdown `components` object (`src/lib/markdown.tsx`) + `headingToId` util (dedupe 4× + 5×).
- [ ] 12. Wire real SSE streaming: `sendChatMessageStream` exists but is dead — `ChatArea` consumes it so the loading shimmer is honest.
- [ ] 13. Decompose monoliths: split `useThreadStore.ts` (chat API layer + store), `PrintPage.tsx` (error boundary, card classifier, markdown renderers, data fetching).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean.

### Tier 3 — Accessibility & Web Interface Guidelines compliance

- [ ] 14. Clickable `<div>`/`<li>` → `<button>`/`<Link>` with keyboard path: `Sidebar` (chapters/threads), `assessment-cards` (MCQ, answer key), `ReferencesPanel`, `FlashcardsPanel` (flip), `ChapterScreenshots` (zoom).
- [ ] 15. `:focus-visible` double-ring pattern app-wide; replace `outline-none`-only inputs.
- [ ] 16. Modals → `role="dialog"` + `aria-modal` + focus trap + focus restore (`ShortcutsModal`, `Lightbox`); fix Escape collision.
- [ ] 17. `aria-live` on ToastContainer + chat streaming; `aria-label` on all icon buttons (`SearchBar`, `ShortcutsModal`).
- [ ] 18. Contrast fixes: bump `nt3`/`nt4`, ensure primary-button text ≥ 4.5:1 AA (red-pencil fill uses ink or white per theme — verify in Pass C).
- [ ] 19. Keyboard-resizable panels (`role="separator"`, `aria-valuenow`, arrow keys); `Intl.RelativeTimeFormat`; `…` not `...`; image `width`/`height`.
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean (incl. Lighthouse a11y).

### Tier 4 — Signature typography pass

- [ ] 20. Typography ramp: collapse tiny sizes into the real `--text-*` scale; **Space Grotesk** (chrome/hero/pipeline/panel headers) + **Newsreader** (reading pane titles/H1s) + mono metadata; tight tracking on display.
- [ ] 21. Signature element: refined "Nora" wordmark in **Space Grotesk** in the AI panel + live status dot.
- [ ] 22. Consistent empty/loading/error states; fix quiz `finishQuiz` silent-failure (`QuizPanel.tsx:189-191`) and unconditional "Quiz started" toast (`AIPanel.tsx:59`); add `incomplete: true` warning badge (from tier2 plan Open Question 2).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean, Pass C vision audit clean.

### Tier 5 — "Architect's Sketchbook" theme layer (reboot)

> Re-tints/supersedes the viridian tokens from Tier 1 (item 7). Loads fonts + flips default theme. Implements the committed §2 system.

- [ ] 23. Fonts: load Space Grotesk + Newsreader in `index.html` (`font-display: swap` + preload); keep Inter + JetBrains Mono.
- [ ] 24. Token re-skin in `index.css` per §2.1/§2.2: vellum light default (flip `:root color-scheme` + `theme-color`) + Prussian dark; retire viridian `np/nph/npfg/npb/npbr` → red-pencil tokens; add `--shadow-bp-*` hard-offset shadows; tighten radii.
   - [ ] 24a. **Theme polarity flip (beyond token swap):** invert `index.css` — base block becomes vellum light (`color-scheme: light`), add a `[data-theme="dark"]` Prussian override (mirrors the old light-override pattern).
   - [ ] 24b. **`ThemeToggle.tsx`:** default from `'dark'` → `'light'` (`ThemeToggle.tsx:8`); update hardcoded meta `theme-color` hex `#0F0F0E`/`#FAFAF8` → vellum `#F6F2E7` / Prussian `#0A1628` (`ThemeToggle.tsx:15`).
   - [ ] 24c. **Elevation shadows:** `--shadow-ev1/2/3` referenced 54×. Keep 1px shadow-as-border base; add `--shadow-bp-*` hard-offset tokens (e.g. `3px 3px 0 0`). Re-point interactive/elevated utilities `shadow-ev2/ev3` → `shadow-bp`; keep `ev1` (or a renamed hairline token) for muted containers. No call-site edits needed (utilities cascade).
- [ ] 25. Texture utilities: `.bg-blueprint-grid` (≤6% opacity), `.noise` grain (~6%), `.fold-marks` corner ticks. Apply to Workspace root, ProcessingPage, UploadPage hero, cards.
- [ ] 26. Spec-section numbering `01.`–`NN.` for pipeline stages, sidebar sections, panel headers (mono ALL-CAPS).
- [ ] 27. ProcessingPage = schematic showpiece: numbered spec rows, self-drawing connector lines (framer-motion `stroke-dasharray`/`offset` driven by `activeStage`), progress bar as dashed draft-line → solid ink. Gated by `prefers-reduced-motion`.
- [ ] 28. Red-pencil annotation utilities: `NOTE:` callouts, dimension markers; UploadPage hero leader-line diagram (`Video → Notes → Quiz → Tutor`).
- [ ] 29. Hairline icon pass: lucide `strokeWidth={1.5}`, ink-colored, in primitives + app-wide.
- [ ] 30. Press-down CTAs on interactive elements (`active:translate` + hard shadow).
- [ ] QA: build + lint green, Pass A review clean, Pass B Chrome MCP clean (dark AND light), Pass C vision audit clean (checklist §4.1).

---

## 4. Verification Per Tier

After every tier, run the full QA protocol (§4.1) and confirm green before starting the next tier.

### 4.1 QA Protocol — Parallel Review + Browser Test

After each tier is implemented, run **three independent passes in parallel** (subagent fan-out):

**Pass A — Code Review (subagent, read-only)**
- Agent: `general` subagent (`--agent general`, pinned to `opencode/deepseek-v4-flash-free`, text-only).
- Scope: only the files changed during the tier (diff via `git diff` against pre-tier state).
- Checks: correctness, the tier's specific checklist items, regressions, dead code introduced, `any` usage, `console.log` leftovers, DESIGN.md / web-interface-guidelines compliance for new UI.
- Output: written to `.tmp/review-tier-N.md`, ends with a one-line verdict.

**Pass B — Browser Test (Chrome DevTools MCP)**
- Start the dev server via `scripts/start-dev.sh start` (idempotent, probe-based; NEVER relaunch over a live port — see AGENTS.md "Dev-server gotchas").
- Drive the real UI with Chrome MCP: load the app, switch themes (dark **and** light), exercise the tier's touched flows (workspace load, chapter switch, notes/revision/assessment render, tutor chat, quiz, flashcards, resize panels, print page), and capture:
  - a screenshot per key view (viewport + full-page where relevant) — **save each as a PNG file** in `.tmp/qa-tier-N/screenshots/`
  - console errors/warnings via `list_console_messages`
  - Lighthouse snapshot audit (accessibility/best practices) where a tier touches a11y
- Output: notes + screenshots in `.tmp/qa-tier-N/`.

**Pass C — Visual Audit (vision subagent)**
> Why: the driving model (`opencode/deepseek-v4-flash-free`) is **text-only** and cannot read images, so screenshots must be audited by a vision-capable model separately.
- Agent: `general` subagent pinned to **`opencode/mimo-v2.5-free`** (free, accepts image attachments).
- Read every PNG in `.tmp/qa-tier-N/screenshots/`. For each, check the tier's visual checklist (post-reboot for tiers ≥5 and Tier 1 re-tint: **only** red-pencil accent `#C2410C`/`#D1552E` — no stray viridian `#0CCAB1`/purple `#7C6FD4`/`#8E82E0`; vellum `#F6F2E7` light AND Prussian `#0A1628` dark both render; grid ≤6% opacity (subliminal, not dominant); fold-marks crisp; hairline 1px edges, no soft glows; hard-offset shadows; Space Grotesk + Newsreader rendering; red-pencil fill text ≥4.5:1 AA).
- Also flag regressions the text passes can't see: font/metrics collapse, contrast, alignment, dead white-on-accent.
- Output: `.tmp/qa-tier-N/visual-review.md`, ends with a one-line verdict.

**Orchestration**
- Dispatch all three passes concurrently (one `opencode serve` + two/three attached `opencode run` workers, or the Task tool's general agents) so code review, browser testing, and visual audit overlap.
- Pass B must finish its screenshot capture before Pass C can start; otherwise they overlap freely.
- On any failure: fix, re-run the affected pass, and only then proceed to the next tier.
- Kill the serve worker and keep `.tmp/` uncommitted after each tier.

### 4.2 Baseline Checks (all passes gate on)

- `npm run build` (tsc + vite) — no type errors
- `npm run lint` (oxlint) — no new warnings

---

## 5. Open Items / Decisions Log

- [ ] Confirm font loading approach (Google Fonts CSS vs self-hosted) for Space Grotesk + Newsreader at Tier 4/5.
- [ ] Confirm default theme: **light (vellum) default, dark (Prussian) via toggle** — committed in §2.1; implementation tracked in Tier 5 items 24a/24b (`index.css` base inversion + `ThemeToggle.tsx` default/meta-hex).
- [ ] Confirm red-pencil hover/tint values for dark (`#E85D2F` hover, `rgba(209,85,46,0.14)` tint) — verify AA in Pass C.
- [ ] Streaming: decide whether real SSE replaces non-streaming path or exists as fallback (Tier 2.12).
- [ ] `incomplete: true` badge design (subtle warning dot + text) — flag from tier2 Open Question 2.

---

## Progress Summary

Each tier gates on: build + lint green, Pass A code review verdict clean, Pass B Chrome MCP test clean (no console errors, screenshots captured), Pass C visual audit clean (vision-model review of `.tmp/qa-tier-N/screenshots/`), Lighthouse a11y where applicable.

- **Tier 0**: `[x]` **complete** — dead code deleted (mocks ×7, App.css, EvidenceCard, assets, clsx); console.logs removed; `/process` URL → relative via Vite proxy; store-layer `any` eliminated (liveReferences→`Reference[]`, typed `ChatResponse`/flashcards, removed dead `fetchSummary`); `Reference`/`RetrievedChunk`/`RetrievedImage`/`ChatResponse`/`ProcessEvent`/`Flashcard` moved to `src/types/index.ts`. Build ✓ lint ✓ Pass A ✓ Pass B ✓ (artifacts in `.tmp/review-tier-0.md`, `.tmp/qa-tier0/`). *(Pass C visual audit added after Tier 0 was completed; retro-apply to `.tmp/qa-tier0/` screenshots if a visual baseline is wanted.)*
- **Tier 1**: `[x]` **complete (PRE-RETINT)** — `@theme` expanded (`--color-nph`, `--shadow-ev1/2/3`, `--text-*` ramp, `--ds-focus-ring`, `--radius-*`); accent swapped purple → Electric Viridian `#0CCAB1`; status-dot palette pinned per DESIGN.md (`#398E4A`/`#FF990A`/`#E5484D`/`#0062D1`/`#7820BC`); all hardcoded `#8E82E0` hovers + inline `rgba(…)` shadows → tokens; gradient dividers removed; `color-scheme` + `theme-color` meta + `prefers-reduced-motion` added. Build ✓ lint ✓ (no new warnings). **Reboot note: viridian tokens + dark-default are superseded — Tier 5 re-tints to red-pencil + flips default to vellum light.** Pass A ✓ (review in `.tmp/review-tier-1.md`), Pass B ✓ (browser test in `.tmp/q-tier1/review-tier-1-passB.md`, Lighthouse a11y 76 — muted `nt4` grays pre-existing, not Tier-1), Pass C ✓ (MiMo vision audit in `.tmp/q-tier1/review-tier-1-passC.md`).
- **Tier 2**: `[ ]` not started
- **Tier 3**: `[ ]` not started
- **Tier 4**: `[ ]` not started
- **Tier 5**: `[ ]` not started (Architect's Sketchbook theme layer — primary reboot work)
