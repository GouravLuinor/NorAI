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

Last Updated:

**Week 11 Complete**

**NorAI v1.1 — End-to-End Multimodal Learning Platform Complete**