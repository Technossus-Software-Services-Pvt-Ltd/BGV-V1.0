import json
import time
from typing import Optional
from dataclasses import dataclass, field

from app.services.ai.ollama_client import OllamaClient
from app.services.ai.prompts import BROAD_CLASSIFICATION_PROMPT, SPECIFIC_CLASSIFICATION_PROMPTS, OWNERSHIP_EXTRACTION_PROMPT
from app.services.ai.sanitizer import sanitize_ocr_text, wrap_ocr_text_for_prompt, validate_classification_evidence
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
    gender: Optional[str] = None


class AIClassifier:
    """AI-powered document classification using local LLM via Ollama."""

    # Schema definitions for Ollama structured outputs
    BROAD_SCHEMA = {
        "type": "object",
        "properties": {
            "broad_group": {
                "type": "string",
                "enum": ["identity", "education", "employment", "financial", "address", "medical", "legal", "other"]
            },
            "confidence": {"type": "number"},
            "reasoning": {"type": "string"}
        },
        "required": ["broad_group", "confidence", "reasoning"]
    }

    SPECIFIC_SCHEMA = {
        "type": "object",
        "properties": {
            "document_type": {"type": "string"},
            "confidence": {"type": "number"}
        },
        "required": ["document_type", "confidence"]
    }

    OWNERSHIP_SCHEMA = {
        "type": "object",
        "properties": {
            "holder_name": {"type": "string"},
            "date_of_birth": {"type": "string"},
            "parent_name": {"type": "string"},
            "id_numbers": {
                "type": "object",
                "properties": {
                    "pan": {"type": "string"},
                    "aadhaar_last_four": {"type": "string"},
                    "dl_number": {"type": "string"},
                    "passport_number": {"type": "string"}
                },
                "required": ["pan", "aadhaar_last_four", "dl_number", "passport_number"]
            },
            "address": {"type": "string"},
            "gender": {"type": "string"},
            "confidence": {"type": "number"}
        },
        "required": ["holder_name", "date_of_birth", "parent_name", "id_numbers", "address", "gender", "confidence"]
    }

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

        # Truncate very long texts to fit context window (word-boundary aware)
        if len(ocr_text) > 3000:
            cut = ocr_text.rfind(" ", 0, 3000)
            truncated_text = ocr_text[:cut] if cut > 2400 else ocr_text[:3000]
        else:
            truncated_text = ocr_text

        # Sanitize OCR text to prevent prompt injection
        sanitized_text, was_injected = sanitize_ocr_text(truncated_text)
        if was_injected:
            logger.warning("prompt_injection_sanitized", word_count=word_count)

        # Wrap with boundary markers
        wrapped_text = wrap_ocr_text_for_prompt(sanitized_text)

        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Stage 1: Broad classification
        broad_prompt = BROAD_CLASSIFICATION_PROMPT.format(ocr_text=wrapped_text)
        broad_response = await self.client.generate(broad_prompt, temperature=0.0, format=self.BROAD_SCHEMA)

        if not broad_response.is_successful:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                reasoning="AI broad classification failed",
                model_used=broad_response.model,
                processing_duration_ms=broad_response.duration_ms,
                error=broad_response.error,
            )

        total_prompt_tokens += broad_response.prompt_tokens
        total_completion_tokens += broad_response.completion_tokens

        # Parse broad classification
        broad_group = "unknown"
        broad_reasoning = ""
        broad_confidence = 0.0
        doc_type = DocumentType.UNKNOWN.value
        spec_confidence = 1.0

        # Ownership extraction fields (might be extracted direct from single-stage or via Stage 3)
        extracted_name = None
        extracted_dob = None
        extracted_gender = None
        extracted_id_number = None

        try:
            broad_json = self._extract_json(broad_response.content)
            broad_data = json.loads(broad_json)

            # Check if this is a direct single-stage response (for backward compatibility or direct mock responses)
            if "document_type" in broad_data:
                doc_type = broad_data.get("document_type", "unknown")
                if doc_type == "relieving_letter":
                    doc_type = DocumentType.EXPERIENCE_LETTER.value
                if doc_type not in VALID_DOCUMENT_TYPES:
                    doc_type = DocumentType.UNKNOWN.value
                combined_confidence = float(broad_data.get("confidence", 0.5))
                broad_reasoning = broad_data.get("reasoning", "Direct classification")
                
                # Direct single-stage parsing of extracted fields
                extracted_name = broad_data.get("extracted_name")
                extracted_dob = broad_data.get("extracted_dob")
                extracted_gender = broad_data.get("extracted_gender")
                extracted_id_number = broad_data.get("extracted_id_number")
                
                broad_group = None
            else:
                broad_group = broad_data.get("broad_group", "unknown").lower()
                broad_reasoning = broad_data.get("reasoning", "")
                broad_confidence = float(broad_data.get("confidence", 0.0))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("ai_broad_response_parse_failed", error=str(e), content=broad_response.content[:200])
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN.value,
                confidence=0.0,
                reasoning=f"Failed to parse AI response: {str(e)}",
                error=f"Parse error: {str(e)}",
                model_used=broad_response.model,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                processing_duration_ms=int((time.time() - start_time) * 1000),
            )

        # Stage 2: Specific classification if we went through broad category step
        if broad_group is not None and broad_group in SPECIFIC_CLASSIFICATION_PROMPTS:
            specific_prompt = SPECIFIC_CLASSIFICATION_PROMPTS[broad_group].format(ocr_text=wrapped_text)
            specific_response = await self.client.generate(specific_prompt, temperature=0.0, format=self.SPECIFIC_SCHEMA)

            if not specific_response.is_successful:
                return ClassificationResult(
                    document_type=DocumentType.UNKNOWN.value,
                    confidence=0.0,
                    reasoning="AI specific classification failed",
                    model_used=specific_response.model,
                    processing_duration_ms=broad_response.duration_ms + specific_response.duration_ms,
                    error=specific_response.error,
                )

            total_prompt_tokens += specific_response.prompt_tokens
            total_completion_tokens += specific_response.completion_tokens

            # Parse specific classification
            try:
                spec_json = self._extract_json(specific_response.content)
                spec_data = json.loads(spec_json)
                doc_type = spec_data.get("document_type", "unknown")
                spec_confidence = float(spec_data.get("confidence", 0.0))
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning("ai_specific_response_parse_failed", error=str(e), content=specific_response.content[:200])
                return ClassificationResult(
                    document_type=DocumentType.UNKNOWN.value,
                    confidence=0.0,
                    reasoning=f"Failed to parse AI response: {str(e)}",
                    error=f"Parse error: {str(e)}",
                    model_used=specific_response.model,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    processing_duration_ms=int((time.time() - start_time) * 1000),
                )

            if doc_type == "relieving_letter":
                doc_type = DocumentType.EXPERIENCE_LETTER.value

            if doc_type not in VALID_DOCUMENT_TYPES:
                doc_type = DocumentType.UNKNOWN.value

            combined_confidence = min(1.0, broad_confidence * spec_confidence)

        # Layer 3: Post-classification evidence validation
        if doc_type != DocumentType.UNKNOWN.value:
            if not validate_classification_evidence(doc_type, truncated_text):
                logger.warning(
                    "classification_evidence_missing",
                    claimed_type=doc_type,
                    confidence=combined_confidence,
                )
                # Reduce confidence — don't override entirely, but flag it
                combined_confidence = min(combined_confidence, 0.4)
                broad_reasoning = (broad_reasoning or "") + " [WARNING: no supporting evidence in OCR text]"

        # Stage 3: Ownership Extraction (run conditionally if valid type and not direct single-stage response)
        if broad_group is not None and doc_type not in [DocumentType.UNKNOWN.value, "photograph"]:
            # Run extraction helper
            extraction_res = await self.extract_ownership(truncated_text, doc_type)
            if not extraction_res.error:
                extracted_name = extraction_res.holder_name
                extracted_dob = extraction_res.date_of_birth
                extracted_gender = extraction_res.gender
                
                # Extract primary ID number from dict
                id_nums = extraction_res.id_numbers or {}
                extracted_id_number = (
                    id_nums.get("pan") or 
                    id_nums.get("aadhaar_last_four") or 
                    id_nums.get("dl_number") or 
                    id_nums.get("passport_number")
                )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info("classification_complete", document_type=doc_type, confidence=f"{combined_confidence:.2f}", duration_ms=duration_ms)

        return ClassificationResult(
            document_type=doc_type,
            confidence=combined_confidence,
            reasoning=broad_reasoning or f"Classified as {doc_type}",
            extracted_name=extracted_name,
            extracted_dob=extracted_dob,
            extracted_gender=extracted_gender,
            extracted_id_number=extracted_id_number,
            key_identifiers=[],
            model_used=broad_response.model,
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            processing_duration_ms=duration_ms,
        )

    async def extract_ownership(
        self,
        ocr_text: str,
        document_type: str,
    ) -> OwnershipExtractionResult:
        if not ocr_text:
            return OwnershipExtractionResult(error="No OCR text provided")

        truncated_text = ocr_text[:2000] if len(ocr_text) > 2000 else ocr_text

        # Sanitize OCR text to prevent prompt injection
        sanitized_text, _ = sanitize_ocr_text(truncated_text)
        wrapped_text = wrap_ocr_text_for_prompt(sanitized_text)

        prompt = OWNERSHIP_EXTRACTION_PROMPT.format(
            document_type=document_type,
            ocr_text=wrapped_text,
        )

        response = await self.client.generate(prompt, temperature=0.0, format=self.OWNERSHIP_SCHEMA)

        if not response.is_successful:
            return OwnershipExtractionResult(error=response.error)

        return self._parse_ownership_response(response.content)

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
                gender=data.get("gender"),
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

        # Last resort: find first { and match balanced braces
        start = content.find("{")
        if start != -1:
            brace_count = 0
            for i in range(start, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        return content[start:i + 1]

        raise ValueError("No JSON found in response")
