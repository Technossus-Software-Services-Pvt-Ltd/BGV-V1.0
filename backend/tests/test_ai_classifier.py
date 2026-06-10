"""Tests for app.services.ai.classifier and ollama_client modules."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai.classifier import AIClassifier, ClassificationResult, OwnershipExtractionResult
from app.services.ai.ollama_client import OllamaClient, OllamaResponse
from app.models.enums import DocumentType


class TestOllamaResponse:
    def test_successful_response(self):
        resp = OllamaResponse(content="hello", model="llama3", duration_ms=100)
        assert resp.is_successful is True

    def test_failed_response_with_error(self):
        resp = OllamaResponse(content="", model="llama3", error="timeout")
        assert resp.is_successful is False

    def test_failed_response_empty_content(self):
        resp = OllamaResponse(content="  ", model="llama3")
        assert resp.is_successful is False


class TestClassificationResult:
    def test_successful_result(self):
        r = ClassificationResult(
            document_type=DocumentType.PAN_CARD.value,
            confidence=0.95,
            reasoning="Detected PAN format",
        )
        assert r.is_successful is True

    def test_failed_result_with_error(self):
        r = ClassificationResult(
            document_type=DocumentType.UNKNOWN.value,
            confidence=0.0,
            reasoning="Failed",
            error="timeout",
        )
        assert r.is_successful is False

    def test_failed_result_invalid_type(self):
        r = ClassificationResult(
            document_type="not_a_valid_type",
            confidence=0.9,
            reasoning="test",
        )
        assert r.is_successful is False


class TestAIClassifier:
    @pytest.mark.asyncio
    async def test_classify_insufficient_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.classify_document("hi", 0.9, 1)
        assert result.document_type == DocumentType.UNKNOWN.value
        assert result.error == "Insufficient text"

    @pytest.mark.asyncio
    async def test_classify_empty_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.classify_document("", 0.0, 0)
        assert result.document_type == DocumentType.UNKNOWN.value

    @pytest.mark.asyncio
    async def test_classify_successful(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=OllamaResponse(
            content='{"document_type": "pan_card", "confidence": 0.95, "reasoning": "PAN format detected", "key_identifiers": ["BSPPS1234K"]}',
            model="llama3",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=500,
        ))
        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document(
            "INCOME TAX DEPARTMENT GOVT OF INDIA PAN BSPPS1234K Name: Priya Sharma",
            0.92,
            15,
        )
        assert result.document_type == "pan_card"
        assert result.confidence == 0.95
        assert result.model_used == "llama3"

    @pytest.mark.asyncio
    async def test_classify_ollama_failure(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=OllamaResponse(
            content="",
            model="llama3",
            error="Connection refused",
        ))
        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document(
            "Some document text with enough words to pass the threshold",
            0.8,
            10,
        )
        assert result.document_type == DocumentType.UNKNOWN.value
        assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_classify_truncates_long_text(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=OllamaResponse(
            content='{"document_type": "aadhaar_card", "confidence": 0.8, "reasoning": "test"}',
            model="llama3",
            duration_ms=100,
        ))
        classifier = AIClassifier(client=mock_client)
        long_text = "word " * 1000  # > 3000 chars
        result = await classifier.classify_document(long_text, 0.9, 1000)
        # Verify it was called (text truncated internally)
        mock_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_ownership_empty_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.extract_ownership("", "pan_card")
        assert result.error == "No OCR text provided"

    @pytest.mark.asyncio
    async def test_classify_uses_zero_temperature(self):
        """Verify classification uses temperature=0.0 for deterministic output."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=OllamaResponse(
            content='{"document_type": "pan_card", "confidence": 0.9, "reasoning": "test"}',
            model="llama3",
            duration_ms=100,
        ))
        classifier = AIClassifier(client=mock_client)
        await classifier.classify_document("Some text with enough words for classification", 0.9, 8)
        mock_client.generate.assert_called_once()
        call_kwargs = mock_client.generate.call_args
        assert call_kwargs[1]["temperature"] == 0.0 or call_kwargs[0][1] == 0.0

    @pytest.mark.asyncio
    async def test_extract_ownership_uses_zero_temperature(self):
        """Verify ownership extraction uses temperature=0.0 for deterministic output."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=OllamaResponse(
            content='{"holder_name": "Test", "confidence": 0.8}',
            model="llama3",
            duration_ms=100,
        ))
        classifier = AIClassifier(client=mock_client)
        await classifier.extract_ownership("Some OCR text for ownership", "pan_card")
        mock_client.generate.assert_called_once()
        call_kwargs = mock_client.generate.call_args
        assert call_kwargs[1]["temperature"] == 0.0 or call_kwargs[0][1] == 0.0


class TestOllamaClient:
    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        import httpx
        client = OllamaClient()
        with patch.object(client, '_request_with_retry', side_effect=httpx.ConnectError("refused")):
            result = await client.generate("test prompt")
            assert result.is_successful is False
            assert "Cannot connect" in result.error

    @pytest.mark.asyncio
    async def test_generate_timeout_error(self):
        import httpx
        client = OllamaClient()
        with patch.object(client, '_request_with_retry', side_effect=httpx.TimeoutException("timed out")):
            result = await client.generate("test prompt")
            assert result.is_successful is False
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_generate_http_error(self):
        import httpx
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        with patch.object(client, '_request_with_retry', side_effect=httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)):
            result = await client.generate("test prompt")
            assert result.is_successful is False
            assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_generate_success(self):
        import httpx
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": '{"document_type": "pan_card"}',
            "model": "llama3",
            "prompt_eval_count": 50,
            "eval_count": 30,
        }
        with patch.object(client, '_request_with_retry', return_value=mock_response):
            result = await client.generate("test prompt")
            assert result.is_successful is True
            assert result.content == '{"document_type": "pan_card"}'
