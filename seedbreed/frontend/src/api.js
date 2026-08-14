// Thin fetch wrapper. Same-origin in production (nginx proxies /api to backend),
// dev uses vite proxy.
const BASE = '';
const TOKEN_KEY = 'seedbreed_token';

// --- auth token storage (a login token, kept in localStorage) ---
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function req(method, path, body, isForm = false) {
  const opts = { method, headers: {} };
  const token = getToken();
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body !== undefined) {
    if (isForm) {
      opts.body = body;
    } else {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
  }
  const r = await fetch(BASE + path, opts);
  if (!r.ok) {
    // A blocked write means we're logged out (or the token expired). Nudge the
    // app to open the login prompt, and surface a friendly message to callers.
    if (r.status === 401) {
      const isWrite = method !== 'GET' && method !== 'HEAD';
      if (isWrite && !path.startsWith('/api/auth/')) {
        window.dispatchEvent(new CustomEvent('seedbreed:auth-required'));
      }
      const err = new Error('Log in to make changes.');
      err.status = 401;
      throw err;
    }
    const text = await r.text();
    const err = new Error(`${r.status} ${r.statusText}: ${text}`);
    err.status = r.status;
    throw err;
  }
  if (r.status === 204) return null;
  return r.json();
}

export const api = {
  get:    (p)        => req('GET', p),
  post:   (p, b)     => req('POST', p, b),
  patch:  (p, b)     => req('PATCH', p, b),
  del:    (p)        => req('DELETE', p),
  upload: (p, form)  => req('POST', p, form, true),
};
