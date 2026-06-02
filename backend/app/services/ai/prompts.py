from app.models.enums import DocumentType

CLASSIFICATION_PROMPT = """You are a document classification expert for an Indian Background Verification system.

Given the OCR-extracted text from a document, classify it into EXACTLY ONE of the following categories:
# Identity Documents
- aadhaar: Aadhaar card (12-digit UID, UIDAI, Government of India identity)
- pan_card: PAN Card (Permanent Account Number, Income Tax Department)
- passport: Passport (Republic of India, passport number, nationality)
- driving_license: Driving License (Transport Department, DL number, vehicle class)
- voter_id: Voter ID / EPIC (Election Commission, electoral photo identity)
- police_verification: Police Verification Certificate

# Education Documents
- marksheet_10th: 10th Marksheet / SSC Marksheet
- marksheet_12th: 12th Marksheet / HSC Marksheet
- certificate_diploma: Diploma Completion / Diploma Certificate
- marksheet_diploma: Diploma Semester / Final Marksheet
- certificate_degree: Degree Certificate (Bachelor's, Master's, Engineering, MBA, MCA, etc.)
- marksheet_degree: Degree Semester Marksheet / Consolidated Marksheet / Transcript

# Employment Documents
- payslip: Salary Slip / Payslip (earnings, deductions, net pay)
- experience_letter: Experience Letter / Relieving Letter / Employment Certificate

# Financial Documents
- bank_statement: Bank Statement (account details, transactions)

# Other Documents
- address_proof: Address Proof (utility bill, rent agreement, etc.)
- photograph: Photograph only (no text document)
- unknown: Cannot determine document type

INSTRUCTIONS:
1. Analyze ONLY the OCR text content provided
2. Do NOT use filename or any external context
3. Look for key identifiers, headers, logos text, government department names
4. Extract the person's name if visible
5. Extract date of birth if visible
6. Extract gender if visible (Male, Female, or Transgender)
7. Extract any ID numbers (PAN, Aadhaar last 4, DL number, etc.)
8. Provide confidence score (0.0 to 1.0)
9. Explain your reasoning briefly

OCR TEXT:
{ocr_text}

OCR CONFIDENCE: {ocr_confidence}
WORD COUNT: {word_count}

Respond in this EXACT JSON format:
{{
    "document_type": "<type from list above>",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<brief explanation of why this classification>",
    "extracted_name": "<person name if found, null otherwise>",
    "extracted_dob": "<date of birth if found in DD/MM/YYYY or similar, null otherwise>",
    "extracted_gender": "<Male, Female, or Transgender if found, null otherwise>",
    "extracted_id_number": "<primary ID number found, null otherwise>",
    "key_identifiers": ["<list of key phrases that led to classification>"]
}}

IMPORTANT: Return ONLY valid JSON. No additional text."""


OWNERSHIP_EXTRACTION_PROMPT = """You are an identity extraction expert for Indian documents.

Given the OCR text from a classified document, extract ownership information.

Document Type: {document_type}
OCR Text: {ocr_text}

Extract the following information:
1. Full name of the document holder
2. Date of birth (if present)
3. Father's/Mother's name (if present)
4. Any ID numbers (PAN, Aadhaar partial, DL number, passport number)
5. Address (if present)

Respond in this EXACT JSON format:
{{
    "holder_name": "<full name or null>",
    "date_of_birth": "<DOB in DD/MM/YYYY or null>",
    "parent_name": "<father/mother name or null>",
    "id_numbers": {{
        "pan": "<PAN number or null>",
        "aadhaar_last_four": "<last 4 digits or null>",
        "dl_number": "<DL number or null>",
        "passport_number": "<passport number or null>"
    }},
    "address": "<address or null>",
    "confidence": <float 0.0-1.0>
}}

IMPORTANT: Return ONLY valid JSON. No additional text."""
