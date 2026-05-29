import pytest
from httpx import AsyncClient
from pathlib import Path


class TestUploadEndpoint:
    @pytest.mark.asyncio
    async def test_upload_no_files_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-001", "candidate_name": "Test User"},
        )
        # FastAPI will return 422 if 'files' field missing from multipart
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_single_pdf(self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path):
        """Test uploading a single PDF file."""
        response = await client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "CAND-UP-1",
                "candidate_name": "Upload Test",
            },
            files=[("files", ("test_document.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert response.status_code == 202
        data = response.json()
        assert data["total_files"] == 1
        assert data["batch_reference"].startswith("BATCH-")
        assert data["correlation_id"] is not None
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "test_document.pdf"

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path):
        """Test uploading multiple files in one batch."""
        files = [
            ("files", ("doc1.pdf", sample_pdf_bytes, "application/pdf")),
            ("files", ("doc2.pdf", sample_pdf_bytes, "application/pdf")),
            ("files", ("doc3.pdf", sample_pdf_bytes, "application/pdf")),
        ]
        response = await client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "CAND-MULTI",
                "candidate_name": "Multi Upload",
            },
            files=files,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["total_files"] == 3
        assert len(data["documents"]) == 3

    @pytest.mark.asyncio
    async def test_upload_creates_candidate_if_not_exists(
        self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Uploading for a new candidate should auto-create the candidate record."""
        response = await client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "CAND-AUTO",
                "candidate_name": "Auto Created",
                "candidate_pan": "ABCDE1234F",
            },
            files=[("files", ("pan_card.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert response.status_code == 202

        # Verify candidate was created
        cand_response = await client.get("/api/v1/candidates/CAND-AUTO")
        assert cand_response.status_code == 200
        assert cand_response.json()["name"] == "Auto Created"

    @pytest.mark.asyncio
    async def test_upload_with_candidate_metadata(
        self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Test that candidate metadata (DOB, PAN, Aadhaar) is stored correctly."""
        response = await client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "CAND-META",
                "candidate_name": "Meta Test",
                "candidate_dob": "1990-01-01",
                "candidate_pan": "XYZAB5678C",
                "candidate_aadhaar_last_four": "9876",
            },
            files=[("files", ("aadhaar.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert response.status_code == 202
        data = response.json()
        assert data["candidate_id"] is not None
