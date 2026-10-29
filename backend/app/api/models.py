"""Settings and Ollama model management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ..deps import AppState, get_state
from ..ollama_client import OllamaUnavailable
from ..schemas import (JobOut, ModelInfo, PullRequest, SettingsOut,
                       SettingsUpdate)
from ..settings import DEFAULTS, RagSettings, load_settings, save_settings

router = APIRouter(prefix="/api", tags=["settings"])

# Curated catalogue: description + role shown in the UI. Names match
# Ollama tags; installed models not listed here still appear.
CATALOG: dict[str, dict] = {
    "llama3.2:3b": {"kind": "chat",
                    "description": "Small general-purpose chat model; good "
                                   "default for fast local answers."},
    "llama3.2:1b": {"kind": "chat",
                    "description": "Very small, fastest replies; weaker "
                                   "reasoning — good for low-RAM machines."},
    "qwen3.6": {"kind": "chat",
                "description": "Strong general reasoning and multilingual "
                               "chat; larger download."},
    "gemma4": {"kind": "chat",
               "description": "Capable mid-size model; good for summarizing "
                              "and grounded answers."},
    "mistral": {"kind": "chat",
                "description": "Solid all-round instruction following."},
    "deepseek-r1:7b": {"kind": "chat",
                       "description": "Reasoning-focused model; slower but "
                                      "better at multi-step questions."},
    "nomic-embed-text": {"kind": "embedding",
                         "description": "Default embedding model for "
                                        "document retrieval."},
    "mxbai-embed-large": {"kind": "embedding",
                          "description": "Larger embedding model; better "
                                         "recall on long documents."},
    "all-minilm": {"kind": "embedding",
                   "description": "Tiny, fast embedding model; slightly "
                                  "lower retrieval quality."},
    "granite-embedding:30m": {"kind": "embedding",
                              "description": "Small IBM embedding model; "
                                             "good speed/quality balance."},
}

EMBEDDING_HINTS = ("embed", "minilm", "bge")


def _kind_of(name: str) -> str:
    low = name.lower()
    return "embedding" if any(h in low for h in EMBEDDING_HINTS) else "chat"


@router.get("/settings", response_model=SettingsOut)
def get_settings(state: AppState = Depends(get_state)) -> SettingsOut:
    s = load_settings(state.db)
    return SettingsOut(values=s.model_dump(), defaults=dict(DEFAULTS))


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsUpdate,
                 state: AppState = Depends(get_state)) -> SettingsOut:
    current = load_settings(state.db)
    merged = {**current.model_dump(),
              **{k: v for k, v in body.values.items() if k in DEFAULTS}}
    try:
        new = RagSettings(**merged)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()) from exc
    save_settings(state.db, new)
    return SettingsOut(values=new.model_dump(), defaults=dict(DEFAULTS),
                       needs_reindex=current.needs_reindex(new))


@router.get("/models", response_model=list[ModelInfo])
def list_models(state: AppState = Depends(get_state)) -> list[ModelInfo]:
    try:
        installed = state.ollama.list_models()
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    out = []
    for m in installed:
        cat = CATALOG.get(m.name, {})
        out.append(ModelInfo(
            name=m.name, size=m.size, family=m.family,
            parameter_size=m.parameter_size,
            quantization=m.quantization,
            kind=cat.get("kind", _kind_of(m.name)),
            description=cat.get("description", "Installed local model."),
        ))
    return out


@router.post("/models/pull", response_model=JobOut)
def pull_model(body: PullRequest,
               state: AppState = Depends(get_state)) -> JobOut:
    """Pull a model only after explicit user confirmation."""
    if not body.confirmed:
        raise HTTPException(
            400, "model downloads require confirmed=true")
    model = body.model.strip()
    if not model or any(c in model for c in " \t\n/\\"):
        raise HTTPException(422, "invalid model name")
    try:
        if state.ollama.is_model_installed(model):
            raise HTTPException(409, f"{model} already installed")
    except OllamaUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    def run(job_id: str) -> dict:
        last = {}
        for event in state.ollama.pull_model(model):
            last = event
            state.jobs.progress(job_id, {"model": model, **event})
        return {"model": model, "status": last.get("status", "done")}

    job_id = state.jobs.submit("model_pull", run, {"model": model})
    return _job_out(state.jobs.get(job_id))


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str,
            state: AppState = Depends(get_state)) -> JobOut:
    row = state.jobs.get(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return _job_out(row)


def _job_out(row: dict) -> JobOut:
    import json
    return JobOut(id=row["id"], type=row["type"], status=row["status"],
                  detail=json.loads(row["detail_json"]),
                  created_at=row["created_at"],
                  updated_at=row["updated_at"])
