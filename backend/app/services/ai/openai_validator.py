import time
import json
import base64
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ai.openai_validator")


@dataclass
class OpenAIOwnershipResult:
    """Result from OpenAI-based ownership validation."""
    ownership_confirmed: bool = False
    confidence_score: float = 0.0
    validation_status: str = "unmatched"
    reasoning: str = ""
    key_evidence: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    # Extracted owner details from document (for candidate comparison)
    extracted_owner_name: Optional[str] = None
    extracted_owner_dob: Optional[str] = None
    extracted_id_number: Optional[str] = None
    # Name comparison result (candidate vs OpenAI-extracted owner)
    name_match_score: Optional[float] = None
    name_match_confirmed: Optional[bool] = None
    # API metadata
    model_used: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: Optional[str] = None


SYSTEM_PROMPT = """You are a document ownership verification expert for Background Verification (BGV).

Your task is to:
1. Extract the document owner's details (name, DOB, ID numbers) directly from the document
2. Determine if the document belongs to the specified candidate

Important Guidelines:
- Extract the EXACT name as it appears on the document (the document owner)
- Consider OCR errors, typos, and variations in name spelling
- Indian names may have prefixes (Mr, Dr, Shri, Smt, Kumari) and suffixes (Ji, Sahab)
- Names may be reordered (first name/last name)
- Dates may appear in multiple formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.)
- Look for contextual clues beyond exact matches
- Assess confidence based on available evidence
- Flag concerns or ambiguities
- Be conservative: if unsure, reject ownership

Respond with structured JSON analysis including the extracted owner details."""


class OpenAIOwnershipValidator:
    """OpenAI-based ownership validation as fallback mechanism.

    Only called when existing rule-based validation fails or has low confidence.
    """

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout = settings.openai_timeout_seconds
        self.max_retries = settings.openai_max_retries

    async def validate(
        self,
        candidate_name: str,
        candidate_dob: Optional[str],
        candidate_gender: Optional[str],
        document_type: str,
        ocr_text: str,
        extracted_name: Optional[str],
        extracted_dob: Optional[str],
        extracted_gender: Optional[str],
        rule_based_score: float,
        rule_based_reasoning: str,
        document_file_path: Optional[str] = None,
        document_mime_type: Optional[str] = None,
    ) -> OpenAIOwnershipResult:
        """Validate document ownership using OpenAI API with vision support.

        Args:
            candidate_name: Name of the candidate to verify against
            candidate_dob: Candidate's date of birth
            candidate_gender: Candidate's gender
            document_type: Type of document being validated
            ocr_text: Full OCR text extracted from document (supplementary)
            extracted_name: Name extracted by AI classification
            extracted_dob: DOB extracted by AI classification
            extracted_gender: Gender extracted by AI classification
            rule_based_score: Score from existing rule-based validation
            rule_based_reasoning: Reasoning from existing validation
            document_file_path: Path to the actual document file on disk
            document_mime_type: MIME type of the document file

        Returns:
            OpenAIOwnershipResult with validation outcome
        """
        start_time = time.time()

        logger.info(
            "openai_validation_start",
            candidate_name=candidate_name,
            document_type=document_type,
            rule_based_score=rule_based_score,
        )

        try:
            messages = self._build_messages(
                candidate_name=candidate_name,
                candidate_dob=candidate_dob,
                candidate_gender=candidate_gender,
                document_type=document_type,
                ocr_text=ocr_text,
                extracted_name=extracted_name,
                extracted_dob=extracted_dob,
                extracted_gender=extracted_gender,
                rule_based_score=rule_based_score,
                rule_based_reasoning=rule_based_reasoning,
                document_file_path=document_file_path,
                document_mime_type=document_mime_type,
            )

            response_data = await self._call_openai(messages)
            result = self._parse_response(response_data, start_time)

            logger.info(
                "openai_validation_complete",
                ownership_confirmed=result.ownership_confirmed,
                confidence=result.confidence_score,
                tokens=result.total_tokens,
                cost_usd=result.cost_usd,
                duration_ms=result.duration_ms,
            )

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("openai_validation_error", error=str(e), duration_ms=duration_ms)
            return OpenAIOwnershipResult(
                ownership_confirmed=False,
                confidence_score=0.0,
                validation_status="error",
                reasoning=f"OpenAI validation failed: {str(e)}",
                model_used=self.model,
                duration_ms=duration_ms,
                error=str(e),
            )

    def _build_messages(self, **kwargs) -> list:
        """Build the system + user messages for OpenAI API with vision support."""
        ocr_text = (kwargs["ocr_text"] or "")[:2000]

        user_text = f"""CANDIDATE INFORMATION (the person we need to verify):
- Name: {kwargs['candidate_name']}
- Date of Birth: {kwargs['candidate_dob'] or 'Not provided'}
- Gender: {kwargs['candidate_gender'] or 'Not provided'}

DOCUMENT INFORMATION:
- Document Type: {kwargs['document_type']}

OCR EXTRACTED TEXT (from the document, for reference):
{ocr_text}

TASK:
1. EXTRACT the document owner's details directly from the document image:
   - Owner's full name as printed on the document
   - Owner's date of birth (if visible)
   - Any ID numbers visible on the document
2. COMPARE the extracted owner details against the candidate information above
3. DETERMINE if this document belongs to the candidate

Respond in this EXACT JSON format:
{{
    "extracted_owner_name": "<the name printed on the document, exactly as it appears>",
    "extracted_owner_dob": "<DOB from document if visible, or null>",
    "extracted_id_number": "<any ID number from document if visible, or null>",
    "ownership_confirmed": <true or false>,
    "confidence_score": <float between 0.0 and 1.0>,
    "reasoning": "<detailed explanation: how the extracted owner details compare to the candidate>",
    "key_evidence": ["<list of evidence supporting your decision>"],
    "concerns": ["<list of concerns or ambiguities, empty array if none>"]
}}

IMPORTANT:
- Return ONLY valid JSON (no markdown, no extra text)
- The extracted_owner_name must be the ACTUAL name from the document, not the candidate name
- Base your ownership decision on comparing candidate name vs document owner name
- Be conservative: if unsure, set ownership_confirmed=false and flag concerns
- Consider name variations, reordering, and OCR artifacts common in Indian documents
- USE THE DOCUMENT IMAGE as your PRIMARY source of truth"""

        # Build user content with image if available
        document_file_path = kwargs.get("document_file_path")
        document_mime_type = kwargs.get("document_mime_type")

        user_content = self._build_user_content(user_text, document_file_path, document_mime_type)

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def _build_user_content(self, user_text: str, document_file_path: Optional[str], document_mime_type: Optional[str]):
        """Build user message content, including document image if available."""
        if not document_file_path:
            return user_text

        file_path = Path(document_file_path)
        if not file_path.exists():
            logger.warning("openai_document_not_found", path=document_file_path)
            return user_text

        # Determine if we can send as image
        mime_type = document_mime_type or ""
        supported_image_types = ("image/jpeg", "image/png", "image/webp", "image/gif")

        if mime_type.lower() in supported_image_types:
            return self._build_image_content(user_text, file_path, mime_type)
        elif mime_type.lower() == "application/pdf":
            # For PDFs, try to find page images (rendered pages)
            return self._build_pdf_content(user_text, file_path)
        else:
            logger.info("openai_unsupported_mime", mime_type=mime_type)
            return user_text

    def _build_image_content(self, user_text: str, file_path: Path, mime_type: str) -> list:
        """Build multimodal content with document image."""
        try:
            image_data = file_path.read_bytes()
            # Limit to 20MB for API
            if len(image_data) > 20 * 1024 * 1024:
                logger.warning("openai_image_too_large", size=len(image_data))
                return user_text

            base64_image = base64.b64encode(image_data).decode("utf-8")
            media_type = mime_type.lower()

            return [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{base64_image}",
                        "detail": "high",
                    },
                },
            ]
        except Exception as e:
            logger.error("openai_image_encode_error", error=str(e))
            return user_text

    def _build_pdf_content(self, user_text: str, file_path: Path) -> list:
        """For PDFs, look for rendered page images in the same directory."""
        # Check if page images exist (rendered during OCR processing)
        parent_dir = file_path.parent
        page_images = sorted(parent_dir.glob("page_*.png")) + sorted(parent_dir.glob("page_*.jpg"))

        if not page_images:
            # No page images found, fall back to text-only
            logger.info("openai_no_pdf_pages", path=str(file_path))
            return user_text

        # Send up to 3 pages to keep token usage reasonable
        content_parts = [{"type": "text", "text": user_text}]

        for page_img in page_images[:3]:
            try:
                image_data = page_img.read_bytes()
                if len(image_data) > 20 * 1024 * 1024:
                    continue
                base64_image = base64.b64encode(image_data).decode("utf-8")
                suffix = page_img.suffix.lower()
                media_type = "image/png" if suffix == ".png" else "image/jpeg"
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{base64_image}",
                        "detail": "high",
                    },
                })
            except Exception as e:
                logger.warning("openai_page_encode_error", page=str(page_img), error=str(e))

        if len(content_parts) == 1:
            # No images were successfully added
            return user_text

        return content_parts

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _call_openai(self, messages: list) -> dict:
        """Call OpenAI API with retry logic."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 800,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            return response.json()

    def _parse_response(self, response_data: dict, start_time: float) -> OpenAIOwnershipResult:
        """Parse OpenAI API response into structured result."""
        duration_ms = int((time.time() - start_time) * 1000)

        usage = response_data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self._calculate_cost(prompt_tokens, completion_tokens)

        # Extract content from response
        choices = response_data.get("choices", [])
        if not choices:
            return OpenAIOwnershipResult(
                reasoning="No response from OpenAI",
                model_used=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                error="Empty response",
            )

        content = choices[0].get("message", {}).get("content", "")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            return OpenAIOwnershipResult(
                reasoning=f"Failed to parse OpenAI response: {content[:200]}",
                model_used=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                error=f"JSON parse error: {str(e)}",
            )

        ownership_confirmed = bool(parsed.get("ownership_confirmed", False))
        confidence_score = float(parsed.get("confidence_score", 0.0))
        # Clamp confidence to [0, 1]
        confidence_score = max(0.0, min(1.0, confidence_score))

        # Extract owner details from OpenAI response
        extracted_owner_name = parsed.get("extracted_owner_name") or None
        extracted_owner_dob = parsed.get("extracted_owner_dob") or None
        extracted_id_number = parsed.get("extracted_id_number") or None

        # Determine validation status from confidence
        if ownership_confirmed and confidence_score >= 0.8:
            validation_status = "matched"
        elif ownership_confirmed and confidence_score >= 0.5:
            validation_status = "partial_match"
        else:
            validation_status = "unmatched"

        return OpenAIOwnershipResult(
            ownership_confirmed=ownership_confirmed,
            confidence_score=confidence_score,
            validation_status=validation_status,
            reasoning=parsed.get("reasoning", ""),
            key_evidence=parsed.get("key_evidence", []),
            concerns=parsed.get("concerns", []),
            extracted_owner_name=extracted_owner_name,
            extracted_owner_dob=extracted_owner_dob,
            extracted_id_number=extracted_id_number,
            model_used=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
        )

    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate API cost based on gpt-4o-mini pricing."""
        # gpt-4o-mini pricing (as of 2024)
        prompt_cost = (prompt_tokens / 1_000_000) * 0.15
        completion_cost = (completion_tokens / 1_000_000) * 0.60
        return prompt_cost + completion_cost
