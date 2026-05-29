import api from './client';
import { UploadResponse, DocumentListItem, DocumentDetail, CandidateResponse, ProcessingTimeline, AuditLogEntry, HealthStatus, BatchInfo } from '../types';

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
