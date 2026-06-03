# BGV Platform - Backend

Production-grade AI-powered Background Verification OCR + Classification platform.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Linux/Mac
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

## Tests

```bash
# Run all tests (excluding e2e)
python -m pytest tests/ --ignore=tests/test_e2e.py -v

# Run specific phase tests
python -m pytest tests/test_task_manager.py -v
python -m pytest tests/test_integration.py -v

# Quick summary
python -m pytest tests/ --ignore=tests/test_e2e.py -q
```

**162 tests** covering: DI, pipeline stages, batch services, error handling, task management, configuration, integration flows, endpoint CRUD, and health.

## Prerequisites

- Python 3.10+
- PostgreSQL 15+
- Ollama with `llama3.1:latest` model pulled
- PaddleOCR dependencies (auto-installed via requirements.txt)

## Configuration

All settings are env-overridable via `.env` file or environment variables. See `app/core/config.py` for the full list, or `ARCHITECTURE_ANALYSIS.md` § Configuration Reference.

Key settings:
- `DATABASE_URL` — PostgreSQL connection (auto-set in development)
- `OLLAMA_BASE_URL` — Ollama server (default: `http://localhost:11434`)
- `SECRET_KEY` — Session signing (auto-generated in development)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth2 (required in production)

## Architecture

See [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md) for the full architecture diagram, design decisions, and configuration reference.
