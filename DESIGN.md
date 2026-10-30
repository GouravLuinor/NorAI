---
name: NorAI — The Stacks
description: Lecture study workspace designed as university library stack signage.
colors:
  ground: "#FBFBF8"
  sheet: "#FFFFFF"
  sheet-muted: "#F2F3EF"
  sheet-sunken: "#E6E8E2"
  ink: "#16181A"
  ink-secondary: "#3F4447"
  ink-muted: "#5D6266"
  library-green: "#1F4D3F"
  library-green-hover: "#2A6352"
  library-green-deep: "#163A2F"
  brass: "#C8932E"
  brass-soft: "#F6EBD2"
  brass-ink: "#8A5F12"
  rail: "#1F4D3F"
  rail-deep: "#163A2F"
  rail-ink: "#EAF1EC"
  rail-muted: "#A9C4B6"
  rail-brass: "#E7B04A"
  zone-notes: "#1F4D3F"
  zone-revision: "#2F6FB2"
  zone-quiz: "#B8432F"
  zone-cards: "#6B4FA0"
  zone-map: "#8A5F12"
  success: "#1F7A45"
  warning: "#A3680F"
  danger: "#B3261E"
  info: "#2F6FB2"
  dark-ground: "#131614"
  dark-sheet: "#1A1E1C"
  dark-ink: "#E6E8E3"
typography:
  display:
    fontFamily: "Literata, Georgia, 'Times New Roman', serif"
    fontSize: "2.125rem"
    fontWeight: 600
    lineHeight: 1.15
  headline:
    fontFamily: "Literata, Georgia, 'Times New Roman', serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
  title:
    fontFamily: "Atkinson Hyperlegible, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Atkinson Hyperlegible, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Atkinson Hyperlegible, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.02em"
  mono:
    fontFamily: "'Atkinson Hyperlegible Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
rounded:
  sm: "3px"
  md: "6px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.library-green}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16px"
  shelf-mark:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "3px 6px"
---

# Design System: NorAI — The Stacks

## Overview

**Creative North Star: "The university library at closing time."**

NorAI borrows its visual grammar from the physical library: green stack-signage rails, white spine labels, call numbers, brass current-item markers, and reading-room paper. The workspace should feel like a place built for sustained study, not a dashboard built for monitoring. Navigation is signage; content is a sheet on the desk; the tutor is a librarian sitting beside it.

The system is flat, typographic, and quietly institutional. Structure comes from rules, tone shifts, and the rail rather than from cards floating in space. Color is functional first: library green carries navigation and primary action, brass marks "you are here" and citations, and one zone color identifies each study mode. The overall impression is calm, legible, and slightly analog — a place that respects the student's time and attention.

**Key Characteristics:**
- Library green signage plus warm paper and brass.
- Literata for reading, Atkinson Hyperlegible for UI, Mono for call numbers.
- Square-ish geometry (3–6px), hairline borders, soft low elevation.
- One color per study zone; brass reserved for current position and cited moments.
- Light "reading room" and dark "after hours" themes with equal contrast.

## Colors

A warm-neutral paper ground, deep library green, and a single brass accent. Status hues are muted and used only for state, never decoration.

### Primary
- **Library Green** (`#1F4D3F`): primary buttons, links, active navigation, the rail, focus rings, and shelf-mark call numbers. It reads as institutional signage, not corporate blue.
- **Green Hover** (`#2A6352`): hover state for green fills; **Green Deep** (`#163A2F`) is the rail's shadow side.

### Secondary
- **Brass** (`#C8932E`): the current chapter marker, cited passages, the tutor avatar, and "you are here" states. It should feel like a small metal label, not a highlight wash.
- **Brass Soft** (`#F6EBD2`) is its tinted ground; **Brass Ink** (`#8A5F12`) is the AA-contrast text form.

### Tertiary
- **Study Zones:** Notes `#1F4D3F`, Revision `#2F6FB2`, Quiz `#B8432F`, Cards `#6B4FA0`, Map `#8A5F12`. Each mode owns one hue; never mix them inside a single panel.

### Neutral
- **Ground** `#FBFBF8` is the page; **Sheet** `#FFFFFF` is content; **Sheet Muted** `#F2F3EF` is secondary panels; **Sheet Sunken** `#E6E8E2` is tracks and dividers.
- **Ink** `#16181A` for body, **Ink Secondary** `#3F4447`, **Ink Muted** `#5D6266` for labels and metadata.
- **Borders** are ink at 12% (`--color-bdr`) or 20% (`--color-bdr2`), never gray-blue.
- **Dark theme:** ground `#131614`, sheet `#1A1E1C`, ink `#E6E8E3`, green `#8FD1B0`, brass `#E7B04A`. The rail stays dark green.

### Named Rules
**The One Accent Rule.** Brass is for the current item and citations only; it never fills a whole panel or decorates a heading.
**The Zone Rule.** A study mode's color appears on its mode control, its shelf marks, and its accents — nowhere else on the screen.
**The Ink Border Rule.** Borders are translucent ink, not a second neutral. If a border needs to be more visible, increase alpha, not blueness.

## Typography

**Display Font:** Literata (with Georgia, Times New Roman)
**Body Font:** Atkinson Hyperlegible (with system sans)
**Label/Mono Font:** Atkinson Hyperlegible Mono

**Character:** A reading serif for the lecture itself, paired with a hyperlegible grotesque for controls and a mono for call numbers. The pairing is scholarly but not precious; the mono gives every timestamp the authority of a catalog label.

### Hierarchy
- **Display** (600, 2.125rem, 1.15): document H1s and the landing hero; Literata only.
- **Headline** (600, 1.5rem, 1.25): chapter titles and section heads inside notes.
- **Title** (700, 1.125rem, 1.3): panel headings, card titles, and mode names.
- **Body** (400, 0.9375rem, 1.55): UI copy; 0.875–1rem is the working range. Notes use Literata at 1.0625rem with a 65–75ch measure.
- **Label** (700, 0.75rem, 0.02em): sentence-case section labels such as "Sources from this lecture". No uppercase kickers.
- **Mono** (600, 0.75rem, tabular): timestamps, call ranges, counts, and shelf marks.

### Named Rules
**The 12px Floor Rule.** Nothing renders below 12px. Small steps in the token ramp resolve to 12px or 13px rather than shrinking further.
**The Reading Serif Rule.** Literata is for content the student reads at length; never set controls, labels, or navigation in it.
**The Shelf-Mark Rule.** Any timestamp, chapter range, or citation that can seek the video is set in mono and carries the shelf-mark treatment.

## Layout

The workspace is a three-part reading desk: a fixed green rail (chapter navigation), a flexible document sheet (notes/revision/quiz/cards/map), and a right-hand tutor/video panel. The rail is the only permanently dark surface in light mode. Panels are separated by 1px ink hairlines, not gaps and shadows.

- Container gutters: 16px on phones, 24px on tablets, 32px on desktop.
- Study surfaces cap their reading measure at roughly 68ch; the document pane scrolls independently.
- Below 1280px the toolbar collapses tools to icons; below 1024px the tutor moves into the doc tab; below 768px the rail becomes a sheet-level chapter selector.
- Spacing rhythm is 4/8/16/24/32. Cards use 16px padding by default; dense list rows use 8–12px.
- The landing page runs full-bleed stack-sign bands with centered content capped near 1120px.

## Elevation & Depth

Depth is tonal and structural first. Surfaces sit on the paper ground with a hairline ink border; the rail is a solid plane. Shadows are soft and low (`--shadow-ev1` = 1px contact + 4% ambient, `--shadow-ev2` = 4–12px, `--shadow-ev3` = 12–32px) and appear on interactive or floating objects, not on every card. There are no hard offset shadows, grid paper, noise, or fold marks.

### Shadow Vocabulary
- **ev1** (`0 0 0 1px rgba(22,24,26,0.10), 0 1px 2px rgba(22,24,26,0.04)`): resting buttons and small controls.
- **ev2** (`0 1px 2px rgba(22,24,26,0.06), 0 4px 12px rgba(22,24,26,0.06)`): primary buttons, popovers, the video dock.
- **ev3** (`0 2px 4px rgba(22,24,26,0.06), 0 12px 32px rgba(22,24,26,0.12)`): dialogs and the command palette.
- Dark theme keeps the same geometry with black-based shadows and a 1px light rim.

### Named Rules
**The Flat-At-Rest Rule.** A static card has a border, not a shadow. Shadows respond to state or float above the page.
**The Rail-Is-A-Plane Rule.** The rail never floats, blurs, or gradients; it is painted signage.

## Shapes

Corners are tight and institutional: 3px for shelf marks and tags, 6px (`--radius-md`) for cards, inputs, and buttons. Pills are reserved for status chips and the theme toggle. Borders are 1px, or 1.5px on shelf marks. Icons are 16–20px, stroke-based, and inherit currentColor.

The signature shape is the **shelf mark**: a small white label with a stacked call number, a 1.5px currentColor border, and a 1px bottom rule that reads as a physical label holder. As a button it presses down 1px and drops its rule.

## Components

### Buttons
Green fill for primary action, hairline outline for secondary, borderless ghost for tertiary. All are 6px radius, use Atkinson Hyperlegible, and press down 1px on active. Focus is a two-ring green halo. Disabled states drop to 60% opacity without changing hue.

### Inputs
White sheet, 1px ink border, 6px radius, 12px vertical padding. Focus uses the green ring; placeholders use Ink Muted. The tutor composer is a bordered sheet with a dedicated Ask button, not a floating pill.

### Cards
White sheet, 1px `--color-bdr`, 6px radius, 16px padding, no resting shadow. A left 2px zone-colored border marks a mode-specific card. Headers are a bold sentence-case label with an optional icon.

### Shelf Mark
The signature component. Mono, tabular numerals, 3px radius, white ground, 1.5px ink border, 1px bottom rule. Variants: default, inline (green text, no rule), current (brass fill, no rule), and rail (transparent until hover). It is a button whenever it can seek the video.

### Rail
Full-height library-green column. Chapter rows are call ranges; the current row hangs on a white sign with a brass shelf mark. The rail remaps surface and ink tokens so standard buttons, selects, and the theme toggle read as signage without variants.

### Tutor
Nora's avatar is a brass disc with dark ink initials. Answers use the body face; citations use inline shelf marks. The "Sources from this lecture" list is open by default and uses the same shelf-mark grammar as the rail.

### Landing
Stack-sign hero using the demo lecture's real chapter ranges, zone-coded output cards, a demo catalogue with call codes, and a green closing band. No stock photography, no fabricated social proof.

## Do's and Don'ts

### Do
- Use library green for navigation and primary action; use brass for the current item and citations.
- Set timestamps, chapter ranges, and citations in mono with the shelf-mark treatment.
- Keep study modes color-coded and visually separate.
- Use Literata for long-form reading and Atkinson Hyperlegible for every control.
- Prefer hairline ink borders and tone shifts over shadows and rounded floating cards.
- Hold the 12px type floor and the 68ch reading measure.

### Don't
- Don't reintroduce grid paper, noise, fold marks, hard offset shadows, or red-pencil annotations.
- Don't use uppercase mono kickers; labels are sentence case.
- Don't use brass as a general highlight or fill large areas with it.
- Don't mix zone colors within one panel or use status red/green for decoration.
- Don't set UI or navigation in Literata, or body copy below 12px.
- Don't add stock imagery, invented testimonials, user counts, or university affiliations.
