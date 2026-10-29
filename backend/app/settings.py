"""User-tunable settings: defaults, validation, and persistence.

Every RAG / generation parameter has a visible default here, is exposed via
the settings API, and can be changed by the user.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

DEFAULTS: dict[str, Any] = {
    # chunking
    "chunk_size": 1000,
    "chunk_overlap": 200,
    # retrieval
    "retrieval_top_k": 12,
    "rerank_top_n": 4,
    "lexical_weight": 0.35,
    # generation
    "chat_model": "llama3.2:3b",
    "embedding_model": "nomic-embed-text",
    "temperature": 0.2,
    "num_ctx": 8192,
    "max_answer_tokens": 1024,
    # behaviour
    "chat_mode": "auto",  # auto | always | never
}


class RagSettings(BaseModel):
    """Validated view over the mutable settings store."""

    chunk_size: int = Field(DEFAULTS["chunk_size"], ge=100, le=8000)
    chunk_overlap: int = Field(DEFAULTS["chunk_overlap"], ge=0, le=2000)
    retrieval_top_k: int = Field(DEFAULTS["retrieval_top_k"], ge=1, le=50)
    rerank_top_n: int = Field(DEFAULTS["rerank_top_n"], ge=1, le=20)
    lexical_weight: float = Field(DEFAULTS["lexical_weight"], ge=0.0, le=1.0)
    chat_model: str = DEFAULTS["chat_model"]
    embedding_model: str = DEFAULTS["embedding_model"]
    temperature: float = Field(DEFAULTS["temperature"], ge=0.0, le=2.0)
    num_ctx: int = Field(DEFAULTS["num_ctx"], ge=512, le=131072)
    max_answer_tokens: int = Field(DEFAULTS["max_answer_tokens"], ge=64, le=8192)
    chat_mode: str = Field(DEFAULTS["chat_mode"], pattern="^(auto|always|never)$")

    def needs_reindex(self, other: "RagSettings") -> bool:
        """True when changing to `other` requires reindexing chunks."""
        return (
            self.chunk_size != other.chunk_size
            or self.chunk_overlap != other.chunk_overlap
            or self.embedding_model != other.embedding_model
        )


def load_settings(db) -> RagSettings:
    stored = db.get_settings()
    return RagSettings(**{k: v for k, v in stored.items() if k in DEFAULTS})


def save_settings(db, settings: RagSettings) -> None:
    for key, value in settings.model_dump().items():
        db.set_setting(key, value)
