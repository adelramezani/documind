"""Chat and session endpoints."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..db import utcnow
from ..deps import AppState, get_state
from ..rag.chain import answer
from ..schemas import (ChatRequest, ChatResponse, MessageOut, SessionOut,
                       SourceRef)

router = APIRouter(prefix="/api", tags=["chat"])


def _session_out(row: dict) -> SessionOut:
    return SessionOut(**row)


def _msg_out(row: dict) -> MessageOut:
    sources = json.loads(row["sources_json"] or "[]")
    return MessageOut(
        id=row["id"], session_id=row["session_id"], role=row["role"],
        content=row["content"], mode=row["mode"],
        sources=[SourceRef(**s) for s in sources],
        created_at=row["created_at"],
    )


def _history(db, session_id: str, limit: int = 10) -> list[dict]:
    rows = db.fetchall(
        "SELECT role, content FROM messages WHERE session_id=?"
        " ORDER BY id DESC LIMIT ?", (session_id, limit))
    return [{"role": r["role"], "content": r["content"]}
            for r in reversed(rows)]


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest,
         state: AppState = Depends(get_state)) -> ChatResponse:
    db = state.db
    session_id = req.session_id
    if session_id:
        if not db.fetchone("SELECT id FROM sessions WHERE id=?",
                           (session_id,)):
            raise HTTPException(404, "session not found")
    else:
        session_id = uuid.uuid4().hex
        title = req.message.strip()[:60] or "New chat"
        now = utcnow()
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at)"
                " VALUES(?,?,?,?)", (session_id, title, now, now))

    settings = state.settings()
    history = _history(db, session_id)
    resp = answer(db, state.vectorstore(), state.ollama, settings,
                  history, req.message, req.mode)

    now = utcnow()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO messages(session_id, role, content, created_at)"
            " VALUES(?,?,?,?)", (session_id, "user", req.message, now))
        cur = conn.execute(
            "INSERT INTO messages(session_id, role, content, mode,"
            " sources_json, created_at) VALUES(?,?,?,?,?,?)",
            (session_id, "assistant", resp.content, resp.mode,
             json.dumps(resp.sources), now))
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?",
                     (now, session_id))
        msg_id = cur.lastrowid

    return ChatResponse(
        session_id=session_id, message_id=msg_id, content=resp.content,
        mode=resp.mode, grounded=resp.grounded,
        sources=[SourceRef(**s) for s in resp.sources],
    )


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(state: AppState = Depends(get_state)) -> list[SessionOut]:
    rows = state.db.fetchall(
        "SELECT * FROM sessions ORDER BY updated_at DESC")
    return [_session_out(r) for r in rows]


@router.get("/sessions/{session_id}/messages",
            response_model=list[MessageOut])
def session_messages(session_id: str,
                     state: AppState = Depends(get_state)) -> list[MessageOut]:
    if not state.db.fetchone("SELECT id FROM sessions WHERE id=?",
                             (session_id,)):
        raise HTTPException(404, "session not found")
    rows = state.db.fetchall(
        "SELECT * FROM messages WHERE session_id=? ORDER BY id",
        (session_id,))
    return [_msg_out(r) for r in rows]


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str,
                   state: AppState = Depends(get_state)) -> dict:
    with state.db.tx() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?",
                     (session_id,))
        cur = conn.execute("DELETE FROM sessions WHERE id=?",
                           (session_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "session not found")
    return {"deleted": session_id}
