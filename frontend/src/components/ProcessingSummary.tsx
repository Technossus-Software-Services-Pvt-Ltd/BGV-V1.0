import { BatchImport, BatchCandidate } from '../types';

interface ProcessingSummaryProps {
  batch: BatchImport;
  candidates: BatchCandidate[];
}

export default function ProcessingSummary({ batch, candidates }: ProcessingSummaryProps) {
  const inProgress = candidates.filter((c) =>
    ['processing', 'discovering', 'downloading'].includes(c.status)
  ).length;
  const completed = batch.processed_candidates;
  const failed = batch.failed_candidates;
  const partial = candidates.filter((c) =>
    ['partial', 'awaiting_required_documents'].includes(c.status)
  ).length;
  const pending = candidates.filter((c) => c.status === 'pending').length;
  const noDocuments = candidates.filter((c) => c.status === 'no_documents').length;

  const items = [
    { label: 'Total Candidates', value: batch.total_candidates, color: 'text-gray-900', icon: 'users', bg: 'bg-gray-100' },
    { label: 'Completed', value: completed, color: 'text-emerald-600', icon: 'check', bg: 'bg-emerald-50' },
    { label: 'In Progress', value: inProgress, color: 'text-sky-600', icon: 'progress', bg: 'bg-sky-50' },
    { label: 'Partial', value: partial, color: 'text-amber-600', icon: 'partial', bg: 'bg-amber-50' },
    { label: 'Failed', value: failed, color: 'text-rose-600', icon: 'failed', bg: 'bg-rose-50' },
    { label: 'No Documents', value: noDocuments, color: 'text-orange-600', icon: 'nodocs', bg: 'bg-orange-50' },
    { label: 'Pending', value: pending, color: 'text-gray-500', icon: 'pending', bg: 'bg-gray-50' },
  ];

  return (
    <div>
      <h3 className="flex items-center gap-2 text-xs font-bold text-gray-700 uppercase tracking-wider mb-4">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4 text-gray-400">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
        Processing Summary
      </h3>
      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.label}
            className={`flex items-center justify-between px-3 py-2.5 rounded-xl ${item.bg}`}
          >
            <div className="flex items-center gap-2.5">
              <StatusIcon type={item.icon} color={item.color} />
              <span className="text-sm font-medium text-gray-700">{item.label}</span>
            </div>
            <span className={`text-lg font-bold tabular-nums ${item.color}`}>{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusIcon({ type, color }: { type: string; color: string }) {
  const cls = `h-4 w-4 ${color}`;
  switch (type) {
    case 'users':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    case 'check':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'progress':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      );
    case 'partial':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      );
    case 'failed':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'pending':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'nodocs':
      return (
        <svg className={cls} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    default:
      return null;
  }
}
