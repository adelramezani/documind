import { useCallback, useEffect, useState } from "react";
import { api, type Session } from "./api";
import ChatView from "./components/ChatView";
import DocumentsView from "./components/DocumentsView";
import ModelsView from "./components/ModelsView";
import SettingsView from "./components/SettingsView";

type Tab = "chat" | "documents" | "models" | "settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  const refreshSessions = useCallback(() => {
    api.sessions().then(setSessions).catch(() => undefined);
  }, []);

  useEffect(() => {
    api.health().catch(() =>
      setBackendError("Backend unreachable — start the FastAPI server."),
    );
    refreshSessions();
  }, [refreshSessions]);

  const newChat = () => {
    setActiveSession(null);
    setTab("chat");
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">Documind</div>
        <button className="primary" onClick={newChat}>+ New chat</button>
        <nav>
          {(["chat", "documents", "models", "settings"] as Tab[]).map((t) => (
            <button key={t}
                    className={tab === t ? "nav active" : "nav"}
                    onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>
        {tab === "chat" && (
          <div className="session-list">
            {sessions.map((s) => (
              <button key={s.id}
                      className={
                        s.id === activeSession ? "session active" : "session"
                      }
                      onClick={() => setActiveSession(s.id)}
                      title={s.title}>
                {s.title}
              </button>
            ))}
          </div>
        )}
      </aside>
      <main className="main">
        {backendError && <div className="banner error">{backendError}</div>}
        {tab === "chat" && (
          <ChatView sessionId={activeSession}
                    onSessionChange={(id) => {
                      setActiveSession(id);
                      refreshSessions();
                    }} />
        )}
        {tab === "documents" && <DocumentsView />}
        {tab === "models" && <ModelsView />}
        {tab === "settings" && <SettingsView />}
      </main>
    </div>
  );
}
