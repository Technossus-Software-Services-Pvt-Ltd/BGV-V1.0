"""
End-to-end test: Upload → Document Created → Processing Queued → Status Tracking.
This tests the complete flow from frontend upload through backend API.
"""
import pytest
from httpx import AsyncClient
from pathlib import Path


class TestEndToEndFlow:
    """Full end-to-end tests simulating the frontend-to-backend workflow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_upload_flow(self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path):
        """
        Simulates the complete user flow:
        1. User creates a candidate
        2. User uploads documents for that candidate
        3. User checks document list
        4. User views document detail
        5. User checks batch status
        6. User views audit logs
        """
        # Step 1: Health check (frontend polls this on load)
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # Step 2: Create candidate
        create_resp = await client.post("/api/v1/candidates", json={
            "candidate_id": "BGV-E2E-001",
            "name": "Priya Sharma",
            "email": "priya.sharma@example.com",
            "phone": "+919876543210",
            "date_of_birth": "1992-03-14",
            "pan_number": "BSPPS1234K",
            "aadhaar_last_four": "5678",
        })
        assert create_resp.status_code == 201
        candidate = create_resp.json()
        assert candidate["candidate_id"] == "BGV-E2E-001"

        # Step 3: Upload documents
        upload_resp = await client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "BGV-E2E-001",
                "candidate_name": "Priya Sharma",
                "candidate_dob": "1992-03-14",
                "candidate_pan": "BSPPS1234K",
                "candidate_aadhaar_last_four": "5678",
            },
            files=[
                ("files", ("pan_card.pdf", sample_pdf_bytes, "application/pdf")),
                ("files", ("aadhaar_front.pdf", sample_pdf_bytes, "application/pdf")),
            ],
        )
        assert upload_resp.status_code == 202
        upload_data = upload_resp.json()
        assert upload_data["total_files"] == 2
        batch_id = upload_data["batch_id"]
        correlation_id = upload_data["correlation_id"]
        doc_ids = [d["id"] for d in upload_data["documents"]]
        assert len(doc_ids) == 2

        # Step 4: List documents (frontend Documents page)
        docs_resp = await client.get("/api/v1/documents")
        assert docs_resp.status_code == 200
        docs = docs_resp.json()
        assert len(docs) == 2
        assert all(d["processing_status"] == "uploaded" for d in docs)

        # Step 5: Get document detail (frontend Document Detail page)
        detail_resp = await client.get(f"/api/v1/documents/{doc_ids[0]}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["document"]["original_filename"] == "pan_card.pdf"
        assert detail["document"]["correlation_id"] == correlation_id

        # Step 6: Check batch status
        batch_resp = await client.get(f"/api/v1/processing/batches/{batch_id}")
        assert batch_resp.status_code == 200
        batch = batch_resp.json()
        assert batch["total_files"] == 2
        assert batch["batch_reference"].startswith("BATCH-")

        # Step 7: Check audit logs for this correlation
        audit_resp = await client.get("/api/v1/audit/logs", params={"correlation_id": correlation_id})
        assert audit_resp.status_code == 200
        audit_logs = audit_resp.json()
        # Should have upload audit entries
        assert len(audit_logs) >= 2  # One per file uploaded

        # Step 8: Verify candidate is still accessible
        cand_resp = await client.get("/api/v1/candidates/BGV-E2E-001")
        assert cand_resp.status_code == 200
        assert cand_resp.json()["name"] == "Priya Sharma"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_upload_for_existing_candidate_reuses_record(
        self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """When uploading for an existing candidate_id, shouldn't create a duplicate."""
        # Create candidate
        await client.post("/api/v1/candidates", json={
            "candidate_id": "BGV-REUSE-001",
            "name": "Existing User",
        })

        # Upload for same candidate
        resp = await client.post(
            "/api/v1/upload",
            data={"candidate_id": "BGV-REUSE-001", "candidate_name": "Existing User"},
            files=[("files", ("doc.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 202

        # Verify only one candidate with this ID
        list_resp = await client.get("/api/v1/candidates")
        data = list_resp.json()
        matching = [c for c in data["candidates"] if c["candidate_id"] == "BGV-REUSE-001"]
        assert len(matching) == 1

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multiple_batches_for_same_candidate(
        self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Same candidate can have multiple upload batches."""
        # First upload batch
        resp1 = await client.post(
            "/api/v1/upload",
            data={"candidate_id": "BGV-BATCH-001", "candidate_name": "Batch Test"},
            files=[("files", ("batch1.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp1.status_code == 202
        batch1_ref = resp1.json()["batch_reference"]

        # Second upload batch
        resp2 = await client.post(
            "/api/v1/upload",
            data={"candidate_id": "BGV-BATCH-001", "candidate_name": "Batch Test"},
            files=[("files", ("batch2.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp2.status_code == 202
        batch2_ref = resp2.json()["batch_reference"]

        # Different batch references
        assert batch1_ref != batch2_ref

        # List batches
        batches_resp = await client.get("/api/v1/processing/batches")
        assert batches_resp.status_code == 200
        batches = batches_resp.json()
        assert len(batches) >= 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_documents_filterable_by_status(
        self, client: AsyncClient, sample_pdf_bytes: bytes, upload_dir: Path
    ):
        """Documents should be filterable by processing status."""
        # Upload a document
        await client.post(
            "/api/v1/upload",
            data={"candidate_id": "BGV-FILTER-001", "candidate_name": "Filter Test"},
            files=[("files", ("filter_test.pdf", sample_pdf_bytes, "application/pdf"))],
        )

        # Filter by uploaded status
        resp = await client.get("/api/v1/documents", params={"status_filter": "uploaded"})
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1
        assert all(d["processing_status"] == "uploaded" for d in docs)

        # Filter by completed status (should be empty)
        resp_completed = await client.get("/api/v1/documents", params={"status_filter": "completed"})
        assert resp_completed.status_code == 200
        assert resp_completed.json() == []
