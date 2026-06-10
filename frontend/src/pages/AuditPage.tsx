import { useEffect, useState, useCallback } from 'react';
import { listBatchImports, getBatchLogs, getBatchDetail, BatchLogItem } from '../api/endpoints';
import { BatchImport, BatchCandidate } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { statusColor } from '../utils/formatting';

export default function AuditPage() {
  const [batches, setBatches] = useState<BatchImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters — default to today's date
  const today = new Date().toISOString().split('T')[0];
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [statusFilter, setStatusFilter] = useState('');

  // Drill-down state
  const [selectedBatch, setSelectedBatch] = useState<BatchImport | null>(null);
  const [batchCandidates, setBatchCandidates] = useState<BatchCandidate[]>([]);
  const [batchLogs, setBatchLogs] = useState<BatchLogItem[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');

  const loadBatches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listBatchImports({
        limit: 50,
        status: statusFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setBatches(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load batches');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  const handleBatchSelect = async (batch: BatchImport) => {
    setSelectedBatch(batch);
    setSelectedCandidate(null);
    setLevelFilter('');
    try {
      const [detail, logs] = await Promise.all([
        getBatchDetail(batch.id),
        getBatchLogs(batch.id),
      ]);
      setBatchCandidates(detail.candidates);
      setBatchLogs(logs);
    } catch {
      setBatchLogs([]);
      setBatchCandidates([]);
    }
  };

  const handleCandidateFilter = async (candidateId: string | null) => {
    setSelectedCandidate(candidateId);
    if (!selectedBatch) return;
    try {
      const logs = await getBatchLogs(selectedBatch.id, {
        candidate_id: candidateId || undefined,
        level: levelFilter || undefined,
      });
      setBatchLogs(logs);
    } catch {
      setBatchLogs([]);
    }
  };

  const handleLevelFilter = async (level: string) => {
    setLevelFilter(level);
    if (!selectedBatch) return;
    try {
      const logs = await getBatchLogs(selectedBatch.id, {
        candidate_id: selectedCandidate || undefined,
        level: level || undefined,
      });
      setBatchLogs(logs);
    } catch {
      setBatchLogs([]);
    }
  };

  const filteredLogs = searchTerm
    ? batchLogs.filter(
        (l) =>
          l.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
          l.stage.toLowerCase().includes(searchTerm.toLowerCase()),
      )
    : batchLogs;

  if (loading && batches.length === 0) return <LoadingSpinner message="Loading audit logs..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadBatches} />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Audit Logs</h1>
          <p className="mt-1 text-sm text-gray-500">Review batch processing history and logs</p>
        </div>
      </div>

      {/* Filters (visible on batch list, not during drill-down) */}
      {!selectedBatch && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="input-field text-sm w-auto"
              aria-label="Filter from date"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="input-field text-sm w-auto"
              aria-label="Filter to date"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-auto text-sm"
            aria-label="Filter by batch status"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="completed_with_errors">Completed with Errors</option>
            <option value="failed">Failed</option>
          </select>
          {(dateFrom || dateTo || statusFilter) && (
            <button
              onClick={() => { setDateFrom(''); setDateTo(''); setStatusFilter(''); }}
              className="text-xs text-primary-600 hover:text-primary-700 font-medium"
            >
              Clear Filters
            </button>
          )}
        </div>
      )}

      {!selectedBatch && (
        <BatchListView
          batches={batches}
          loading={loading}
          onSelect={handleBatchSelect}
        />
      )}

      {selectedBatch && (
        <BatchDrillDown
          batch={selectedBatch}
          candidates={batchCandidates}
          logs={filteredLogs}
          selectedCandidate={selectedCandidate}
          levelFilter={levelFilter}
          searchTerm={searchTerm}
          onBack={() => setSelectedBatch(null)}
          onCandidateFilter={handleCandidateFilter}
          onLevelFilter={handleLevelFilter}
          onSearchChange={setSearchTerm}
        />
      )}
    </div>
  );
}

// ==================== Batch List View ====================

function BatchListView({
  batches,
  loading,
  onSelect,
}: {
  batches: BatchImport[];
  loading: boolean;
  onSelect: (b: BatchImport) => void;
}) {
  if (loading) {
    return <LoadingSpinner message="Loading batches..." />;
  }

  if (batches.length === 0) {
    return (
      <div className="card text-center py-16">
        <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
          <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <p className="text-gray-500 font-medium">No batches found</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {batches.map((batch) => (
        <button
          key={batch.id}
          onClick={() => onSelect(batch)}
          className="card text-left hover:shadow-card-hover hover:border-primary-200 transition-all duration-200 cursor-pointer group"
        >
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-sm font-bold text-gray-900">{batch.batch_code}</span>
            <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${statusColor(batch.status)}`}>
              {batch.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-xs text-gray-400 mb-4 truncate">{batch.original_filename}</p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-gray-50/80 rounded-xl py-2">
              <p className="text-lg font-bold text-gray-900 tabular-nums">{batch.total_candidates}</p>
              <p className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Candidates</p>
            </div>
            <div className="bg-emerald-50/60 rounded-xl py-2">
              <p className="text-lg font-bold text-emerald-600 tabular-nums">{batch.processed_candidates}</p>
              <p className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Processed</p>
            </div>
            <div className="bg-rose-50/60 rounded-xl py-2">
              <p className="text-lg font-bold text-rose-600 tabular-nums">{batch.failed_candidates}</p>
              <p className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Failed</p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3">
            {new Date(batch.created_at).toLocaleString()}
          </p>
        </button>
      ))}
    </div>
  );
}

// ==================== Batch Drill-Down ====================

function BatchDrillDown({
  batch,
  candidates,
  logs,
  selectedCandidate,
  levelFilter,
  searchTerm,
  onBack,
  onCandidateFilter,
  onLevelFilter,
  onSearchChange,
}: {
  batch: BatchImport;
  candidates: BatchCandidate[];
  logs: BatchLogItem[];
  selectedCandidate: string | null;
  levelFilter: string;
  searchTerm: string;
  onBack: () => void;
  onCandidateFilter: (id: string | null) => void;
  onLevelFilter: (level: string) => void;
  onSearchChange: (term: string) => void;
}) {
  const errorCount = logs.filter((l) => l.level === 'error').length;
  const warningCount = logs.filter((l) => l.level === 'warning').length;

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <button onClick={onBack} className="text-primary-600 hover:text-primary-700 font-medium">
          ← All Batches
        </button>
        <span className="text-gray-400">/</span>
        <span className="font-mono text-gray-700">{batch.batch_code}</span>
      </div>

      {/* Batch Summary Header */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{batch.batch_code}</h2>
            <p className="text-sm text-gray-500">{batch.original_filename} • {new Date(batch.created_at).toLocaleString()}</p>
          </div>
          <div className="flex gap-2.5">
            {errorCount > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 bg-rose-50 text-rose-700 rounded-lg text-xs font-semibold ring-1 ring-inset ring-rose-600/10">
                <span className="w-1.5 h-1.5 bg-rose-500 rounded-full" />
                {errorCount} errors
              </span>
            )}
            {warningCount > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-semibold ring-1 ring-inset ring-amber-600/10">
                <span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
                {warningCount} warnings
              </span>
            )}
          </div>
        </div>

        {/* Candidate pills */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onCandidateFilter(null)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${!selectedCandidate ? 'bg-primary-100 text-primary-800' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            All ({logs.length})
          </button>
          {candidates.map((c) => (
            <button
              key={c.id}
              onClick={() => onCandidateFilter(c.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${selectedCandidate === c.id ? 'bg-primary-100 text-primary-800' : c.status === 'failed' ? 'bg-rose-50 text-rose-700 hover:bg-rose-100' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              {c.source_name}
              {c.status === 'failed' && ' ✗'}
              {c.status === 'completed' && ' ✓'}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search logs..."
          className="input-field flex-1 text-sm"
        />
        <select
          value={levelFilter}
          onChange={(e) => onLevelFilter(e.target.value)}
          className="input-field w-auto text-sm"
          aria-label="Filter by log level"
        >
          <option value="">All Levels</option>
          <option value="error">Errors</option>
          <option value="warning">Warnings</option>
          <option value="info">Info</option>
        </select>
      </div>

      {/* Timeline */}
      <div className="card max-h-[60vh] overflow-y-auto">
        {logs.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-12">No logs found.</p>
        ) : (
          <div className="relative pl-6 border-l-2 border-gray-100 space-y-3">
            {logs.map((log) => (
              <LogTimelineItem key={log.id} log={log} candidates={candidates} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== Log Timeline Item ====================

function LogTimelineItem({ log, candidates }: { log: BatchLogItem; candidates: BatchCandidate[] }) {
  const levelStyles: Record<string, { dot: string; bg: string }> = {
    error: { dot: 'bg-rose-500', bg: 'bg-rose-50/80 border-rose-100' },
    warning: { dot: 'bg-amber-500', bg: 'bg-amber-50/80 border-amber-100' },
    info: { dot: 'bg-sky-500', bg: 'bg-white border-gray-100' },
  };
  const style = levelStyles[log.level] || levelStyles.info;
  const candidate = candidates.find((c) => c.id === log.batch_candidate_id);

  return (
    <div className={`relative rounded-xl border p-3.5 ${style.bg}`}>
      {/* Timeline dot */}
      <div className={`absolute -left-[25px] top-4 w-3 h-3 rounded-full border-2 border-white shadow-sm ${style.dot}`} />

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-block px-2 py-0.5 rounded-lg text-xs font-semibold bg-gray-100 text-gray-600">
              {log.stage}
            </span>
            {candidate && (
              <span className="text-xs text-gray-500">
                {candidate.source_name}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-800 mt-1">{log.message}</p>
          {log.details && (
            <p className="text-xs text-gray-500 mt-1 font-mono truncate">{log.details}</p>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap flex-shrink-0">
          {new Date(log.created_at).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
}


