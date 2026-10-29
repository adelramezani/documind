"""Document upload, listing, deletion, and reindex endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from ..deps import AppState, get_state
from ..ingest.pipeline import (delete_document, ingest_document,
                               register_document, sanitize_rel_path)
from ..schemas import DocumentOut, UploadResult

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _doc_out(row: dict) -> DocumentOut:
    return DocumentOut(**{k: row[k] for k in DocumentOut.model_fields})


@router.post("/upload", response_model=UploadResult)
async def upload(files: list[UploadFile],
                 state: AppState = Depends(get_state)) -> UploadResult:
    """Accept one or more files. The multipart filename may carry the
    browser-relative path (webkitRelativePath) for folder uploads."""
    result = UploadResult()
    max_bytes = state.config.max_upload_mb * 1024 * 1024
    settings = state.settings()
    vs = state.vectorstore()
    pending: list[tuple[dict, bytes]] = []

    for f in files:
        rel = f.filename or "upload"
        try:
            rel = sanitize_rel_path(rel)
        except ValueError:
            result.rejected.append({"file": rel, "reason": "invalid path"})
            continue
        data = await f.read()
        if not data:
            result.rejected.append({"file": rel, "reason": "empty file"})
            continue
        if len(data) > max_bytes:
            result.rejected.append(
                {"file": rel, "reason": "file exceeds size limit"})
            continue
        name = rel.rsplit("/", 1)[-1]
        row, dup = register_document(
            state.db, name=name, rel_path=rel, data=data,
            mime=f.content_type)
        if dup:
            result.duplicates.append(rel)
            continue
        state.upload_path(row["id"]).write_bytes(data)
        pending.append((row, data))
        result.accepted.append(_doc_out(row))

    if pending:
        def run(job_id: str) -> dict:
            done = failed = 0
            for row, data in pending:
                res = ingest_document(state.db, vs, state.ollama,
                                      settings, row["id"], data)
                done += res.status == "indexed"
                failed += res.status != "indexed"
                state.jobs.progress(
                    job_id, {"done": done, "failed": failed,
                             "total": len(pending)})
            return {"done": done, "failed": failed, "total": len(pending)}

        result.job_id = state.jobs.submit(
            "ingest", run, {"total": len(pending)})
    return result


@router.get("", response_model=list[DocumentOut])
def list_documents(state: AppState = Depends(get_state)) -> list[DocumentOut]:
    rows = state.db.fetchall(
        "SELECT * FROM documents ORDER BY created_at DESC")
    return [_doc_out(r) for r in rows]


@router.delete("/{document_id}")
def remove_document(document_id: str,
                    state: AppState = Depends(get_state)) -> dict:
    ok = delete_document(state.db, state.vectorstore(), document_id)
    if not ok:
        raise HTTPException(404, "document not found")
    path = state.upload_path(document_id)
    if path.exists():
        path.unlink()
    return {"deleted": document_id}


@router.post("/reindex")
def reindex(state: AppState = Depends(get_state)) -> dict:
    from ..ingest.pipeline import reindex_all

    docs = state.db.fetchall("SELECT * FROM documents")
    uploads = {}
    for d in docs:
        p = state.upload_path(d["id"])
        if p.exists():
            uploads[d["id"]] = p.read_bytes()

    def run(job_id: str) -> dict:
        return reindex_all(state.db, state.vectorstore(), state.ollama,
                           state.settings(), uploads)

    job_id = state.jobs.submit("reindex", run, {"total": len(docs)})
    return {"job_id": job_id, "total": len(docs)}
