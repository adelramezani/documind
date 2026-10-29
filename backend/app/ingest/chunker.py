"""Chunking stage: split extracted units into sized chunks with provenance.

Chunk IDs are deterministic (document + unit + offset + content hash) so
re-ingesting the same file produces stable IDs and safe deduplication.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .extractors import ExtractedUnit


@dataclass
class Chunk:
    id: str
    document_id: str
    ord: int
    text: str
    page: int | None
    sheet: str | None
    slide: int | None
    location: dict


def chunk_units(
    document_id: str,
    units: list[ExtractedUnit],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Chunk] = []
    for unit_idx, unit in enumerate(units):
        pieces = splitter.split_text(unit.text)
        for piece_idx, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
            digest = hashlib.sha256(
                f"{document_id}:{unit_idx}:{piece_idx}:{piece}".encode()
            ).hexdigest()[:24]
            loc = {k: v for k, v in {
                "page": unit.page, "sheet": unit.sheet, "slide": unit.slide,
                "section": unit.section, **unit.meta,
            }.items() if v is not None}
            chunks.append(
                Chunk(
                    id=f"{document_id[:8]}-{digest}",
                    document_id=document_id,
                    ord=len(chunks),
                    text=piece,
                    page=unit.page,
                    sheet=unit.sheet,
                    slide=unit.slide,
                    location=loc,
                )
            )
    return chunks


def location_json(chunk: Chunk) -> str:
    return json.dumps(chunk.location)
