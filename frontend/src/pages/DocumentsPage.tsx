import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { listDocuments } from '../api/endpoints';
import { DocumentListItem } from '../types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocuments = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await listDocuments({
        status_filter: statusFilter || undefined,
        limit: 100,
      });
      setDocuments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [statusFilter]);

  // Auto-poll every 5 seconds if any document is still processing
  useEffect(() => {
    const hasProcessing = documents.some(
      (doc) => !['completed', 'failed', 'ocr_failed'].includes(doc.processing_status)
    );
    if (hasProcessing) {
      pollRef.current = setInterval(() => loadDocuments(false), 5000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [documents]);

  if (loading) return <LoadingSpinner message="Loading documents..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadDocuments} />;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-auto text-sm"
          >
            <option value="">All Statuses</option>
            <option value="uploaded">Uploaded</option>
            <option value="ocr_processing">OCR Processing</option>
            <option value="ocr_complete">OCR Complete</option>
            <option value="classified">Classified</option>
            <option value="validated">Validated</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <Link to="/upload" className="btn-primary">
            Upload New
          </Link>
        </div>
      </div>

      {documents.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-gray-500">No documents found.</p>
          <Link to="/upload" className="text-primary-600 hover:underline text-sm mt-2 inline-block">
            Upload your first document
          </Link>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Filename</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Size</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Type</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Date</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium text-gray-900 max-w-xs truncate">
                    {doc.original_filename}
                  </td>
                  <td className="py-3 px-4 text-gray-500">{formatFileSize(doc.file_size_bytes)}</td>
                  <td className="py-3 px-4 text-gray-500 text-xs">{doc.mime_type}</td>
                  <td className="py-3 px-4">
                    <StatusBadge status={doc.processing_status} />
                  </td>
                  <td className="py-3 px-4 text-gray-500 text-xs">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4">
                    <Link
                      to={`/documents/${doc.id}`}
                      className="text-primary-600 hover:text-primary-700 font-medium text-xs"
                    >
                      View Detail
                    </Link>
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

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
