import api from './client';
import {
  UploadResponse,
  DocumentListItem,
  DocumentDetail,
  CandidateResponse,
  ProcessingTimeline,
  AuditLogEntry,
  HealthStatus,
  BatchInfo,
  BatchUploadResponse,
  BatchImport,
  BatchDetail,
  BatchCandidate,
  IntegrationConfig,
  GmailStatus,
  DriveConfig,
} from '../types';
import { UploadResponse, DocumentListItem, DocumentDetail, CandidateResponse, ProcessingTimeline, AuditLogEntry, HealthStatus, BatchInfo } from '../types';
import { GoogleAuthStartResponse, GoogleAuthCallbackResponse } from '../types/auth';

export async function checkHealth(): Promise<HealthStatus> {
  const response = await api.get('/health');
  return response.data;
}

export async function uploadDocuments(formData: FormData): Promise<UploadResponse> {
  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function listDocuments(params?: {
  candidate_id?: string;
  status_filter?: string;
  skip?: number;
  limit?: number;
}): Promise<DocumentListItem[]> {
  const response = await api.get('/documents', { params });
  return response.data;
}

export async function getDocumentDetail(documentId: string): Promise<DocumentDetail> {
  const response = await api.get(`/documents/${documentId}`);
  return response.data;
}

export async function listCandidates(params?: {
  skip?: number;
  limit?: number;
}): Promise<CandidateResponse> {
  const response = await api.get('/candidates', { params });
  return response.data;
}

export async function createCandidate(data: {
  candidate_id: string;
  name: string;
  email?: string;
  phone?: string;
}): Promise<unknown> {
  const response = await api.post('/candidates', data);
  return response.data;
}

export async function getProcessingTimeline(documentId: string): Promise<ProcessingTimeline> {
  const response = await api.get(`/processing/timeline/${documentId}`);
  return response.data;
}

export async function listBatches(params?: {
  candidate_id?: string;
  skip?: number;
  limit?: number;
}): Promise<BatchInfo[]> {
  const response = await api.get('/processing/batches', { params });
  return response.data;
}

export async function getAuditLogs(params?: {
  correlation_id?: string;
  document_id?: string;
  candidate_id?: string;
  action?: string;
  skip?: number;
  limit?: number;
}): Promise<AuditLogEntry[]> {
  const response = await api.get('/audit/logs', { params });
  return response.data;
}

// === Batch Processing ===

export async function uploadBatchFile(formData: FormData): Promise<BatchUploadResponse> {
  const response = await api.post('/batch/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function startBatchProcessing(batchId: string): Promise<BatchImport> {
  const response = await api.post(`/batch/${batchId}/start`);
  return response.data;
}

export async function listBatchImports(params?: {
  skip?: number;
  limit?: number;
  status?: string;
  date_from?: string;
  date_to?: string;
}): Promise<BatchImport[]> {
  const response = await api.get('/batch', { params });
  return response.data;
}

export async function getBatchDetail(batchId: string): Promise<BatchDetail> {
  const response = await api.get(`/batch/${batchId}`);
  return response.data;
}

export async function listBatchCandidates(
  batchId: string,
  statusFilter?: string,
): Promise<BatchCandidate[]> {
  const response = await api.get(`/batch/${batchId}/candidates`, {
    params: statusFilter ? { status_filter: statusFilter } : undefined,
  });
  return response.data;
}

export async function retryBatchCandidate(
  batchId: string,
  candidateId: string,
): Promise<BatchCandidate> {
  const response = await api.post(`/batch/${batchId}/candidates/${candidateId}/retry`);
  return response.data;
}

export function createBatchLogStream(batchId: string): EventSource {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  return new EventSource(`${baseUrl}/batch/${batchId}/logs`);
}

export interface BatchLogItem {
  id: string;
  batch_import_id: string;
  batch_candidate_id: string | null;
  level: string;
  stage: string;
  message: string;
  details: string | null;
  created_at: string;
}

export async function getBatchLogs(
  batchId: string,
  params?: { candidate_id?: string; level?: string },
): Promise<BatchLogItem[]> {
  const response = await api.get(`/batch/${batchId}/logs/all`, { params });
  return response.data;
}

// === Settings / Integrations ===

export async function listIntegrations(): Promise<IntegrationConfig[]> {
  const response = await api.get('/settings/integrations');
  return response.data;
}

export async function getIntegration(provider: string): Promise<IntegrationConfig> {
  const response = await api.get(`/settings/integrations/${provider}`);
  return response.data;
}

export async function updateIntegration(
  provider: string,
  data: { is_enabled?: boolean; credentials_json?: string; config_json?: string },
): Promise<IntegrationConfig> {
  const response = await api.put(`/settings/integrations/${provider}`, data);
  return response.data;
}

export async function validateIntegration(
  provider: string,
): Promise<{ status: string; message: string }> {
  const response = await api.post(`/settings/integrations/${provider}/validate`);
  return response.data;
}

// === Gmail OAuth2 ===

export async function getGmailAuthUrl(): Promise<{ auth_url: string }> {
  const response = await api.get('/settings/integrations/gmail/auth-url');
  return response.data;
}

export async function disconnectGmail(): Promise<{ status: string; message: string }> {
  const response = await api.post('/settings/integrations/gmail/disconnect');
  return response.data;
}

export async function getGmailStatus(): Promise<GmailStatus> {
  const response = await api.get('/settings/integrations/gmail/status');
  return response.data;
}

// === Drive Config ===

export async function getDriveConfig(): Promise<DriveConfig> {
  const response = await api.get('/settings/integrations/drive/config');
  return response.data;
}

export async function updateDriveConfig(
  data: { search_folder_ids: string[]; storage_root_folder_id: string | null },
): Promise<{ status: string; message: string }> {
  const response = await api.put('/settings/integrations/drive/config', data);
  return response.data;
}

// === Dashboard ===

export interface DashboardStats {
  summary: {
    total_documents: number;
    completed_documents: number;
    failed_documents: number;
    skipped_documents: number;
    in_progress_documents: number;
    total_batches: number;
    total_candidates: number;
  };
  document_status: { status: string; count: number }[];
  batch_status: { status: string; count: number }[];
  ownership_verification: { status: string; count: number }[];
  daily_documents: { date: string; count: number }[];
  daily_batches: { date: string; count: number }[];
  document_types: { type: string; count: number }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get('/dashboard/stats');
  return response.data;
}

// === Dashboard ===

export interface DashboardStats {
  summary: {
    total_documents: number;
    completed_documents: number;
    failed_documents: number;
    skipped_documents: number;
    in_progress_documents: number;
    total_batches: number;
    total_candidates: number;
  };
  document_status: { status: string; count: number }[];
  batch_status: { status: string; count: number }[];
  ownership_verification: { status: string; count: number }[];
  daily_documents: { date: string; count: number }[];
  daily_batches: { date: string; count: number }[];
  document_types: { type: string; count: number }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get('/dashboard/stats');
  return response.data;
}

export async function startGoogleLogin(redirectUri?: string): Promise<GoogleAuthStartResponse> {
  const response = await api.get('/auth/google/start', {
    params: { redirect_uri: redirectUri },
  });
  return response.data;
}

export async function completeGoogleLogin(code: string, state: string): Promise<GoogleAuthCallbackResponse> {
  const response = await api.post('/auth/google/callback', { code, state });
  return response.data;
}

export async function logoutUser(): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/auth/logout');
  return response.data;
}

export async function startGoogleLogin(redirectUri?: string): Promise<GoogleAuthStartResponse> {
  const response = await api.get('/auth/google/start', {
    params: { redirect_uri: redirectUri },
  });
  return response.data;
}

export async function completeGoogleLogin(code: string, state: string): Promise<GoogleAuthCallbackResponse> {
  const response = await api.post('/auth/google/callback', { code, state });
  return response.data;
}

export async function logoutUser(): Promise<{ success: boolean; message: string }> {
  const response = await api.post('/auth/logout');
  return response.data;
}