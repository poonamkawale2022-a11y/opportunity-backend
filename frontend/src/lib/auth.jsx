import React, { createContext, useContext, useEffect, useState } from 'react';
import { api, getToken, setToken } from './api.js';

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      if (!getToken()) { setReady(true); return; }
      try { setUser((await api.me()).data); } catch { setToken(''); }
      setReady(true);
    })();
  }, []);

  const uid = () => (user?.email ? `user:${user.email}` : 'demo-user');

  const register = async (b) => { const r = await api.register(b); setToken(r.data.token); setUser(r.data.user); return r; };
  const login = async (b) => { const r = await api.login(b); setToken(r.data.token); setUser(r.data.user); return r; };
  const logout = async () => { try { await api.logout(); } catch {} setToken(''); setUser(null); };

  return <Ctx.Provider value={{ user, ready, uid, register, login, logout }}>{children}</Ctx.Provider>;
}
