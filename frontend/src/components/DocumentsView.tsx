import { useCallback, useEffect, useRef, useState } from "react";
import { api, pollJob, type DocumentItem } from "../api";

export default function DocumentsView() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dirRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    api.documents().then(setDocs).catch((e) =>
      setError(e instanceof Error ? e.message : "failed to load"),
    );
  }, []);

  useEffect(refresh, [refresh]);

  const upload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    setStatus(`Uploading ${files.length} file(s)…`);
    try {
      const res = await api.upload(Array.from(files));
      const notes: string[] = [];
      if (res.duplicates.length)
        notes.push(`${res.duplicates.length} duplicate(s) skipped`);
      for (const r of res.rejected)
        notes.push(`${r.file}: ${r.reason}`);
      if (res.job_id) {
        setStatus(`Indexing ${res.accepted.length} file(s)…`);
        const job = await pollJob(res.job_id);
        const d = job.detail as { done?: number; failed?: number };
        notes.push(`indexed ${d.done ?? 0}, failed ${d.failed ?? 0}`);
      }
      setStatus(notes.join(" · ") || "Done");
      refresh();
    } catch (e) {
      setStatus(null);
      setError(e instanceof Error ? e.message : "upload failed");
    }
  }, [refresh]);

  const remove = useCallback(async (id: string) => {
    await api.deleteDocument(id);
    refresh();
  }, [refresh]);

  const reindex = useCallback(async () => {
    setError(null);
    setStatus("Reindexing…");
    try {
      const { job_id } = await api.reindex();
      const job = await pollJob(job_id);
      const d = job.detail as { reindexed?: number; failed?: number };
      setStatus(`reindexed ${d.reindexed ?? 0}, failed ${d.failed ?? 0}`);
      refresh();
    } catch (e) {
      setStatus(null);
      setError(e instanceof Error ? e.message : "reindex failed");
    }
  }, [refresh]);

  return (
    <div className="panel">
      <h2>Documents</h2>
      <div className="upload-row">
        <button className="primary" onClick={() => fileRef.current?.click()}>
          Add files
        </button>
        <button onClick={() => dirRef.current?.click()}>
          Add folder
        </button>
        <button onClick={() => void reindex()} disabled={docs.length === 0}>
          Reindex all
        </button>
        <input ref={fileRef} type="file" multiple hidden
               onChange={(e) => void upload(e.target.files)} />
        <input ref={dirRef} type="file" hidden
               // @ts-expect-error webkitdirectory is non-standard but supported
               webkitdirectory=""
               onChange={(e) => void upload(e.target.files)} />
      </div>
      {status && <div className="banner">{status}</div>}
      {error && <div className="banner error">{error}</div>}
      <table className="doc-table">
        <thead>
          <tr><th>Path</th><th>Status</th><th>Chunks</th><th></th></tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              <td title={d.rel_path}>{d.rel_path}</td>
              <td>
                <span className={`badge ${d.status}`}>{d.status}</span>
                {d.error && <div className="err-detail">{d.error}</div>}
              </td>
              <td>{d.chunk_count}</td>
              <td>
                <button onClick={() => void remove(d.id)}>Delete</button>
              </td>
            </tr>
          ))}
          {docs.length === 0 && (
            <tr><td colSpan={4} className="muted">
              No documents yet — add files or a folder to begin.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
