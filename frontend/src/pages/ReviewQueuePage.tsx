import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getReviewQueue } from '../api/endpoints';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

interface ReviewQueueItem {
  id: string;
  batch_import_id: string;
  batch_code: string;
  candidate_id: string | null;
  source_candidate_id: string;
  source_name: string;
  source_email: string | null;
  status: string;
  documents_found: number;
  documents_processed: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
}

const PAGE_SIZE = 20;

export default function ReviewQueuePage() {
  const navigate = useNavigate();
  const [data, setData] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result: ReviewQueueResponse = await getReviewQueue({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        search: search || undefined,
        status: statusFilter || undefined,
      });
      setData(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setSearch(searchInput);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const statusLabel = (status: string) => {
    switch (status) {
      case 'partial': return 'Partial';
      case 'awaiting_required_documents': return 'Awaiting Documents';
      case 'failed': return 'Failed';
      default: return status;
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case 'partial': return 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/10';
      case 'awaiting_required_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
      case 'failed': return 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10';
      default: return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
    }
  };

  const reasonText = (item: ReviewQueueItem) => {
    if (item.status === 'failed') return item.error_message || 'Processing error';
    if (item.status === 'awaiting_required_documents') return 'No required documents matched';
    if (item.status === 'partial') return 'Missing mandatory documents';
    return '-';
  };

  if (loading && data.length === 0) return <LoadingSpinner message="Loading review queue..." />;
  if (error && data.length === 0) return <ErrorMessage message={error} onRetry={loadData} />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Review Queue</h1>
          <p className="mt-1 text-sm text-gray-500">
            {total} candidate{total !== 1 ? 's' : ''} requiring review
          </p>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-3">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by name, email, candidate ID, or batch code..."
              className="input-field flex-1"
            />
            <button type="submit" className="btn-primary whitespace-nowrap">
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => { setSearchInput(''); setSearch(''); setPage(0); }}
                className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg"
              >
                Clear
              </button>
            )}
          </form>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            className="input-field sm:w-56"
          >
            <option value="">All Statuses</option>
            <option value="partial">Partial</option>
            <option value="awaiting_required_documents">Awaiting Documents</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {data.length === 0 ? (
        <div className="card text-center py-16">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-6 w-6 text-gray-400">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No candidates in review queue</p>
          <p className="text-gray-400 text-sm mt-1">All candidates have been fully verified</p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/80">
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Batch</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidate ID</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Docs Received</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{item.batch_code}</td>
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{item.source_candidate_id}</td>
                    <td className="py-3.5 px-4 font-medium text-gray-900">{item.source_name}</td>
                    <td className="py-3.5 px-4 text-gray-500">{item.source_email || '-'}</td>
                    <td className="py-3.5 px-4">
                      {item.status === 'partial' ? (
                        <span className="text-orange-700 font-medium">{item.documents_processed}/{item.documents_found}</span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-semibold ${statusBadge(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-gray-500 text-xs max-w-[200px] truncate" title={reasonText(item)}>
                      {reasonText(item)}
                    </td>
                    <td className="py-3.5 px-4">
                      {item.candidate_id ? (
                        <button
                          onClick={() => navigate(`/candidates`)}
                          className="text-indigo-600 hover:text-indigo-800 text-xs font-medium hover:underline"
                        >
                          View
                        </button>
                      ) : (
                        <span className="text-gray-300 text-xs">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/50">
              <p className="text-xs text-gray-500">
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
              </p>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-200 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                  const pageNum = page < 3 ? i : page - 2 + i;
                  if (pageNum >= totalPages) return null;
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md border ${
                        pageNum === page
                          ? 'bg-indigo-600 text-white border-indigo-600'
                          : 'border-gray-200 hover:bg-white text-gray-700'
                      }`}
                    >
                      {pageNum + 1}
                    </button>
                  );
                })}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="px-3 py-1.5 text-xs font-medium rounded-md border border-gray-200 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
