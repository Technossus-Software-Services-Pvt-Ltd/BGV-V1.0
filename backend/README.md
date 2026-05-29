# BGV Platform - Backend

Production-grade AI-powered Background Verification OCR + Classification platform.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Database

```bash
alembic upgrade head
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Prerequisites

- Python 3.11
- PostgreSQL 15+
- Ollama with phi3:mini model pulled
- PaddleOCR dependencies
