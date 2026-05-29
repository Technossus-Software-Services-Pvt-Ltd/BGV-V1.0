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
}

export interface DocumentDetail {
  document: DocumentListItem;
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
