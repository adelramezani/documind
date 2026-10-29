import { useCallback, useEffect, useState } from "react";
import { api, pollJob, type ModelInfo } from "../api";

function fmtSize(bytes: number | null): string {
  if (!bytes) return "—";
  return `${(bytes / 1e9).toFixed(1)} GB`;
}

export default function ModelsView() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pullName, setPullName] = useState("");

  const refresh = useCallback(() => {
    api.models().then(setModels).catch((e) =>
      setError(e instanceof Error ? e.message : "Ollama unreachable"),
    );
  }, []);

  useEffect(refresh, [refresh]);

  const pull = useCallback(async () => {
    const name = pullName.trim();
    if (!name) return;
    const ok = window.confirm(
      `Download "${name}" from the Ollama registry?\n\n` +
      "This is the only operation that uses the network. " +
      "Continue?",
    );
    if (!ok) return;
    setError(null);
    setStatus(`Pulling ${name}…`);
    try {
      const job = await api.pullModel(name);
      const done = await pollJob(job.id, (j) => {
        const d = j.detail as { status?: string; completed?: number;
                              total?: number };
        const pct = d.total
          ? ` ${Math.round(((d.completed ?? 0) / d.total) * 100)}%`
          : "";
        setStatus(`Pulling ${name}: ${d.status ?? "working"}${pct}`);
      });
      if (done.status === "failed") {
        setError(String((done.detail as { error?: string }).error));
        setStatus(null);
      } else {
        setStatus(`${name} installed.`);
        refresh();
      }
    } catch (e) {
      setStatus(null);
      setError(e instanceof Error ? e.message : "pull failed");
    }
  }, [pullName, refresh]);

  const chats = models.filter((m) => m.kind === "chat");
  const embeds = models.filter((m) => m.kind === "embedding");

  return (
    <div className="panel">
      <h2>Models</h2>
      <p className="muted">
        Models run locally through Ollama. Pulling a missing model is the
        only network operation and always asks for your confirmation.
      </p>
      {error && <div className="banner error">{error}</div>}
      {status && <div className="banner">{status}</div>}

      <div className="pull-row">
        <input value={pullName} placeholder="model name, e.g. qwen3:8b"
               onChange={(e) => setPullName(e.target.value)} />
        <button onClick={() => void pull()} disabled={!pullName.trim()}>
          Pull model…
        </button>
      </div>

      {([["Chat models", chats], ["Embedding models", embeds]] as const).map(
        ([title, list]) => (
          <section key={title as string}>
            <h3>{title}</h3>
            <table className="doc-table">
              <thead>
                <tr><th>Name</th><th>Params</th><th>Quant</th>
                    <th>Size</th><th>Good for</th></tr>
              </thead>
              <tbody>
                {(list as ModelInfo[]).map((m) => (
                  <tr key={m.name}>
                    <td>{m.name}</td>
                    <td>{m.parameter_size ?? "—"}</td>
                    <td>{m.quantization ?? "—"}</td>
                    <td>{fmtSize(m.size)}</td>
                    <td className="muted">{m.description}</td>
                  </tr>
                ))}
                {(list as ModelInfo[]).length === 0 && (
                  <tr><td colSpan={5} className="muted">None installed</td></tr>
                )}
              </tbody>
            </table>
          </section>
        ),
      )}
    </div>
  );
}
