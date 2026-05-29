import { Classification } from '../types';

interface ClassificationViewerProps {
  classifications: Classification[];
}

export default function ClassificationViewer({ classifications }: ClassificationViewerProps) {
  if (classifications.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">AI Classification</h3>
        <p className="text-sm text-gray-500">No classification results available yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Classification</h3>
      <div className="space-y-4">
        {classifications.map((cls) => (
          <div key={cls.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex justify-between items-center mb-3">
              <div>
                <span className="text-sm font-medium text-gray-700">{cls.model_used}</span>
                <span className="ml-3 px-2 py-0.5 bg-primary-50 text-primary-700 text-xs font-medium rounded">
                  {cls.document_type.replace(/_/g, ' ')}
                </span>
              </div>
              <span
                className={`text-xs font-medium ${
                  cls.confidence_score >= 0.85
                    ? 'text-green-600'
                    : cls.confidence_score >= 0.6
                    ? 'text-yellow-600'
                    : 'text-red-600'
                }`}
              >
                {(cls.confidence_score * 100).toFixed(1)}% confidence
              </span>
            </div>

            {cls.ai_reasoning && (
              <p className="text-sm text-gray-600 mb-3 italic">"{cls.ai_reasoning}"</p>
            )}

            {(cls.extracted_name || cls.extracted_dob || cls.extracted_id_number) && (
              <div className="bg-gray-50 rounded-md p-3">
                <p className="text-xs font-medium text-gray-500 mb-2">Extracted Fields</p>
                <dl className="grid grid-cols-2 gap-2">
                  {cls.extracted_name && (
                    <div>
                      <dt className="text-xs text-gray-500">Name</dt>
                      <dd className="text-sm text-gray-900">{cls.extracted_name}</dd>
                    </div>
                  )}
                  {cls.extracted_dob && (
                    <div>
                      <dt className="text-xs text-gray-500">Date of Birth</dt>
                      <dd className="text-sm text-gray-900">{cls.extracted_dob}</dd>
                    </div>
                  )}
                  {cls.extracted_id_number && (
                    <div>
                      <dt className="text-xs text-gray-500">ID Number</dt>
                      <dd className="text-sm text-gray-900">{cls.extracted_id_number}</dd>
                    </div>
                  )}
                </dl>
              </div>
            )}

            {cls.processing_duration_ms && (
              <div className="flex gap-4 mt-3 pt-3 border-t border-gray-100">
                <span className="text-xs text-gray-400">Duration: {cls.processing_duration_ms}ms</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
