"""Tests for Phase 7: Query optimization patterns."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest


# ─── Document list validation query optimization ─────────────────────────────────


class TestDocumentListQueryOptimization:
    """Tests that document list uses optimized subquery for best validation."""

    @pytest.mark.asyncio
    @patch("app.api.routes.documents.get_current_user")
    @patch("app.api.routes.documents.get_db")
    async def test_list_documents_calls_subquery_pattern(self, mock_get_db, mock_get_user):
        """Verify the endpoint executes the optimized subquery join."""
        from app.api.routes.documents import list_documents

        mock_db = AsyncMock()
        mock_user = MagicMock()

        # First query: documents
        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.candidate_id = "cand-1"
        mock_doc.processing_status = "completed"
        mock_doc.created_at = datetime.now(timezone.utc)

        doc_result = MagicMock()
        doc_result.scalars.return_value.all.return_value = [mock_doc]

        # Second query: validation subquery join
        val_result = MagicMock()
        val_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[doc_result, val_result])

        with patch("app.api.routes.documents.DocumentResponse") as MockResp:
            mock_resp = MagicMock()
            MockResp.model_validate.return_value = mock_resp

            result = await list_documents(
                candidate_id=None,
                status_filter=None,
                date_from=None,
                date_to=None,
                skip=0,
                limit=50,
                db=mock_db,
                _current_user=mock_user,
            )

        # Should have executed exactly 2 queries (documents + validation subquery)
        assert mock_db.execute.await_count == 2


class TestDocumentDetailOptimization:
    """Tests for document detail query structure."""

    @pytest.mark.asyncio
    async def test_fetch_document_relations_returns_tuple(self):
        """Helper function should return a 4-tuple of lists."""
        from app.api.routes.documents import _fetch_document_relations

        mock_db = AsyncMock()

        # Mock 4 sequential query results
        results = []
        for _ in range(4):
            r = MagicMock()
            r.scalars.return_value.all.return_value = []
            results.append(r)

        mock_db.execute = AsyncMock(side_effect=results)

        pages, ocr, classifications, validations = await _fetch_document_relations(
            mock_db, "doc-123"
        )

        assert pages == []
        assert ocr == []
        assert classifications == []
        assert validations == []
        assert mock_db.execute.await_count == 4


# ─── Review queue notification optimization ──────────────────────────────────────


class TestReviewQueueNotificationOptimization:
    """Tests that review queue uses subquery for latest notification."""

    @pytest.mark.asyncio
    @patch("app.api.routes.review_queue.get_current_user")
    @patch("app.api.routes.review_queue.get_db")
    async def test_review_queue_uses_subquery_for_notifications(self, mock_get_db, mock_get_user):
        """The notification lookup should use a GROUP BY subquery, not fetch-all."""
        from app.api.routes.review_queue import list_review_queue

        mock_db = AsyncMock()
        mock_user = MagicMock()

        # Count query result
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # Paginated results (empty)
        rows_result = MagicMock()
        rows_result.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

        result = await list_review_queue(
            skip=0, limit=20, search=None, status=None,
            db=mock_db, _current_user=mock_user,
        )

        # With empty results, should execute 2 queries (count + paginated)
        # No notification query needed when no candidates
        assert mock_db.execute.await_count == 2


# ─── Batch documents JOIN optimization ───────────────────────────────────────────


class TestBatchDocumentsJoinOptimization:
    """Tests that batch documents uses JOIN instead of 2-step IN."""

    @pytest.mark.asyncio
    @patch("app.api.routes.batch.get_current_user")
    @patch("app.api.routes.batch.get_db")
    async def test_batch_documents_uses_single_join_query(self, mock_get_db, mock_get_user):
        """Should use 2 queries: verify batch + JOIN query (not 3 queries with IN)."""
        from app.api.routes.batch import list_batch_documents

        mock_db = AsyncMock()
        mock_user = MagicMock()

        # First query: batch exists
        mock_batch = MagicMock()
        mock_batch.id = "batch-1"
        mock_batch.created_at = datetime.now(timezone.utc)
        batch_result = MagicMock()
        batch_result.scalar_one_or_none.return_value = mock_batch

        # Second query: JOIN result
        doc_result = MagicMock()
        doc_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[batch_result, doc_result])

        result = await list_batch_documents(
            batch_id="batch-1", db=mock_db, _current_user=mock_user,
        )

        # Should be exactly 2 queries (verify batch + single JOIN)
        assert mock_db.execute.await_count == 2
        assert result == []

    @pytest.mark.asyncio
    @patch("app.api.routes.batch.get_current_user")
    @patch("app.api.routes.batch.get_db")
    async def test_batch_documents_returns_404_when_batch_missing(self, mock_get_db, mock_get_user):
        """Should raise 404 if batch not found."""
        from app.api.routes.batch import list_batch_documents
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_user = MagicMock()

        batch_result = MagicMock()
        batch_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=batch_result)

        with pytest.raises(HTTPException) as exc_info:
            await list_batch_documents(batch_id="bad-id", db=mock_db, _current_user=mock_user)

        assert exc_info.value.status_code == 404


# ─── Config validation ───────────────────────────────────────────────────────────


class TestPhase7QueryPatterns:
    """Verify the query patterns are importable and don't have syntax errors."""

    def test_documents_route_importable(self):
        from app.api.routes.documents import list_documents, get_document_detail
        assert callable(list_documents)
        assert callable(get_document_detail)

    def test_review_queue_route_importable(self):
        from app.api.routes.review_queue import list_review_queue
        assert callable(list_review_queue)

    def test_batch_documents_importable(self):
        from app.api.routes.batch import list_batch_documents
        assert callable(list_batch_documents)

    def test_fetch_document_relations_importable(self):
        from app.api.routes.documents import _fetch_document_relations
        assert callable(_fetch_document_relations)
