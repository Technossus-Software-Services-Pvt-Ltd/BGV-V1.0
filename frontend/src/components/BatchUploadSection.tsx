import { useRef } from 'react';

interface BatchUploadSectionProps {
  batchFile: File | null;
  setBatchFile: (file: File | null) => void;
  batchUploading: boolean;
  onUpload: () => void;
}

export default function BatchUploadSection({
  batchFile,
  setBatchFile,
  batchUploading,
  onUpload,
}: BatchUploadSectionProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="card">
      <div
        role="button"
        tabIndex={0}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
        className="border-2 border-dashed border-gray-200 rounded-2xl p-10 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/30 transition-all duration-200 group focus:outline-none focus:ring-2 focus:ring-primary-500/40 focus:ring-offset-2"
      >
        <div className="mx-auto h-14 w-14 rounded-2xl bg-gray-100 group-hover:bg-primary-100 flex items-center justify-center transition-colors mb-3">
          <svg className="h-7 w-7 text-gray-400 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <p className="mt-2 text-sm text-gray-600">
          {batchFile ? batchFile.name : 'Click to select an Excel (.xlsx) or CSV file'}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          Required columns: candidate_id, name. Optional: email, phone, dob, gender
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.csv"
        onChange={(e) => {
          if (e.target.files?.[0]) setBatchFile(e.target.files[0]);
        }}
        className="hidden"
      />

      {batchFile && (
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">{batchFile.name}</span>
            <span className="text-xs text-gray-400">({(batchFile.size / 1024).toFixed(0)} KB)</span>
            <button onClick={() => setBatchFile(null)} className="text-gray-400 hover:text-red-500 text-xs ml-2">Remove</button>
          </div>
          <button
            onClick={onUpload}
            disabled={batchUploading}
            className="btn-primary"
          >
            {batchUploading ? 'Uploading...' : 'Upload & Parse'}
          </button>
        </div>
      )}
    </div>
  );
}
