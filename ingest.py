import fitz
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle
import os
import re

model = SentenceTransformer("all-MiniLM-L6-v2")

def clean_name(filename: str) -> str:
    """Convert filename to a clean folder name"""
    name = os.path.splitext(filename)[0]  # remove .pdf
    name = re.sub(r'[^a-zA-Z0-9-_]', '-', name)  # replace special chars
    return name.lower()

def ingest_pdf(pdf_path: str):
    print(f"Reading PDF: {pdf_path}")

    doc = fitz.open(pdf_path)
    chunks = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue
        words = text.split()
        chunk_size = 150
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append({
                "text": chunk,
                "page": page_num + 1,
                "source": os.path.basename(pdf_path)
            })

    print(f"Created {len(chunks)} chunks from {len(doc)} pages")

    print("Converting chunks to vectors...")
    texts = [chunk["text"] for chunk in chunks]
    vectors = model.encode(texts, show_progress_bar=True)

    dimension = vectors.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(vectors))

    # ── Save to its own folder ────────────────────────────────────────
    pdf_name = clean_name(os.path.basename(pdf_path))
    save_dir = f"vector_store/{pdf_name}"
    os.makedirs(save_dir, exist_ok=True)

    faiss.write_index(index, f"{save_dir}/index.faiss")
    with open(f"{save_dir}/chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    print(f"Done! Saved {len(chunks)} chunks to {save_dir}/")
    return len(chunks), pdf_name


def list_pdfs() -> list:
    """Returns list of all ingested PDFs"""
    if not os.path.exists("vector_store"):
        return []
    pdfs = []
    for folder in os.listdir("vector_store"):
        folder_path = f"vector_store/{folder}"
        if os.path.isdir(folder_path) and os.path.exists(f"{folder_path}/index.faiss"):
            pdfs.append(folder)
    return pdfs


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ingest.py yourfile.pdf")
    else:
        ingest_pdf(sys.argv[1])