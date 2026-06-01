import { useEffect, useState } from 'react';
import { listCandidates, createCandidate } from '../api/endpoints';
import { Candidate } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [formId, setFormId] = useState('');
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formDob, setFormDob] = useState('');
  const [formPan, setFormPan] = useState('');
  const [formAadhaar, setFormAadhaar] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const loadCandidates = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCandidates({ limit: 100 });
      setCandidates(data.candidates);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load candidates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const handleCreateCandidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      await createCandidate({
        candidate_id: formId,
        name: formName,
        email: formEmail || undefined,
        phone: formPhone || undefined,
        date_of_birth: formDob || undefined,
        pan_number: formPan || undefined,
        aadhaar_last_four: formAadhaar || undefined,
      });
      setShowForm(false);
      setFormId('');
      setFormName('');
      setFormEmail('');
      setFormPhone('');
      setFormDob('');
      setFormPan('');
      setFormAadhaar('');
      await loadCandidates();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create candidate');
    }
  };

  if (loading) return <LoadingSpinner message="Loading candidates..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadCandidates} />;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Candidates</h1>
          <p className="text-sm text-gray-500 mt-1">{total} total candidates</p>
        </div>
      </div>

      {/* Create Form - hidden */}
      {false && showForm && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Add New Candidate</h2>
          {formError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-sm text-red-700">{formError}</p>
            </div>
          )}
          <form onSubmit={handleCreateCandidate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Candidate ID *</label>
              <input
                type="text"
                value={formId}
                onChange={(e) => setFormId(e.target.value)}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input
                type="tel"
                value={formPhone}
                onChange={(e) => setFormPhone(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
              <input
                type="date"
                value={formDob}
                onChange={(e) => setFormDob(e.target.value)}
                className="input-field"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">PAN Number</label>
              <input
                type="text"
                value={formPan}
                onChange={(e) => setFormPan(e.target.value.toUpperCase())}
                className="input-field"
                maxLength={10}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Aadhaar Last 4</label>
              <input
                type="text"
                value={formAadhaar}
                onChange={(e) => setFormAadhaar(e.target.value.replace(/\D/g, '').slice(0, 4))}
                className="input-field"
                maxLength={4}
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button type="submit" className="btn-primary">
                Create Candidate
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Candidates Table */}
      {candidates.length === 0 ? (
        <div className="card text-center py-16">
          <div className="mx-auto h-12 w-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
            <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="8" r="3.5" /><path d="M5 20c1.8-3 4-4.5 7-4.5s5.2 1.5 7 4.5" />
            </svg>
          </div>
          <p className="text-gray-500 font-medium">No candidates yet</p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/80">
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Candidate ID</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Email</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Phone</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">DOB</th>
                <th className="text-left py-3.5 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {candidates.map((candidate) => (
                <tr key={candidate.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="py-3.5 px-4 font-mono text-xs text-gray-600">{candidate.candidate_id}</td>
                  <td className="py-3.5 px-4 font-medium text-gray-900">{candidate.name}</td>
                  <td className="py-3.5 px-4 text-gray-500">{candidate.email || '-'}</td>
                  <td className="py-3.5 px-4 text-gray-500">{candidate.phone || '-'}</td>
                  <td className="py-3.5 px-4 text-gray-500">{candidate.date_of_birth || '-'}</td>
                  <td className="py-3.5 px-4 text-gray-400 text-xs">
                    {new Date(candidate.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
