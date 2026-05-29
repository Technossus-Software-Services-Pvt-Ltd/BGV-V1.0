import { ValidationResult } from '../types';

interface ValidationResultViewerProps {
  results: ValidationResult[];
}

export default function ValidationResultViewer({ results }: ValidationResultViewerProps) {
  if (results.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Validation Results</h3>
        <p className="text-sm text-gray-500">No validation results available yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Validation Results</h3>
      <div className="space-y-4">
        {results.map((result) => (
          <div key={result.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-sm font-medium text-gray-900">Ownership Verification</h4>
                <span className="text-xs text-gray-500">{result.validation_status}</span>
              </div>
              <span
                className={`badge ${
                  result.ownership_confirmed ? 'badge-success' : 'badge-error'
                }`}
              >
                {result.ownership_confirmed ? 'Confirmed' : 'Not Confirmed'}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4 mb-3">
              <CheckItem label="Name Match" passed={result.name_match ?? false} score={result.name_match_score ?? undefined} />
            </div>

            {result.validation_reasoning && (
              <div className="bg-gray-50 rounded-md p-3 mt-2">
                <p className="text-xs font-medium text-gray-500 mb-1">Reasoning</p>
                <p className="text-sm text-gray-700">{result.validation_reasoning}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckItem({
  label,
  passed,
  score,
}: {
  label: string;
  passed: boolean;
  score?: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-4 h-4 rounded-full flex items-center justify-center ${
          passed ? 'bg-green-100' : 'bg-red-100'
        }`}
      >
        {passed ? (
          <svg className="w-3 h-3 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        ) : (
          <svg className="w-3 h-3 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </div>
      <div>
        <span className="text-xs text-gray-700">{label}</span>
        {score !== undefined && (
          <span className="text-xs text-gray-400 ml-1">({score.toFixed(0)}%)</span>
        )}
      </div>
    </div>
  );
}
