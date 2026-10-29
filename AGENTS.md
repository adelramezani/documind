# Documind — project notes

Local-first RAG assistant: FastAPI + SQLite + Chroma backend (`backend/`),
React + Vite frontend (`frontend/`). All state under `data/` (gitignored).

## Overview

A local-first RAG application, Private, locally hosted AI knowledge assistant that ingests confidential documents, builds a RAG (Retrieval-Augmented Generation) knowledge base, answers questions about the documents, and translates their content — all using local AI models through Ollama and LangChain.
- It should be able to have a normal conversation with the user
- When it come to the document it should be able to identify when document or documents needed there to be queried
- I should be able to add a single individual file, or select some files, or a directory that it contains sub-directories and files
- All known documents such as pdf, docx, xlsx, txt, md, ... should be supported
- For the unknown documents it should try to find out the way for extracting data
- The user should be able to talk with chat instead of writing , and it should be converted to text by AI agent itself
- RAG Data splitting, Data embeding, Data storing parameters should have default and visible values in setting and it should be changeable too ().
- LLM models used there should be changable
- if the LLM is not available there it should be download and available automatically
- every selected LLM should provide a simple description about what is it good for, and detailed parameters
- if there is multiple approach or multiple stronge option to choice, please let me know and ask first by giving your oponion first
- Sessions and chat history should be provided
- Trustworthy answers: cite document names and page numbers, distinguish evidence from inference, and admit when the documents do not contain an answer (In every answer there should be an information button at the end that it should provide detail information about which documents the answer collected from).
- Multi-stage RAG: document ingestion, parsing, chunking, indexing, retrieval, reranking, answer generation, and citation validation are separate stages.
- Local AI: Ollama provides local models, while LangChain/LangGraph can orchestrate retrieval and agent workflows.
- Document translation: translate retrieved passages or complete documents while preserving structure, tables, and references (it can be returned in MarkDown format).
- Maintainable code: modular architecture, tests, typed interfaces, configuration, error handling, and reproducible deployment.


## Commands

- Backend tests: `.venv/Scripts/python -m pytest backend/tests -x -q`
- Run backend: `.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000`
- Frontend: `cd frontend && /c/Development/nodejs24/npm.cmd install && npm run dev`
- Frontend tests/build: `npm test` / `npm run build`

## Gotchas

- In Git Bash, bare `npm` resolves to a broken WSL shim — use
  `/c/Development/nodejs24/npm.cmd`.
- Corporate Cntlm proxy at `localhost:63328` intermittently returns 407;
  retry `npm install` — cache makes retries cheap. Direct egress is blocked.
- Ollama `/api/tags` may list models whose manifests were partially
  deleted — verify usability with `/api/show`, not `/api/tags`. On this
  machine (2026-10-28), usable: `llama3.2:1b-instruct-q4_K_M`,
  `all-minilm`, `granite-embedding:30m`. Ghost entries: qwen3.6, gemma4,
  mistral, llama3.2*, deepseek-r1, nomic-embed-text, mxbai-embed-large.
- Ollama embed/generate endpoints require exact model tags —
  `OllamaClient._resolve_model` maps bare names to installed tags.
- `llama3.2:1b` answers are very terse and may emit stray `[n]` markers;
  the simplified `_SYSTEM_RAG`/`_RAG_USER` prompt split works better than
  a long rules list on tiny models.
- Windows curl cannot read MSYS `/tmp` — use repo-relative paths in tests.
- jsdom lacks `scrollIntoView` — stubbed in `src/test-setup.ts`.
- Deployment: Ansible under `deploy/` targets `ls-dp-integration-test`
  (AlmaLinux 8.10, SSH user `documind`, CPU-only — no vLLM). Fully rootless:
  everything under `~/.local`, `systemd --user` units (needs linger for
  reboot persistence), no nginx — uvicorn serves API + SPA via the
  `_SPAStaticFiles` mount in `backend/app/main.py` on `0.0.0.0:8000`.
  Control node must be Linux/WSL; server needs git, python3.11+, and
  egress to github.com, nodejs.org, ollama.com, npm registry.

## Conventions

- Chat routing (`decide_mode`): auto mode treats messages made only of
  small-talk phrases as normal chat; everything else uses RAG when indexed
  documents exist. Override via `mode` field (auto/always/never).
- Chroma collection name is derived from the embedding model
  (`documind-<model>`) so vectors from different models never mix;
  changing chunk/embedding settings flags `needs_reindex` in the settings API.
- Citation validation strips `[n]` markers outside the retrieved range —
  models can't cite sources they weren't given.
- New files/features update the README Features table in the same change.
