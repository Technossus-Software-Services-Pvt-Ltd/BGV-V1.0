import { getStoredUser } from '../utils/auth';

export default function ProfilePage() {
  const user = getStoredUser();

  if (!user) {
    return (
      <div className="card">
        <h1 className="text-xl font-semibold text-gray-900">Profile</h1>
        <p className="mt-2 text-gray-600">No user profile is available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Profile</h1>
        <p className="mt-2 text-gray-600">Your Google account details</p>
      </div>

      <div className="card">
        <div className="flex items-center gap-4">
          {user.picture ? (
            <img src={user.picture} alt={user.name || user.email} className="h-16 w-16 rounded-full object-cover" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary-600 text-lg font-semibold text-white">
              {(user.name || user.email).slice(0, 2).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-lg font-semibold text-gray-900">{user.name || 'Google User'}</p>
            <p className="text-sm text-gray-500">{user.email}</p>
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-gray-200 p-4">
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">Email</dt>
            <dd className="mt-1 text-sm text-gray-900 break-all">{user.email}</dd>
          </div>
          <div className="rounded-lg border border-gray-200 p-4">
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">Google ID</dt>
            <dd className="mt-1 text-sm text-gray-900 break-all">{user.google_id || 'Not available'}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
