import { useState, useEffect, useCallback } from 'react';
import { getFileNamingRule, saveFileNamingRule } from '../api/endpoints';

interface FileNamingSectionProps {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export default function FileNamingSection({ onError, onSuccess }: FileNamingSectionProps) {
  const [folderStructurePattern, setFolderStructurePattern] = useState('');
  const [fileRenamePattern, setFileRenamePattern] = useState('');
  const [fileNamingExample, setFileNamingExample] = useState('');
  const [savingFileNaming, setSavingFileNaming] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadNamingRule = useCallback(async () => {
    try {
      const namingRule = await getFileNamingRule();
      setFolderStructurePattern(namingRule.folder_structure_pattern);
      setFileRenamePattern(namingRule.file_rename_pattern);
      setFileNamingExample(namingRule.example_output);
    } catch {
      onError('Failed to load file naming rules');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => { loadNamingRule(); }, [loadNamingRule]);

  const handleSaveFileNaming = async () => {
    const normalizedFolderPattern = folderStructurePattern.trim();
    const normalizedFilePattern = fileRenamePattern.trim();

    if (!normalizedFolderPattern || !normalizedFilePattern) {
      onError('Folder and file naming patterns are required');
      return;
    }

    setSavingFileNaming(true);
    try {
      const saved = await saveFileNamingRule({
        folder_structure_pattern: normalizedFolderPattern,
        file_rename_pattern: normalizedFilePattern,
      });
      setFolderStructurePattern(saved.folder_structure_pattern);
      setFileRenamePattern(saved.file_rename_pattern);
      setFileNamingExample(saved.example_output);
      onSuccess('File naming rules saved');
    } catch {
      onError('Failed to save file naming rules');
    } finally {
      setSavingFileNaming(false);
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
    </div>
  );
}
