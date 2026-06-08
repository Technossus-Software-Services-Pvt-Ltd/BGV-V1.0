import { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { uploadDocuments } from '../api/endpoints';
import { UploadResponse } from '../types';

interface ManualUploadFormProps {
  onError: (message: string) => void;
}

export default function ManualUploadForm({ onError }: ManualUploadFormProps) {
  const [candidateId, setCandidateId] = useState('');
  const [candidateName, setCandidateName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!candidateId || !candidateName || files.length === 0) return;

    setUploading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('candidate_id', candidateId);
      formData.append('candidate_name', candidateName);
      files.forEach((file) => formData.append('files', file));

      const response = await uploadDocuments(formData);
      setResult(response);
      setFiles([]);
      setCandidateId('');
      setCandidateName('');
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <details className="card">
      <summary className="cursor-pointer text-sm font-medium text-gray-600 hover:text-gray-900">
        Manual Single-Candidate Upload
      </summary>
      <div className="mt-4 space-y-4">
        {result && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-green-800 mb-2">Upload Successful</h3>
            <p className="text-sm text-green-700">{result.message}</p>
            <p className="text-xs text-green-600 mt-1">
              Batch: {result.batch_reference} | Correlation: {result.correlation_id}
            </p>
            <div className="mt-3 flex gap-2">
              {result.documents.map((doc) => (
                <Link key={doc.id} to={`/documents/${doc.id}`} className="text-xs text-primary-600 hover:underline">
                  {doc.filename}
                </Link>
              ))}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Candidate ID *</label>
              <input type="text" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} className="input-field" placeholder="e.g., CAND-001" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
              <input type="text" value={candidateName} onChange={(e) => setCandidateName(e.target.value)} className="input-field" placeholder="e.g., Rajesh Kumar" required />
            </div>
          </div>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-200 rounded-2xl p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/30 transition-all duration-200 group"
          >
            <p className="text-sm text-gray-600">Click to select document files</p>
            <p className="text-xs text-gray-400">PDF, JPEG, PNG up to 15MB each. Max 20 files.</p>
          </div>
          <input ref={fileInputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png" aria-label="Select document files" onChange={(e) => { if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)].slice(0, 20)); }} className="hidden" />

          {files.length > 0 && (
            <div className="space-y-1">
              {files.map((file, index) => (
                <div key={index} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded">
                  <span className="text-sm text-gray-700 truncate">{file.name}</span>
                  <button type="button" onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))} className="text-gray-400 hover:text-red-500 text-xs">Remove</button>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end">
            <button type="submit" disabled={uploading || !candidateId || !candidateName || files.length === 0} className="btn-primary">
              {uploading ? 'Uploading...' : `Upload ${files.length} Document${files.length !== 1 ? 's' : ''}`}
            </button>
          </div>
        </form>
      </div>
    </details>
  );
}
