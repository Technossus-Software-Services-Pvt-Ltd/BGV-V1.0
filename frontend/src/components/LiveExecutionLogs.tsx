import { useEffect, useRef } from 'react';
import { BatchLogEntry } from '../types';

interface LiveExecutionLogsProps {
  logs: BatchLogEntry[];
  onClear: () => void;
}

export default function LiveExecutionLogs({ logs }: LiveExecutionLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">
          Processing Logs
        </h3>
      </div>
      <div
        ref={scrollRef}
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
                {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} {log.level === 'warning' ? 'AM' : 'AM'}
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
