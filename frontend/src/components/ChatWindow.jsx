import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";

function Sources({ sources }) {
  const pages = (sources || [])
    .map((s) => s.page)
    .filter((p) => p !== null && p !== undefined)
    .sort((a, b) => a - b);
  if (pages.length === 0) return null;
  return <div className="sources">Sources: page {pages.join(", ")}</div>;
}

export default function ChatWindow({ messages, loading }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="chat-window">
      {messages.length === 0 && !loading && (
        <div className="placeholder">Ask a question about the report to get started.</div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`row ${m.role === "human" ? "user" : "ai"}`}>
          <div className="avatar">{m.role === "human" ? "You" : "AI"}</div>
          <div className="bubble">
            {m.role === "human" ? (
              <p>{m.content}</p>
            ) : (
              <>
                <ReactMarkdown>{m.content}</ReactMarkdown>
                <Sources sources={m.sources} />
              </>
            )}
          </div>
        </div>
      ))}
      {loading && (
        <div className="row ai">
          <div className="avatar">AI</div>
          <div className="bubble typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
