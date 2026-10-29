"""Chain tests: mode routing, citation validation, answer assembly."""
from app.ingest.pipeline import ingest_document, register_document
from app.rag.chain import (Answer, _validate_citations, answer,
                           decide_mode)
from app.settings import RagSettings


def test_decide_mode():
    assert decide_mode("hi", True, "auto") == "chat"
    assert decide_mode("hi, how are you?", True, "auto") == "chat"
    assert decide_mode("hi there", True, "auto") == "chat"
    # Small-talk prefix must not hijack a real document question.
    assert decide_mode("hi, summarize the contract", True, "auto") == "rag"
    assert decide_mode("what is the deadline?", True, "auto") == "rag"
    assert decide_mode("what is the deadline?", False, "auto") == "chat"
    assert decide_mode("hi", True, "always") == "rag"
    assert decide_mode("anything", True, "never") == "chat"


def test_validate_citations_strips_invalid():
    text, cited = _validate_citations("Fact [1] and guess [9] and [2].", 3)
    assert "[1]" in text and "[2]" in text and "[9]" not in text
    assert cited == {1, 2}


def _index_doc(state, text: str, name="doc.txt") -> str:
    row, _ = register_document(state.db, name, name, text.encode(), "text/plain")
    res = ingest_document(state.db, state.vectorstore(), state.ollama,
                          state.settings(), row["id"], text.encode())
    assert res.status == "indexed", res.error
    return row["id"]


def test_chat_bypasses_retrieval(state):
    out = answer(state.db, state.vectorstore(), state.ollama,
                 state.settings(), [], "hello there", "auto")
    assert out.mode == "chat"
    assert out.sources == []


def test_rag_answer_with_citations(state):
    _index_doc(state, "The project deadline is Friday. All teams must "
                      "submit before then.")
    out = answer(state.db, state.vectorstore(), state.ollama,
                 state.settings(), [], "what is the project deadline?",
                 "auto")
    assert out.mode == "rag"
    assert out.grounded
    assert out.sources[0]["document_name"] == "doc.txt"
    assert "[1]" in out.content


def test_no_documents_no_sources(state):
    out = answer(state.db, state.vectorstore(), state.ollama,
                 state.settings(), [], "summarize the contract", "always")
    # No indexed docs -> falls back to chat rather than pretending.
    assert out.mode == "chat"
    assert out.sources == []
