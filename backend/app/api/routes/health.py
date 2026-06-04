from fastapi import APIRouter
from app.services.ai.ollama_client import OllamaClient
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    ollama_client = OllamaClient()
    ollama_healthy = await ollama_client.check_health()
    model_available = await ollama_client.ensure_model_available() if ollama_healthy else False

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
