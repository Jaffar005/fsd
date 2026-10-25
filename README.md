# Conversational RAG: React + FastAPI + MongoDB

Your Streamlit/SQLite RAG app, converted to a React frontend, a FastAPI backend and MongoDB.
The RAG logic is unchanged: `PyPDFLoader` → `RecursiveCharacterTextSplitter` (1000/150) →
`all-MiniLM-L6-v2` embeddings → Chroma (`k=4`) → Groq `openai/gpt-oss-120b`.

```
backend/    FastAPI + LangChain + MongoDB
  main.py   API endpoints
  rag.py    RAG pipeline + chat-title generation (Groq)
  db.py     MongoDB code (replaces SQLite)
frontend/   React (Vite)
  src/components/  Sidebar, ChatWindow, ChatInput
```

## Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB running locally (`mongodb://localhost:27017`) or a MongoDB Atlas URI
- A Groq API key

## 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then put your GROQ_API_KEY (and MONGO_URI if needed) in .env
# copy your PDF into the backend folder and name it report.pdf (or set PDF_PATH in .env)

uvicorn main:app --reload --port 8000
```

On startup it checks the MongoDB connection and builds the vector store once
(the first run downloads the embedding model, so it can take a minute).
API docs: http://127.0.0.1:8000/docs

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In dev, Vite proxies `/api` to the backend on port 8000.
If your backend runs elsewhere, create `frontend/.env` with `VITE_API_URL=http://host:port`
and add that frontend origin to `CORS_ORIGINS` in the backend `.env`.

## API

| Method | Path                              | Purpose                                              |
|--------|-----------------------------------|------------------------------------------------------|
| GET    | `/api/sessions`                   | List chats, newest first                             |
| GET    | `/api/sessions/{id}/messages`     | Full history of one chat                             |
| POST   | `/api/chat`                       | `{session_id?, message}`: omit `session_id` to start a new chat |

## MongoDB schema (replaces the SQLite `chat_history` table)

- `sessions`: `{ _id: session_id, title, title_generated, created_at, updated_at }`
- `messages`: `{ session_id, role: "human" | "ai", content, sources, created_at }`
  with an index on `(session_id, created_at)`

## Chat titles
A new chat is created when its first question is sent. The sidebar first shows the question
(first ~40 characters), then a background Groq call (`TITLE_MODEL`, default `llama-3.1-8b-instant`)
replaces it with a 3-6 word title. If that call fails, the truncated question stays.

## Changes from the original code
- Fixed: the current question was sent to the model twice (once in the history, once as `input`).
  History is now loaded before the new question is saved.
- Fixed typos in the system prompt ("Al" → "AI", "Asnwer" → "Answer").
- Page numbers of the retrieved chunks are shown under each answer (1-based; PyPDFLoader's
  internal page index is 0-based).
- Sessions are titled from the user's question instead of the UUID.
- Embeddings stay local (Groq has no embeddings API); Groq is used for answers and titles.
- The Chroma store is still in-memory and rebuilt at every server start, as in your original app.
