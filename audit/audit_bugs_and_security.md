# Part 1 — Bugs & Security Audit Report

This report documents bugs, security risks, error handling gaps, resource leaks, and race conditions identified across `backend/`, `ingest/`, `visual/`, `tutor/`, `extract/`, `notes/`, `revision_notes/`, `assessment/`, and `flashcards/`.

---

## 1. Runtime Scoping & Variable Bugs

### 1.1 Unbound Scoping in Google Drive Ingestion (`ingest/ingest.py`)
- **Location**: [ingest/ingest.py:L102-L121](file:///home/gourav/coding/VScode/Projects/NorAI/ingest/ingest.py#L102-L121)
- **Issue**: `gdown.download(id=file_id, output=video_dir, quiet=False)` downloads a file into `video_dir` using Google Drive's remote filename. If `gdown` returns a string path, `downloaded_path` contains the target file. However, if `downloaded_path` is returned as a relative path or `None` on failure, `if downloaded_path is None:` raises `RuntimeError`. If it succeeds, `extract_from_local(downloaded_path, output_dir)` is called. Inside `extract_from_local` (line 376-391), `copied_video_path` is constructed as `os.path.join(video_dir, f"{filename}{Path(file_path).suffix}")`. If `downloaded_path` is already located inside `video_dir`, `shutil.copy2` is attempted on identical source and destination paths unless `os.path.abspath` matches exactly.
- **Code Snippet**:
  ```python
  # ingest/ingest.py:L118-L121
  return extract_from_local(
      downloaded_path,
      output_dir
  )
  ```
- **Remediation**: Normalize target paths explicitly and check if source and target files are identical before invoking `shutil.copy2`.

### 1.2 Import Shadowing & Re-imports in CLI Entrypoints (`flashcards/generate_flashcards.py`)
- **Location**: [flashcards/generate_flashcards.py:L177-L189](file:///home/gourav/coding/VScode/Projects/NorAI/flashcards/generate_flashcards.py#L177-L189)
- **Issue**: In `if __name__ == "__main__":`, `import flashcards.generate_flashcards as fg` re-imports the current module under `fg`, shadowing global module variables `ASSESSMENT_DIR` and `FLASHCARDS_DIR`.
- **Code Snippet**:
  ```python
  # flashcards/generate_flashcards.py:L186-L188
  import flashcards.generate_flashcards as fg
  fg.ASSESSMENT_DIR = Path(args.output_dir) / "assessment"
  fg.FLASHCARDS_DIR = Path(args.output_dir) / "flashcards"
  ```
- **Remediation**: Pass `output_dir` directly as an explicit parameter to `main()` instead of mutating module-level global variables via self-import aliases.

---

## 2. Security Analysis

### 2.1 Arbitrary Directory Traversal via `lecture_id`
- **Location**: [backend/main.py:L213-L327](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L213-L327), [backend/dependencies.py:L70-L72](file:///home/gourav/coding/VScode/Projects/NorAI/backend/dependencies.py#L70-L72)
- **Impact**: High Risk — Arbitrary local file access and deletion.
- **Vulnerability Details**: Several FastAPI endpoints accept `lecture_id` directly from user request parameters without path sanitization:
  - `GET /threads?lecture_id=...`
  - `POST /threads?lecture_id=...`
  - `GET /threads/{thread_id}?lecture_id=...`
  - `DELETE /threads/{thread_id}?lecture_id=...`
  - `GET /notes/{chapter_id}?lecture_id=...`
  - `GET /summary?chapter_id=...&lecture_id=...`
  - `GET /quiz/questions?lecture_id=...`
  - `GET /flashcards?lecture_id=...`

  `get_lecture_db_path(lecture_id)` executes:
  ```python
  # backend/dependencies.py:L70-L72
  def get_lecture_db_path(lecture_id: str) -> Path:
      return Path("outputs") / lecture_id / "tutor" / "checkpoints.sqlite"
  ```
  If `lecture_id` contains path traversal sequences such as `../../`, `Path("outputs") / lecture_id` escapes the `outputs` directory. In `delete_thread` ([backend/main.py:L318-L320](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L318-L320)), executing `DELETE FROM ...` against an arbitrary SQLite file location opens or modifies arbitrary `.sqlite` files on the host filesystem.

- **Remediation Code**:
  ```python
  def sanitize_lecture_id(lecture_id: str) -> str:
      """Ensure lecture_id is a safe alphanumeric/UUID string."""
      clean_id = Path(lecture_id).name
      if not re.match(r"^[a-zA-Z0-9_-]+$", clean_id):
          raise HTTPException(status_code=400, detail="Invalid lecture_id format")
      return clean_id
  ```

### 2.2 Unvalidated Upload Filenames in `/process`
- **Location**: [backend/main.py:L493-L508](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L493-L508)
- **Vulnerability Details**: File uploads construct target paths using `file.filename` directly:
  ```python
  # backend/main.py:L505
  file_path = upload_dir / f"{task_id}_{file.filename}"
  ```
  If `file.filename` contains path traversal characters (`../video.mp4`), `upload_dir / filename` can resolve outside `outputs/uploads`.
- **Remediation**: Use `Path(file.filename).name` or sanitize filenames with `werkzeug.utils.secure_filename` or UUID prefixes.

### 2.3 SSRF Risk in Ingestion URL Processors
- **Location**: [ingest/ingest.py:L27-L45](file:///home/gourav/coding/VScode/Projects/NorAI/ingest/ingest.py#L27-L45), [backend/main.py:L493-L518](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L493-L518)
- **Vulnerability Details**: `process_source` determines handler by checking if `is_url(source)` is True. `is_youtube_url` and `is_gdrive_url` perform substring checks (`"youtube.com" in url` or `"drive.google.com" in url`).
  - An attacker could craft a domain like `http://drive.google.com.attacker.com/video` or `http://attacker.com/?ref=youtube.com`.
  - `gdown.download` or `yt_dlp.YoutubeDL` will then execute outbound requests to the attacker-controlled server.
- **Remediation**: Validate URL schemes and strictly parse `urlparse(url).netloc` against an explicit whitelist of allowed domain names (`youtube.com`, `www.youtube.com`, `youtu.be`, `drive.google.com`).

### 2.4 Unprotected API Endpoints & Permissive CORS
- **Location**: [backend/main.py:L47-L60](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L47-L60)
- **Vulnerability Details**: The FastAPI application has no authentication or authorization middleware on high-privilege endpoints (`POST /process`, `DELETE /threads/{id}`). CORS configuration allows wildcard headers and methods with `allow_credentials=True`.

---

## 3. Error Handling Gaps

### 3.1 Silent Exception Swallowing in Orchestrator
- **Location**: [backend/orchestrator.py:L183-L195](file:///home/gourav/coding/VScode/Projects/NorAI/backend/orchestrator.py#L183-L195)
- **Issue**: Visual knowledge extraction and knowledge merging failure exceptions are logged and swallowed:
  ```python
  # backend/orchestrator.py:L185-L186
  except Exception as e:
      logger.error(f"Visual knowledge failed (continuing): {e}")
  ```
  If Stage 8 fails, `visual_objects` directory remains unpopulated. Stage 9 (`merge_all_chunks`) will either crash or attempt to merge empty directories. If Stage 9 fails, downstream outline generation and chapter building proceed with missing or corrupt data, generating silent pipeline degradations.
- **Remediation**: Explicitly verify intermediate file outputs before proceeding to dependent downstream stages, or set clear fallback default objects.

### 3.2 Database Exception Masking in `main.py`
- **Location**: [backend/main.py:L245-L246](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L245-L246), [backend/main.py:L270-L271](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L270-L271)
- **Issue**: `list_threads` and `create_thread_endpoint` wrap SQLite operations in broad `try...except Exception: pass` blocks.
  - If the database file is locked or corrupt, the endpoints silently return empty thread lists or ignore thread creation failures without informing the API caller.

---

## 4. Resource Leaks

### 4.1 SQLite Connection Leaks in Endpoint Handlers
- **Location**: [backend/main.py:L222-L246](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L222-L246)
- **Issue**: In `list_threads`:
  ```python
  # backend/main.py:L222-L245
  conn = sqlite3.connect(str(db_path), timeout=10.0)
  try:
      ...
  except Exception:
      pass
  conn.close()
  ```
  If an exception occurs prior to `conn.close()` inside nested blocks where `conn.close()` is placed outside the `finally` block, the SQLite file handle remains unclosed.
- **Remediation**: Use `with sqlite3.connect(...) as conn:` context managers consistently for all database connections.

### 4.2 Unreleased OpenCV Video Capture Objects
- **Location**: [visual/extract_frames.py:L55-L151](file:///home/gourav/coding/VScode/Projects/NorAI/visual/extract_frames.py#L55-L151)
- **Issue**: `cap = cv2.VideoCapture(str(video_path))` is opened. `cap.release()` is called at line 151. If an unhandled exception occurs inside the frame extraction `while` loop (e.g. disk full during `cv2.imwrite`), `cap.release()` is bypassed, leaking the C++ video capture handle.
- **Remediation**: Wrap `cv2.VideoCapture` operations in a `try...finally: cap.release()` block.

---

## 5. Race Conditions & Multi-Lecture Isolation

### 5.1 Unlocked Simultaneous Pipeline Execution
- **Location**: [backend/orchestrator.py:L127-L136](file:///home/gourav/coding/VScode/Projects/NorAI/backend/orchestrator.py#L127-L136), [backend/main.py:L511-L516](file:///home/gourav/coding/VScode/Projects/NorAI/backend/main.py#L511-L516)
- **Issue**: When `POST /process` is triggered, a new daemon thread is launched running `run_pipeline(task_id, ...)`. `create_lecture(task_id)` creates `outputs/{task_id}/`. However, if multiple calls are submitted with custom or legacy fixed output directories, concurrent runs overwrite the same temporary chunk and screenshot files simultaneously.

### 5.2 Default Graph Cache Lock Contention
- **Location**: [backend/dependencies.py:L24-L30](file:///home/gourav/coding/VScode/Projects/NorAI/backend/dependencies.py#L24-L30), [backend/dependencies.py:L90-L96](file:///home/gourav/coding/VScode/Projects/NorAI/backend/dependencies.py#L90-L96)
- **Issue**: When requests do not pass a `lecture_id`, all invocations fall back to `_default_graph` and `_default_lock`. Concurrent tutor chat requests across different user sessions block each other completely while `_default_lock` is held during LLM generation calls.
