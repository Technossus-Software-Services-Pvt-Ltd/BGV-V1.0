import api from './client';
import { getSessionToken } from '../utils/auth';
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
  RequiredDocumentRule,
  RequiredDocumentChecklistSaveRequest,
  FileNamingRule,
  FileNamingRuleSaveRequest,
  ReviewQueueItem,
  ReviewQueueResponse,
  NotificationLogItem,
  DashboardStats,
} from '../types';
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
  date_from?: string;
  date_to?: string;
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
  date_from?: string;
  date_to?: string;
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

export function createBatchLogStream(batchId: string): { close: () => void; onMessage: (handler: (event: string, data: string) => void) => void } {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const token = getSessionToken();
  const url = `${baseUrl}/batch/${batchId}/logs`;

  let aborted = false;
  const controller = new AbortController();
  let messageHandler: ((event: string, data: string) => void) | null = null;

  // Use fetch with Authorization header instead of EventSource (which can't set headers)
  (async () => {
    try {
      const response = await fetch(url, {
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
          'Accept': 'text/event-stream',
        },
        signal: controller.signal,
      });

      if (!response.ok || !response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (!aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = 'message';
        let dataLines: string[] = [];

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trim());
          } else if (line === '' && dataLines.length > 0) {
            messageHandler?.(currentEvent, dataLines.join('\n'));
            currentEvent = 'message';
            dataLines = [];
          }
        }
      }
    } catch {
      // Connection closed or aborted
    }
  })();

  return {
    close: () => {
      aborted = true;
      controller.abort();
    },
    onMessage: (handler) => {
      messageHandler = handler;
    },
  };
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

export async function listRequiredDocuments(): Promise<RequiredDocumentRule[]> {
  const response = await api.get('/settings/required-documents');
  return response.data;
}

export async function saveRequiredDocuments(
  data: RequiredDocumentChecklistSaveRequest,
): Promise<RequiredDocumentRule[]> {
  const response = await api.put('/settings/required-documents', data);
  return response.data;
}

export async function getFileNamingRule(): Promise<FileNamingRule> {
  const response = await api.get('/settings/file-naming');
  return response.data;
}

export async function saveFileNamingRule(
  data: FileNamingRuleSaveRequest,
): Promise<FileNamingRule> {
  const response = await api.put('/settings/file-naming', data);
  return response.data;
}

// === Dashboard ===

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

export async function getReviewQueue(params?: {
  skip?: number;
  limit?: number;
  search?: string;
  status?: string;
}): Promise<ReviewQueueResponse> {
  const response = await api.get('/review-queue', { params });
  return response.data;
}

export async function notifyReviewCandidates(candidateIds: string[]): Promise<{ queued: number; skipped: number; message: string }> {
  const response = await api.post('/review-queue/notify', { candidate_ids: candidateIds });
  return response.data;
}

export async function getNotificationHistory(candidateId: string): Promise<NotificationLogItem[]> {
  const response = await api.get(`/review-queue/notifications/${candidateId}`);
  return response.data;
}

export async function retryNotification(notificationId: string): Promise<{ message: string }> {
  const response = await api.post(`/review-queue/notify/retry/${notificationId}`);
  return response.data;
}