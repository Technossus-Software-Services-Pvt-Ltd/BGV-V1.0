import { useEffect, useState } from 'react';
import { getAuditLogs } from '../api/endpoints';
import { AuditLogEntry } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterAction, setFilterAction] = useState('');

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAuditLogs({
        action: filterAction || undefined,
        limit: 200,
      });
      setLogs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [filterAction]);

  if (loading) return <LoadingSpinner message="Loading audit logs..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadLogs} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
        <div className="flex items-center gap-3">
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="input-field w-auto text-sm"
          >
            <option value="">All Actions</option>
            <option value="upload">Upload</option>
            <option value="ocr_start">OCR Start</option>
            <option value="ocr_complete">OCR Complete</option>
            <option value="classify_start">Classify Start</option>
            <option value="classify_complete">Classify Complete</option>
            <option value="validate_start">Validate Start</option>
            <option value="validate_complete">Validate Complete</option>
            <option value="error">Error</option>
          </select>
          <button onClick={loadLogs} className="btn-secondary text-sm">
            Refresh
          </button>
        </div>
      </div>

      {logs.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-gray-500">No audit logs recorded yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="card py-3 px-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <LogLevelIndicator level={log.log_level} />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 capitalize">
                        {log.action.replace(/_/g, ' ')}
                      </span>
                      {log.processing_stage && (
                        <span className="text-xs text-gray-400">
                          ({log.processing_stage})
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{log.message}</p>
                  </div>
                </div>
                <div className="text-right flex-shrink-0 ml-4">
                  <p className="text-xs text-gray-400">
                    {new Date(log.created_at).toLocaleString()}
                  </p>
                  {log.correlation_id && (
                    <p className="text-xs text-gray-300 font-mono mt-0.5">
                      {log.correlation_id.slice(0, 8)}...
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LogLevelIndicator({ level }: { level: string }) {
  const colorMap: Record<string, string> = {
    info: 'bg-blue-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
    debug: 'bg-gray-400',
  };

  return (
    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${colorMap[level] || 'bg-gray-400'}`} />
  );
}
