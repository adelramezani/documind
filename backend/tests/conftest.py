"""Shared fixtures: isolated AppState, fake Ollama, FastAPI test client."""
from __future__ import annotations

import hashlib
import math
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AppConfig  # noqa: E402
from app.deps import AppState, get_state, reset_state  # noqa: E402


class FakeOllama:
    """Deterministic stand-in for OllamaClient.

    Embeddings are hashed bag-of-words vectors so lexical overlap between
    query and document produces semantic proximity. ``chat`` inspects the
    system prompt: RAG prompts answer with a [1] citation, chat prompts
    return small talk.
    """

    DIM = 64

    def __init__(self):
        self.chat_calls: list[dict] = []
        self.pulls: list[str] = []

    # ----- embeddings -----
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.DIM
        for tok in re.findall(r"\w+", text.lower()):
            h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
            v[h % self.DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, model: str, text: str) -> list[float]:
        return self._vec(text)

    # ----- chat -----
    def chat(self, model: str, messages: list[dict], **kw) -> str:
        self.chat_calls.append({"model": model, "messages": messages})
        if any("Sources:" in m["content"] for m in messages):
            return "The project deadline is Friday [1]."
        return "Hello! How can I help?"

    # ----- management -----
    def list_models(self):
        from app.ollama_client import LocalModel
        return [
            LocalModel("llama3.2:3b", 2_000_000_000, "llama", "3.2B",
                       "Q4_K_M"),
            LocalModel("nomic-embed-text", 274_000_000, "nomic-bert",
                       "137M", "F16"),
        ]

    def is_model_installed(self, model: str) -> bool:
        return any(m.name == model for m in self.list_models())

    def pull_model(self, model: str):
        self.pulls.append(model)
        yield {"status": f"pulling {model}"}
        yield {"status": "success"}


@pytest.fixture()
def state(tmp_path, monkeypatch):
    cfg = AppConfig(data_dir=tmp_path / "data")
    st = AppState(cfg)
    fake = FakeOllama()
    monkeypatch.setattr(st, "ollama", fake)
    yield st
    st.close()


@pytest.fixture()
def fake_ollama(state) -> FakeOllama:
    return state.ollama


@pytest.fixture()
def client(state):
    from fastapi.testclient import TestClient
    from app.main import app

    app.dependency_overrides[get_state] = lambda: state
    reset_state(state)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    reset_state(None)
