import { BatchImport } from '../types';
import { statusColor } from '../utils/formatting';

interface BatchHistoryTabProps {
  batchHistory: BatchImport[];
  onViewBatch: (batchId: string) => void;
}

export default function BatchHistoryTab({ batchHistory, onViewBatch }: BatchHistoryTabProps) {
  return (
    <div className="card">
      <h2 className="text-base font-semibold text-gray-900 mb-4">Import History</h2>
      {batchHistory.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-12">No batch imports yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Batch</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">File</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidates</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Documents</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
                <th className="px-4 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {batchHistory.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3.5 text-sm font-medium text-gray-900">{b.batch_code}</td>
                  <td className="px-4 py-3.5 text-sm text-gray-500">{b.original_filename}</td>
                  <td className="px-4 py-3.5">
                    <span className={`inline-block px-2.5 py-1 rounded-lg text-xs font-semibold ${statusColor(b.status)}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-sm text-gray-500">
                    {b.processed_candidates}/{b.total_candidates}
                    {b.failed_candidates > 0 && <span className="text-rose-500 ml-1">({b.failed_candidates} failed)</span>}
                  </td>
                  <td className="px-4 py-3.5 text-sm text-gray-500">{b.total_documents_processed}/{b.total_documents_found}</td>
                  <td className="px-4 py-3.5 text-sm text-gray-400">{new Date(b.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3.5">
                    <button
                      onClick={() => onViewBatch(b.id)}
                      className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
