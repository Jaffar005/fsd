import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import ChatInput from "./components/ChatInput.jsx";
import { getMessages, getSessions, sendChat } from "./api.js";

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null); // null = a new, unsaved chat
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pollTimer = useRef(null);

  const refreshSessions = useCallback(async (isInitial = false, retries = 5) => {
    try {
      const data = await getSessions();
      setSessions(data);
      setError("");
      return data;
    } catch (e) {
      if (isInitial && retries > 0) {
        // Backend might still be initializing; retry silently without showing error
        setTimeout(() => refreshSessions(true, retries - 1), 1200);
        return [];
      }
      setError(e.message);
      return [];
    }
  }, []);

  useEffect(() => {
    refreshSessions(true, 5);
    return () => clearTimeout(pollTimer.current);
  }, [refreshSessions]);

  // The AI title is generated in the background after the first answer,
  // so poll the session list briefly until it shows up.
  const pollForTitle = useCallback(
    (sessionId, attempt = 0) => {
      clearTimeout(pollTimer.current);
      pollTimer.current = setTimeout(async () => {
        const data = await refreshSessions();
        const s = data.find((x) => x.session_id === sessionId);
        if (s && !s.title_generated && attempt < 8) {
          pollForTitle(sessionId, attempt + 1);
        }
      }, 1200);
    },
    [refreshSessions]
  );

  const handleNewChat = () => {
    setActiveId(null);
    setMessages([]);
    setError("");
  };

  const handleSelect = async (sessionId) => {
    if (sessionId === activeId) return;
    setError("");
    setActiveId(sessionId);
    setMessages([]);
    try {
      setMessages(await getMessages(sessionId));
    } catch (e) {
      setError(e.message);
    }
  };

  const handleSend = async (text) => {
    setError("");
    setMessages((prev) => [...prev, { role: "human", content: text }]);
    setLoading(true);
    try {
      const res = await sendChat(activeId, text);
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: res.answer, sources: res.sources },
      ]);
      const isNew = activeId === null;
      setActiveId(res.session_id);
      await refreshSessions();
      if (isNew && !res.title_generated) pollForTitle(res.session_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onNewChat={handleNewChat}
        onSelect={handleSelect}
      />
      <main className="main">
        <header className="topbar">Conversational RAG with Database Memory</header>
        <ChatWindow messages={messages} loading={loading} />
        {error && <div className="error">{error}</div>}
        <ChatInput onSend={handleSend} disabled={loading} />
      </main>
    </div>
  );
}
