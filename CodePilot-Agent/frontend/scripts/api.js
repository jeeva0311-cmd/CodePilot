/**
 * API client — all fetch calls to the FastAPI backend.
 * Automatically attaches Bearer token from localStorage.
 */

const API_BASE = '';  // same-origin

function _getToken() {
  return localStorage.getItem('cp_token') || '';
}

async function apiFetch(path, options = {}) {
  const token = _getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const cfg = { ...options, headers: { ...headers, ...(options.headers || {}) } };
  if (cfg.body && typeof cfg.body === 'object') {
    cfg.body = JSON.stringify(cfg.body);
  }

  const res = await fetch(API_BASE + path, cfg);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const d = await res.json(); msg = d.detail || d.error || d.message || msg; } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

const API = {
  // ── Health ────────────────────────────────────────────────────────────────
  health: () => apiFetch('/api/health'),
  testLLM: () => apiFetch('/api/health/llm'),

  // ── Auth ──────────────────────────────────────────────────────────────────
  signup: (data) => apiFetch('/api/auth/signup', { method: 'POST', body: data }),
  login:  (data) => apiFetch('/api/auth/login',  { method: 'POST', body: data }),
  me:     ()     => apiFetch('/api/auth/me'),
  logout: ()     => apiFetch('/api/auth/logout', { method: 'POST' }),

  // ── Conversations ─────────────────────────────────────────────────────────
  listConversations:   ()        => apiFetch('/api/conversations'),
  createConversation:  (data)    => apiFetch('/api/conversations', { method: 'POST', body: data }),
  getConversation:     (id)      => apiFetch(`/api/conversations/${id}`),
  updateConversation:  (id, data)=> apiFetch(`/api/conversations/${id}`, { method: 'PATCH', body: data }),
  deleteConversation:  (id)      => apiFetch(`/api/conversations/${id}`, { method: 'DELETE' }),
  addMessage:          (cid, data)=> apiFetch(`/api/conversations/${cid}/messages`, { method: 'POST', body: data }),

  // ── Agent tasks ───────────────────────────────────────────────────────────
  createTask: (data) => apiFetch('/api/agent/tasks', { method: 'POST', body: data }),
  getTask:    (id)   => apiFetch(`/api/agent/tasks/${id}`),
  cancelTask: (id)   => apiFetch(`/api/agent/tasks/${id}/cancel`, { method: 'POST' }),

  // ── Approvals ─────────────────────────────────────────────────────────────
  getPendingApprovals: ()                 => apiFetch('/api/approvals/pending'),
  decideApproval:      (id, dec, reason) => apiFetch(`/api/approvals/${id}/decide`, {
    method: 'POST', body: { decision: dec, reason: reason || '' }
  }),

  // ── Workspace ─────────────────────────────────────────────────────────────
  getWorkspace:  ()     => apiFetch('/api/workspace'),
  setWorkspace:  (path) => apiFetch('/api/workspace', { method: 'POST', body: { path } }),
  listFiles:     (dir, depth) => apiFetch(`/api/workspace/files?dir=${encodeURIComponent(dir||'')}&depth=${depth||3}`),
  readFile:      (path) => apiFetch(`/api/files/read?path=${encodeURIComponent(path)}`),

  // ── Settings ─────────────────────────────────────────────────────────────
  getSettings:    ()         => apiFetch('/api/settings'),
  saveSetting:    (key, val) => apiFetch('/api/settings', { method: 'POST', body: { key, value: val } }),
  updateProvider: (data)     => apiFetch('/api/settings/provider', { method: 'POST', body: data }),
  getDbInfo:      ()         => apiFetch('/api/settings/db-info'),

  // ── RAG ───────────────────────────────────────────────────────────────────
  ragIndex:  (workspace_path) => apiFetch('/api/rag/index', { method: 'POST', body: { workspace_path } }),
  ragQuery:  (query, workspace_path, top_k) => apiFetch('/api/rag/query', {
    method: 'POST', body: { query, workspace_path, top_k: top_k || 5 }
  }),
  ragStats:  (workspace_path) => apiFetch(`/api/rag/stats${workspace_path ? '?workspace_path=' + encodeURIComponent(workspace_path) : ''}`),
  ragClear:  (workspace_path) => apiFetch(`/api/rag/index${workspace_path ? '?workspace_path=' + encodeURIComponent(workspace_path) : ''}`, { method: 'DELETE' }),
};
