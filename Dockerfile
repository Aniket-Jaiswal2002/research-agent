# ── Base image — Python 3.11 on Linux ────────────────────────────────
FROM python:3.11-slim

# Why slim? It's a minimal Python image — smaller size, faster builds
# Full Python image is 900MB, slim is 130MB

# ── Set working directory inside container ────────────────────────────
WORKDIR /app

# Why /app? It's the standard convention for app code in containers

# ── Install system dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Why build-essential? Some Python packages (like faiss) need C++ compiler

# ── Copy requirements first (Docker cache optimization) ───────────────
COPY requirements.txt .

# ── Install Python packages ───────────────────────────────────────────
RUN pip install --no-cache-dir -r requirements.txt

# Why --no-cache-dir? Saves space inside the container

# ── Copy the rest of the code ─────────────────────────────────────────
COPY . .

# ── Expose port 8000 ──────────────────────────────────────────────────
EXPOSE 8000

# ── Start the FastAPI server ──────────────────────────────────────────
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

# Why 0.0.0.0? Inside a container, localhost only refers to the container itself
# 0.0.0.0 means "accept connections from anywhere" — needed for Docker
