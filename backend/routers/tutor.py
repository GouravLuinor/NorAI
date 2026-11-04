"""
backend/routers/tutor.py — AI-tutor chat + conversation-thread endpoints (P5.1).

Extracted verbatim from main.py; the app mounts this router with no prefix,
so paths are unchanged (/chat, /chat/stream, /threads*).

Indirection note: handlers call tutor_deps.ainvoke_tutor /
tutor_deps.astream_tutor_tokens (backend.dependencies is the canonical
patch point for offline tests), NOT module-level `from ... import` copies.
"""

import asyncio
import json as json_lib
import logging
import re
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend import dependencies as tutor_deps
from backend import transcript
from backend.access import (
    _DEMO_TURNS_DAILY,
    _effective_persona_instructions,
    _flush_tutor_usage_async,
    _is_free_demo_access,
    _is_guest,
    check_guest_tutor_cap,
    ensure_lecture_access,
    get_guest_remaining_questions,
)
from backend.demo_suggested_qa import (
    get_cached_demo_qa,
    get_suggested_questions_for_lecture,
)
from backend.auth import get_current_user_optional
from backend.db.database import get_db
from backend.db.models import User
from backend.dependencies import (
    ThreadDeletedError,
    _aget_or_create_lecture_graph,
    configure_sqlite,
    get_lecture_db_path,
    sanitize_lecture_id,
)
from backend.logging_config import bind
from config import DEMO_LECTURE_IDS, dev_access

router = APIRouter()


def _get_user_scope(user: Optional[User], guest_id: Optional[str] = None) -> str:
    """Return user scope ID for partitioning demo lectures."""
    if user and getattr(user, "id", None) and not str(user.id).startswith("guest-"):
        return str(user.id)
    if guest_id:
        return f"guest-{guest_id}"
    return "guest"


def _get_scoped_thread_id(
    lecture_id: Optional[str],
    thread_id: str,
    user: Optional[User],
    guest_id: Optional[str] = None,
) -> str:
    """Return scoped thread ID for storage in LangGraph checkpointer.
    For shared demo lectures, conversations are scoped per-user so they never leak across users.
    For user-uploaded lectures, thread_id is unchanged.
    """
    clean_id = sanitize_lecture_id(lecture_id or "default")
    if clean_id in DEMO_LECTURE_IDS or clean_id == "default":
        user_scope = _get_user_scope(user, guest_id)
        return f"{user_scope}:{thread_id}"
    return thread_id


# Thread/message ids are client-generated ("thread-<ms>", "msg-<ms>-<rand>").
# Constrain them: they become SQLite keys and part of the scoped thread id.
_ID_PATTERN = r"^[A-Za-z0-9_.-]{1,100}$"

# Must match the client's stripSources() (frontend/src/lib/references.ts):
# only a Sources *header* starts the appendix. The previous pattern also cut at
# any mid-sentence "sources" ("renewable sources of energy…"), so an answer
# shown in full while streaming came back truncated after a reload.
_SOURCES_RE = re.compile(r"(\*\*Sources\*\*|\n[ \t]*Sources\s*[:•]|\n[ \t]*Sources\s*\n)", re.IGNORECASE)


def _strip_sources(text: str) -> str:
    text = str(text)
    match = _SOURCES_RE.search(text)
    return (text[: match.start()] if match else text).strip()


class CreateThreadRequest(BaseModel):
    thread_id: str | None = None

class ChatRequest(BaseModel):
    thread_id: str = Field(pattern=_ID_PATTERN)
    user_question: str = Field(min_length=1, max_length=8000)
    lecture_title: str = ""
    lecture_id: str | None = None   # ← new field
    message_id: str | None = Field(default=None, pattern=_ID_PATTERN)
    study_mode: str = "default"
    persona_instructions: str = ""

class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: list
    retrieved_images: list
    verified_citations: list = []   # P3.3
    chapter_id: int | None
    thread_id: str


@router.get("/lectures/{lecture_id}/suggested-questions")
async def get_suggested_questions(
    lecture_id: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Return pre-cached canonical questions and guest question quota for a demo lecture."""
    clean_id = sanitize_lecture_id(lecture_id)
    guest_id = request.headers.get("x-guest-id")
    is_guest = user is None or _is_guest(user)
    return {
        "lecture_id": clean_id,
        "suggested_questions": get_suggested_questions_for_lecture(clean_id),
        "is_guest": is_guest,
        "guest_questions_remaining": get_guest_remaining_questions(guest_id) if is_guest else None,
    }


@router.post("/chat")
async def chat(
    req: ChatRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
        clean_id = sanitize_lecture_id(req.lecture_id or "default")
        guest_id = request.headers.get("x-guest-id")

        # Phase D: Cached suggested QA on demo lectures returns immediately with zero Gemini tokens.
        if clean_id in DEMO_LECTURE_IDS or clean_id == "default":
            cached_res = get_cached_demo_qa(clean_id, req.user_question)
            if cached_res is not None:
                if user is None and not guest_id and not dev_access():
                    raise HTTPException(status_code=401, detail="Authentication required to use AI Tutor")

                scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user, guest_id)
                db_path = tutor_deps.turn_db_path(clean_id)
                msg_id = req.message_id or f"msg-{int(time.time() * 1000)}"
                ans = cached_res["answer"]

                # Persist turn to transcript & user_threads
                await asyncio.to_thread(tutor_deps._register_thread_if_needed, db_path, scoped_thread_id)
                await asyncio.to_thread(transcript.append_turn, db_path, scoped_thread_id, msg_id, req.user_question, ans, [])

                return {
                    "answer": ans,
                    "assistant_message_id": transcript.assistant_id_for(msg_id),
                    "retrieved_chunks": [],
                    "retrieved_images": [],
                    "verified_citations": cached_res.get("verified_citations", []),
                    "chapter_id": None,
                    "thread_id": req.thread_id,
                    "cached": True,
                }

        if clean_id not in DEMO_LECTURE_IDS and clean_id != "default":
            if user is None:
                raise HTTPException(status_code=401, detail="Authentication required to use AI Tutor")
        else:
            # Demo lecture live question: check visitor cap (5/day) & global cap (100/day)
            if user is None or _is_guest(user):
                if not dev_access():
                    check_guest_tutor_cap(clean_id, guest_id)

        # P6.4 / Phase D: chat is a tutor-gated write — owner, share link with tutor,
        # or guest visitor on demo lectures (capped at 5 questions/day).
        await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True, guest_id=guest_id)
        # P1.1: demo/default lectures cost real Gemini tokens with no quota
        # attached — bound anonymous/guest usage with a global daily budget.
        if _is_free_demo_access(req.lecture_id, user) and not _DEMO_TURNS_DAILY.check_and_increment("global"):
            raise HTTPException(
                status_code=429,
                detail="The demo tutor is at capacity today. Please sign up and add "
                       "your own lecture to continue learning.",
            )
        # P6.5: diff the tutor ledger across this turn so we can meter its cost.
        from backend.usage_ledger import snapshot_usage, diff_usage
        from backend.usage import record_tutor_turn

        _tutor_before = snapshot_usage()
        scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user, guest_id)
        result = await tutor_deps.ainvoke_tutor(
            thread_id=scoped_thread_id,
            user_question=req.user_question,
            lecture_title=req.lecture_title,
            lecture_id=req.lecture_id,
            message_id=req.message_id,
            study_mode=req.study_mode,
            persona_instructions=await _effective_persona_instructions(
                req.persona_instructions, user, db, req.lecture_id
            ),
        )
        if isinstance(result, dict) and "thread_id" in result:
            result["thread_id"] = req.thread_id
        await _flush_tutor_usage_async(user, req.lecture_id or "default", _tutor_before, diff_usage)
        return result
    except ThreadDeletedError:
        # P2.2: user-input condition, not a server fault — 409, not 500.
        raise HTTPException(status_code=409, detail="This conversation was deleted. Please start a new one.")
    except HTTPException as e:
        # P6.4: let access-gate 404s (unshared / tutor-disabled) propagate as-is.
        raise e
    except Exception as e:
        logging.getLogger("norai").exception("POST /chat failed")
        raise HTTPException(status_code=500, detail="Internal error processing your request")




@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
    clean_id = sanitize_lecture_id(req.lecture_id or "default")
    guest_id = request.headers.get("x-guest-id")

    # Phase D: Cached suggested QA on demo lectures streams immediately with zero Gemini tokens.
    if clean_id in DEMO_LECTURE_IDS or clean_id == "default":
        cached_res = get_cached_demo_qa(clean_id, req.user_question)
        if cached_res is not None:
            if user is None and not guest_id and not dev_access():
                raise HTTPException(status_code=401, detail="Authentication required to use AI Tutor")

            scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user, guest_id)
            db_path = tutor_deps.turn_db_path(clean_id)
            msg_id = req.message_id or f"msg-{int(time.time() * 1000)}"
            ans = cached_res["answer"]

            # Persist turn to transcript & user_threads
            await asyncio.to_thread(tutor_deps._register_thread_if_needed, db_path, scoped_thread_id)
            await asyncio.to_thread(transcript.append_turn, db_path, scoped_thread_id, msg_id, req.user_question, ans, [])

            async def cached_event_generator():
                words = ans.split(" ")
                for i in range(0, len(words), 4):
                    chunk = " ".join(words[i:i + 4]) + (" " if i + 4 < len(words) else "")
                    yield f"data: {json_lib.dumps({'t': chunk})}\n\n"
                    await asyncio.sleep(0.01)
                final_payload = {
                    "final": {
                        "answer": ans,
                        "assistant_message_id": transcript.assistant_id_for(msg_id),
                        "retrieved_chunks": [],
                        "retrieved_images": [],
                        "verified_citations": cached_res.get("verified_citations", []),
                        "chapter_id": None,
                        "thread_id": req.thread_id,
                        "cached": True,
                    }
                }
                yield f"data: {json_lib.dumps(final_payload)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                cached_event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    if clean_id not in DEMO_LECTURE_IDS and clean_id != "default":
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required to use AI Tutor")
    else:
        # Demo lecture live question: check visitor cap (5/day) & global cap (100/day)
        if user is None or _is_guest(user):
            if not dev_access():
                check_guest_tutor_cap(clean_id, guest_id)

    await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True, guest_id=guest_id)
    # P1.1: demo/default daily budget (see POST /chat).
    if _is_free_demo_access(req.lecture_id, user) and not _DEMO_TURNS_DAILY.check_and_increment("global"):
        raise HTTPException(
            status_code=429,
            detail="The demo tutor is at capacity today. Please sign up and add "
                   "your own lecture to continue learning.",
        )

    async def event_generator():
        try:
            # P6.5: snapshot the tutor ledger before the turn (metered after).
            from backend.usage_ledger import snapshot_usage, diff_usage
            from backend.usage import record_tutor_turn

            _tutor_before = snapshot_usage()
            # P6.1: REAL token streaming. astream_tutor_tokens drives the graph
            # with astream_events and yields the incremental tokens produced by
            # generate_answer_node, then a single {final: ...} payload with the
            # committed turn's metadata. The wire contract (data: {t} chunks,
            # data: {final}, data: [DONE]) is unchanged, so the frontend's
            # reassembly is untouched — only time-to-first-token changes.
            scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user, guest_id)
            async for frame in tutor_deps.astream_tutor_tokens(
                thread_id=scoped_thread_id,
                user_question=req.user_question,
                lecture_title=req.lecture_title,
                lecture_id=req.lecture_id,
                message_id=req.message_id,
                study_mode=req.study_mode,
                persona_instructions=await _effective_persona_instructions(
                    req.persona_instructions, user, db, req.lecture_id
                ),
            ):
                if isinstance(frame, dict) and "final" in frame and isinstance(frame["final"], dict):
                    frame["final"]["thread_id"] = req.thread_id
                yield f"data: {json_lib.dumps(frame)}\n\n"
            yield "data: [DONE]\n\n"
            await _flush_tutor_usage_async(user, req.lecture_id or "default", _tutor_before, diff_usage)
        except ThreadDeletedError:
            # P2.2: honest terminal frame for a deleted thread.
            logging.getLogger("norai").info("Stream aborted: thread %s was deleted", req.thread_id)
            yield "data: [ERROR] This conversation was deleted. Please start a new one.\n\n"
        except Exception as exc:
            logging.getLogger("norai").exception("POST /chat/stream failed")
            yield "data: [ERROR] An internal error occurred while streaming the answer.\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/threads")
async def list_threads(
    request: Request,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return all thread IDs for a lecture."""
    guest_id = request.headers.get("x-guest-id")
    await ensure_lecture_access(lecture_id, user, db, guest_id=guest_id)
    db_path = get_lecture_db_path(lecture_id)
    if not db_path.exists():
        return {"threads": ["default"]}

    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user, guest_id)

    threads = set()
    deleted = set()
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        configure_sqlite(conn)
        try:
            # 0) Read deleted_threads
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_threads'").fetchone():
                del_cols = [c[1] for c in conn.execute("PRAGMA table_info(deleted_threads)").fetchall()]
                if is_demo and "user_id" in del_cols:
                    for row in conn.execute("SELECT thread_id FROM deleted_threads WHERE user_id = ?", (user_scope,)):
                        if row[0]:
                            deleted.add(row[0])
                else:
                    for row in conn.execute("SELECT thread_id FROM deleted_threads"):
                        if row[0]:
                            deleted.add(row[0])

            # 1) Ensure user_threads schema
            conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT, user_id TEXT DEFAULT '', PRIMARY KEY (thread_id, user_id))")
            ut_cols = [c[1] for c in conn.execute("PRAGMA table_info(user_threads)").fetchall()]
            if "user_id" not in ut_cols:
                try:
                    conn.execute("ALTER TABLE user_threads ADD COLUMN user_id TEXT DEFAULT ''")
                except Exception:
                    pass

            # 2) For non-demo lectures, auto-migrate legacy checkpoints if user_threads is empty
            if not is_demo:
                try:
                    cursor = conn.execute("SELECT thread_id, checkpoint FROM checkpoints")
                    rows = cursor.fetchall()
                    for row in rows:
                        tid = row[0]
                        chk = row[1]
                        if isinstance(chk, bytes) and b"HumanMessage" in chk and tid not in deleted:
                            conn.execute("INSERT OR IGNORE INTO user_threads (thread_id, user_id) VALUES (?, '')", (tid,))
                    conn.commit()
                except Exception:
                    pass

            # 3) Read user_threads table
            if is_demo:
                for row in conn.execute("SELECT thread_id FROM user_threads WHERE user_id = ?", (user_scope,)):
                    if row[0] and row[0] not in deleted:
                        threads.add(row[0])
            else:
                for row in conn.execute("SELECT thread_id FROM user_threads"):
                    if row[0] and row[0] not in deleted:
                        threads.add(row[0])
        finally:
            conn.close()
    except Exception:
        pass

    # Ensure "default" is included if not explicitly deleted
    if "default" not in deleted:
        threads.add("default")

    return {"threads": sorted(threads)}


@router.post("/threads")
async def create_thread_endpoint(
    request: Request,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation thread in a lecture."""
    guest_id = request.headers.get("x-guest-id")
    await ensure_lecture_access(lecture_id, user, db, guest_id=guest_id)
    thread_id = None
    try:
        body = await request.json()
        thread_id = body.get("thread_id")
        if (not lecture_id or lecture_id == "default") and body.get("lecture_id"):
            lecture_id = body.get("lecture_id")
    except Exception:
        pass
    if not thread_id:
        thread_id = f"thread-{int(time.time() * 1000)}"

    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user, guest_id)

    db_path = get_lecture_db_path(lecture_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        configure_sqlite(conn)
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS user_threads (thread_id TEXT, user_id TEXT DEFAULT '', PRIMARY KEY (thread_id, user_id))")
            ut_cols = [c[1] for c in conn.execute("PRAGMA table_info(user_threads)").fetchall()]
            if "user_id" not in ut_cols:
                try:
                    conn.execute("ALTER TABLE user_threads ADD COLUMN user_id TEXT DEFAULT ''")
                except Exception:
                    pass

            target_user_id = user_scope if is_demo else ""
            conn.execute("INSERT OR IGNORE INTO user_threads (thread_id, user_id) VALUES (?, ?)", (thread_id, target_user_id))
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deleted_threads'").fetchone():
                del_cols = [c[1] for c in conn.execute("PRAGMA table_info(deleted_threads)").fetchall()]
                if is_demo and "user_id" in del_cols:
                    conn.execute("DELETE FROM deleted_threads WHERE thread_id = ? AND user_id = ?", (thread_id, user_scope))
                else:
                    conn.execute("DELETE FROM deleted_threads WHERE thread_id = ?", (thread_id,))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    return {"thread_id": thread_id}


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    request: Request,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the full message history for a thread in a specific lecture."""
    # Thread transcripts are private tutor conversations.
    guest_id = request.headers.get("x-guest-id")
    await ensure_lecture_access(lecture_id, user, db, guest_id=guest_id)
    scoped_thread_id = _get_scoped_thread_id(lecture_id, thread_id, user, guest_id)
    try:
        graph, _ = await _aget_or_create_lecture_graph(lecture_id)
        config = {"configurable": {"thread_id": scoped_thread_id}}
        snapshot = await graph.aget_state(config)

        # The append-only transcript is the display history. The checkpoint's
        # `messages` is tutor memory (summarised turns are deleted from it),
        # so it is only a fallback for threads that predate the transcript.
        rows = await asyncio.to_thread(
            transcript.load, tutor_deps.turn_db_path(lecture_id), scoped_thread_id
        )
        if rows:
            values = snapshot.values if (snapshot and snapshot.values) else {}
            return {
                "thread_id": thread_id,
                "messages": [
                    {**r, "content": _strip_sources(r["content"]) if r["role"] == "assistant" else r["content"]}
                    for r in rows
                ],
                "last_retrieved_chunks": values.get("retrieved_chunks", []),
                "last_retrieved_images": values.get("retrieved_images", []),
                "verified_citations": values.get("verified_citations", []),
                "answer": values.get("answer", ""),
            }

        if not snapshot or not snapshot.values:
            return {"thread_id": thread_id, "messages": []}

        result = []
        for msg in snapshot.values.get("messages", []):
            if isinstance(msg, dict):
                msg_type = str(msg.get("type", msg.get("role", ""))).lower()
                if msg_type in ("system", "systemmessage", "removemessage"):
                    continue
                role = "user" if msg_type in ("human", "user", "humanmessage", "humanmessagechunk") else "assistant"
                content = msg.get("content", "")
                msg_id = msg.get("id") or str(uuid.uuid4())
            else:
                class_name = msg.__class__.__name__
                if class_name in ("SystemMessage", "RemoveMessage"):
                    continue
                role = "user" if class_name in ("HumanMessage", "HumanMessageChunk") else "assistant"
                content = getattr(msg, "content", "")
                msg_id = getattr(msg, "id", None) or str(uuid.uuid4())

            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
                )
            if role == "assistant":
                content = _strip_sources(content)

            result.append({
                "id": str(msg_id),
                "role": role,
                "content": str(content),
            })

        last_retrieved_chunks = snapshot.values.get("retrieved_chunks", [])
        last_retrieved_images = snapshot.values.get("retrieved_images", [])

        return {
            "thread_id": thread_id,
            "messages": result,
            "last_retrieved_chunks": last_retrieved_chunks,
            "last_retrieved_images": last_retrieved_images,
            "verified_citations": snapshot.values.get("verified_citations", []),
            "answer": snapshot.values.get("answer", ""),
        }
    except HTTPException:
        raise
    except Exception:
        logging.getLogger("norai").exception("GET /threads/%s failed", thread_id)
        raise HTTPException(status_code=500, detail="Internal error loading thread")


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    request: Request,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Delete a thread from a lecture."""
    # Destructive tutor-write.
    guest_id = request.headers.get("x-guest-id")
    await ensure_lecture_access(lecture_id, user, db, guest_id=guest_id)
    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user, guest_id)
    scoped_thread_id = _get_scoped_thread_id(lecture_id, thread_id, user, guest_id)

    db_path = get_lecture_db_path(lecture_id)
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), timeout=10.0)
            configure_sqlite(conn)
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS deleted_threads (thread_id TEXT, user_id TEXT DEFAULT '', PRIMARY KEY (thread_id, user_id))")
                del_cols = [c[1] for c in conn.execute("PRAGMA table_info(deleted_threads)").fetchall()]
                if "user_id" not in del_cols:
                    try:
                        conn.execute("ALTER TABLE deleted_threads ADD COLUMN user_id TEXT DEFAULT ''")
                    except Exception:
                        pass

                target_user_id = user_scope if is_demo else ""
                conn.execute("INSERT OR REPLACE INTO deleted_threads (thread_id, user_id) VALUES (?, ?)", (thread_id, target_user_id))
                for table in ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]:
                    try:
                        conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (scoped_thread_id,))
                    except sqlite3.OperationalError:
                        pass
                transcript.delete_thread(conn, scoped_thread_id)
                if is_demo:
                    conn.execute("DELETE FROM user_threads WHERE thread_id = ? AND user_id = ?", (thread_id, user_scope))
                else:
                    conn.execute("DELETE FROM user_threads WHERE thread_id = ?", (thread_id,))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass
    return {"deleted": thread_id}
