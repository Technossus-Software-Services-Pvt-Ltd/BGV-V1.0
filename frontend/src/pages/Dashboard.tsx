import { useEffect, useState } from 'react';
import { getDashboardStats, DashboardStats } from '../api/endpoints';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line,
} from 'recharts';

const COLORS = ['#10b981', '#ef4444', '#f59e0b', '#6366f1', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6'];
const DOC_STATUS_COLORS = ['#10b981', '#ef4444', '#a3a3a3', '#3b82f6'];
const OWNERSHIP_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <LoadingSpinner message="Loading dashboard..." />;
  if (error) return <ErrorMessage message={error} onRetry={loadData} />;
  if (!stats) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-0.5 text-sm text-gray-500">Overview of verification activities</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Documents" value={stats.summary.total_documents} color="blue" />
        <StatCard label="Completed" value={stats.summary.completed_documents} color="green" />
        <StatCard label="Total Batches" value={stats.summary.total_batches} color="indigo" />
        <StatCard label="Total Candidates" value={stats.summary.total_candidates} color="purple" />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Processing Status - Pie */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="inline-block w-1 h-4 rounded-full bg-blue-500"></span>
            Document Processing Status
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={stats.document_status.filter(d => d.count > 0)}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={90}
                paddingAngle={3}
                dataKey="count"
                nameKey="status"
                label={((props: Record<string, unknown>) => `${props.name}: ${props.value}`) as never}
              >
                {stats.document_status.map((_, i) => (
                  <Cell key={i} fill={DOC_STATUS_COLORS[i % DOC_STATUS_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Ownership Verification - Pie */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="inline-block w-1 h-4 rounded-full bg-green-500"></span>
            Ownership Verification
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={stats.ownership_verification.filter(d => d.count > 0)}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={90}
                paddingAngle={3}
                dataKey="count"
                nameKey="status"
                label={((props: Record<string, unknown>) => `${props.name}: ${props.value}`) as never}
              >
                {stats.ownership_verification.map((_, i) => (
                  <Cell key={i} fill={OWNERSHIP_COLORS[i % OWNERSHIP_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Documents - Line Chart */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="inline-block w-1 h-4 rounded-full bg-blue-500"></span>
            Documents (Last 7 Days)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stats.daily_documents}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Daily Batches - Line Chart */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="inline-block w-1 h-4 rounded-full bg-indigo-500"></span>
            Batches (Last 7 Days)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stats.daily_batches}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Document Type Distribution - Bar Chart */}
      {stats.document_types.length > 0 && (
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <span className="inline-block w-1 h-4 rounded-full bg-indigo-500"></span>
            Document Type Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.document_types} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} />
              <YAxis dataKey="type" type="category" tick={{ fontSize: 12 }} width={100} />
              <Tooltip />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]}>
                {stats.document_types.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

const STAT_ICON_CONFIG: Record<string, { iconBg: string; iconColor: string; icon: JSX.Element }> = {
  blue: {
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden="true">
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
        <path d="M14 3v5h5" />
        <path d="M10 13h4" /><path d="M10 17h4" />
      </svg>
    ),
  },
  green: {
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    ),
  },
  indigo: {
    iconBg: 'bg-indigo-100',
    iconColor: 'text-indigo-600',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden="true">
        <rect x="3" y="4" width="8" height="7" rx="1.5" />
        <rect x="13" y="4" width="8" height="7" rx="1.5" />
        <rect x="3" y="13" width="8" height="7" rx="1.5" />
        <rect x="13" y="13" width="8" height="7" rx="1.5" />
      </svg>
    ),
  },
  purple: {
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-6" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c1.8-3 4-4.5 7-4.5s5.2 1.5 7 4.5" />
      </svg>
    ),
  },
};

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const cfg = STAT_ICON_CONFIG[color] ?? STAT_ICON_CONFIG.blue;
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center justify-between gap-4">
      <div className="min-w-0">
        <p className="text-xs font-semibold tracking-widest text-gray-400 uppercase truncate">{label}</p>
        <p className="mt-1.5 text-3xl font-bold text-gray-900 tabular-nums">{value.toLocaleString()}</p>
      </div>
      <div className={`shrink-0 h-12 w-12 rounded-xl ${cfg.iconBg} ${cfg.iconColor} flex items-center justify-center`}>
        {cfg.icon}
      </div>
    </div>
  );
}
