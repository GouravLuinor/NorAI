# 🧠 NorAI

### From lecture video to an interactive learning workspace.

**NorAI is an end-to-end multimodal AI platform that transforms
long-form lectures into structured study notes, revision material,
assessments, flashcards, important visual references, and a
lecture-grounded AI tutor.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Gemini](https://img.shields.io/badge/Gemini-Multimodal_AI-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Workflows-1C3C3C?style=for-the-badge)](https://www.langchain.com/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B35?style=for-the-badge)](https://www.trychroma.com/)

[![Status](https://img.shields.io/badge/Status-Active_Development-orange?style=flat-square)](#-development-status)
[![PRs
Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](#-contributing)

**Lecture In → Understanding → Structure → Practice → Recall →
Conversation**

[✨ Features](#-what-norai-does) · [🎬 Demo](#-demo) · [⚙️
Architecture](#️-system-architecture) · [🔄
Pipeline](#-18-stage-processing-pipeline) · [🚀
Setup](#-getting-started) · [🗺️ Roadmap](#️-roadmap)
------------------------------------------------------------------------

## ✨ What is NorAI?

Watching a lecture is easy. **Revising it effectively is not.**

A technical lecture can contain definitions hidden in speech, code shown
only on screen, diagrams absent from the transcript, examples scattered
across timestamps, and concepts that only make sense when audio and
visuals are considered together.

Most lecture tools reduce that complexity to:

``` text
Video → Transcript → Summary
```

NorAI takes a different approach:

``` text
Lecture Video
     ↓
Speech + Visual Understanding
     ↓
Structured Knowledge
     ↓
Dynamic Chapters
     ↓
Notes + Revision + Assessment + Flashcards
     ↓
Lecture-Grounded AI Tutor
```

> **NorAI does not just summarize a lecture. It reconstructs it into a
> structured, interactive learning system.**

------------------------------------------------------------------------

## 🎬 Demo

> Add a short 10--20 second GIF showing: **lecture input → live
> processing → workspace → tutor interaction**.

```{=html}
<p align="center">
```
`<img src="docs/assets/norai-demo.gif" alt="NorAI end-to-end demo" width="900" />`{=html}
```{=html}
</p>
```

------------------------------------------------------------------------

## 🌟 What NorAI Does

  -----------------------------------------------------------------------
  Feature                             What it does
  ----------------------------------- -----------------------------------
  📝 **Study Notes**                  Detailed, chapter-aware notes
                                      generated from structured lecture
                                      knowledge

  ⚡ **Revision Notes**               High-density summaries designed for
                                      rapid review

  🧪 **Assessments**                  Chapter-specific MCQ, True/False,
                                      short-answer, and scenario-style
                                      questions

  🃏 **Flashcards**                   Recall cards with concise answers,
                                      explanations, and confidence
                                      ratings

  🖼️ **Important Visuals**            Relevant lecture frames mapped back
                                      to concepts and note sections

  🤖 **AI Tutor**                     Retrieval-grounded Q&A over
                                      lecture-specific notes and visual
                                      context

  💬 **Persistent Threads**           Lecture-scoped tutor conversations
                                      with saved history

  ✨ **Highlight & Ask**              Select text in study material and
                                      ask the tutor directly

  🔍 **Document Search**              Search generated learning material
                                      inside the workspace

  📄 **PDF Export**                   On-demand, print-ready study,
                                      revision, and assessment documents

  📚 **Multi-Lecture Workspace**      Isolated artifacts, state,
                                      retrieval indexes, and
                                      conversations per lecture
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 🧠 Why NorAI is Different

### 1. Multimodal by design

Lectures are not audio files with decorative video. NorAI separately
processes spoken explanations, timestamped transcript segments, code
visible on screen, slides, diagrams, whiteboard content, interfaces,
demonstrations, and other educationally important frames.

### 2. Dynamic lecture structure

NorAI does **not** assume every lecture has a fixed number of chapters.
The outline stage determines lecture title, chapter count, boundaries,
titles, focus concepts, and source chunk membership.

### 3. Lecture-scoped retrieval

Every lecture gets isolated artifacts and retrieval context. Tutor
answers are grounded in the active lecture instead of a shared global
knowledge pool.

### 4. Built for active learning

``` text
Understand → Revise → Test → Recall → Ask
```

Notes, revision, assessments, flashcards, and tutoring live in one
connected workspace.

------------------------------------------------------------------------

## 🏗️ System Architecture

``` text
┌────────────────────────────────────────────────────────────────────┐
│                    React + TypeScript Frontend                     │
│                                                                    │
│  Lecture Sidebar  │  Notes / Revision / Assessment  │  AI Panel   │
│  Chapters         │  Search / Highlight & Ask        │  Tutor      │
│  Lectures         │  Important Visuals               │  Quiz       │
│  Threads          │  PDF Export                      │  Flashcards │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ REST + Polling
┌──────────────────────────────▼─────────────────────────────────────┐
│                         FastAPI Backend                            │
│  Lecture APIs  │  Pipeline Status  │  Educational APIs  │ Tutor   │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────┐
│                    Async Pipeline Orchestrator                     │
│ Ingest → Transcribe → Extract → Vision → Merge → Structure        │
│        → Notes → Revision → Assessment → Flashcards → Index       │
└───────────────────┬────────────────────────────┬───────────────────┘
                    │                            │
          ┌─────────▼─────────┐        ┌─────────▼────────────────┐
          │ Lecture Artifacts │        │ Retrieval / Tutor Layer │
          │ Notes, Revision   │        │ LangGraph, ChromaDB     │
          │ Assessments       │        │ Embeddings              │
          │ Flashcards        │        │ Note + Screenshot RAG   │
          │ Screenshots       │        │ Persistent Memory       │
          └───────────────────┘        └──────────────────────────┘
```

------------------------------------------------------------------------

## 🔄 18-Stage Processing Pipeline

  ------------------------------------------------------------------------
                         Stage Process               Purpose
  ---------------------------- --------------------- ---------------------
                            01 Ingestion         Resolve source and
                                                     create lecture-scoped
                                                     media artifacts

                            02 Transcription     Convert audio into
                                                     timestamped
                                                     transcript segments

                            03 Chunking          Build
                                                     context-preserving
                                                     transcript chunks

                            04 **Knowledge           Extract concepts,
                               Extraction**          explanations,
                                                     formulas, code, and
                                                     relationships

                            05 Frame Extraction  Sample the lecture's
                                                     visual stream

                            06 Scene Detection   Reduce redundant
                                                     frames and preserve
                                                     meaningful scene
                                                     changes

                            07 **Chunk ↔ Screenshot  Associate transcript
                               Mapping**             chunks with relevant
                                                     visuals

                            08 **Visual              Analyze selected
                               Understanding**       frames with
                                                     multimodal AI

                            09 Knowledge Merging Fuse textual and
                                                     visual knowledge

                            10 **Outline             Infer title, chapter
                               Generation**          count, boundaries,
                                                     and focus concepts

                            11 Chapter Building  Materialize
                                                     chapter-specific
                                                     knowledge

                            12 Study Notes       Generate detailed
                                                     chapter-aware notes

                            13 **Screenshot          Select educationally
                               Selection**           important visuals

                            14 Revision Notes    Generate compact
                                                     revision material

                            15 Assessment        Generate
                                                     chapter-specific
                                                     questions and answer
                                                     data

                            16 Flashcards        Convert assessment
                                                     knowledge into recall
                                                     cards

                            17 Tutor Index       Embed lecture notes
                                                     into a persistent
                                                     retrieval index

                            18 Screenshot Index  Index selected visual
                                                     explanations for
                                                     tutor retrieval
  ------------------------------------------------------------------------

------------------------------------------------------------------------

## 🔬 Inside the Multimodal Pipeline

### 🎙️ Speech Understanding

NorAI uses **Faster-Whisper** and preserves timestamp-aware transcript
segments.

``` text
Audio → Timestamped Transcript → Context-Preserving Chunks → Structured Knowledge
```

### 📸 Visual Understanding

``` text
Video → Frame Extraction → Scene Detection → Keyframes
      → Temporal Chunk Mapping → Multimodal Analysis
```

Visual analysis can capture code snippets, diagrams, formulas, slides,
architecture drawings, UI demonstrations, and worked examples.

### 🧬 Knowledge Fusion

``` text
Spoken Knowledge ─────────┐
                          ├──► Unified Lecture Knowledge
Visual Knowledge ─────────┘
```

### 🧭 Dynamic Outline Generation

The lecture outline is generated from processed knowledge itself. A
lecture can become four chapters, six chapters, or another structure
depending on content.

``` json
{
  "lecture_title": "Example Lecture",
  "chapters": [
    {
      "chapter_id": 1,
      "title": "Foundations",
      "focus_concepts": ["Concept A", "Concept B"],
      "start_chunk": 0,
      "end_chunk": 3,
      "chunk_ids": [0, 1, 2, 3]
    }
  ]
}
```

------------------------------------------------------------------------

## 🤖 Lecture-Grounded AI Tutor

``` text
User Question
      ↓
Lecture-Scoped Retrieval
      ↓
Relevant Note Chunks + Screenshot Context + Conversation State
      ↓
Grounded Tutor Response
```

The tutor layer includes:

-   **LangGraph** for stateful AI workflows
-   **ChromaDB** for persistent vector retrieval
-   lecture-specific note indexes
-   screenshot-caption retrieval
-   persistent conversation threads
-   active lecture identity
-   contextual tools and commands

### ✨ Highlight & Ask

``` text
Study Notes → Select Text → Highlight & Ask → Tutor with selected context
```

------------------------------------------------------------------------

## 🖥️ Learning Workspace

```{=html}
<p align="center">
```
`<img src="docs/assets/workspace.png" alt="NorAI learning workspace" width="900" />`{=html}
```{=html}
</p>
```
### 📝 Study Notes

Chapter-aware content with card-based sections, callouts, tables,
syntax-highlighted code, mathematical notation, and selected lecture
visuals.

### ⚡ Revision Notes

Condensed material for exam revision, interview preparation, pre-class
review, and quick concept refresh.

### 🧪 Assessment

Generated Multiple Choice, True/False, Short Answer, and Scenario-Based
questions.

### 🃏 Flashcards

Cards contain a front, back, explanation, and `Again` / `Hard` / `Good`
/ `Easy` confidence ratings with review statistics.

------------------------------------------------------------------------

## 📚 Multi-Lecture by Design

Workspace routes are lecture-specific:

``` text
/workspace/{lectureId}
```

Artifacts are isolated:

``` text
outputs/
├── lectures.json
├── <lecture-id-a>/
│   ├── audio/
│   ├── videos/
│   ├── metadata/
│   ├── transcripts/
│   ├── chunks/
│   ├── objects/
│   ├── visual_objects/
│   ├── merged_objects/
│   ├── mappings/
│   ├── chapters/
│   ├── notes/
│   ├── revision/
│   ├── assessment/
│   ├── flashcards/
│   ├── screenshots/
│   └── tutor/
└── <lecture-id-b>/
    └── ...
```

Lecture identity propagates through routes, Zustand stores, backend
requests, documents, assessments, flashcards, screenshots, tutor
indexes, conversation threads, and PDF generation.

------------------------------------------------------------------------

## 📄 On-Demand PDF Generation

NorAI supports downloadable Study Notes, Revision Notes, and
Assessments.

``` text
User clicks PDF
      ↓
Backend gathers lecture-specific data
      ↓
Print data injected into React print page
      ↓
Browser renders document and images
      ↓
PDF generated on demand
```

PDFs are generated when requested rather than during every pipeline run.

------------------------------------------------------------------------

## 🛠️ Tech Stack

  -----------------------------------------------------------------------
  Layer                   Technology              Role
  ----------------------- ----------------------- -----------------------
  **Frontend**            React, TypeScript       Interactive learning
                                                  workspace

  **Build Tooling**       Vite                    Frontend development
                                                  and bundling

  **Styling**             Tailwind CSS            UI system

  **State**               Zustand                 Lecture, chapter, and
                                                  workspace state

  **Routing**             React Router            Lecture-aware
                                                  navigation

  **Documents**           React Markdown, KaTeX   Markdown and math
                                                  rendering

  **Backend**             FastAPI, Uvicorn        APIs and pipeline
                                                  integration

  **Pipeline**            Python 3.12             Core orchestration

  **AI**                  Google Gemini           Text generation and
                                                  multimodal
                                                  understanding

  **AI Workflows**        LangChain, LangGraph    Model integration and
                                                  stateful tutor flows

  **Speech**              Faster-Whisper          Lecture transcription

  **Vector Store**        ChromaDB                Persistent semantic
                                                  retrieval

  **Visual Processing**   OpenCV                  Frame and image
                                                  processing

  **Media**               FFmpeg                  Audio/video processing

  **Video Sources**       yt-dlp                  Online video ingestion

  **Storage**             File system, SQLite,    Artifacts, conversation
                          ChromaDB                state, vectors
  -----------------------------------------------------------------------

> Exact model choices can evolve while NorAI is under active
> development.

------------------------------------------------------------------------

## 🗂️ Repository Structure

``` text
NorAI/
├── backend/
│   ├── main.py
│   ├── orchestrator.py
│   ├── lecture_registry.py
│   ├── generate_pdfs.py
│   └── routers/
├── ingest/
├── transcription/
├── chunking/
├── extract/
│   ├── extractor.py
│   └── merger.py
├── visual/
│   ├── extract_frames.py
│   ├── scene_detector.py
│   ├── mapper.py
│   └── visual_extractor.py
├── notes/
│   ├── outline_generator.py
│   ├── outline_reviewer.py
│   ├── chapter_builder.py
│   ├── chapter_clusterer.py
│   ├── chapter_structurer.py
│   ├── notes_generator.py
│   └── screenshot_selector.py
├── revision_notes/
├── assessment/
├── flashcards/
│   └── generate_flashcards.py
├── tutor/
│   ├── graph.py
│   ├── state.py
│   ├── nodes.py
│   ├── nodes_retrieval.py
│   ├── retriever.py
│   ├── embedding.py
│   ├── memory.py
│   ├── quiz_nodes.py
│   └── tools.py
├── retrieval/
├── embeddings/
├── vectordb/
├── frontend/
│   ├── src/
│   ├── public/
│   └── vite.config.ts
├── docs/
├── outputs/
├── PROJECT_PROGRESS.md
└── requirements.txt
```

------------------------------------------------------------------------

## 🚀 Getting Started

### Prerequisites

-   Python 3.12+
-   Node.js 18+
-   npm
-   FFmpeg
-   Git
-   Google Gemini API key

### 1. Clone

``` bash
git clone <YOUR_REPOSITORY_URL>
cd NorAI
```

### 2. Create Python environment

``` bash
python3 -m venv venv
source venv/bin/activate
```

Windows PowerShell:

``` powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

``` bash
pip install -r requirements.txt
```

### 4. Configure environment

Create `.env`:

``` env
GEMINI_API_KEY=your_api_key_here
```

> Never commit secrets or API keys.

### 5. Install frontend dependencies

``` bash
cd frontend
npm install
cd ..
```

### 6. Start backend

``` bash
uvicorn backend.main:app --reload --port 8000
```

API docs:

``` text
http://localhost:8000/docs
```

### 7. Start frontend

``` bash
cd frontend
npm run dev
```

Open:

``` text
http://localhost:5173
```

------------------------------------------------------------------------

## 🧪 Development Status

NorAI is under **active development**.

### Implemented

-   [x] Lecture video ingestion
-   [x] Audio extraction
-   [x] Faster-Whisper transcription
-   [x] Timestamp-aware chunking
-   [x] Structured knowledge extraction
-   [x] Frame extraction
-   [x] Scene detection
-   [x] Chunk-to-screenshot mapping
-   [x] Multimodal visual understanding
-   [x] Text + visual knowledge merging
-   [x] Dynamic lecture outline generation
-   [x] Dynamic chapter construction
-   [x] Study notes generation
-   [x] Revision notes generation
-   [x] Assessment generation
-   [x] Flashcard generation
-   [x] Important screenshot selection
-   [x] Multi-lecture artifact isolation
-   [x] Lecture registry
-   [x] FastAPI integration
-   [x] React + TypeScript workspace
-   [x] Lecture switching
-   [x] Processing progress tracking
-   [x] Lecture-specific ChromaDB indexes
-   [x] Screenshot-context retrieval
-   [x] Persistent tutor threads
-   [x] Highlight & Ask
-   [x] Document search
-   [x] On-demand PDF generation

------------------------------------------------------------------------

## 🧩 Engineering Challenges

NorAI is also a practical exploration of real-world AI systems
engineering:

-   orchestrating long-running multi-stage AI pipelines
-   preventing blocking workloads from starving API progress endpoints
-   coordinating frontend polling with backend task state
-   isolating artifacts across lectures
-   preventing cross-lecture frontend state leakage
-   handling malformed JSON from LLM responses
-   retrying failed structured generation
-   mapping timestamped transcript chunks to visual keyframes
-   merging textual and visual knowledge
-   dynamically determining chapter counts
-   keeping screenshots available in browser-rendered PDFs
-   generating flashcards in lecture-scoped subprocesses
-   propagating output directories across subprocess boundaries
-   maintaining lecture-specific vector indexes
-   indexing screenshot explanations separately from notes
-   tolerating optional-stage failures without discarding the full
    pipeline
-   rendering Markdown, code, tables, and math consistently
-   preserving tutor conversation state

------------------------------------------------------------------------

## 🧭 Design Principles

1.  **Ground everything in the lecture** --- generated material should
    remain connected to source content.
2.  **Treat visuals as knowledge** --- a lecture is not just a
    transcript.
3.  **Keep lectures isolated** --- artifacts, indexes, conversations,
    and frontend state follow lecture identity.
4.  **Prefer dynamic structure** --- different lectures require
    different chapter boundaries and counts.
5.  **Design for partial failure** --- one optional stage should not
    destroy all successful work.
6.  **Build for learning, not summarization** --- help learners
    understand, revise, test, recall, and ask.

------------------------------------------------------------------------

## 🗺️ Roadmap

### Near Term

-   [ ] Authentication and user profiles
-   [ ] Production-grade background job queue
-   [ ] Pipeline resume and recovery
-   [ ] Cloud object storage
-   [ ] Dockerized deployment
-   [ ] Better mobile responsiveness
-   [ ] Structured-output hardening for LLM stages
-   [ ] Processing observability and cost analytics
-   [ ] Improved tutor citations and source navigation
-   [ ] Automated integration tests for full lecture runs

### Future

-   [ ] Cross-lecture knowledge retrieval
-   [ ] Course-level organization
-   [ ] Spaced repetition scheduling
-   [ ] Adaptive expertise tracking
-   [ ] Personalized revision plans
-   [ ] Weak-concept detection
-   [ ] Learning analytics
-   [ ] Knowledge graph visualization
-   [ ] Collaborative study rooms
-   [ ] Multilingual lecture workflows
-   [ ] Adaptive assessments

------------------------------------------------------------------------

## 📊 Performance & Cost

Pipeline runtime and model usage depend on lecture duration, transcript
chunk count, extracted keyframes, visual-analysis retries, selected
model, API rate limits, local hardware, and network conditions.

For that reason, this README intentionally avoids promising fixed
processing times or fixed API costs.

> Add reproducible benchmarks here with lecture duration, hardware,
> model, frame count, and pipeline configuration.

------------------------------------------------------------------------

## 🤝 Contributing

Contributions, bug reports, experiments, and architecture discussions
are welcome.

``` bash
git checkout -b feature/your-feature
git add .
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a Pull Request.

Especially valuable areas include retrieval quality, multimodal
evaluation, structured generation reliability, frontend UX,
accessibility, pipeline recovery, testing, observability, and
deployment.

------------------------------------------------------------------------

## 🔐 Security Notes

Before public deployment:

-   keep API keys in environment variables
-   never commit `.env`
-   validate uploaded files
-   enforce upload size limits
-   add authentication and authorization
-   add production rate limiting
-   isolate user-owned lecture artifacts
-   review generated content before high-stakes use

------------------------------------------------------------------------


## 👨‍💻 Author

Built by **Gourav Kumar Singh**

NorAI explores the intersection of:

-   Artificial Intelligence
-   Multimodal Learning
-   Retrieval-Augmented Generation
-   Full-Stack Engineering
-   Educational Technology

------------------------------------------------------------------------

## ⭐ If NorAI interests you, consider starring the repository.

**From passive watching to active learning.**

`Video → Understanding → Structure → Practice → Recall → Conversation`

Built through iteration, experimentation, and a lot of debugging.
