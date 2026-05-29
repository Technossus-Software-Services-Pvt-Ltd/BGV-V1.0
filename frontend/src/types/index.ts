export interface HealthStatus {
  status: string;
  services: {
    api: boolean;
    ollama: boolean;
    ollama_model: boolean;
  };
}

export interface UploadResponse {
  batch_id: string;
  batch_reference: string;
  candidate_id: string;
  documents: DocumentUploadInfo[];
  total_files: number;
  correlation_id: string;
  message: string;
}

export interface DocumentUploadInfo {
  id: string;
  filename: string;
  size_bytes: number;
  mime_type: string;
  status: string;
}

export interface DocumentListItem {
  id: string;
  candidate_id: string;
  upload_batch_id: string;
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  total_pages: number;
  processing_status: string;
  is_multi_page: boolean;
  error_message: string | null;
  correlation_id: string;
  created_at: string;
  updated_at: string;
  // Ownership verification
  validation_status: string | null;
  ownership_confirmed: boolean | null;
  validated_at: string | null;
}

export interface DocumentDetail {
  document: DocumentListItem;
  candidate_name: string | null;
  pages: DocumentPage[];
  ocr_results: OCRResult[];
  classifications: Classification[];
  validation_results: ValidationResult[];
}

export interface DocumentPage {
  id: string;
  document_id: string;
  page_number: number;
  width: number | null;
  height: number | null;
  orientation_corrected: boolean;
  processing_status: string;
  created_at: string;
}

export interface OCRResult {
  id: string;
  document_id: string;
  page_id: string | null;
  ocr_engine: string;
  extracted_text: string | null;
  confidence_score: number | null;
  word_count: number;
  language_detected: string | null;
  orientation_angle: number;
  processing_duration_ms: number | null;
  created_at: string;
}

export interface Classification {
  id: string;
  document_id: string;
  page_id: string | null;
  document_type: string;
  confidence_score: number;
  ai_reasoning: string | null;
  extracted_name: string | null;
  extracted_dob: string | null;
  extracted_id_number: string | null;
  model_used: string;
  processing_duration_ms: number | null;
  created_at: string;
}

export interface ValidationResult {
  id: string;
  document_id: string;
  candidate_id: string;
  validation_status: string;
  name_match: boolean | null;
  name_match_score: number | null;
  dob_match: boolean | null;
  id_number_match: boolean | null;
  ownership_confirmed: boolean;
  validation_reasoning: string | null;
  processing_duration_ms: number | null;
  created_at: string;
}

export interface CandidateResponse {
  candidates: Candidate[];
  total: number;
}

export interface Candidate {
  id: string;
  candidate_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingTimeline {
  document_id: string;
  events: ProcessingEvent[];
  current_status: string;
  total_duration_ms: number | null;
}

export interface ProcessingEvent {
  id: string;
  correlation_id: string;
  document_id: string;
  page_id: string | null;
  event_type: string;
  stage: string;
  status: string;
  message: string | null;
  confidence: number | null;
  duration_ms: number | null;
  error_details: string | null;
  created_at: string;
}

export interface BatchInfo {
  id: string;
  candidate_id: string;
  batch_reference: string;
  total_files: number;
  processed_files: number;
  failed_files: number;
  processing_status: string;
  correlation_id: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  id: string;
  correlation_id: string;
  action: string;
  log_level: string;
  processing_stage: string | null;
  message: string;
  candidate_id: string | null;
  document_id: string | null;
  duration_ms: number | null;
  created_at: string;
}

// === Batch Processing Types ===

export interface BatchUploadResponse {
  batch_id: string;
  batch_code: string;
  total_candidates: number;
  correlation_id: string;
  message: string;
}

export interface BatchImport {
  id: string;
  batch_code: string;
  original_filename: string;
  status: string;
  total_candidates: number;
  processed_candidates: number;
  failed_candidates: number;
  skipped_candidates: number;
  total_documents_found: number;
  total_documents_processed: number;
  error_message: string | null;
  correlation_id: string;
  created_at: string;
  updated_at: string;
}

export interface BatchCandidate {
  id: string;
  batch_import_id: string;
  candidate_id: string | null;
  row_number: number;
  source_candidate_id: string;
  source_name: string;
  source_email: string | null;
  source_phone: string | null;
  source_dob: string | null;
  source_gender: string | null;
  status: string;
  documents_found: number;
  documents_processed: number;
  documents_failed: number;
  gmail_emails_found: number;
  drive_files_found: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface BatchDetail {
  batch: BatchImport;
  candidates: BatchCandidate[];
}

export interface BatchLogEntry {
  id: string;
  level: string;
  stage: string;
  message: string;
  details: string | null;
  batch_candidate_id: string | null;
  created_at: string;
  type?: string;
  status?: string;
}

export interface IntegrationConfig {
  id: string;
  provider: string;
  is_enabled: boolean;
  has_credentials: boolean;
  config_json: string | null;
  last_validated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GmailStatus {
  connected: boolean;
  has_client_config: boolean;
  email: string | null;
  scopes: string[];
  is_enabled: boolean;
  last_validated_at: string | null;
}

export interface DriveConfig {
  search_folder_ids: string[];
  storage_root_folder_id: string | null;
}
