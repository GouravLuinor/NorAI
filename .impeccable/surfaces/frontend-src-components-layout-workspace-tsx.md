---
version: 1
slug: "frontend-src-components-layout-workspace-tsx"
primary_target: "frontend/src/components/layout/Workspace.tsx"
related_targets: ["frontend/src/pages/LandingPage.tsx","frontend/src/pages/UploadPage.tsx"]
---

# Surface brief: NorAI app shell + study workspace (whole-app world)

Scope: the one visual world for every NorAI surface. First surface: the study workspace (Operate). It reaches the landing and pricing (Persuade), auth, upload/study home, processing and share pages.
Audience/job: western university students in exam crunch turning a lecture into something they can revise from now; they return for due flashcards, missed quiz questions and the next chapter.
Constraints: PRODUCT.md (free only, no invented proof, Nora/NorAI fixed). Light and dark themes, phone width, reduced motion.

## Direction contract

THESIS: Every part of a lecture gets a shelf mark you can walk straight to. Refuses the category default of grey sidebar + indigo accent + rounded cards, and the cream-notebook / mono-spec-label looks it replaces.

OWN-WORLD: University stack signage. Library-green shell (#1F4D3F) carries navigation as range signs; reading happens on spine-label white (#FBFBF8) in near-black ink. Brass (#C8932E) marks the current item. Each study mode owns one zone colour (notes green, revision blue #2F6FB2, quiz brick #B8432F, flashcards violet #6B4FA0, mind map brass). Flat colour only: no grain, grid paper, noise or fold marks. Type: Atkinson Hyperlegible for UI, Atkinson Hyperlegible Mono for shelf marks and figures, Literata for notes and headings.

STORY: The student sees where they are (chapter range), reads notes whose every section carries a shelf mark, asks Nora and gets answers whose citations are the same shelf marks; clicking any mark walks the video there. They leave knowing what is due.

FIRST VIEWPORT: Workspace at 1440: 268px green rail (wordmark, lecture, chapters as call ranges with the current one on a white sign and brass label, due-today block at the foot); centre notes on white under a zone-coloured mode bar, Literata 34px title, sections each led by a 72px spine label; 380px white tutor column with Nora, the question, an answer with inline shelf marks, and the ask box at the bottom. Primary action: Ask.

FORM: The Stacks: university library stack signage and spine labels; position 4 of 7 on the grounded list; seed key 420854a4. Signature move: shelf marks (stacked call-number labels) on chapters, sections, citations and timestamps, all seeking the video. Raises: zone colour per study mode (acetate), flat colour only (zoo), destructive actions stand alone (console), strict tabular figures (ikeda). Motion: a label press settles 1px; seeks scroll and highlight the target section once; nothing else animates.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
