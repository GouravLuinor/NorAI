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

# Week 9 - Interactive AI Tutor ✅

## 9.1 LangGraph Tutor Architecture ✅

Goal:

Educational Knowledge Base

↓

State-driven AI Tutor

Completed:

* LangGraph workflow
* Persistent conversation state
* Modular node architecture
* Conditional graph routing
* Multi-phase tutor pipeline

Features:

* Stateful conversations
* Extensible graph design
* Modular retrieval pipeline
* Independent tool execution

Output:

```text
tutor/
    __init__.py
    build_index.py              – build Chroma index from study notes
    build_screenshot_index.py   – build screenshot caption index
    chunker.py                  – Markdown → heading-hierarchy chunks
    cli.py                      – interactive CLI for tutor testing
    config.py                   – model, API key, checkpoint configuration
    embedding.py                – Gemini embedding wrapper for Chroma
    graph.py                    – LangGraph workflow and routing
    memory.py                   – SQLite checkpoint persistence
    nodes.py                    – core tutor nodes (memory, answer generation)
    nodes_retrieval.py          – query rewrite, chapter routing, text/image retrieval
    prompts.py                  – tutor prompts and context builders
    quiz_nodes.py               – interactive quiz state machine
    retrieval_config.py         – retrieval and screenshot constants
    retriever.py                – Chroma retrieval utilities
    state.py                    – ChatState definition
    test_chunker.py             – unit tests for Markdown chunking
    tools.py                    – tool implementations (quiz, summary, flashcards)

---

## 9.2 Persistent Memory & Multi-Thread Conversations ✅

Goal:

User Conversations

↓

Persistent Learning Sessions

Completed:

* SQLite checkpointing
* Conversation persistence
* Multi-thread support
* Memory restoration
* Conversation window management

Results:

* Multiple independent conversations
* Memory preserved across sessions
* Long-running tutoring supported

---

## 9.3 Intelligent Retrieval Pipeline ✅

Goal:

Student Question

↓

Relevant Educational Context

Completed:

* Gemini embedding generation
* ChromaDB vector search
* Heading-aware Markdown chunking
* Query rewriting
* Chapter-aware retrieval
* Parallel retrieval pipeline

Features:

* Semantic retrieval
* Chapter-specific search
* Automatic query refinement
* Efficient vector indexing

Data Sources:

```text
outputs/notes/chapter_*.md
```

---

## 9.4 Screenshot-Grounded Learning ✅

Goal:

Question

*

Relevant Slides

↓

Visual Explanation

Completed:

* Screenshot caption indexing
* Screenshot vector retrieval
* Parallel image retrieval
* Screenshot-grounded responses
* Educational citation support

Results:

* Relevant lecture slides retrieved alongside text
* Visual explanations integrated naturally
* Better conceptual understanding

Data Sources:

```text
outputs/screenshots/selected/
```

---

## 9.5 Conversation Intelligence ✅

Goal:

Natural Multi-turn Tutoring

Completed:

* Conversation summarization
* Context window compression
* Chapter routing
* Confidence estimation
* Progressive response prompting

Features:

* Windowed memory
* Low-confidence signaling
* Automatic conversation summaries
* Natural follow-up handling

Results:

* Stable long conversations
* Reduced token usage
* Better conversational continuity

---

## 9.6 Interactive Quiz Engine ✅

Goal:

Tutor

↓

Active Learning

Completed:

* Interactive quiz sessions
* Question tracking
* Answer collection
* Automatic grading
* LLM-based evaluation
* Session scoring

Supported Questions:

* Multiple Choice
* True / False
* Fill in the Blank
* Short Answer
* Conceptual
* Scenario-based
* Complexity

Results:

* Interactive assessment directly inside the tutor
* Immediate educational feedback

---

## 9.7 Tool Calling Infrastructure ✅

Goal:

AI Tutor

↓

Educational Agent

Completed:

* LLM tool selection
* Generic tool execution
* ToolNode integration
* Agent loop
* Extensible tool framework

Current Tools:

* Start Quiz
* Chapter Summary
* Flashcards

Results:

* Tutor automatically selects appropriate tools
* Easily extensible architecture for future capabilities

---

## 9.8 Flashcard Generation ✅

Goal:

Assessment Bank

↓

Revision Flashcards

Completed:

* Flashcard generation
* Random concept selection
* Question-answer format
* Interactive review

Results:

* Lightweight revision mode
* Rapid concept recall
* Reuse of assessment knowledge base

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

Visual Knowledge Extraction

↓

Knowledge Merging

↓

Lecture Outline Generation

↓

Chapter Builder

↓

Study Notes

↓

Study PDF

↓

Revision Notes

↓

Revision PDF

↓

Assessment Generation

↓

Assessment PDF

↓

LangGraph AI Tutor

↓

Screenshot Retrieval

↓

Interactive Quiz

↓

Flashcards

↓

Tool Calling

NorAI has evolved from a lecture-processing pipeline into a complete AI-powered educational platform capable of generating learning resources and providing interactive tutoring.

---

## Week 10 - Interactive Learning Platform ✅

Goal:

Educational Backend

↓

Complete Interactive Learning Platform

Completed:

* React + TypeScript + Vite frontend
* Three-panel study workspace
* Custom NorAI dark theme
* Study Notes viewer
* Revision Notes viewer
* Assessment viewer
* AI Tutor interface
* Interactive Quiz interface
* Flashcards interface
* Sidebar navigation
* Resizable workspace
* Keyboard shortcuts
* Responsive layouts
* Mock data architecture
* Educational UI component system

Workspace Layout:

```
┌───────────────────────────────────────────────────────────────┐
│ Sidebar │ Study Material │ AI Assistant                      │
│         │                │                                   │
│ Threads │ Study Notes    │ Tutor                             │
│ Chapters│ Revision Notes │ Quiz                              │
│         │ Assessment     │ Flashcards                        │
└───────────────────────────────────────────────────────────────┘
```

Document Features:

* Markdown-based study notes
* Educational revision cards
* Assessment worksheets
* Rich typography
* Code highlighting
* Progress indicators

AI Workspace:

* Conversational tutor interface
* Interactive quizzes
* Flashcards with spaced-repetition ratings
* Evidence cards
* Screenshot previews
* Streaming-ready chat interface

UX Features:

* Custom panel resizing
* Collapsible sidebar
* Framer Motion animations
* Ripple interactions
* Keyboard shortcuts
* Responsive design
* Loading shimmer
* Interactive navigation

Frontend Architecture:

```
React
↓
Component Layer
↓
Zustand State
↓
(Mock API Layer)
↓
LangGraph Backend (Upcoming)
```

Output:

```
frontend/
├── components/
│   ├── layout/
│   ├── chat/
│   ├── quiz/
│   ├── flashcards/
│   └── doc/
├── stores/
├── mocks/
├── App.tsx
├── main.tsx
└── index.css
```

---

# Current Project Status

Current Pipeline:

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
Visual Understanding
↓
Knowledge Merging
↓
Chapter Generation
↓
Study Notes
↓
Revision Notes
↓
Assessments
↓
AI Tutor
↓
Interactive Frontend
```

The complete educational pipeline is finished.

The frontend has been fully developed using realistic mock data and is ready for backend integration.

---

# Upcoming Work

# Week 11 - Full-Stack Platform Integration & Automated Pipeline ✅

Goal:

Raw Lecture Video

↓

Automated Educational Processing

↓

Complete Interactive Learning Platform

Week 11 transformed NorAI from separate educational, tutor, and frontend systems into a single end-to-end application.

A user can now submit a lecture and move through the complete workflow:

```text
Lecture Upload
↓
Automated Processing
↓
Educational Content Generation
↓
Tutor Indexing
↓
Interactive Workspace
```

---

## 11.1 Full-Stack Integration ✅

Goal:

React Frontend

+

FastAPI Backend

+

LangGraph Tutor

↓

Unified Application

Completed:

* React ↔ FastAPI integration
* FastAPI ↔ LangGraph integration
* Removal of frontend mock data
* Live educational content loading
* Real tutor responses
* Persistent conversation threads
* Real quiz integration
* Real flashcard integration
* Real revision summary integration
* Study notes API integration

Architecture:

```text
React Frontend
      ↓
FastAPI Backend
      ↓
LangGraph Tutor
      ↓
Educational Knowledge Base
```

---

## 11.2 Automated Lecture Processing Pipeline ✅

Goal:

Lecture Source

↓

Complete NorAI Educational Workspace

Completed:

* Unified pipeline orchestrator
* Background processing
* Sequential stage execution
* Live progress tracking
* SSE progress updates
* Polling fallback
* Failure isolation
* Outline fallback generation

Pipeline:

```text
Video Source
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
Chunk-to-Screenshot Mapping
↓
Visual Knowledge Extraction
↓
Knowledge Merging
↓
Outline Generation
↓
Chapter Building
↓
Study Notes Generation
↓
Screenshot Selection
↓
Revision Notes Generation
↓
Assessment Generation
↓
PDF Generation
↓
Tutor Index Generation
↓
Screenshot Index Generation
```

The complete educational pipeline can now run automatically from a single user submission.

---

## 11.3 Lecture Upload Workflow ✅

Goal:

User Input

↓

Automated Processing

Completed:

* YouTube URL input
* Local video upload
* Google Drive link input
* Upload landing page
* Processing page
* Task-based background execution
* Live processing timeline
* Progress bar
* Workspace navigation after completion

Frontend Pages:

```text
/
↓
UploadPage

/process/:taskId
↓
ProcessingPage

/workspace/:lectureId
↓
Learning Workspace
```

---

## 11.4 Multi-Lecture Architecture ✅

Goal:

Multiple Lectures

↓

Independent Learning Environments

Completed:

* Lecture registry
* Unique lecture IDs
* Lecture-scoped output directories
* Lecture selector
* Lecture-specific notes
* Lecture-specific revision material
* Lecture-specific assessments
* Lecture-specific flashcards
* Lecture-specific tutor indexes
* Lecture-specific screenshot indexes
* Lecture-specific conversation memory

Output Structure:

```text
outputs/

├── lecture_1/
│   ├── notes/
│   ├── revision/
│   ├── assessment/
│   ├── screenshots/
│   ├── flashcards/
│   ├── pdfs/
│   └── tutor/
│
├── lecture_2/
│   └── ...
│
└── lectures.json
```

Switching lectures now loads the corresponding educational workspace and tutor context.

---

## 11.5 Per-Lecture AI Tutor Isolation ✅

Goal:

Lecture

↓

Dedicated Tutor Knowledge Space

Completed:

* Per-lecture LangGraph graphs
* Per-lecture SQLite checkpoints
* Per-lecture Chroma indexes
* Per-lecture thread history
* Graph caching
* Dedicated graph locks
* Backward-compatible default tutor mode

Architecture:

```text
Lecture A
├── Tutor Graph
├── Checkpointer
├── Text Index
└── Screenshot Index

Lecture B
├── Tutor Graph
├── Checkpointer
├── Text Index
└── Screenshot Index
```

Tutor conversations and retrieval are now isolated between lectures.

---

## 11.6 Live Tutor Integration ✅

Goal:

Student Question

↓

Grounded Interactive Explanation

Completed:

* Real LangGraph tutor responses
* Persistent multi-thread conversations
* Study note retrieval
* Screenshot retrieval
* Chapter-aware routing
* Query rewriting
* Confidence-aware answers
* Tool calling
* Quiz workflows
* Flashcards
* Chapter summaries
* Retrieved references
* Screenshot previews

Tutor Flow:

```text
User Message
↓
FastAPI
↓
Lecture-Scoped LangGraph
↓
Memory
↓
Query Understanding
↓
Parallel Retrieval
├── Study Notes
└── Screenshot Knowledge
↓
Tool Calling / Answer Generation
↓
Persistent Response
```

---

## 11.7 Educational Resource APIs ✅

Completed APIs for:

* Study notes
* Revision summaries
* Assessments
* Quiz evaluation
* Flashcards
* Screenshots
* PDF downloads
* Threads
* Lectures
* Processing status
* Tutor chat

Educational artifacts are now exposed through a unified backend rather than accessed directly by the frontend.

---

## 11.8 Interactive Workspace Improvements ✅

Completed:

* Resizable workspace panels
* Study Notes viewer
* Revision Notes viewer
* Assessment viewer
* Tutor panel
* Quiz panel
* Flashcards panel
* Lecture selector
* Persistent thread sidebar
* Search
* Highlight & Ask
* Screenshot lightbox
* KaTeX math rendering
* Reference-to-notes navigation
* Cross-chapter reference navigation
* Keyboard shortcut modal
* Toast notifications
* Dark/Light theme

Workspace:

```text
┌────────────────────────────────────────────────────────────┐
│ Sidebar │ Educational Document │ AI Learning Assistant    │
│         │                      │                          │
│ Lectures│ Study Notes          │ Tutor                    │
│ Threads │ Revision             │ Quiz                     │
│ Chapters│ Assessment           │ Flashcards               │
│         │                      │ References               │
└────────────────────────────────────────────────────────────┘
```

---

## 11.9 Highlight & Ask ✅

Goal:

Selected Learning Material

↓

Immediate Tutor Explanation

Completed:

* Text selection detection
* Floating "Ask Nora" action
* Automatic tutor query creation
* Active lecture context preservation
* Direct answer in tutor panel

Flow:

```text
Select Text
↓
Ask Nora
↓
Lecture-Scoped Tutor
↓
Contextual Explanation
```

This creates direct interaction between static educational content and the AI tutor.

---

## 11.10 Cross-Panel Reference Linking ✅

Goal:

Tutor Evidence

↓

Exact Learning Material

Completed:

* Clickable tutor references
* Automatic chapter switching
* Automatic Notes tab switching
* Exact section scrolling
* Heading ID generation
* Temporary pulse highlighting
* Deep sub-heading support

Flow:

```text
Tutor Answer
↓
Reference Click
↓
Correct Chapter
↓
Correct Section
↓
Visual Highlight
```

This tightly connects AI explanations with source educational material.

---

## 11.11 Search & Navigation ✅

Completed:

* Inline document search
* Match highlighting
* Next/previous result navigation
* Cross-chapter reference navigation
* Lecture switching
* Chapter switching
* Persistent active workspace state

---

## 11.12 Mathematical Rendering ✅

Completed:

* Inline LaTeX
* Block LaTeX
* KaTeX rendering
* Math support in study notes
* Math support in revision notes
* Math support in tutor responses

Technology:

```text
remark-math
+
rehype-katex
```

Examples:

```text
$O(\log n)$

$$
\frac{a}{b}
$$
```

---

## 11.13 PDF Generation Pipeline ✅

Goal:

Interactive Educational Content

↓

Downloadable Learning Documents

Completed:

* Playwright-based PDF generation
* Study Notes PDF
* Revision Notes PDF
* Assessment PDF
* Dedicated print route
* Important Visuals expansion
* Visible assessment answer keys
* Lecture-scoped PDF storage
* Frontend download buttons

Pipeline:

```text
React Print Page
↓
Headless Chromium
↓
Rendered Educational Layout
↓
PDF
```

Output:

```text
outputs/{lecture_id}/pdfs/

├── notes.pdf
├── revision.pdf
└── assessment.pdf
```

---

## 11.14 Pipeline Reliability Improvements ✅

Completed:

* Shared Gemini API rate limiter
* Thread-safe request limiting
* Retry count increased
* Random retry jitter
* Reduced worker concurrency
* Balanced model usage
* LLM-stage failure isolation
* SSE keep-alive
* Polling fallback
* Missing visual fallback
* Outline fallback
* Missing chapter guards

Model Strategy:

```text
High-Volume Stages
↓
Gemini Flash-Lite

Quality-Critical Stages
↓
Gemma 4
```

Flash-Lite is used for:

* Knowledge extraction
* Outline generation
* Screenshot scoring
* Screenshot ranking

Gemma 4 is used for:

* Visual understanding
* Study notes
* Revision notes
* Assessments

---

## 11.15 Major Stability Fixes ✅

Resolved:

* CORS development issues
* Infinite React render loops
* Thread persistence failures
* Message duplication
* Shimmer state leakage
* Stale quiz state
* Hard-refresh thread loss
* Double chat submissions
* JSON-wrapped Markdown rendering
* Reference ID mismatches
* Deep heading navigation
* Cross-chapter reference navigation
* Outline-to-chapter range errors
* Missing visual object handling
* Non-sequential chapter numbering
* Missing chapter crashes
* SSE connection drops
* Empty lecture dropdown
* Chapter switching issues
* Per-lecture flashcard storage
* Per-lecture Chroma indexing

---

# Current Project Status

Current End-to-End Pipeline:

```text
Lecture Upload
↓
Ingestion
↓
Transcription
↓
Chunking
↓
Knowledge Extraction
↓
Visual Understanding
↓
Knowledge Merging
↓
Outline Generation
↓
Chapter Building
↓
Study Notes
↓
Screenshot Selection
↓
Revision Notes
↓
Assessments
↓
Flashcards
↓
PDF Generation
↓
Tutor Indexing
↓
Interactive Workspace
↓
Persistent AI Tutor
```

NorAI now supports the complete journey from raw lecture video to an interactive multimodal learning environment.

---

# Upcoming Work

## Week 12 - Production Readiness & Advanced Learning

Goal:

Functional Full-Stack Platform

↓

Production-Ready Personalized Learning System

Planned Features:

* Thread system edge-case fixes
* Async migration
* User authentication
* User profiles
* Mobile responsive layout
* Full-text cross-chapter search
* Adaptive expertise tracking
* Learning analytics
* Personalized recommendations
* Docker deployment
* Production configuration
* Production database strategy

---

# Future Roadmap

Planned Features:

* Personal knowledge base
* Multi-video knowledge spaces
* Cross-lecture retrieval
* Lecture comparison
* Adaptive expertise tracking
* Weak-concept detection
* Personalized revision plans
* Learning analytics
* Spaced repetition
* Multi-user deployment
* Cloud object storage
* Background job queue
* Production observability

---

# Lessons Learned

* A multimodal educational pipeline becomes significantly more useful when connected directly to an interactive workspace.
* Per-lecture isolation is essential for scaling from a single demo lecture to a real learning platform.
* Graph-based tutoring and structured educational artifacts complement each other better than raw transcript RAG.
* Visual lecture knowledge should remain a first-class retrieval source throughout the entire platform.
* Background orchestration requires failure isolation because one LLM stage should never destroy an entire processing run.
* Rate limiting and controlled concurrency are essential for reliable multi-stage AI pipelines.
* Pre-generated educational artifacts reduce runtime latency and API cost.
* Cross-panel linking significantly improves trust by connecting tutor explanations directly to source material.
* Highlight & Ask creates a natural bridge between reading and conversational learning.
* A lecture-scoped architecture provides a strong foundation for future multi-user and multi-course systems.
* Full-stack integration exposed edge cases that isolated frontend and backend development could not reveal.
* Modular architecture allowed the original NorAI pipeline to evolve into a complete platform without requiring a fundamental rewrite.

---

# Week 12 — Full-Stack Integration, Multi-Lecture Architecture & Pipeline Stabilization

## Objective

The primary goal of Week 12 was to transform NorAI from a collection of independently working AI pipelines and frontend components into a fully integrated, end-to-end learning platform.

Until this stage, most major systems already existed independently:

- Video ingestion
- Transcription
- Transcript chunking
- Knowledge extraction
- Visual understanding
- Chapter generation
- Study notes
- Revision notes
- Assessments
- Flashcards
- RAG-based tutoring
- React frontend

The focus of Week 12 was therefore not simply to add another isolated feature.

The real objective was to connect the complete system:

> Video Input → Automated Processing Pipeline → Lecture-Specific Artifacts → Interactive Workspace → AI Tutor

This required major architectural work across the FastAPI backend, React frontend, processing orchestration, lecture storage, tutor state management, PDF generation, progress tracking, and multi-lecture isolation.

---

# 1. FastAPI Backend Integration

A FastAPI backend was introduced as the central application layer connecting the AI pipeline with the React frontend.

The backend now acts as the bridge between:

- video ingestion
- long-running lecture processing
- generated study materials
- assessments
- flashcards
- screenshots
- lecture metadata
- tutor conversations
- PDF downloads
- progress tracking

The frontend no longer depends on mock data for the primary learning workflow.

Major API capabilities include:

- lecture processing
- lecture registry access
- lecture outline retrieval
- study notes retrieval
- revision notes retrieval
- assessment retrieval
- flashcard retrieval
- screenshot retrieval
- tutor chat
- conversation threads
- processing progress
- generated document access

This converted NorAI from a local pipeline prototype into an actual full-stack application.

---

# 2. Complete Automated Lecture Processing Pipeline

A centralized orchestration layer was created in:

`backend/orchestrator.py`

The orchestrator coordinates the complete NorAI pipeline for each lecture.

The final processing flow became:

1. Ingestion
2. Transcription
3. Chunking
4. Knowledge Extraction
5. Frame Extraction
6. Scene Detection
7. Chunk-to-Screenshot Mapping
8. Visual Knowledge Extraction
9. Knowledge Merging
10. Lecture Outline Generation
11. Chapter Building
12. Study Notes Generation
13. Screenshot Selection
14. Revision Notes Generation
15. Assessment Generation
16. Flashcard Generation
17. Tutor Index Construction
18. Screenshot Index Construction

This was one of the most important architectural milestones in the project.

Previously, many stages had to be executed manually.

After Week 11, a single lecture submission could trigger the complete workflow automatically.

---

# 3. Real-Time Processing Progress System

A processing progress system was implemented so the frontend could display the current pipeline stage.

Each task tracks:

- task ID
- current stage
- status message
- percentage complete
- completion state
- error state

Example pipeline updates:

- Downloading video
- Transcribing lecture
- Chunking transcript
- Extracting knowledge
- Understanding visuals
- Generating outline
- Writing study notes
- Creating assessment
- Generating flashcards
- Indexing tutor knowledge
- Indexing screenshots

The frontend ProcessingPage displays these stages as a visual timeline.

Initially, Server-Sent Events were used for real-time updates.

However, several reliability problems appeared:

- dropped connections
- pending stream requests
- frontend stuck on "Preparing…"
- reconnect complexity
- interaction with long-running blocking pipeline stages

The progress architecture was eventually simplified to:

> Frontend polling `/process/{task_id}/status` every 1.5 seconds

This provided a much more predictable development experience.

---

# 4. Critical Async Event Loop Bug

One of the most significant bugs discovered during Week 12 was that the frontend remained stuck on:

`Preparing…`

even though the backend pipeline continued successfully.

The browser Network panel showed repeated status requests remaining:

`(pending)`

The root cause was architectural.

The pipeline function was declared asynchronous, but most internal operations were synchronous and blocking:

- FFmpeg
- Faster-Whisper
- file processing
- scene detection
- synchronous LLM calls
- ChromaDB operations
- subprocess execution

An `async def` function does not automatically make synchronous operations non-blocking.

The long-running pipeline occupied the FastAPI execution path and prevented lightweight progress requests from being served reliably.

The final architecture moved pipeline execution into a background thread.

This allowed:

- FastAPI to continue serving HTTP requests
- `/status` polling to respond immediately
- the processing page to update continuously
- long-running pipeline stages to execute independently

This became one of the most important backend engineering lessons from the project:

> Async syntax alone does not make blocking workloads asynchronous.

---

# 5. Multi-Lecture Architecture

NorAI was upgraded from a single-lecture prototype into a multi-lecture platform.

Every lecture now receives a unique lecture ID.

Example:

`a0a493e7-34e0-4c64-b423-2958f3e4a2f1`

Each lecture receives its own isolated directory:

`outputs/{lecture_id}/`

The structure contains lecture-specific artifacts such as:

- metadata
- transcripts
- chunks
- extracted knowledge
- screenshots
- mappings
- visual objects
- merged objects
- chapters
- notes
- revision notes
- assessments
- flashcards
- tutor indexes
- checkpoint databases

Conceptually:

`outputs/{lecture_id}/notes/`

`outputs/{lecture_id}/assessment/`

`outputs/{lecture_id}/flashcards/`

`outputs/{lecture_id}/screenshots/`

`outputs/{lecture_id}/tutor/`

This eliminated accidental data sharing between lectures.

---

# 6. Lecture Registry

A lecture registry was introduced to track processed lectures.

Each lecture stores information such as:

- lecture ID
- title
- creation metadata
- processing information

Initially, every lecture appeared as:

`New Lecture`

because the registry entry was created before outline generation.

The pipeline was updated so that after the lecture outline is generated, the real AI-generated lecture title is written back into the registry.

This allowed the frontend lecture switcher to display meaningful titles.

---

# 7. Dynamic Workspace Routing

The workspace routing system was updated to include the lecture ID.

Old behavior:

`/workspace`

New behavior:

`/workspace/{lectureId}`

Example:

`/workspace/a0a493e7-34e0-4c64-b423-2958f3e4a2f1`

This ensured that:

- page refreshes preserve lecture context
- lecture switching updates the URL
- shared workspace links remain lecture-specific
- frontend state can be restored from routing information

A bug was also fixed where lecture switching updated only the Zustand store but not the route.

The final solution updates both:

- active lecture state
- browser URL

---

# 8. Dynamic Chapter Sidebar

The chapter sidebar originally relied on static mock data.

This caused a major inconsistency:

- notes changed correctly
- revision notes changed correctly
- assessments changed correctly
- screenshots changed correctly
- chapter names remained from the previous lecture

The root cause was:

`mocks/chapters.ts`

The sidebar was migrated to dynamic chapter loading through the lecture outline API.

The frontend now requests:

`/outline?lecture_id={lectureId}`

and builds the chapter list from:

`data.chapters`

This allows every lecture to display its own:

- chapter IDs
- chapter titles
- chapter count

The `/outline` endpoint was also added to the Vite proxy configuration.

---

# 9. Lecture-Aware Study Materials

All educational resources were updated to use the active lecture ID.

This included:

- Study Notes
- Revision Notes
- Assessment
- Flashcards
- Screenshots

A recurring class of bugs involved frontend functions silently using:

`lecture_id=default`

This caused content from the original Segment Tree lecture to appear inside unrelated lectures.

The fix was to consistently retrieve:

`activeLectureId`

from the lecture store and pass it into every relevant API request.

---

# 10. Assessment Integration

The assessment system was connected to the live backend.

Generated chapter assessments now support:

- multiple-choice questions
- true/false questions
- short-answer questions
- chapter-aware loading
- answer keys

A major bug occurred because quiz requests continued using the default lecture.

The fix was to pass the active lecture ID explicitly into:

`fetchQuizQuestions(chapterId, lectureId)`

This prevented assessment data from leaking between lectures.

---

# 11. Flashcard Pipeline Integration

Flashcards were integrated as a generated educational artifact derived from assessment questions.

The generation flow became:

> Assessment Questions → Batch Processing → Gemini → Flashcards

Each flashcard contains:

- front
- back
- explanation

Flashcards are stored per chapter:

`flashcards_chapter_1.json`

`flashcards_chapter_2.json`

`flashcards_chapter_3.json`

and also as a combined file:

`flashcards.json`

The frontend flashcard panel supports:

- card flipping
- previous/next navigation
- Again
- Hard
- Good
- Easy
- reviewed count
- mastery statistics

Several major bugs were discovered.

### Bug 1 — Flashcard Stage Indentation

The flashcard generation stage had accidentally been placed inside the assessment exception path.

This meant flashcards could run only when assessment generation failed.

The indentation was corrected so flashcards execute after assessment generation.

### Bug 2 — Wrong Output Directory

The flashcard script originally relied on global paths:

`outputs/assessment`

`outputs/flashcards`

This caused it to read assessment data from the default lecture.

The result was especially visible when a four-chapter lecture generated flashcards for six chapters from an old Segment Tree lecture.

The fix introduced lecture-specific output directory handling.

The flashcard generator now uses:

`outputs/{lecture_id}/assessment`

and writes to:

`outputs/{lecture_id}/flashcards`

### Bug 3 — Fragile Subprocess Execution

Subprocess execution introduced additional problems:

- output directory propagation
- hidden stderr
- hidden stdout
- ignored non-zero exit codes
- interpreter ambiguity

The architecture was changed toward direct inline execution with explicit lecture-specific module paths.

This made flashcard generation significantly more predictable.

---

# 12. Per-Lecture AI Tutor

The AI Tutor was upgraded for multi-lecture isolation.

Each lecture now receives its own retrieval environment.

Tutor data is stored under:

`outputs/{lecture_id}/tutor/`

This includes lecture-specific ChromaDB collections and conversation state.

The tutor can retrieve from:

- study notes
- chapter content
- screenshot explanations

This prevents questions about one lecture from retrieving knowledge from another.

---

# 13. Tutor Index Generation

Tutor indexing was moved directly into the orchestrator.

The pipeline reads generated study notes and creates retrieval chunks.

Each chunk contains metadata such as:

- heading
- heading path
- chapter ID
- source

The chunks are embedded and stored in a persistent ChromaDB collection.

Collection:

`norai_notes`

This allows the tutor to retrieve semantically relevant lecture material.

---

# 14. Screenshot Retrieval Index

A separate screenshot caption index was introduced.

Selected screenshots contain metadata such as:

- image path
- section
- reason
- importance
- chapter ID

These screenshot descriptions are embedded into ChromaDB.

Collection:

`screenshot_captions`

This allows the tutor to retrieve visual lecture evidence when answering questions.

The result is a more multimodal tutoring system where screenshots remain first-class knowledge sources.

---

# 15. Per-Lecture Conversation Threads

Conversation threads were isolated by lecture.

Previously, thread state could leak between lectures because localStorage keys were global.

The frontend was updated to scope thread keys using the lecture ID.

Conceptually:

`threads-{lectureId}`

instead of:

`threads`

This prevents:

- old conversations appearing in new lectures
- thread duplication
- cross-lecture state leakage

Additional guards were added to avoid loading threads before the active lecture ID was initialized.

---

# 16. Highlight & Ask

A cross-panel interaction feature was integrated.

Users can:

1. select text inside study material
2. activate Highlight & Ask
3. send the selected context to the AI Tutor
4. receive an explanation grounded in the selected material

This improved the relationship between static generated content and interactive tutoring.

Instead of manually copying text into chat, the user can directly ask questions about highlighted material.

---

# 17. Search and Navigation

Search functionality was integrated into the document panel.

Users can search within generated educational content while switching between:

- Study Notes
- Revision
- Assessment

This improved navigation across long generated lectures.

---

# 18. Screenshot Rendering and PDF Fixes

The PDF system went through several architectural changes.

Initially, PDFs were generated server-side using Playwright.

The flow was:

> Python → Playwright → Vite Print Page → PDF

This created several reliability issues:

- Vite connection failures
- Playwright timeout
- duplicated API requests
- screenshot loading races
- dynamic chapter count problems

The system was changed to on-demand browser-native printing.

The PrintPage renders the same React educational layouts and automatically triggers:

`window.print()`

This reduced dependency on headless browser infrastructure.

---

# 19. Dynamic PDF Chapter Count

The print page originally assumed every lecture had six chapters:

`Array.from({ length: 6 })`

This caused four-chapter lectures to display:

- Chapter 5
- Chapter 6

even when those chapters did not exist.

The fix introduced dynamic chapter count retrieval from:

`/outline?lecture_id={lectureId}`

The actual chapter count is now derived from:

`data.chapters.length`

This ensures the generated print document matches the real lecture structure.

---

# 20. Screenshot Loading in Print Mode

Another PDF bug occurred where:

- screenshot captions appeared
- screenshot cards appeared
- some actual images were missing

The screenshots existed correctly in the backend.

The problem involved lecture context and image loading behavior.

The PrintPage was updated to synchronize the lecture ID with the lecture store:

`setActiveLecture(lectureId)`

The screenshot component was also configured for print rendering with:

- expanded screenshot sections
- eager image loading

This allowed all chapter screenshots to appear correctly in the final printed document.

---

# 21. Visual Knowledge JSON Reliability

During visual understanding, Gemini occasionally returned malformed JSON.

Example failures included:

`Expecting ',' delimiter`

The model response often contained valid-looking structured data but invalid escaping inside fields such as:

- OCR text
- code snippets
- quoted strings

The visual extraction pipeline already included retry logic.

Example:

- attempt 1
- attempt 2
- attempt 3
- attempt 4
- attempt 5

This allowed transient malformed outputs to be retried instead of immediately destroying the pipeline.

The issue highlighted the importance of defensive parsing when LLM-generated JSON contains:

- source code
- escaped quotes
- multiline OCR
- backslashes

---

# 22. Pipeline Failure Isolation

One of the major reliability improvements was wrapping later pipeline stages in independent error handling.

Examples include:

- visual understanding
- knowledge merging
- outline generation
- chapter building
- study notes
- screenshot selection
- revision notes
- assessment
- flashcards
- tutor indexing
- screenshot indexing

Instead of one failure terminating the entire lecture processing run, recoverable stages can log the failure and continue.

This was essential because a multimodal AI pipeline contains many external failure points:

- model API instability
- malformed JSON
- rate limits
- missing screenshots
- incomplete generated artifacts
- file-system inconsistencies

---

# 23. Missing Visual Object Fallback

The knowledge merger originally assumed every chunk had visual knowledge.

This was incorrect.

Some transcript chunks naturally have:

- no relevant screenshot
- no selected frame
- no visual object

The merger was updated with a fallback path for chunks without visual information.

This ensures textual knowledge is still preserved and merged even when no screenshot exists.

---

# 24. Chapter ID Normalization

The outline generation model occasionally returned non-sequential chapter IDs such as:

`0, 2, 5, 7, 9, 10`

This broke downstream assumptions.

After outline generation, chapters are now normalized to:

`1, 2, 3, ..., N`

This provides stable chapter identifiers across:

- notes
- revision
- assessment
- flashcards
- screenshots
- frontend navigation
- tutor metadata

---

# 25. Missing Chapter Guards

Several content generators originally assumed all expected chapter files existed.

This caused crashes when a chapter was missing.

Guards were added to:

- notes generation
- revision generation
- assessment generation

The pipeline now checks for file existence before processing.

This significantly improved resilience when an earlier stage produces incomplete output.

---

# 26. Model Stability Changes

Gemma 4 produced repeated server-side failures during several pipeline stages.

Frequent errors included HTTP 500 responses.

To improve stability, high-volume pipeline stages were migrated toward:

`gemini-3.1-flash-lite-preview`

This reduced repeated failures and improved pipeline completion reliability.

The project also adopted controlled model selection based on workload characteristics.

---

# 27. Rate Limiting Improvements

Parallel AI calls occasionally produced rate-limit failures.

The pipeline uses controlled concurrency and shared rate limiters.

The maximum call threshold was reduced:

`13 → 12`

This created a small safety margin below provider limits.

The change improved reliability across:

- extraction
- visual processing
- content generation
- assessment
- flashcards

---

# 28. Frontend Toast Fix

Toast notifications were not consistently visible.

The root cause was component placement.

`<ToastContainer />`

had been rendered inside routing structure where it was not guaranteed to exist on every page.

It was moved outside `<Routes>`.

This ensured global toast availability.

---

# 29. Thread Duplication Guards

The conversation system occasionally produced:

- duplicate threads
- ghost threads
- old lecture threads
- repeated thread loading

One root cause was thread loading occurring before the lecture store had initialized.

Additional guards were introduced:

- skip loading when `activeLectureId` is missing
- prevent duplicate in-flight thread requests
- scope localStorage by lecture ID

This improved thread isolation, although some thread-system issues remain for future work.

---

# 30. Final Week 12 Architecture

By the end of Week 12, NorAI had evolved into a complete full-stack multimodal learning platform.

Final flow:

> User submits lecture  
> ↓  
> Backend creates unique lecture ID  
> ↓  
> Pipeline runs in background  
> ↓  
> Frontend polls live progress  
> ↓  
> Video is transcribed  
> ↓  
> Transcript is chunked  
> ↓  
> Knowledge is extracted  
> ↓  
> Frames and scenes are analyzed  
> ↓  
> Visual and textual knowledge are merged  
> ↓  
> Lecture outline is generated  
> ↓  
> Chapters are built  
> ↓  
> Study notes are generated  
> ↓  
> Screenshots are selected  
> ↓  
> Revision notes are generated  
> ↓  
> Assessment is created  
> ↓  
> Flashcards are generated  
> ↓  
> Tutor retrieval index is built  
> ↓  
> Screenshot retrieval index is built  
> ↓  
> Workspace becomes available  
> ↓  
> User studies with notes, revision, quiz, flashcards, screenshots, and AI Tutor

---

# Key Technical Achievements

- Built complete FastAPI integration layer
- Automated the full 18-stage lecture pipeline
- Added background processing for long-running workloads
- Implemented live progress tracking
- Migrated from SSE to polling for reliability
- Added multi-lecture architecture
- Added per-lecture filesystem isolation
- Added lecture registry
- Added dynamic workspace routing
- Replaced static chapter mocks with live outline data
- Added lecture-aware notes and revision views
- Added lecture-aware assessments
- Added lecture-aware flashcards
- Added per-lecture ChromaDB indexes
- Added per-lecture LangGraph state
- Added screenshot retrieval index
- Added cross-panel Highlight & Ask
- Added dynamic print layouts
- Added browser-native PDF generation
- Fixed dynamic chapter counts
- Fixed screenshot rendering in PDFs
- Added pipeline failure isolation
- Added malformed LLM JSON retry handling
- Added chapter ID normalization
- Added missing chapter guards
- Improved API rate limiting
- Improved thread isolation
- Fixed global toast rendering

---

# Major Engineering Lessons

## 1. Async Does Not Mean Non-Blocking

Declaring a function with:

`async def`

does not make synchronous operations asynchronous.

Blocking workloads such as:

- FFmpeg
- Whisper
- synchronous model clients
- CPU-heavy processing

must be isolated from the FastAPI request loop.

---

## 2. Per-Lecture Isolation Must Exist Everywhere

It is not enough to isolate only files.

Lecture identity must propagate through:

- URLs
- API requests
- Zustand stores
- localStorage
- ChromaDB
- SQLite
- screenshots
- assessments
- flashcards
- tutor threads

A single forgotten `default` value can cause cross-lecture data leakage.

---

## 3. Long AI Pipelines Need Failure Isolation

A multimodal pipeline should not fail completely because one optional stage fails.

Each recoverable stage should:

- catch errors
- log failures
- preserve previous artifacts
- continue when safe

---

## 4. Subprocesses Add Hidden Complexity

`subprocess.run()` can introduce:

- interpreter mismatches
- ignored exit codes
- hidden stderr
- hidden stdout
- environment differences
- path propagation bugs

Direct Python integration is often safer for internal pipeline stages.

---

## 5. LLM JSON Must Never Be Trusted Blindly

Even when explicitly instructed to return JSON, models can produce:

- invalid escaping
- malformed code strings
- missing commas
- truncated objects

Retries, validation, and defensive parsing are necessary.

---

## 6. Frontend State Must Follow Routing State

Changing only a global store is insufficient for multi-lecture navigation.

The route itself should encode lecture identity:

`/workspace/{lectureId}`

This improves:

- refresh behavior
- deep linking
- navigation consistency
- debugging

---

# Week 12 Result
h
Week 12 transformed NorAI from a collection of powerful AI modules into a cohesive, lecture-aware, full-stack learning platform.

The system now supports:

- automated lecture ingestion
- multimodal knowledge extraction
- dynamic chapter generation
- rich study notes
- revision notes
- assessments
- flashcards
- screenshot-grounded learning
- persistent AI tutoring
- multi-lecture switching
- live processing progress
- lecture-specific retrieval
- on-demand printable documents

The most important achievement was not a single feature.

It was the architectural transition from:

> Independent AI scripts and frontend prototypes

to:

> A unified end-to-end multimodal educational platform.

---

## Status

**Week 12: Completed**

**Current Version:** NorAI v1.2

**Platform State:** Stable end-to-end multimodal learning workflow with remaining improvements focused on thread UX, dynamic quiz refresh, mobile responsiveness, authentication, and production deployment.

---

## Frontend Design Rebuild (Tier 2 — Component Foundation)

Implemented the frontend component foundation per `frontend_design_roadmap.md`.

- **UI primitives** (`frontend/src/components/ui/`): `Button`, `IconButton` (required `label` — aria-label floor), `Card`/`CardHeader`, `Input`, `SegmentedControl` (`aria-pressed`), `Badge`, plus shared `FOCUS_RING` (`shared.ts`). Zero visual delta vs the hand-rolled classes they replaced (hairline `border-bdr2`, hard `shadow-ev1/2`, lucide `strokeWidth={1.5}`, mono ALL-CAPS section labels).
- **Migration sweep**: ~15 copy-paste sites → primitives — NotesView, RevisionView, PrintPage, FlashcardsPanel (rating row → SegmentedControl), AIPanel (mode switch → SegmentedControl), DocPanel, Sidebar, Workspace, QuizPanel, AssessmentView, HighlightAsk, SearchBar (Input + IconButtons + `focus-within` ring), UploadPage (source tabs → SegmentedControl), Lightbox, ShortcutsModal, ToastContainer. Deliberate holds documented: QuizPanel options (3-state), assessment True/False print stubs (static), UploadPage lecture rows stay `<button>` (Card is a div — a11y regression otherwise), ChapterScreenshots toggle (ghost hover bg).
- **PrintPage decomposition** (`src/components/print/`): `types.ts`, `cardClassifier.ts`, `parseChapter.ts`, `PrintSectionCard.tsx`, `PrintErrorBoundary.tsx`, `usePrintData.ts`, `PrintChapter.tsx`, `PrintAssessmentChapter.tsx`; `PrintPage.tsx` is now a thin entry. Behavior-preserving (title/preamble/sections, `__PRINT_DATA__` → `printDataReady` → 500 ms fallback fetch, 3 s auto-print).

Build ✓ lint ✓ (no new warnings — 3 pre-existing exhaustive-deps). **QA complete (all three passes green):** Pass A skill-gated code review (2 a11y fixes: SearchBar focus-within ring, UploadPage URL `aria-label`), Pass B Chrome MCP (tutor/quiz/cards, doc search, all three print routes, dark + light — 1 a11y fix: URL input `id`/`name`), Pass C human visual audit of `/.tmp/qa-tier-2/screenshots/` (12 screenshots). Review: `/.tmp/review-tier-2.md`.

---

## Frontend Design Rebuild (Tier 5 — "Architect's Sketchbook")

Implemented the approved theme reboot for the app frontend (see `frontend_design_roadmap.md`). The old viridian direction is superseded.

- **Theme polarity flip**: vellum-paper **light** (`#F6F2E7`) is now the default; Prussian-blue dark (`#0B1E3A`) via `[data-theme="dark"]` override. `ThemeToggle` default + meta `theme-color` updated (`#F6F2E7`/`#0B1E3A`).
- **Accent = Red Pencil**: `#C2410C` (light fill) / `#D1552E` (dark accent) / `#E85D2F` (dark hover). Viridian tokens retired. Status-dot palette pinned per DESIGN.md.
- **Dark-theme AA contrast fix**: white text on the dark `#D1552E` fill was 4.16:1 (failed WCAG AA). Added dedicated `--color-npf`/`--color-npfh` button-fill tokens (light `#C2410C`/`#A9361C`, dark `#C43D1E`/`#B93A1D` — white-on ≥5.2:1) applied to 22 text-bearing fill sites (buttons, letter/N badges). Non-text accent fills (dots, rails, progress bars, tints) keep `bg-np`.
- **Hard-offset shadows**: `--shadow-bp` (`3px 3px 0 0`, zero blur); `shadow-ev2/ev3` re-pointed to it (54 call sites cascade). 1px shadow-as-border hairline kept for muted containers. Dark mode uses **light-edge** offsets (lit cut) since black-on-black is invisible.
- **Typography**: Space Grotesk (display/chrome) + Newsreader (reading pane H1s) loaded via Google Fonts; Inter + JetBrains Mono kept; `.spec-label` mono ALL-CAPS.
- **Textures**: `.bg-blueprint-grid` (8px — light ink 5%, dark luminous cyan 8% via `--color-grid`), `.noise` grain, `.fold-marks` corner ticks applied to Workspace, ProcessingPage, UploadPage.
- **Signature elements**: ProcessingPage rebuilt as a schematic showpiece (numbered spec rows `01.`–`18.`, self-drawing ink rail via framer-motion, dashed→solid progress line, `prefers-reduced-motion`-gated); UploadPage hero leader-line diagram (`Video → Notes → Quiz → Tutor`) + `NOTE:` red-pencil callouts in NotesView.
- **Hairline icons**: lucide `strokeWidth={1.5}` sweep (71 icons); 8 gradient avatars flattened to solid `bg-np`; soft `shadow-np/30` glow removed.
- **Press-down CTAs**: `active:translate-y-[1px]` + hard-shadow collapse on interactive elements.

Build ✓ lint ✓ (no new warnings). **QA complete (all three passes green):** Pass A code review clean, Pass B Chrome MCP (dark AND light, zero console errors, 21 screenshots), Pass C MiMo vision audit clean + fix re-verification. Artifacts in `.tmp/qa-tier5/` (screenshots/, `passB-notes.md`, `visual-review.md`, `visual-review-fix.md`).

### Dark-mode revision — "Luminous Blueprint at Night" (user-driven audit)

Follow-up to Tier 5: the dark theme originally read as a flat, muddy inverted ramp of the light tokens. Per a design audit, the dark mode was rebuilt as its own night language (contrast-validated, Pass C vision re-audited).

- **Lifted Prussian canvas**: `#0A1628` → `#0B1E3A`; wider surface ramp `#112948`/`#173352`/`#1F4063`/`#274C74` (separation 1.14→1.88:1 — panels now read as distinct layers, not one slab).
- **Shadow polarity flipped**: dark `--shadow-bp` was `rgba(0,0,0,0.45)` (invisible black-on-black) → **light-edge lit cut** `rgba(150,200,255,0.10)`, restoring the stamped-paper lift in dark; `--shadow-ev1` dark drop swapped to a blue-tinted ambient.
- **Luminous grid**: added `--color-grid` token — dark `rgba(140,200,255,0.08)` (brief-faithful glow), light `rgba(36,31,26,0.05)` (unchanged); `.bg-blueprint-grid` rewired off `color-mix(nt 6%)`.
- **Brighter red-pencil**: `np #E85D2F` (AA on canvas), `nph #FF6B38`, fill `npf #C84926` (white-on 4.73:1), tint `0.14→0.20`; scrollbar/scrollpulse tokenized off hardcoded rgba.
- **Status dots fixed for dark**: blue `#0062D1`→`#2F7FE0`, purple `#7820BC`→`#9A5CC0` (were camouflage on Prussian); green/amber/red brightened + tint alphas aligned.
- **Theme persistence fix**: added a pre-paint inline script in `index.html` reading `localStorage` so dark applies on fresh loads of non-workspace routes (was silently dropping to light on `/` and `/process/:id`); `theme-color` meta → `#0B1E3A`.
- Light mode verified unchanged (ink grid, vellum canvas, no dark bleed).

**Verification:** build ✓ lint ✓; Pass C MiMo vision re-audit PASS on all 10 fresh dark screenshots (`.tmp/qa-darkmode/visual-review.md` + `visual-review-fix.md` + `visual-review-light.md`; screenshots/). Zero console errors/warnings.

---

## Frontend Design Rebuild (Tier 4 — Signature Typography Pass)

Implemented the closing design tier per `frontend_design_roadmap.md`, in the user-approved **minimal scope** (no full 98-site type sweep).

- **Item 20 — type ramp hygiene**: added `--text-hero` (1.625rem) token to `@theme`; doc-pane H1s switched from `text-[26px]` → `text-hero` (NotesView + RevisionView, Newsreader). Remaining `text-[9px]` build-step spec prefixes → `text-3xs` (DocPanel `03/04/05` tab prefixes, UploadPage `[48px]` dimension marker). `text-[21px]` print titles and `text-[15px]` quiz questions left as deliberate reading/display sizes.
- **Item 21 — signature wordmark**: verified already consistent — the Nora panel header uses Space Grotesk with the "Nora" wordmark + `01 · TUTOR` spec label + live status dot; no change needed.
- **Item 22 — consistent states + quiz correctness**:
  - `QuizPanel` `finishQuiz` no longer swallows evaluate failures: surfaced in a `role="status"` red-tint error box with a Retry button (tokens `border-nrbr bg-nrb text-nr` — matches the existing incorrect-feedback box), incl. a distinct "came back empty" message.
  - `AIPanel` quiz switch now calls `setMode('quiz')` eagerly and only fires the "Quiz started" toast once questions actually load (`qs.length > 0`). Fixes the latent bug where a quiz-fetch error left the user silently on Tutor while still showing the success toast.
  - New `PartialContentBadge` (shared `ui` component, `role="status"`) in NotesView + RevisionView, shown when the backend's graceful-degradation marker ("partially degraded") is present in the fetched content. Assessment intentionally excluded — `/quiz/questions` returns `[]` for both degraded and never-generated chapters, which is indistinguishable frontend-only.

Build ✓ lint ✓ (only 3 pre-existing exhaustive-deps). **QA complete (all three passes green):** Pass A (web-design-guidelines review — `role="status"` regions, Retry button `FOCUS_RING`, lucide icons `aria-hidden`, error copy includes next step), Pass B (Chrome MCP — computed H1 26px Newsreader, 9px spec labels, quiz mode now switches to "QUIZ" + MCQ card renders, zero console errors, both themes, Lighthouse a11y 100 / best-practices 100), Pass C (MiMo vision audit PASS — serif H1, mono labels, MCQ card + 4 options, active Quiz tab, no spurious partial badge). Artifacts in `.tmp/qa-tier4/` (`passA-notes.md`, `passB-notes.md`, `visual-review.md`, `screenshots/`).

---

## Frontend Design Rebuild (Tier 3 — Accessibility & Web Interface Guidelines)

Implemented the a11y / Web Guidelines compliance pass per `frontend_design_roadmap.md`. **Lighthouse a11y now 100 on BOTH themes** across Study notes, Revision, Assessment, and Quiz views.

- **Real buttons + keyboard paths**: collapsed clickable `div`/`li` (Sidebar chapters/threads, QuizPanel MCQ + answer-key toggles, ReferencesPanel rows, FlashcardsPanel flip, ChapterScreenshots zoom + "Important Visuals" toggle with `aria-expanded` + `FOCUS_RING`).
- **Focus**: `FOCUS_RING` double-ring on all interactive primitives + quiz options + chapter zoom buttons; `:focus-visible` app-wide.
- **Modals**: ShortcutsModal + Lightbox are real `role="dialog"`/`aria-modal` with focus trap + restore + scroll lock; Escape-collision with the sidebar collapse guard fixed; Lightbox img got `width`/`height` + caption via `aria-describedby`.
- **Live regions / labels**: ToastContainer `aria-live="polite"`; chat streaming live-region; `aria-label` on SearchBar/ShortcutsModal icon buttons; Sidebar `<select aria-label="Select lecture">`; UploadPage sr-only `<h1>`; doc root `<div>`→`<main>`.
- **Contrast fixes**: light `nt3`/`nt4` darkened, dark `nt4` lightened; per-theme accent-text token system (`npt/ngt/nat/nrt/nblt` + `[data-theme] .text-*` overrides) + dark fill tokens `ngfill/nrfill` so white-on-green/red **quiz chips** pass AA; sidebar chapter numbers `opacity-70`→`text-nt4`; active chapter ink-on-red-tint; `.note-callout` label → `--color-npt`; AI-panel `h3`→`h2`.
- **Keyboard-resizable panels**: `role="separator"` + `aria-valuenow` + ArrowLeft/Right (16px) + Home/End — verified with real Chrome `press_key` (synthetic keyboard events don't drive React).

Build ✓ lint ✓ (only 3 pre-existing exhaustive-deps). **QA complete (all three passes green):** Pass A code review (0 critical / 4 major — all fixed: Dialog `onClose` ref-stabilized effect, ReferencesPanel `inert={collapsed}`, quiz dark chips, callout label; 27 minor/nit), Pass B Chrome MCP + Lighthouse (a11y 100 both themes on notes/revision/assessment/quiz; stale console form-field issue verified DOM-clean), Pass C MiMo vision audit (0 critical/major, 3 minor/4 nits — minor #2 already covered by accent-text tokens). Artifacts in `.tmp/qa-tier3/` (`passA-notes.md`, `passB-notes.md`, `visual-review.md`, `screenshots/`).

Remaining Lighthouse SEO gap (no meta description, invalid robots.txt) is out of scope for the frontend a11y tier.