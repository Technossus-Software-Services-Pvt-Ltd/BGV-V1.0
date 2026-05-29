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
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Document Processing Status</h2>
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Ownership Verification</h2>
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Documents (Last 7 Days)</h2>
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Batches (Last 7 Days)</h2>
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Document Type Distribution</h2>
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

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-green-50 text-green-700 border-green-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
  };
  return (
    <div className={`rounded-xl border p-4 ${colorMap[color] || colorMap.blue}`}>
      <p className="text-3xl font-bold">{value}</p>
      <p className="text-sm mt-1 opacity-80">{label}</p>
    </div>
  );
}
