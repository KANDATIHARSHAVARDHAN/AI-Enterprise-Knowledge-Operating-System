import React, { useState, useEffect } from 'react';
import { adminService } from '../services/api';
import { Settings, ShieldCheck, Activity, Users, RefreshCw, Trash2, Edit, Database } from 'lucide-react';

const Admin = () => {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);

  useEffect(() => {
    fetchAdminData();
  }, []);

  const fetchAdminData = async () => {
    setReloading(true);
    try {
      const statsData = await adminService.getStats();
      setStats(statsData);

      const usersList = await adminService.listUsers();
      setUsers(usersList.users || []);

      const logsList = await adminService.getAuditLogs();
      setAuditLogs(logsList.logs || []);
    } catch (err) {
      console.error('Failed to load admin stats/users:', err);
    } finally {
      setLoading(false);
      setReloading(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await adminService.updateUserRole(userId, newRole);
      await fetchAdminData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update user role');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Are you sure you want to permanently delete this user?')) return;
    try {
      await adminService.deleteUser(userId);
      await fetchAdminData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner-border animate-spin"></div>
        <p>Loading Admin Dashboard Control Panel...</p>
      </div>
    );
  }

  return (
    <div className="page-wrapper animate-fadeIn">
      <div className="page-header flex justify-between items-center">
        <div>
          <h1 className="text-gradient">Admin Settings</h1>
          <p className="subtitle">Global system administration, roles control, and security logs auditing</p>
        </div>
        <button 
          className="btn-primary flex items-center gap-2" 
          onClick={fetchAdminData}
          disabled={reloading}
        >
          <RefreshCw size={16} className={reloading ? 'animate-spin' : ''} />
          <span>Sync Vaults</span>
        </button>
      </div>

      {/* System Statistics Panel */}
      <div className="kpis-grid">
        <div className="kpi-card glass flex items-center gap-4">
          <Database className="text-cyan" size={32} />
          <div>
            <h3>{stats?.vector_store?.total_vectors || 0}</h3>
            <p className="kpi-label">Vector Store Index</p>
            <span className="text-[10px] text-slate-500 uppercase">{stats?.vector_store?.dimension} Dimensions (FAISS)</span>
          </div>
        </div>
        
        <div className="kpi-card glass flex items-center gap-4">
          <Activity className="text-emerald" size={32} />
          <div>
            <h3>{stats?.knowledge_graph?.total_nodes || 0} Nodes</h3>
            <p className="kpi-label">Knowledge Graph</p>
            <span className="text-[10px] text-slate-500 uppercase">{stats?.knowledge_graph?.total_edges || 0} Relations (NetworkX)</span>
          </div>
        </div>

        <div className="kpi-card glass flex items-center gap-4">
          <Settings className="text-pink" size={32} />
          <div>
            <h3 className="text-slate-300">Healthy</h3>
            <p className="kpi-label">PII Guard & Masking</p>
            <span className="text-[10px] text-emerald-400 uppercase">Active</span>
          </div>
        </div>
      </div>

      {/* User Management Section */}
      <div className="vault-card glass p-6 rounded-xl mt-6">
        <div className="vault-header border-b border-slate-700/50 pb-3 mb-4">
          <h3>User Management</h3>
        </div>
        
        <div className="table-responsive">
          <table className="vault-table w-full text-left">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase">
                <th className="py-2">User Details</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created At</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-slate-800/50 hover:bg-slate-800/10 text-sm">
                  <td className="py-3">
                    <p className="font-bold text-slate-200">{u.full_name || u.username}</p>
                    <span className="text-xs text-slate-500">{u.email}</span>
                  </td>
                  <td>
                    <select 
                      className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded p-1"
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                    >
                      <option value="viewer">viewer</option>
                      <option value="analyst">analyst</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td>
                    <span className={`status-badge-pill ${u.is_active ? 'completed' : 'failed'}`}>
                      {u.is_active ? 'active' : 'suspended'}
                    </span>
                  </td>
                  <td className="text-slate-400 text-xs">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="text-right">
                    <button 
                      className="delete-doc-btn text-red-400 hover:text-red-300 p-1"
                      onClick={() => handleDeleteUser(u.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Security Audit Log */}
      <div className="vault-card glass p-6 rounded-xl mt-6">
        <div className="vault-header border-b border-slate-700/50 pb-3 mb-4">
          <h3>Security Audit Trail</h3>
        </div>

        {auditLogs.length === 0 ? (
          <div className="empty-vault-state flex flex-col items-center justify-center p-8 text-slate-500">
            <ShieldCheck size={32} />
            <p>No audit trail logs recorded yet.</p>
          </div>
        ) : (
          <div className="table-responsive" style={{ maxHeight: '300px' }}>
            <table className="vault-table w-full text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-xs uppercase">
                  <th className="py-2">User ID</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Details</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((log) => (
                  <tr key={log.id} className="border-b border-slate-800/50 hover:bg-slate-800/10 text-xs">
                    <td className="py-2 text-slate-300 font-bold">UID: {log.user_id || 'SYSTEM'}</td>
                    <td>
                      <span className={`status-badge-pill ${log.action.toLowerCase()}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="text-slate-400 font-mono">{log.resource_type || 'N/A'}</td>
                    <td className="text-slate-300 font-mono truncate max-w-xs">{JSON.stringify(log.details || {})}</td>
                    <td className="text-slate-500">{new Date(log.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;
