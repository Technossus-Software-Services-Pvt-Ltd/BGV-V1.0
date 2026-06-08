import { useAuth } from '../hooks/useAuth';

export default function ProfilePage() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="card">
        <h1 className="text-xl font-semibold text-gray-900">Profile</h1>
        <p className="mt-2 text-gray-600">No user profile is available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-gray-500">Your Google account details</p>
      </div>

      <div className="card">
        <div className="flex items-center gap-4">
          {user.picture ? (
            <img src={user.picture} alt={user.name || user.email} className="h-16 w-16 rounded-2xl object-cover shadow-sm" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 text-lg font-bold text-white shadow-sm">
              {(user.name || user.email).slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-lg font-bold text-gray-900">{user.name || 'Google User'}</p>
            <p className="text-sm text-gray-500">{user.email}</p>
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-4">
            <dt className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Email</dt>
            <dd className="mt-1.5 text-sm font-medium text-gray-900 break-all">{user.email}</dd>
          </div>
          <div className="rounded-xl border border-gray-100 bg-gray-50/50 p-4">
            <dt className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Google ID</dt>
            <dd className="mt-1.5 text-sm font-medium text-gray-900 break-all">{user.google_id || 'Not available'}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
