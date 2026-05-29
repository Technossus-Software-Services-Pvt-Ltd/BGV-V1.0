# BGV-V1 — AI-Powered Background Verification Platform (Phase 1)

Production-grade scaffold for an enterprise Background Verification (BGV) platform
focused on **OCR stability, AI-based document classification, candidate ownership
validation, and full auditability**.

> Phase 1 deliberately stops at: Upload → Normalize → OCR → AI Classify → Validate
> → Audit. The architecture is engineered to extend into Gmail/Drive ingestion,
> human-in-the-loop review, vendor routing, SLA tracking, and RBAC without
> structural change.

---

## Architectural Non-Negotiables

| # | Rule |
|---|------|
| 1 | No raw document binary is ever sent to AI. Flow is **Document → OCR → OCR Text → AI**. |
| 2 | Filename is **never** used as a classification signal. |
| 3 | AI classification is **mandatory** (lightweight local LLM via Ollama). Regex alone is insufficient. |
| 4 | Runs on **8 GB RAM, i3/i5 CPU, no GPU**. CPU-only optimization is mandatory. |
| 5 | Every stage produces an **audit event** with `correlation_id`. |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PHASE_PLAN.md](docs/PHASE_PLAN.md),
and [docs/API.md](docs/API.md).

---

## Tech Stack

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL-ready
(SQLite default for local dev), PaddleOCR, Ollama (Phi/TinyLlama/Gemma).

**Frontend** — React 18, TypeScript, Vite, TailwindCSS, SSE for live pipeline.

**Infra** — Docker Compose (api, web, db, ollama).

---

## Quick Start (Local Dev — no Docker)

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

> PaddleOCR and Ollama are **optional at boot**. The pipeline detects missing
> engines and falls back to a deterministic stub so the UI flow is testable
> immediately. Install them when you are ready:
> ```
> pip install paddleocr paddlepaddle
> # and run an Ollama model:
> ollama pull phi3:mini
> ```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

### Docker (everything)
```powershell
docker compose up --build
```

---

## Repo Layout

```
backend/        FastAPI service (OCR + AI + validation + audit)
frontend/       React + TS + Tailwind UI (upload + live pipeline)
docs/           Architecture, phase plan, API contracts
docker-compose.yml
```
