# NorAI - Project Progress

## Project Vision

NorAI is an AI-powered Lecture Revision Assistant that transforms long educational videos into an intelligent study companion.

Pipeline:

Video
→ Audio Extraction
→ Transcription
→ Chunking
→ Knowledge Extraction
→ Visual Understanding
→ Embeddings
→ Retrieval
→ Notes Generation
→ Quiz Generation
→ AI Revision Assistant

---

# Current Architecture

Video
↓
Ingestion
↓
Audio Extraction
↓
Transcription
↓
Chunking
↓
Knowledge Extraction
↓
Visual Knowledge Extraction
↓
Merged Knowledge Objects
↓
Embeddings
↓
ChromaDB
↓
Retrieval
↓
Question Answering

---

# Week 1 - Ingestion Pipeline ✅

Completed:

* Local video ingestion
* YouTube video ingestion
* Google Drive video ingestion
* Audio extraction using FFmpeg
* Metadata generation
* Duration tracking
* Error handling
* File validation

Output:

* video.mp4
* audio.mp3
* metadata.json

---

# Week 2 - Transcription Pipeline ✅

Completed:

* Faster-Whisper integration
* Timestamped transcripts
* TXT transcript export
* JSON transcript export
* Metadata integration
* Language detection
* Long lecture validation

Output Schema:

```json
{
  "source": {...},
  "segments": [...]
}
```

Notes:

* No chunking performed during transcription
* Raw Whisper segments preserved

---

# Week 3 - Chunking Pipeline ✅

Completed:

* Transcript loading
* Segment-based chunking
* Timestamp preservation
* Chunk metadata schema
* Segment tracking
* Duration tracking
* JSON chunk export

Chunk Schema:

```json
{
  "chunk_id": 0,
  "start": 0.0,
  "end": 57.4,
  "duration": 57.4,
  "segment_start": 0,
  "segment_end": 14,
  "segment_ids": [...],
  "text": "..."
}
```

Validation:

* 518 transcript segments
* 35 generated chunks

---

# Week 4 - Embeddings & Retrieval ✅

Completed:

* Sentence Transformers integration
* all-MiniLM-L6-v2 embeddings
* Embedding generation
* ChromaDB integration
* Metadata storage
* Semantic retrieval
* Retrieval validation

Validation Queries:

* What is a segment tree?
* Why do we use segment trees?
* Range query problem
* Full binary tree
* O(log n)

Results:

* Relevant chunks retrieved successfully
* Non-existent concepts correctly produced low-confidence matches

Current Flow:

Question
↓
Embedding
↓
Chroma Search
↓
Top-K Chunks

Working successfully.

---

# Week 5 - Question Answering (RAG) ✅

Goal:

Question
↓
Retrieval
↓
Context Construction
↓
LLM
↓
Grounded Answer

Completed:

* Gemini API integration
* Context assembly from retrieved chunks
* Prompt engineering
* Source citation generation
* Answer generation
* Timestamp-aware retrieval
* Retrieval confidence analysis

Features:

* Grounded answers from lecture content
* Source chunk tracking
* Timestamp references
* Evidence display

Example Output:

```json
{
  "question": "...",
  "answer": "...",
  "sources": [...]
}
```

Improvements Added:

* Human-readable timestamps
* Source snippet display
* Better citation formatting

---

# Week 6 - Knowledge Extraction Pipeline ✅

Goal:

Transcript
↓
Knowledge Object

Problem:

Raw transcripts are difficult to use directly for notes, quizzes, and revision.

Solution:

Transform transcript chunks into structured educational knowledge.

Completed:

* Gemma 4 26B integration
* Structured knowledge extraction
* JSON schema generation
* Parallel processing
* Retry handling
* Knowledge object storage

Knowledge Object Schema:

```json
{
  "chunk_id": 0,
  "topic": "...",
  "transcript": "...",
  "lecture_notes": "...",
  "key_points": [...],
  "concepts": [...],
  "inferred_knowledge": [...],
  "external_knowledge": {...}
}
```

Capabilities:

* Topic extraction
* Concept identification
* Educational note generation
* Key point extraction
* Inferred learning generation
* External supporting knowledge

Validation:

* 35 chunks processed successfully
* Parallel extraction implemented
* Automatic retry mechanism added

Output:

```text
outputs/objects/
├── chunk_0.json
├── chunk_1.json
...
├── chunk_34.json
```

---

# Week 7 - Visual Understanding Pipeline ✅

Goal:

Lecture understanding should not depend solely on transcripts.

Many lectures contain:

* Whiteboard drawings
* Slides
* Diagrams
* Mathematical derivations
* Visual explanations

Solution:

Extract knowledge from screenshots and merge it with transcript understanding.

---

## 7.1 Frame Extraction ✅

Completed:

* Video frame extraction
* H.264-compatible processing
* Timestamp preservation
* Frame metadata generation

Output:

```text
outputs/screenshots/raw/
```

---

## 7.2 Scene Detection ✅

Completed:

* Visual similarity comparison
* Duplicate frame filtering
* Keyframe selection
* Metadata generation

Output:

```text
outputs/screenshots/keyframes/
```

Results:

* 551 extracted frames
* 101 educational keyframes selected

---

## 7.3 Chunk ↔ Screenshot Mapping ✅

Completed:

* Timestamp alignment
* Chunk-to-screenshot mapping
* Screenshot metadata preservation

Schema:

```json
{
  "chunk_id": 8,
  "screenshots": [...]
}
```

---

## 7.4 Visual Knowledge Extraction ✅

Goal:

Screenshots
↓
Visual Knowledge Object

Completed:

* Gemma 4 Vision integration
* Multi-image analysis
* OCR extraction
* Educational content extraction
* Diagram understanding
* Screenshot importance scoring
* Automatic screenshot selection

Visual Object Schema:

```json
{
  "visual_summary": "...",
  "visual_notes": "...",
  "ocr_text": "...",
  "concepts": [...],
  "important_information": [...],
  "visual_type": "...",
  "teaching_stage": "...",
  "selected_image_indices": [...]
}
```

Capabilities:

* Diagram understanding
* Whiteboard understanding
* Slide understanding
* OCR extraction
* Educational note generation
* Screenshot ranking

Results:

* 35 chunks processed
* 35 visual objects generated
* Retry and recovery mechanisms implemented

Output:

```text
outputs/visual_objects/
├── chunk_0_visual.json
├── chunk_1_visual.json
...
├── chunk_34_visual.json
```

---

## 7.5 Unified Knowledge Merging ✅

Goal:

Knowledge Object
+
Visual Object
↓
Unified Lecture Understanding

Completed:

* Object merging
* Screenshot selection
* Concept merging
* Visual knowledge integration
* Unified schema generation

Merged Object Schema:

```json
{
  "chunk_id": 8,
  "topic": "...",
  "lecture_notes": "...",
  "visual_notes": "...",
  "concepts": [...],
  "important_information": [...],
  "selected_screenshots": [...]
}
```

Results:

* 35 merged objects generated
* Transcript and visual understanding combined

Output:

```text
outputs/merged_objects/
├── chunk_0.json
├── chunk_1.json
...
├── chunk_34.json
```

---

# Current Project Status

Current Pipeline:

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
↓
Merged Knowledge Objects

All stages through Week 7 are complete.

---

# Week 8 - Educational Content Generation Pipeline ✅

## 8.1 Lecture Outline Generation ✅

Goal:

Merged Knowledge Objects
↓
Lecture Outline

Completed:

* Lecture outline generation using Gemini
* Automatic chapter title generation
* Chapter boundary prediction
* Focus concept extraction
* Lecture structure planning

Output Schema:

```json
{
  "lecture_title": "...",
  "chapters": [
    {
      "chapter_id": 1,
      "title": "...",
      "start_chunk": 0,
      "end_chunk": 5,
      "focus_concepts": [...]
    }
  ]
}
```

Results:

* Entire lecture organized into semantic chapters
* Global understanding created before note generation
* Reduced chapter ambiguity

Output:

```text
outputs/notes/
└── lecture_outline.json
```

---

## 8.2 Chapter Builder ✅

Goal:

Lecture Outline
+
Merged Objects
↓
Chapter Objects

Completed:

* Automatic chapter construction
* Chunk aggregation
* Concept deduplication
* Topic merging
* Screenshot association
* Unified chapter schema generation

Chapter Schema:

```json
{
  "chapter_id": 1,
  "title": "...",
  "chunk_ids": [...],
  "focus_concepts": [...],
  "topics": [...],
  "concepts": [...],
  "lecture_notes": [...],
  "visual_notes": [...],
  "important_information": [...],
  "inferred_knowledge": [...],
  "screenshots": [...]
}
```

Results:

* Structured chapter objects created
* Complete educational context preserved

Output:

```text
outputs/chapters/
├── chapter_1.json
├── chapter_2.json
...
```

---

## 8.3 Study Notes Generation ✅

Goal:

Chapter Objects
↓
Professional Study Notes

Completed:

* Chapter-aware note generation
* Lecture-wide context awareness
* Duplicate reduction across chapters
* Educational content synthesis
* Markdown generation

Features:

* Core Concepts
* Detailed Explanations
* Important Observations
* Applications
* Key Takeaways
* Technical formatting
* Tables and lists

Results:

* High-quality structured study notes
* Minimal cross-chapter repetition
* Textbook-style educational content

Output:

```text
outputs/notes/
├── chapter_1.md
├── chapter_2.md
...
└── study_notes.md
```

---

## 8.4 Intelligent Screenshot Selection ✅

Goal:

Chapter
+
Candidate Screenshots
↓
Important Educational Screenshots

Completed:

* Vision-based screenshot analysis
* Automatic educational value estimation
* Screenshot ranking
* Context-aware placement metadata
* Importance scoring

Screenshot Schema:

```json
{
  "chapter_id": 1,
  "screenshots": [
    {
      "path": "...",
      "reason": "...",
      "section": "...",
      "importance": 10
    }
  ]
}
```

Results:

* Only meaningful screenshots selected
* Reduced visual clutter
* Educational diagrams prioritized

Output:

```text
outputs/screenshots/selected/
├── chapter_1_screenshots.json
├── chapter_2_screenshots.json
...
```

---

## 8.5 Study Notes PDF Generation ✅

Goal:

Study Notes
+
Selected Screenshots
↓
Professional Study Guide PDF

Completed:

* Markdown rendering
* Professional PDF layout
* Chapter formatting
* Table rendering
* Mathematical notation support
* Screenshot integration
* Automatic pagination

Results:

* High-quality printable study guide
* Rich multimodal educational content
* Consistent formatting across chapters

Output:

```text
outputs/notes/
├── study_notes.md
└── study_notes.pdf
```

---

## 8.6 Revision Notes Generation ✅

Goal:

Study Notes
↓
Concise Revision Notes

Completed:

* Chapter compression
* Redundant information removal
* Revision-focused restructuring
* Formula preservation
* Complexity preservation
* Markdown generation

Features:

* Core Idea
* Key Concepts
* Operations
* Complexity
* Important Observations

Results:

* High information density
* Exam-oriented revision material
* Significantly reduced reading time

Output:

```text
outputs/revision/
├── revision_chapter_1.md
├── revision_chapter_2.md
...
└── revision_notes.md
```

---

## 8.7 Revision PDF Generation ✅

Goal:

Revision Notes
↓
Compact Revision Sheet

Completed:

* Professional revision layout
* Dense formatting
* Tables
* Clean typography
* Printable revision PDF

Results:

* Quick-review document
* Ideal for last-minute revision
* Compact yet comprehensive

Output:

```text
outputs/revision/
├── revision_notes.md
└── revision_notes.pdf
```

---

## 8.8 Assessment Generation ✅

Goal:

Study Notes
↓
Comprehensive Assessment

Completed:

* Automatic question generation
* Multi-format assessments
* Difficulty balancing
* Concept coverage
* Answer generation
* Explanation generation

Supported Question Types:

* Multiple Choice
* True / False
* Fill in the Blank
* Short Answer
* Conceptual Questions
* Scenario-based Questions
* Complexity Questions

Assessment Schema:

```json
{
  "question_id": 1,
  "chapter_id": 1,
  "type": "MCQ",
  "difficulty": "Easy",
  "concepts": [...],
  "question": "...",
  "options": [...],
  "answer": "...",
  "explanation": "..."
}
```

Results:

* Diverse educational assessments
* Balanced question difficulty
* Concept-focused evaluation

Output:

```text
outputs/assessment/
├── assessment.json
└── assessment.pdf
```

---

# Current Project Status

Current Pipeline:

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

↓

Lecture Outline Generation

↓

Chapter Builder

↓

Study Notes Generation

↓

Screenshot Selection

↓

Study Notes PDF

↓

Revision Notes Generation

↓

Revision PDF

↓

Assessment Generation

↓

Assessment PDF

NorAI can now automatically transform a lecture into a complete educational package consisting of study notes, revision material, assessments, and professionally formatted PDFs.

---

# Upcoming Work

## Week 9 - Interactive Learning Assistant

Goal:

Educational Content

↓

Personalized Learning Experience

Planned Features:

* Retrieval-Augmented Question Answering (RAG)
* Context-aware AI tutor
* Screenshot-grounded explanations
* Flashcard generation
* Interactive quizzes
* Learning progress tracking

---

# Future Roadmap

Planned Features:

* AI Tutor
* Flashcard generation
* Interactive quiz engine
* Multi-video knowledge base
* Lecture comparison
* Cross-lecture retrieval
* Web application
* User authentication
* Personal knowledge base
* Learning analytics
* Adaptive learning recommendations

---

# Lessons Learned

* Global lecture structure significantly improves note quality.
* Chapter ownership greatly reduces cross-chapter duplication.
* Educational content generation benefits from a multi-stage pipeline rather than a single LLM prompt.
* Vision models are highly effective for selecting educational screenshots.
* Separating study notes, revision notes, and assessments produces better specialized learning resources.
* Structured intermediate artifacts make the pipeline easier to debug, improve, and extend.
* Modular pipeline design enables independent optimization of each educational component.

---

Last Updated:

**Week 8 Complete**

**NorAI v0.8 — Educational Content Generation Pipeline Complete**

