/** Typed client for the Documind backend. */

export interface SourceRef {
  chunk_id: string;
  document_id: string;
  document_name: string;
  rel_path: string;
  page: number | null;
  sheet: string | null;
  slide: number | null;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  session_id: string;
  message_id: number;
  role: string;
  content: string;
  mode: string;
  sources: SourceRef[];
  grounded: boolean;
}

export interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  mode: string | null;
  sources: SourceRef[];
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  name: string;
  rel_path: string;
  sha256: string;
  size: number;
  mime: string | null;
  status: "pending" | "indexed" | "failed";
  error: string | null;
  chunk_count: number;
  created_at: string;
}

export interface UploadResult {
  accepted: DocumentItem[];
  duplicates: string[];
  rejected: { file?: string; reason?: string }[];
  job_id: string | null;
}

export interface Job {
  id: string;
  type: string;
  status: "pending" | "running" | "done" | "failed";
  detail: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SettingsPayload {
  values: Record<string, unknown>;
  defaults: Record<string, unknown>;
  needs_reindex: boolean;
}

export interface ModelInfo {
  name: string;
  size: number | null;
  family: string | null;
  parameter_size: string | null;
  quantization: string | null;
  kind: "chat" | "embedding";
  description: string;
  installed: boolean;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `${r.status} ${r.statusText}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string }>("/api/health"),

  chat: (message: string, sessionId: string | null, mode: string) =>
    req<ChatResponse>("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId, mode }),
    }),

  sessions: () => req<Session[]>("/api/sessions"),
  messages: (id: string) => req<Message[]>(`/api/sessions/${id}/messages`),
  deleteSession: (id: string) =>
    req<{ deleted: string }>(`/api/sessions/${id}`, { method: "DELETE" }),

  documents: () => req<DocumentItem[]>("/api/documents"),
  upload: (files: File[]) => {
    const fd = new FormData();
    for (const f of files) {
      const rel = (f as File & { webkitRelativePath?: string })
        .webkitRelativePath;
      fd.append("files", f, rel && rel.length > 0 ? rel : f.name);
    }
    return req<UploadResult>("/api/documents/upload", {
      method: "POST",
      body: fd,
    });
  },
  deleteDocument: (id: string) =>
    req<{ deleted: string }>(`/api/documents/${id}`, { method: "DELETE" }),
  reindex: () =>
    req<{ job_id: string; total: number }>("/api/documents/reindex", {
      method: "POST",
    }),

  settings: () => req<SettingsPayload>("/api/settings"),
  saveSettings: (values: Record<string, unknown>) =>
    req<SettingsPayload>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    }),

  models: () => req<ModelInfo[]>("/api/models"),
  pullModel: (model: string) =>
    req<Job>("/api/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, confirmed: true }),
    }),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
};

export async function pollJob(id: string,
                              onUpdate?: (j: Job) => void): Promise<Job> {
  // Poll until the job settles; caller shows progress from detail.
  for (;;) {
    const job = await api.job(id);
    onUpdate?.(job);
    if (job.status === "done" || job.status === "failed") return job;
    await new Promise((r) => setTimeout(r, 400));
  }
}
