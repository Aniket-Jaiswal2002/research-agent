from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from ingest import ingest_pdf, list_pdfs
from agent import chat
from tools import set_active_pdf

app = FastAPI(
    title="ResearchMind API",
    description="AI Research Agent — chat with your PDFs",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    answer: str
    success: bool

class UploadResponse(BaseModel):
    message: str
    chunks: int
    pdf_name: str
    success: bool

class SelectPDFRequest(BaseModel):
    pdf_name: str


@app.get("/")
def root():
    return {"status": "ResearchMind API v2 is running!"}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF file"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    upload_path = f"uploaded_{file.filename}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks, pdf_name = ingest_pdf(upload_path)
        os.remove(upload_path)

        # auto select the newly uploaded PDF
        set_active_pdf(pdf_name)

        return UploadResponse(
            message=f"Successfully ingested {file.filename}",
            chunks=chunks,
            pdf_name=pdf_name,
            success=True
        )
    except Exception as e:
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/select-pdf")
def select_pdf(request: SelectPDFRequest):
    """Switch the active PDF the agent searches"""
    pdf_path = f"vector_store/{request.pdf_name}"
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    set_active_pdf(request.pdf_name)
    return {"message": f"Now searching: {request.pdf_name}", "success": True}


@app.get("/pdfs")
def get_pdfs():
    """Get list of all uploaded PDFs"""
    pdfs = list_pdfs()
    return {"pdfs": pdfs, "count": len(pdfs)}


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question to the AI agent"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        answer = chat(request.question)
        return AnswerResponse(answer=answer, success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def status():
    """Check system status"""
    pdfs = list_pdfs()
    from tools import active_pdf
    return {
        "pdf_loaded": len(pdfs) > 0,
        "active_pdf": active_pdf["name"],
        "total_pdfs": len(pdfs),
        "pdfs": pdfs
    }
