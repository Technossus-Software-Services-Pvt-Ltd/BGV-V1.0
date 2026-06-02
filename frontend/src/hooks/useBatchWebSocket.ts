import { useEffect, useRef, useState, useCallback } from 'react';
import { BatchWebSocketService } from '../services/websocket';
import { BatchCandidate, BatchLogEntry } from '../types';

export interface ProcessingSummaryData {
  total: number;
  completed: number;
  failed: number;
  in_progress: number;
  partial: number;
  pending: number;
  no_documents: number;
  batch_status: string;
}

interface UseBatchWebSocketReturn {
  logs: BatchLogEntry[];
  candidateUpdates: Map<string, Partial<BatchCandidate>>;
  summary: ProcessingSummaryData | null;
  connected: boolean;
}

/**
 * React hook for real-time batch processing updates via WebSocket.
 * Connects when batchId is provided, disconnects on unmount or batchId change.
 */
export function useBatchWebSocket(batchId: string | null): UseBatchWebSocketReturn {
  const wsRef = useRef<BatchWebSocketService | null>(null);
  const [logs, setLogs] = useState<BatchLogEntry[]>([]);
  const [candidateUpdates, setCandidateUpdates] = useState<Map<string, Partial<BatchCandidate>>>(
    new Map()
  );
  const [summary, setSummary] = useState<ProcessingSummaryData | null>(null);
  const [connected, setConnected] = useState(false);

  const MAX_LOGS = 500;

  const handleLog = useCallback((data: Record<string, unknown>) => {
    const logEntry: BatchLogEntry = {
      id: data.id as string,
      level: data.level as string,
      stage: data.stage as string,
      message: data.message as string,
      details: (data.details as string) || null,
      batch_candidate_id: (data.batch_candidate_id as string) || null,
      created_at: data.created_at as string,
      type: data.level as string,
      status: data.stage as string,
    };
    setLogs((prev) => {
      const next = [...prev, logEntry];
      return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
    });
  }, []);

  const handleCandidateStatus = useCallback((data: Record<string, unknown>) => {
    const candidateId = data.candidate_id as string;
    const update: Partial<BatchCandidate> = {
      id: candidateId,
      status: data.status as string,
      documents_found: data.documents_found as number,
      documents_processed: data.documents_processed as number,
      documents_failed: data.documents_failed as number,
      error_message: (data.error_message as string) || null,
    };
    setCandidateUpdates((prev) => {
      const next = new Map(prev);
      next.set(candidateId, update);
      return next;
    });
  }, []);

  const handleSummary = useCallback((data: Record<string, unknown>) => {
    setSummary({
      total: data.total as number,
      completed: data.completed as number,
      failed: data.failed as number,
      in_progress: data.in_progress as number,
      partial: data.partial as number,
      pending: data.pending as number,
      no_documents: data.no_documents as number,
      batch_status: data.batch_status as string,
    });
  }, []);

  useEffect(() => {
    if (!batchId) {
      // No batch to track — cleanup if needed
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
      setConnected(false);
      return;
    }

    // Reset state for new batch
    setLogs([]);
    setCandidateUpdates(new Map());
    setSummary(null);

    const ws = new BatchWebSocketService();
    wsRef.current = ws;

    ws.on('connected', () => setConnected(true));
    ws.on('disconnected', () => setConnected(false));
    ws.on('processing-log', handleLog);
    ws.on('candidate-status-updated', handleCandidateStatus);
    ws.on('processing-summary-updated', handleSummary);

    ws.connect(batchId);

    return () => {
      ws.disconnect();
      wsRef.current = null;
      setConnected(false);
    };
  }, [batchId, handleLog, handleCandidateStatus, handleSummary]);

  return { logs, candidateUpdates, summary, connected };
}
