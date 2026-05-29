import { useState, useEffect, useCallback } from 'react';
import {
  getGmailAuthUrl,
  getGmailStatus,
  disconnectGmail,
  getDriveConfig,
  updateDriveConfig,
  validateIntegration,
} from '../api/endpoints';
import { GmailStatus, DriveConfig } from '../types';

export default function SettingsPage() {
  // Gmail OAuth state
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);

  // Drive config state
  const [driveConfig, setDriveConfig] = useState<DriveConfig>({ search_folder_ids: [], storage_root_folder_id: null });
  const [searchFolderInput, setSearchFolderInput] = useState('');
  const [storageRootInput, setStorageRootInput] = useState('');
  const [savingDrive, setSavingDrive] = useState(false);

  // General
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const [status, drive] = await Promise.all([getGmailStatus(), getDriveConfig()]);
      setGmailStatus(status);
      setDriveConfig(drive);
      setSearchFolderInput(drive.search_folder_ids.join(', '));
      setStorageRootInput(drive.storage_root_folder_id || '');
    } catch {
      setError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Listen for OAuth popup success
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
      const ids = searchFolderInput
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      await updateDriveConfig({
        search_folder_ids: ids,
        storage_root_folder_id: storageRootInput.trim() || null,
      });
      setSuccess('Drive configuration saved');
      await loadStatus();
    } catch {
      setError('Failed to save Drive configuration');
    } finally {
      setSavingDrive(false);
    }
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
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start justify-between">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={() => setError(null)} className="text-xs text-red-500 hover:underline ml-4">Dismiss</button>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start justify-between">
          <p className="text-sm text-green-700">{success}</p>
          <button onClick={() => setSuccess(null)} className="text-xs text-green-500 hover:underline ml-4">Dismiss</button>
        </div>
      )}

      {/* ── Gmail Configuration ───────────────────── */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center">
            <svg className="w-5 h-5 text-red-600" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Gmail Configuration</h2>
            <p className="text-sm text-gray-500">Connect your Gmail account to scan for candidate document attachments.</p>
          </div>
        </div>

        {/* Connection Status */}
        <div className={`rounded-lg p-4 mb-4 ${connected ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`}></div>
              <span className={`text-sm font-medium ${connected ? 'text-green-800' : 'text-gray-600'}`}>
                {connected ? 'Connected' : 'Not Connected'}
              </span>
              {gmailStatus?.email && (
                <span className="text-sm text-green-700 ml-1">— {gmailStatus.email}</span>
              )}
            </div>
            {connected && (
              <div className="flex gap-2">
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="px-3 py-1 text-xs font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-white disabled:opacity-50"
                >
                  {testing ? 'Testing...' : 'Test Connection'}
                </button>
                <button
                  onClick={handleConnect}
                  disabled={connecting}
                  className="px-3 py-1 text-xs font-medium text-blue-700 border border-blue-300 rounded-md hover:bg-blue-50 disabled:opacity-50"
                >
                  {connecting ? 'Connecting...' : 'Reconnect'}
                </button>
                <button
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                  className="px-3 py-1 text-xs font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-50 disabled:opacity-50"
                >
                  {disconnecting ? 'Disconnecting...' : 'Disconnect'}
                </button>
              </div>
            )}
          </div>

          {connected && gmailStatus?.scopes && gmailStatus.scopes.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {gmailStatus.scopes.map((scope) => {
                const label = scope.includes('gmail.modify')
                  ? 'gmail.modify'
                  : scope.includes('drive')
                    ? 'drive'
                    : scope.split('/').pop() || scope;
                return (
                  <span key={scope} className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                    {label}
                  </span>
                );
              })}
            </div>
          )}

          {gmailStatus?.last_validated_at && (
            <p className="text-xs text-gray-500 mt-2">
              Last validated: {new Date(gmailStatus.last_validated_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`rounded-lg p-3 mb-4 text-sm ${
            testResult.status === 'valid' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            {testResult.message}
          </div>
        )}

        {/* Connect Button (shown when not connected) */}
        {!connected && (
          <div className="mt-2">
            <p className="text-sm text-gray-600 mb-3">
              Sign in with your Google account to grant <code className="bg-gray-100 px-1 rounded text-xs">gmail.modify</code> and <code className="bg-gray-100 px-1 rounded text-xs">drive</code> permissions.
            </p>
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="btn-primary inline-flex items-center gap-2"
            >
              {connecting ? (
                <>
                  <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                  Waiting for Google login...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12.545 10.239v3.821h5.445c-.712 2.315-2.647 3.972-5.445 3.972a6.033 6.033 0 110-12.064c1.498 0 2.866.549 3.921 1.453l2.814-2.814A9.969 9.969 0 0012.545 2C7.021 2 2.543 6.477 2.543 12s4.478 10 10.002 10c8.396 0 10.249-7.85 9.426-11.748l-9.426-.013z"/>
                  </svg>
                  Connect with Google
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* ── Google Drive Configuration ────────────── */}
      {connected && (
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
                <path d="M7.71 3.5L1.15 15l3.43 5.5h6.56l3.43-5.5L7.71 3.5zm6.58 0L20.85 15l-3.43 5.5H10.5l6.56-12H14.29L7.71 3.5h6.58z"/>
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Google Drive Folders</h2>
              <p className="text-sm text-gray-500">Configure which Drive folders to search and where to store processed documents.</p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label htmlFor="searchFolders" className="block text-sm font-medium text-gray-700 mb-1">
                Search Folder IDs
              </label>
              <input
                id="searchFolders"
                type="text"
                value={searchFolderInput}
                onChange={(e) => setSearchFolderInput(e.target.value)}
                className="input-field"
                placeholder="folder-id-1, folder-id-2"
              />
              <p className="text-xs text-gray-400 mt-1">Comma-separated Google Drive folder IDs to search for candidate documents.</p>
            </div>
            <div>
              <label htmlFor="storageRoot" className="block text-sm font-medium text-gray-700 mb-1">
                Storage Root Folder ID
              </label>
              <input
                id="storageRoot"
                type="text"
                value={storageRootInput}
                onChange={(e) => setStorageRootInput(e.target.value)}
                className="input-field"
                placeholder="folder-id"
              />
              <p className="text-xs text-gray-400 mt-1">Drive folder where processed documents will be uploaded and organized.</p>
            </div>
            <button
              onClick={handleSaveDriveConfig}
              disabled={savingDrive}
              className="btn-primary text-sm"
            >
              {savingDrive ? 'Saving...' : 'Save Drive Config'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
