from fastapi import APIRouter
from app.services.ai.ollama_client import OllamaClient
from app.core.config import settings

router = APIRouter()

_ollama_client = OllamaClient()


@router.get("/health")
async def health_check():
    ollama_healthy = await _ollama_client.check_health()
    model_available = await _ollama_client.ensure_model_available() if ollama_healthy else False

    return {
        "status": "healthy",
        "services": {
            "api": True,
            "ollama": ollama_healthy,
            "ollama_model": model_available,
        },
        "features": {
            "openai_enabled": settings.openai_enabled,
        },
    }
