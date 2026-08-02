# NorAI Comprehensive Audit Report — Executive Summary

## Overview
This audit provides a deep technical review of the **NorAI** codebase (video ingestion, transcription, chunking, multimodal knowledge extraction, notes generation, assessment, flashcards, and tutor backend). The audit evaluates code safety, security vulnerabilities, runtime bug risks, architectural pipeline bottlenecks, real lecture data metrics, and structural recommendations for a full architectural rebuild.

The complete findings are organized into 4 detailed audit reports:

1. 📄 **[Part 1: Bugs & Vulnerabilities](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_bugs_and_security.md)**
   - Analysis of variable scoping risks, path traversal vulnerabilities, missing API authorization, SSRF risks in ingestion, error handling gaps, resource leaks, and race conditions.
2. 📄 **[Part 2: Architecture & Pipeline Optimization](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_architecture_optimization.md)**
   - Formal evaluation of 6 optimization hypotheses to collapse the pipeline from ~128 LLM API calls down to 15–20 calls while unlocking concurrent stage execution.
3. 📄 **[Part 3: Real Data Extraction & Benchmarks](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_real_data_extraction.md)**
   - Benchmark data extracted directly from real 25-minute lecture run (`outputs/5154a6ea-ccfe-4698-a9e1-799d4a5fec75/`), including chunk statistics, screenshot survival counts per chapter, exact API call breakdown, and Files API latency analysis.
4. 📄 **[Part 4: Open Architectural Findings](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_open_findings.md)**
   - High-impact architectural improvements: fragmented rate-limiter instances, hardcoded configurations, dead PDF builder code, and SQLite lock bottlenecks.

---

## 1-Paragraph Summaries of Audit Reports

### [Audit Part 1: Bugs & Vulnerabilities](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_bugs_and_security.md)
Identifies critical security and reliability flaws across the backend and processing modules. Key findings include an **arbitrary directory traversal vulnerability** via the `lecture_id` parameter in `backend/main.py` allowing file access and deletion outside intended paths, **unvalidated upload filenames** susceptible to path injection, **SSRF risks** during URL ingestion in `ingest/ingest.py`, and **unprotected backend endpoints** lacking authentication. Additionally, error handling gaps in `backend/orchestrator.py` swallow visual pipeline failures and allow corrupt state propagation, while unclosed SQLite connections in `list_threads` create connection leaks.

### [Audit Part 2: Architecture & Pipeline Optimization](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_architecture_optimization.md)
Evaluates 6 core architectural hypotheses for pipeline streamline. Confirms that H.264 video conversion is direct, but identifies **Stage 2/3 (Transcription/Chunking)** and **Stage 5/6 (Frame Extraction/Scene Detection)** as completely independent stages that should run concurrently to save ~40% wall-clock time. Proposes leveraging Gemini 3.1 Flash-Lite's 1M context window to merge Knowledge Extraction, Visual Extraction, and Outline Generation into unified chapter calls, merging Notes/Revision/Assessment into single structured-output passes, and converting Flashcard generation into a 0-call deterministic Python transformation.

### [Audit Part 3: Real Data Extraction](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_real_data_extraction.md)
Presents concrete baseline metrics from processing a 24m56s lecture video (35 chunks, 10 chapters, 66 candidate keyframes). A typical chunk averages 127 words (165 tokens). Total pipeline execution incurred **128 separate LLM API calls** and uploaded 66 images sequentially to Gemini Files API. Demonstrates that replacing sequential Files API uploads with inline JPEG bytes or concurrent async uploads will save 90–120 seconds per lecture run alone.

### [Audit Part 4: Open Architectural Findings](file:///home/gourav/coding/VScode/Projects/NorAI/audit/audit_open_findings.md)
Highlights structural anti-patterns and technical debt across the project. Finds that rate limiters (`RPMRateLimiter`) are instantiated locally per module rather than shared globally, causing concurrent threads to breach Gemini API rate limits. Identifies dead PDF builder scripts (`assessment_pdf_builder.py`, `study_pdf_builder.py`), unconfigured SQLite WAL mode causing `database is locked` errors during tutor queries, and scattered hardcoded parameters across 6 separate python files.
