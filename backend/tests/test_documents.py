import pytest
from httpx import AsyncClient


class TestDocumentsEndpoint:
    @pytest.mark.asyncio
    async def test_list_documents_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_list_documents_with_status_filter(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents", params={"status_filter": "completed"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_document_ocr_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents/nonexistent-id/ocr")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_document_classification_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents/nonexistent-id/classification")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_document_validation_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/documents/nonexistent-id/validation")
        assert response.status_code == 200
        assert response.json() == []


class TestProcessingEndpoint:
    @pytest.mark.asyncio
    async def test_get_timeline_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/processing/timeline/nonexistent-id")
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "nonexistent-id"
        assert data["events"] == []
        assert data["current_status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_batches_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/processing/batches")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_batch_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/processing/batches/nonexistent-id")
        assert response.status_code == 404


class TestAuditEndpoint:
    @pytest.mark.asyncio
    async def test_list_audit_logs_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/audit/logs")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filter(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/v1/audit/logs", params={"action": "upload"})
        assert response.status_code == 200
        assert response.json() == []
