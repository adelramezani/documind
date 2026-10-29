# documind

Private, locally hosted AI knowledge assistant that ingests confidential documents, builds a RAG (Retrieval-Augmented Generation) knowledge base, answers questions about the documents, and translates their content — all using local AI models through Ollama and LangChain.

## Features

| Feature | Location | Description | Date |
|---|---|---|---|
| Cited document chat | `backend/app/rag/chain.py` | RAG answers with `[n]` citations, source-name/page provenance, no-evidence abstention, and per-answer source details | 2026-10-28 |
| Multi-format ingestion | `backend/app/ingest/` | Upload single files, multiple files, or recursive folders; PDF, DOCX, XLSX/XLSM, PPTX, TXT, MD, CSV/TSV, HTML + safe text fallback for unknown types | 2026-10-28 |
| Hybrid retrieval | `backend/app/rag/` | Chroma dense embeddings + SQLite FTS5 lexical search, deterministic RRF reranking | 2026-10-28 |
| Sessions & history | `backend/app/api/chat.py` | Persistent chat sessions and message history (SQLite) | 2026-10-28 |
| Model management | `backend/app/api/models.py` | Lists installed Ollama models with descriptions/params; confirmed-pull downloads via `/api/models/pull` | 2026-10-28 |
| Visible RAG settings | `backend/app/settings.py` | Chunking, retrieval, rerank, generation, and model defaults — all viewable/editable in the Settings UI | 2026-10-28 |
| React UI | `frontend/src/` | Chat view (auto/always/never document mode), Documents, Models, Settings panels | 2026-10-28 |

Voice input and document translation are planned for a later release.

## Requirements

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com) running locally with at least one chat model and one embedding model (e.g. `ollama pull llama3.2` + `ollama pull nomic-embed-text`)

## Run

```bash
# Backend (from repo root)
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.lock   # Windows
# or: .venv/bin/pip install -r backend/requirements.lock  # macOS/Linux
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

## Tests

```bash
.venv/Scripts/python -m pytest backend/tests -x -q   # backend (33 tests)
cd frontend && npm test                            # frontend (vitest)
cd frontend && npm run build                       # production build
```

All private data stays in `./data` (uploads, SQLite DB, Chroma index) — nothing leaves the machine except user-confirmed Ollama model pulls.
