import { useEffect, useState } from 'react';
import { listBatchImports, getBatchLogs, getBatchDetail, BatchLogItem } from '../api/endpoints';
import { BatchImport, BatchCandidate } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

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

  const loadBatches = async () => {
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
  };

  useEffect(() => {
    loadBatches();
  }, [statusFilter, dateFrom, dateTo]);

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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
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
  const statusColor = (s: string) => {
    switch (s) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'completed_with_errors': return 'bg-yellow-100 text-yellow-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'processing': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  if (loading) {
    return <LoadingSpinner message="Loading batches..." />;
  }

  if (batches.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500">No batches found.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {batches.map((batch) => (
        <button
          key={batch.id}
          onClick={() => onSelect(batch)}
          className="card text-left hover:ring-2 hover:ring-primary-300 transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-sm font-semibold text-gray-900">{batch.batch_code}</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(batch.status)}`}>
              {batch.status.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-xs text-gray-500 mb-3">{batch.original_filename}</p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-lg font-bold text-gray-900">{batch.total_candidates}</p>
              <p className="text-xs text-gray-400">Candidates</p>
            </div>
            <div>
              <p className="text-lg font-bold text-green-600">{batch.processed_candidates}</p>
              <p className="text-xs text-gray-400">Processed</p>
            </div>
            <div>
              <p className="text-lg font-bold text-red-600">{batch.failed_candidates}</p>
              <p className="text-xs text-gray-400">Failed</p>
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
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{batch.batch_code}</h2>
            <p className="text-sm text-gray-500">{batch.original_filename} • {new Date(batch.created_at).toLocaleString()}</p>
          </div>
          <div className="flex gap-3">
            {errorCount > 0 && (
              <span className="flex items-center gap-1 px-2 py-1 bg-red-50 text-red-700 rounded-lg text-xs font-medium">
                <span className="w-2 h-2 bg-red-500 rounded-full" />
                {errorCount} errors
              </span>
            )}
            {warningCount > 0 && (
              <span className="flex items-center gap-1 px-2 py-1 bg-yellow-50 text-yellow-700 rounded-lg text-xs font-medium">
                <span className="w-2 h-2 bg-yellow-500 rounded-full" />
                {warningCount} warnings
              </span>
            )}
          </div>
        </div>

        {/* Candidate pills */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onCandidateFilter(null)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              !selectedCandidate ? 'bg-primary-100 text-primary-800' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            All ({logs.length})
          </button>
          {candidates.map((c) => (
            <button
              key={c.id}
              onClick={() => onCandidateFilter(c.id)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selectedCandidate === c.id
                  ? 'bg-primary-100 text-primary-800'
                  : c.status === 'failed'
                  ? 'bg-red-50 text-red-700 hover:bg-red-100'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
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
          <p className="text-sm text-gray-500 text-center py-8">No logs found.</p>
        ) : (
          <div className="relative pl-6 border-l-2 border-gray-200 space-y-3">
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
    error: { dot: 'bg-red-500', bg: 'bg-red-50 border-red-100' },
    warning: { dot: 'bg-yellow-500', bg: 'bg-yellow-50 border-yellow-100' },
    info: { dot: 'bg-blue-500', bg: 'bg-white border-gray-100' },
  };
  const style = levelStyles[log.level] || levelStyles.info;
  const candidate = candidates.find((c) => c.id === log.batch_candidate_id);

  return (
    <div className={`relative rounded-lg border p-3 ${style.bg}`}>
      {/* Timeline dot */}
      <div className={`absolute -left-[25px] top-4 w-3 h-3 rounded-full border-2 border-white ${style.dot}`} />

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-200 text-gray-700">
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


