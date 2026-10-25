"""RAG pipeline: same LangChain logic as the Streamlit app, moved out of the UI."""
import os
import re
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

PDF_PATH = os.getenv("PDF_PATH", "report.pdf")
CHAT_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-oss-120b")
TITLE_MODEL = os.getenv("TITLE_MODEL", "llama-3.1-8b-instant")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Filled in by init_rag() at server startup (the Streamlit @st.cache_resource equivalent).
retriever = None
llm = None
title_llm = None

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(
            content=(
                "You are a helpful AI Assistant. Answer strictly from the provided "
                "context. If the answer is not present in the context, just say you "
                "don't know.\n"
                "Format your responses cleanly and readability using standard Markdown: "
                "use clear headings, bullet points, and normal paragraph spacing. "
                "Do NOT use HTML tags like <br>."
            )
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "Context: \n {context} \n\n question: \n{input}"),
    ]
)

title_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You write short chat titles. Given the user's first question, reply with "
            "a title of 3 to 6 words that captures the topic. Reply with the title "
            "only: no quotes, no trailing punctuation, no explanation.",
        ),
        ("human", "{question}"),
    ]
)


def init_rag() -> None:
    """Load the PDF, build the vector store once, and create the Groq clients."""
    global retriever, llm, title_llm

    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(
            f"PDF not found at '{PDF_PATH}'. Put your PDF there or set PDF_PATH in .env."
        )

    CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
    embeddings = FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)

    if os.path.exists(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0:
        vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    else:
        documents = PyPDFLoader(PDF_PATH).load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(
            documents=chunks, embedding=embeddings, persist_directory=CHROMA_DIR
        )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    llm = ChatGroq(model=CHAT_MODEL)
    title_llm = ChatGroq(model=TITLE_MODEL, temperature=0, max_tokens=24)


def to_langchain_history(rows: List[Dict[str, Any]]) -> List[BaseMessage]:
    history: List[BaseMessage] = []
    for row in rows:
        if row["role"] == "human":
            history.append(HumanMessage(content=row["content"]))
        elif row["role"] == "ai":
            history.append(AIMessage(content=row["content"]))
    return history


def conversational_rag(
    user_input: str, chat_history: List[BaseMessage]
) -> Tuple[str, List[Dict[str, Any]]]:
    """`chat_history` must NOT include the current question (it is passed as `input`)."""
    docs = retriever.invoke(user_input)
    context = "\n\n".join(
        f"[Page {d.metadata.get('page', 'N/A')}]\n{d.page_content}" for d in docs
    )
    messages = prompt.invoke(
        {"input": user_input, "context": context, "chat_history": chat_history}
    )
    response = llm.invoke(messages)

    sources: List[Dict[str, Any]] = []
    seen = set()
    for d in docs:
        page = d.metadata.get("page")
        # PyPDFLoader pages are 0-based; show human-friendly 1-based numbers.
        label = page + 1 if isinstance(page, int) else None
        if label in seen:
            continue
        seen.add(label)
        sources.append({"page": label, "snippet": d.page_content[:200].strip()})
    return response.content, sources


def fallback_title(question: str, limit: int = 40) -> str:
    text = " ".join(question.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def generate_title(question: str) -> str:
    """Ask Groq for a 3-6 word title. Falls back to the truncated question on any failure."""
    try:
        result = title_llm.invoke(title_prompt.invoke({"question": question}))
        title = (result.content or "").strip().splitlines()[0] if result.content else ""
        title = re.sub(r"^[\"'`\s]+|[\"'`\s.]+$", "", title)
        title = re.sub(r"^title\s*:\s*", "", title, flags=re.IGNORECASE)
        return title[:60] if title else fallback_title(question)
    except Exception:
        return fallback_title(question)
