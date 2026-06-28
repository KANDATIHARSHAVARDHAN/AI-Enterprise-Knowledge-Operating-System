import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  MessageSquare, 
  FileText, 
  Settings, 
  ShieldAlert, 
  LogOut, 
  Activity 
} from 'lucide-react';

const Sidebar = () => {
  const { user, logout } = useAuth();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
    { path: '/chat', label: 'AI Chat', icon: <MessageSquare size={20} /> },
    { path: '/documents', label: 'Documents', icon: <FileText size={20} /> },
    { path: '/evaluation', label: 'Evaluation', icon: <Activity size={20} /> },
  ];

  if (user?.role === 'admin') {
    navItems.push({ path: '/admin', label: 'Admin Control', icon: <Settings size={20} /> });
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <ShieldAlert size={28} className="brand-icon text-cyan" />
        <span className="brand-text text-gradient">EKOS</span>
      </div>
      
      <div className="user-profile-badge">
        <div className="user-avatar">
          {user?.username?.substring(0, 2).toUpperCase() || 'U'}
        </div>
        <div className="user-info">
          <p className="user-name">{user?.full_name || user?.username}</p>
          <span className={`role-badge ${user?.role}`}>{user?.role}</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink 
            key={item.path} 
            to={item.path}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            end={item.path === '/'}
          >
            {item.icon}
            <span className="link-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="logout-btn" onClick={logout}>
          <LogOut size={18} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
