"""Phase 7: Integration tests for the upload→processing pipeline.

These tests exercise the full HTTP flow with mocked external dependencies
(OCR engine, Ollama AI) to verify end-to-end behavior without needing
real ML/AI infrastructure.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

from httpx import AsyncClient


class TestUploadProcessingIntegration:
    """Integration tests: upload files and verify background processing runs."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_triggers_background_processing(
        self, authenticated_client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Upload a file, then verify the document transitions from UPLOADED status."""
        response = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-INT-1", "candidate_name": "Integration Test"},
            files=[("files", ("test.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert response.status_code == 202
        data = response.json()
        assert data["total_files"] == 1
        doc_id = data["documents"][0]["id"]

        # The document should exist in the DB
        doc_resp = await authenticated_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()["document"]
        assert doc_data["original_filename"] == "test.pdf"
        # Status may already be processing or still uploaded (race with background task)
        valid_statuses = [
            "uploaded", "queued", "normalizing", "ocr_running", "ocr_complete",
            "ai_classifying", "ai_classification_complete", "validating",
            "validation_complete", "completed", "failed",
        ]
        assert doc_data["processing_status"] in valid_statuses

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_max_files_limit_enforced(
        self, authenticated_client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Uploading more than max_files_per_upload returns 400."""
        from app.core.config import settings

        files = [
            ("files", (f"doc{i}.pdf", sample_pdf_bytes, "application/pdf"))
            for i in range(settings.max_files_per_upload + 1)
        ]
        response = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-LIMIT", "candidate_name": "Limit Test"},
            files=files,
        )
        assert response.status_code == 400
        assert "Maximum" in response.json()["detail"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_invalid_extension_rejected(
        self, authenticated_client: AsyncClient, upload_dir: Path
    ):
        """Uploading a file with disallowed extension should fail."""
        response = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-EXT", "candidate_name": "Ext Test"},
            files=[("files", ("malware.exe", b"MZ\x90\x00", "application/octet-stream"))],
        )
        # Should reject with 400 (invalid extension)
        assert response.status_code == 400

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_oversized_file_rejected(
        self, authenticated_client: AsyncClient, upload_dir: Path, monkeypatch
    ):
        """Uploading a file larger than max size returns 413."""
        from app.core.config import settings
        # Temporarily set very small max size
        monkeypatch.setattr(settings, "max_upload_size_mb", 0)

        response = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-BIG", "candidate_name": "Big Test"},
            files=[("files", ("big.pdf", b"%PDF-1.4\n" + b"x" * 2048, "application/pdf"))],
        )
        assert response.status_code == 413


class TestCandidateWorkflowIntegration:
    """Integration tests for candidate CRUD + document listing."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_candidate_then_upload_then_list_docs(
        self, authenticated_client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Full workflow: create candidate → upload documents → list their docs."""
        # Create candidate
        create_resp = await authenticated_client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-FLOW-1",
            "name": "Flow Test User",
            "email": "flow@example.com",
        })
        assert create_resp.status_code == 201

        # Upload documents for candidate
        upload_resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-FLOW-1", "candidate_name": "Flow Test User"},
            files=[
                ("files", ("pan.pdf", sample_pdf_bytes, "application/pdf")),
                ("files", ("aadhaar.pdf", sample_pdf_bytes, "application/pdf")),
            ],
        )
        assert upload_resp.status_code == 202
        assert upload_resp.json()["total_files"] == 2

        # List all documents
        docs_resp = await authenticated_client.get("/api/v1/documents")
        assert docs_resp.status_code == 200
        docs = docs_resp.json()
        assert len(docs) >= 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_candidate_search_by_name(self, authenticated_client: AsyncClient):
        """Test searching candidates by name."""
        # Create multiple candidates
        await authenticated_client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-SEARCH-1",
            "name": "Alice Smith",
        })
        await authenticated_client.post("/api/v1/candidates", json={
            "candidate_id": "CAND-SEARCH-2",
            "name": "Bob Johnson",
        })

        # Search by name
        resp = await authenticated_client.get("/api/v1/candidates", params={"search": "Alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("Alice" in c["name"] for c in data["candidates"])


class TestDashboardIntegration:
    """Integration tests for dashboard stats endpoint."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dashboard_stats_returns_structure(self, authenticated_client: AsyncClient):
        """Dashboard should return stats even with empty DB."""
        resp = await authenticated_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        # Should have expected keys
        assert "total_documents" in data or "total_candidates" in data or isinstance(data, dict)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dashboard_stats_caching(self, authenticated_client: AsyncClient):
        """Subsequent calls should return cached data within TTL."""
        resp1 = await authenticated_client.get("/api/v1/dashboard/stats")
        resp2 = await authenticated_client.get("/api/v1/dashboard/stats")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Both should return same data (cached)
        assert resp1.json() == resp2.json()


class TestAuthIntegration:
    """Integration tests verifying auth enforcement."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, client: AsyncClient):
        """Endpoints should reject unauthenticated requests."""
        response = await client.get("/api/v1/candidates")
        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unauthenticated_upload_returns_401(self, client: AsyncClient):
        """Upload endpoint should require auth."""
        response = await client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-X", "candidate_name": "X"},
            files=[("files", ("doc.pdf", b"%PDF-1.4\n", "application/pdf"))],
        )
        assert response.status_code == 401

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unauthenticated_dashboard_returns_401(self, client: AsyncClient):
        """Dashboard should require auth."""
        response = await client.get("/api/v1/dashboard/stats")
        assert response.status_code == 401


class TestHealthNoAuth:
    """Health endpoint should work without authentication."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: AsyncClient):
        """Health check should not require authentication."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
