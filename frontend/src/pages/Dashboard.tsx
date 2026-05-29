import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { checkHealth, listDocuments, listBatches } from '../api/endpoints';
import { DocumentListItem, BatchInfo, HealthStatus } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [batches, setBatches] = useState<BatchInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, docsData, batchData] = await Promise.all([
        checkHealth(),
        listDocuments({ limit: 10 }),
        listBatches({ limit: 5 }),
      ]);
      setHealth(healthData);
      setDocuments(docsData);
      setBatches(batchData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <LoadingSpinner message="Loading dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <Link to="/upload" className="btn-primary">
          Upload Documents
        </Link>
      </div>

      {/* System Health */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <HealthCard
          title="API Server"
          status={health?.services.api ?? false}
        />
        <HealthCard
          title="Ollama LLM"
          status={health?.services.ollama ?? false}
        />
        <HealthCard
          title="AI Model"
          status={health?.services.ollama_model ?? false}
        />
      </div>

      {/* Recent Batches */}
      {batches.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Upload Batches</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 font-medium text-gray-500">Reference</th>
                  <th className="text-left py-2 font-medium text-gray-500">Files</th>
                  <th className="text-left py-2 font-medium text-gray-500">Processed</th>
                  <th className="text-left py-2 font-medium text-gray-500">Failed</th>
                  <th className="text-left py-2 font-medium text-gray-500">Status</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch) => (
                  <tr key={batch.id} className="border-b border-gray-100">
                    <td className="py-2 font-mono text-xs">{batch.batch_reference}</td>
                    <td className="py-2">{batch.total_files}</td>
                    <td className="py-2">{batch.processed_files}</td>
                    <td className="py-2">{batch.failed_files}</td>
                    <td className="py-2">
                      <StatusBadge status={batch.processing_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Documents */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Documents</h2>
          <Link to="/documents" className="text-sm text-primary-600 hover:text-primary-700">
            View all
          </Link>
        </div>
        {documents.length === 0 ? (
          <p className="text-sm text-gray-500">No documents uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 font-medium text-gray-500">Filename</th>
                  <th className="text-left py-2 font-medium text-gray-500">Size</th>
                  <th className="text-left py-2 font-medium text-gray-500">Type</th>
                  <th className="text-left py-2 font-medium text-gray-500">Status</th>
                  <th className="text-left py-2 font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 font-medium">{doc.original_filename}</td>
                    <td className="py-2 text-gray-500">{formatFileSize(doc.file_size_bytes)}</td>
                    <td className="py-2 text-gray-500">{doc.mime_type}</td>
                    <td className="py-2">
                      <StatusBadge status={doc.processing_status} />
                    </td>
                    <td className="py-2">
                      <Link
                        to={`/documents/${doc.id}`}
                        className="text-primary-600 hover:text-primary-700 text-xs font-medium"
                      >
                        Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function HealthCard({ title, status }: { title: string; status: boolean }) {
  return (
    <div className="card flex items-center gap-3">
      <div
        className={`w-3 h-3 rounded-full ${status ? 'bg-green-500' : 'bg-red-500'}`}
      />
      <div>
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className={`text-xs ${status ? 'text-green-600' : 'text-red-600'}`}>
          {status ? 'Healthy' : 'Unavailable'}
        </p>
      </div>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
