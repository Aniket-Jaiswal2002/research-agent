# 🔬 ResearchMind — AI Research Agent

An intelligent research assistant that lets you chat with your PDF documents and search the web — powered by LLaMA 3.3 and LangChain.

![ResearchMind](https://img.shields.io/badge/AI-LLaMA%203.3-purple) ![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green) ![React](https://img.shields.io/badge/Frontend-React-blue) ![Docker](https://img.shields.io/badge/Deploy-Docker-blue)

## ✨ Features

- 📄 **PDF Chat** — Upload any PDF and ask questions about it
- 🌐 **Web Search** — Searches the internet for latest information
- 📌 **Cited Answers** — Every answer includes page numbers and URLs
- 📚 **Multiple PDFs** — Upload and switch between multiple documents
- ⚡ **Fast** — Powered by Groq's LPU inference engine
- 🐳 **Docker Ready** — One command to run everything

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | LLaMA 3.3 70B via Groq |
| Agent Framework | LangChain |
| Vector Search | FAISS |
| Embeddings | Sentence Transformers |
| Web Search | Tavily API |
| Backend | FastAPI |
| Frontend | React + Vite |
| Deployment | Docker + Render |

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key (free at console.groq.com)
- Tavily API key (free at app.tavily.com)

### Installation

1. **Clone the repo**
```bash
git clone https://github.com/Aniket-Jaiswal2002/research-agent.git
cd research-agent
```

2. **Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Add your API keys to .env
```

5. **Run with Docker**
```bash
docker-compose up
```

6. **Or run manually**

Terminal 1 — Backend:
```bash
uvicorn api:app --reload
```

Terminal 2 — Frontend:
```bash
cd frontend
npm install
npm run dev
```

## 📖 How It Works

User uploads PDF
↓
pymupdf reads pages → split into chunks
↓
sentence-transformers converts chunks to vectors
↓
FAISS stores vectors for fast search
↓
User asks question
↓
Agent decides: search PDF or web?
↓
FAISS finds relevant chunks / Tavily searches web
↓
LLaMA 3.3 generates cited answer
↓
React displays answer with clickable sources

## 🔑 Environment Variables

Create a `.env` file with:
```bash
GROQ_API_KEY=your_groq_key_here
TAVILY_API_KEY=your_tavily_key_here
```
## 📁 Project Structure

```bash
research-agent/
├── ingest.py          # PDF processing pipeline
├── tools.py           # Agent tools (PDF + web search)
├── agent.py           # AI agent brain
├── api.py             # FastAPI backend
├── Dockerfile         # Backend container
├── docker-compose.yml # Run everything together
├── requirements.txt   # Python dependencies
└── frontend/
├── src/
│   └── App.jsx    # React UI
└── Dockerfile     # Frontend container
```

## 👨‍💻 Author

**Aniket Jaiswal**
- GitHub: [@Aniket-Jaiswal2002](https://github.com/Aniket-Jaiswal2002)
- LinkedIn: [Aniket Jaiswal](https://www.linkedin.com/in/aniket-jaiswal-6748a5248/)

## 📄 License

MIT License
