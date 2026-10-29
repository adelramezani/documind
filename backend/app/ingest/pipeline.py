"""Ingestion pipeline: extract -> chunk -> embed -> index.

Runs synchronously inside a background job; each stage is a separate
function so failures are attributable and testable.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass

from ..db import Database, utcnow
from ..ollama_client import OllamaClient
from ..settings import RagSettings
from .chunker import Chunk, chunk_units
from .extractors import ExtractionError, UnsupportedFormat, extract

_SAFE_COMPONENT = re.compile(r"[^\w.\-]+")


def sanitize_rel_path(rel_path: str) -> str:
    """Normalize a browser-supplied relative path; rejects traversal."""
    parts = [p for p in rel_path.replace("\\", "/").split("/")
             if p not in ("", ".", "..")]
    if not parts:
        raise ValueError("empty relative path")
    return "/".join(_SAFE_COMPONENT.sub("_", p) for p in parts)


@dataclass
class IngestResult:
    document_id: str
    status: str  # indexed | failed
    chunk_count: int
    error: str | None = None


def register_document(db: Database, name: str, rel_path: str,
                      data: bytes, mime: str | None) -> tuple[dict | None, bool]:
    """Insert a pending document row unless the same content exists.

    Returns (row, is_duplicate).
    """
    sha = hashlib.sha256(data).hexdigest()
    existing = db.fetchone("SELECT * FROM documents WHERE sha256 = ?", (sha,))
    if existing:
        return existing, True
    doc_id = uuid.uuid4().hex
    now = utcnow()
    safe_rel = sanitize_rel_path(rel_path)
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO documents(id, name, rel_path, sha256, size, mime,"
            " status, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (doc_id, name, safe_rel, sha, len(data), mime or "",
             "pending", now, now),
        )
    return db.fetchone("SELECT * FROM documents WHERE id = ?", (doc_id,)), False


def ingest_document(
    db: Database,
    vectorstore,
    ollama: OllamaClient,
    settings: RagSettings,
    document_id: str,
    data: bytes,
) -> IngestResult:
    doc = db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
    if doc is None:
        return IngestResult(document_id, "failed", 0, "document not found")
    try:
        units = extract(data, doc["name"])
        chunks = chunk_units(document_id, units,
                             settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ExtractionError("no text could be extracted")
        embeddings = ollama.embed(settings.embedding_model,
                                  [c.text for c in chunks])
        _store_chunks(db, vectorstore, doc, chunks, embeddings)
        with db.tx() as conn:
            conn.execute(
                "UPDATE documents SET status='indexed', error=NULL,"
                " chunk_count=?, updated_at=? WHERE id=?",
                (len(chunks), utcnow(), document_id),
            )
        return IngestResult(document_id, "indexed", len(chunks))
    except (UnsupportedFormat, ExtractionError) as exc:
        _mark_failed(db, document_id, str(exc))
        return IngestResult(document_id, "failed", 0, str(exc))
    except Exception as exc:  # noqa: BLE001 - surface infra failures too
        _mark_failed(db, document_id, f"indexing failed: {exc}")
        return IngestResult(document_id, "failed", 0, str(exc))


def _store_chunks(db: Database, vectorstore, doc: dict,
                  chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    now = utcnow()
    with db.tx() as conn:
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc["id"],))
        conn.executemany(
            "INSERT INTO chunks(id, document_id, ord, text, page, sheet,"
            " slide, location_json) VALUES(?,?,?,?,?,?,?,?)",
            [(c.id, c.document_id, c.ord, c.text, c.page, c.sheet, c.slide,
              json.dumps(c.location)) for c in chunks],
        )
    vectorstore.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[{
            "document_id": c.document_id,
            "document_name": doc["name"],
            "rel_path": doc["rel_path"],
            "page": c.page if c.page is not None else -1,
        } for c in chunks],
    )


def _mark_failed(db: Database, document_id: str, error: str) -> None:
    with db.tx() as conn:
        conn.execute(
            "UPDATE documents SET status='failed', error=?, updated_at=?"
            " WHERE id=?", (error, utcnow(), document_id),
        )


def delete_document(db: Database, vectorstore, document_id: str) -> bool:
    doc = db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
    if not doc:
        return False
    vectorstore.delete_document(document_id)
    with db.tx() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return True


def reindex_all(db: Database, vectorstore, ollama: OllamaClient,
                settings: RagSettings, uploads: dict[str, bytes]) -> dict:
    """Rebuild every document's chunks under current settings.

    ``uploads`` maps document_id -> raw bytes (stored upload copy).
    """
    docs = db.fetchall("SELECT * FROM documents")
    vectorstore.reset_collection()
    ok, failed = 0, 0
    for doc in docs:
        data = uploads.get(doc["id"])
        if data is None:
            _mark_failed(db, doc["id"], "original upload missing")
            failed += 1
            continue
        res = ingest_document(db, vectorstore, ollama, settings,
                              doc["id"], data)
        if res.status == "indexed":
            ok += 1
        else:
            failed += 1
    return {"reindexed": ok, "failed": failed}
