import faiss
import pickle
import numpy as np
from fastembed import TextEmbedding
from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

model = TextEmbedding("BAAI/bge-small-en-v1.5")

# ── Active PDF tracker ────────────────────────────────────────────────
# This keeps track of which PDF is currently selected
active_pdf = {"name": None}

def set_active_pdf(pdf_name: str):
    """Set which PDF the agent should search"""
    active_pdf["name"] = pdf_name

def load_vector_store(pdf_name: str = None):
    """Load FAISS index for a specific PDF or the active one"""
    name = pdf_name or active_pdf["name"]
    
    if not name:
        # fallback — try old single vector store
        if os.path.exists("vector_store/index.faiss"):
            import faiss as f
            index = f.read_index("vector_store/index.faiss")
            with open("vector_store/chunks.pkl", "rb") as f:
                chunks = pickle.load(f)
            return index, chunks
        raise FileNotFoundError("No PDF loaded")
    
    path = f"vector_store/{name}"
    index = faiss.read_index(f"{path}/index.faiss")
    with open(f"{path}/chunks.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks

import os

@tool
def pdf_search_tool(query: str) -> str:
    """
    Searches the uploaded PDF document for relevant information.
    Use this tool when the question is about the document content.
    Returns relevant text chunks with page numbers.
    """
    try:
        index, chunks = load_vector_store()

        query_vector = list(model.embed([query]))
        query_vector = np.array(query_vector, dtype=np.float32)

        distances, indices = index.search(query_vector, k=4)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            chunk = chunks[idx]
            result = (
                f"[Source: {chunk['source']}, Page {chunk['page']}]\n"
                f"{chunk['text']}"
            )
            results.append(result)

        if not results:
            return "No relevant information found in the PDF."

        return "\n\n---\n\n".join(results)

    except FileNotFoundError:
        return "No PDF has been loaded. Please upload a PDF first."


web_search_tool = TavilySearchResults(
    max_results=3,
    include_answer=True,
    include_raw_content=False,
    name="web_search_tool",
    description=(
        "Searches the internet for current information. "
        "Use this when the question needs up-to-date info "
        "or is not covered in the PDF document."
    )
)

tools = [pdf_search_tool, web_search_tool]