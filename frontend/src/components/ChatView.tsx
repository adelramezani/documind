import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Message, type SourceRef } from "../api";

type Mode = "auto" | "always" | "never";

interface Props {
  sessionId: string | null;
  onSessionChange: (id: string) => void;
}

function sourceLabel(s: SourceRef): string {
  const parts = [s.document_name];
  if (s.page != null) parts.push(`p. ${s.page}`);
  else if (s.sheet) parts.push(`sheet ${s.sheet}`);
  else if (s.slide != null) parts.push(`slide ${s.slide}`);
  return parts.join(", ");
}

function SourcesPanel({ sources, onClose }: {
  sources: SourceRef[];
  onClose: () => void;
}) {
  return (
    <div className="sources-panel" data-testid="sources-panel">
      <div className="sources-head">
        <strong>Answer sources</strong>
        <button onClick={onClose} aria-label="close sources">×</button>
      </div>
      {sources.length === 0 && (
        <p className="muted">No document sources were used for this answer.</p>
      )}
      {sources.map((s) => (
        <div key={s.chunk_id} className="source-card">
          <div className="source-title">{sourceLabel(s)}</div>
          <div className="source-path">{s.rel_path} · score {s.score}</div>
          <div className="source-snippet">{s.snippet}</div>
        </div>
      ))}
    </div>
  );
}

export default function ChatView({ sessionId, onSessionChange }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoFor, setInfoFor] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sessionId) {
      api.messages(sessionId).then(setMessages).catch(() => setMessages([]));
    } else {
      setMessages([]);
    }
    setInfoFor(null);
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    const pending: Message = {
      id: -Date.now(), session_id: sessionId ?? "", role: "user",
      content: text, mode: null, sources: [], created_at: "",
    };
    setMessages((m) => [...m, pending]);
    try {
      const resp = await api.chat(text, sessionId, mode);
      if (!sessionId) onSessionChange(resp.session_id);
      const answer: Message = {
        id: resp.message_id, session_id: resp.session_id,
        role: "assistant", content: resp.content, mode: resp.mode,
        sources: resp.sources, created_at: "",
      };
      setMessages((m) => [...m, answer]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
      setMessages((m) => m.filter((x) => x.id !== pending.id));
    } finally {
      setBusy(false);
    }
  }, [input, busy, mode, sessionId, onSessionChange]);

  return (
    <div className="chat">
      <div className="chat-toolbar">
        <label>
          Document retrieval:{" "}
          <select value={mode}
                  onChange={(e) => setMode(e.target.value as Mode)}>
            <option value="auto">Auto</option>
            <option value="always">Always use documents</option>
            <option value="never">Normal chat only</option>
          </select>
        </label>
      </div>
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            Ask a question — Documind answers normally, or retrieves from
            your documents when needed.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="msg-body">{m.content}</div>
            {m.role === "assistant" && (
              <div className="msg-meta">
                {m.mode === "rag" && m.sources.length > 0 && (
                  <span className="badge grounded">
                    grounded in {m.sources.length} source
                    {m.sources.length > 1 ? "s" : ""}
                  </span>
                )}
                {m.mode === "rag_no_evidence" && (
                  <span className="badge warn">no evidence in documents</span>
                )}
                <button className="info-btn"
                        title="Show answer sources"
                        aria-label="answer details"
                        onClick={() =>
                          setInfoFor(infoFor === m.id ? null : m.id)}>
                  ⓘ
                </button>
              </div>
            )}
            {infoFor === m.id && (
              <SourcesPanel sources={m.sources}
                            onClose={() => setInfoFor(null)} />
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      {error && <div className="banner error">{error}</div>}
      <div className="composer">
        <textarea
          value={input}
          placeholder="Type a message…"
          rows={2}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />
        <button className="primary" disabled={busy || !input.trim()}
                onClick={() => void send()}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
