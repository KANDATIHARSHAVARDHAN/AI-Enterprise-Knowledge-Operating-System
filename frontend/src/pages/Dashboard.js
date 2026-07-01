import React, { useState, useEffect } from 'react';
import { adminService, queryService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, Legend
} from 'recharts';
import { 
  Cpu, Database, HelpCircle, Users, Clock, FileText, MessageSquare,
  UploadCloud, FolderOpen
} from 'lucide-react';

const Dashboard = () => {
  const { user } = useAuth();
  const [userStats, setUserStats] = useState(null);
  const [adminStats, setAdminStats] = useState(null);
  const [docAnalytics, setDocAnalytics] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        // Per-user stats (available to all users)
        const userStatsData = await queryService.getDashboardStats();
        setUserStats(userStatsData);

        // Document analytics for charts (driven by real uploads)
        const analytics = await queryService.getDocumentAnalytics();
        setDocAnalytics(analytics);
        
        // Admin-only global stats
        if (isAdmin) {
          const globalStats = await adminService.getStats();
          setAdminStats(globalStats);
        }
        
        // Query history for latency chart
        const historyData = await queryService.getHistory();
        setHistory(historyData.queries || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, [isAdmin]);

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner-border animate-spin"></div>
        <p>Loading System Intelligence Dashboard...</p>
      </div>
    );
  }

  // Build KPI cards based on role
  const kpis = isAdmin
    ? [
        { label: 'Total Users', value: adminStats?.users || 0, icon: <Users className="text-cyan" />, desc: 'System accounts' },
        { label: 'All Documents', value: adminStats?.documents || 0, icon: <Database className="text-purple" />, desc: 'Across all users' },
        { label: 'Total AI Queries', value: adminStats?.queries || 0, icon: <HelpCircle className="text-pink" />, desc: 'System-wide' },
        { label: 'Vector Count', value: adminStats?.vector_store?.total_vectors || 0, icon: <Cpu className="text-emerald" />, desc: 'FAISS embeddings' },
      ]
    : [
        { label: 'My Documents', value: userStats?.documents || 0, icon: <FileText className="text-cyan" />, desc: 'Your uploaded files' },
        { label: 'My Queries', value: userStats?.queries || 0, icon: <HelpCircle className="text-purple" />, desc: 'Your AI questions' },
        { label: 'Conversations', value: userStats?.conversations || 0, icon: <MessageSquare className="text-pink" />, desc: 'Your chat threads' },
        { label: 'My Vectors', value: userStats?.vector_count || 0, icon: <Cpu className="text-emerald" />, desc: 'Your chunk embeddings' },
      ];

  // Document analytics data
  const fileTypeData = docAnalytics?.file_type_data || [];
  const statusData = docAnalytics?.status_data || [];
  const uploadTimeline = docAnalytics?.upload_timeline || [];
  const topDocsData = docAnalytics?.top_docs_data || [];

  // Color palette for file type bars
  const FILE_TYPE_COLORS = [
    '#22d3ee', '#a855f7', '#ec4899', '#38bdf8', '#f59e0b',
    '#10b981', '#6366f1', '#f87171', '#84cc16', '#14b8a6',
  ];

  // Check if there is any document data at all
  const hasDocumentData = fileTypeData.length > 0 || statusData.length > 0;

  // Empty state component
  const EmptyChartState = ({ icon: Icon, title, description }) => (
    <div className="no-data" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '100%', gap: '8px',
    }}>
      <Icon size={40} style={{ color: '#475569', marginBottom: '4px' }} />
      <p style={{ color: '#94a3b8', fontSize: '14px', fontWeight: 500 }}>{title}</p>
      <p style={{ color: '#64748b', fontSize: '12px', maxWidth: '280px', textAlign: 'center' }}>
        {description}
      </p>
    </div>
  );

  return (
    <div className="page-wrapper animate-fadeIn">
      <div className="page-header">
        <h1 className="text-gradient">System Intelligence</h1>
        <p className="subtitle">
          {isAdmin 
            ? 'EKOS System Status & Document Analytics' 
            : `Welcome, ${userStats?.username || 'User'} — Your EKOS Dashboard`}
        </p>
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
        {/* Documents by File Type — Bar Chart */}
        <div className="chart-panel glass">
          <div className="chart-header">
            <h3>Documents by File Type</h3>
            <p>Distribution of uploaded file formats</p>
          </div>
          <div className="chart-body" style={{ height: '300px' }}>
            {fileTypeData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={fileTypeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" allowDecimals={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                    labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                  />
                  <Bar dataKey="count" name="Document Count" radius={[4, 4, 0, 0]}>
                    {fileTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={FILE_TYPE_COLORS[index % FILE_TYPE_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChartState 
                icon={UploadCloud}
                title="No documents uploaded yet"
                description="Upload documents in the Documents page to see file type analytics here."
              />
            )}
          </div>
        </div>

        {/* Document Status Distribution — Pie Chart */}
        <div className="chart-panel glass">
          <div className="chart-header">
            <h3>Document Status Distribution</h3>
            <p>Ingestion pipeline status breakdown</p>
          </div>
          <div className="chart-body flex justify-center items-center" style={{ height: '300px' }}>
            {statusData.length > 0 ? (
              <>
                <div className="w-1/2 h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {statusData.map((entry, index) => (
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
                  {statusData.map((entry, index) => (
                    <div key={index} className="legend-item flex items-center gap-2">
                      <span className="dot" style={{ backgroundColor: entry.color }}></span>
                      <span className="label text-slate-300">{entry.name}: {entry.value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <EmptyChartState 
                icon={FolderOpen}
                title="No status data available"
                description="Upload and ingest documents to see their processing status here."
              />
            )}
          </div>
        </div>
      </div>

      {/* Top Documents by Chunk Count — Bar Chart */}
      <div className="chart-panel glass mt-6">
        <div className="chart-header">
          <h3>Top Documents by Chunk Count</h3>
          <p>Successfully ingested documents ranked by number of chunks produced</p>
        </div>
        <div className="chart-body" style={{ height: '280px' }}>
          {topDocsData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topDocsData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" stroke="#94a3b8" allowDecimals={false} />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  stroke="#94a3b8" 
                  width={140}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                  formatter={(value, name) => {
                    if (name === 'Chunks') return [value, 'Chunks'];
                    if (name === 'Size (KB)') return [value, 'Size (KB)'];
                    return [value, name];
                  }}
                />
                <Legend />
                <Bar dataKey="chunks" fill="#22d3ee" radius={[0, 4, 4, 0]} name="Chunks" />
                <Bar dataKey="size_kb" fill="#a855f7" radius={[0, 4, 4, 0]} name="Size (KB)" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChartState 
              icon={FileText}
              title="No ingested documents yet"
              description="Complete document ingestion to see chunk distribution across your files."
            />
          )}
        </div>
      </div>

      {/* Upload Timeline — Area Chart */}
      <div className="chart-panel glass mt-6">
        <div className="chart-header">
          <h3>Upload Timeline</h3>
          <p>Document uploads and chunk generation over time</p>
        </div>
        <div className="chart-body" style={{ height: '240px' }}>
          {uploadTimeline.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={uploadTimeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" allowDecimals={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff', fontWeight: 'bold' }}
                />
                <Legend />
                <Area 
                  type="monotone" 
                  dataKey="documents" 
                  stroke="#22d3ee" 
                  fill="#22d3ee" 
                  fillOpacity={0.15} 
                  name="Documents Uploaded" 
                />
                <Area 
                  type="monotone" 
                  dataKey="chunks" 
                  stroke="#a855f7" 
                  fill="#a855f7" 
                  fillOpacity={0.1} 
                  name="Chunks Generated" 
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChartState 
              icon={UploadCloud}
              title="No upload history yet"
              description="Your document upload timeline will appear here after you start uploading files."
            />
          )}
        </div>
      </div>

      {/* Query Latency History */}
      <div className="chart-panel glass mt-6">
        <div className="chart-header">
          <h3>Query Latency History</h3>
          <p>Execution latency for your recent RAG system requests</p>
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
            <EmptyChartState 
              icon={Clock}
              title="No query history yet"
              description="Send a query in the Chat page to see latency metrics here."
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
