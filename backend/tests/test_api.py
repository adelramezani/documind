"""API tests: upload flow, chat persistence, settings, model pull gate."""
import io
import time


def _wait_job(client, job_id, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        job = r.json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_upload_ingest_and_list(client):
    files = [("files", ("docs/readme.txt", b"The deployment deadline is Friday.", "text/plain"))]
    r = client.post("/api/documents/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert len(body["accepted"]) == 1
    assert body["accepted"][0]["rel_path"] == "docs/readme.txt"
    job = _wait_job(client, body["job_id"])
    assert job["status"] == "done", job
    assert job["detail"]["done"] == 1

    docs = client.get("/api/documents").json()
    assert docs[0]["status"] == "indexed"
    assert docs[0]["chunk_count"] > 0


def test_upload_duplicate_and_rejected(client):
    payload = b"same content"
    for i in range(2):
        files = [("files", ("a.txt", payload, "text/plain"))]
        body = client.post("/api/documents/upload", files=files).json()
        if i == 0:
            _wait_job(client, body["job_id"])
    assert body["duplicates"] == ["a.txt"]

    files = [("files", ("../evil.txt", b"x", "text/plain"))]
    body = client.post("/api/documents/upload", files=files).json()
    if body["job_id"]:
        _wait_job(client, body["job_id"])
    # Traversal is sanitized to a safe name rather than rejected outright,
    # but '..' must never appear in stored paths.
    for doc in client.get("/api/documents").json():
        assert ".." not in doc["rel_path"]


def test_chat_roundtrip_persists(client):
    r = client.post("/api/chat", json={"message": "hello", "mode": "auto"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "chat"
    sid = body["session_id"]

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    sessions = client.get("/api/sessions").json()
    assert sessions[0]["id"] == sid


def test_rag_chat_returns_sources(client):
    files = [("files", ("policy.txt", b"The project deadline is Friday.", "text/plain"))]
    job_id = client.post(
        "/api/documents/upload", files=files).json()["job_id"]
    _wait_job(client, job_id)

    r = client.post("/api/chat",
                    json={"message": "when is the project deadline?",
                          "mode": "auto"})
    body = r.json()
    assert body["mode"] == "rag"
    assert body["sources"][0]["document_name"] == "policy.txt"


def test_settings_get_and_update(client):
    s = client.get("/api/settings").json()
    assert s["values"]["chunk_size"] == s["defaults"]["chunk_size"]

    r = client.put("/api/settings", json={
        "values": {"chunk_size": 400, "chat_mode": "always"}})
    assert r.status_code == 200
    body = r.json()
    assert body["values"]["chunk_size"] == 400
    assert body["needs_reindex"] is True

    r = client.put("/api/settings",
                   json={"values": {"chunk_size": 5}})
    assert r.status_code == 422


def test_models_and_pull_gate(client):
    models = client.get("/api/models").json()
    names = {m["name"] for m in models}
    assert "llama3.2:3b" in names
    chat = next(m for m in models if m["name"] == "llama3.2:3b")
    assert chat["kind"] == "chat" and chat["description"]

    r = client.post("/api/models/pull", json={"model": "gemma4"})
    assert r.status_code == 400

    r = client.post("/api/models/pull",
                    json={"model": "llama3.2:3b", "confirmed": True})
    assert r.status_code == 409

    r = client.post("/api/models/pull",
                    json={"model": "gemma4", "confirmed": True})
    assert r.status_code == 200
    job = _wait_job(client, r.json()["id"])
    assert job["status"] == "done"


def test_delete_document(client):
    files = [("files", ("gone.txt", b"temporary", "text/plain"))]
    body = client.post("/api/documents/upload", files=files).json()
    _wait_job(client, body["job_id"])
    doc_id = body["accepted"][0]["id"]
    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get("/api/documents").json() == []
