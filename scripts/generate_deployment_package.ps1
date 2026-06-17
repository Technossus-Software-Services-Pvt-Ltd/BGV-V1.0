# ══════════════════════════════════════════════════════════════
# BGV Platform - Package Generator Script
# ══════════════════════════════════════════════════════════════
# Run this script from the project root to generate a self-contained
# deployment package in the target directory (without source code).
# ══════════════════════════════════════════════════════════════

param(
    [string]$TargetDir = "C:\bgv-deployment-package",
    [bool]$IncludeInfraImages = $true
)

$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BGV Platform - Generating Deployment Package" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running. Please start it and retry." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker Desktop is running" -ForegroundColor Green
Write-Host ""

# Setup directories
Write-Host "Preparing target directories at: $TargetDir..." -ForegroundColor Yellow
if (Test-Path $TargetDir) {
    Remove-Item -Recurse -Force $TargetDir
}
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\images" | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\backend\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$TargetDir\data" | Out-Null
Write-Host "  ✓ Target directories created" -ForegroundColor Green
Write-Host ""

# Get script root (assumes running from project root)
$projectRoot = Get-Location

# 1. Build BGV Backend Image
Write-Host "Building BGV Backend Docker image..." -ForegroundColor Yellow
cd "$projectRoot\backend"
docker build -t bgv-backend:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build BGV Backend image." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Backend image built successfully" -ForegroundColor Green
Write-Host ""

# 2. Build BGV Frontend Image
Write-Host "Building BGV Frontend Docker image..." -ForegroundColor Yellow
cd "$projectRoot\frontend"
docker build -t bgv-frontend:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to build BGV Frontend image." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Frontend image built successfully" -ForegroundColor Green
Write-Host ""

# 3. Export images to tarballs
Write-Host "Exporting images to tar files..." -ForegroundColor Yellow

Write-Host "  Exporting BGV Backend -> bgv-backend.tar..." -ForegroundColor Yellow
docker save -o "$TargetDir\images\bgv-backend.tar" bgv-backend:latest

Write-Host "  Exporting BGV Frontend -> bgv-frontend.tar..." -ForegroundColor Yellow
docker save -o "$TargetDir\images\bgv-frontend.tar" bgv-frontend:latest

if ($IncludeInfraImages) {
    Write-Host "  Pulling & exporting PostgreSQL image..." -ForegroundColor Yellow
    docker pull postgres:15-alpine
    docker save -o "$TargetDir\images\bgv-postgres.tar" postgres:15-alpine

    Write-Host "  Pulling & exporting Redis image..." -ForegroundColor Yellow
    docker pull redis:7-alpine
    docker save -o "$TargetDir\images\bgv-redis.tar" redis:7-alpine
}
Write-Host "  ✓ Images exported successfully" -ForegroundColor Green
Write-Host ""

# 4. Generate docker-compose.yml
Write-Host "Generating docker-compose.yml..." -ForegroundColor Yellow
$composeContent = @'
version: "3.9"

services:
  postgres:
    image: postgres:15-alpine
    container_name: bgv_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: bgv_db
      POSTGRES_USER: bgv_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-bgv_secure_pass_change_me}
    ports:
      - "5432:5432"
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
      - "6379:6379"
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
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - bgv-network
    healthcheck:
      test: ["CMD", "ollama", "list"]
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
      - DATABASE_URL=postgresql+asyncpg://bgv_user:${POSTGRES_PASSWORD:-bgv_secure_pass_change_me}@postgres:5432/bgv_db
      - DATABASE_SYNC_URL=postgresql://bgv_user:${POSTGRES_PASSWORD:-bgv_secure_pass_change_me}@postgres:5432/bgv_db
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
      - "8000:8000"
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
'@
$composeContent | Out-File -FilePath "$TargetDir\docker-compose.yml" -Encoding utf8
Write-Host "  ✓ Generated docker-compose.yml" -ForegroundColor Green
Write-Host ""

# 5. Generate .env.template
Write-Host "Generating .env.template..." -ForegroundColor Yellow
$envContent = @"
# ============================================================
# BGV Platform - Deployment Settings
# ============================================================

# Database credentials
POSTGRES_PASSWORD=bgv_secure_pass_change_me

# JWT / Security key
# Generate a strong key: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=change-this-to-a-secure-random-string-in-production

# Google OAuth2 Credentials (required for login)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback

# OpenAI Fallback API (optional)
OPENAI_ENABLED=false
OPENAI_API_KEY=
"@
$envContent | Out-File -FilePath "$TargetDir\.env.template" -Encoding utf8
$envContent | Out-File -FilePath "$TargetDir\.env" -Encoding utf8
Write-Host "  ✓ Generated .env.template and default .env" -ForegroundColor Green
Write-Host ""

# 6. Generate install.ps1
Write-Host "Generating install.ps1..." -ForegroundColor Yellow
$installContent = @"
# ══════════════════════════════════════════════════════════════
# BGV Platform - Installation Script
# ══════════════════════════════════════════════════════════════

`$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BGV Platform - Installing Docker Images" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check Docker is running
Write-Host "Checking Docker Desktop..." -ForegroundColor Yellow
`$dockerInfo = docker info 2>&1
if (`$LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running! Please start it and try again." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker Desktop is running" -ForegroundColor Green
Write-Host ""

# Get script directory
`$scriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$imagesDir = Join-Path `$scriptDir "images"

# Load each image
`$tarFiles = Get-ChildItem -Path `$imagesDir -Filter "*.tar"
if (`$tarFiles.Count -eq 0) {
    Write-Host "ERROR: No .tar image files found in: `$imagesDir" -ForegroundColor Red
    exit 1
}

`$step = 1
`$total = `$tarFiles.Count

foreach (`$tar in `$tarFiles) {
    `$size = [math]::Round(`$tar.Length / 1MB, 1)
    Write-Host "[`$step/`$total] Loading `$(`$tar.Name) (`$size MB)..." -ForegroundColor Yellow
    docker load -i `$tar.FullName
    if (`$LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to load `$(`$tar.Name)" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ Loaded successfully" -ForegroundColor Green
    `$step++
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installed images:" -ForegroundColor Yellow
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}" | Select-String "bgv"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open the '.env' file and configure database and OAuth credentials." -ForegroundColor White
Write-Host "  2. Run '.\Start.ps1' to start the platform." -ForegroundColor White
"@
$installContent | Out-File -FilePath "$TargetDir\install.ps1" -Encoding utf8
Write-Host "  ✓ Generated install.ps1" -ForegroundColor Green
Write-Host ""

# 7. Generate Start.ps1
Write-Host "Generating Start.ps1..." -ForegroundColor Yellow
$startContent = @"
# ══════════════════════════════════════════════════════════════
# BGV Platform - Start Services
# ══════════════════════════════════════════════════════════════

`$ErrorActionPreference = "Stop"
`$scriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location `$scriptDir

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BGV Platform - Starting Services" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.template to .env and configure it first." -ForegroundColor Red
    exit 1
}

# Check Docker
`$dockerInfo = docker info 2>&1
if (`$LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running!" -ForegroundColor Red
    exit 1
}

Write-Host "Starting containers..." -ForegroundColor Yellow
docker compose --env-file .env up -d --force-recreate
if (`$LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start services." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting for services to spin up..." -ForegroundColor Yellow
Start-Sleep -Seconds 12

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BGV Platform is running!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:    http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:    http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Use .\Stop.ps1 to stop services." -ForegroundColor Gray
Write-Host "  Use .\health-check.ps1 to verify health status." -ForegroundColor Gray
"@
$startContent | Out-File -FilePath "$TargetDir\Start.ps1" -Encoding utf8
Write-Host "  ✓ Generated Start.ps1" -ForegroundColor Green
Write-Host ""

# 8. Generate Stop.ps1
Write-Host "Generating Stop.ps1..." -ForegroundColor Yellow
$stopContent = @"
# ══════════════════════════════════════════════════════════════
# BGV Platform - Stop Services
# ══════════════════════════════════════════════════════════════

`$scriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location `$scriptDir

Write-Host "Stopping BGV Platform services and cleaning up containers..." -ForegroundColor Yellow
docker compose down --remove-orphans

if (`$LASTEXITCODE -eq 0) {
    Write-Host "  ✓ All services stopped successfully" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Error stopping some containers" -ForegroundColor Yellow
}
"@
$stopContent | Out-File -FilePath "$TargetDir\Stop.ps1" -Encoding utf8
Write-Host "  ✓ Generated Stop.ps1" -ForegroundColor Green
Write-Host ""

# 9. Generate restart.ps1
Write-Host "Generating restart.ps1..." -ForegroundColor Yellow
$restartContent = @"
# ══════════════════════════════════════════════════════════════
# BGV Platform - Restart Services
# ══════════════════════════════════════════════════════════════

`$scriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location `$scriptDir

Write-Host "Restarting BGV Platform services..." -ForegroundColor Yellow
docker compose --env-file .env down
docker compose --env-file .env up -d

if (`$LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  ✓ Services restarted successfully" -ForegroundColor Green
    Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
} else {
    Write-Host "  ⚠ Restart failed or had errors. Run .\health-check.ps1" -ForegroundColor Yellow
}
"@
$restartContent | Out-File -FilePath "$TargetDir\restart.ps1" -Encoding utf8
Write-Host "  ✓ Generated restart.ps1" -ForegroundColor Green
Write-Host ""

# 10. Generate health-check.ps1
Write-Host "Generating health-check.ps1..." -ForegroundColor Yellow
$healthContent = @"
# ══════════════════════════════════════════════════════════════
# BGV Platform - Health Check Script
# ══════════════════════════════════════════════════════════════

`$scriptDir = Split-Path -Parent `$MyInvocation.MyCommand.Path
Set-Location `$scriptDir

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BGV Platform - Health Status" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

Write-Host "Container Status:" -ForegroundColor Yellow
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
Write-Host ""

`$services = @(
    @{ Name = "PostgreSQL"; Url = `$null; Container = "bgv_postgres" },
    @{ Name = "Redis Cache"; Url = `$null; Container = "bgv_redis" },
    @{ Name = "Ollama Inference"; Url = "http://localhost:11434/api/tags"; Container = "bgv_ollama" },
    @{ Name = "Backend Service"; Url = "http://localhost:8000/api/v1/health"; Container = "bgv_backend" },
    @{ Name = "Frontend Portal"; Url = "http://localhost:3000"; Container = "bgv_frontend" }
)

Write-Host "Service Checks:" -ForegroundColor Yellow
foreach (`$svc in `$services) {
    if (`$svc.Url) {
        try {
            `$response = Invoke-WebRequest -Uri `$svc.Url -UseBasicParsing -TimeoutSec 5
            Write-Host "  ✓ `$($svc.Name) - OK (`$($response.StatusCode))" -ForegroundColor Green
        } catch {
            Write-Host "  ✗ `$($svc.Name) - UNREACHABLE" -ForegroundColor Red
        }
    } elseif (`$svc.Container) {
        `$status = docker inspect --format='{{.State.Status}}' `$svc.Container 2>&1
        if (`$status -eq "running") {
            Write-Host "  ✓ `$($svc.Name) - Running" -ForegroundColor Green
        } else {
            Write-Host "  ✗ `$($svc.Name) - `$status" -ForegroundColor Red
        }
    }
}
Write-Host ""
"@
$healthContent | Out-File -FilePath "$TargetDir\health-check.ps1" -Encoding utf8
Write-Host "  ✓ Generated health-check.ps1" -ForegroundColor Green
Write-Host ""

# 11. Generate README.md
Write-Host "Generating README.md..." -ForegroundColor Yellow
$readmeContent = @"
# BGV Platform - Deployment Package

This is a self-contained deployment package for the AI-Powered Background Verification (BGV) Platform. The source code is compiled into Docker images and packaged locally so it can be deployed on any machine running Docker Desktop without revealing the underlying code.

## Package Directory Layout
```
BGV-Package/
├── .env                 # Environment config (created on install)
├── .env.template        # Template with setup fields
├── docker-compose.yml   # Multi-container config
├── install.ps1          # Load docker images from tarballs
├── Start.ps1            # Spin up the containers
├── Stop.ps1             # Stop the containers
├── restart.ps1          # Restart the containers
├── health-check.ps1     # Verify services status
└── images/              # Stored image tarballs
    ├── bgv-backend.tar
    └── bgv-frontend.tar
```

## Quick Start (Deployment Instructions)

### 1. Prerequisites
- **Docker Desktop** installed and running.
- **Git** installed.

### 2. Installation
Open **PowerShell as Administrator** in this directory and run:
```powershell
.\install.ps1
```
This loads the precompiled backend and frontend docker images into your local Docker daemon.

### 3. Configuration
Copy `.env.template` to `.env` (the installer does this automatically if it doesn't exist) and fill in the required fields:
- `SECRET_KEY`: Change to a secure random string.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: Put your Google API Client credentials here.

### 4. Running the Platform
Run the startup script:
```powershell
.\Start.ps1
```
This will automatically launch the database, caching layer, Ollama, backend API, and the frontend portal. 

Once started:
- **Frontend Portal**: http://localhost:3000
- **Backend Swagger UI**: http://localhost:8000/docs

### 5. Control Services
- **Stop**: `.\Stop.ps1`
- **Restart**: `.\restart.ps1`
- **Verify status**: `.\health-check.ps1`
"@
$readmeContent | Out-File -FilePath "$TargetDir\README.md" -Encoding utf8
Write-Host "  ✓ Generated README.md" -ForegroundColor Green
Write-Host ""

# Done!
cd $projectRoot
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Package generation successfully completed!" -ForegroundColor Green
Write-Host "  Folder location: $TargetDir" -ForegroundColor White
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
