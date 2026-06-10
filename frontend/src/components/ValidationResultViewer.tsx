import { ValidationResult } from '../types';

interface ValidationResultViewerProps {
  results: ValidationResult[];
  openaiEnabled?: boolean;
}

export default function ValidationResultViewer({ results, openaiEnabled }: ValidationResultViewerProps) {
  if (results.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-bold text-gray-900 mb-2">Validation Results</h3>
        <p className="text-sm text-gray-500">No validation results available yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-bold text-gray-900 mb-4">Validation Results</h3>
      <div className="space-y-4">
        {results.map((result) => (
          <div key={result.id} className="border border-gray-100 rounded-xl p-4">
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
              <div className="bg-gray-50/80 rounded-xl p-3 mt-2">
                <p className="text-xs font-medium text-gray-500 mb-1">Reasoning</p>
                <p className="text-sm text-gray-700">{result.validation_reasoning}</p>
              </div>
            )}

            {openaiEnabled && result.openai_fallback_used && (
              <OpenAIResultSection result={result} />
            )}

            {openaiEnabled && result.openai_error && !result.openai_fallback_used && (
              <div className="bg-red-50/80 rounded-xl p-3 mt-2">
                <p className="text-xs font-medium text-red-600 mb-1">OpenAI Fallback Error</p>
                <p className="text-sm text-red-700">{result.openai_error}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function safeParseArray(json: string | null): string[] {
  if (!json) return [];
  try {
    const parsed = JSON.parse(json);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function OpenAIResultSection({ result }: { result: ValidationResult }) {
  const keyEvidence = safeParseArray(result.openai_key_evidence_json);
  const concerns = safeParseArray(result.openai_concerns_json);

  return (
    <div className="bg-blue-50/80 rounded-xl p-3 mt-3 border border-blue-100">
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <p className="text-xs font-semibold text-blue-700">OpenAI Fallback Result</p>
        {result.openai_confidence !== null && (
          <span className="ml-auto text-xs font-medium text-blue-600">
            Confidence: {(result.openai_confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {result.openai_reasoning && (
        <div className="mb-2">
          <p className="text-xs font-medium text-gray-500 mb-1">AI Reasoning</p>
          <p className="text-sm text-gray-700">{result.openai_reasoning}</p>
        </div>
      )}

      {(result.openai_extracted_owner_name || result.openai_extracted_owner_dob || result.openai_name_match_score !== null) && (
        <div className="mb-2 bg-white/60 rounded-lg p-2 border border-blue-50">
          <p className="text-xs font-medium text-gray-500 mb-1">Extracted Owner Details</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            {result.openai_extracted_owner_name && (
              <>
                <span className="text-gray-500">Owner Name:</span>
                <span className="text-gray-800 font-medium">{result.openai_extracted_owner_name}</span>
              </>
            )}
            {result.openai_extracted_owner_dob && (
              <>
                <span className="text-gray-500">Owner DOB:</span>
                <span className="text-gray-800 font-medium">{result.openai_extracted_owner_dob}</span>
              </>
            )}
            {result.openai_name_match_score !== null && (
              <>
                <span className="text-gray-500">Name Match Score:</span>
                <span className={`font-medium ${result.openai_name_match_score >= 85 ? 'text-emerald-700' : result.openai_name_match_score >= 60 ? 'text-amber-700' : 'text-rose-700'}`}>
                  {result.openai_name_match_score.toFixed(1)}%
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {keyEvidence.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-medium text-gray-500 mb-1">Key Evidence</p>
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-0.5">
            {keyEvidence.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {concerns.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-medium text-amber-600 mb-1">Concerns</p>
          <ul className="list-disc list-inside text-sm text-amber-700 space-y-0.5">
            {concerns.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-400">
        {result.openai_model_used && <span>Model: {result.openai_model_used}</span>}
        {result.openai_duration_ms !== null && <span>Duration: {result.openai_duration_ms}ms</span>}
        {result.openai_total_tokens !== null && <span>Tokens: {result.openai_total_tokens}</span>}
        {result.openai_cost_usd !== null && <span>Cost: ${result.openai_cost_usd.toFixed(4)}</span>}
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
          passed ? 'bg-emerald-100' : 'bg-rose-100'
        }`}
      >
        {passed ? (
          <svg className="w-3 h-3 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        ) : (
          <svg className="w-3 h-3 text-rose-600" fill="currentColor" viewBox="0 0 20 20">
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
