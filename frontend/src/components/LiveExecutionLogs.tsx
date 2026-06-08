import { useEffect, useRef, useCallback } from 'react';
import { BatchLogEntry } from '../types';

interface LiveExecutionLogsProps {
  logs: BatchLogEntry[];
  onClear: () => void;
}

export default function LiveExecutionLogs({ logs, onClear }: LiveExecutionLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Consider "near bottom" if within 50px of the bottom
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
  }, []);

  useEffect(() => {
    if (scrollRef.current && isNearBottomRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">
          Processing Logs
        </h3>
        {logs.length > 0 && (
          <button onClick={onClear} className="text-xs text-gray-400 hover:text-gray-600 transition-colors">
            Clear
          </button>
        )}
      </div>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 bg-gray-900 rounded-xl p-4 overflow-y-auto max-h-[440px] font-mono text-xs leading-relaxed"
      >
        {logs.length === 0 ? (
          <div className="flex items-center justify-center h-full min-h-[120px] text-gray-500">
            <p>Waiting for processing to start...</p>
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={log.id || idx} className="py-0.5">
              <span className="text-gray-400">
                {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              {' '}
              <span className={`${log.level === 'warning' ? 'text-amber-400' : 'text-sky-300'}`}>
                [{log.level.toUpperCase()}]
              </span>
              {' '}
              <span className="text-amber-300">
                {log.stage}
              </span>
              {'   '}
              <span className={`${log.level === 'warning' ? 'text-amber-400' : 'text-gray-200'}`}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
