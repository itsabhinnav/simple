/**
 * Resolve the API base URL at runtime.
 *
 * Strategy:
 *  1. If the global `window.__SAKURA_API_BASE__` is set (injected by the host
 *     page or a deploy-time index.html shim), use it verbatim.
 *  2. If the app is served by the Angular dev server on port 4200, talk to the
 *     Flask backend running on the same hostname at port 5000.
 *  3. Otherwise the Flask backend serves the static frontend on the same
 *     origin, so an empty string yields same-origin relative URLs.
 */
function resolveApiBase(): string {
  if (typeof window !== 'undefined') {
    const injected = (window as any).__SAKURA_API_BASE__;
    if (typeof injected === 'string' && injected.length > 0) {
      return injected.replace(/\/+$/, '');
    }
    const { protocol, hostname, port } = window.location;
    if (port === '4200') {
      return `${protocol}//${hostname}:5000`;
    }
  }
  return '';
}

export const API_BASE = resolveApiBase();
export const API_URL = `${API_BASE}/api`;

export const APP_SETTINGS = {
  auth: {
    enabled: true
  },
  features: {
    specificationImportEnabled: false
  },
  api: {
    base: API_BASE,
    url: API_URL
  }
} as const;

export const AUTH_DISABLED_USER = {
  id: 0,
  username: 'workspace',
  email: 'workspace@sakura.local',
  first_name: 'Workspace',
  last_name: 'User',
  // Admin privileges are temporarily disabled globally — the role here is
  // informational only since AdminGuard / require_admin currently allow
  // every caller through.
  role: 'admin'
} as const;
