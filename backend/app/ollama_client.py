"""Ollama integration: model listing, streaming pulls, chat, embeddings.

Chat and embedding calls go through langchain-ollama; model management
(list/pull) uses Ollama's HTTP API directly so we can stream pull progress.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator

import httpx


class OllamaUnavailable(Exception):
    pass


class ModelNotFound(Exception):
    pass


@dataclass
class LocalModel:
    name: str
    size: int
    family: str | None
    parameter_size: str | None
    quantization: str | None


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, timeout: float = 10.0) -> dict:
        try:
            r = httpx.get(f"{self.base_url}{path}", timeout=timeout)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f"Ollama unreachable: {exc}") from exc

    def list_models(self) -> list[LocalModel]:
        data = self._get("/api/tags")
        models = []
        for m in data.get("models", []):
            d = m.get("details") or {}
            models.append(
                LocalModel(
                    name=m.get("name") or m.get("model"),
                    size=m.get("size", 0),
                    family=d.get("family"),
                    parameter_size=d.get("parameter_size"),
                    quantization=d.get("quantization_level"),
                )
            )
        return models

    def is_model_installed(self, model: str) -> bool:
        try:
            return any(
                m.name == model or m.name == f"{model}:latest"
                or m.name.split(":")[0] == model.split(":")[0]
                for m in self.list_models()
            )
        except OllamaUnavailable:
            raise

    def pull_model(self, model: str) -> Iterator[dict]:
        """Stream pull progress events from Ollama. Caller must have obtained
        user confirmation before invoking this."""
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"model": model, "stream": True},
                timeout=None,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        yield json.loads(line)
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f"pull failed: {exc}") from exc

    def _resolve_model(self, model: str) -> str:
        """Map a possibly-untagged name to an installed tag.

        Ollama's generate/embed endpoints require exact tags; a bare
        ``name`` resolves to the installed ``name:latest`` (or the first
        installed variant) when present.
        """
        if ":" in model:
            return model
        try:
            for m in self.list_models():
                if m.name == f"{model}:latest" or m.name.split(":")[0] == model:
                    return m.name
        except OllamaUnavailable:
            pass
        return model

    # ----- LangChain-backed inference --------------------------------------
    def chat(self, model: str, messages: list[dict[str, str]],
             temperature: float = 0.2, num_ctx: int = 8192,
             num_predict: int = 1024) -> str:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=self._resolve_model(model),
            base_url=self.base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
        )
        try:
            resp = llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - surface model errors cleanly
            raise OllamaUnavailable(f"chat failed for {model}: {exc}") from exc
        return resp.content if isinstance(resp.content, str) else str(resp.content)

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        from langchain_ollama import OllamaEmbeddings

        emb = OllamaEmbeddings(model=self._resolve_model(model),
                               base_url=self.base_url)
        try:
            return emb.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            raise OllamaUnavailable(
                f"embedding failed for {model}: {exc}") from exc

    def embed_query(self, model: str, text: str) -> list[float]:
        from langchain_ollama import OllamaEmbeddings

        emb = OllamaEmbeddings(model=self._resolve_model(model),
                               base_url=self.base_url)
        try:
            return emb.embed_query(text)
        except Exception as exc:  # noqa: BLE001
            raise OllamaUnavailable(
                f"embedding failed for {model}: {exc}") from exc
