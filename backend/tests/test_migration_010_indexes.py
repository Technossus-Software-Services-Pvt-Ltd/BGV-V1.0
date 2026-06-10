"""Tests for migration 010: performance indexes.

Verifies that:
1. The migration creates all expected indexes
2. The downgrade removes all indexes cleanly
3. Index names follow the project naming conventions
"""

import pytest
from unittest.mock import patch, MagicMock, call


class TestPerformanceIndexesMigration:
    """Verify the 010_performance_indexes migration structure."""

    def _import_migration(self):
        """Import the migration module."""
        import importlib.util
        import os

        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "alembic", "versions", "010_add_performance_indexes.py",
        )
        spec = importlib.util.spec_from_file_location("migration_010", migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_chain(self):
        """Migration should follow the correct revision chain."""
        migration = self._import_migration()
        assert migration.revision == "010_performance_indexes"
        assert migration.down_revision == "009_parent_document_id"

    @patch("alembic.op.create_index")
    def test_upgrade_creates_all_indexes(self, mock_create_index):
        """Upgrade should create exactly 8 compound indexes."""
        migration = self._import_migration()
        migration.upgrade()

        assert mock_create_index.call_count == 8

        # Verify each index by name
        index_names = [c[0][0] for c in mock_create_index.call_args_list]
        assert "ix_documents_candidate_id_created_at" in index_names
        assert "ix_documents_processing_status_created_at" in index_names
        assert "ix_ai_classifications_document_id_confidence" in index_names
        assert "ix_validation_results_document_id_score" in index_names
        assert "ix_batch_import_candidates_batch_status" in index_names
        assert "ix_batch_logs_batch_import_id_created_at" in index_names
        assert "ix_processing_events_document_id_created_at" in index_names
        assert "ix_notification_logs_candidate_id_created_at" in index_names

    @patch("alembic.op.create_index")
    def test_upgrade_uses_correct_tables(self, mock_create_index):
        """Each index should target the correct table."""
        migration = self._import_migration()
        migration.upgrade()

        # Build map: index_name -> table
        calls = mock_create_index.call_args_list
        index_table_map = {c[0][0]: c[0][1] for c in calls}

        assert index_table_map["ix_documents_candidate_id_created_at"] == "documents"
        assert index_table_map["ix_documents_processing_status_created_at"] == "documents"
        assert index_table_map["ix_ai_classifications_document_id_confidence"] == "ai_classifications"
        assert index_table_map["ix_validation_results_document_id_score"] == "validation_results"
        assert index_table_map["ix_batch_import_candidates_batch_status"] == "batch_import_candidates"
        assert index_table_map["ix_batch_logs_batch_import_id_created_at"] == "batch_logs"
        assert index_table_map["ix_processing_events_document_id_created_at"] == "processing_events"
        assert index_table_map["ix_notification_logs_candidate_id_created_at"] == "notification_logs"

    @patch("alembic.op.create_index")
    def test_upgrade_uses_correct_columns(self, mock_create_index):
        """Each index should use the correct column combination."""
        migration = self._import_migration()
        migration.upgrade()

        calls = mock_create_index.call_args_list
        index_columns_map = {c[0][0]: c[0][2] for c in calls}

        assert index_columns_map["ix_documents_candidate_id_created_at"] == ["candidate_id", "created_at"]
        assert index_columns_map["ix_documents_processing_status_created_at"] == ["processing_status", "created_at"]
        assert index_columns_map["ix_ai_classifications_document_id_confidence"] == ["document_id", "confidence_score"]
        assert index_columns_map["ix_validation_results_document_id_score"] == ["document_id", "ownership_score"]
        assert index_columns_map["ix_batch_import_candidates_batch_status"] == ["batch_import_id", "status"]
        assert index_columns_map["ix_batch_logs_batch_import_id_created_at"] == ["batch_import_id", "created_at"]
        assert index_columns_map["ix_processing_events_document_id_created_at"] == ["document_id", "created_at"]
        assert index_columns_map["ix_notification_logs_candidate_id_created_at"] == ["candidate_id", "created_at"]

    @patch("alembic.op.drop_index")
    def test_downgrade_removes_all_indexes(self, mock_drop_index):
        """Downgrade should drop all 8 indexes."""
        migration = self._import_migration()
        migration.downgrade()

        assert mock_drop_index.call_count == 8

        # Verify correct table_name kwargs
        dropped = {c[0][0]: c[1]["table_name"] for c in mock_drop_index.call_args_list}
        assert dropped["ix_documents_candidate_id_created_at"] == "documents"
        assert dropped["ix_documents_processing_status_created_at"] == "documents"
        assert dropped["ix_ai_classifications_document_id_confidence"] == "ai_classifications"
        assert dropped["ix_validation_results_document_id_score"] == "validation_results"
        assert dropped["ix_batch_import_candidates_batch_status"] == "batch_import_candidates"
        assert dropped["ix_batch_logs_batch_import_id_created_at"] == "batch_logs"
        assert dropped["ix_processing_events_document_id_created_at"] == "processing_events"
        assert dropped["ix_notification_logs_candidate_id_created_at"] == "notification_logs"
