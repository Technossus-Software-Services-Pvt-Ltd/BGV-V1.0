import { useState, useEffect, useRef, useCallback } from 'react';
import IntegrationsSection from '../components/IntegrationsSection';
import DocumentRulesSection from '../components/DocumentRulesSection';
import FileNamingSection from '../components/FileNamingSection';

type SectionId = 'integrations' | 'document-rules' | 'file-naming';

const SECTION_META: { id: SectionId; label: string; icon: string }[] = [
  { id: 'integrations', label: 'Integrations', icon: '🔗' },
  { id: 'document-rules', label: 'Document Rules', icon: '📄' },
  { id: 'file-naming', label: 'File Naming', icon: '📁' },
];

export default function SettingsPage() {
  const sectionRefs = useRef<Record<SectionId, HTMLElement | null>>({
    integrations: null,
    'document-rules': null,
    'file-naming': null,
  });

  const [activeSection, setActiveSection] = useState<SectionId>('integrations');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleError = useCallback((msg: string) => {
    setError(msg);
    setSuccess(null);
  }, []);

  const handleSuccess = useCallback((msg: string) => {
    setSuccess(msg);
    setError(null);
  }, []);

  useEffect(() => {
    const syncActiveSectionByScroll = () => {
      const activationOffset = 180;
      let nextActive: SectionId = SECTION_META[0].id;

      for (const section of SECTION_META) {
        const element = sectionRefs.current[section.id];
        if (!element) continue;
        if (element.getBoundingClientRect().top <= activationOffset) {
          nextActive = section.id;
        } else {
          break;
        }
      }

      setActiveSection((current) => (current === nextActive ? current : nextActive));
    };

    syncActiveSectionByScroll();
    window.addEventListener('scroll', syncActiveSectionByScroll, { passive: true });
    window.addEventListener('resize', syncActiveSectionByScroll);

    return () => {
      window.removeEventListener('scroll', syncActiveSectionByScroll);
      window.removeEventListener('resize', syncActiveSectionByScroll);
    };
  }, []);

  const handleJumpToSection = (sectionId: SectionId) => {
    setActiveSection(sectionId);
    sectionRefs.current[sectionId]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-6 pb-8 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage integrations, required document checklist, and file naming rules.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200/60 bg-rose-50 p-4 flex items-start justify-between gap-4">
          <p className="text-sm text-rose-700 font-medium">{error}</p>
          <button onClick={() => setError(null)} className="text-xs font-semibold text-rose-600 hover:text-rose-700">
            Dismiss
          </button>
        </div>
      )}

      {success && (
        <div className="rounded-xl border border-emerald-200/60 bg-emerald-50 p-4 flex items-start justify-between gap-4">
          <p className="text-sm text-emerald-700 font-medium">{success}</p>
          <button onClick={() => setSuccess(null)} className="text-xs font-semibold text-emerald-600 hover:text-emerald-700">
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="h-fit rounded-2xl border border-gray-100 bg-white p-3 shadow-card backdrop-blur lg:sticky lg:top-24">
          <p className="px-3 pb-2 text-[10px] font-bold tracking-[0.2em] text-gray-400 uppercase">SETTINGS</p>
          <nav className="space-y-1" aria-label="Settings Navigation">
            {SECTION_META.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleJumpToSection(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`group flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2 ${
                    active
                      ? 'border-primary-100 bg-primary-50 font-semibold text-primary-700 shadow-sm'
                      : 'border-transparent bg-white text-gray-500 hover:border-gray-200 hover:bg-gray-50 hover:text-gray-700'
                  }`}
                >
                  <span className={`${active ? 'text-[#d5c7dc]' : 'text-[#cfc4d9] group-hover:text-[#bca9cd]'}`}>{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="space-y-8">
          <section
            id="integrations"
            ref={(element) => { sectionRefs.current.integrations = element; }}
            className="scroll-mt-24"
          >
            <IntegrationsSection onError={handleError} onSuccess={handleSuccess} />
          </section>

          <section
            id="document-rules"
            ref={(element) => { sectionRefs.current['document-rules'] = element; }}
            className="scroll-mt-24"
          >
            <DocumentRulesSection onError={handleError} onSuccess={handleSuccess} />
          </section>

          <section
            id="file-naming"
            ref={(element) => { sectionRefs.current['file-naming'] = element; }}
            className="scroll-mt-24"
          >
            <FileNamingSection onError={handleError} onSuccess={handleSuccess} />
          </section>
        </section>
      </div>
    </div>
  );
}
