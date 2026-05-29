import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "api" in data["services"]

    @pytest.mark.asyncio
    async def test_health_shows_api_as_healthy(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        data = response.json()
        assert data["services"]["api"] is True
