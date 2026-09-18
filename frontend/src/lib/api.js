let _token = localStorage.getItem('oi_token') || '';
export const getToken = () => _token;
export const setToken = (t) => { _token = t || ''; t ? localStorage.setItem('oi_token', t) : localStorage.removeItem('oi_token'); };

async function req(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(_token ? { Authorization: `Bearer ${_token}` } : {}), ...(opts.headers || {}) },
    ...opts,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

export const api = {
  health: () => req('/api/health'),
  meta: () => req('/api/meta'),
  seed: () => req('/api/seed', { method: 'POST' }),
  register: (b) => req('/api/auth/register', { method: 'POST', body: JSON.stringify(b) }),
  login: (b) => req('/api/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  logout: () => req('/api/auth/logout', { method: 'POST', body: '{}' }),
  me: () => req('/api/auth/me'),
  integrations: () => req('/api/integrations'),
  gmailStatus: () => req('/api/integrations/gmail/status'),
  gmailConnect: () => req('/api/integrations/gmail/connect', { method: 'POST', body: '{}' }),
  profile: (user_id) => req(`/api/profile?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  saveProfile: (p) => req('/api/profile', { method: 'POST', body: JSON.stringify(p) }),
  resumeText: (user_id, text) => req('/api/profile/resume', { method: 'POST', body: JSON.stringify({ user_id, text }) }),
  resumeFile: async (user_id, file) => {
    const fd = new FormData();
    fd.append('user_id', user_id);
    fd.append('file', file);
    const r = await fetch('/api/profile/resume', {
      method: 'POST', body: fd,
      ...(getToken() ? { headers: { Authorization: `Bearer ${getToken()}` } } : {}),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  },
  discover: (goal, max_results = 12, user_id) =>
    req('/api/opportunities/discover', { method: 'POST', body: JSON.stringify({ user_goal: goal, max_results, user_id: user_id || 'demo-user' }) }),
  listOpps: (user_id) => req(`/api/opportunities?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  getOpp: (id) => req(`/api/opportunities/${id}`),
  investigate: (id) => req(`/api/opportunities/${id}/investigate`, { method: 'POST', body: '{}' }),
  verify: (id) => req(`/api/opportunities/${id}/verify`, { method: 'POST' }),
  match: (id) => req(`/api/opportunities/${id}/match`, { method: 'POST', body: '{}' }),
  prepareApp: (id) => req(`/api/opportunities/${id}/prepare-application`, { method: 'POST', body: '{}' }),
  resumeQuestions: (id, user_id) => req(`/api/opportunities/${id}/resume-questions`, { method: 'POST', body: JSON.stringify({ user_id }) }),
  buildResume: (id, user_id, answers, keep_template) => req(`/api/opportunities/${id}/build-resume`, { method: 'POST', body: JSON.stringify({ user_id, answers, keep_template: !!keep_template }) }),
  templateInfo: (user_id) => req(`/api/profile/template?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  listApps: (user_id) => req(`/api/applications?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  findContact: (id) => req(`/api/opportunities/${id}/find-contact`, { method: 'POST' }),
  genOutreach: (id) => req(`/api/opportunities/${id}/generate-outreach`, { method: 'POST', body: '{}' }),
  approveOutreach: (id, patch = {}) => req(`/api/outreach/${id}/approve`, { method: 'POST', body: JSON.stringify(patch) }),
  draftOutreach: (id) => req(`/api/outreach/${id}/draft`, { method: 'POST', body: '{}' }),
  sendOutreach: (id, approval_id) => req(`/api/outreach/${id}/send`, { method: 'POST', body: JSON.stringify({ approval_id }) }),
  watch: (id, user_id) => req(`/api/opportunities/${id}/watch`, { method: 'POST', body: JSON.stringify({ user_id: user_id || 'demo-user' }) }),
  checkNow: (id, simulated) => req(`/api/opportunities/${id}/check-now`, { method: 'POST', body: JSON.stringify(simulated ? { simulated } : {}) }),
  monitoring: (user_id) => req(`/api/monitoring?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  notifications: (user_id) => req(`/api/notifications?user_id=${encodeURIComponent(user_id || 'demo-user')}`),
  approvals: () => req('/api/approvals'),
  decideApproval: (id, decision) => req(`/api/approvals/${id}/decide`, { method: 'POST', body: JSON.stringify({ decision }) }),
  activity: () => req('/api/activity'),
  oppActivity: (id) => req(`/api/opportunities/${id}/activity`),
  testAll: () => req('/api/test/all'),
};
