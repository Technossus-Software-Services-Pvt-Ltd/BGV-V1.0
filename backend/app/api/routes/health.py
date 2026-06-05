from functools import lru_cache

from fastapi import APIRouter
from app.services.dependencies import get_ai_classifier

router = APIRouter()


@lru_cache(maxsize=1)
def _get_ollama_client():
    return get_ai_classifier().client


@router.get("/health")
async def health_check():
    client = _get_ollama_client()
    ollama_healthy = await client.check_health()
    model_available = await client.ensure_model_available() if ollama_healthy else False

    return {
        "status": "healthy",
        "services": {
            "api": True,
            "ollama": ollama_healthy,
            "ollama_model": model_available,
        },
    }
