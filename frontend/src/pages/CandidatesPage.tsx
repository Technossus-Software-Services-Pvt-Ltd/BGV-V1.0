import { useEffect, useState, useCallback } from 'react';
import { listCandidates } from '../api/endpoints';
import { Candidate } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

const PAGE_SIZE = 25;

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCandidates({ skip: page * PAGE_SIZE, limit: PAGE_SIZE });
      setCandidates(data.candidates);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load candidates');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (loading && candidates.length === 0) return <LoadingSpinner message="Loading candidates..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadCandidates} />;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Candidates</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total candidates</p>
        </div>
      </div>

      {/* Create Form - hidden */}
      {/* Candidates Table */}
      {candidates.length === 0 ? (
        <div className="card text-center py-16">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
            <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="8" r="3.5" /><path d="M5 20c1.8-3 4-4.5 7-4.5s5.2 1.5 7 4.5" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No candidates yet</p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidate ID</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Phone</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {candidates.map((candidate) => (
                <tr key={candidate.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{candidate.candidate_id}</td>
                  <td className="py-3.5 px-4 font-medium text-gray-900">{candidate.name}</td>
                  <td className="py-3.5 px-4 text-gray-500">{candidate.email || '-'}</td>
                  <td className="py-3.5 px-4 text-gray-500">{candidate.phone || '-'}</td>
                  <td className="py-3.5 px-4 text-gray-400 text-xs">
                    {new Date(candidate.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages - 1}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
