"""FastAPI application entrypoint."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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


_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class _SPAStaticFiles(StaticFiles):
    """Serve the frontend build; unknown paths fall back to index.html."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


# Mounted last so /api routes win; no-op when dist/ is absent (dev mode).
if _DIST.is_dir():
    app.mount("/", _SPAStaticFiles(directory=_DIST, html=True))
