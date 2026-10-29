"""Answer generation stage: mode routing, grounded prompting, and
citation validation.

The router is deterministic (no extra model call): obvious small talk or
an empty index stays in plain chat; otherwise the query goes through RAG.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..db import Database
from ..ollama_client import OllamaClient
from ..settings import RagSettings
from .reranker import rerank
from .retriever import retrieve

_SMALL_TALK_PHRASES = (
    "hi", "hello", "hey", "good morning", "good afternoon",
    "good evening", "how are you", "how's it going", "thanks",
    "thank you", "bye", "goodbye", "ok", "okay", "who are you",
    "what can you do", "today", "there", "you",
)

_SMALL_TALK_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(p) for p in
               sorted(_SMALL_TALK_PHRASES, key=len, reverse=True))
    + r")(?:[\s,]+(?:"
    + "|".join(re.escape(p) for p in
               sorted(_SMALL_TALK_PHRASES, key=len, reverse=True))
    + r"))*$",
    re.IGNORECASE,
)

_SMALL_TALK_MAX_LEN = 60


def _is_small_talk(query: str) -> bool:
    q = re.sub(r"[.!?]+$", "", query.strip().lower())
    if not q or len(q) > _SMALL_TALK_MAX_LEN:
        return False
    return _SMALL_TALK_RE.match(q) is not None


@dataclass
class Answer:
    content: str
    mode: str  # "chat" | "rag" | "rag_no_evidence"
    sources: list[dict] = field(default_factory=list)
    grounded: bool = False


def decide_mode(query: str, has_docs: bool,
                override: str) -> str:
    """Return 'chat' or 'rag'."""
    if override == "never":
        return "chat"
    if override == "always":
        return "rag" if has_docs else "chat"
    # auto
    if not has_docs:
        return "chat"
    if _is_small_talk(query):
        return "chat"
    return "rag"


_SYSTEM_RAG = (
    "You are Documind, a private document assistant. Answer ONLY from the "
    "sources given in the user's message. Cite claims with [n] markers "
    "matching the source numbers. If the sources do not contain the "
    "answer, say so. Prefix anything beyond the sources with "
    "'(inference)'."
)

_RAG_USER = "Sources:\n{context}\n\nQuestion: {question}"

_SYSTEM_CHAT = (
    "You are Documind, a helpful local assistant. Answer normally and "
    "concisely. You have no access to documents in this reply."
)

_CITE_RE = re.compile(r"\[(\d+)\]")


def _build_context(scored: list) -> str:
    blocks = []
    for i, (chunk, _score) in enumerate(scored, start=1):
        name = chunk.meta.get("document_name", "document")
        page = chunk.meta.get("page")
        loc = f", page {page}" if page and page > 0 else ""
        blocks.append(f"[{i}] {name}{loc}\n{chunk.text}")
    return "\n\n".join(blocks)


def _validate_citations(content: str, n_sources: int) -> tuple[str, set[int]]:
    """Strip citation markers outside the valid range; return cleaned text
    and the set of cited source numbers."""
    cited: set[int] = set()

    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        if 1 <= n <= n_sources:
            cited.add(n)
            return m.group(0)
        return ""  # invalid citation removed

    return _CITE_RE.sub(repl, content), cited


def answer(
    db: Database,
    vectorstore,
    ollama: OllamaClient,
    settings: RagSettings,
    history: list[dict],
    query: str,
    mode_override: str = "auto",
) -> Answer:
    has_docs = db.fetchone(
        "SELECT 1 AS x FROM documents WHERE status='indexed' LIMIT 1"
    ) is not None
    mode = decide_mode(query, has_docs, mode_override or settings.chat_mode)

    if mode == "chat":
        content = ollama.chat(
            settings.chat_model,
            [{"role": "system", "content": _SYSTEM_CHAT},
             *history, {"role": "user", "content": query}],
            temperature=settings.temperature,
            num_ctx=settings.num_ctx,
            num_predict=settings.max_answer_tokens,
        )
        return Answer(content=content, mode="chat")

    # RAG path
    q_emb = ollama.embed_query(settings.embedding_model, query)
    candidates = retrieve(db, vectorstore, q_emb, query,
                          settings.retrieval_top_k)
    scored = rerank(candidates, query,
                    settings.lexical_weight, settings.rerank_top_n)
    if not scored:
        return Answer(
            content="The documents do not contain an answer to that "
                    "question (no relevant passages were found).",
            mode="rag_no_evidence",
        )

    context = _build_context(scored)
    raw = ollama.chat(
        settings.chat_model,
        [{"role": "system", "content": _SYSTEM_RAG},
         *history,
         {"role": "user",
          "content": _RAG_USER.format(context=context, question=query)}],
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        num_predict=settings.max_answer_tokens,
    )
    content, cited = _validate_citations(raw, len(scored))

    sources = []
    for i, (chunk, score) in enumerate(scored, start=1):
        if cited and i not in cited:
            continue
        meta = chunk.meta or {}
        page = meta.get("page")
        sources.append({
            "chunk_id": chunk.chunk_id,
            "document_id": meta.get("document_id", ""),
            "document_name": meta.get("document_name", ""),
            "rel_path": meta.get("rel_path", ""),
            "page": page if isinstance(page, int) and page > 0 else None,
            "sheet": meta.get("sheet"),
            "slide": meta.get("slide"),
            "snippet": chunk.text[:300],
            "score": round(score, 4),
        })
    no_evidence = not sources or (
        "do not contain" in content.lower() and not cited
    )
    return Answer(
        content=content,
        mode="rag_no_evidence" if no_evidence else "rag",
        sources=sources,
        grounded=bool(sources),
    )
