# SOTA 2026 EduVerse Backend Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable real-time logging
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

WORKDIR /app

# Install system dependencies for PDF parsing and local inference
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies using requirements.txt
COPY requirements.txt .
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
COPY . .

# Create directory for local document storage
RUN mkdir -p data/uploads

# Expose FastAPI port
EXPOSE 8000

# Start the application using uvicorn with dynamic port binding for Render
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
