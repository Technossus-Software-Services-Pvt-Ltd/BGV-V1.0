# BGV Platform v1.0 — Docker Desktop Deployment Guide

## Complete Step-by-Step Guide for Building & Deploying via Docker Desktop

This guide covers the entire process from building Docker images on a developer machine to deploying on a client's target machine using Docker Desktop — **without exposing the underlying source code**.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Developer Machine: Build & Package](#3-developer-machine-build--package)
4. [Create Deployment Package Files](#4-create-deployment-package-files)
5. [Build Docker Images](#5-build-docker-images)
6. [Export Docker Images](#6-export-docker-images)
7. [Target Machine: Setup & Deploy](#7-target-machine-setup--deploy)
8. [Configuration](#8-configuration)
9. [Start the Application](#9-start-the-application)
10. [Management Scripts](#10-management-scripts)
11. [Health Check & Verification](#11-health-check--verification)
12. [Troubleshooting](#12-troubleshooting)
13. [Backup & Restore](#13-backup--restore)

---

## 1. Overview

### Architecture

```
┌────────────────────────────────────────────────────────┐
│                   Docker Desktop                       │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ Frontend │  │ Backend  │  │  Redis   │  │Postgres│  │
│  │ (Nginx)  │  │ (FastAPI)│  │ (Cache)  │  │  (15)  │  │
│  │ :3000    │  │ :8000    │  │ :6379    │  │ :5432  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                        │
│  Ollama LLM: Running inside Docker OR Host at :11434  │
└────────────────────────────────────────────────────────┘
```

### What Gets Deployed (No Source Code)

```
BGV-Package/
├── docker-compose.yml          # Production container orchestration
├── .env.template               # Environment variable template
├── .env                        # Configuration (created from template)
├── install.ps1                 # Load Docker images from tarballs
├── Start.ps1                   # Start all services
├── Stop.ps1                    # Stop all services
├── restart.ps1                 # Restart all services
├── health-check.ps1            # Check service health
├── backup.ps1                  # Database backup script
├── README.md                   # Quick reference document
├── images/                     # Pre-built Docker image tarballs
│   ├── bgv-frontend.tar
│   ├── bgv-backend.tar
│   ├── bgv-postgres.tar
│   └── bgv-redis.tar
└── data/                       # Runtime persistent data (auto-created)
    ├── logs/
    └── uploads/
```

---

## 2. Prerequisites

### Developer Machine (Build Machine)

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker Desktop | Latest | Build Docker images |
| PowerShell | 5.1+ | Run packaging scripts |
| Git | Any | Clone source code |
| Internet | Required | Download base images & dependencies |

### Target Machine (Deployment Machine)

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker Desktop | Latest | Run containers |
| PowerShell | 5.1+ | Run management scripts |
| Disk Space | ~10 GB | For images + data |
| RAM | 16 GB+ recommended | For all services + local LLM |
| OS | Windows 10/11 Pro/Enterprise | Docker Desktop support |

---

## 3. Developer Machine: Build & Package

### Step 3.1: Verify Source Code Location

Ensure the source code is available at:
`C:\Users\PoojaThite\source\repos\BGV-V1.0\BGV-V1.0`

### Step 3.2: Create the Package Directory

Open PowerShell as Administrator and run:

```powershell
$packagePath = "C:\bgv-deployment-package"

# Create directories
New-Item -ItemType Directory -Force -Path "$packagePath"
New-Item -ItemType Directory -Force -Path "$packagePath\images"
New-Item -ItemType Directory -Force -Path "$packagePath\backend\logs"
New-Item -ItemType Directory -Force -Path "$packagePath\data"
```

---

## 4. Create Deployment Package Files

### Step 4.1: Create `docker-compose.yml`

Create the orchestration file at `C:\bgv-deployment-package\docker-compose.yml`:

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15-alpine
    container_name: bgv_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: bgv_db
      POSTGRES_USER: bgv_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - bgv-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bgv_user -d bgv_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: bgv_redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - bgv-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    container_name: bgv_ollama
    restart: unless-stopped
    ports:
      - "127.0.0.1:11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - bgv-network
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:11434/api/tags || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    deploy:
      resources:
        limits:
          memory: 4G

  backend:
    image: bgv-backend:latest
    container_name: bgv_backend
    restart: unless-stopped
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://bgv_user:${POSTGRES_PASSWORD}@postgres:5432/bgv_db
      - DATABASE_SYNC_URL=postgresql://bgv_user:${POSTGRES_PASSWORD}@postgres:5432/bgv_db
      - SECRET_KEY=${SECRET_KEY}
      - OLLAMA_BASE_URL=http://ollama:11434
      - REDIS_URL=redis://redis:6379/0
      - UPLOAD_DIR=/app/uploads
      - LOG_LEVEL=INFO
      - REDIS_ENABLED=true
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - GOOGLE_REDIRECT_URI=${GOOGLE_REDIRECT_URI}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_ENABLED=${OPENAI_ENABLED}
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - upload_data:/app/uploads
      - ./backend/logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - bgv-network

  frontend:
    image: bgv-frontend:latest
    container_name: bgv_frontend
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - backend
    networks:
      - bgv-network

volumes:
  pgdata:
  redis_data:
  ollama_data:
  upload_data:

networks:
  bgv-network:
    driver: bridge
```

### Step 4.2: Create `.env.template`

Create file: `C:\bgv-deployment-package\.env.template`

```env
# ============================================================
# BGV Platform - Environment Configuration
# ============================================================

# Database credentials
POSTGRES_PASSWORD=change_me_to_a_strong_password

# Security key (JWT Signing / Sessions)
# Generate one: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=change-this-to-a-secure-random-string-in-production

# Google OAuth2 Settings (required for login)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback

# OpenAI Fallback Settings (optional)
OPENAI_ENABLED=false
OPENAI_API_KEY=
```

---

## 5. Build Docker Images

On the **developer machine**, build the backend and frontend custom images.

```powershell
# Build Backend
cd C:\Users\PoojaThite\source\repos\BGV-V1.0\BGV-V1.0\backend
docker build -t bgv-backend:latest .

# Build Frontend
cd C:\Users\PoojaThite\source\repos\BGV-V1.0\BGV-V1.0\frontend
docker build -t bgv-frontend:latest .
```

---

## 6. Export Docker Images

Export the built images and required infrastructure dependencies to `.tar` files in the package directory.

```powershell
$packagePath = "C:\bgv-deployment-package"

# Pull third party images from Docker Hub
docker pull postgres:15-alpine
docker pull redis:7-alpine

# Save to tar files
docker save -o "$packagePath\images\bgv-backend.tar" bgv-backend:latest
docker save -o "$packagePath\images\bgv-frontend.tar" bgv-frontend:latest
docker save -o "$packagePath\images\bgv-postgres.tar" postgres:15-alpine
docker save -o "$packagePath\images\bgv-redis.tar" redis:7-alpine
```

---

## 7. Target Machine: Setup & Deploy

### Step 7.1: Setup Target Machine
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Enable WSL2 backend when prompted during installation.
3. Open Docker Desktop and ensure it is running successfully.

### Step 7.2: Copy the Package
Copy the entire `C:\bgv-deployment-package` folder to the target machine via network share, external storage, or Git clone.

### Step 7.3: Load the Images
On the target machine, open **PowerShell as Administrator** in the package folder and run:

```powershell
.\install.ps1
```

*(This loads all the `.tar` image files in the `images` directory into the local Docker engine using `docker load`.)*

---

## 8. Configuration

Create and edit the `.env` file in the package folder:

```powershell
# Copy the template to .env
Copy-Item .env.template .env
```

Open `.env` in Notepad:
```powershell
notepad .env
```
Update `POSTGRES_PASSWORD`, `SECRET_KEY`, and Google OAuth settings as needed.

---

## 9. Start the Application

Start all containerized services:

```powershell
.\Start.ps1
```

Once running:
- **Frontend Portal**: `http://localhost:3000`
- **Backend API Docs**: `http://localhost:8000/docs`

---

## 10. Management Scripts

The package includes helper scripts to manage the services easily:

*   **Start**: `.\Start.ps1` — Launches all containers in the background.
*   **Stop**: `.\Stop.ps1` — Shuts down the container stack cleanly.
*   **Restart**: `.\restart.ps1` — Stops and starts all containers to apply configuration updates.
*   **Health Check**: `.\health-check.ps1` — Runs health-status checks on endpoints and containers.
*   **Backup**: `.\backup.ps1` — Generates a safe timestamped SQL backup of PostgreSQL.

---

## 11. Health Check & Verification

Run the verification check:

```powershell
.\health-check.ps1
```

### Expected Container Output
```
Name            Status               Ports
bgv_postgres    Up (healthy)         127.0.0.1:5432->5432/tcp
bgv_redis       Up (healthy)         127.0.0.1:6379->6379/tcp
bgv_ollama      Up (healthy)         127.0.0.1:11434->11434/tcp
bgv_backend     Up                   127.0.0.1:8000->8000/tcp
bgv_frontend    Up                   0.0.0.0:3000->80/tcp
```

---

## 12. Troubleshooting

| Symptom | Common Cause | Resolution |
|---------|--------------|------------|
| "Docker Desktop not running" | Docker daemon is stopped | Launch Docker Desktop from the Start Menu. |
| Backend crashes on start | Database migrations or connection failed | Wait 20 seconds and run `.\restart.ps1` to re-trigger migration checks. |
| AI features fail or time out | Ollama model is missing | Inside the `bgv_ollama` container, download the required model: `docker exec -it bgv_ollama ollama pull llama3.1:latest` (or `phi3:mini`). |
| Port 3000 already in use | Conflicting local web server | Identify the conflict or modify the port binding under `frontend` in `docker-compose.yml`. |

---

## 13. Backup & Restore

### Create Database Backup
```powershell
.\backup.ps1
```

### Restore Database from Backup
```powershell
# Stop services
.\Stop.ps1

# Clear database volume
docker volume rm bgv-deployment-package_pgdata

# Start database only
docker compose up -d postgres
Start-Sleep -Seconds 8

# Load the SQL backup file
Get-Content ".\backups\bgv_backup_XXXXXXXX_XXXXXX.sql" | docker exec -i bgv_postgres psql -U bgv_user -d bgv_db

# Restart whole stack
.\Start.ps1
```
