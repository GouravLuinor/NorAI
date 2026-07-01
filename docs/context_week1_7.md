# NorAI — Project Context (Weeks 1–7)

## Project Vision

NorAI is an AI-powered Lecture Revision Assistant that transforms long educational videos into structured learning material.

Instead of simply answering questions about transcripts, NorAI first converts lectures into structured educational knowledge, enabling high-quality study notes, revision notes, quizzes, flashcards, and an intelligent tutor.

The philosophy is:

Video

↓

Understanding

↓

Knowledge

↓

Learning

Every stage of the pipeline is modular and independently improvable.

---

# Overall Pipeline (Weeks 1–7)

```
Video

↓

Ingestion

↓

Transcription

↓

Chunking

↓

Knowledge Extraction

↓

Frame Extraction

↓

Scene Detection

↓

Visual Knowledge Extraction

↓

Knowledge Merging
```

The output after Week 7 is a collection of multimodal knowledge objects.

Everything built afterwards (study notes, revision notes, assessments, tutor) consumes these objects.

---

# Week 1 — Video Ingestion

Goal

Support multiple lecture sources.

Completed

- Local video ingestion
- YouTube download support
- Google Drive support
- Metadata generation
- Automatic directory creation

Output

```
outputs/

video.mp4

metadata.json
```

Metadata contains

- lecture title
- duration
- source type
- source URL
- upload time

---

# Week 2 — Transcription

Goal

Convert lectures into accurate timestamps.

Technology

- Faster Whisper

Completed

- Speech transcription
- Timestamp generation
- Segment generation
- Speaker-independent transcription

Output

```
outputs/transcripts/

transcript.json
```

Each segment contains

```
start

end

text
```

---

# Week 3 — Chunking

Goal

Convert transcript segments into semantic lecture chunks.

Instead of fixed token windows,

chunks preserve educational continuity.

Completed

- Timestamp-aware chunking
- Semantic grouping
- Metadata preservation
- Stable chunk IDs

Output

```
outputs/chunks/

chunk_0.json

...

chunk_n.json
```

Each chunk contains

```
chunk_id

timestamps

text

segment_ids
```

Chunk IDs become the backbone of every later stage.

---

# Week 4 — Knowledge Extraction

Goal

Convert raw transcript chunks into educational knowledge.

Instead of retrieving transcript text,

the system retrieves structured knowledge.

Each chunk is sent to an LLM.

Generated information includes

- topic
- lecture notes
- concepts
- important information
- inferred knowledge

Knowledge Schema

```json
{
    "chunk_id": 8,
    "topic": "...",
    "lecture_notes": [...],
    "concepts": [...],
    "important_information": [...],
    "inferred_knowledge": [...]
}
```

Output

```
outputs/knowledge/

chunk_0.json

...

chunk_n.json
```

---

# Week 5 — Visual Understanding

Goal

Understand what appears on lecture slides.

Pipeline

Video

↓

Keyframe Extraction

↓

Scene Detection

↓

Vision LLM

Completed

- Keyframe extraction
- Scene change detection
- Screenshot selection
- Visual description generation

Each visual object contains

- screenshot path
- OCR information
- diagrams
- equations
- code
- visual explanations

Visual Schema

```json
{
    "chunk_id": 8,
    "screenshots": [...],
    "visual_notes": [...],
    "important_visual_information": [...]
}
```

Output

```
outputs/visual/

chunk_0.json

...

chunk_n.json
```

---

# Week 6 — Multimodal Knowledge Merging

Goal

Combine transcript understanding and visual understanding into unified educational objects.

Pipeline

Knowledge Object

+

Visual Object

↓

Merged Knowledge Object

Completed

- Topic merging
- Concept merging
- Screenshot integration
- Visual note integration
- Unified schema generation

Merged Object Schema

```json
{
    "chunk_id": 8,
    "topic": "...",
    "lecture_notes": [...],
    "visual_notes": [...],
    "concepts": [...],
    "important_information": [...],
    "inferred_knowledge": [...],
    "screenshots": [...]
}
```

Output

```
outputs/merged_objects/

chunk_0.json

...

chunk_n.json
```

---

# Architecture Principles

The pipeline intentionally separates every educational stage.

Instead of one large prompt,

NorAI builds educational knowledge incrementally.

```
Transcript

↓

Knowledge Extraction

↓

Visual Extraction

↓

Knowledge Merging
```

Each stage can be independently improved without redesigning the entire system.

---

# Design Decisions

## Structured Knowledge

The system never retrieves raw transcripts directly.

Instead, retrieval operates over structured educational knowledge.

---

## Modular Pipeline

Each processing stage has a single responsibility.

Examples

- transcription
- chunking
- knowledge extraction
- visual extraction
- merging

This makes debugging significantly easier.

---

## Timestamp Preservation

Every object preserves timestamps from the original lecture.

This enables

- screenshot alignment
- future video jumping
- citation support

---

## Vision-First Philosophy

Lecture slides often contain information never spoken aloud.

Visual understanding is treated as first-class educational knowledge rather than an optional enhancement.

---

## Unified Knowledge Objects

All downstream educational pipelines consume a single merged object format.

This removes the need for later stages to understand transcripts or screenshots separately.

---

# Output Produced After Week 7

```
outputs/

├── transcripts/
├── chunks/
├── knowledge/
├── visual/
└── merged_objects/
```

The merged objects are the final output of the knowledge generation pipeline.

Everything built afterwards—including study notes, revision notes, assessments, AI tutor, and frontend—uses these merged objects as its primary data source.

---

# Current Status (End of Week 7)

Completed

✅ Video Ingestion

✅ Transcription

✅ Chunking

✅ Knowledge Extraction

✅ Visual Understanding

✅ Knowledge Merging

The knowledge generation pipeline is complete.

The next stage begins the Educational Content Generation pipeline, starting with lecture outline generation and chapter building.