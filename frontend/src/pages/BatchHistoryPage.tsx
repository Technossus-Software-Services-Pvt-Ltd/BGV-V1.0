import { useEffect, useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { listBatchImports } from '../api/endpoints';
import { BatchImport } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function BatchHistoryPage() {
  const [batches, setBatches] = useState<BatchImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { limit: number; status?: string; date_from?: string; date_to?: string } = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const data = await listBatchImports(params);
      setBatches(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load batch history');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSearch = () => {
    loadData();
  };

  // Stats
  const stats = useMemo(() => {
    const total = batches.length;
    const completed = batches.filter((b) => b.status === 'completed').length;
    const failed = batches.filter((b) => b.status === 'failed').length;
    const completionRate = total > 0 ? ((completed / total) * 100).toFixed(1) : '0';
    return { total, completed, failed, completionRate };
  }, [batches]);

  // Filtered batches
  const filteredBatches = useMemo(() => {
    if (!searchQuery.trim()) return batches;
    const q = searchQuery.toLowerCase();
    return batches.filter(
      (b) =>
        b.batch_code.toLowerCase().includes(q) ||
        b.original_filename.toLowerCase().includes(q) ||
        b.correlation_id.toLowerCase().includes(q)
    );
  }, [batches, searchQuery]);

  if (loading) return <LoadingSpinner message="Loading batch history..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Batches */}
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <div className="h-10 w-10 rounded-xl bg-primary-50 flex items-center justify-center">
              <svg className="h-5 w-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </div>
            <span className="text-xs font-semibold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-lg">All Time</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">{stats.total}</p>
          <p className="text-sm text-gray-500">Total Batches</p>
        </div>

        {/* Completed */}
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <div className="h-10 w-10 rounded-xl bg-emerald-50 flex items-center justify-center">
              <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-lg">{stats.completionRate}%</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">{stats.completed}</p>
          <p className="text-sm text-gray-500">Completed Batches</p>
        </div>

        {/* Failed */}
        <div className="card p-5">
          <div className="flex items-center justify-between">
            <div className="h-10 w-10 rounded-xl bg-rose-50 flex items-center justify-center">
              <svg className="h-5 w-5 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">{stats.failed}</p>
          <p className="text-sm text-gray-500">Failed Batches</p>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search batches by ID, uploader..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-field pl-10 text-sm"
              />
            </div>
          </div>

          {/* Date Range */}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="input-field text-sm w-auto"
              placeholder="dd-mm-yyyy"
            />
            <span className="text-xs text-gray-400">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="input-field text-sm w-auto"
              placeholder="dd-mm-yyyy"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field text-sm w-auto"
          >
            <option value="">All Status</option>
            <option value="completed">Completed</option>
            <option value="completed_with_errors">Partial</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
            <option value="parsed">Parsed</option>
          </select>

          {/* Search Button */}
          <button onClick={handleSearch} className="btn-primary flex items-center gap-2 text-sm">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            Search
          </button>
        </div>
      </div>

      {/* Batch Table */}
      {filteredBatches.length === 0 ? (
        <div className="card text-center py-16">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
            <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No batches found</p>
          <Link to="/upload" className="text-primary-600 hover:text-primary-700 text-sm mt-2 inline-block font-semibold">
            Start a new batch import
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/80">
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Run ID</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Upload Date</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">File Name</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Total</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Successful</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Partial</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Failed</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Duration</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredBatches.map((batch) => (
                  <BatchRow key={batch.id} batch={batch} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Batch Row ─── */
function BatchRow({ batch }: { batch: BatchImport }) {
  const duration = useMemo(() => {
    const start = new Date(batch.created_at).getTime();
    const end = new Date(batch.updated_at).getTime();
    const diff = end - start;
    if (diff < 1000) return '< 1s';
    if (diff < 60000) return `${Math.round(diff / 1000)}s`;
    if (diff < 3600000) return `${Math.round(diff / 60000)}m`;
    return `${(diff / 3600000).toFixed(1)}h`;
  }, [batch.created_at, batch.updated_at]);

  const successful = batch.processed_candidates;
  const partial = batch.skipped_candidates;
  const failed = batch.failed_candidates;

  return (
    <tr className="hover:bg-gray-50/50 transition-colors">
      <td className="px-4 py-3.5">
        <span className="text-sm font-medium text-gray-900">{batch.batch_code}</span>
      </td>
      <td className="px-4 py-3.5 text-sm text-gray-500">
        {new Date(batch.created_at).toLocaleDateString()} {new Date(batch.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </td>
      <td className="px-4 py-3.5 text-sm text-gray-500 truncate max-w-[160px]" title={batch.original_filename}>
        {batch.original_filename}
      </td>
      <td className="px-4 py-3.5 text-sm font-medium text-gray-900 tabular-nums">{batch.total_candidates}</td>
      <td className="px-4 py-3.5">
        <span className="text-sm font-medium text-emerald-600 tabular-nums">{successful}</span>
      </td>
      <td className="px-4 py-3.5">
        <span className="text-sm font-medium text-amber-600 tabular-nums">{partial}</span>
      </td>
      <td className="px-4 py-3.5">
        <span className="text-sm font-medium text-rose-600 tabular-nums">{failed}</span>
      </td>
      <td className="px-4 py-3.5 text-sm text-gray-500">{duration}</td>
      <td className="px-4 py-3.5">
        <StatusBadge status={batch.status} />
      </td>
      <td className="px-4 py-3.5">
        <Link
          to={`/batch-history/${batch.id}`}
          className="text-xs text-primary-600 hover:text-primary-800 font-semibold"
        >
          View Details
        </Link>
      </td>
    </tr>
  );
}
