import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add Authorization header interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('ekos_access_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('ekos_refresh_token');
        if (refreshToken) {
          const res = await axios.post(`${API_URL}/auth/refresh`, { refresh_token: refreshToken });
          if (res.status === 200) {
            localStorage.setItem('ekos_access_token', res.data.access_token);
            api.defaults.headers.common['Authorization'] = `Bearer ${res.data.access_token}`;
            return api(originalRequest);
          }
        }
      } catch (refreshError) {
        // Log out user
        localStorage.removeItem('ekos_user');
        localStorage.removeItem('ekos_access_token');
        localStorage.removeItem('ekos_refresh_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login: async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  },
  register: async (email, username, password, fullName) => {
    const res = await api.post('/auth/register', { email, username, password, full_name: fullName });
    return res.data;
  },
  getProfile: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  },
};

export const queryService = {
  ask: async (query, conversationId = null) => {
    const res = await api.post('/query', { query, conversation_id: conversationId });
    return res.data;
  },
  getHistory: async () => {
    const res = await api.get('/query/history');
    return res.data;
  },
  getTrace: async (queryId) => {
    const res = await api.get(`/query/${queryId}/trace`);
    return res.data;
  },
  getConversations: async () => {
    const res = await api.get('/query/conversations');
    return res.data;
  },
  getMessages: async (conversationId) => {
    const res = await api.get(`/query/conversations/${conversationId}/messages`);
    return res.data;
  },
};

export const documentService = {
  upload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
  list: async () => {
    const res = await api.get('/documents');
    return res.data;
  },
  delete: async (documentId) => {
    const res = await api.delete(`/documents/${documentId}`);
    return res.data;
  },
};

export const evaluationService = {
  getMetrics: async () => {
    const res = await api.get('/evaluation/metrics');
    return res.data;
  },
  getRecent: async () => {
    const res = await api.get('/evaluation/recent');
    return res.data;
  },
};

export const adminService = {
  getStats: async () => {
    const res = await api.get('/admin/system/stats');
    return res.data;
  },
  getAuditLogs: async () => {
    const res = await api.get('/admin/audit-logs');
    return res.data;
  },
  listUsers: async () => {
    const res = await api.get('/admin/users');
    return res.data;
  },
  updateUserRole: async (userId, role) => {
    const res = await api.put(`/admin/users/${userId}/role`, { role });
    return res.data;
  },
  deleteUser: async (userId) => {
    const res = await api.delete(`/admin/users/${userId}`);
    return res.data;
  },
};

export default api;
