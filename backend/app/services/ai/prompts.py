from app.models.enums import DocumentType

CLASSIFICATION_PROMPT = """You are a document classification expert for an Indian Background Verification system.

Given the OCR-extracted text from a document, classify it into EXACTLY ONE of the following categories:
- aadhaar: Classify as aadhaar only if OCR text contains strong Aadhaar-specific evidence.
Positive signals: Aadhaar, Aadhar, Unique Identification Authority of India, UIDAI, Government of India plus Aadhaar-specific content, 12-digit Aadhaar number usually grouped like 1234 5678 9012, VID, DOB or Year of Birth, Gender, Address.
Negative rule: Do not classify as aadhaar only because text contains Government of India or Government of Maharashtra.

- pan_card: Classify as pan_card only if OCR text contains PAN-specific evidence.
Positive signals: Income Tax Department, Permanent Account Number, PAN, PAN number pattern like ABCDE1234F, Father's name, Date of birth, Signature.


- passport:
Classify as passport if OCR text indicates an Indian passport or passport-related document.
Positive signals: Republic of India, Indian Passport, Passport, PASSPORT, Type P, Country Code IND, Passport No, File No, Given Name, Surname, Nationality Indian, Place of Birth, Date of Issue, Date of Expiry, Place of Issue, Passport Office, Ministry of External Affairs, MEA, MRZ (machine-readable zone with P<IND pattern), ECNR, ECR (Emigration Check Required/Not Required).
Negative rule: Do not classify as passport merely because text mentions "nationality" or "country" — there must be explicit passport-specific identifiers like Passport No, Type P, or Republic of India passport header.
Negative rule: Do not classify a visa or travel document as passport unless it is the passport booklet itself.

- driving_license:
Classify as driving_license if OCR text indicates an Indian Driving License.
Positive signals: Driving Licence, Driving License, DL, Motor Vehicles Act, Transport Department, Regional Transport Office, RTO, Licensing Authority, DL No, Licence No, COV (Class of Vehicle), LMV, MCWG, HMV, Transport Vehicle, Non-Transport Vehicle, Date of Issue, Valid Till, Valid Upto, Blood Group, badge number, Authorization to Drive, Form 7, Learner's Licence, Permanent Licence, State name with Transport/Motor Vehicles Department.
Negative rule: Do not classify vehicle registration (RC book) as driving_license. RC contains registration number, chassis number, engine number, and vehicle owner details — not driving authorization.
Negative rule: Do not classify as driving_license merely because text mentions "vehicle" or "transport" without DL-specific identifiers.

- voter_id:
Classify as voter_id if OCR text indicates an Indian Voter ID card (EPIC - Electors Photo Identity Card).
Positive signals: Election Commission of India, ELECTORS PHOTO IDENTITY CARD, EPIC, Voter ID, Electoral Roll, Part No, Serial No, Polling Station, Assembly Constituency, Parliamentary Constituency, EPIC No (pattern: 3 letters followed by 7 digits like ABC1234567), Age, Date of Birth, Gender, Father's/Husband's Name, Address, Photo, CEO (Chief Electoral Officer), ERO (Electoral Registration Officer).
Negative rule: Do not classify as voter_id merely because text mentions "election" or "vote" in a general context — there must be EPIC-specific identifiers like EPIC No, Electoral Roll, or Election Commission of India header.
Negative rule: Do not classify party membership cards or election result documents as voter_id.

- marksheet_10th:
Classify as marksheet_10th if OCR text indicates Class 10 / Secondary School Certificate / SSC marksheet.
Positive signals: Secondary School Certificate, SSC, Class X, Class 10, 10th, Matriculation, Secondary Examination, Statement of Marks, Board name, Seat number or roll number, subject marks table, total marks, percentage, result/pass/fail.
Mandatory mapping: If OCR contains "SECONDARY SCHOOL CERTIFICATE EXAMINATION - STATEMENT OF MARKS", return marksheet_10th.
Negative rule: Do NOT classify as marksheet_10th if OCR contains "Senior School Certificate Examination" or "Senior Secondary" or "SSCE" — those indicate Class 12, not Class 10.

- marksheet_12th:
Classify as marksheet_12th if OCR text indicates Class 12 / Higher Secondary Certificate / HSC marksheet.
Positive signals: Higher Secondary Certificate, HSC, Class XII, Class 12, 12th, Senior Secondary, Senior School Certificate Examination, SSCE, Intermediate Examination, Statement of Marks, Marks Statement Cum Certificate (when from CBSE with Senior School Certificate context), Stream Science/Commerce/Arts/Vocational, Board name, Seat number or roll number, subject marks table, total marks, percentage, result/pass/fail.
Mandatory mapping: If OCR contains "HIGHER SECONDARY CERTIFICATE EXAMINATION - STATEMENT OF MARKS", return marksheet_12th.
Mandatory mapping: If OCR contains "SENIOR SCHOOL CERTIFICATE EXAMINATION" (CBSE Class 12), return marksheet_12th.
Do not return unsupported labels like Higher Secondary Certificate Examination Result Slip, HSC result slip, or academic result document.

- certificate_diploma:
Classify as certificate_diploma if OCR text indicates a Diploma completion/award certificate (NOT a marksheet).
Positive signals: Diploma Certificate, Certificate of Diploma, This is to certify, awarded, conferred, Diploma in Engineering/Technology, Polytechnic, MSBTE, Board of Technical Education, Date of passing, Class (First Class/Second Class/Distinction/Pass Class), Final result, Passed with, Principal, Director, Chairman, Seal, Registration number, Enrollment number.
Key distinction: A certificate is an AWARD document — it certifies that a student has completed and passed. It does NOT have a subject-wise marks table, semester breakdown, internal/external marks columns, or individual subject scores.
Mandatory rule: If OCR text contains phrases like "This is to certify", "has been awarded", "conferred upon", "Diploma Certificate", or shows overall class/result WITHOUT a subject-wise marks table, classify as certificate_diploma, NOT marksheet_diploma.

- marksheet_diploma:
Classify as marksheet_diploma if OCR text indicates a Diploma-level marksheet or statement of marks.
Positive signals: Diploma in Engineering, Diploma in Technology, Polytechnic, MSBTE, Board of Technical Education, Statement of Marks, Semester I/II/III/IV/V/VI, Subject marks table, Total marks, Percentage, Result/Pass/Fail, Seat number or Enrollment number.
Negative rule: Do not classify a Diploma Certificate (completion/award certificate) as marksheet_diploma. A marksheet MUST have a subject-wise marks/grades table with individual subject names and their scores. Merely mentioning "First Class", "Distinction", overall percentage, or "passed" does NOT make it a marksheet — those appear on certificates too. If the document certifies completion/award without listing individual subject marks, it is certificate_diploma.

- certificate_degree:
Classify as certificate_degree if OCR text indicates a university degree completion/award certificate (Bachelor's, Master's, PhD, etc.).
Positive signals: Bachelor of Technology, Bachelor of Engineering, Bachelor of Science, Bachelor of Arts, Bachelor of Commerce, Master of Technology, Master of Science, MBA, MCA, PhD, Degree Certificate, Provisional Degree Certificate, Convocation, This is to certify, has been conferred, has been awarded, degree of, passed the examination, University name, Senate, Chancellor, Vice-Chancellor, Registrar, year of passing, Division (First/Second/Distinction), awarded on, conferred upon, seal of the university.
Key distinction: A degree certificate is an AWARD/CONFERMENT document — it certifies that a student has been awarded a degree. It does NOT have a subject-wise marks table, semester grades, SGPA/CGPA breakdown, or individual course scores. If the document has those, it is marksheet_degree instead.
Negative rule: Do not classify a semester marksheet/grade card as certificate_degree merely because it mentions a degree name (B.Tech, MBA, etc.). A degree certificate must have conferment/award language.
Negative rule: Do not classify a college ID card as certificate_degree merely because it mentions university name, programme, or student details.

- marksheet_degree:
Classify as marksheet_degree only if OCR text indicates college/university semester result, marksheet, or grade card.
Positive signals: Semester Marksheet, Semester Grade Card, Grade Card, Statement of Grades, Statement of Marks, Semester I/II/III/IV/V/VI/VII/VIII, SGPA, CGPA, SPI, CPI, Credits, Course Code, Course Title, Grade, Grade Points, Internal marks, External marks, University result, B.Tech/B.E./B.Sc./M.Tech/MBA/MCA.
Negative rule: Do not classify a college ID card as marksheet_degree merely because it contains university name, college name, programme, department, MIS number, PRN, enrollment number, issued on, valid upto, student signature, or authorised signatory. A semester marksheet/grade card must have marks, grades, credits, SGPA, CGPA, semester, or course table evidence.

- college_id_card:
Classify as college_id_card if OCR text indicates a student identity card issued by a college or university.
Positive signals: College ID card, Student ID card, Identity Card, Student Identity Card, I-Card, ID Card, college/university name, student name, roll number, MIS number, PRN, enrollment number, registration number, programme, department, branch, course, year of admission, academic year, blood group, issued on, valid upto, valid till, valid from, expiry date, student signature, principal signature, authorised signatory, emergency contact, student photo placeholder, barcode, QR code.
Key distinction: A college ID card is a IDENTITY document for campus access — it identifies a student. It typically has: student photo, name, ID/roll/MIS/PRN number, programme/department, validity dates, and authorized signatures. It does NOT award a degree, does NOT contain marks/grades/SGPA, and does NOT certify course completion.
Negative rules:
  - Do NOT classify as college_id_card if OCR has subject-wise marks, grades, SGPA, CGPA, credits, or course-credit table — those indicate marksheet_degree.
  - Do NOT classify as college_id_card if OCR has "conferred", "awarded", "degree of", "passed the examination", or convocation language — those indicate certificate_degree.
  - Do NOT classify as college_id_card if OCR has Aadhaar/UIDAI/PAN/Voter ID specific content.
  - A document with ONLY university name, student name, programme, department, ID number, validity dates, and signatures is college_id_card.
Example: COEP Technological University, Name, MIS No, Programme B.Tech, Department, Issued on, Valid Upto, Student's Signature, Authorised Signatory => college_id_card.
Example: Savitribai Phule Pune University, Student Identity Card, PRN, Faculty of Engineering, Valid 2022-2026 => college_id_card.

- payslip: Salary Slip / Payslip (earnings, deductions, net pay)
- experience_letter: Experience Letter / Relieving Letter / Employment Certificate
- bank_statement: Bank Statement (account details, transactions)

- photograph: Photograph only (no text document)

-fitment_medical_certificate:
Classify as fitment_medical_certificate if OCR text indicates a medical fitness, fitment, or doctor-issued health certificate.
Positive signals: Medical Certificate, Medical Fitness Certificate, Fitness Certificate, Fitment Certificate, Fit to work, Fit for employment, Fit for duty, physically fit, medically fit, health checkup, Doctor, Physician, Hospital, Clinic, MBBS, Registration number, blood pressure, vision, height, weight, pulse, medical examination, no communicable disease, signature of medical officer, seal of hospital/doctor.
Negative rule: Do not classify prescriptions or medicine bills as fitment_medical_certificate unless there is explicit certificate/fitness/fitment wording.

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
