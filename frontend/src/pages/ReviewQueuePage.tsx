import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getReviewQueue, notifyReviewCandidates, getNotificationHistory, retryNotification } from '../api/endpoints';
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
  notification_status: string | null;
  notification_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

interface NotificationLogItem {
  id: string;
  candidate_id: string;
  recipient_email: string;
  subject: string;
  body_html: string;
  status: string;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
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

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Notification modal
  const [notifModal, setNotifModal] = useState<{ candidateId: string; name: string } | null>(null);
  const [notifHistory, setNotifHistory] = useState<NotificationLogItem[]>([]);
  const [notifLoading, setNotifLoading] = useState(false);

  // Toast
  const [toast, setToast] = useState<string | null>(null);

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

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setSearch(searchInput);
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === data.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.map((d) => d.id)));
    }
  };

  const handleBulkNotify = async () => {
    if (selectedIds.size === 0) return;
    try {
      const result = await notifyReviewCandidates(Array.from(selectedIds));
      setToast(`${result.queued} email(s) queued${result.skipped > 0 ? `, ${result.skipped} skipped (no email)` : ''}`);
      setSelectedIds(new Set());
      setTimeout(() => loadData(), 2000); // Refresh after short delay
    } catch (err) {
      setToast('Failed to send notifications');
    }
  };

  const handleSingleNotify = async (id: string) => {
    try {
      const result = await notifyReviewCandidates([id]);
      setToast(result.message);
      setTimeout(() => loadData(), 2000);
    } catch {
      setToast('Failed to send notification');
    }
  };

  const handleViewNotifications = async (candidateId: string, name: string) => {
    setNotifModal({ candidateId, name });
    setNotifLoading(true);
    try {
      const history = await getNotificationHistory(candidateId);
      setNotifHistory(history);
    } catch {
      setNotifHistory([]);
    } finally {
      setNotifLoading(false);
    }
  };

  const handleRetry = async (notificationId: string) => {
    try {
      await retryNotification(notificationId);
      setToast('Retry queued');
      if (notifModal) {
        const history = await getNotificationHistory(notifModal.candidateId);
        setNotifHistory(history);
      }
    } catch {
      setToast('Retry failed');
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const statusLabel = (status: string) => {
    switch (status) {
      case 'partial': return 'Partial';
      case 'awaiting_required_documents': return 'Awaiting Documents';
      case 'failed': return 'Failed';
      case 'no_documents': return 'No Documents';
      default: return status;
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case 'partial': return 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/10';
      case 'awaiting_required_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
      case 'failed': return 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10';
      case 'no_documents': return 'bg-slate-50 text-slate-700 ring-1 ring-inset ring-slate-600/10';
      default: return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
    }
  };

  const notifStatusBadge = (status: string | null) => {
    switch (status) {
      case 'sent': return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-green-50 text-green-700 ring-1 ring-inset ring-green-600/10">✓ Sent</span>;
      case 'queued': return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/10">● Queued</span>;
      case 'failed': return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10">✗ Failed</span>;
      default: return <span className="text-gray-300 text-xs">—</span>;
    }
  };

  const reasonText = (item: ReviewQueueItem) => {
    if (item.status === 'failed') return item.error_message || 'Processing error';
    if (item.status === 'no_documents') return 'No documents received from candidate';
    if (item.status === 'awaiting_required_documents') return 'No required documents matched';
    if (item.status === 'partial') return 'Missing mandatory documents';
    return '-';
  };

  if (loading && data.length === 0) return <LoadingSpinner message="Loading review queue..." />;
  if (error && data.length === 0) return <ErrorMessage message={error} onRetry={loadData} />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-gray-900 text-white px-4 py-3 rounded-lg shadow-lg text-sm animate-fade-in">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Review Queue</h1>
          <p className="mt-1 text-sm text-gray-500">
            {total} candidate{total !== 1 ? 's' : ''} requiring review
          </p>
        </div>
        {selectedIds.size > 0 && (
          <button
            onClick={handleBulkNotify}
            className="btn-primary flex items-center gap-2"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
              <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Notify {selectedIds.size} Selected
          </button>
        )}
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
            <option value="no_documents">No Documents</option>
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
                  <th className="py-3.5 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === data.length && data.length > 0}
                      onChange={toggleSelectAll}
                      className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Batch</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidate ID</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Docs</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Notification</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Reason</th>
                  <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="py-3.5 px-4">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelect(item.id)}
                        className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{item.batch_code}</td>
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{item.source_candidate_id}</td>
                    <td className="py-3.5 px-4 font-medium text-gray-900">{item.source_name}</td>
                    <td className="py-3.5 px-4 text-gray-500">{item.source_email || '-'}</td>
                    <td className="py-3.5 px-4">
                      <span className="text-gray-700 font-medium">{item.documents_processed}/{item.documents_found}</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-semibold ${statusBadge(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => handleViewNotifications(item.id, item.source_name)}
                        className="hover:opacity-80 transition-opacity"
                      >
                        {notifStatusBadge(item.notification_status)}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 text-gray-500 text-xs max-w-[180px] truncate" title={reasonText(item)}>
                      {reasonText(item)}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        {item.source_email && (
                          <button
                            onClick={() => handleSingleNotify(item.id)}
                            className="text-indigo-600 hover:text-indigo-800 transition-colors"
                            title="Send email notification"
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
                              <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                          </button>
                        )}
                        {item.candidate_id && (
                          <button
                            onClick={() => navigate(`/candidates`)}
                            className="text-gray-500 hover:text-gray-700 text-xs font-medium hover:underline"
                          >
                            View
                          </button>
                        )}
                      </div>
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

      {/* Notification History Modal */}
      {notifModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setNotifModal(null)}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900">
                Notifications — {notifModal.name}
              </h3>
              <button onClick={() => setNotifModal(null)} className="text-gray-400 hover:text-gray-600">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                  <path d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="overflow-y-auto max-h-[65vh] p-6 space-y-4">
              {notifLoading ? (
                <div className="text-center py-8 text-gray-500">Loading...</div>
              ) : notifHistory.length === 0 ? (
                <div className="text-center py-8 text-gray-400">No notifications sent yet</div>
              ) : (
                notifHistory.map((notif) => (
                  <div key={notif.id} className="border border-gray-100 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {notif.status === 'sent' && <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-green-50 text-green-700">Sent</span>}
                        {notif.status === 'queued' && <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700">Queued</span>}
                        {notif.status === 'failed' && (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-rose-50 text-rose-700">Failed</span>
                            <button
                              onClick={() => handleRetry(notif.id)}
                              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium hover:underline"
                            >
                              Retry
                            </button>
                          </div>
                        )}
                        <span className="text-xs text-gray-400">
                          {notif.sent_at
                            ? new Date(notif.sent_at).toLocaleString()
                            : new Date(notif.created_at).toLocaleString()}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500">To: {notif.recipient_email}</span>
                    </div>
                    <div className="text-sm font-medium text-gray-800">{notif.subject}</div>
                    <div
                      className="text-sm text-gray-600 bg-gray-50 rounded-md p-3 prose prose-sm max-w-none"
                      dangerouslySetInnerHTML={{ __html: notif.body_html }}
                    />
                    {notif.error_message && (
                      <p className="text-xs text-rose-600 bg-rose-50 rounded px-2 py-1">{notif.error_message}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
