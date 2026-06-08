import json
import time
from typing import Optional
from dataclasses import dataclass, field

from app.services.ai.ollama_client import OllamaClient
from app.services.ai.prompts import CLASSIFICATION_PROMPT, OWNERSHIP_EXTRACTION_PROMPT
from app.models.enums import DocumentType
from app.core.logging import get_logger

logger = get_logger("ai.classifier")

VALID_DOCUMENT_TYPES = {dt.value for dt in DocumentType}


@dataclass
class ClassificationResult:
    document_type: str
    confidence: float
    reasoning: str
    extracted_name: Optional[str] = None
    extracted_dob: Optional[str] = None
    extracted_gender: Optional[str] = None
    extracted_id_number: Optional[str] = None
    key_identifiers: list = field(default_factory=list)
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    processing_duration_ms: int = 0
    error: Optional[str] = None

    @property
    def is_successful(self) -> bool:
        return self.error is None and self.document_type in VALID_DOCUMENT_TYPES


@dataclass
class OwnershipExtractionResult:
    holder_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    parent_name: Optional[str] = None
    id_numbers: dict = field(default_factory=dict)
    address: Optional[str] = None
    confidence: float = 0.0
    error: Optional[str] = None


class AIClassifier:
    """AI-powered document classification using local LLM via Ollama."""

    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()

    async def classify_document(
        self,
        ocr_text: str,
        ocr_confidence: float,
        word_count: int,
    ) -> ClassificationResult:
        start_time = time.time()
        logger.info("classification_start", word_count=word_count, ocr_confidence=f"{ocr_confidence:.2f}")

        if not ocr_text or word_count < 3:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                reasoning="Insufficient OCR text for classification",
                processing_duration_ms=int((time.time() - start_time) * 1000),
                error="Insufficient text",
            )

        # Truncate very long texts to fit context window
        truncated_text = ocr_text[:3000] if len(ocr_text) > 3000 else ocr_text

        prompt = CLASSIFICATION_PROMPT.format(
            ocr_text=truncated_text,
            ocr_confidence=f"{ocr_confidence:.2f}",
            word_count=word_count,
        )

        response = await self.client.generate(prompt, temperature=0.1)

        if not response.is_successful:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                reasoning="AI classification failed",
                model_used=response.model,
                processing_duration_ms=response.duration_ms,
                error=response.error,
            )

        # Parse JSON response
        result = self._parse_classification_response(response.content)
        result.model_used = response.model
        result.prompt_tokens = response.prompt_tokens
        result.completion_tokens = response.completion_tokens
        result.processing_duration_ms = response.duration_ms

        logger.info("classification_complete", document_type=result.document_type, confidence=f"{result.confidence:.2f}", duration_ms=response.duration_ms)
        return result

    async def extract_ownership(
        self,
        ocr_text: str,
        document_type: str,
    ) -> OwnershipExtractionResult:
        if not ocr_text:
            return OwnershipExtractionResult(error="No OCR text provided")

        truncated_text = ocr_text[:2000] if len(ocr_text) > 2000 else ocr_text

        prompt = OWNERSHIP_EXTRACTION_PROMPT.format(
            document_type=document_type,
            ocr_text=truncated_text,
        )

        response = await self.client.generate(prompt, temperature=0.1)

        if not response.is_successful:
            return OwnershipExtractionResult(error=response.error)

        return self._parse_ownership_response(response.content)

    def _parse_classification_response(self, content: str) -> ClassificationResult:
        try:
            # Try to extract JSON from response
            json_str = self._extract_json(content)
            data = json.loads(json_str)

            doc_type = data.get("document_type", "unknown")
            if doc_type not in VALID_DOCUMENT_TYPES:
                doc_type = DocumentType.UNKNOWN.value

            return ClassificationResult(
                document_type=doc_type,
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
                reasoning=data.get("reasoning", "No reasoning provided"),
                extracted_name=data.get("extracted_name"),
                extracted_dob=data.get("extracted_dob"),
                extracted_gender=data.get("extracted_gender"),
                extracted_id_number=data.get("extracted_id_number"),
                key_identifiers=data.get("key_identifiers", []),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("ai_response_parse_failed", error=str(e), content=content[:200])
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                reasoning=f"Failed to parse AI response: {str(e)}",
                error=f"Parse error: {str(e)}",
            )

    def _parse_ownership_response(self, content: str) -> OwnershipExtractionResult:
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)

            return OwnershipExtractionResult(
                holder_name=data.get("holder_name"),
                date_of_birth=data.get("date_of_birth"),
                parent_name=data.get("parent_name"),
                id_numbers=data.get("id_numbers", {}),
                address=data.get("address"),
                confidence=float(data.get("confidence", 0.5)),
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("ownership_parse_failed", error=str(e))
            return OwnershipExtractionResult(error=f"Parse error: {str(e)}")

    def _extract_json(self, content: str) -> str:
        content = content.strip()

        # If it starts with {, try direct parse
        if content.startswith("{"):
            # Find the matching closing brace
            brace_count = 0
            for i, ch in enumerate(content):
                if ch == "{":
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        return content[:i + 1]
            return content

        # Try to find JSON in markdown code blocks
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return content[start:end].strip()

        if "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            return content[start:end].strip()

        # Last resort: find first { and last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            return content[start:end + 1]

        raise ValueError("No JSON found in response")
