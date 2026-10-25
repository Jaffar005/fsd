export default function Sidebar({ sessions, activeId, onNewChat, onSelect }) {
  return (
    <aside className="sidebar">
      <h2 className="sidebar-title">Chats</h2>
      <button className="new-chat" onClick={onNewChat}>
        + New Chat
      </button>
      <div className="sidebar-label">Previous Conversations</div>
      <nav className="session-list">
        {sessions.length === 0 && (
          <div className="empty-sessions">No conversations yet</div>
        )}
        {sessions.map((s) => (
          <button
            key={s.session_id}
            className={`session-item ${s.session_id === activeId ? "active" : ""}`}
            onClick={() => onSelect(s.session_id)}
            title={s.title}
          >
            {s.title}
          </button>
        ))}
      </nav>
    </aside>
  );
}
