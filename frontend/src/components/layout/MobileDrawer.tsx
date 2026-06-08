import { useEffect } from 'react';
import SidebarNav from './NavigationItems';

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileDrawer({ open, onClose }: MobileDrawerProps) {

  // Trap focus inside drawer when open
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  return (
    <div
      className={`fixed inset-0 z-40 lg:hidden transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-hidden={!open}
    >
      <button
        type="button"
        aria-label="Close navigation"
        className="absolute inset-0 bg-slate-950/50"
        onClick={onClose}
      />
      <aside className="relative h-full w-[17rem] bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 text-white shadow-xl">
        <div className="border-b border-white/[0.08] px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-xs">BGV</span>
            </div>
            <span className="font-bold text-white">BGV Platform</span>
          </div>
          <button
            type="button"
            aria-label="Close menu"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] text-slate-200 hover:bg-white/[0.08] transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden="true">
              <path d="M6 6l12 12" />
              <path d="M18 6L6 18" />
            </svg>
          </button>
        </div>
        <div className="px-3 py-4">
          <SidebarNav onItemClick={onClose} />
        </div>
      </aside>
    </div>
  );
}
