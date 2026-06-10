import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getGmailAuthUrl,
  getGmailStatus,
  disconnectGmail,
  getDriveConfig,
  updateDriveConfig,
  validateIntegration,
} from '../api/endpoints';
import { GmailStatus } from '../types';

interface IntegrationsSectionProps {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

export default function IntegrationsSection({ onError, onSuccess }: IntegrationsSectionProps) {
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);
  const [storageRootInput, setStorageRootInput] = useState('');
  const [savingDrive, setSavingDrive] = useState(false);
  const [isEditingDrive, setIsEditingDrive] = useState(false);
  const [loading, setLoading] = useState(true);

  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;

  const loadStatus = useCallback(async () => {
    try {
      const [status, drive] = await Promise.all([getGmailStatus(), getDriveConfig()]);
      setGmailStatus(status);
      setStorageRootInput(drive.storage_root_folder_id || '');
    } catch {
      onErrorRef.current('Failed to load integration settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'gmail-oauth-success') {
        setConnecting(false);
        onSuccessRef.current('Gmail connected successfully!');
        loadStatus();
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [loadStatus]);

  const handleConnect = async () => {
    setConnecting(true);
    setTestResult(null);
    try {
      const { auth_url } = await getGmailAuthUrl();
      const w = 600, h = 700;
      const left = window.screenX + (window.outerWidth - w) / 2;
      const top = window.screenY + (window.outerHeight - h) / 2;
      const popup = window.open(auth_url, 'gmail-oauth', `width=${w},height=${h},left=${left},top=${top}`);
      if (!popup || popup.closed) {
        onErrorRef.current('Popup was blocked by your browser. Please allow popups for this site and try again.');
        setConnecting(false);
        return;
      }
    } catch {
      onErrorRef.current('Failed to start Google login. Check server configuration.');
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setTestResult(null);
    try {
      await disconnectGmail();
      onSuccessRef.current('Gmail disconnected');
      await loadStatus();
    } catch {
      onErrorRef.current('Failed to disconnect');
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
    try {
      await updateDriveConfig({ search_folder_ids: [], storage_root_folder_id: storageRootInput.trim() || null });
      onSuccessRef.current('Drive configuration saved');
      await loadStatus();
      setIsEditingDrive(false);
    } catch {
      onErrorRef.current('Failed to save Drive configuration');
    } finally {
      setSavingDrive(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  const connected = gmailStatus?.connected ?? false;

  return (
    <div className="space-y-4">
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
    </div>
  );
}
