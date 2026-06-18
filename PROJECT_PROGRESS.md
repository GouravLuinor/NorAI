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

# Upcoming Work

## Week 8 - Notes Generation

Goal:

Merged Objects
↓
Lecture Notes

Features:

* Structured chapter generation
* Topic grouping
* Educational note synthesis
* Screenshot insertion
* Markdown export
* PDF generation

Output:

* Lecture Notes PDF
* Lecture Notes Markdown

---

# Future Roadmap

Planned Features:

* Quiz generation
* Flashcard generation
* Revision mode
* Multi-video retrieval
* Lecture comparison
* Interactive learning assistant
* Web UI
* User authentication
* Personal knowledge base
* Learning analytics

---

# Lessons Learned

* Preserve timestamps everywhere.
* Transcript-only understanding is insufficient.
* Visual information contains substantial educational value.
* Knowledge extraction should be separated from retrieval.
* Structured educational objects scale better than raw transcripts.
* Retry mechanisms are essential for large-scale AI pipelines.
* Merged multimodal knowledge creates significantly richer lecture understanding.

---

Last Updated:

Week 7 Complete
NorAI v0.7
