"""FastAPI server exposing the RAG chatbot to the React frontend."""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()   # fails fast with a clear error if MongoDB is not reachable
    rag.init_rag()  # builds the vector store once
    yield


app = FastAPI(title="Conversational RAG API", lifespan=lifespan)

origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # omit to start a new chat
    message: str = Field(min_length=1)


def _generate_title_task(session_id: str, question: str) -> None:
    db.set_generated_title(session_id, rag.generate_title(question))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/sessions")
def list_sessions():
    return db.list_sessions()


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return db.get_messages(session_id)


@app.post("/api/chat")
def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")

    is_new = req.session_id is None
    if is_new:
        # Provisional title = truncated question; replaced by the Groq title below.
        session_id = db.create_session(rag.fallback_title(message))
        history = []
    else:
        session_id = req.session_id
        if not db.session_exists(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        # History is loaded BEFORE saving the new question, so it is not sent twice.
        history = rag.to_langchain_history(db.get_messages(session_id))

    try:
        answer, sources = rag.conversational_rag(message, history)
    except Exception as exc:
        if is_new:
            # Nothing was answered, so don't leave an empty chat in the sidebar.
            db.sessions.delete_one({"_id": session_id})
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")

    db.save_message(session_id, "human", message)
    db.save_message(session_id, "ai", answer, sources)

    if is_new:
        background_tasks.add_task(_generate_title_task, session_id, message)

    session = db.get_session(session_id)
    return {
        "session_id": session_id,
        "title": session["title"],
        "title_generated": session["title_generated"],
        "answer": answer,
        "sources": sources,
    }
