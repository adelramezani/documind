"""Chunker tests: size bounds, provenance, deterministic IDs."""
from app.ingest.chunker import chunk_units
from app.ingest.extractors import ExtractedUnit


def test_respects_size_and_overlap():
    text = "Sentence one. " * 100  # ~1400 chars
    units = [ExtractedUnit(text=text, page=3)]
    chunks = chunk_units("doc1", units, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)
    assert all(c.page == 3 for c in chunks)


def test_deterministic_ids():
    units = [ExtractedUnit(text="hello world", page=1)]
    a = chunk_units("doc1", units, 100, 10)
    b = chunk_units("doc1", units, 100, 10)
    assert [c.id for c in a] == [c.id for c in b]


def test_provenance_carried():
    units = [ExtractedUnit(text="data", sheet="Sheet1",
                           meta={"row_start": 5})]
    chunks = chunk_units("doc1", units, 100, 10)
    assert chunks[0].sheet == "Sheet1"
    assert chunks[0].location["row_start"] == 5


def test_empty_pieces_skipped():
    units = [ExtractedUnit(text="   \n\n   ")]
    assert chunk_units("doc1", units, 100, 10) == []
