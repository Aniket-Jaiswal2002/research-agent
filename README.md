# 🔬 ResearchMind — AI Research Agent

> A RAG research agent that chats with your PDFs and searches the web — LangChain tool-calling, FAISS vector search, FastAPI and React, running open models on Groq. It ships with an eval suite that measures how reliable the agent actually is.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![LangChain](https://img.shields.io/badge/LangChain-Agent-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 📊 Evaluation

ResearchMind ships with a 31-task eval suite ([`evals/`](evals/README.md)) built on a **fictional** PDF. The model can't answer from memory, so every correct answer has to come from retrieval. It checks tool selection, retrieval hit rate, page citations, fact accuracy, hallucination on unanswerable questions, tool-call loops and prompt injection.

The default agent is **v3** (`RM_AGENT_VERSION`): v1 is the original loop, v2 adds loop and prompt guardrails, v3 adds guardrails enforced in code. See [`evals/README.md`](evals/README.md).

<!-- Numbers come from evals/RESULTS.md (python evals/report.py evals/runs/*/summary.json) -->
| Metric | gpt-oss-20b · v1 | gpt-oss-20b · v2 | gpt-oss-120b · v2 | gpt-oss-20b · v3 |
|---|---|---|---|---|
| **Pass rate (deterministic)** | **77%** (24/31) | **76%** (22/29) | **87%** (27/31) | **90%** (28/31) |
| Pass rate excl. the 3 citation checks | 81% | 86% | 94% | 90% |
| Pass rate incl. LLM judge | – | 69% | 81% | 87% |
| Groundedness (judge: qwen3.8-27b) | – | 88% | 93% | 96% |
| Retrieval hit | 100% | 89% | 100% | 100% |
| Correct page cited † | 100% | 84% | 95% | 100% |
| Abstains when unanswerable | 0% | 67% | 100% | 67% |
| Resists prompt injection | 100% | – | 100% | 100% |
| Latency p50 / p95 | 14.2s / 51.8s | 12.9s / 78.1s | 2.5s / 103.1s | 11.4s / 62.6s |

31 tasks, one run per column; each task ≈ 3 points, so differences under ~10 points are within run-to-run variance. "–": not measured (v2's two injection tasks hit Groq's daily token limit and are excluded, as all API outages are; the 120b run had one model error, `web-04`, which counts as a failure). All models are on Groq; the judge is a different model from the one under test. † **v3 appends citations in code**, so `cites_source`, `web_cited` and `correct_page_cited` are not evidence of better answers; compare v3 on the "excl. citation checks" row. Details: [`evals/RESULTS.md`](evals/RESULTS.md), [`evals/SCORER_CHANGELOG.md`](evals/SCORER_CHANGELOG.md).

**What the evals found:**
- **v1 returned empty answers** when it used up its 6 tool rounds (abstention 0%, completion 90%). v2 fixes that: abstention 67% and no empty answers (completion 100%). It does not stop loops: `loop-01` ("tell me everything") still blows the tool-call budget in every run.
- **v1 and v2 are not distinguishable overall** (77% vs 76%): v2 won two unanswerable-question tasks and lost two on tool choice and citation format, which looks like run-to-run variance. Repeating each run a few times would settle it.
- **The first scorer was too strict.** It rejected correct answers written with a non-breaking hyphen (`LPSC‑9`), `kg⁻¹` instead of `kg/`, or "Page 3 & 6". Fixing that moved v1 from 61% to 77%; the before/after for every run is in the changelog.
- **The remaining misses are behavioural, not retrieval:** retrieval hit is 89–100%. The common failures are calling the web tool before the PDF, dropping URLs from web citations, and looping on "tell me everything".
- **The bigger model scores higher** (87%) and abstains correctly every time, but produced one malformed tool call that Groq rejected (`output_parse_failed`).
- **v3 (guardrails in code) scored 90% (28/31) vs v2's 76% (22/29), but most of that gap is the citation code, not better answers.** Without the three citation checks v3 is 90% and v2 86%: about one task, inside the noise band. v3 appended a `Sources:` block on 9 tasks, and that block alone decided pass/fail on two of them (`mixed-02`, `mixed-03`); three of the nine were on unanswerable questions, where listing sources next to "not found" is noise (v3 now skips abstentions; this run predates that change and has not been re-run). These are single runs.
- **Forcing PDF-first with `tool_choice` works, but not always.** It was used on all 31 tasks, yet Groq returned a 400 on the forced first call for 3 of them (10%). One recovered on retry; two fell back to the unforced runner, and one of those (`pdf-09`) then called the web first. So `first_tool` is 97% for v3, the same as v1.
- **What v3 did not move:** abstention is still 67% (`abstain-01` still fails), and `loop-01` still fails (`no_duplicate_calls`). Facts and retrieval hit went from 89% to 100% versus v2 (two tasks); v3's code doesn't control either, so I'd treat that as variance until the runs are repeated.

---

> **Live demo paused** (hosting trial ended). Run it locally in 2 minutes with Docker, see [Quick Start](#-quick-start). Demo GIFs below show it working.

## 📸 Demo

### Local — Full PDF + Web Search
![Local Demo](assets/demo-local.gif)

### Web Search with Citations
![Web search demo](assets/demo-live.gif)

*Recorded with an earlier version (Llama 3.1 on Groq). Current default model: openai/gpt-oss-20b.*

---

## ✨ Features

- 📄 **PDF Chat** — Upload any PDF and ask questions with page citations
- 🌐 **Web Search** — Real-time web search with clickable sources
- 📌 **Cited Answers** — Every answer includes page numbers and URLs
- 📚 **Multiple PDFs** — Upload and switch between multiple documents
- ⚡ **Fast** — Powered by Groq's LPU inference engine
- 🐳 **Docker Ready** — One command to run everything

---

## 🧠 How the Agent Works

```
User asks: "What is electrochemistry and latest battery tech?"
↓
LLM decides which tools to use
↓
┌───────────────────────────────┐
│                               │
pdf_search_tool              web_search_tool
(FAISS vector search)        (Tavily API)
→ Page 67, NCERT Chemistry   → Forbes, Nature 2025
│                               │
└───────────────┬───────────────┘
↓
LLM combines results + adds citations
↓
"Electrochemistry is... (Source: NCERT, Page 67)
Latest developments... (Forbes)"
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **LLM** | `openai/gpt-oss-20b` via Groq (set `RM_MODEL` to change) | Fast, free tier, supports tool calling |
| **Agent** | LangChain tool-calling | Decides PDF vs web automatically |
| **Embeddings** | FastEmbed (BAAI/bge-small) | Lightweight, no GPU needed |
| **Vector DB** | FAISS | Fast local semantic search |
| **Web Search** | Tavily API | Purpose-built for AI agents |
| **Backend** | FastAPI + Uvicorn | Fast async Python API |
| **Frontend** | React + Vite | Modern, fast UI |
| **Container** | Docker + Docker Compose | One-command local deployment |

---

## 🚀 Quick Start

### Option 1 — Docker (Recommended)

```bash
git clone https://github.com/Aniket-Jaiswal2002/research-agent.git
cd research-agent
cp .env.example .env          # macOS / Linux
# copy .env.example .env      # Windows (cmd or PowerShell) — use this line instead
# Add your GROQ_API_KEY and TAVILY_API_KEY to .env
docker compose up --build
```

Open **http://localhost:5173** 🎉 (the API runs on http://localhost:8000)

If the page says *Backend offline*, the backend container isn't reachable on port 8000 (still starting, or it stopped): check `docker compose ps` and `docker compose logs backend`.

### Option 2 — Manual

Create `.env` first (see above).

**Backend:**
```bash
python -m venv venv
venv\Scripts\activate          # Windows. macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

---

## 🔑 Environment Variables

```env
GROQ_API_KEY=your_groq_key_here      # Free at console.groq.com
TAVILY_API_KEY=your_tavily_key_here  # Free at app.tavily.com

# optional
RM_MODEL=openai/gpt-oss-20b          # any Groq model that supports tool calling
RM_AGENT_VERSION=v3                  # v1 original loop | v2 | v3 (default)
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/upload` | Upload and ingest a PDF |
| `POST` | `/ask` | Ask the AI agent |
| `POST` | `/select-pdf` | Switch active PDF |
| `GET` | `/pdfs` | List all PDFs |
| `GET` | `/status` | System status |

---

## 📁 Project Structure

```
research-agent/
├── ingest.py          # PDF → chunks → vectors → FAISS
├── tools.py           # pdf_search_tool + web_search_tool
├── agent.py           # agent loop (v1/v2/v3) with a traced run_agent()
├── abstain.py         # "could not find it" detector shared by the agent and the scorer
├── api.py             # FastAPI REST endpoints
├── mcp_server.py      # the same tools over MCP
├── evals/             # 31-task eval suite, scorers, results
├── Dockerfile         # Backend container
├── docker-compose.yml # Full stack orchestration
├── requirements.txt   # Python dependencies
├── assets/            # Demo GIFs
└── frontend/
    ├── src/App.jsx    # React chat UI
    └── Dockerfile     # Nginx container
```

---

## 🔌 MCP Server

The same retrieval tools are exposed over the Model Context Protocol, so Claude Desktop, Cursor or any MCP client can search your PDFs:

```bash
python mcp_server.py
```

```json
{"mcpServers": {"researchmind": {"command": "python", "args": ["/path/to/research-agent/mcp_server.py"]}}}
```

Tools: `list_documents`, `search_pdf(query, document?)`, `web_search(query)`.

---

## 🗺️ Roadmap

- [x] PDF ingestion with FAISS
- [x] LangChain agent with tool calling
- [x] Web search with Tavily
- [x] FastAPI REST backend
- [x] React chat UI with citations
- [x] Multiple PDF support
- [x] Docker deployment
- [ ] Live deployment (paused: hosting trial ended)
- [x] Eval suite with retrieval / citation / injection checks
- [x] MCP server
- [ ] Tracing dashboard (Langfuse / Phoenix)
- [ ] Context compaction for long sessions
- [ ] User authentication
- [ ] Persistent PDF library per user
- [ ] Streaming responses
- [ ] Mobile app

---

## 👨‍💻 Author

**Aniket Jaiswal** — AI Engineer

- 🐙 GitHub: [@Aniket-Jaiswal2002](https://github.com/Aniket-Jaiswal2002)
- 💼 LinkedIn: [Aniket Jaiswal](https://www.linkedin.com/in/aniket-jaiswal-6748a5248/)
- 📧 Open to international AI engineer opportunities

---

## 📄 License

MIT License — feel free to use as a template!
