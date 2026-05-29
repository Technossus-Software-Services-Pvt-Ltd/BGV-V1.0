import { useState, useRef, useEffect, useCallback } from 'react';
import { uploadDocuments } from '../api/endpoints';
import {
  uploadBatchFile,
  startBatchProcessing,
  getBatchDetail,
  listBatchImports,
  retryBatchCandidate,
  createBatchLogStream,
} from '../api/endpoints';
import { UploadResponse, BatchImport, BatchCandidate, BatchLogEntry } from '../types';
import { Link } from 'react-router-dom';

type TabView = 'upload' | 'history';

export default function UploadPage() {
  const [tab, setTab] = useState<TabView>('upload');

  // --- Manual upload state (legacy) ---
  const [candidateId, setCandidateId] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [manualResult, setManualResult] = useState<UploadResponse | null>(null);

  // --- Batch upload state ---
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchUploading, setBatchUploading] = useState(false);
  const [activeBatch, setActiveBatch] = useState<BatchImport | null>(null);
  const [batchCandidates, setBatchCandidates] = useState<BatchCandidate[]>([]);
  const [batchLogs, setBatchLogs] = useState<BatchLogEntry[]>([]);
  const [batchHistory, setBatchHistory] = useState<BatchImport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const batchFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Load batch history
  useEffect(() => {
    if (tab === 'history') {
      listBatchImports({ limit: 50 }).then(setBatchHistory).catch(() => {});
    }
  }, [tab]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [batchLogs]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const connectSSE = useCallback((batchId: string) => {
    eventSourceRef.current?.close();
    const es = createBatchLogStream(batchId);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data: BatchLogEntry = JSON.parse(event.data);
        setBatchLogs((prev) => [...prev, data]);

        // If batch completed/failed, refresh detail and close SSE
        if (data.type === 'batch_status' && (data.status === 'completed' || data.status === 'failed' || data.status === 'completed_with_errors')) {
          refreshBatchDetail(batchId);
          es.close();
          setProcessing(false);
        }
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
      setProcessing(false);
    };
  }, []);

  const refreshBatchDetail = async (batchId: string) => {
    try {
      const detail = await getBatchDetail(batchId);
      setActiveBatch(detail.batch);
      setBatchCandidates(detail.candidates);
    } catch {
      // silent
    }
  };

  // --- Batch upload handler ---
  const handleBatchUpload = async () => {
    if (!batchFile) return;

    setBatchUploading(true);
    setError(null);
    setActiveBatch(null);
    setBatchCandidates([]);
    setBatchLogs([]);

    try {
      const formData = new FormData();
      formData.append('file', batchFile);

      const response = await uploadBatchFile(formData);
      // Fetch full batch detail
      const detail = await getBatchDetail(response.batch_id);
      setActiveBatch(detail.batch);
      setBatchCandidates(detail.candidates);
      setBatchFile(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Batch upload failed';
      setError(msg);
    } finally {
      setBatchUploading(false);
    }
  };

  // --- Start processing ---
  const handleStartProcessing = async () => {
    if (!activeBatch) return;

    setProcessing(true);
    setError(null);
    setBatchLogs([]);

    try {
      await startBatchProcessing(activeBatch.id);
      connectSSE(activeBatch.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start processing';
      setError(msg);
      setProcessing(false);
    }
  };

  // --- Retry candidate ---
  const handleRetryCandidate = async (candidateId: string) => {
    if (!activeBatch) return;
    try {
      await retryBatchCandidate(activeBatch.id, candidateId);
      refreshBatchDetail(activeBatch.id);
    } catch {
      // silent
    }
  };

  // --- Manual upload handler ---
  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateId || !candidateName || files.length === 0) return;

    setUploading(true);
    setError(null);
    setManualResult(null);

    try {
      const formData = new FormData();
      formData.append('candidate_id', candidateId);
      formData.append('candidate_name', candidateName);
      files.forEach((file) => formData.append('files', file));

      const response = await uploadDocuments(formData);
      setManualResult(response);
      setFiles([]);
      setCandidateId('');
      setCandidateName('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'processing': case 'discovering': case 'downloading': return 'bg-blue-100 text-blue-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'pending': return 'bg-gray-100 text-gray-700';
      case 'skipped': case 'no_documents': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const logLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'text-red-600';
      case 'warning': return 'text-yellow-600';
      case 'info': return 'text-blue-600';
      default: return 'text-gray-600';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Upload Documents</h1>
        <div className="flex bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => setTab('upload')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === 'upload' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            New Import
          </button>
          <button
            onClick={() => setTab('history')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              tab === 'history' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            History
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {tab === 'upload' && (
        <div className="space-y-6">
          {/* ====== BATCH IMPORT SECTION ====== */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Batch Import</h2>
            <p className="text-sm text-gray-500 mb-4">
              Upload an Excel or CSV file with candidate details. Documents will be auto-discovered from Gmail and Google Drive.
            </p>

            {!activeBatch && (
              <>
                <div
                  onClick={() => batchFileInputRef.current?.click()}
                  className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/30 transition-colors"
                >
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600">
                    {batchFile ? batchFile.name : 'Click to select an Excel (.xlsx) or CSV file'}
                  </p>
                  <p className="mt-1 text-xs text-gray-400">
                    Required columns: candidate_id, name. Optional: email, phone, dob, gender
                  </p>
                </div>

                <input
                  ref={batchFileInputRef}
                  type="file"
                  accept=".xlsx,.csv"
                  onChange={(e) => {
                    if (e.target.files?.[0]) setBatchFile(e.target.files[0]);
                  }}
                  className="hidden"
                />

                {batchFile && (
                  <div className="mt-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700">{batchFile.name}</span>
                      <span className="text-xs text-gray-400">({(batchFile.size / 1024).toFixed(0)} KB)</span>
                      <button onClick={() => setBatchFile(null)} className="text-gray-400 hover:text-red-500 text-xs ml-2">Remove</button>
                    </div>
                    <button
                      onClick={handleBatchUpload}
                      disabled={batchUploading}
                      className="btn-primary"
                    >
                      {batchUploading ? 'Uploading...' : 'Upload & Parse'}
                    </button>
                  </div>
                )}
              </>
            )}

            {/* Batch Summary */}
            {activeBatch && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{activeBatch.original_filename}</h3>
                    <p className="text-xs text-gray-500">
                      Batch: {activeBatch.batch_code} | Status: <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(activeBatch.status)}`}>{activeBatch.status}</span>
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {activeBatch.status === 'parsed' && (
                      <button onClick={handleStartProcessing} disabled={processing} className="btn-primary">
                        {processing ? 'Processing...' : 'Start Processing'}
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setActiveBatch(null);
                        setBatchCandidates([]);
                        setBatchLogs([]);
                        eventSourceRef.current?.close();
                      }}
                      className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg"
                    >
                      New Import
                    </button>
                  </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-gray-900">{activeBatch.total_candidates}</p>
                    <p className="text-xs text-gray-500">Total Candidates</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-green-700">{activeBatch.processed_candidates}</p>
                    <p className="text-xs text-gray-500">Processed</p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-red-700">{activeBatch.failed_candidates}</p>
                    <p className="text-xs text-gray-500">Failed</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-blue-700">{activeBatch.total_documents_found}</p>
                    <p className="text-xs text-gray-500">Documents Found</p>
                  </div>
                </div>

                {/* Progress bar */}
                {activeBatch.total_candidates > 0 && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary-600 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${Math.round(((activeBatch.processed_candidates + activeBatch.failed_candidates + activeBatch.skipped_candidates) / activeBatch.total_candidates) * 100)}%` }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Candidates Table */}
          {batchCandidates.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Candidates ({batchCandidates.length})</h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Candidate ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Docs</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {batchCandidates.map((c) => (
                      <tr key={c.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-500">{c.row_number}</td>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.source_candidate_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{c.source_name}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{c.source_email || '—'}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(c.status)}`}>
                            {c.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {c.documents_found > 0 ? `${c.documents_processed}/${c.documents_found}` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {c.status === 'failed' && (
                            <button
                              onClick={() => handleRetryCandidate(c.id)}
                              className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                            >
                              Retry
                            </button>
                          )}
                          {c.candidate_id && (
                            <Link to={`/candidates`} className="text-xs text-primary-600 hover:underline ml-2">
                              View
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Live Logs */}
          {batchLogs.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Processing Logs</h2>
              <div className="bg-gray-900 rounded-lg p-4 max-h-80 overflow-y-auto font-mono text-xs">
                {batchLogs.map((log, i) => (
                  <div key={i} className="py-0.5">
                    <span className="text-gray-500">{log.created_at ? new Date(log.created_at).toLocaleTimeString() : ''}</span>
                    {' '}
                    <span className={logLevelColor(log.level || 'info')}>[{(log.level || 'info').toUpperCase()}]</span>
                    {' '}
                    <span className="text-gray-300">{log.stage || ''}</span>
                    {' — '}
                    <span className="text-gray-100">{log.message || ''}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}

          {/* ====== MANUAL UPLOAD SECTION (Collapsed) ====== */}
          <details className="card">
            <summary className="cursor-pointer text-sm font-medium text-gray-600 hover:text-gray-900">
              Manual Single-Candidate Upload
            </summary>
            <div className="mt-4 space-y-4">
              {manualResult && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-green-800 mb-2">Upload Successful</h3>
                  <p className="text-sm text-green-700">{manualResult.message}</p>
                  <p className="text-xs text-green-600 mt-1">
                    Batch: {manualResult.batch_reference} | Correlation: {manualResult.correlation_id}
                  </p>
                  <div className="mt-3 flex gap-2">
                    {manualResult.documents.map((doc) => (
                      <Link key={doc.id} to={`/documents/${doc.id}`} className="text-xs text-primary-600 hover:underline">
                        {doc.filename}
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              <form onSubmit={handleManualSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Candidate ID *</label>
                    <input type="text" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} className="input-field" placeholder="e.g., CAND-001" required />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
                    <input type="text" value={candidateName} onChange={(e) => setCandidateName(e.target.value)} className="input-field" placeholder="e.g., Rajesh Kumar" required />
                  </div>
                </div>

                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-primary-400 transition-colors"
                >
                  <p className="text-sm text-gray-600">Click to select document files</p>
                  <p className="text-xs text-gray-400">PDF, JPEG, PNG up to 15MB each. Max 20 files.</p>
                </div>
                <input ref={fileInputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png" aria-label="Select document files" onChange={(e) => { if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)].slice(0, 20)); }} className="hidden" />

                {files.length > 0 && (
                  <div className="space-y-1">
                    {files.map((file, index) => (
                      <div key={index} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded">
                        <span className="text-sm text-gray-700 truncate">{file.name}</span>
                        <button type="button" onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))} className="text-gray-400 hover:text-red-500 text-xs">Remove</button>
                      </div>
                    ))}
                  </div>
                )}

                <div className="flex justify-end">
                  <button type="submit" disabled={uploading || !candidateId || !candidateName || files.length === 0} className="btn-primary">
                    {uploading ? 'Uploading...' : `Upload ${files.length} Document${files.length !== 1 ? 's' : ''}`}
                  </button>
                </div>
              </form>
            </div>
          </details>
        </div>
      )}

      {/* ====== BATCH HISTORY TAB ====== */}
      {tab === 'history' && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Import History</h2>
          {batchHistory.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">No batch imports yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batch</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">File</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Candidates</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Documents</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {batchHistory.map((b) => (
                    <tr key={b.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{b.batch_code}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{b.original_filename}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(b.status)}`}>
                          {b.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {b.processed_candidates}/{b.total_candidates}
                        {b.failed_candidates > 0 && <span className="text-red-500 ml-1">({b.failed_candidates} failed)</span>}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">{b.total_documents_processed}/{b.total_documents_found}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">{new Date(b.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={async () => {
                            const detail = await getBatchDetail(b.id);
                            setActiveBatch(detail.batch);
                            setBatchCandidates(detail.candidates);
                            setBatchLogs([]);
                            setTab('upload');
                          }}
                          className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
