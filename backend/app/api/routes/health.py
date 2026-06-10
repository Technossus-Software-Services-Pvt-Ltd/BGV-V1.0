from fastapi import APIRouter
from app.services.dependencies import get_ai_classifier
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    client = get_ai_classifier().client
    ollama_healthy = await client.check_health()
    model_available = await client.ensure_model_available() if ollama_healthy else False

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
