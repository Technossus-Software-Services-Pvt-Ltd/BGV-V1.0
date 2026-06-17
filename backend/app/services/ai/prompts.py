from app.models.enums import DocumentType

BROAD_CLASSIFICATION_PROMPT = """Classify the Indian BGV document OCR text into exactly one broad group.

GROUPS:
- identity: Aadhaar card, PAN card, Passport, Driving License, Voter ID, Birth Certificate, OCI card
- education: Marksheets, Degree/Diploma certificates, College/Student ID cards, Transfer/Bonafide/Migration certificates
- employment: Offer/Appointment/Relieving/Experience letters, Employee ID card, Promotion/Increment letters
- financial: Payslips/Salary slips, Bank statements/Passbook/Account details, Form 16, Form 26AS, ITR, Cancelled Cheques
- address: Utility bills (Electricity/Water/Gas/Phone), Rent/Lease agreements
- medical: Medical certificates, Fitness/Fitment certificates, Vaccination cards, Health insurance
- legal: PCC, Legal affidavits, Court documents
- other: Photograph, Unknown

CRITICAL RULES - READ CAREFULLY:
1. PAN card is ALWAYS "identity", NEVER "financial". PAN cards say "INCOME TAX DEPARTMENT" but are government identity cards.
2. Payslip/Salary slip is ALWAYS "financial", NEVER "employment". Payslips show monthly earnings and deductions (Basic, HRA, EPF, Net Pay).
3. Bank Passbook, Bank Account Details page, Bank Account Summary, or Bank Statement is ALWAYS "financial", NEVER "address" or "identity", even if it shows the holder's home address or name.
4. College ID, Student ID, or University ID card is ALWAYS "education", NEVER "identity", even if it contains emergency contacts, blood group, or is in card format.
5. Medical fitness/fitment certificate, doctor's certificate, or health checkup report is ALWAYS "medical", NEVER "identity" or "employment", even if it contains a certification phrase like "This is to certify".
6. Form 16 is ALWAYS "financial". It is a tax document showing TDS details.
7. Offer/Appointment letters discuss joining details and job terms. They do NOT show itemized monthly salary deductions.

EXAMPLES:
Example 1 (Bank Account Details / Passbook → financial, NOT address):
OCR: "PITaTgP&AOCh-:PUNE GANESHNAGAR(756) Address: SAMRATH PATH PUNE MICR Code:411014018 IFSC Code:MAHB0000756 Account No: 20084661033 Account Type: SB-Chq Mr. SOHAM NILESH VAZE"
Response: {{"broad_group": "financial", "confidence": 1.0, "reasoning": "Bank account details page with Account Number, IFSC, and MICR code."}}

Example 2 (College ID without 'ID' text → education, NOT identity):
OCR: "MIT WORLDPEACE MIT-WPU UNIVERSITY PUNE Faculty of Engineering and Technology B.Tech.Electrical & Computer Engineering Kumar Bikku Emergency No 919387990733 Valid Upto 07/26 Blood Group A+ ve"
Response: {{"broad_group": "education", "confidence": 1.0, "reasoning": "University student profile card for B.Tech program."}}

Example 3 (Medical Fitness Certificate → medical, NOT identity):
OCR: "Dr. Mahesh Apte FAMILY DOCTOR M.B.B.S. Reg.No. 68667 Clinic: 2544 2323 16/12/2025 This is to certify that I have examined Soham Nilesh Vaze and found him fit."
Response: {{"broad_group": "medical", "confidence": 1.0, "reasoning": "Doctor certificate certifying candidate's medical fitness."}}

Example 4 (Payslip → financial, NOT employment):
OCR: "INFOSYS LIMITED Payslip July 2025 Employee: Pooja Thite Basic: 43392 HRA: 21696 EPF: 5207 Net Pay: 79577"
Response: {{"broad_group": "financial", "confidence": 1.0, "reasoning": "Monthly payslip showing salary details and deductions."}}

Example 5 (PAN Card → identity, NOT financial):
OCR: "INCOME TAX DEPARTMENT GOVT OF INDIA Permanent Account Number AVUPT6435D POOJA BABURAO THITE DOB: 15/06/1998"
Response: {{"broad_group": "identity", "confidence": 1.0, "reasoning": "Government-issued PAN identity card."}}

Example 6 (Degree Certificate → education, NOT identity):
OCR: "Solapur University Degree Certificate certify that Thite Pooja Baburao Aadhaar No: 882800715902 has completed Bachelor of Engineering"
Response: {{"broad_group": "education", "confidence": 1.0, "reasoning": "University degree certificate."}}

Example 7 (Appointment Letter → employment, NOT financial):
OCR: "We are pleased to appoint you as Software Engineer. Your date of joining will be 01/07/2025. Your annual CTC will be Rs. 6,00,000."
Response: {{"broad_group": "employment", "confidence": 1.0, "reasoning": "Appointment letter offering employment terms."}}

Respond ONLY with valid JSON in this format:
{{"broad_group": "<group>", "confidence": <float 0.0-1.0>, "reasoning": "<brief reason>"}}

OCR TEXT:
{ocr_text}"""


SPECIFIC_CLASSIFICATION_PROMPTS = {
    "identity": """Classify this identity document OCR text into EXACTLY ONE type:
- aadhaar (Keywords: UIDAI, Aadhaar, Aadhar, Unique Identification, 12-digit UID number like XXXX XXXX XXXX, VID)
- pan_card (Keywords: PAN, Permanent Account Number, INCOME TAX DEPARTMENT, 10-character alphanumeric, GOVT OF INDIA)
- passport (Keywords: PASSPORT, Republic of India, Passport No, Type P, Nationality IND, Place of Issue, ECNR)
- driving_license (Keywords: Driving Licence, Driving License, DL No, RTO, Transport, Motor Vehicle, LMV, MCWG)
- voter_id (Keywords: Election Commission, EPIC, Voter ID, Electoral, Elector Photo Identity)
- birth_certificate (Keywords: Birth Certificate, Registrar of Births and Deaths, Date of Birth, Place of Birth)
- oci_card (Keywords: OCI, Overseas Citizen of India)
- unknown (cannot determine)

WARNING:
- Student ID cards, College ID cards, Employee ID cards, and Bank Passbooks/Details pages are NOT valid identity documents for this category. Classify them as 'unknown'.
- A passport MUST contain terms like "passport" or "republic of india" or "passport no". Do NOT classify general ID cards or emergency cards as passport.

EXAMPLES:
Example (PAN Card):
OCR: "INCOMETAX DEPARTMENT GOVT OF INDIA Permanent Account Number AVUPT6435D POOJA THITE"
Response: {{"document_type": "pan_card", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "education": """Classify this education document OCR text into EXACTLY ONE type:
- marksheet_10th (Secondary School Examination, AISSE, SSC, Class X, Class 10, 10th standard - board examination marks/grades table)
- marksheet_12th (Senior School Certificate Examination, AISSCE, HSC, Higher Secondary Certificate Examination, Class XII, Class 12, 12th standard, Intermediate - board examination marks/grades table)
- certificate_diploma (Diploma Certificate, awarded/conferred diploma completion - NO marks table)
- marksheet_diploma (Diploma marksheet/grade card with subject marks or grades table specifically for a Diploma/Polytechnic program)
- certificate_degree (Degree Certificate, University/College degree, certifying that the candidate has completed Bachelor/Master/Engineering course)
- provisional_degree_certificate (Provisional Degree Certificate, Provisional Certificate)
- marksheet_degree (Semester Grade Card, SGPA, CGPA, Credits, Grades table, university examination report for Bachelor/Master degree courses like B.Tech, B.E., B.Sc, B.Com, B.A, M.B.A, etc.)
- college_id_card (Student ID Card, College ID Card, University ID, containing university details, degree/branch name, student name, roll number, or register number)
- bonafide_certificate (Bonafide Certificate, certifying student of this institution)
- transfer_certificate (Transfer Certificate, TC, School Leaving Certificate, SLC)
- migration_certificate (Migration Certificate)
- education_gap_affidavit (Education Gap Affidavit, Gap in Education)
- unknown (cannot determine)

CRITICAL RULES FOR MARKSHEETS:
1. In India (especially CBSE), "Secondary School Examination" is Class 10 (marksheet_10th).
2. "Senior School Certificate Examination" is Class 12 (marksheet_12th). "Senior School Certificate" is ALWAYS Class 12.
3. State boards (like Maharashtra State Board) often print both "Secondary" and "Higher Secondary" in their board header (e.g., "Board of Secondary and Higher Secondary Education"). You MUST look at the exam name: "HIGHER SECONDARY CERTIFICATE EXAMINATION" or "HSC" is ALWAYS Class 12 (marksheet_12th). "SECONDARY SCHOOL CERTIFICATE" or "SSC" is Class 10 (marksheet_10th).
4. Degree marksheets vs Diploma: Marksheets, scorecards, or grade reports from a University for a degree program (e.g. Bachelor, Master, B.Tech, B.E, B.Sc, B.Com, B.A, M.B.A, M.Tech) are ALWAYS `marksheet_degree`, NEVER `marksheet_diploma`. A diploma marksheet (`marksheet_diploma`) is only for Polytechnic or non-degree Diploma courses (which explicitly mention the word "Diploma" or "Polytechnic").

EXAMPLES:
Example 1 (12th Marksheet - State Board):
OCR: "Maharashtra State Board Of Secondary and Higher Secondary Education, Pune HIGHER SECONDARY CERTIFICATE EXAMINATION - STATEMENT OF MARKS Vaze Soham Nilesh SCIENCE"
Response: {{"document_type": "marksheet_12th", "confidence": 1.0}}

Example 2 (12th Marksheet - CBSE):
OCR: "CENTRAL BOARD OF SECONDARY EDUCATION MARKS STATEMENT CUM CERTIFICATE 2021 SENIOR SCHOOL CERTIFICATE EXAMINATION, 2021 BIKKU KUMAR Roll 22629096"
Response: {{"document_type": "marksheet_12th", "confidence": 1.0}}

Example 3 (10th Marksheet - CBSE):
OCR: "CENTRAL BOARD OF SECONDARY EDUCATION MARKS STATEMENT CUM CERTIFICATE 2019 ALL INDIA SECONDARY SCHOOL EXAMINATION, 2019 BIKKU KUMAR Roll 7141628"
Response: {{"document_type": "marksheet_10th", "confidence": 1.0}}

Example 4 (College ID):
OCR: "MIT WORLDPEACE MIT-WPU UNIVERSITY PUNE Faculty of Engineering and Technology B.Tech.Electrical & Computer Engineering Kumar Bikku Register No 1032222863"
Response: {{"document_type": "college_id_card", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "employment": """Classify this employment document OCR text into EXACTLY ONE type:
- offer_letter (Offer Letter, Offer of Employment, Compensation Package, proposed CTC)
- appointment_letter (Appointment Letter, Employment Terms, Date of Joining, terms of appointment)
- experience_letter (Experience Certificate, Experience Letter, worked with us, service period, designation)
- relieving_letter (Relieving Letter, relieved from duties, Last Working Day, resignation)
- employment_verification_letter (Employment Verification, Employment Confirmation)
- promotion_letter (Promotion, Promoted To, New Designation)
- increment_letter (Salary Revision, Increment Letter)
- employee_id_card (Employee ID Card, Employee Code, card format with company logo and employee name)
- unknown (cannot determine)

WARNING:
- A PAYSLIP/SALARY SLIP showing monthly basic, HRA, EPF, Net Pay is NOT an employment document. It is a financial document.
- If it is a bank statement or bank details page, classify it as 'unknown'.

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "financial": """Classify this financial document OCR text into EXACTLY ONE type:
- payslip (Payslip, Salary Slip, monthly salary statement with earnings/deductions/Net Pay)
- bank_statement (Bank Statement, Account Statement, Bank Passbook, Bank Account Details page containing Account Number, IFSC, MICR, Branch name, or transactions list)
- form16 (FORM NO.16, TDS Certificate, Tax Deducted at Source, Assessment Year)
- form26as (Form 26AS, Annual Tax Statement, Tax Credit Statement)
- itr (ITR-V, Income Tax Return Verification, Assessment Year)
- cancelled_cheque (Cancelled Cheque, CANCELLED written across cheque leaf, IFSC, MICR, Account Number)
- unknown (cannot determine)

CRITICAL RULES:
1. Bank Account Details page, bank passbook front page (showing Account No, IFSC, MICR, Branch, name, and address) belongs to `bank_statement`.
2. A monthly payslip contains Basic, HRA, PF, TDS, Net Pay for a specific month.

EXAMPLES:
Example (Bank Account Details):
OCR: "PUNE GANESHNAGAR Branch Address: SAMRATH PATH PUNE MICR Code: 411014018 IFSC Code: MAHB0000756 Account No: 20084661033 Mr. SOHAM NILESH VAZE"
Response: {{"document_type": "bank_statement", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "address": """Classify this address/utility document OCR text into EXACTLY ONE type:
- electricity_bill (Electricity Bill, Energy Charges, kWh, units consumed, consumer number)
- water_bill (Water Bill, Water Charges)
- gas_bill (Gas Bill, LPG, PNG)
- telephone_bill (Airtel, Jio, Vodafone, BSNL, Telephone Bill, Mobile Bill)
- utility_bill (Utility Bill, consumer number)
- rent_agreement (Rent Agreement, Tenant, Landlord, monthly rent)
- lease_agreement (Lease Agreement, Lessor, Lessee)
- unknown (cannot determine)

WARNING:
- A bank statement, bank passbook, or bank account details page is NOT a utility bill or rent agreement. Even if it contains an address, classify it as 'unknown' under this address category.

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "medical": """Classify this medical document OCR text into EXACTLY ONE type:
- fitment_medical_certificate (Medical Fitness Certificate, Medical Certificate, Fit for Employment, doctor examined candidate)
- vaccination_certificate (Vaccination Certificate, CoWIN, COVID-19 Vaccine)
- health_insurance_card (Health Insurance, Policy Number)
- unknown (cannot determine)

EXAMPLES:
Example (Fitness Certificate):
OCR: "Dr. Mahesh Apte FAMILY DOCTOR M.B.B.S. Reg.No. 68667 Clinic Timing: Morning 09:00 to 12:30 This is to certify that I have examined Soham Nilesh Vaze M21 yos today and found him fit."
Response: {{"document_type": "fitment_medical_certificate", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "legal": """Classify this legal document OCR text into EXACTLY ONE type:
- police_clearance_certificate (Police Clearance Certificate, PCC, no criminal record)
- legal_affidavit (Affidavit, Notary, Sworn Statement, deponent)
- court_document (Court, Case Number, Judgment, Order)
- unknown (cannot determine)

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "other": """Classify this document OCR text into EXACTLY ONE type:
- photograph (No meaningful OCR text, human photo only)
- unknown (unable to confidently determine document type)

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text."""
}

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
6. Gender (Male, Female, or Transgender, if present)

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
    "gender": "<Male, Female, or Transgender or null>",
    "confidence": <float 0.0-1.0>
}}

IMPORTANT: Return ONLY valid JSON. No additional text."""
