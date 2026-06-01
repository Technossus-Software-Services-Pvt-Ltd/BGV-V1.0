import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { getDocumentDetail, getProcessingTimeline } from '../api/endpoints';
import { DocumentDetail, ProcessingTimeline } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import OCRResultViewer from '../components/OCRResultViewer';
import ClassificationViewer from '../components/ClassificationViewer';
import ValidationResultViewer from '../components/ValidationResultViewer';
import ProcessingTimelineView from '../components/ProcessingTimelineView';

const TERMINAL_STATUSES = ['completed', 'failed', 'ocr_failed', 'skipped'];

const TAB_CONFIG = [
  { key: 'ocr' as const, label: 'OCR', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { key: 'classification' as const, label: 'Classification', icon: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z' },
  { key: 'validation' as const, label: 'Validation', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'timeline' as const, label: 'Timeline', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
];

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [timeline, setTimeline] = useState<ProcessingTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'ocr' | 'classification' | 'validation' | 'timeline'>('ocr');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = async (showLoading = true) => {
    if (!documentId) return;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const [docDetail, timelineData] = await Promise.allSettled([
        getDocumentDetail(documentId),
        getProcessingTimeline(documentId),
      ]);

      if (docDetail.status === 'fulfilled') setDetail(docDetail.value);
      else throw new Error('Failed to load document');

      if (timelineData.status === 'fulfilled') setTimeline(timelineData.value);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document detail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [documentId]);

  // Auto-poll while processing is in progress
  useEffect(() => {
    if (detail && !TERMINAL_STATUSES.includes(detail.document.processing_status)) {
      pollRef.current = setInterval(() => loadData(false), 5000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [detail?.document.processing_status]);

  if (loading) return <LoadingSpinner message="Loading document details..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;
  if (!detail) return <ErrorMessage message="Document not found" />;

  const { document: doc } = detail;

  const processingPercent = (() => {
    const stages = ['uploaded', 'normalizing', 'normalized', 'ocr_processing', 'ocr_complete', 'classifying', 'classified', 'validating', 'validated', 'completed'];
    const idx = stages.indexOf(doc.processing_status);
    if (idx < 0) return doc.processing_status === 'failed' ? 100 : 0;
    return Math.round(((idx + 1) / stages.length) * 100);
  })();

  const isProcessing = !TERMINAL_STATUSES.includes(doc.processing_status);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Back + Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => window.history.length > 1 ? window.history.back() : window.location.assign('/batch-history')}
          className="mt-1 shrink-0 h-9 w-9 rounded-xl bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors"
        >
          <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-gray-900 tracking-tight truncate">{doc.original_filename}</h1>
            <StatusBadge status={doc.processing_status} />
          </div>
          <p className="text-sm text-gray-400 mt-0.5">
            {detail.candidate_name && <span className="font-medium text-gray-600">{detail.candidate_name}</span>}
            {detail.candidate_name && ' \u00b7 '}
            <span className="font-mono text-xs">{doc.correlation_id}</span>
          </p>
        </div>
      </div>

      {/* Top summary strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
        <MetaCard label="File Size" value={formatFileSize(doc.file_size_bytes)} />
        <MetaCard label="Format" value={doc.mime_type.split('/').pop()?.toUpperCase() || doc.mime_type} />
        <MetaCard label="Pages" value={String(detail.pages.length)} />
        <MetaCard label="Created" value={new Date(doc.created_at).toLocaleDateString()} />
        {isProcessing && (
          <div className="rounded-xl border border-primary-100 bg-primary-50/50 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-primary-400 mb-1">Progress</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-primary-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-700"
                  style={{ width: `${processingPercent}%` }}
                />
              </div>
              <span className="text-xs font-bold text-primary-700 tabular-nums">{processingPercent}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-100 overflow-x-auto">
        {TAB_CONFIG.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === key
                ? 'border-primary-600 text-primary-700'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
            </svg>
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[200px]">
        {activeTab === 'ocr' && <OCRResultViewer results={detail.ocr_results} />}
        {activeTab === 'classification' && <ClassificationViewer classifications={detail.classifications} />}
        {activeTab === 'validation' && <ValidationResultViewer results={detail.validation_results} />}
        {activeTab === 'timeline' && timeline && (
          <ProcessingTimelineView
            events={timeline.events}
            currentStatus={timeline.current_status}
            totalDurationMs={timeline.total_duration_ms}
          />
        )}
        {activeTab === 'timeline' && !timeline && (
          <div className="card text-center py-12">
            <div className="mx-auto h-10 w-10 rounded-2xl bg-gray-100 flex items-center justify-center mb-3">
              <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm text-gray-500 font-medium">No processing events recorded yet</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">{label}</p>
      <p className="text-sm font-bold text-gray-900 truncate">{value}</p>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
