import pytest
from httpx import AsyncClient


class TestCandidatesEndpoint:
    @pytest.mark.asyncio
    async def test_create_candidate_success(self, client: AsyncClient):
        payload = {
            "candidate_id": "CAND-001",
            "name": "Rajesh Kumar",
            "email": "rajesh@example.com",
            "phone": "+919876543210",
            "date_of_birth": "1990-05-15",
            "pan_number": "ABCDE1234F",
            "aadhaar_last_four": "4321",
        }
        response = await client.post("/api/v1/candidates", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["candidate_id"] == "CAND-001"
        assert data["name"] == "Rajesh Kumar"
        assert data["email"] == "rajesh@example.com"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_candidate_duplicate_returns_409(self, client: AsyncClient):
        payload = {
            "candidate_id": "CAND-DUP",
            "name": "Test User",
        }
        response1 = await client.post("/api/v1/candidates", json=payload)
        assert response1.status_code == 201

        response2 = await client.post("/api/v1/candidates", json=payload)
        assert response2.status_code == 409

    @pytest.mark.asyncio
    async def test_create_candidate_missing_required_field(self, client: AsyncClient):
        payload = {"candidate_id": "CAND-002"}  # missing name
        response = await client.post("/api/v1/candidates", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_candidates_empty(self, client: AsyncClient):
        response = await client.get("/api/v1/candidates")
        assert response.status_code == 200
        data = response.json()
        assert data["candidates"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_candidates_with_data(self, client: AsyncClient):
        # Create a candidate
        await client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-LIST-1",
            "name": "User One",
        })
        await client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-LIST-2",
            "name": "User Two",
        })

        response = await client.get("/api/v1/candidates")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["candidates"]) == 2

    @pytest.mark.asyncio
    async def test_get_candidate_by_id(self, client: AsyncClient):
        # Create
        create_resp = await client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-GET-1",
            "name": "Get Test",
        })
        assert create_resp.status_code == 201

        # Get by candidate_id
        response = await client.get("/api/v1/candidates/CAND-GET-1")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_candidate_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/candidates/NONEXISTENT")
        assert response.status_code == 404
