from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from ingest import ingest_pdf
from agent import chat

# ── Create FastAPI app ────────────────────────────────────────────────
app = FastAPI(
    title="ResearchMind API",
    description="AI Research Agent — chat with your PDFs",
    version="1.0.0"
)

# ── CORS — allows React frontend to talk to this API ─────────────────
# Without this, browser will block requests from frontend to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # in production, replace with your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response models ───────────────────────────────────────────
# Pydantic models define what data the API accepts and returns
# FastAPI automatically validates and documents them
class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str
    success: bool

class UploadResponse(BaseModel):
    message: str
    chunks: int
    success: bool

# ── Routes ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — confirms API is running"""
    return {"status": "ResearchMind API is running!"}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file and ingest it into the vector store.
    The agent can then answer questions about this PDF.
    """
    # validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    # save uploaded file temporarily
    upload_path = f"uploaded_{file.filename}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # ingest the PDF into vector store
        chunks = ingest_pdf(upload_path)

        # clean up temp file
        os.remove(upload_path)

        return UploadResponse(
            message=f"Successfully ingested {file.filename}",
            chunks=chunks,
            success=True
        )
    except Exception as e:
        # clean up on error
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Ask a question to the AI agent.
    It will search the PDF and/or web and return an answer with citations.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    try:
        answer = chat(request.question)
        return AnswerResponse(answer=answer, success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status():
    """Check if a PDF has been ingested"""
    has_pdf = os.path.exists("vector_store/index.faiss")
    return {
        "pdf_loaded": has_pdf,
        "message": "PDF is loaded and ready" if has_pdf else "No PDF loaded yet"
    }
