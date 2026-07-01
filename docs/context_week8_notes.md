# NorAI — Week 8 Context (Educational Content Generation)

## Overview

Week 8 transforms NorAI from a **knowledge extraction pipeline** into a complete **educational content generation system**.

Instead of retrieving merged knowledge objects directly, the system first converts them into structured learning resources designed for different stages of studying.

The educational pipeline now produces:

- Study Notes
- Revision Notes
- Assessments (Quiz Bank)

These resources later become the primary knowledge base for the AI Tutor.

---

# Overall Educational Pipeline

```
Merged Knowledge Objects

↓

Lecture Outline Generation

↓

Chapter Builder

↓

Study Notes Generation

↓

Screenshot Selection

↓

Study PDF Builder

↓

Revision Notes Generation

↓

Revision Metadata

↓

Revision PDF Builder

↓

Assessment Generation
```

The output is a complete set of educational artifacts generated from a single lecture.

---

# Step 1 — Lecture Outline Generation

## Goal

Organize the lecture into meaningful educational chapters.

Rather than splitting content arbitrarily, the LLM analyzes the entire lecture and produces a structured outline.

Each chapter contains:

- chapter title
- start chunk
- end chunk
- focus concepts

Example

```json
{
  "chapter_id": 3,
  "title": "Querying a Segment Tree",
  "start_chunk": 10,
  "end_chunk": 15,
  "focus_concepts": [
    "Range Query",
    "Divide and Conquer",
    "Identity Element"
  ]
}
```

Key improvements:

- Chapter ownership
- Reduced overlap
- Better concept grouping
- Global lecture awareness

Output

```
outputs/notes/

lecture_outline.json
```

---

# Step 2 — Chapter Builder

## Goal

Aggregate merged knowledge objects into chapter objects.

The builder combines all chunk-level information belonging to the same chapter.

Each chapter contains:

- topics
- concepts
- lecture notes
- visual notes
- screenshots
- important information
- inferred knowledge

Chapter Schema

```json
{
    "chapter_id": 1,
    "title": "...",
    "chunk_ids": [...],
    "concepts": [...],
    "lecture_notes": [...],
    "visual_notes": [...],
    "screenshots": [...]
}
```

Output

```
outputs/chapters/

chapter_1.json

...

chapter_n.json
```

---

# Step 3 — Study Notes Generation

## Goal

Generate high-quality educational study notes.

Unlike textbook generation, the objective is to create structured notes that are concise, readable, and suitable for learning.

Important prompt improvements:

- Entire lecture outline included in context.
- Chapter ownership enforced.
- Reduced duplication across chapters.
- Previous/next chapter awareness.
- Educational writing style.
- Technical accuracy prioritized.

Generated notes include:

- Core Concepts
- Detailed Explanation
- Important Observations
- Applications
- Key Takeaways

Output

```
outputs/notes/

chapter_1.md

...

chapter_n.md
```

---

# Step 4 — Screenshot Selection

## Goal

Choose only the most educational screenshots.

Instead of inserting every extracted frame, a vision model reviews all candidate screenshots for each chapter.

Selection criteria:

- diagrams
- algorithms
- formulas
- handwritten explanations
- code snippets
- examples

Rejected:

- instructor-only frames
- transition slides
- decorative content
- duplicates

Each selected screenshot stores:

```json
{
    "path": "...",
    "reason": "...",
    "section": "...",
    "importance": 10
}
```

Output

```
outputs/screenshots/selected/

chapter_1_screenshots.json

...

chapter_n_screenshots.json
```

---

# Step 5 — Study PDF Builder

## Goal

Transform Markdown study notes into professionally formatted study material.

Unlike direct Markdown-to-PDF conversion, the PDF builder creates educational pages with:

- rich typography
- section hierarchy
- tables
- highlighted callouts
- embedded screenshots
- consistent spacing

Screenshots are inserted near their corresponding explanations.

Output

```
outputs/notes/

study_notes.pdf
```

---

# Step 6 — Revision Notes Generation

## Goal

Compress study notes into concise revision sheets.

These are designed for quick revision before exams.

Characteristics:

- highly condensed
- concept-focused
- minimal explanations
- formulas
- complexity tables
- algorithm summaries
- comparison tables

Output

```
outputs/revision/

revision_chapter_1.md

...

revision_chapter_n.md
```

---

# Step 7 — Revision Metadata

## Goal

Generate structured metadata describing each revision chapter.

Metadata enables:

- search
- indexing
- tutor retrieval
- future adaptive learning

Example

```json
{
    "chapter_id": 2,
    "title": "...",
    "concepts": [...],
    "difficulty": "...",
    "keywords": [...]
}
```

Output

```
outputs/revision/

revision_metadata.json
```

---

# Step 8 — Assessment Generation

## Goal

Automatically generate educational assessments from study notes.

Question types:

- Multiple Choice
- True / False
- Fill in the Blank
- Short Answer
- Conceptual
- Complexity
- Scenario-Based

Each question includes:

- difficulty
- concepts
- explanation
- answer

Example

```json
{
    "question_id": 5,
    "chapter_id": 2,
    "type": "MCQ",
    "difficulty": "Medium",
    "question": "...",
    "answer": "...",
    "explanation": "..."
}
```

Output

```
outputs/assessment/

assessment_chapter_1.json

...

assessment.json
```

---

# Educational Design Principles

## Global Lecture Awareness

Every chapter receives the complete lecture outline.

This significantly reduces duplication and improves chapter cohesion.

---

## Chapter Ownership

Each concept belongs primarily to one chapter.

Other chapters may reference it briefly but avoid full re-explanations.

---

## Multiple Learning Resources

Instead of one document, NorAI generates multiple educational resources optimized for different purposes.

Study Notes

↓

Deep learning

Revision Notes

↓

Quick review

Assessments

↓

Active recall

---

## Screenshot-Grounded Learning

Educational screenshots are treated as first-class learning resources.

Only the most valuable visuals are included.

---

## Modular Educational Pipeline

Each educational artifact is generated independently.

This allows:

- prompt improvements
- model replacement
- regeneration
- debugging

without affecting other stages.

---

# Output Produced After Week 8

```
outputs/

├── chapters/
├── notes/
│   ├── lecture_outline.json
│   ├── chapter_1.md
│   ├── ...
│   └── study_notes.pdf
│
├── revision/
│   ├── revision_chapter_1.md
│   ├── ...
│   └── revision_metadata.json
│
├── assessment/
│   ├── assessment_chapter_1.json
│   ├── ...
│   └── assessment.json
│
└── screenshots/
    └── selected/
```

---

# Current Status (End of Week 8)

Completed

✅ Lecture Outline Generation

✅ Chapter Builder

✅ Study Notes Generation

✅ Screenshot Selection

✅ Study PDF Builder

✅ Revision Notes Generation

✅ Revision Metadata

✅ Assessment Generation

The educational content generation pipeline is complete.

The next stage begins the **Interactive AI Tutor**, where these generated educational artifacts become the primary retrieval knowledge base for conversational learning.