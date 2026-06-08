import { useEffect, useState, useMemo, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getBatchDetail, listDocuments } from '../api/endpoints';
import { BatchImport, BatchCandidate, DocumentListItem } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const [batch, setBatch] = useState<BatchImport | null>(null);
  const [candidates, setCandidates] = useState<BatchCandidate[]>([]);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCandidates, setExpandedCandidates] = useState<Set<string>>(new Set());

  const loadData = useCallback(async () => {
    if (!batchId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await getBatchDetail(batchId);
      setBatch(detail.batch);
      setCandidates(detail.candidates);

      // Fetch documents in parallel chunks to avoid flooding the backend
      const candidateIds = detail.candidates
        .map((c) => c.candidate_id)
        .filter(Boolean) as string[];

      if (candidateIds.length > 0) {
        const CHUNK_SIZE = 5;
        const chunks: string[][] = [];

        for (let i = 0; i < candidateIds.length; i += CHUNK_SIZE) {
          chunks.push(candidateIds.slice(i, i + CHUNK_SIZE));
        }

        const chunkResults = await Promise.all(
          chunks.map((chunk) =>
            Promise.all(
              chunk.map((cid) => listDocuments({ candidate_id: cid, limit: 100 }))
            )
          )
        );
        const allDocs: DocumentListItem[] = chunkResults.flat(2);

        setDocuments(allDocs);
      } else {
        setDocuments([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load batch details');
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Group documents by candidate — only include docs created after the batch started
  const candidateDocMap = useMemo(() => {
    const map = new Map<string, DocumentListItem[]>();
    const batchCreatedAt = batch ? new Date(batch.created_at).getTime() : 0;
    const candidateIds = new Set(candidates.map((c) => c.candidate_id).filter(Boolean));
    for (const doc of documents) {
      if (doc.candidate_id && candidateIds.has(doc.candidate_id)) {
        const docTime = new Date(doc.created_at).getTime();
        if (docTime >= batchCreatedAt) {
          const list = map.get(doc.candidate_id) || [];
          list.push(doc);
          map.set(doc.candidate_id, list);
        }
      }
    }
    return map;
  }, [documents, batch, candidates]);

  const toggleCandidate = (candidateId: string) => {
    setExpandedCandidates((prev) => {
      const next = new Set(prev);
      if (next.has(candidateId)) next.delete(candidateId);
      else next.add(candidateId);
      return next;
    });
  };

  const expandAll = () => setExpandedCandidates(new Set(candidates.map((c) => c.id)));
  const collapseAll = () => setExpandedCandidates(new Set());

  if (loading) return <LoadingSpinner message="Loading batch details..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;
  if (!batch) return <ErrorMessage message="Batch not found" />;

  const progressPercent = batch.total_candidates > 0
    ? Math.round(((batch.processed_candidates + batch.failed_candidates + batch.skipped_candidates) / batch.total_candidates) * 100)
    : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/batch-history"
            className="h-9 w-9 rounded-xl bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors"
          >
            <svg className="h-4 w-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              Batch: {batch.batch_code}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {batch.original_filename} &mdash; {new Date(batch.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
        <StatusBadge status={batch.status} />
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="card p-4 text-center">
          <p className="text-xl font-bold text-gray-900">{batch.total_candidates}</p>
          <p className="text-xs text-gray-500">Total</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xl font-bold text-emerald-600">{batch.processed_candidates}</p>
          <p className="text-xs text-gray-500">Successful</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xl font-bold text-amber-600">{batch.skipped_candidates}</p>
          <p className="text-xs text-gray-500">Partial/Skipped</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xl font-bold text-rose-600">{batch.failed_candidates}</p>
          <p className="text-xs text-gray-500">Failed</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xl font-bold text-gray-900">{batch.total_documents_processed}/{batch.total_documents_found}</p>
          <p className="text-xs text-gray-500">Documents</p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Processing Progress</span>
          <span className="text-sm text-gray-500 tabular-nums">{progressPercent}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="bg-gradient-to-r from-primary-500 to-emerald-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Expand / Collapse toggle */}
      {candidates.length > 1 && (
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

      {/* Candidate List */}
      {candidates.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-gray-500 font-medium">No candidates in this batch</p>
        </div>
      ) : (
        <div className="space-y-3">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              docs={candidateDocMap.get(candidate.candidate_id || '') || []}
              expanded={expandedCandidates.has(candidate.id)}
              onToggle={() => toggleCandidate(candidate.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Candidate Card ─── */
function CandidateCard({
  candidate,
  docs,
  expanded,
  onToggle,
}: {
  candidate: BatchCandidate;
  docs: DocumentListItem[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const completedDocs = docs.filter((d) => d.processing_status === 'completed').length;
  const failedDocs = docs.filter((d) => ['failed', 'ocr_failed'].includes(d.processing_status)).length;

  return (
    <div className="card p-0 overflow-hidden">
      {/* Candidate header — clickable */}
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

        {/* Candidate icon */}
        <div className="shrink-0 h-10 w-10 rounded-xl bg-primary-50 flex items-center justify-center">
          <svg className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
        </div>

        {/* Candidate info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-900 truncate">
              {candidate.source_name}
            </p>
            <span className="text-xs text-gray-400 font-mono">{candidate.source_candidate_id}</span>
            <StatusBadge status={candidate.status} />
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
            {candidate.source_email && <span>{candidate.source_email}</span>}
            {candidate.documents_found > 0 && (
              <>
                {candidate.source_email && <span className="text-gray-200">|</span>}
                <span>{candidate.documents_found} document{candidate.documents_found !== 1 ? 's' : ''} found</span>
              </>
            )}
            {failedDocs > 0 && (
              <>
                <span className="text-gray-200">|</span>
                <span className="text-rose-500 font-medium">{failedDocs} failed</span>
              </>
            )}
          </div>
        </div>

        {/* Mini progress */}
        <div className="hidden sm:flex items-center gap-3 shrink-0 w-36">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                failedDocs > 0
                  ? 'bg-gradient-to-r from-emerald-400 to-rose-400'
                  : completedDocs === docs.length && docs.length > 0
                  ? 'bg-emerald-400'
                  : 'bg-gradient-to-r from-primary-400 to-primary-500'
              }`}
              style={{ width: `${docs.length > 0 ? Math.round((completedDocs / docs.length) * 100) : 0}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-gray-500 tabular-nums w-12 text-right">
            {completedDocs}/{docs.length}
          </span>
        </div>
      </button>

      {/* Expanded document list */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50/30">
          {docs.length === 0 ? (
            <div className="px-6 py-4 text-sm text-gray-400">No documents found for this candidate</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <DocumentRow key={doc.id} doc={doc} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Document Row ─── */
function DocumentRow({ doc }: { doc: DocumentListItem }) {
  return (
    <Link
      to={`/documents/${doc.id}`}
      className="flex items-center gap-4 hover:bg-gray-50 transition-all duration-200 group cursor-pointer px-6 py-3 pl-[4.5rem]"
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

      {/* Ownership badge */}
      <div className="hidden sm:flex items-center gap-3 shrink-0">
        <OwnershipBadge status={doc.validation_status} confirmed={doc.ownership_confirmed} />
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

function OwnershipBadge({ status, confirmed }: { status: string | null; confirmed: boolean | null }) {
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
