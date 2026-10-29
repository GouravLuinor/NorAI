# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

University students in English-speaking western markets, studying from recorded lectures (class recordings, university lectures on YouTube, online courses). The primary moment is the **exam crunch**: a student has hours of lecture video and limited time, and needs something they can revise from now. Secondary users (weekly course keepers, self-learners) are supported but not optimized for first.

Visitors usually arrive cold, from search, an AI answer engine, or a link a classmate shared, and decide within a minute whether to try it.

## Product Purpose

NorAI turns one lecture video into a complete study set: chapter-by-chapter study notes, a revision sheet, a quiz, flashcards with spaced repetition, a mind map, and an AI tutor that answers only from that lecture. Success means a student who processes one lecture comes back, both to study it again (review cards, retake missed questions, ask the tutor) and to process the next one.

## Positioning

Everything is grounded in the student's own lecture. The tutor answers from the transcript and slides of that one video, cites the timestamp, and links back to the moment in the video. It says when the lecture does not cover something instead of filling the gap from the open web. Notes follow the order the professor taught and pull the slides that mattered out of the video.

## Operating Context

- Input is a YouTube link or an uploaded video file (MP4, MOV, MKV, AVI, WebM). The tool shows the length and the lecture-minutes it will use before starting.
- Processing takes a few minutes and runs server-side; the user can close the tab.
- Study happens in one workspace: notes / revision / quiz / guide / mind map beside the tutor and the lecture video. It is used on laptops and, often, phones.
- Lectures live in a personal library and can be grouped into courses and shared by link.
- Three permanent demo lectures can be opened without an account.

## Capabilities and Constraints

- **Free-only launch:** every account gets 60 lecture-minutes every 30 days (`NORAI_FREE_MINUTES`), with every feature included. There is no paid tier at launch; billing code exists but stays hidden.
- **Runs on free tiers:** Supabase free tier (auth + DB) and the Gemini free-tier API (~500 requests/day per key, shared by processing and the tutor). Anything that spends AI calls needs a budget guard.
- Works best on English-language lectures.
- Deferred, not to be implied as existing: analytics, transactional email (notifications), legal pages (privacy, terms), paid plans, a production domain.

## Brand Commitments

- Product name: **NorAI** (fixed).
- Tutor persona: **Nora** (fixed).
- Voice: plain, specific, honest about limits; US English.

## Evidence on Hand

- Three processed demo lectures (neural networks, economics, open-weights models), openable without an account. These are the only proof.
- Product screenshots: `frontend/public/landing/` (notes + tutor, quiz, mobile tutor), `frontend/public/og.jpg`.
- No testimonials, user counts, university, or press mentions exist. Never fabricate them.

## Product Principles

1. **Time to "I can study this" beats everything.** In the exam crunch, every screen should move the student toward studying their lecture, fast.
2. **Grounded and honest.** Show where every answer comes from; never claim the product does more than it does.
3. **Give the reason to come back.** Surface what to study next (due cards, missed questions, the next chapter) rather than an empty form.
4. **Free means free.** No upsell pressure, dark patterns, or fake scarcity.
5. **Work on a phone.** Students revise on the bus; every study surface must hold up at phone width.

## Accessibility & Inclusion

Keyboard operable, visible focus, WCAG AA contrast in light and dark themes, respects reduced motion. Long-form reading (notes) must stay comfortable at small sizes.
