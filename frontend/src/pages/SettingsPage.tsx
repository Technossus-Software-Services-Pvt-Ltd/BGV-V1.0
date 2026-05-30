import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getGmailAuthUrl,
  getGmailStatus,
  disconnectGmail,
  getDriveConfig,
  updateDriveConfig,
  validateIntegration,
  listRequiredDocuments,
  saveRequiredDocuments,
  getFileNamingRule,
  saveFileNamingRule,
} from '../api/endpoints';
import { GmailStatus, RequiredDocumentRuleInput } from '../types';

type SectionId = 'integrations' | 'document-rules' | 'file-naming';

type ChecklistRow = RequiredDocumentRuleInput & { local_id: string };

const SUPPORTED_FORMATS = ['pdf', 'jpg', 'png'];

const DEFAULT_CHECKLIST: ChecklistRow[] = [
  {
    local_id: crypto.randomUUID(),
    document_name: 'Aadhaar Card',
    category: 'Identity',
    is_mandatory: true,
    accepted_formats: ['pdf', 'jpg', 'png'],
    sort_order: 0,
    is_active: true,
  },
  {
    local_id: crypto.randomUUID(),
    document_name: 'PAN Card',
    category: 'Identity',
    is_mandatory: true,
    accepted_formats: ['pdf', 'jpg', 'png'],
    sort_order: 1,
    is_active: true,
  },
];

function groupByCategory(rows: ChecklistRow[]): Map<string, ChecklistRow[]> {
  const map = new Map<string, ChecklistRow[]>();
  for (const row of rows) {
    const cat = row.category || 'Uncategorized';
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat)!.push(row);
  }
  return map;
}

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
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const [activeSection, setActiveSection] = useState<SectionId>('integrations');
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);

  const [storageRootInput, setStorageRootInput] = useState('');
  const [savingDrive, setSavingDrive] = useState(false);
  const [isEditingDrive, setIsEditingDrive] = useState(false);
  const [checklistRows, setChecklistRows] = useState<ChecklistRow[]>([]);
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ChecklistRow | null>(null);
  const [savingChecklist, setSavingChecklist] = useState(false);
  const [folderStructurePattern, setFolderStructurePattern] = useState('');
  const [fileRenamePattern, setFileRenamePattern] = useState('');
  const [fileNamingExample, setFileNamingExample] = useState('');
  const [savingFileNaming, setSavingFileNaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const [status, drive, requiredDocs, namingRule] = await Promise.all([
        getGmailStatus(),
        getDriveConfig(),
        listRequiredDocuments(),
        getFileNamingRule(),
      ]);
      setGmailStatus(status);
      setStorageRootInput(drive.storage_root_folder_id || '');
      setFolderStructurePattern(namingRule.folder_structure_pattern);
      setFileRenamePattern(namingRule.file_rename_pattern);
      setFileNamingExample(namingRule.example_output);
      setChecklistRows(
        requiredDocs.length === 0
          ? DEFAULT_CHECKLIST
          : requiredDocs
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((item, idx) => ({
                local_id: item.id || `${item.document_name}-${idx}`,
                document_name: item.document_name,
                category: item.category,
                is_mandatory: item.is_mandatory,
                accepted_formats: item.accepted_formats,
                sort_order: item.sort_order,
                is_active: item.is_active,
              })),
      );
    } catch {
      setError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  useEffect(() => {
    const syncActiveSectionByScroll = () => {
      const activationOffset = 180;
      let nextActive: SectionId = SECTION_META[0].id;

      for (const section of SECTION_META) {
        const element = sectionRefs.current[section.id];
        if (!element) {
          continue;
        }
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

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'gmail-oauth-success') {
        setConnecting(false);
        setSuccess('Gmail connected successfully!');
        loadStatus();
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [loadStatus]);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    setTestResult(null);
    try {
      const { auth_url } = await getGmailAuthUrl();
      const w = 600, h = 700;
      const left = window.screenX + (window.outerWidth - w) / 2;
      const top = window.screenY + (window.outerHeight - h) / 2;
      window.open(auth_url, 'gmail-oauth', `width=${w},height=${h},left=${left},top=${top}`);
    } catch {
      setError('Failed to start Google login. Check server configuration.');
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setError(null);
    setTestResult(null);
    try {
      await disconnectGmail();
      setSuccess('Gmail disconnected');
      await loadStatus();
    } catch {
      setError('Failed to disconnect');
    } finally {
      setDisconnecting(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await validateIntegration('gmail');
      setTestResult(result);
    } catch {
      setTestResult({ status: 'error', message: 'Validation request failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleSaveDriveConfig = async () => {
    setSavingDrive(true);
    setError(null);
    try {
      await updateDriveConfig({ search_folder_ids: [], storage_root_folder_id: storageRootInput.trim() || null });
      setSuccess('Drive configuration saved');
      await loadStatus();
      setIsEditingDrive(false);
    } catch {
      setError('Failed to save Drive configuration');
    } finally {
      setSavingDrive(false);
    }
  };

  // Per-row inline edit
  const handleStartEdit = (row: ChecklistRow) => {
    setEditingRowId(row.local_id);
    setEditDraft({ ...row });
  };

  const handleCancelEdit = () => {
    setEditingRowId(null);
    setEditDraft(null);
  };

  const handleDraftChange = (
    field: keyof RequiredDocumentRuleInput,
    value: string | boolean | string[] | number,
  ) => {
    setEditDraft((prev) => (prev ? { ...prev, [field]: value } : null));
  };

  const toggleDraftFormat = (format: string) => {
    if (!editDraft) return;
    const exists = editDraft.accepted_formats.includes(format);
    setEditDraft({
      ...editDraft,
      accepted_formats: exists
        ? editDraft.accepted_formats.filter((f) => f !== format)
        : [...editDraft.accepted_formats, format],
    });
  };

  const handleSaveRowEdit = () => {
    if (!editDraft) return;
    setChecklistRows((prev) =>
      prev.map((row) => (row.local_id === editDraft.local_id ? editDraft : row)),
    );
    setEditingRowId(null);
    setEditDraft(null);
  };

  const handleAddChecklistRow = () => {
    setChecklistRows((prev) => [
      ...prev,
      {
        local_id: crypto.randomUUID(),
        document_name: '',
        category: 'Identity',
        is_mandatory: true,
        accepted_formats: ['pdf'],
        sort_order: prev.length,
        is_active: true,
      },
    ]);
  };

  const handleRemoveChecklistRow = (rowId: string) => {
    setChecklistRows((prev) => prev.filter((row) => row.local_id !== rowId));
  };

  const handleSaveChecklist = async () => {
    setSavingChecklist(true);
    setError(null);
    try {
      const normalizedRows = checklistRows
        .map((row, idx) => ({
          document_name: row.document_name.trim(),
          category: row.category.trim(),
          is_mandatory: row.is_mandatory,
          accepted_formats: row.accepted_formats.map((fmt) => fmt.toLowerCase()),
          sort_order: idx,
          is_active: row.is_active,
        }))
        .filter((row) => row.document_name && row.category);

      if (normalizedRows.length === 0) {
        setError('Add at least one valid checklist row before saving');
        return;
      }

      const saved = await saveRequiredDocuments({ items: normalizedRows });
      setChecklistRows(
        saved
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((item, idx) => ({
            local_id: item.id || `${item.document_name}-${idx}`,
            document_name: item.document_name,
            category: item.category,
            is_mandatory: item.is_mandatory,
            accepted_formats: item.accepted_formats,
            sort_order: item.sort_order,
            is_active: item.is_active,
          })),
      );
      setSuccess('Required documents checklist saved');
    } catch {
      setError('Failed to save required documents checklist');
    } finally {
      setSavingChecklist(false);
    }
  };

  const handleSaveFileNaming = async () => {
    const normalizedFolderPattern = folderStructurePattern.trim();
    const normalizedFilePattern = fileRenamePattern.trim();

    if (!normalizedFolderPattern || !normalizedFilePattern) {
      setError('Folder and file naming patterns are required');
      return;
    }

    setSavingFileNaming(true);
    setError(null);
    try {
      const saved = await saveFileNamingRule({
        folder_structure_pattern: normalizedFolderPattern,
        file_rename_pattern: normalizedFilePattern,
      });
      setFolderStructurePattern(saved.folder_structure_pattern);
      setFileRenamePattern(saved.file_rename_pattern);
      setFileNamingExample(saved.example_output);
      setSuccess('File naming rules saved');
    } catch {
      setError('Failed to save file naming rules');
    } finally {
      setSavingFileNaming(false);
    }
  };

  const handleDownloadTemplate = () => {
    const rows = checklistRows.length > 0 ? checklistRows : DEFAULT_CHECKLIST;
    const csv = [
      'Document Name,Category,Mandatory,Accepted Formats',
      ...rows.map((row) => {
        const mandatoryText = row.is_mandatory ? 'Yes' : 'No';
        const formats = row.accepted_formats.join('|');
        return `${row.document_name},${row.category},${mandatoryText},${formats}`;
      }),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'required-documents-template.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const parseChecklistCsv = (text: string): ChecklistRow[] => {
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length <= 1) {
      return [];
    }

    const parsed: ChecklistRow[] = [];
    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(',');
      if (cols.length < 4) {
        continue;
      }

      const documentName = cols[0].trim();
      const category = cols[1].trim() || 'Identity';
      const mandatoryToken = cols[2].trim().toLowerCase();
      const acceptedFormats = cols
        .slice(3)
        .join(',')
        .split('|')
        .map((fmt) => fmt.trim().toLowerCase())
        .filter(Boolean);

      if (!documentName) {
        continue;
      }

      parsed.push({
        local_id: crypto.randomUUID(),
        document_name: documentName,
        category,
        is_mandatory: ['yes', 'true', '1'].includes(mandatoryToken),
        accepted_formats: acceptedFormats.length > 0 ? acceptedFormats : ['pdf'],
        sort_order: parsed.length,
        is_active: true,
      });
    }

    return parsed;
  };

  const handleUploadChecklist = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const text = await file.text();
      const parsed = parseChecklistCsv(text);
      if (parsed.length === 0) {
        setError('Uploaded file is empty or has invalid checklist rows');
      } else {
        setChecklistRows(parsed);
        setSuccess(`Loaded ${parsed.length} checklist rows from file`);
      }
    } catch {
      setError('Failed to read uploaded checklist file');
    } finally {
      event.target.value = '';
    }
  };

  const handleJumpToSection = (sectionId: SectionId) => {
    setActiveSection(sectionId);
    sectionRefs.current[sectionId]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  const connected = gmailStatus?.connected ?? false;

  return (
    <div className="space-y-6 pb-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage integrations, required document checklist, and file naming rules.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 flex items-start justify-between gap-4">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={() => setError(null)} className="text-xs font-medium text-red-600 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {success && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-4 flex items-start justify-between gap-4">
          <p className="text-sm text-green-700">{success}</p>
          <button onClick={() => setSuccess(null)} className="text-xs font-medium text-green-600 hover:underline">
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="h-fit rounded-3xl border border-gray-200/70 bg-white/95 p-3 shadow-[0_12px_30px_rgba(15,23,42,0.08)] backdrop-blur lg:sticky lg:top-24">
          <p className="px-3 pb-2 text-xs font-semibold tracking-[0.16em] text-gray-400">SETTINGS</p>
          <nav className="space-y-2" aria-label="Settings Navigation">
            {SECTION_META.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleJumpToSection(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`group flex w-full items-center gap-2 rounded-2xl border px-3 py-2.5 text-left text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 focus-visible:ring-offset-2 ${
                    active
                      ? 'border-primary-100 bg-primary-50 font-semibold text-primary-700 shadow-sm'
                      : 'border-transparent bg-white text-gray-500 hover:-translate-y-0.5 hover:border-gray-200 hover:bg-gray-50 hover:text-gray-700'
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
            ref={(element) => {
              sectionRefs.current.integrations = element;
            }}
            className="space-y-4 scroll-mt-24"
          >
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-gray-900">
                <span className="inline-flex items-center text-base text-[#d5c7dc]" aria-hidden="true">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
                    <path d="M10 13a5 5 0 0 1 0-7l1.6-1.6a5 5 0 0 1 7 7L17 13" />
                    <path d="M14 11a5 5 0 0 1 0 7l-1.6 1.6a5 5 0 1 1-7-7L7 11" />
                  </svg>
                </span>
                <span>Source Integrations</span>
              </h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Connect Gmail or Google Drive to automatically ingest candidate documents.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-start gap-3">
                  <div className="h-10 w-10 rounded-xl bg-red-100 text-red-600 flex items-center justify-center">
                    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-lg font-semibold text-gray-900">HR Gmail</h3>
                    <p className="text-xs text-gray-500">Automated email attachment monitoring</p>
                  </div>
                </div>

                <div className="space-y-2 rounded-xl bg-gray-50 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Account</span>
                    <span className="font-medium text-gray-800 truncate">{gmailStatus?.email || 'Not linked'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-500">Status</span>
                    <span className={`inline-flex items-center gap-1 text-sm font-medium ${connected ? 'text-green-700' : 'text-gray-500'}`}>
                      <span className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                      {connected ? 'Connected' : 'Not Connected'}
                    </span>
                  </div>
                </div>

                {gmailStatus?.last_validated_at && (
                  <p className="mt-3 text-xs text-gray-500">
                    Last validated: {new Date(gmailStatus.last_validated_at).toLocaleString()}
                  </p>
                )}

                {testResult && (
                  <div
                    className={`mt-3 rounded-lg border p-3 text-sm ${
                      testResult.status === 'valid'
                        ? 'border-green-200 bg-green-50 text-green-700'
                        : 'border-red-200 bg-red-50 text-red-700'
                    }`}
                  >
                    {testResult.message}
                  </div>
                )}

                <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {connected ? (
                    <>
                      <button
                        onClick={handleTest}
                        disabled={testing}
                        className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        {testing ? 'Testing...' : 'Validate'}
                      </button>
                      <button
                        onClick={handleConnect}
                        disabled={connecting}
                        className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                      >
                        {connecting ? 'Connecting...' : 'Reconnect'}
                      </button>
                      <button
                        onClick={handleDisconnect}
                        disabled={disconnecting}
                        className="sm:col-span-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                      >
                        {disconnecting ? 'Disconnecting...' : 'Disconnect'}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={handleConnect}
                      disabled={connecting}
                      className="sm:col-span-2 btn-primary inline-flex items-center justify-center gap-2"
                    >
                      {connecting ? (
                        <>
                          <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                          Waiting for Google login...
                        </>
                      ) : (
                        'Connect with Google'
                      )}
                    </button>
                  )}
                </div>
              </div>

              {connected && (
                <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
                  <div className="mb-4 flex items-start gap-3">
                    <div className="h-10 w-10 rounded-xl bg-teal-100 text-teal-600 flex items-center justify-center">
                      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M7.71 3.5L1.15 15l3.43 5.5h6.56l3.43-5.5L7.71 3.5zm6.58 0L20.85 15l-3.43 5.5H10.5l6.56-12H14.29L7.71 3.5h6.58z" />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900">HR Drive</h3>
                      <p className="text-xs text-gray-500">Shared drive folder monitoring</p>
                    </div>
                  </div>

                  {isEditingDrive ? (
                    <div className="space-y-2 rounded-xl bg-gray-50 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-gray-500">Shared Drive</span>
                        <span className="font-medium text-gray-800 text-right">My Drive</span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <label htmlFor="storageRoot" className="text-gray-500">
                          Destination Folder
                        </label>
                        <input
                          id="storageRoot"
                          type="text"
                          value={storageRootInput}
                          onChange={(e) => setStorageRootInput(e.target.value)}
                          className="w-[60%] rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-right text-sm font-medium text-gray-800 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
                          placeholder="/DocHire-output"
                        />
                      </div>

                      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <button
                          onClick={handleSaveDriveConfig}
                          disabled={savingDrive}
                          className="rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-sm font-medium text-primary-700 hover:bg-primary-100 disabled:opacity-50"
                        >
                          {savingDrive ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsEditingDrive(false)}
                          disabled={savingDrive}
                          className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2 rounded-xl bg-gray-50 p-3 text-sm">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-gray-500">Shared Drive</span>
                        <span className="font-medium text-gray-800 text-right">My Drive</span>
                      </div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-gray-500">Destination Folder</span>
                        <span className="font-medium text-gray-800 text-right break-all">{storageRootInput || 'Not configured'}</span>
                      </div>

                      <button
                        type="button"
                        onClick={() => setIsEditingDrive(true)}
                        className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
                      >
                        <span className="mr-1.5 text-orange-500" aria-hidden="true">✏️</span>
                        Edit Folder Paths
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          <section
            id="document-rules"
            ref={(element) => {
              sectionRefs.current['document-rules'] = element;
            }}
            className="space-y-4 scroll-mt-24"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-xl font-semibold text-gray-900">
                  <span className="text-base">📄</span> Required Documents Checklist
                </h2>
                <p className="mt-0.5 text-sm text-gray-500">
                  Configure which documents are required for candidate verification.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleDownloadTemplate}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                    <path d="M12 4v12M7 11l5 5 5-5" /><path d="M4 20h16" />
                  </svg>
                  Download Template
                </button>
                <button
                  type="button"
                  onClick={() => uploadInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-orange-600"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                    <path d="M12 4v12M7 9l5-5 5 5" /><path d="M4 20h16" />
                  </svg>
                  Upload Checklist
                </button>
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={handleUploadChecklist}
                />
              </div>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 w-10">#</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Document Name</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Category</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Mandatory</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Accepted Formats</th>
                      <th className="px-4 py-3 w-20"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {(() => {
                      const groups = groupByCategory(checklistRows);
                      let globalIdx = 0;
                      return Array.from(groups.entries()).flatMap(([category, rows]) => {
                        const separator = (
                          <tr key={`sep-${category}`} className="bg-gray-50/60">
                            <td colSpan={6} className="px-5 py-1.5 text-[11px] font-semibold tracking-[0.12em] text-gray-400">
                              — {category.toUpperCase()} ({rows.length} {rows.length === 1 ? 'DOCUMENT' : 'DOCUMENTS'}) —
                            </td>
                          </tr>
                        );
                        const dataRows = rows.map((row) => {
                          const displayIdx = ++globalIdx;
                          const isEditing = editingRowId === row.local_id;
                          if (isEditing && editDraft) {
                            return (
                              <tr key={row.local_id} className="bg-primary-50/30">
                                <td className="px-5 py-3 text-gray-400 text-xs">{displayIdx}</td>
                                <td className="px-4 py-2">
                                  <input
                                    value={editDraft.document_name}
                                    onChange={(e) => handleDraftChange('document_name', e.target.value)}
                                    className="w-full rounded-lg border border-primary-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                                    placeholder="Document name"
                                  />
                                </td>
                                <td className="px-4 py-2">
                                  <input
                                    value={editDraft.category}
                                    onChange={(e) => handleDraftChange('category', e.target.value)}
                                    className="w-full rounded-lg border border-primary-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                                    placeholder="Category"
                                  />
                                </td>
                                <td className="px-4 py-2">
                                  <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-gray-700">
                                    <input
                                      type="checkbox"
                                      checked={editDraft.is_mandatory}
                                      onChange={(e) => handleDraftChange('is_mandatory', e.target.checked)}
                                      className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-400"
                                    />
                                    <span>{editDraft.is_mandatory ? 'Yes' : 'No'}</span>
                                  </label>
                                </td>
                                <td className="px-4 py-2">
                                  <div className="flex flex-wrap gap-1.5">
                                    {SUPPORTED_FORMATS.map((fmt) => {
                                      const active = editDraft.accepted_formats.includes(fmt);
                                      return (
                                        <button
                                          key={fmt}
                                          type="button"
                                          onClick={() => toggleDraftFormat(fmt)}
                                          className={`rounded border px-2 py-0.5 text-xs font-mono font-medium transition-colors ${
                                            active
                                              ? 'border-primary-300 bg-primary-100 text-primary-700'
                                              : 'border-gray-200 bg-white text-gray-400 hover:border-gray-300'
                                          }`}
                                        >
                                          .{fmt}
                                        </button>
                                      );
                                    })}
                                  </div>
                                </td>
                                <td className="px-4 py-2">
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={handleSaveRowEdit}
                                      className="rounded-lg bg-primary-600 px-3 py-1 text-xs font-medium text-white hover:bg-primary-700"
                                    >
                                      Save
                                    </button>
                                    <button
                                      type="button"
                                      onClick={handleCancelEdit}
                                      className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          }

                          return (
                            <tr key={row.local_id} className="group hover:bg-gray-50/50 transition-colors">
                              <td className="px-5 py-3 text-xs text-gray-400">{displayIdx}</td>
                              <td className="px-4 py-3 font-medium text-gray-900">{row.document_name}</td>
                              <td className="px-4 py-3">
                                <span className="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                                  {row.category}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <span className={`text-sm font-semibold ${row.is_mandatory ? 'text-green-600' : 'text-gray-400'}`}>
                                  {row.is_mandatory ? 'Yes' : 'No'}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex flex-wrap gap-1.5">
                                  {row.accepted_formats.map((fmt) => (
                                    <span key={fmt} className="rounded border border-gray-200 bg-gray-50 px-2 py-0.5 font-mono text-xs text-gray-600">
                                      .{fmt}
                                    </span>
                                  ))}
                                </div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button
                                    type="button"
                                    aria-label={`Edit ${row.document_name}`}
                                    onClick={() => handleStartEdit(row)}
                                    className="rounded-lg p-1.5 text-gray-400 hover:bg-primary-50 hover:text-primary-600"
                                  >
                                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4Z" />
                                    </svg>
                                  </button>
                                  <button
                                    type="button"
                                    aria-label={`Remove ${row.document_name}`}
                                    onClick={() => handleRemoveChecklistRow(row.local_id)}
                                    className="rounded-lg p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500"
                                  >
                                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                                      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
                                    </svg>
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        });
                        return [separator, ...dataRows];
                      });
                    })()}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between border-t border-gray-100 px-5 py-3">
                <button
                  type="button"
                  onClick={handleAddChecklistRow}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-gray-300 px-3 py-1.5 text-sm text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-colors"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  Add Document
                </button>
                <button
                  type="button"
                  onClick={handleSaveChecklist}
                  disabled={savingChecklist}
                  className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {savingChecklist ? 'Saving...' : 'Save Checklist'}
                </button>
              </div>
            </div>
          </section>

          <section
            id="file-naming"
            ref={(element) => {
              sectionRefs.current['file-naming'] = element;
            }}
            className="space-y-4 scroll-mt-24"
          >
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-gray-900">
                <span className="text-base">📁</span> File Naming Rules
              </h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Configure automatic file naming conventions.
              </p>
            </div>

            <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="folderStructurePattern" className="mb-1 block text-sm font-medium text-gray-700">
                    Folder Structure Pattern
                  </label>
                  <input
                    id="folderStructurePattern"
                    type="text"
                    value={folderStructurePattern}
                    onChange={(event) => setFolderStructurePattern(event.target.value)}
                    className="input-field"
                    placeholder="{CandidateID}_{FirstName}_{Date}"
                  />
                </div>
                <div>
                  <label htmlFor="fileRenamePattern" className="mb-1 block text-sm font-medium text-gray-700">
                    File Rename Pattern
                  </label>
                  <input
                    id="fileRenamePattern"
                    type="text"
                    value={fileRenamePattern}
                    onChange={(event) => setFileRenamePattern(event.target.value)}
                    className="input-field"
                    placeholder="{CandidateID}_{FirstName}_{DocType}"
                  />
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-primary-100 bg-primary-50/60 px-3 py-2 text-sm text-primary-700">
                <span className="font-medium">Example:</span> {fileNamingExample || 'Preview will appear after save'}
              </div>

              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={handleSaveFileNaming}
                  disabled={savingFileNaming}
                  className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {savingFileNaming ? 'Saving...' : 'Save Rules'}
                </button>
              </div>
            </div>
          </section>
        </section>
      </div>
    </div>
  );
}
