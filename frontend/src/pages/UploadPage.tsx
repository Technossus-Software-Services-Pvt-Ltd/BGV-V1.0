import { useState, useRef, useEffect } from 'react';
import { useBatchProcessing } from '../hooks/useBatchProcessing';
import BatchUploadSection from '../components/BatchUploadSection';
import BatchProcessingView from '../components/BatchProcessingView';
import BatchHistoryTab from '../components/BatchHistoryTab';

type TabView = 'upload' | 'history';

export default function UploadPage() {
  const [tab, setTab] = useState<TabView>('upload');
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

  useEffect(() => {
    if (tab === 'history') {
      loadHistory();
    }
  }, [tab]);

  const onBatchUpload = async () => {
    if (!batchFile) return;
    await handleBatchUpload(batchFile);
    setBatchFile(null);
  };

  const handleViewBatch = async (batchId: string) => {
    await viewBatchDetail(batchId);
    setTab('upload');
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

      {/* Hidden file input for header button */}
      <input
        ref={batchFileInputRef}
        type="file"
        accept=".xlsx,.csv"
        onChange={(e) => {
          if (e.target.files?.[0]) setBatchFile(e.target.files[0]);
        }}
        className="hidden"
      />

      {error && (
        <div className="bg-rose-50 border border-rose-200/60 rounded-xl p-4">
          <p className="text-sm text-rose-700 font-medium">{error}</p>
        </div>
      )}

      {tab === 'upload' && (
        <div className="space-y-6">
          {!activeBatch && (
            <BatchUploadSection
              batchFile={batchFile}
              setBatchFile={setBatchFile}
              batchUploading={batchUploading}
              onUpload={onBatchUpload}
            />
          )}

          {activeBatch && (
            <BatchProcessingView
              activeBatch={activeBatch}
              batchCandidates={batchCandidates}
              batchLogs={batchLogs}
              clearLogs={clearLogs}
            />
          )}
        </div>
      )}

      {tab === 'history' && (
        <BatchHistoryTab
          batchHistory={batchHistory}
          onViewBatch={handleViewBatch}
        />
      )}
    </div>
  );
}
