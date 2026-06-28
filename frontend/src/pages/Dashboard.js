import React, { useState, useEffect } from 'react';
import { adminService, queryService } from '../services/api';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';
import { 
  Cpu, Database, HelpCircle, Users, Clock, AlertTriangle, Hammer, DollarSign 
} from 'lucide-react';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const statsData = await adminService.getStats();
        setStats(statsData);
        
        const historyData = await queryService.getHistory();
        setHistory(historyData.queries || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner-border animate-spin"></div>
        <p>Loading System Intelligence Dashboard...</p>
      </div>
    );
  }

  // Sample static data derived from setup_db.sql / seed_data.sql for visuals
  const machineFailureData = [
    { name: 'CNC Machine X', failures: 3, cost: 36450, downtime: 18.5 },
    { name: 'Hydraulic Press Y', failures: 1, cost: 6500, downtime: 3.0 },
    { name: 'Laser Station Z', failures: 1, cost: 18000, downtime: 5.0 },
    { name: 'Welding Arm A', failures: 1, cost: 9800, downtime: 7.0 },
    { name: 'Conveyor B', failures: 1, cost: 22000, downtime: 10.0 },
  ];

  const severityData = [
    { name: 'Critical', value: 3, color: '#f87171' },
    { name: 'High', value: 3, color: '#fb923c' },
    { name: 'Medium', value: 3, color: '#fbbf24' },
    { name: 'Low', value: 2, color: '#38bdf8' },
  ];

  const kpis = [
    { label: 'Total Users', value: stats?.users || 0, icon: <Users className="text-cyan" />, desc: 'System accounts' },
    { label: 'Ingested Documents', value: stats?.documents || 0, icon: <Database className="text-purple" />, desc: 'Manuals, logs & reports' },
    { label: 'Total AI Queries', value: stats?.queries || 0, icon: <HelpCircle className="text-pink" />, desc: 'Across all channels' },
    { label: 'Vector Count', value: stats?.vector_store?.total_vectors || 0, icon: <Cpu className="text-emerald" />, desc: 'Chunk embeddings in FAISS' },
  ];

  return (
    <div className="page-wrapper animate-fadeIn">
      <div className="page-header">
        <h1 className="text-gradient">System Intelligence</h1>
        <p className="subtitle">EKOS System status and Manufacturing RAG Analytics</p>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpis-grid">
        {kpis.map((kpi, index) => (
          <div key={index} className="kpi-card glass hover-lift">
            <div className="kpi-icon-wrapper">{kpi.icon}</div>
            <div className="kpi-data">
              <h3>{kpi.value}</h3>
              <p className="kpi-label">{kpi.label}</p>
              <span className="kpi-desc">{kpi.desc}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Charts Panels */}
      <div className="charts-grid">
        {/* Machine Failures Bar Chart */}
        <div className="chart-panel glass">
          <div className="chart-header">
            <h3>Machine Downtime & Failure Analysis</h3>
            <p>Seeded manufacturing logs metrics</p>
          </div>
          <div className="chart-body" style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={machineFailureData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                />
                <Bar dataKey="downtime" fill="#22d3ee" radius={[4, 4, 0, 0]} name="Downtime (Hours)" />
                <Bar dataKey="failures" fill="#c084fc" radius={[4, 4, 0, 0]} name="Failure Events Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Severity Distribution Pie Chart */}
        <div className="chart-panel glass">
          <div className="chart-header">
            <h3>Failure Severity Distribution</h3>
            <p>Percentage of manufacturing alerts severity</p>
          </div>
          <div className="chart-body flex justify-center items-center" style={{ height: '300px' }}>
            <div className="w-1/2 h-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {severityData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="pie-legend flex flex-col gap-2">
              {severityData.map((entry, index) => (
                <div key={index} className="legend-item flex items-center gap-2">
                  <span className="dot" style={{ backgroundColor: entry.color }}></span>
                  <span className="label text-slate-300">{entry.name}: {entry.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Latency History */}
      <div className="chart-panel glass mt-6">
        <div className="chart-header">
          <h3>Query Latency History</h3>
          <p>Execution latency for recent RAG system requests</p>
        </div>
        <div className="chart-body" style={{ height: '240px' }}>
          {history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history.slice().reverse()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="created_at" tickFormatter={(t) => new Date(t).toLocaleTimeString()} stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" unit="ms" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                />
                <Area type="monotone" dataKey="latency_ms" stroke="#e11d48" fill="#e11d48" fillOpacity={0.1} name="Latency" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="no-data flex items-center justify-center h-full">
              <Clock size={36} className="text-slate-500 mb-2 animate-pulse" />
              <p className="text-slate-400">No query history records to show yet. Send a query to populate logs.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
