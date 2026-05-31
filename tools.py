import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

# ── Load embedding model and vector store ─────────────────────────────
# Same model we used in ingest.py — must match!
model = SentenceTransformer("all-MiniLM-L6-v2")

def load_vector_store():
    """Loads FAISS index and chunks from disk"""
    index = faiss.read_index("vector_store/index.faiss")
    with open("vector_store/chunks.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks

# ── Tool 1: PDF Search ────────────────────────────────────────────────
@tool
def pdf_search_tool(query: str) -> str:
    """
    Searches the uploaded PDF document for relevant information.
    Use this tool when the question is about the document content.
    Returns relevant text chunks with page numbers.
    """
    try:
        index, chunks = load_vector_store()

        # convert question to vector — same way we converted chunks
        query_vector = model.encode([query])
        query_vector = np.array(query_vector, dtype=np.float32)

        # search FAISS for top 4 most similar chunks
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
        return "No PDF has been ingested yet. Please run ingest.py first."


# ── Tool 2: Web Search ────────────────────────────────────────────────
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

# ── Export tools as a list ────────────────────────────────────────────
tools = [pdf_search_tool, web_search_tool]