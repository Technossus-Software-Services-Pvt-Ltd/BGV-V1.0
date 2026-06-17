import time
import httpx
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import OllamaConnectionError

logger = get_logger("ai.ollama")


class OllamaResponse:
    def __init__(
        self,
        content: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        duration_ms: int = 0,
        error: Optional[str] = None,
    ):
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.duration_ms = duration_ms
        self.error = error

    @property
    def is_successful(self) -> bool:
        return self.error is None and len(self.content.strip()) > 0


class OllamaClient:
    """Client for communicating with local Ollama instance.

    Reuses a persistent httpx.AsyncClient for connection pooling.
    """

    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.ai_timeout_seconds
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=settings.ollama_connect_timeout),
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        format: Optional[dict | str] = "json",
    ) -> OllamaResponse:
        start_time = time.time()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": format,
            "options": {
                "temperature": temperature,
                "num_predict": settings.ollama_num_predict,
                "top_p": 0.9,
                "num_ctx": settings.ollama_num_ctx,
            },
        }

        try:
            response = await self._request_with_retry(payload)
            data = response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            return OllamaResponse(
                content=data.get("response", ""),
                model=data.get("model", self.model),
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                duration_ms=duration_ms,
            )

        except httpx.ConnectError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running."
            logger.error("ollama_connection_failed", error=str(e), url=self.base_url)
            return OllamaResponse(
                content="",
                model=self.model,
                duration_ms=duration_ms,
                error=error_msg,
            )

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Ollama request timed out after {self.timeout}s"
            logger.error("ollama_timeout", timeout=self.timeout)
            return OllamaResponse(
                content="",
                model=self.model,
                duration_ms=duration_ms,
                error=error_msg,
            )

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Ollama returned HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error("ollama_http_error", status=e.response.status_code)
            return OllamaResponse(
                content="",
                model=self.model,
                duration_ms=duration_ms,
                error=error_msg,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected Ollama error: {str(e)}"
            logger.error("ollama_unexpected_error", error=str(e))
            return OllamaResponse(
                content="",
                model=self.model,
                duration_ms=duration_ms,
                error=error_msg,
            )

    async def check_health(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    @retry(
        stop=stop_after_attempt(settings.ollama_max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _request_with_retry(self, payload: dict) -> httpx.Response:
        """POST to Ollama with retry on transient connection/timeout errors."""
        response = await self._client.post("/api/generate", json=payload)
        response.raise_for_status()
        return response

    async def ensure_model_available(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            if response.status_code != 200:
                return False
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            # Check if model is available (with or without tag)
            model_base = self.model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False

    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
