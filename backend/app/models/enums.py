import enum


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    NORMALIZING = "normalizing"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"
    SKIPPED = "skipped"
    AI_CLASSIFYING = "ai_classifying"
    AI_CLASSIFICATION_COMPLETE = "ai_classification_complete"
    AI_CLASSIFICATION_FAILED = "ai_classification_failed"
    VALIDATING = "validating"
    VALIDATION_COMPLETE = "validation_complete"
    VALIDATION_FAILED = "validation_failed"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    AADHAAR = "aadhaar"
    PAN_CARD = "pan_card"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    POLICE_VERIFICATION = "police_verification"
    CERTIFICATE_10TH = "certificate_10th"
    CERTIFICATE_12TH = "certificate_12th"
    CERTIFICATE_DIPLOMA = "certificate_diploma"
    CERTIFICATE_DEGREE = "certificate_degree"
    PAYSLIP = "payslip"
    EXPERIENCE_LETTER = "experience_letter"
    BANK_STATEMENT = "bank_statement"
    ADDRESS_PROOF = "address_proof"
    PHOTOGRAPH = "photograph"
    UNKNOWN = "unknown"


class ValidationStatus(str, enum.Enum):
    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    UNMATCHED = "unmatched"
    NOT_APPLICABLE = "not_applicable"


class AuditAction(str, enum.Enum):
    UPLOAD = "upload"
    OCR_START = "ocr_start"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"
    AI_START = "ai_start"
    AI_COMPLETE = "ai_complete"
    AI_FAILED = "ai_failed"
    VALIDATION_START = "validation_start"
    VALIDATION_COMPLETE = "validation_complete"
    VALIDATION_FAILED = "validation_failed"
    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_FAILED = "processing_failed"
    DOCUMENT_SPLIT = "document_split"
    PAGE_CLASSIFIED = "page_classified"


class LogLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BatchImportStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class BatchCandidateStatus(str, enum.Enum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    DOCUMENTS_FOUND = "documents_found"
    NO_DOCUMENTS = "no_documents"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    AWAITING_REQUIRED_DOCUMENTS = "awaiting_required_documents"
    FAILED = "failed"
    SKIPPED = "skipped"


class IntegrationProvider(str, enum.Enum):
    GMAIL = "gmail"
    GOOGLE_DRIVE = "google_drive"


class NotificationStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
