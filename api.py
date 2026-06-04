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
    allow_origins=[
        "https://researchmind-sigma.vercel.app",
        "http://localhost:5173",
        "*"
    ],
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


@app.on_event("startup")
async def startup_event():
    pdfs = list_pdfs()
    if pdfs:
        set_active_pdf(pdfs[0])
        print(f"Auto-loaded PDF: {pdfs[0]}")


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    upload_path = f"uploaded_{file.filename}"
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks, pdf_name = ingest_pdf(upload_path)
        os.remove(upload_path)
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
    pdf_path = f"vector_store/{request.pdf_name}"
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    set_active_pdf(request.pdf_name)
    return {"message": f"Now searching: {request.pdf_name}", "success": True}


@app.get("/pdfs")
def get_pdfs():
    pdfs = list_pdfs()
    return {"pdfs": pdfs, "count": len(pdfs)}


@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        answer = chat(request.question)
        return AnswerResponse(answer=answer, success=True)
    except Exception as e:
        print(f"ERROR in ask_question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def status():
    pdfs = list_pdfs()
    from tools import active_pdf
    return {
        "pdf_loaded": len(pdfs) > 0,
        "active_pdf": active_pdf["name"],
        "total_pdfs": len(pdfs),
        "pdfs": pdfs
    }
