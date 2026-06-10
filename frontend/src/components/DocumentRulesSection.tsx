import { useState, useEffect, useCallback, useRef } from 'react';
import { listRequiredDocuments, saveRequiredDocuments } from '../api/endpoints';
import { RequiredDocumentRuleInput } from '../types';

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

interface DocumentRulesSectionProps {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export default function DocumentRulesSection({ onError, onSuccess }: DocumentRulesSectionProps) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [checklistRows, setChecklistRows] = useState<ChecklistRow[]>([]);
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ChecklistRow | null>(null);
  const [savingChecklist, setSavingChecklist] = useState(false);
  const [loading, setLoading] = useState(true);

  // Refs to avoid re-triggering loadChecklist when parent re-renders
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;

  const loadChecklist = useCallback(async () => {
    try {
      const requiredDocs = await listRequiredDocuments();
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
      onErrorRef.current('Failed to load document rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadChecklist(); }, [loadChecklist]);

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
        onErrorRef.current('Add at least one valid checklist row before saving');
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
      onSuccessRef.current('Required documents checklist saved');
    } catch {
      onErrorRef.current('Failed to save required documents checklist');
    } finally {
      setSavingChecklist(false);
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

    if (lines.length <= 1) return [];

    const parsed: ChecklistRow[] = [];
    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(',');
      if (cols.length < 4) continue;

      const documentName = cols[0].trim();
      const category = cols[1].trim() || 'Identity';
      const mandatoryToken = cols[2].trim().toLowerCase();
      const acceptedFormats = cols
        .slice(3)
        .join(',')
        .split('|')
        .map((fmt) => fmt.trim().toLowerCase())
        .filter(Boolean);

      if (!documentName) continue;

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
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = parseChecklistCsv(text);
      if (parsed.length === 0) {
        onErrorRef.current('Uploaded file is empty or has invalid checklist rows');
      } else {
        setChecklistRows(parsed);
        onSuccessRef.current(`Loaded ${parsed.length} checklist rows from file`);
      }
    } catch {
      onErrorRef.current('Failed to read uploaded checklist file');
    } finally {
      event.target.value = '';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
    </div>
  );
}
