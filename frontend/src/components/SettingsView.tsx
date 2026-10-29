import { useCallback, useEffect, useState } from "react";
import { api, type ModelInfo, type SettingsPayload } from "../api";

const NUMERIC = new Set([
  "chunk_size", "chunk_overlap", "retrieval_top_k", "rerank_top_n",
  "num_ctx", "max_answer_tokens",
]);

const LABELS: Record<string, string> = {
  chunk_size: "Chunk size (characters)",
  chunk_overlap: "Chunk overlap (characters)",
  retrieval_top_k: "Retrieval candidates (top-k)",
  rerank_top_n: "Sources used in answer (top-n)",
  lexical_weight: "Lexical search weight (0–1)",
  temperature: "Temperature",
  num_ctx: "Context window (tokens)",
  max_answer_tokens: "Max answer length (tokens)",
  chat_mode: "Document retrieval default",
  chat_model: "Chat model",
  embedding_model: "Embedding model",
};

export default function SettingsView() {
  const [payload, setPayload] = useState<SettingsPayload | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.settings().then((p) => {
      setPayload(p);
      setForm(p.values);
    }).catch((e) => setError(e instanceof Error ? e.message : "load failed"));
    api.models().then(setModels).catch(() => undefined);
  }, []);

  const save = useCallback(async () => {
    setError(null);
    try {
      const p = await api.saveSettings(form);
      setPayload(p);
      setForm(p.values);
      setStatus(p.needs_reindex
        ? "Saved — chunking/embedding changed, reindex documents to apply."
        : "Saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    }
  }, [form]);

  const reset = useCallback(() => {
    if (payload) setForm(payload.defaults);
  }, [payload]);

  if (!payload) return <div className="panel">Loading…</div>;

  const chatModels = models.filter((m) => m.kind === "chat");
  const embedModels = models.filter((m) => m.kind === "embedding");

  const set = (k: string) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const v = NUMERIC.has(k) ? Number(e.target.value) : e.target.value;
      setForm((f) => ({ ...f, [k]: v }));
    };

  const modelSelect = (key: string, list: ModelInfo[]) => (
    <select value={String(form[key] ?? "")} onChange={set(key)}>
      <option value={String(form[key] ?? "")}>{String(form[key] ?? "")}</option>
      {list.filter((m) => m.name !== form[key]).map((m) => (
        <option key={m.name} value={m.name}>{m.name}</option>
      ))}
    </select>
  );

  return (
    <div className="panel">
      <h2>Settings</h2>
      {status && <div className="banner">{status}</div>}
      {error && <div className="banner error">{error}</div>}
      <div className="settings-grid">
        {(["chunk_size", "chunk_overlap", "retrieval_top_k", "rerank_top_n",
           "lexical_weight", "temperature", "num_ctx",
           "max_answer_tokens"] as const).map((k) => (
          <label key={k}>
            {LABELS[k]}
            <span className="default-hint">
              default: {String(payload.defaults[k])}
            </span>
            <input type="number" step={k === "lexical_weight" ||
                   k === "temperature" ? "0.05" : "1"}
                   value={Number(form[k])} onChange={set(k)} />
          </label>
        ))}
        <label>
          {LABELS.chat_mode}
          <span className="default-hint">
            default: {String(payload.defaults.chat_mode)}
          </span>
          <select value={String(form.chat_mode)} onChange={set("chat_mode")}>
            <option value="auto">Auto</option>
            <option value="always">Always use documents</option>
            <option value="never">Normal chat only</option>
          </select>
        </label>
        <label>
          {LABELS.chat_model}
          <span className="default-hint">
            default: {String(payload.defaults.chat_model)}
          </span>
          {modelSelect("chat_model", chatModels)}
        </label>
        <label>
          {LABELS.embedding_model}
          <span className="default-hint">
            default: {String(payload.defaults.embedding_model)}
          </span>
          {modelSelect("embedding_model", embedModels)}
        </label>
      </div>
      <div className="settings-actions">
        <button className="primary" onClick={() => void save()}>Save</button>
        <button onClick={reset}>Reset to defaults</button>
      </div>
    </div>
  );
}
