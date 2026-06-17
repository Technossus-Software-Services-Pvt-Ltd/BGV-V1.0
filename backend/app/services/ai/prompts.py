from app.models.enums import DocumentType

BROAD_CLASSIFICATION_PROMPT = """Classify the Indian BGV document OCR text into exactly one broad group.

GROUPS:
- identity: Aadhaar card, PAN card, Passport, Driving License, Voter ID, Birth Certificate, OCI card
- education: Marksheets, Degree/Diploma certificates, College IDs, Transfer/Bonafide/Migration certificates
- employment: Offer/Appointment/Relieving/Experience letters, Employee ID card, Promotion/Increment letters
- financial: Payslips/Salary slips, Bank statements, Form 16, Form 26AS, ITR, Cancelled Cheques
- address: Utility bills (Electricity/Water/Gas/Phone), Rent/Lease agreements
- medical: Medical certificates, Vaccination cards, Health insurance
- legal: PCC, Legal affidavits, Court documents
- other: Photograph, Unknown

CRITICAL RULES - READ CAREFULLY:
1. PAN card is ALWAYS "identity", NEVER "financial". PAN cards say "INCOME TAX DEPARTMENT" and "Permanent Account Number" but they are government-issued IDENTITY cards.
2. Payslip/Salary slip is ALWAYS "financial", NEVER "employment". Payslips show monthly earnings (Basic, HRA, DA, EPF, TDS, Net Pay) even though they contain employee name, designation, and company name.
3. Form 16 is ALWAYS "financial". It is a tax certificate showing TDS details.
4. Offer/Appointment letters discuss job terms (role, CTC, joining date). They do NOT show monthly salary breakdowns with deductions.
5. Degree/Diploma certificates are ALWAYS "education", even if they mention Aadhaar numbers or parent names.

EXAMPLES:
Example 1 (Payslip → financial, NOT employment):
OCR: "INFOSYS LIMITED Payslip July 2025 Employee: Pooja Thite Designation: Software Engineer Basic: 43392 HRA: 21696 EPF: 5207 TDS: 8200 Net Pay: 79577"
Response: {{"broad_group": "financial", "confidence": 1.0, "reasoning": "Payslip showing monthly salary breakdown with earnings and deductions."}}

Example 2 (PAN Card → identity, NOT financial):
OCR: "INCOME TAX DEPARTMENT GOVT OF INDIA Permanent Account Number AVUPT6435D POOJA BABURAO THITE Date of Birth 15/06/1998 Signature"
Response: {{"broad_group": "identity", "confidence": 1.0, "reasoning": "PAN card issued by Income Tax Department - this is a government identity document."}}

Example 3 (Aadhaar → identity):
OCR: "UNIQUE IDENTIFICATION AUTHORITY OF INDIA Aadhaar 1234 5678 9012 DOB: 15/06/1998"
Response: {{"broad_group": "identity", "confidence": 1.0, "reasoning": "Government-issued Aadhaar identity card with UID number."}}

Example 4 (Appointment Letter → employment, NOT financial):
OCR: "Dear Pooja, We are pleased to appoint you as Software Engineer at our organization. Your date of joining will be 01/07/2025. Your annual CTC will be Rs. 6,00,000."
Response: {{"broad_group": "employment", "confidence": 1.0, "reasoning": "Appointment letter offering a job with joining date and CTC."}}

Example 5 (Degree Certificate → education, NOT identity):
OCR: "Solapur University Degree Certificate certify that Thite Pooja Baburao Aadhaar No: 882800715902 has completed Bachelor of Engineering"
Response: {{"broad_group": "education", "confidence": 1.0, "reasoning": "University degree certificate, even though it contains an Aadhaar number."}}

Example 6 (Relieving Letter → employment):
OCR: "Relieving Letter This is to certify that Pooja Thite has resigned and is relieved from duties effective 30/06/2025."
Response: {{"broad_group": "employment", "confidence": 1.0, "reasoning": "Relieving letter confirming end of employment."}}

Example 7 (Form 16 → financial, NOT identity):
OCR: "FORM NO. 16 Certificate under section 203 of the Income-tax Act TDS Tax Deducted at Source PAN: AVUPT6435D Assessment Year 2025-26"
Response: {{"broad_group": "financial", "confidence": 1.0, "reasoning": "Form 16 is a TDS tax certificate - a financial document, not identity even though it shows PAN."}}

Example 8 (Bank Statement → financial):
OCR: "State Bank of India Account Statement Account No: 1234567890 Opening Balance: 45000 Credit: 50000 Debit: 30000"
Response: {{"broad_group": "financial", "confidence": 1.0, "reasoning": "Bank account statement showing transactions."}}

Respond ONLY with valid JSON in this format:
{{"broad_group": "<group>", "confidence": <float 0.0-1.0>, "reasoning": "<brief reason>"}}

OCR TEXT:
{ocr_text}"""


SPECIFIC_CLASSIFICATION_PROMPTS = {
    "identity": """Classify this identity document OCR text into EXACTLY ONE type:
- aadhaar (Keywords: UIDAI, Aadhaar, Aadhar, Unique Identification, 12-digit UID number like XXXX XXXX XXXX, VID, enrolment)
- pan_card (Keywords: PAN, Permanent Account Number, INCOME TAX DEPARTMENT, 10-character alphanumeric like ABCDE1234F, GOVT OF INDIA)
- passport (Keywords: PASSPORT, Republic of India, Passport No, Type P, Nationality IND, Place of Issue, ECNR)
- driving_license (Keywords: Driving Licence, Driving License, DL No, RTO, Transport, Motor Vehicle, LMV, MCWG)
- voter_id (Keywords: Election Commission, EPIC, Voter ID, Electoral, Elector Photo Identity)
- birth_certificate (Keywords: Birth Certificate, Registrar of Births and Deaths, Date of Birth, Place of Birth, Registration No)
- oci_card (Keywords: OCI, Overseas Citizen of India, OCI Card)
- unknown (cannot determine)

EXAMPLES:
Example (PAN Card):
OCR: "INCOMETAX DEPARTMENT GOVT OF INDIA Permanent Account Number AVUPT6435D POOJA THITE"
Response: {{"document_type": "pan_card", "confidence": 1.0}}

Example (Aadhaar):
OCR: "UNIQUE IDENTIFICATION AUTHORITY OF INDIA 9876 5432 1098 DOB: 15/06/1998"
Response: {{"document_type": "aadhaar", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "education": """Classify this education document OCR text into EXACTLY ONE type:
- marksheet_10th (SSC, Secondary School Certificate, Class X, Class 10, 10th standard, board examination with marks/grades table)
- marksheet_12th (HSC, Higher Secondary Certificate, Class XII, Class 12, 12th standard, intermediate with marks/grades table)
- certificate_diploma (Diploma Certificate, awarded/conferred diploma completion - NO marks table, certifying completion)
- marksheet_diploma (Diploma marksheet/grade card with subject marks or grades table)
- certificate_degree (Degree Certificate, University/College degree, certifying that the candidate has completed Bachelor/Master/Engineering course)
- provisional_degree_certificate (Provisional Degree Certificate, Provisional Certificate, issued before final degree)
- marksheet_degree (Semester Grade Card, SGPA, CGPA, Credits, Grades table, university examination)
- college_id_card (Student ID Card, card format with library, barcode, roll number, student photo)
- bonafide_certificate (Bonafide Certificate, certifying student of this institution)
- transfer_certificate (Transfer Certificate, TC, School Leaving Certificate, SLC)
- migration_certificate (Migration Certificate, migration from one university to another)
- education_gap_affidavit (Education Gap Affidavit, Gap in Education, sworn statement about gap year)
- unknown (cannot determine)

EXAMPLES:
Example (Degree Certificate):
OCR: "Solapur University certify that Thite Pooja Baburao has pursued a course of study in Bachelor of Engineering"
Response: {{"document_type": "certificate_degree", "confidence": 1.0}}

Example (10th Marksheet):
OCR: "SECONDARY SCHOOL CERTIFICATE EXAMINATION Seat No: 12345 Subject Marks: English 85 Maths 92 Science 88"
Response: {{"document_type": "marksheet_10th", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "employment": """Classify this employment document OCR text into EXACTLY ONE type:
- offer_letter (Offer Letter, Offer of Employment, "pleased to offer", Compensation Package, proposed CTC)
- appointment_letter (Appointment Letter, "pleased to appoint", Employment Terms, Date of Joining, terms and conditions of appointment)
- experience_letter (Experience Certificate, Experience Letter, "worked with us", "was employed with", service period, designation held)
- relieving_letter (Relieving Letter, "relieved from duties", Last Working Day, resignation accepted)
- employment_verification_letter (Employment Verification, Employment Confirmation Letter)
- promotion_letter (Promotion, Promoted To, New Designation, promotion effective)
- increment_letter (Salary Revision, Increment Letter, revised compensation)
- employee_id_card (Employee ID Card, Employee Code, badge, card format with photo and designation)
- unknown (cannot determine)

WARNING - DO NOT CONFUSE THESE:
- A PAYSLIP/SALARY SLIP is NOT an employment document. If the text shows monthly salary breakdown with Basic, HRA, DA, EPF, TDS, deductions, Net Pay, Gross Salary — that is a payslip (financial), NOT appointment_letter.
- An APPOINTMENT LETTER discusses job offer terms, joining date, role description. It does NOT show itemized monthly salary deductions.
- An INCREMENT LETTER announces a salary revision. A PAYSLIP shows actual monthly payment with deductions.

EXAMPLES:
Example (Appointment Letter):
OCR: "We are pleased to appoint you as Software Engineer. Your date of joining is 01/07/2025. Terms and conditions..."
Response: {{"document_type": "appointment_letter", "confidence": 1.0}}

Example (Experience Letter):
OCR: "This is to certify that Ms. Pooja Thite was employed with us as Software Engineer from 01/01/2023 to 30/06/2025."
Response: {{"document_type": "experience_letter", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "financial": """Classify this financial document OCR text into EXACTLY ONE type:
- payslip (Payslip, Salary Slip, Pay Slip, monthly salary statement with: Basic/HRA/DA earnings AND EPF/TDS/ESI deductions AND Net Pay/Gross Pay. Contains employee name, month, and itemized salary components)
- bank_statement (Bank Statement, Account Statement, Transactions list, Balance, Credit/Debit entries, Account Number, IFSC)
- form16 (FORM NO.16, Form 16, Certificate under section 203, TDS Certificate, Tax Deducted at Source, Assessment Year)
- form26as (Form 26AS, Annual Tax Statement, Tax Credit Statement, traces)
- itr (ITR-V, Income Tax Return Verification, ITR Acknowledgement, Assessment Year)
- cancelled_cheque (Cancelled Cheque, CANCELLED written across cheque, IFSC, MICR code, Account Number on cheque leaf)
- unknown (cannot determine)

CRITICAL RULES:
- A PAYSLIP shows a SINGLE MONTH salary with itemized components (Basic, HRA, Conveyance, EPF, Professional Tax, TDS). Look for words like "Payslip", "Salary Slip", "Pay Slip", "Net Pay", "Gross Earnings", "Total Deductions".
- Form 16 is an ANNUAL tax certificate with Assessment Year, TDS summary. It mentions "section 203" or "FORM NO. 16".
- A bank statement has a list of TRANSACTIONS with dates, credits, debits, running balance.

EXAMPLES:
Example (Payslip):
OCR: "INFOSYS LIMITED Payslip for July 2025 Employee: Pooja Thite EmpID: 12345 Designation: SE Basic: 43392 HRA: 21696 EPF: 5207 TDS: 8200 Net Pay: 79577"
Response: {{"document_type": "payslip", "confidence": 1.0}}

Example (Form 16):
OCR: "FORM NO. 16 Certificate under section 203 of Income-tax Act PAN: AVUPT6435D Assessment Year 2025-26 TDS Deducted: 98400"
Response: {{"document_type": "form16", "confidence": 1.0}}

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "address": """Classify this address/utility document OCR text into EXACTLY ONE type:
- electricity_bill (Electricity Bill, Energy Charges, kWh, units consumed, MSEDCL, BESCOM, TPDDL)
- water_bill (Water Bill, Water Supply, Water Charges, water consumption)
- gas_bill (Gas Bill, LPG, PNG, Indane, Bharat Gas, HP Gas)
- telephone_bill (Airtel, Jio, Vodafone, BSNL, Telephone Bill, Mobile Bill, broadband)
- utility_bill (General Utility Bill, Consumer Number, not specifically electricity/water/gas/telephone)
- rent_agreement (Rent Agreement, Tenant, Landlord, monthly rent, lease period)
- lease_agreement (Lease Agreement, Lessor, Lessee, lease deed)
- unknown (cannot determine)

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "medical": """Classify this medical document OCR text into EXACTLY ONE type:
- fitment_medical_certificate (Medical Fitness Certificate, Fit for Employment, Medical Examination Report)
- vaccination_certificate (Vaccination Certificate, CoWIN, COVID-19 Vaccine, immunization)
- health_insurance_card (Health Insurance, Policy Number, Sum Insured, TPA)
- unknown (cannot determine)

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "legal": """Classify this legal document OCR text into EXACTLY ONE type:
- police_clearance_certificate (Police Clearance Certificate, PCC, no criminal record, character certificate from police)
- legal_affidavit (Affidavit, Notary, Sworn Statement, deponent, oath)
- court_document (Court, Case Number, Judgment, Order, petition, tribunal)
- unknown (cannot determine)

Respond ONLY with valid JSON:
{{"document_type": "<type>", "confidence": <float 0.0-1.0>}}

OCR TEXT:
{ocr_text}

IMPORTANT: Return ONLY valid JSON. No additional text.""",

    "other": """Classify this document OCR text into EXACTLY ONE type:
- photograph (No meaningful OCR text, very few words, human photo only)
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
