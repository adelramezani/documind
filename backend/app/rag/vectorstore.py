"""Chroma-backed persistent vector index.

Collection name is derived from the embedding model so vectors from
different models never mix; reindexing just repopulates the collection.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def collection_name_for(embedding_model: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", embedding_model)
    return f"documind-{slug}"[:63]


class VectorStore:
    def __init__(self, persist_dir: Path, embedding_model: str):
        import chromadb

        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self._client.get_or_create_collection(
            collection_name_for(embedding_model),
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids: list[str], embeddings: list[list[float]],
            documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        # Chroma metadata values must be str/int/float/bool.
        clean = [{k: v for k, v in m.items()
                  if isinstance(v, (str, int, float, bool))}
                 for m in metadatas]
        self.collection.upsert(
            ids=ids, embeddings=embeddings,
            documents=documents, metadatas=clean,
        )

    def query(self, embedding: list[float], n: int,
              where: dict | None = None) -> dict:
        kwargs: dict[str, Any] = dict(
            query_embeddings=[embedding], n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

    def delete_document(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        return self.collection.count()

    def reset_collection(self) -> None:
        """Drop all vectors in the active collection (reindex path only)."""
        name = self.collection.name
        self._client.delete_collection(name)
        self.collection = self._client.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine"},
        )
