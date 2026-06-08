import { BatchImport, BatchCandidate, BatchLogEntry } from '../types';
import ProcessingSummary from './ProcessingSummary';
import LiveExecutionLogs from './LiveExecutionLogs';
import { statusColor } from '../utils/formatting';

interface BatchProcessingViewProps {
  activeBatch: BatchImport;
  batchCandidates: BatchCandidate[];
  batchLogs: BatchLogEntry[];
  clearLogs: () => void;
}

export default function BatchProcessingView({
  activeBatch,
  batchCandidates,
  batchLogs,
  clearLogs,
}: BatchProcessingViewProps) {
  const processed = activeBatch.processed_candidates + activeBatch.failed_candidates + activeBatch.skipped_candidates;
  const progressPercent = activeBatch.total_candidates > 0
    ? Math.round((processed / activeBatch.total_candidates) * 100)
    : 0;

  return (
    <>
      {/* Progress Bar - Full Width */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Processing Progress</span>
          <span className="text-sm text-gray-500 tabular-nums">
            {processed} / {activeBatch.total_candidates} candidates
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div
            className="bg-gradient-to-r from-emerald-500 to-emerald-600 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* 3-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Processing Summary */}
        <div className="lg:col-span-3">
          <div className="card">
            <ProcessingSummary batch={activeBatch} candidates={batchCandidates} />
          </div>
        </div>

        {/* Center: Candidate Table */}
        <div className="lg:col-span-5">
          <div className="card overflow-hidden p-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 text-gray-400">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M3 9h18M9 21V9" />
                </svg>
                Candidate Processing Status
              </h3>
              <span className="text-xs text-gray-500 font-medium px-2.5 py-1 rounded-full border border-gray-200">{batchCandidates.length} records</span>
            </div>
            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10">
                  <tr className="border-b border-gray-100 bg-gray-50/80">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Docs</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {batchCandidates.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-3 text-xs font-mono text-gray-600">{c.source_candidate_id}</td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.source_name}</td>
                      <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-[140px]">{c.source_email || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-lg text-xs font-semibold ${statusColor(c.status)}`}>
                          {c.status === 'awaiting_required_documents' ? 'Awaiting' : c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500 tabular-nums">
                        {c.documents_found > 0 ? `${c.documents_processed}/${c.documents_found}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: Live Execution Logs */}
        <div className="lg:col-span-4">
          <div className="card p-4">
            <LiveExecutionLogs logs={batchLogs} onClear={clearLogs} />
          </div>
        </div>
      </div>
    </>
  );
}
