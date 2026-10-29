"""Pydantic schemas for the HTTP API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SourceRef(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    rel_path: str
    page: int | None = None
    sheet: str | None = None
    slide: int | None = None
    snippet: str
    score: float


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    mode: Literal["auto", "always", "never"] = "auto"


class ChatResponse(BaseModel):
    session_id: str
    message_id: int
    role: str = "assistant"
    content: str
    mode: str  # "chat" | "rag" | "rag_no_evidence"
    sources: list[SourceRef] = []
    grounded: bool = False


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    mode: str | None
    sources: list[SourceRef] = []
    created_at: str


class DocumentOut(BaseModel):
    id: str
    name: str
    rel_path: str
    sha256: str
    size: int
    mime: str | None
    status: str
    error: str | None
    chunk_count: int
    created_at: str


class UploadResult(BaseModel):
    accepted: list[DocumentOut] = []
    duplicates: list[str] = []
    rejected: list[dict[str, str]] = []
    job_id: str | None = None


class SettingsOut(BaseModel):
    values: dict[str, Any]
    defaults: dict[str, Any]
    needs_reindex: bool = False


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class ModelInfo(BaseModel):
    name: str
    size: int | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    kind: str = "chat"  # chat | embedding
    description: str = ""
    installed: bool = True


class PullRequest(BaseModel):
    model: str
    confirmed: bool = False


class JobOut(BaseModel):
    id: str
    type: str
    status: str
    detail: dict[str, Any]
    created_at: str
    updated_at: str
