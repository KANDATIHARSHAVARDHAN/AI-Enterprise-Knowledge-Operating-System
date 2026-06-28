import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is logged in
    const storedUser = localStorage.getItem('ekos_user');
    const token = localStorage.getItem('ekos_access_token');
    
    if (storedUser && token) {
      setUser(JSON.parse(storedUser));
    }
    setLoading(false);
  }, []);

  const login = (userData, accessToken, refreshToken) => {
    setUser(userData);
    localStorage.setItem('ekos_user', JSON.stringify(userData));
    localStorage.setItem('ekos_access_token', accessToken);
    localStorage.setItem('ekos_refresh_token', refreshToken);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('ekos_user');
    localStorage.removeItem('ekos_access_token');
    localStorage.removeItem('ekos_refresh_token');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
