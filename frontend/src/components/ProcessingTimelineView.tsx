import { ProcessingEvent } from '../types';

interface ProcessingTimelineViewProps {
  events: ProcessingEvent[];
  currentStatus: string;
  totalDurationMs: number | null;
}

export default function ProcessingTimelineView({
  events,
  currentStatus,
  totalDurationMs,
}: ProcessingTimelineViewProps) {
  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Processing Timeline</h3>
        {totalDurationMs && (
          <span className="text-sm text-gray-500">
            Total: {(totalDurationMs / 1000).toFixed(2)}s
          </span>
        )}
      </div>

      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />

        <div className="space-y-4">
          {events.map((event, index) => (
            <div key={event.id} className="relative flex items-start gap-4 pl-10">
              <div
                className={`absolute left-2.5 w-3 h-3 rounded-full border-2 ${
                  index === events.length - 1
                    ? currentStatus === 'completed'
                      ? 'bg-green-500 border-green-500'
                      : currentStatus === 'failed'
                      ? 'bg-red-500 border-red-500'
                      : 'bg-yellow-500 border-yellow-500'
                    : 'bg-white border-primary-500'
                }`}
              />

              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start">
                  <p className="text-sm font-medium text-gray-900 capitalize">
                    {event.stage.replace(/_/g, ' ')}
                  </p>
                  {event.duration_ms && (
                    <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                      {event.duration_ms}ms
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{event.message}</p>
                {event.confidence !== null && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Confidence: {(event.confidence * 100).toFixed(1)}%
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
