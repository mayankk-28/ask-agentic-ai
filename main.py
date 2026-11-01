import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent import LLMUnavailable, run_agent

app = FastAPI(title="ASK Agentic AI")

HERE = Path(__file__).parent


# ----------------------------------------------------------- simple rate limit
# Protects your free API quota from spam. In-memory, per IP (fine for one free instance).
RATE_LIMIT = 20          # requests
RATE_WINDOW = 60         # per this many seconds
_hits = defaultdict(deque)


def check_rate_limit(request: Request):
    forwarded = request.headers.get("x-forwarded-for")  # Render sits behind a proxy
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute and try again.")
    q.append(now)


# --------------------------------------------------------------------- models
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[Msg] = Field(min_length=1, max_length=40)
    memory: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------- routes
@app.get("/")
@app.get("/chat")
def page():
    return FileResponse(HERE / "chat.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(body: ChatRequest, request: Request):
    check_rate_limit(request)
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Last message must be from the user.")

    history = [m.model_dump() for m in body.messages]
    memory = {str(k)[:40]: str(v)[:200] for k, v in list(body.memory.items())[:30]}

    try:
        return run_agent(history, memory)
    except LLMUnavailable as e:
        print("All LLM providers failed:", e)
        raise HTTPException(
            status_code=503,
            detail="The AI service is busy right now (free-tier limit). Please try again in a minute.",
        )


# Old URL kept so any existing links keep working
@app.get("/ask")
def ask(question: str, request: Request):
    check_rate_limit(request)
    try:
        out = run_agent([{"role": "user", "content": question[:4000]}], {})
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="The AI service is busy right now. Please try again.")
    return {"question": question, "result": {"message": out["reply"]}}
