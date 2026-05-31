import fitz  # this is pymupdf — reads PDF files
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle
import os

# ── Load the embedding model ──────────────────────────────────────────
# This model converts text into vectors (numbers)
# "all-MiniLM-L6-v2" is small, fast, and works great for search
model = SentenceTransformer("all-MiniLM-L6-v2")

def ingest_pdf(pdf_path: str):
    """
    Reads a PDF, splits it into chunks,
    converts chunks to vectors, stores in FAISS
    """

    print(f"Reading PDF: {pdf_path}")

    # ── Step 1: Read the PDF ──────────────────────────────────────────
    doc = fitz.open(pdf_path)
    chunks = []  # will store (text, page_number) pairs

    for page_num, page in enumerate(doc):
        text = page.get_text()  # extract raw text from page

        # skip empty pages
        if not text.strip():
            continue

        # split page into chunks of ~500 characters
        # why? because LLMs work better with smaller focused chunks
        words = text.split()
        chunk_size = 150  # roughly 150 words per chunk
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append({
                "text": chunk,
                "page": page_num + 1,  # page numbers start at 1
                "source": os.path.basename(pdf_path)
            })

    print(f"Created {len(chunks)} chunks from {len(doc)} pages")

    # ── Step 2: Convert chunks to vectors ────────────────────────────
    # This is called "embedding" — turning text into numbers
    # so FAISS can compare and search them mathematically
    print("Converting chunks to vectors...")
    texts = [chunk["text"] for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=True)

    # ── Step 3: Store vectors in FAISS ───────────────────────────────
    # FAISS needs to know the size of each vector
    dimension = vectors.shape[1]  # typically 384 for this model
    index = faiss.IndexFlatL2(dimension)  # L2 = euclidean distance search
    index.add(np.array(vectors))  # add all vectors to the index

    # ── Step 4: Save everything to disk ──────────────────────────────
    # We save both the FAISS index and the original chunks
    # because FAISS only stores vectors, not the original text
    os.makedirs("vector_store", exist_ok=True)
    faiss.write_index(index, "vector_store/index.faiss")

    with open("vector_store/chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    print(f"Done! Saved {len(chunks)} chunks to vector_store/")
    return len(chunks)


# ── Run this file directly to test it ────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ingest.py yourfile.pdf")
    else:
        ingest_pdf(sys.argv[1])
        