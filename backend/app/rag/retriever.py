"""Retrieval stage: hybrid dense (Chroma) + lexical (SQLite FTS5) search."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..db import Database


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    dense_rank: int | None
    lexical_rank: int | None
    meta: dict


def _fts_terms(query: str) -> str:
    """Build a safe FTS5 OR query from user text (no raw FTS syntax)."""
    terms = re.findall(r"\w+", query.lower())
    return " OR ".join(f'"{t}"' for t in terms[:20]) or '""'


def lexical_search(db: Database, query: str, n: int) -> dict[str, int]:
    """Return chunk_id -> lexical rank using FTS5 BM25 ordering."""
    match = _fts_terms(query)
    if match == '""':
        return {}
    try:
        rows = db.fetchall(
            "SELECT c.id FROM chunks_fts f JOIN chunks c"
            " ON c.rowid = f.rowid WHERE chunks_fts MATCH ?"
            " ORDER BY rank LIMIT ?",
            (match, n),
        )
    except Exception:  # noqa: BLE001 - malformed FTS queries degrade to none
        return {}
    return {r["id"]: i for i, r in enumerate(rows)}


def dense_search(vectorstore, embedding: list[float],
                 n: int) -> dict[str, tuple[int, dict]]:
    """Return chunk_id -> (rank, chroma result row)."""
    res = vectorstore.query(embedding, n)
    out: dict[str, tuple[int, dict]] = {}
    ids = res.get("ids", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    docs = res.get("documents", [[]])[0]
    for i, cid in enumerate(ids):
        out[cid] = (i, {"meta": metas[i], "text": docs[i]})
    return out


def retrieve(db: Database, vectorstore, query_embedding: list[float],
             query_text: str, top_k: int) -> list[RetrievedChunk]:
    dense = dense_search(vectorstore, query_embedding, top_k)
    lexical = lexical_search(db, query_text, top_k)
    ids = set(dense) | set(lexical)
    chunks: list[RetrievedChunk] = []
    for cid in ids:
        d = dense.get(cid)
        row = db.fetchone("SELECT * FROM chunks WHERE id = ?", (cid,))
        text = d[1]["text"] if d else (row["text"] if row else "")
        meta = d[1]["meta"] if d else {}
        chunks.append(RetrievedChunk(
            chunk_id=cid, text=text,
            dense_rank=d[0] if d else None,
            lexical_rank=lexical.get(cid),
            meta=meta,
        ))
    return chunks
