import { useState, useEffect, useCallback, useRef } from 'react';
import {
  uploadBatchFile,
  startBatchProcessing,
  getBatchDetail,
  listBatchImports,
  getBatchLogs,
} from '../api/endpoints';
import { BatchImport, BatchCandidate, BatchLogEntry } from '../types';
import { useBatchWebSocket } from './useBatchWebSocket';

export function useBatchProcessing() {
  const [activeBatch, setActiveBatch] = useState<BatchImport | null>(null);
  const [batchCandidates, setBatchCandidates] = useState<BatchCandidate[]>([]);
  const [batchLogs, setBatchLogs] = useState<BatchLogEntry[]>([]);
  const [batchHistory, setBatchHistory] = useState<BatchImport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [batchUploading, setBatchUploading] = useState(false);
  const [processing, setProcessing] = useState(false);

  // WebSocket for real-time updates
  const { logs: wsLogs, candidateUpdates, summary } = useBatchWebSocket(
    processing && activeBatch ? activeBatch.id : null
  );

  // Merge WebSocket logs into batchLogs state (only when new logs arrive)
  useEffect(() => {
    if (wsLogs.length > 0) {
      setBatchLogs(wsLogs);
    }
  }, [wsLogs]);

  // Apply candidate status updates from WebSocket
  useEffect(() => {
    if (candidateUpdates.size === 0) return;
    setBatchCandidates((prev) =>
      prev.map((c) => {
        const update = candidateUpdates.get(c.id);
        if (update) {
          return { ...c, ...update };
        }
        return c;
      })
    );
  }, [candidateUpdates]);

  // Re-fetch final state from API when batch completes (WebSocket updates may be lost)
  const activeBatchIdRef = useRef<string | null>(null);
  activeBatchIdRef.current = activeBatch?.id ?? null;

  const refetchBatchState = useCallback(async (batchId: string) => {
    try {
      const detail = await getBatchDetail(batchId);
      setActiveBatch(detail.batch);
      setBatchCandidates(detail.candidates);
    } catch {
      // Ignore — WebSocket state is still usable
    }
  }, []);

  // Apply processing summary from WebSocket
  useEffect(() => {
    if (!summary || !activeBatchIdRef.current) return;
    setActiveBatch((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        processed_candidates: summary.completed,
        failed_candidates: summary.failed,
        status: summary.batch_status,
      };
    });

    // Stop processing when batch reaches terminal status
    const DONE = ['completed', 'completed_with_errors', 'failed'];
    if (DONE.includes(summary.batch_status)) {
      setProcessing(false);
      // Re-fetch from API to get accurate final state
      const batchId = activeBatchIdRef.current;
      if (batchId) {
        refetchBatchState(batchId);
      }
    }
  }, [summary, refetchBatchState]);

  const loadHistory = async () => {
    try {
      const history = await listBatchImports({ limit: 50 });
      setBatchHistory(history);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load batch history';
      setError(msg);
    }
  };

  const handleBatchUpload = async (file: File) => {
    setBatchUploading(true);
    setError(null);
    setActiveBatch(null);
    setBatchCandidates([]);
    setBatchLogs([]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await uploadBatchFile(formData);
      const detail = await getBatchDetail(response.batch_id);
      setActiveBatch(detail.batch);
      setBatchCandidates(detail.candidates);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Batch upload failed';
      setError(msg);
    } finally {
      setBatchUploading(false);
    }
  };

  const handleStartProcessing = async () => {
    if (!activeBatch) return;

    setProcessing(true);
    setError(null);
    setBatchLogs([]);

    try {
      await startBatchProcessing(activeBatch.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start processing';
      setError(msg);
      setProcessing(false);
    }
  };

  const viewBatchDetail = async (batchId: string) => {
    const detail = await getBatchDetail(batchId);
    setActiveBatch(detail.batch);
    setBatchCandidates(detail.candidates);
    const logs = await getBatchLogs(batchId);
    setBatchLogs(logs.map((l) => ({ ...l, type: l.level, status: l.stage })));
  };

  const resetBatch = () => {
    setActiveBatch(null);
    setBatchCandidates([]);
    setBatchLogs([]);
    setProcessing(false);
  };

  const clearLogs = () => setBatchLogs([]);

  return {
    activeBatch,
    batchCandidates,
    batchLogs,
    batchHistory,
    error,
    setError,
    batchUploading,
    processing,
    loadHistory,
    handleBatchUpload,
    handleStartProcessing,
    viewBatchDetail,
    resetBatch,
    clearLogs,
  };
}
