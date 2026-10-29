"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import chat, documents, models
from .ollama_client import OllamaUnavailable

app = FastAPI(title="Documind", version="0.1.0")

# Local-only by default; the Vite dev server proxies /api anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OllamaUnavailable)
def _ollama_down(_req, exc: OllamaUnavailable):
    return JSONResponse(status_code=503,
                        content={"detail": str(exc)})


app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(models.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
