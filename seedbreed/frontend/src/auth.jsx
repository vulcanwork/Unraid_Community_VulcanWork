import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, getToken, setToken } from './api.js';

// Auth state for the whole app. The site is fully browsable while logged out;
// this only governs who may make changes.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [username, setUsername] = useState(null);
  const [loginOpen, setLoginOpen] = useState(false);

  // On load, validate any saved token so the UI reflects the real session.
  useEffect(() => {
    if (!getToken()) return;
    api.get('/api/auth/me')
      .then((d) => setUsername(d.username))
      .catch(() => setToken(null));
  }, []);

  // A write was rejected (logged out or token expired) — clear state and prompt.
  useEffect(() => {
    const onAuthRequired = () => {
      setToken(null);
      setUsername(null);
      setLoginOpen(true);
    };
    window.addEventListener('seedbreed:auth-required', onAuthRequired);
    return () => window.removeEventListener('seedbreed:auth-required', onAuthRequired);
  }, []);

  const login = useCallback(async (u, p) => {
    const d = await api.post('/api/auth/login', { username: u, password: p });
    setToken(d.token);
    setUsername(d.username);
    setLoginOpen(false);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUsername(null);
  }, []);

  const value = {
    username,
    isAuthed: !!username,
    login,
    logout,
    openLogin: () => setLoginOpen(true),
    closeLogin: () => setLoginOpen(false),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      {loginOpen && <LoginModal />}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

function LoginModal() {
  const { login, closeLogin } = useAuth();
  const [u, setU] = useState('');
  const [p, setP] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      await login(u, p);
    } catch (ex) {
      setErr('Invalid username or password.');
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={closeLogin}>
      <div className="modal" style={{ maxWidth: 380 }} onClick={(e) => e.stopPropagation()}>
        <h2>Log in</h2>
        <p className="small muted mb-2">
          Browsing is open to everyone — log in to add or edit.
        </p>
        <form onSubmit={submit}>
          <div className="field">
            <label>Username</label>
            <input autoFocus value={u} onChange={(e) => setU(e.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={p} onChange={(e) => setP(e.target.value)} />
          </div>
          {err && <p className="small" style={{ color: 'var(--copper-dark)' }}>{err}</p>}
          <div className="modal-actions">
            <button type="button" onClick={closeLogin}>Cancel</button>
            <button type="submit" className="primary" disabled={busy || !u || !p}>
              {busy ? 'Logging in…' : 'Log in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
