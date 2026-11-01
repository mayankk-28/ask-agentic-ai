# ASK — Agentic AI Assistant 🤖

> **Ask anything. The agent decides when it needs a tool.**

ASK is a conversational AI assistant built with Python and FastAPI. A language model reads your message, decides on its own whether a tool is needed (calculator, weather, date/time, memory), runs it, and writes the final answer in natural language. It remembers the conversation, replies in the language you write in (English, Hindi or Hinglish), and automatically switches to a backup model if the main one is unavailable.

The entire stack runs on **free tiers**: no paid API or hosting is needed.

- **Live app:** https://agentic-ai-learning.onrender.com
- **API docs (Swagger):** https://agentic-ai-learning.onrender.com/docs
- **Source code:** https://github.com/mayankk-28/agentic-ai-learning

> The app is hosted on Render's free plan. It goes to sleep after ~15 minutes without traffic, so the **first request can take up to a minute** while it wakes up.

---

## Table of contents

1. [Features](#-features)
2. [How it works](#-how-it-works)
3. [Tech stack](#-tech-stack)
4. [Project structure](#-project-structure)
5. [Tools the agent can use](#-tools-the-agent-can-use)
6. [Reliability: provider fallback](#-reliability-provider-fallback)
7. [Memory and chat history](#-memory-and-chat-history)
8. [API reference](#-api-reference)
9. [Run locally](#-run-locally)
10. [Environment variables](#-environment-variables)
11. [Deploy on Render](#-deploy-on-render)
12. [Limitations](#-limitations)
13. [Roadmap](#-roadmap)
14. [What I learned](#-what-i-learned)
15. [About](#-about)

---

## ✨ Features

- **Real LLM tool-calling.** The model chooses tools itself; there is no keyword router or fixed intent list.
- **Open-ended chat.** Most questions need no tool, and the model simply answers them.
- **Follow-up questions work.** The recent conversation is sent with every request, so "explain more" or "give an example" has context.
- **Five built-in tools:** calculator, weather for any city, current date and time, a demo user lookup, and memory.
- **Safe calculator.** Expressions are parsed with Python's `ast` module. `eval()` is never used.
- **Automatic fallback.** If Gemini is overloaded or rate-limited, the request moves to Groq.
- **Multilingual.** The assistant answers in the language the user writes in.
- **Browser chat UI.** Saved chat history, history search, light/dark theme, and a Fun Zone with jokes and a trivia quiz.
- **Basic abuse protection.** Per-IP rate limiting protects the free API quota.

---

## 🏗️ How it works

```text
Browser (chat.html)
   |
   |  POST /chat   { messages: [...recent chat...], memory: {...} }
   v
FastAPI (main.py)
   |  validate input, rate-limit by IP
   v
Agent loop (agent.py)
   |
   |  1. Build system prompt (+ remembered facts)
   |  2. Ask the LLM  (Gemini first, Groq as fallback)
   |  3. Did the model request a tool?
   |        yes -> run it (tools.py), send the result back, go to step 2
   |        no  -> this is the final answer
   |  (max 5 tool rounds per message)
   v
{ reply, memory_updates, provider }
   |
   v
Browser shows the reply and stores any new memory
```

### Example: "What is 15% of 2400, and what's the weather in Bhopal?"

1. The model requests `calculator("15/100*2400")` and `get_weather("Bhopal")`.
2. The server runs both tools and returns the results to the model.
3. The model writes one natural answer using both results.

For a question like "What is Python?", no tool is called and the model answers directly.

---

## 🧰 Tech stack

| Technology | Role |
|---|---|
| Python 3 | Backend and tools |
| FastAPI | HTTP API |
| Pydantic | Request validation |
| Uvicorn | ASGI server |
| OpenAI Python SDK | Client for Gemini and Groq (both expose OpenAI-compatible APIs) |
| Google Gemini API | Primary LLM |
| Groq API | Fallback LLM |
| Open-Meteo | Weather and geocoding (free, no API key) |
| JSONPlaceholder | Demo user data |
| HTML, CSS, JavaScript | Chat interface (no framework) |
| `localStorage` | Chat history and memory, stored in the browser |
| Render | Free hosting |

---

## 📁 Project structure

```text
agentic-ai-learning/
├── main.py            # FastAPI app: routes, validation, rate limiting
├── agent.py           # Agent loop, system prompt, provider fallback
├── tools.py           # Tool functions and their JSON schemas
├── chat.html          # Browser chat UI (HTML + CSS + JS)
├── requirements.txt   # Python dependencies
└── .gitignore
```

- **`main.py`** exposes the endpoints, validates requests and applies the rate limit.
- **`agent.py`** contains the tool-calling loop and decides which model to call.
- **`tools.py`** contains every tool and a dispatcher that never crashes the chat if a tool fails.

---

## 🛠️ Tools the agent can use

| Tool | What it does |
|---|---|
| `calculator` | Evaluates arithmetic safely (`+ - * / ** % //`, parentheses). Rejects anything else, including attempts to run code. |
| `get_weather` | Current temperature, humidity, wind and conditions for any city, via Open-Meteo geocoding and forecast. |
| `get_current_datetime` | Today's date and time in a given timezone (default `Asia/Kolkata`). |
| `get_sample_user` | Fetches a demo user profile (IDs 1–10) from JSONPlaceholder. |
| `save_memory` | Stores a lasting fact the user shares (name, city, preferences). |

Each tool returns a small JSON result or an `{"error": ...}` object. The model reads that result and explains it in plain sentences.

---

## 🛡️ Reliability: provider fallback

Free LLM tiers have rate limits and occasional overload, so ASK is built to survive that:

1. **Gemini** is tried first.
2. On any failure (rate limit, `503`, timeout), the request automatically goes to **Groq**.
3. Within one request, the agent **stays with the provider that started it**, because the two providers format tool calls slightly differently.
4. Each call has a 20-second timeout, so a slow provider cannot freeze the chat.
5. If every provider fails, the user gets a clear "service is busy" message with HTTP `503`.

---

## 💾 Memory and chat history

Render's free filesystem is wiped on every restart, so the server is deliberately **stateless**.

- **Chat history** is saved in the browser (`localStorage`) and the recent messages are sent with each request.
- **Memory** (for example your name) is also saved in the browser. The server receives it with each request, places it in the system prompt, and returns any updates for the browser to store.

This works with no database and no cost. The trade-off is that memory is per browser and per device.

---

## 🔌 API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` and `/chat` | Serves the chat UI |
| `POST` | `/chat` | Main agent endpoint |
| `GET` | `/ask?question=...` | Single-question endpoint (kept for older links) |
| `GET` | `/health` | Health check, returns `{"status": "ok"}` |
| `GET` | `/docs` | Interactive Swagger documentation |

### `POST /chat`

Request:

```json
{
  "messages": [
    { "role": "user", "content": "What is 12 times (3+4)?" }
  ],
  "memory": { "name": "Mayank" }
}
```

Response:

```json
{
  "reply": "12 times (3 + 4) is 84.",
  "memory_updates": {},
  "provider": "gemini"
}
```

Limits: up to 40 messages per request, 4,000 characters per message, 30 memory entries. The last message must come from the user. Exceeding the rate limit returns `429`; all providers failing returns `503`.

---

## 🚀 Run locally

**1. Clone and enter the project**

```bash
git clone https://github.com/mayankk-28/agentic-ai-learning.git
cd agentic-ai-learning
```

**2. Create and activate a virtual environment**

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**

```bash
python -m pip install -r requirements.txt
```

**4. Create a `.env` file** in the project root (see the next section for the values).

**5. Start the server**

```bash
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. After changing `.env`, stop the server (`Ctrl+C`) and start it again, because environment variables are read only at startup.

---

## 🔐 Environment variables

Create a `.env` file (never commit it):

```env
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.1-flash-lite

GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-120b
```

| Variable | Purpose | Required |
|---|---|---|
| `GEMINI_API_KEY` | Key for the primary model (free from Google AI Studio) | Recommended |
| `GEMINI_MODEL` | Gemini model name | Optional (has a default) |
| `GROQ_API_KEY` | Key for the fallback model (free from the Groq console) | Recommended |
| `GROQ_MODEL` | Groq model name | Optional (has a default) |

At least one key is required. With both, you get automatic fallback. Free-tier model names change over time, so if a model returns `404` or `429`, list the models available to your key and update `GEMINI_MODEL`.

---

## ☁️ Deploy on Render

1. Push the repository to GitHub.
2. In Render, create a **Web Service** from the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add the four environment variables above in the **Environment** tab.
6. Deploy. Later pushes to the main branch redeploy automatically.

---

## ⚠️ Limitations

- **Free-tier constraints.** Model quotas and availability depend on the providers' free plans.
- **Cold starts.** Render's free service sleeps when idle, so the first request after a pause is slow.
- **No live internet access.** The assistant cannot browse the web, so it says so when asked about very recent events.
- **Memory is per browser.** It is not shared across devices.
- **Plain-text replies.** Markdown and code blocks are not rendered yet.
- **Rate limiter is in-memory.** It resets on restart and is suited to a single free instance.
- **No authentication.** The public demo is open, protected only by the per-IP limit.

---

## 🛣️ Roadmap

- [ ] Streaming responses (token-by-token output)
- [ ] Markdown and code-block rendering in the chat UI
- [ ] Web search tool for current information
- [ ] Persistent per-user memory in a free database
- [ ] Automated tests with a mocked LLM
- [ ] Authentication and per-user quotas

---

## 📚 What I learned

- How an LLM **tool-calling loop** really works: the model requests a tool, the server runs it and returns the result, and the loop repeats until a final answer
- Designing safe tools (an AST-based calculator instead of `eval`)
- Making free-tier LLM APIs dependable with **fallbacks, timeouts and per-request provider consistency**
- Building a **stateless backend** and keeping state in the client
- Input validation and rate limiting with FastAPI and Pydantic
- Debugging real API failures: `404` for retired models, `429` quota limits, `503` overload and timeouts
- Deploying and configuring a service on Render

---

## 👨‍💻 About

I'm **Mayank Chouhan**, a B.Tech Computer Science Engineering student building toward a career as an AI engineer. I learn by building, testing and debugging real applications, and ASK is where I explore how AI agents work from the inside.

- GitHub: [mayankk-28](https://github.com/mayankk-28)
- LinkedIn: [Mayank Chouhan](https://www.linkedin.com/in/mayank-chouhan-2b318b365)

---

**ASK — Ask anything. The agent decides when it needs a tool. 🤖**
