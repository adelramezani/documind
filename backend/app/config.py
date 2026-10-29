"""Application configuration via pydantic-settings.

All paths default to ``<repo>/data`` so the app is self-contained; override
with ``DOCUMIND_*`` environment variables or a ``.env`` file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_", env_file=".env", extra="ignore"
    )

    data_dir: Path = _REPO_ROOT / "data"
    ollama_base_url: str = "http://localhost:11434"
    host: str = "127.0.0.1"
    port: int = 8000
    max_upload_mb: int = 100

    @property
    def db_path(self) -> Path:
        return self.data_dir / "documind.db"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_config() -> AppConfig:
    cfg = AppConfig()
    cfg.ensure_dirs()
    return cfg
