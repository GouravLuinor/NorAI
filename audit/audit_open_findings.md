# Part 4 — Open Architectural Findings & Rebuild Recommendations

This report surfaces structural anti-patterns, technical debt, hardcoded configurations, dead code, and dependency risks identified during the codebase audit.

---

## 1. Rate Limiting Architecture Deficiencies

### Fragmented Rate Limiter Instances
- **Location**:
  - [extract/extractor.py:L22-L23](file:///home/gourav/coding/VScode/Projects/NorAI/extract/extractor.py#L22-L23)
  - [visual/visual_extractor.py:L21-L22](file:///home/gourav/coding/VScode/Projects/NorAI/visual/visual_extractor.py#L21-L22)
  - [notes/screenshot_selector.py:L20-L21](file:///home/gourav/coding/VScode/Projects/NorAI/notes/screenshot_selector.py#L20-L21)
  - [notes/notes_generator.py:L31-L32](file:///home/gourav/coding/VScode/Projects/NorAI/notes/notes_generator.py#L31-L32)
  - [revision_notes/revision_generator.py:L38-L39](file:///home/gourav/coding/VScode/Projects/NorAI/revision_notes/revision_generator.py#L38-L39)
  - [assessment/assessment_generator.py:L56-L57](file:///home/gourav/coding/VScode/Projects/NorAI/assessment/assessment_generator.py#L56-L57)

- **Issue**: Each Python module creates its own isolated instance of `RPMRateLimiter(max_calls=12)`:
  ```python
  _limiter = RPMRateLimiter(max_calls=12)
  ```
  When multi-threading (`ThreadPoolExecutor(max_workers=4)`) is used inside a module or across stages, each worker thread or module tracks rate limits independently. Their combined requests hit the Gemini API simultaneously, triggering HTTP `429 Too Many Requests` rate limit exceptions and forcing costly retry loops (`MAX_RETRIES = 8`).
- **Rebuild Recommendation**: Implement a single global thread-safe rate limiter singleton or async queue manager shared across the entire application process.

---

## 2. Database & State Management Anti-Patterns

### 2.1 Unconfigured SQLite WAL Mode in Tutor Checkpointer
- **Location**: [backend/dependencies.py:L38](file:///home/gourav/coding/VScode/Projects/NorAI/backend/dependencies.py#L38), [backend/main.py:L70](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L70)
- **Issue**: SQLite connections to `checkpoints.sqlite` use standard rollback journal mode without enabling Write-Ahead Logging (WAL).
  - Under concurrent SSE chat streaming (`POST /chat/stream`) and state inspection (`GET /threads/{id}`), SQLite locks the database file exclusively, throwing `sqlite3.OperationalError: database is locked`.
- **Rebuild Recommendation**: Execute `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;` on every SQLite database connection upon initialization.

### 2.2 Global File-Based Registry Lock Contention
- **Location**: [backend/lecture_registry.py:L16-L26](file:///home/gourav/coding/VScode/Projects/NorAI/backend/lecture_registry.py#L16-L26)
- **Issue**: `outputs/lectures.json` is opened, loaded, updated, and overwritten directly on disk during lecture creation and title updates without file locking (`fcntl` or `threading.Lock`). Concurrent pipeline runs risk corrupting `lectures.json`.

---

## 3. Unused & Dead Code

### 3.1 Unused PDF Builder Modules
- **Location**:
  - `assessment/assessment_pdf_builder.py`
  - `notes/study_pdf_builder.py`
  - `revision_notes/revision_pdf_builder.py`
  - `backend/generate_pdfs.py`
- **Issue**: These reportlab PDF generation scripts were superseded by frontend markdown rendering. They remain in the codebase, introducing unused dependencies (`reportlab`) and maintenance overhead.
- **Rebuild Recommendation**: Remove dead PDF generation modules from the core repository.

### 3.2 Legacy Test & CLI Scripts in Root
- **Location**:
  - `test_api.py`
  - `visual.txt`
  - `tree.txt`
- **Issue**: Root directory contains orphan test scripts and text dumps.

---

## 4. Hardcoded Parameter Drift Across Modules

| Parameter | Location | Value | Recommendation |
|-----------|----------|-------|----------------|
| **Gemini Model Name** | `notes/screenshot_selector.py:L35` | `"gemini-3.1-flash-lite-preview"` | Move to central `config.py` |
| **Gemini Model Name** | `assessment/assessment_generator.py:L70` | `"gemini-3.1-flash-lite-preview"` | Move to central `config.py` |
| **Gemini Model Name** | `tutor/config.py:L7` | `"gemini-2.5-flash"` | Inconsistent tutor model! |
| **Frame Interval** | `visual/extract_frames.py:L23` | `8` seconds | Configurable parameter |
| **Chunk Size** | `chunking/chunk.py:L15` | `15` segments | Configurable parameter |
| **Max Retries** | Multiple files | `8` | Centralize backoff policy |

---

## 5. Summary of Architectural Rebuild Principles

1. **Unified Pipeline Engine**: Replace linear synchronous script calls with an asynchronous DAG workflow runner (e.g. `Temporal`, `Prefect`, or custom `asyncio` DAG engine).
2. **Centralized Configuration Service**: Establish a single `config.py` storing model names, chunk sizes, rate limits, and output directories.
3. **Structured Single-Pass Prompting**: Consolidate text/visual extraction, notes generation, and quiz creation into minimal structured JSON calls to maximize token efficiency.
4. **Database Modernization**: Upgrade from SQLite checkpointing to PostgreSQL or SQLite with strict WAL configuration and connection pooling.
