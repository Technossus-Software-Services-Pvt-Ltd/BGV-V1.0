import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getDocumentDetail, getProcessingTimeline } from '../api/endpoints';
import { DocumentDetail, ProcessingTimeline } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import OCRResultViewer from '../components/OCRResultViewer';
import ClassificationViewer from '../components/ClassificationViewer';
import ValidationResultViewer from '../components/ValidationResultViewer';
import ProcessingTimelineView from '../components/ProcessingTimelineView';

const TERMINAL_STATUSES = ['completed', 'failed', 'ocr_failed'];

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/documents" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{doc.original_filename}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {detail.candidate_name && <span className="font-medium text-gray-700">{detail.candidate_name}</span>}
            {detail.candidate_name && ' · '}
            Correlation: {doc.correlation_id}
          </p>
        </div>
        <div className="ml-auto">
          <StatusBadge status={doc.processing_status} />
        </div>
      </div>

      {/* Document Metadata */}
      <div className="card">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetaItem label="File Size" value={formatFileSize(doc.file_size_bytes)} />
          <MetaItem label="MIME Type" value={doc.mime_type} />
          <MetaItem label="Pages" value={String(detail.pages.length)} />
          <MetaItem label="Created" value={new Date(doc.created_at).toLocaleString()} />
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {(['ocr', 'classification', 'validation', 'timeline'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-2 px-1 text-sm font-medium border-b-2 transition-colors capitalize ${
                activeTab === tab
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'ocr' ? 'OCR Results' : tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
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
        <div className="card">
          <p className="text-sm text-gray-500">No processing events recorded yet.</p>
        </div>
      )}
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-medium text-gray-900 mt-0.5">{value}</p>
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
