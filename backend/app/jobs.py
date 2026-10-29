"""In-process background job runner (threaded, persisted in SQLite)."""
from __future__ import annotations

import json
import threading
import uuid
from typing import Callable

from .db import Database, utcnow


class JobRunner:
    def __init__(self, db: Database):
        self.db = db
        self._threads: list[threading.Thread] = []

    def submit(self, job_type: str, fn: Callable[[dict], dict],
               detail: dict | None = None) -> str:
        job_id = uuid.uuid4().hex
        now = utcnow()
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO jobs(id, type, status, detail_json,"
                " created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, job_type, "pending",
                 json.dumps(detail or {}), now, now),
            )

        def run() -> None:
            self._update(job_id, "running")
            try:
                result = fn(job_id) or {}
                merged = {**(detail or {}), **result}
                self._update(job_id, "done", merged)
            except Exception as exc:  # noqa: BLE001
                self._update(job_id, "failed",
                             {**(detail or {}), "error": str(exc)})

        t = threading.Thread(target=run, daemon=True,
                             name=f"job-{job_id[:8]}")
        t.start()
        self._threads.append(t)
        return job_id

    def _update(self, job_id: str, status: str,
                detail: dict | None = None) -> None:
        with self.db.tx() as conn:
            if detail is None:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                    (status, utcnow(), job_id))
            else:
                conn.execute(
                    "UPDATE jobs SET status=?, detail_json=?, updated_at=?"
                    " WHERE id=?",
                    (status, json.dumps(detail), utcnow(), job_id))

    def get(self, job_id: str) -> dict | None:
        return self.db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))

    def progress(self, job_id: str, patch: dict) -> None:
        row = self.get(job_id)
        detail = json.loads(row["detail_json"]) if row else {}
        detail.update(patch)
        self._update(job_id, row["status"] if row else "running", detail)
