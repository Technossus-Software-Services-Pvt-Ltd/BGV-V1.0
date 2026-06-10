"""Tests for Phase 6: Celery task queue and task dispatcher."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


# ─── TaskDispatcher tests ────────────────────────────────────────────────────────


class TestTaskDispatcherCeleryMode:
    """Tests for TaskDispatcher when Celery is enabled."""

    @patch("app.services.task_dispatcher.settings")
    def test_using_celery_true_when_enabled(self, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = True
        dispatcher = TaskDispatcher()
        assert dispatcher.using_celery is True

    @patch("app.services.task_dispatcher.settings")
    def test_using_celery_false_when_disabled(self, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = False
        dispatcher = TaskDispatcher()
        assert dispatcher.using_celery is False

    @patch("app.services.task_dispatcher.settings")
    @patch("app.tasks.document.process_document")
    def test_dispatch_document_to_celery(self, mock_task, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = True

        mock_result = MagicMock()
        mock_result.id = "celery-task-123"
        mock_task.delay.return_value = mock_result

        dispatcher = TaskDispatcher()
        task_id = dispatcher.dispatch_document_processing("doc-001")

        assert task_id == "celery-task-123"
        mock_task.delay.assert_called_once_with("doc-001")

    @patch("app.services.task_dispatcher.settings")
    @patch("app.tasks.batch.process_batch")
    def test_dispatch_batch_to_celery(self, mock_task, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = True

        mock_result = MagicMock()
        mock_result.id = "celery-batch-456"
        mock_task.delay.return_value = mock_result

        dispatcher = TaskDispatcher()
        task_id = dispatcher.dispatch_batch_processing("batch-001")

        assert task_id == "celery-batch-456"
        mock_task.delay.assert_called_once_with("batch-001")

    @patch("app.services.task_dispatcher.settings")
    @patch("app.tasks.batch.retry_candidate")
    def test_dispatch_retry_to_celery(self, mock_task, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = True

        mock_result = MagicMock()
        mock_result.id = "celery-retry-789"
        mock_task.delay.return_value = mock_result

        dispatcher = TaskDispatcher()
        task_id = dispatcher.dispatch_retry_candidate("batch-001", "cand-001")

        assert task_id == "celery-retry-789"
        mock_task.delay.assert_called_once_with("batch-001", "cand-001")

    @patch("app.services.task_dispatcher.settings")
    @patch("app.tasks.notification.send_notifications")
    def test_dispatch_notifications_to_celery(self, mock_task, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = True

        mock_result = MagicMock()
        mock_result.id = "celery-notify-111"
        mock_task.delay.return_value = mock_result

        dispatcher = TaskDispatcher()
        log_ids = ["log-1", "log-2"]
        task_id = dispatcher.dispatch_notifications(log_ids)

        assert task_id == "celery-notify-111"
        mock_task.delay.assert_called_once_with(log_ids)


class TestTaskDispatcherInProcessMode:
    """Tests for TaskDispatcher when Celery is disabled (fallback)."""

    @patch("app.services.task_dispatcher.settings")
    @patch("app.services.task_dispatcher.task_manager")
    def test_dispatch_document_in_process(self, mock_tm, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = False
        mock_tm.submit.return_value = MagicMock()

        dispatcher = TaskDispatcher()
        result = dispatcher.dispatch_document_processing("doc-002")

        assert result is None  # In-process returns None (no celery task ID)
        mock_tm.submit.assert_called_once()

    @patch("app.services.task_dispatcher.settings")
    @patch("app.services.task_dispatcher.task_manager")
    def test_dispatch_batch_in_process(self, mock_tm, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = False
        mock_tm.submit.return_value = MagicMock()

        dispatcher = TaskDispatcher()
        result = dispatcher.dispatch_batch_processing("batch-002")

        assert result is None
        mock_tm.submit.assert_called_once()

    @patch("app.services.task_dispatcher.settings")
    @patch("app.services.task_dispatcher.task_manager")
    def test_dispatch_notifications_in_process(self, mock_tm, mock_settings):
        from app.services.task_dispatcher import TaskDispatcher
        mock_settings.celery_enabled = False
        mock_tm.submit.return_value = MagicMock()

        dispatcher = TaskDispatcher()
        result = dispatcher.dispatch_notifications(["log-1"])

        assert result is None
        mock_tm.submit.assert_called_once()


# ─── Celery task definition tests ────────────────────────────────────────────────


class TestCeleryTaskDefinitions:
    """Verify Celery tasks are properly registered."""

    def test_document_task_registered(self):
        from app.tasks.document import process_document
        assert process_document.name == "app.tasks.document.process_document"

    def test_batch_task_registered(self):
        from app.tasks.batch import process_batch
        assert process_batch.name == "app.tasks.batch.process_batch"

    def test_retry_candidate_task_registered(self):
        from app.tasks.batch import retry_candidate
        assert retry_candidate.name == "app.tasks.batch.retry_candidate"

    def test_notification_task_registered(self):
        from app.tasks.notification import send_notifications
        assert send_notifications.name == "app.tasks.notification.send_notifications"


# ─── Celery app configuration tests ─────────────────────────────────────────────


class TestCeleryAppConfig:
    """Verify Celery app is configured correctly."""

    def test_celery_app_name(self):
        from app.celery_app import celery
        assert celery.main == "bgv_worker"

    def test_celery_task_serializer(self):
        from app.celery_app import celery
        assert celery.conf.task_serializer == "json"

    def test_celery_task_routes(self):
        from app.celery_app import celery
        routes = celery.conf.task_routes
        assert "app.tasks.document.*" in routes
        assert routes["app.tasks.document.*"] == {"queue": "bgv_documents"}
        assert "app.tasks.batch.*" in routes
        assert routes["app.tasks.batch.*"] == {"queue": "bgv_batches"}
        assert "app.tasks.notification.*" in routes
        assert routes["app.tasks.notification.*"] == {"queue": "bgv_notifications"}

    def test_celery_acks_late(self):
        from app.celery_app import celery
        assert celery.conf.task_acks_late is True


# ─── Config tests ────────────────────────────────────────────────────────────────


class TestPhase6Config:
    """Tests for Phase 6 config settings."""

    def test_celery_enabled_default_false(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.celery_enabled is False

    def test_celery_broker_url_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.celery_broker_url == "redis://localhost:6379/1"

    def test_celery_result_backend_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.celery_result_backend == "redis://localhost:6379/2"
