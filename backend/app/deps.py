"""Application state and FastAPI dependencies."""
from __future__ import annotations

from pathlib import Path

from .config import AppConfig, get_config
from .db import Database
from .jobs import JobRunner
from .ollama_client import OllamaClient
from .rag.vectorstore import VectorStore
from .settings import RagSettings, load_settings


class AppState:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or get_config()
        self.config.ensure_dirs()
        self.db = Database(self.config.db_path)
        self.ollama = OllamaClient(self.config.ollama_base_url)
        self.jobs = JobRunner(self.db)
        self._stores: dict[str, VectorStore] = {}

    def settings(self) -> RagSettings:
        return load_settings(self.db)

    def vectorstore(self) -> VectorStore:
        model = self.settings().embedding_model
        if model not in self._stores:
            self._stores[model] = VectorStore(
                self.config.chroma_dir, model)
        return self._stores[model]

    def upload_path(self, document_id: str) -> Path:
        return self.config.upload_dir / document_id

    def close(self) -> None:
        self.db.close()


_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_state(state: AppState | None) -> None:
    """Test hook: replace the global state."""
    global _state
    _state = state
