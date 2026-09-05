"""
backend/routers/tutor.py — AI-tutor chat + conversation-thread endpoints (P5.1).

Extracted verbatim from main.py; the app mounts this router with no prefix,
so paths are unchanged (/chat, /chat/stream, /threads*).

Indirection note: handlers call tutor_deps.ainvoke_tutor /
tutor_deps.astream_tutor_tokens (backend.dependencies is the canonical
patch point for offline tests), NOT module-level `from ... import` copies.
"""

import json as json_lib
import logging
import re
import sqlite3
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend import dependencies as tutor_deps
from backend.access import (
    _DEMO_TURNS_DAILY,
    _effective_persona_instructions,
    _flush_tutor_usage_async,
    _is_free_demo_access,
    ensure_lecture_access,
)
from backend.auth import get_current_user, get_current_user_optional
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
from config import DEMO_LECTURE_IDS

router = APIRouter()


def _get_user_scope(user: Optional[User]) -> str:
    """Return user scope ID for partitioning demo lectures."""
    if user and getattr(user, "id", None) and not str(user.id).startswith("guest-"):
        return str(user.id)
    return "guest"


def _get_scoped_thread_id(lecture_id: Optional[str], thread_id: str, user: Optional[User]) -> str:
    """Return scoped thread ID for storage in LangGraph checkpointer.
    For shared demo lectures, conversations are scoped per-user so they never leak across users.
    For user-uploaded lectures, thread_id is unchanged.
    """
    clean_id = sanitize_lecture_id(lecture_id or "default")
    if clean_id in DEMO_LECTURE_IDS or clean_id == "default":
        user_scope = _get_user_scope(user)
        return f"{user_scope}:{thread_id}"
    return thread_id


class CreateThreadRequest(BaseModel):
    thread_id: str | None = None

class ChatRequest(BaseModel):
    thread_id: str
    user_question: str
    lecture_title: str = ""
    lecture_id: str | None = None   # ← new field
    message_id: str | None = None
    study_mode: str = "default"
    persona_instructions: str = ""

class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: list
    retrieved_images: list
    verified_citations: list = []   # P3.3
    chapter_id: int | None
    thread_id: str


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
        # P6.4: chat is a tutor-gated write — owner OR share link with tutor
        # chat enabled. Anonymous users without a share link are 404'd.
        await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True)
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
        scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user)
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bind(lecture_id=req.lecture_id, thread_id=req.thread_id)
    await ensure_lecture_access(req.lecture_id or "default", user, db, require_tutor=True)
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
            scoped_thread_id = _get_scoped_thread_id(req.lecture_id, req.thread_id, user)
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
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return all thread IDs for a lecture."""
    # P6.4: thread listing is a lecture-scoped read — owner or valid share link.
    await ensure_lecture_access(lecture_id, user, db)
    db_path = get_lecture_db_path(lecture_id)
    if not db_path.exists():
        return {"threads": ["default"]}

    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user)

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
    # Threads power the AI tutor, so creation follows the same tutor-gated
    # write rule as POST /chat (owner or share link with tutor chat enabled).
    await ensure_lecture_access(lecture_id, user, db, require_tutor=True)
    thread_id = None
    try:
        body = await request.json()
        thread_id = body.get("thread_id")
    except Exception:
        pass
    if not thread_id:
        thread_id = f"thread-{int(time.time() * 1000)}"

    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user)

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
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the full message history for a thread in a specific lecture."""
    # Thread transcripts are private tutor conversations — same gate as /chat.
    await ensure_lecture_access(lecture_id, user, db, require_tutor=True)
    scoped_thread_id = _get_scoped_thread_id(lecture_id, thread_id, user)
    try:
        graph, _ = await _aget_or_create_lecture_graph(lecture_id)
        config = {"configurable": {"thread_id": scoped_thread_id}}
        snapshot = await graph.aget_state(config)
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
                content = re.sub(r'(\*\*Sources\*\*|\n\nSources\b|Sources\s*[\:\•]|Sources\b[\s\S]*$)[\s\S]*$', '', str(content), flags=re.IGNORECASE).strip()

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
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Delete a thread from a lecture."""
    # Destructive tutor-write: same gate as POST /chat.
    await ensure_lecture_access(lecture_id, user, db, require_tutor=True)
    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS or clean_id == "default"
    user_scope = _get_user_scope(user)
    scoped_thread_id = _get_scoped_thread_id(lecture_id, thread_id, user)

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
