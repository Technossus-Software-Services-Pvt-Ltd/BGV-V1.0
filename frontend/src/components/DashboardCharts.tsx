import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line,
} from 'recharts';
import { DashboardStats } from '../types';

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6'];
const DOC_STATUS_COLORS = ['#10b981', '#ef4444', '#94a3b8', '#6366f1'];
const OWNERSHIP_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

interface DashboardChartsProps {
  stats: DashboardStats;
}

export default function DashboardCharts({ stats }: DashboardChartsProps) {
  return (
    <>
      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Processing Status - Pie */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-900 mb-5 flex items-center gap-2.5">
            <span className="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-primary-400 to-primary-600"></span>
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
                label={({ name, value }: { name?: string; value?: number }) => `${name ?? ''}: ${value ?? ''}`}
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
          <h2 className="text-sm font-semibold text-gray-900 mb-5 flex items-center gap-2.5">
            <span className="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-emerald-400 to-emerald-600"></span>
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
                label={({ name, value }: { name?: string; value?: number }) => `${name ?? ''}: ${value ?? ''}`}
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
          <h2 className="text-sm font-semibold text-gray-900 mb-5 flex items-center gap-2.5">
            <span className="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-primary-400 to-primary-600"></span>
            Documents (Last 7 Days)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stats.daily_documents}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis allowDecimals={false} stroke="#94a3b8" />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 4, fill: '#6366f1' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Daily Batches - Line Chart */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-900 mb-5 flex items-center gap-2.5">
            <span className="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-violet-400 to-violet-600"></span>
            Batches (Last 7 Days)
          </h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={stats.daily_batches}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis allowDecimals={false} stroke="#94a3b8" />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2.5} dot={{ r: 4, fill: '#8b5cf6' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Document Type Distribution - Bar Chart */}
      {stats.document_types.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-900 mb-5 flex items-center gap-2.5">
            <span className="inline-block w-1 h-5 rounded-full bg-gradient-to-b from-violet-400 to-violet-600"></span>
            Document Type Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.document_types} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" allowDecimals={false} stroke="#94a3b8" />
              <YAxis dataKey="type" type="category" tick={{ fontSize: 11 }} width={100} stroke="#94a3b8" />
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
    </>
  );
}
