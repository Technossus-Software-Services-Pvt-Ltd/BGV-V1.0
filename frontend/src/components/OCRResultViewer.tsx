import { OCRResult } from '../types';

interface OCRResultViewerProps {
  results: OCRResult[];
}

export default function OCRResultViewer({ results }: OCRResultViewerProps) {
  if (results.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">OCR Results</h3>
        <p className="text-sm text-gray-500">No OCR results available yet.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">OCR Results</h3>
      <div className="space-y-4">
        {results.map((result) => (
          <div key={result.id} className="border border-gray-200 rounded-lg p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">
                {result.ocr_engine}
              </span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {result.word_count} words
                </span>
                {result.processing_duration_ms && (
                  <span className="text-xs text-gray-500">
                    {result.processing_duration_ms}ms
                  </span>
                )}
                {result.confidence_score !== null && (
                  <ConfidenceIndicator score={result.confidence_score} />
                )}
              </div>
            </div>
            <pre className="text-sm text-gray-800 bg-gray-50 p-3 rounded-md overflow-auto max-h-48 whitespace-pre-wrap font-mono">
              {result.extracted_text}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfidenceIndicator({ score }: { score: number }) {
  const percentage = (score * 100).toFixed(1);
  const color = score >= 0.85 ? 'text-green-600' : score >= 0.6 ? 'text-yellow-600' : 'text-red-600';

  return (
    <span className={`text-xs font-medium ${color}`}>
      {percentage}%
    </span>
  );
}
