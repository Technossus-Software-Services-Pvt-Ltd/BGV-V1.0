export function statusColor(status: string): string {
  switch (status) {
    case 'completed': return 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/10';
    case 'partial': return 'bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-600/10';
    case 'awaiting_required_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
    case 'processing': case 'discovering': case 'downloading': return 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/10';
    case 'failed': return 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-600/10';
    case 'pending': return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
    case 'skipped': case 'no_documents': return 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/10';
    default: return 'bg-gray-50 text-gray-600 ring-1 ring-inset ring-gray-500/10';
  }
}
