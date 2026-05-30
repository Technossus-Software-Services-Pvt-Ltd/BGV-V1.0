import { useEffect, useState, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { listDocuments, listBatches } from '../api/endpoints';
import { DocumentListItem, BatchInfo } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [batches, setBatches] = useState<BatchInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const [docsData, batchData] = await Promise.all([
        listDocuments({ limit: 100 }),
        listBatches({ limit: 100 }),
      ]);
      setDocuments(docsData);
      setBatches(batchData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Auto-poll every 5 seconds if any document is still processing
  useEffect(() => {
    const hasProcessing = documents.some(
      (doc) => !['completed', 'failed', 'ocr_failed', 'skipped'].includes(doc.processing_status)
    );
    if (hasProcessing) {
      pollRef.current = setInterval(() => loadData(false), 5000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [documents]);

  // Group documents by batch
  const { batchGroups, ungroupedDocs } = useMemo(() => {
    const filteredDocs = documents;

    const byBatch = new Map<string, DocumentListItem[]>();
    const ungrouped: DocumentListItem[] = [];

    for (const doc of filteredDocs) {
      if (doc.upload_batch_id) {
        const list = byBatch.get(doc.upload_batch_id) || [];
        list.push(doc);
        byBatch.set(doc.upload_batch_id, list);
      } else {
        ungrouped.push(doc);
      }
    }

    // Match batch info to grouped docs, sort by newest first
    const batchMap = new Map(batches.map((b) => [b.id, b]));
    const groups: { batch: BatchInfo; docs: DocumentListItem[] }[] = [];

    for (const [batchId, docs] of byBatch) {
      const batchInfo = batchMap.get(batchId);
      if (batchInfo) {
        groups.push({ batch: batchInfo, docs });
      } else {
        // Batch info not found — synthesize a minimal one from docs
        groups.push({
          batch: {
            id: batchId,
            candidate_id: docs[0]?.candidate_id || '',
            batch_reference: batchId.slice(0, 8).toUpperCase(),
            total_files: docs.length,
            processed_files: docs.filter((d) => d.processing_status === 'completed').length,
            failed_files: docs.filter((d) => ['failed', 'ocr_failed'].includes(d.processing_status)).length,
            processing_status: docs.every((d) => d.processing_status === 'completed') ? 'completed' : 'processing',
            correlation_id: docs[0]?.correlation_id || '',
            created_at: docs[0]?.created_at || '',
            updated_at: docs[0]?.updated_at || '',
          },
          docs,
        });
      }
    }

    groups.sort((a, b) => new Date(b.batch.created_at).getTime() - new Date(a.batch.created_at).getTime());
    return { batchGroups: groups, ungroupedDocs: ungrouped };
  }, [documents, batches]);

  // Stats
  const stats = useMemo(() => {
    const total = documents.length;
    const completed = documents.filter((d) => d.processing_status === 'completed').length;
    const failed = documents.filter((d) => ['failed', 'ocr_failed'].includes(d.processing_status)).length;
    const processing = total - completed - failed;
    return { total, completed, failed, processing, batches: batches.length };
  }, [documents, batches]);

  const toggleBatch = (batchId: string) => {
    setExpandedBatches((prev) => {
      const next = new Set(prev);
      if (next.has(batchId)) next.delete(batchId);
      else next.add(batchId);
      return next;
    });
  };

  const expandAll = () => setExpandedBatches(new Set(batchGroups.map((g) => g.batch.id)));
  const collapseAll = () => setExpandedBatches(new Set());

  if (loading) return <LoadingSpinner message="Loading documents..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;

  const totalGroups = batchGroups.length + (ungroupedDocs.length > 0 ? 1 : 0);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Documents</h1>
          <p className="mt-1 text-sm text-gray-500">
            {stats.batches} batches &middot; {stats.total} documents &mdash; {stats.completed} completed, {stats.processing} in progress, {stats.failed} failed
          </p>
        </div>
        <Link to="/upload" className="btn-primary shrink-0">
          Upload New
        </Link>
      </div>

      {/* Expand / Collapse toggle */}
      {totalGroups > 1 && (
        <div className="flex justify-end gap-2">
          <button onClick={expandAll} className="text-xs text-primary-600 hover:text-primary-700 font-semibold">
            Expand All
          </button>
          <span className="text-gray-300">|</span>
          <button onClick={collapseAll} className="text-xs text-primary-600 hover:text-primary-700 font-semibold">
            Collapse All
          </button>
        </div>
      )}

      {/* Content */}
      {batchGroups.length === 0 && ungroupedDocs.length === 0 ? (
        <div className="card text-center py-16">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
            <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 3h7l5 5v13H8z" /><path d="M15 3v5h5" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No documents found</p>
          <Link to="/upload" className="text-primary-600 hover:text-primary-700 text-sm mt-2 inline-block font-semibold">
            Upload your first document
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {batchGroups.map(({ batch, docs }) => (
            <BatchCard
              key={batch.id}
              batch={batch}
              docs={docs}
              expanded={expandedBatches.has(batch.id)}
              onToggle={() => toggleBatch(batch.id)}
            />
          ))}
          {ungroupedDocs.length > 0 && (
            <div className="space-y-2 pt-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">Unlinked Documents</p>
              {ungroupedDocs.map((doc) => (
                <DocumentRow key={doc.id} doc={doc} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Batch Card ─── */
function BatchCard({
  batch,
  docs,
  expanded,
  onToggle,
}: {
  batch: BatchInfo;
  docs: DocumentListItem[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const completedCount = docs.filter((d) => d.processing_status === 'completed').length;
  const failedCount = docs.filter((d) => ['failed', 'ocr_failed'].includes(d.processing_status)).length;
  const progressPercent = docs.length > 0 ? Math.round((completedCount / docs.length) * 100) : 0;
  const allDone = completedCount + failedCount === docs.length;

  return (
    <div className="card p-0 overflow-hidden">
      {/* Batch header — clickable */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 p-4 text-left hover:bg-gray-50/50 transition-colors"
      >
        {/* Chevron */}
        <svg
          className={`h-4 w-4 text-gray-400 shrink-0 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>

        {/* Batch icon */}
        <div className="shrink-0 h-10 w-10 rounded-xl bg-primary-50 flex items-center justify-center">
          <svg className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
        </div>

        {/* Batch info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-900 truncate">{batch.batch_reference}</p>
            <StatusBadge status={batch.processing_status} />
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
            <span>{docs.length} file{docs.length !== 1 ? 's' : ''}</span>
            <span className="text-gray-200">|</span>
            <span>{new Date(batch.created_at).toLocaleDateString()}</span>
            {failedCount > 0 && (
              <>
                <span className="text-gray-200">|</span>
                <span className="text-rose-500 font-medium">{failedCount} failed</span>
              </>
            )}
          </div>
        </div>

        {/* Mini progress bar */}
        <div className="hidden sm:flex items-center gap-3 shrink-0 w-36">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                failedCount > 0
                  ? 'bg-gradient-to-r from-emerald-400 to-rose-400'
                  : allDone
                  ? 'bg-emerald-400'
                  : 'bg-gradient-to-r from-primary-400 to-primary-500'
              }`}
              style={{ width: `${allDone ? 100 : progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-gray-500 tabular-nums w-12 text-right">
            {completedCount}/{docs.length}
          </span>
        </div>
      </button>

      {/* Expanded document list */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50/30">
          <div className="divide-y divide-gray-100">
            {docs.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} nested />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Document Row ─── */
function DocumentRow({ doc, nested = false }: { doc: DocumentListItem; nested?: boolean }) {
  return (
    <Link
      to={`/documents/${doc.id}`}
      className={`flex items-center gap-4 hover:bg-gray-50 transition-all duration-200 group cursor-pointer ${
        nested ? 'px-6 py-3 pl-[4.5rem]' : 'card p-4 hover:shadow-card-hover hover:border-primary-200'
      }`}
    >
      {/* File icon */}
      <div className={`shrink-0 h-8 w-8 rounded-lg flex items-center justify-center ${fileIconBg(doc.mime_type)}`}>
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          {doc.mime_type.includes('pdf') ? (
            <path d="M7 3h7l5 5v11a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2zm7 0v5h5" />
          ) : (
            <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          )}
        </svg>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-primary-700 transition-colors">
            {doc.original_filename}
          </p>
          <StatusBadge status={doc.processing_status} />
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
          <span>{formatFileSize(doc.file_size_bytes)}</span>
          <span className="text-gray-200">|</span>
          <span className="font-mono">{doc.mime_type.split('/').pop()}</span>
          <span className="text-gray-200">|</span>
          <span>{new Date(doc.created_at).toLocaleDateString()}</span>
          {doc.total_pages > 1 && (
            <>
              <span className="text-gray-200">|</span>
              <span>{doc.total_pages} pages</span>
            </>
          )}
        </div>
      </div>

      {/* Ownership & Error */}
      <div className="hidden sm:flex items-center gap-3 shrink-0">
        <OwnershipBadge
          status={doc.validation_status}
          confirmed={doc.ownership_confirmed}
        />
        {doc.error_message && (
          <span
            className="max-w-[160px] truncate text-xs text-rose-600 bg-rose-50 px-2.5 py-1 rounded-lg ring-1 ring-inset ring-rose-600/10"
            title={doc.error_message}
          >
            {doc.error_message}
          </span>
        )}
      </div>

      {/* Arrow */}
      <svg className="h-4 w-4 text-gray-300 group-hover:text-primary-500 transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  );
}

/* ─── Helpers ─── */
function fileIconBg(mime: string): string {
  if (mime.includes('pdf')) return 'bg-rose-50 text-rose-500';
  if (mime.includes('image')) return 'bg-sky-50 text-sky-500';
  return 'bg-gray-50 text-gray-400';
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function OwnershipBadge({
  status,
  confirmed,
}: {
  status: string | null;
  confirmed: boolean | null;
}) {
  if (!status) return null;

  if (confirmed) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg ring-1 ring-inset ring-emerald-600/10">
        <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
        Verified
      </span>
    );
  }

  if (status === 'partial_match') {
    return (
      <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg ring-1 ring-inset ring-amber-600/10">
        Review
      </span>
    );
  }

  return (
    <span className="text-xs font-semibold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-lg ring-1 ring-inset ring-rose-600/10">
      Not Verified
    </span>
  );
}
