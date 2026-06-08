import { useState, useRef, useEffect } from 'react';
import { uploadDocuments } from '../api/endpoints';
import { UploadResponse } from '../types';
import { Link } from 'react-router-dom';
import ProcessingSummary from '../components/ProcessingSummary';
import LiveExecutionLogs from '../components/LiveExecutionLogs';
import { useBatchProcessing } from '../hooks/useBatchProcessing';

type TabView = 'upload' | 'history';

export default function UploadPage() {
  const [tab, setTab] = useState<TabView>('upload');

  // --- Manual upload state (legacy) ---
  const [candidateId, setCandidateId] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [manualResult, setManualResult] = useState<UploadResponse | null>(null);

  // --- Batch upload state (extracted hook) ---
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const {
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
  } = useBatchProcessing();

  const batchFileInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load batch history
  useEffect(() => {
    if (tab === 'history') {
      loadHistory();
    }
  }, [tab]);

  // --- Batch upload handler ---
  const onBatchUpload = async () => {
    if (!batchFile) return;
    await handleBatchUpload(batchFile);
    setBatchFile(null);
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
      case 'completed': return 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/10';
      case 'partial': return 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/10';
      case 'awaiting_required_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
      case 'processing': case 'discovering': case 'downloading': return 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/10';
      case 'failed': return 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10';
      case 'pending': return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
      case 'skipped': case 'no_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
      default: return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ====== HEADER ====== */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-primary-50 flex items-center justify-center">
              <svg className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">Upload Candidate Excel</h1>
              <p className="text-sm text-gray-500">Upload an Excel file with Candidate ID, Name, Email, etc. to start candidate verification</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-gray-100/80 rounded-xl p-1">
              <button
                onClick={() => setTab('upload')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${tab === 'upload' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-900'}`}>
                New Import
              </button>
              <button
                onClick={() => setTab('history')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${tab === 'history' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-900'}`}>
                History
              </button>
            </div>
            {tab === 'upload' && (
              <button
                onClick={() => {
                  if (activeBatch) {
                    resetBatch();
                  }
                  batchFileInputRef.current?.click();
                }}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-gray-900 text-white hover:bg-gray-800 transition-colors"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                  <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Upload Excel
              </button>
            )}
            {activeBatch && tab === 'upload' && (
              <button
                onClick={handleStartProcessing}
                disabled={processing || activeBatch.status !== 'parsed'}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                  <path d="M8 5v14l11-7z" />
                </svg>
                {processing ? 'Processing...' : 'Start Processing'}
              </button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-rose-50 border border-rose-200/60 rounded-xl p-4">
          <p className="text-sm text-rose-700 font-medium">{error}</p>
        </div>
      )}

      {tab === 'upload' && (
        <div className="space-y-6">
          {/* ====== FILE UPLOAD AREA (when no active batch) ====== */}
          {!activeBatch && (
            <div className="card">
              <div
                onClick={() => batchFileInputRef.current?.click()}
                className="border-2 border-dashed border-gray-200 rounded-2xl p-10 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/30 transition-all duration-200 group"
              >
                <div className="mx-auto h-14 w-14 rounded-2xl bg-gray-100 group-hover:bg-primary-100 flex items-center justify-center transition-colors mb-3">
                  <svg className="h-7 w-7 text-gray-400 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
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
                    onClick={onBatchUpload}
                    disabled={batchUploading}
                    className="btn-primary"
                  >
                    {batchUploading ? 'Uploading...' : 'Upload & Parse'}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ====== PROCESSING VIEW (3-column layout) ====== */}
          {activeBatch && (
            <>
              {/* Progress Bar - Full Width */}
              <div className="card p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">Processing Progress</span>
                  <span className="text-sm text-gray-500 tabular-nums">
                    {activeBatch.processed_candidates + activeBatch.failed_candidates + activeBatch.skipped_candidates} / {activeBatch.total_candidates} candidates
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2.5">
                  <div
                    className="bg-gradient-to-r from-emerald-500 to-emerald-600 h-2.5 rounded-full transition-all duration-500"
                    style={{ width: `${activeBatch.total_candidates > 0 ? Math.round(((activeBatch.processed_candidates + activeBatch.failed_candidates + activeBatch.skipped_candidates) / activeBatch.total_candidates) * 100) : 0}%` }}
                  />
                </div>
              </div>

              {/* 3-Column Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left: Processing Summary */}
                <div className="lg:col-span-3">
                  <div className="card">
                    <ProcessingSummary batch={activeBatch} candidates={batchCandidates} />
                  </div>
                </div>

                {/* Center: Candidate Table */}
                <div className="lg:col-span-5">
                  <div className="card overflow-hidden p-0">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                      <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 text-gray-400">
                          <rect x="3" y="3" width="18" height="18" rx="2" />
                          <path d="M3 9h18M9 21V9" />
                        </svg>
                        Candidate Processing Status
                      </h3>
                      <span className="text-xs text-gray-500 font-medium px-2.5 py-1 rounded-full border border-gray-200">{batchCandidates.length} records</span>
                    </div>
                    <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 z-10">
                          <tr className="border-b border-gray-100 bg-gray-50/80">
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">ID</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Docs</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {batchCandidates.map((c) => (
                            <tr key={c.id} className="hover:bg-gray-50/50 transition-colors">
                              <td className="px-4 py-3 text-xs font-mono text-gray-600">{c.source_candidate_id}</td>
                              <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.source_name}</td>
                              <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-[140px]">{c.source_email || '—'}</td>
                              <td className="px-4 py-3">
                                <span className={`inline-block px-2 py-0.5 rounded-lg text-xs font-semibold ${statusColor(c.status)}`}>
                                  {c.status === 'awaiting_required_documents' ? 'Awaiting' : c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-500 tabular-nums">
                                {c.documents_found > 0 ? `${c.documents_processed}/${c.documents_found}` : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {/* Right: Live Execution Logs */}
                <div className="lg:col-span-4">
                  <div className="card p-4">
                    <LiveExecutionLogs logs={batchLogs} onClear={clearLogs} />
                  </div>
                </div>
              </div>
            </>
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
                  className="border-2 border-dashed border-gray-200 rounded-2xl p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/30 transition-all duration-200 group"
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
          <h2 className="text-base font-semibold text-gray-900 mb-4">Import History</h2>
          {batchHistory.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-12">No batch imports yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/80">
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Batch</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">File</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidates</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Documents</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {batchHistory.map((b) => (
                    <tr key={b.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-3.5 text-sm font-medium text-gray-900">{b.batch_code}</td>
                      <td className="px-4 py-3.5 text-sm text-gray-500">{b.original_filename}</td>
                      <td className="px-4 py-3.5">
                        <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-semibold ${statusColor(b.status)}`}>
                          {b.status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-gray-500">
                        {b.processed_candidates}/{b.total_candidates}
                        {b.failed_candidates > 0 && <span className="text-rose-500 ml-1">({b.failed_candidates} failed)</span>}
                      </td>
                      <td className="px-4 py-3.5 text-sm text-gray-500">{b.total_documents_processed}/{b.total_documents_found}</td>
                      <td className="px-4 py-3.5 text-sm text-gray-400">{new Date(b.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3.5">
                        <button
                          onClick={async () => {
                            await viewBatchDetail(b.id);
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
