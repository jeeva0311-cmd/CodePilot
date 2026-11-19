/**
 * CodePilot Agent — SPA with client-side routing
 * Pages: landing, about, login, signup, chat
 */

// ── Router ─────────────────────────────────────────────────────────────────
const PAGES = ['landing', 'about', 'login', 'signup', 'chat'];

function showPage(name) {
  PAGES.forEach(p => {
    const el = document.getElementById(`page-${p}`);
    if (el) el.classList.toggle('active', p === name);
  });
  history.pushState({ page: name }, '', `/${name === 'landing' ? '' : name}`);
  if (name === 'chat') initChat();
  if (name === 'landing') checkHealthBadge();
}

window.addEventListener('popstate', (e) => {
  const page = e.state?.page || 'landing';
  showPage(page);
});

// ── Auth state ──────────────────────────────────────────────────────────────
const Auth = {
  get token() { return localStorage.getItem('cp_token'); },
  get user()  { try { return JSON.parse(localStorage.getItem('cp_user') || 'null'); } catch { return null; } },
  set(token, user) {
    localStorage.setItem('cp_token', token);
    localStorage.setItem('cp_user', JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem('cp_token');
    localStorage.removeItem('cp_user');
  },
  isLoggedIn() { return !!this.token; },
};

// ── Boot ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Route based on current path
  const path = location.pathname.replace('/', '');
  const pageMap = { '': 'landing', 'login': 'login', 'signup': 'signup', 'about': 'about', 'chat': 'chat' };
  const initPage = pageMap[path] || 'landing';

  // If trying to access chat without auth, redirect to login
  if (initPage === 'chat' && !Auth.isLoggedIn()) {
    showPage('login');
  } else {
    showPage(initPage);
  }

  setupLandingEvents();
  setupAuthEvents();
  checkHealthBadge();
});

// ── Landing ─────────────────────────────────────────────────────────────────
function setupLandingEvents() {
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const target = el.dataset.nav;
      if (target === 'chat' && !Auth.isLoggedIn()) {
        showPage('login');
      } else {
        showPage(target);
      }
    });
  });
}

async function checkHealthBadge() {
  try {
    const h = await API.health();
    const badges = document.querySelectorAll('.api-status-inline');
    badges.forEach(b => {
      b.textContent = h.api_key_configured ? `● ${h.model}` : '● API key not configured';
      b.style.color = h.api_key_configured ? 'var(--green)' : 'var(--amber)';
    });
  } catch {}
}

// ── Auth — Signup ───────────────────────────────────────────────────────────
function setupAuthEvents() {
  // Signup form
  const signupForm = document.getElementById('signup-form');
  if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await handleSignup();
    });
  }

  // Login form
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      await handleLogin();
    });
  }
}

async function handleSignup() {
  const btn = document.getElementById('btn-signup');
  const alert = document.getElementById('signup-alert');
  const email = document.getElementById('su-email').value.trim();
  const username = document.getElementById('su-username').value.trim();
  const password = document.getElementById('su-password').value;
  const fullName = document.getElementById('su-fullname').value.trim();

  clearAuthAlert('signup-alert');
  if (!email || !username || !password) {
    showAuthAlert('signup-alert', 'Please fill in all required fields.', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating account…';

  try {
    const res = await API.signup({ email, username, password, full_name: fullName });
    Auth.set(res.token, res);
    showAuthAlert('signup-alert', 'Account created! Redirecting…', 'success');
    setTimeout(() => showPage('chat'), 800);
  } catch (err) {
    showAuthAlert('signup-alert', err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Create Account →';
  }
}

async function handleLogin() {
  const btn = document.getElementById('btn-login');
  const email = document.getElementById('li-email').value.trim();
  const password = document.getElementById('li-password').value;

  clearAuthAlert('login-alert');
  if (!email || !password) {
    showAuthAlert('login-alert', 'Please enter your email and password.', 'error');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Signing in…';

  try {
    const res = await API.login({ email, password });
    Auth.set(res.token, res);
    showAuthAlert('login-alert', 'Welcome back! Redirecting…', 'success');
    setTimeout(() => showPage('chat'), 600);
  } catch (err) {
    showAuthAlert('login-alert', err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Sign In →';
  }
}

function showAuthAlert(id, msg, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = `auth-alert ${type}`;
}
function clearAuthAlert(id) {
  const el = document.getElementById(id);
  if (el) { el.className = 'auth-alert'; el.textContent = ''; }
}

// ── Chat workspace ──────────────────────────────────────────────────────────
let chatState = {
  convId: null,
  taskId: null,
  taskStatus: 'idle',
  eventSource: null,
  plan: [],
  toolCount: 0,
  fileChanges: [],
  errors: 0,
  filesRead: 0,
  workspace: '',
  actTab: 'activity',
  actCollapsed: false,
  initialized: false,
  _lastAgentMessage: null,
};

async function initChat() {
  if (chatState.initialized) return;
  chatState.initialized = true;

  // Show user info in sidebar
  const user = Auth.user;
  if (user) {
    const nameEl = document.getElementById('sidebar-username');
    const avatarEl = document.getElementById('sidebar-avatar');
    if (nameEl) nameEl.textContent = user.username || user.email;
    if (avatarEl) avatarEl.textContent = (user.username || user.email || 'U')[0].toUpperCase();
  }

  // Load conversations list
  await loadConversations();

  // Load workspace info
  try {
    const ws = await API.getWorkspace();
    chatState.workspace = ws.path || '';
    updateWorkspaceLabel(ws);
  } catch {}

  // Set up input events
  setupChatInput();
  setupActivityTabs();
  switchActTab('activity');   // ensure correct tab is shown on first load
  updateStatusBadge();

  // Auto-open most recent conversation if one exists
  try {
    const convs = await API.listConversations();
    if (convs.length > 0) {
      await openConversation(convs[0].id);
    }
  } catch {}
}

function setupChatInput() {
  const textarea = document.getElementById('chat-textarea');
  if (!textarea) return;

  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  textarea.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 180) + 'px';
  });

  // Welcome suggestions
  document.querySelectorAll('.suggest-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      textarea.value = btn.textContent.trim();
      textarea.focus();
    });
  });
}

function setupActivityTabs() {
  document.querySelectorAll('.act-tab').forEach(tab => {
    tab.addEventListener('click', () => switchActTab(tab.dataset.tab));
  });
}

// ── Conversations ───────────────────────────────────────────────────────────
async function loadConversations() {
  try {
    const convs = await API.listConversations();
    renderConvList(convs);
  } catch (e) {
    console.warn('Could not load conversations', e);
  }
}

function renderConvList(convs) {
  const list = document.getElementById('conv-list');
  if (!list) return;
  list.innerHTML = '';

  if (!convs.length) {
    list.innerHTML = '<div style="padding:12px 10px;font-size:12px;color:var(--text-dim);">No conversations yet</div>';
    return;
  }

  convs.forEach(c => {
    const el = document.createElement('div');
    el.className = 'conv-item' + (c.id === chatState.convId ? ' active' : '');
    el.dataset.id = c.id;
    el.innerHTML = `
      <span class="conv-ico">💬</span>
      <span class="conv-title">${esc(c.title)}</span>
      <button class="conv-del" title="Delete" onclick="deleteConv('${c.id}',event)">✕</button>
    `;
    el.addEventListener('click', (e) => {
      if (e.target.classList.contains('conv-del')) return;
      openConversation(c.id);
    });
    list.appendChild(el);
  });
}

async function openConversation(id) {
  chatState.convId = id;
  document.querySelectorAll('.conv-item').forEach(el =>
    el.classList.toggle('active', el.dataset.id === id));

  const msgArea = document.getElementById('chat-messages');
  document.getElementById('chat-welcome').classList.add('hidden');
  msgArea.innerHTML = '';

  try {
    const conv = await API.getConversation(id);
    document.getElementById('topbar-conv-title').textContent = conv.title;
    conv.messages.forEach(m => {
      if (m.role === 'user') appendUserMsg(m.content, false);
      else if (m.role === 'assistant' && m.message_type === 'approval') appendApprovalCard(JSON.parse(m.metadata_json || '{}'), false);
      else if (m.role === 'assistant') appendBotMsg(m.content, false);
    });
    scrollMessages();
  } catch (e) {
    showToast('Failed to load conversation', 'err');
  }
}

async function newConversation() {
  try {
    const conv = await API.createConversation({ title: 'New Chat', workspace_path: chatState.workspace });
    chatState.convId = conv.id;
    await loadConversations();
    clearChat();
    document.getElementById('topbar-conv-title').textContent = 'New Chat';
    resetActivityPanel();
  } catch (e) {
    showToast('Failed to create conversation', 'err');
  }
}

async function deleteConv(id, event) {
  event.stopPropagation();
  if (!confirm('Delete this conversation?')) return;
  try {
    await API.deleteConversation(id);
    if (chatState.convId === id) {
      chatState.convId = null;
      clearChat();
      document.getElementById('topbar-conv-title').textContent = 'CodePilot Agent';
    }
    await loadConversations();
  } catch {
    showToast('Failed to delete', 'err');
  }
}

function clearChat() {
  const msgs = document.getElementById('chat-messages');
  if (msgs) msgs.innerHTML = '';
  const welcome = document.getElementById('chat-welcome');
  if (welcome) welcome.classList.remove('hidden');
}

// ── Send message ────────────────────────────────────────────────────────────
async function sendMessage() {
  const textarea = document.getElementById('chat-textarea');
  if (!textarea) return;
  const prompt = textarea.value.trim();
  if (!prompt) return;

  // Prevent double-send while running
  if (chatState.taskStatus === 'running') {
    showToast('Agent is still running. Wait or click Stop.', 'warn');
    return;
  }

  // Ensure a conversation exists — create one silently if needed
  if (!chatState.convId) {
    try {
      const conv = await API.createConversation({
        title: prompt.slice(0, 55) + (prompt.length > 55 ? '…' : ''),
        workspace_path: chatState.workspace || '',
      });
      chatState.convId = conv.id;
      loadConversations().catch(() => {});
    } catch (e) {
      showToast('Could not start conversation: ' + e.message, 'err');
      return;
    }
  }

  // ── Optimistic UI: show user message immediately ──
  textarea.value = '';
  textarea.style.height = 'auto';

  // Hide welcome screen
  const welcome = document.getElementById('chat-welcome');
  if (welcome) welcome.classList.add('hidden');

  appendUserMsg(prompt, true);
  setRunning(true);
  resetActivityPanel();

  // Show typing indicator
  const typingId = appendTyping();

  // Create the backend task
  try {
    const task = await API.createTask({
      prompt,
      conversation_id: chatState.convId,
      workspace_path: chatState.workspace || '',
    });

    chatState.taskId = task.id;
    chatState.taskStatus = 'running';
    updateTaskWidget({ status: 'running', prompt });

    // Start SSE stream — typing indicator removed on first real event
    subscribeSSE(task.id, typingId);

    // Update conversation title in sidebar
    document.getElementById('topbar-conv-title').textContent =
      prompt.slice(0, 50) + (prompt.length > 50 ? '…' : '');
    loadConversations().catch(() => {});

  } catch (err) {
    removeTyping(typingId);
    setRunning(false);
    chatState.taskStatus = 'idle';
    const errMsg = `**Could not reach the agent:** ${err.message}\n\nMake sure the backend is running and your API key is configured in Settings.`;
    appendBotMsg(errMsg, true);
    showToast(err.message, 'err');
  }
}

// ── SSE ─────────────────────────────────────────────────────────────────────
function subscribeSSE(taskId, typingId) {
  if (chatState.eventSource) {
    chatState.eventSource.close();
    chatState.eventSource = null;
  }

  const es = new EventSource(`/api/agent/tasks/${taskId}/events`);
  chatState.eventSource = es;

  // Track whether we've removed the typing indicator yet
  let typingRemoved = false;
  function removeTypingOnce() {
    if (!typingRemoved) {
      typingRemoved = true;
      removeTyping(typingId);
    }
  }

  es.onmessage = (e) => {
    if (e.data === '{"type": "heartbeat"}' || e.data.includes('"heartbeat"')) return;
    try {
      const data = JSON.parse(e.data);
      // Remove typing indicator on the first real event that carries content
      if (data.type !== 'heartbeat' && data.type !== 'iteration_started') {
        removeTypingOnce();
      }
      handleEvent(data);
    } catch (err) {
      console.warn('SSE parse error:', err, e.data);
    }
  };

  es.onerror = (e) => {
    removeTypingOnce();
    es.close();
    chatState.eventSource = null;
    if (chatState.taskStatus === 'running') {
      chatState.taskStatus = 'idle';
      setRunning(false);
      appendBotMsg('**Connection to agent lost.** The task may have completed — check the conversation history or refresh.', true);
    }
  };
}

function handleEvent(data) {
  switch (data.type) {
    case 'heartbeat': break;

    case 'agent_started':
      addLogLine('Agent started', '');
      break;

    case 'planning':
      addLogLine('Planning...', '');
      break;

    case 'plan_generated':
    case 'plan_updated':
      chatState.plan = data.plan || [];
      renderPlan(chatState.plan);
      break;

    case 'rag_context':
      addLogLine('RAG', `${data.chunks} relevant chunks injected`);
      appendRagNotice(data.chunks);
      break;

    case 'iteration_started':
      updateTaskIter(data.iteration, data.max);
      break;

    case 'agent_message':
      if (data.content && data.content.trim()) {
        // Mark that we've received a real message — used to avoid duplication in task_completed
        chatState._lastAgentMessage = data.content;
        appendBotMsg(data.content, true);
        // Persist assistant message to conversation
        if (chatState.convId) {
          API.addMessage(chatState.convId, { role: 'assistant', content: data.content }).catch(() => {});
        }
      }
      break;

    case 'tool_started':
      addToolCard(data);
      addLogLine('Tool: ' + data.tool, summarizeArgs(data.arguments));
      chatState.toolCount++;
      updateStat('stat-tools', chatState.toolCount);
      switchActTab('tools');
      break;

    case 'tool_completed':
      updateToolCard(data.tool, data.status, data.duration, data.result_summary);
      addLogLine(data.status === 'completed' ? data.tool + ' done' : data.tool + ' failed', data.result_summary || '');
      if (data.status === 'failed') {
        chatState.errors++;
        updateStat('stat-errors', chatState.errors);
      }
      break;

    case 'tool_rejected':
      updateToolCard(data.tool, 'rejected', 0, data.reason);
      addLogLine(data.tool + ' rejected', '');
      break;

    case 'approval_requested':
      appendApprovalCard(data, true);
      addLogLine('Approval needed', data.summary || data.tool);
      switchActTab('activity');
      break;

    case 'approval_approved': addLogLine('Approved', data.tool || ''); break;
    case 'approval_rejected':
    case 'approval_timeout':  addLogLine('Rejected', data.tool || ''); break;

    case 'task_completed': {
      chatState.taskStatus = 'completed';
      chatState.fileChanges = [
        ...(data.files_created  || []).map(f => ({ path: f, type: 'created' })),
        ...(data.files_modified || []).map(f => ({ path: f, type: 'modified' })),
      ];
      chatState.filesRead = (data.files_read || []).length;
      updateStat('stat-files-r', chatState.filesRead);
      updateStat('stat-files-c', chatState.fileChanges.length);
      renderFileChanges(chatState.fileChanges);
      setRunning(false);
      updateTaskWidget({ status: 'completed' });

      // Show final_response only if it's different from the last agent_message we showed
      const finalResp = data.final_response || '';
      if (finalResp.trim() && finalResp !== chatState._lastAgentMessage) {
        appendBotMsg(finalResp, true);
        if (chatState.convId) {
          API.addMessage(chatState.convId, { role: 'assistant', content: finalResp }).catch(() => {});
        }
      }
      chatState._lastAgentMessage = null;
      addLogLine('Completed', (data.iterations || 1) + ' iteration(s)');
      loadConversations().catch(() => {});
      break;
    }

    case 'task_failed':
      chatState.taskStatus = 'failed';
      chatState._lastAgentMessage = null;
      setRunning(false);
      updateTaskWidget({ status: 'failed' });
      appendBotMsg(`**Task failed:** ${data.error || 'Unknown error'}\n\nCheck Settings to verify your API key and model.`, true);
      addLogLine('Failed', data.error || '');
      break;

    case 'task_cancelled':
      chatState.taskStatus = 'cancelled';
      chatState._lastAgentMessage = null;
      setRunning(false);
      updateTaskWidget({ status: 'cancelled' });
      appendBotMsg('**Task was cancelled.**', true);
      addLogLine('Cancelled', '');
      break;
  }
}

// ── Message rendering ────────────────────────────────────────────────────────
function appendUserMsg(text, animate) {
  const user = Auth.user;
  const initials = (user?.username || user?.email || 'U')[0].toUpperCase();
  const msgs = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = 'msg-group';
  el.innerHTML = `
    <div class="msg-row user-row" ${animate ? 'style="animation:slideup 0.2s"' : ''}>
      <div class="msg-avatar user-av">${esc(initials)}</div>
      <div class="msg-content">
        <div class="msg-bubble user-bubble">${esc(text)}</div>
        <div class="msg-meta">${timestamp()}</div>
      </div>
    </div>`;
  msgs.appendChild(el);
  if (animate) scrollMessages();
}

function appendBotMsg(text, animate) {
  const msgs = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = 'msg-group';
  el.innerHTML = `
    <div class="msg-row" ${animate ? 'style="animation:slideup 0.2s"' : ''}>
      <div class="msg-avatar bot-av">🤖</div>
      <div class="msg-content">
        <div class="msg-bubble bot-bubble">${renderMarkdown(text)}</div>
        <div class="msg-meta">${timestamp()}</div>
      </div>
    </div>`;
  msgs.appendChild(el);
  if (animate) scrollMessages();
}

function appendApprovalCard(data, animate) {
  const id = data.approval_id || '';
  const tool = data.tool || 'unknown';
  const summary = data.summary || '';
  const risk = data.risk || 'high';
  const args = data.arguments ? JSON.stringify(data.arguments, null, 2) : '';

  const msgs = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = 'msg-group';
  el.innerHTML = `
    <div class="msg-row" ${animate ? 'style="animation:slideup 0.2s"' : ''}>
      <div class="msg-avatar bot-av">⚠️</div>
      <div class="msg-content">
        <div class="approval-card" id="approval-${id}">
          <div class="approval-header">
            <span class="approval-title">Approval Required</span>
            <span class="risk-chip">${esc(risk.toUpperCase())}</span>
          </div>
          <div class="approval-body"><strong>${esc(tool)}</strong> — ${esc(summary)}</div>
          ${args ? `<div class="approval-cmd">${esc(args)}</div>` : ''}
          <div class="approval-btns">
            <button class="btn-approve" onclick="respondApproval('${id}','approved')">✓ Approve</button>
            <button class="btn-reject"  onclick="respondApproval('${id}','rejected')">✕ Reject</button>
          </div>
        </div>
      </div>
    </div>`;
  msgs.appendChild(el);
  if (animate) scrollMessages();
}

async function respondApproval(approvalId, decision) {
  try {
    await API.decideApproval(approvalId, decision);
    const card = document.getElementById(`approval-${approvalId}`);
    if (card) {
      card.style.opacity = '0.6';
      card.style.pointerEvents = 'none';
      const btns = card.querySelector('.approval-btns');
      if (btns) {
        const color = decision === 'approved' ? 'var(--green)' : 'var(--red)';
        btns.innerHTML = `<span style="font-size:13px;font-weight:700;color:${color};">
          ${decision === 'approved' ? '✓ Approved' : '✕ Rejected'}
        </span>`;
      }
    }
    showToast(`Operation ${decision}`, decision === 'approved' ? 'ok' : 'warn');
  } catch (e) {
    showToast(`Failed: ${e.message}`, 'err');
  }
}

function appendRagNotice(chunks) {
  const msgs = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.style.cssText = 'max-width:760px;margin:0 auto;padding:0 20px 4px;';
  el.innerHTML = `<span class="rag-notice">🔍 RAG: ${chunks} relevant code chunks injected into context</span>`;
  msgs.appendChild(el);
}

function appendTyping() {
  const id = 'typing-' + Date.now();
  const msgs = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.className = 'msg-group'; el.id = id;
  el.innerHTML = `
    <div class="msg-row">
      <div class="msg-avatar bot-av">🤖</div>
      <div class="msg-content">
        <div class="msg-bubble bot-bubble">
          <div class="typing-indicator"><span></span><span></span><span></span></div>
        </div>
      </div>
    </div>`;
  msgs.appendChild(el);
  scrollMessages();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Activity panel ───────────────────────────────────────────────────────────
function resetActivityPanel() {
  chatState.toolCount = 0; chatState.fileChanges = []; chatState.errors = 0; chatState.filesRead = 0;
  chatState._lastAgentMessage = null;
  updateStat('stat-tools', 0); updateStat('stat-errors', 0);
  updateStat('stat-files-r', 0); updateStat('stat-files-c', 0);
  const actLog = document.getElementById('act-log');
  if (actLog) actLog.innerHTML = '';
  const actPlan = document.getElementById('act-plan');
  if (actPlan) actPlan.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px 0;">Plan will appear here.</div>';
  const actTools = document.getElementById('act-tools');
  if (actTools) actTools.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px 0;">Tool calls will appear here.</div>';
  const actChanges = document.getElementById('act-changes');
  if (actChanges) actChanges.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px 0;">File changes will appear here.</div>';
  updateTaskWidget({ status: 'idle' });
}

function switchActTab(tab) {
  chatState.actTab = tab;
  document.querySelectorAll('.act-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.act-pane').forEach(p => p.classList.toggle('show', p.dataset.pane === tab));
}

function updateTaskWidget({ status, prompt, iteration, max }) {
  const dot = document.getElementById('task-dot');
  const lbl = document.getElementById('task-label');
  const iter = document.getElementById('task-iter');
  const preview = document.getElementById('task-preview');

  if (dot) dot.className = `task-dot ${status || 'idle'}`;
  if (lbl) lbl.textContent = (status || 'idle').charAt(0).toUpperCase() + (status || 'idle').slice(1);
  if (iter && iteration) iter.textContent = `${iteration}/${max}`;
  if (preview && prompt) preview.textContent = prompt.slice(0, 70);
}

function updateTaskIter(iter, max) {
  const el = document.getElementById('task-iter');
  if (el) el.textContent = `${iter}/${max}`;
}

function updateStat(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function addLogLine(title, detail) {
  const log = document.getElementById('act-log');
  if (!log) return;
  const el = document.createElement('div');
  el.className = 'log-line';
  el.innerHTML = `<strong style="color:var(--cream)">${esc(title)}</strong>${detail ? `<span>${esc(detail.slice(0,70))}</span>` : ''}`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
}

function renderPlan(steps) {
  const container = document.getElementById('act-plan');
  if (!container) return;
  container.innerHTML = '';
  if (!steps?.length) return;

  const icons = { completed: '✅', in_progress: '🔄', pending: '○', failed: '❌', skipped: '⏭' };
  steps.forEach(step => {
    const el = document.createElement('div');
    el.className = 'plan-step';
    const cls = step.status === 'completed' ? 'done' : step.status === 'in_progress' ? 'active' : '';
    el.innerHTML = `<span class="plan-step-icon">${icons[step.status] || '○'}</span>
      <span class="plan-step-desc ${cls}">${esc(step.description)}</span>`;
    container.appendChild(el);
  });
}

function addToolCard(data) {
  const container = document.getElementById('act-tools');
  // Clear placeholder text
  if (container.querySelector('div[style]')) container.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'tool-card';
  card.dataset.tool = data.tool;
  const args = data.arguments ? JSON.stringify(data.arguments, null, 2) : '';
  const riskColor = { low: 'var(--green)', medium: 'var(--amber)', high: 'var(--red)' };
  card.innerHTML = `
    <div class="tool-card-head" onclick="this.nextElementSibling.classList.toggle('open')">
      <span style="color:${riskColor[data.risk]||'var(--text-dim)'};font-size:10px;">●</span>
      <span class="tool-name-label">${esc(data.tool)}</span>
      <span class="tool-chip chip-run">running</span>
    </div>
    <div class="tool-card-body">
      <div class="tool-code">${esc(args)}</div>
      <div class="tool-dur">Running…</div>
    </div>`;
  container.insertBefore(card, container.firstChild);
}

function updateToolCard(toolName, status, duration, summary) {
  const cards = Array.from(document.querySelectorAll(`.tool-card[data-tool="${toolName}"]`));
  const card = cards.find(c => c.querySelector('.chip-run'));
  if (!card) return;
  const chip = card.querySelector('.tool-chip');
  const chipMap = { completed: 'chip-ok', failed: 'chip-err', rejected: 'chip-rej', cancelled: 'chip-rej' };
  chip.className = `tool-chip ${chipMap[status] || 'chip-ok'}`;
  chip.textContent = status.charAt(0).toUpperCase() + status.slice(1);
  const dur = card.querySelector('.tool-dur');
  if (dur) dur.textContent = duration ? `${duration.toFixed(2)}s — ${summary || ''}` : (summary || '');
}

function renderFileChanges(changes) {
  const container = document.getElementById('act-changes');
  container.innerHTML = '';
  if (!changes.length) {
    container.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px 0;">No file changes.</div>';
    return;
  }
  changes.forEach(fc => {
    const el = document.createElement('div');
    el.className = 'fc-item';
    el.innerHTML = `<span class="fc-badge fc-${fc.type}">${fc.type}</span><span class="fc-path" title="${esc(fc.path)}">${esc(fc.path)}</span>`;
    container.appendChild(el);
  });
}

// ── Stop agent ───────────────────────────────────────────────────────────────
async function stopAgent() {
  if (!chatState.taskId) return;
  try {
    await API.cancelTask(chatState.taskId);
    showToast('Cancellation requested', 'warn');
  } catch (e) {
    showToast(`Cancel failed: ${e.message}`, 'err');
  }
}

// ── UI helpers ───────────────────────────────────────────────────────────────
function setRunning(running) {
  const send = document.getElementById('btn-chat-send');
  const stop = document.getElementById('btn-chat-stop');
  const ta   = document.getElementById('chat-textarea');
  if (send) send.disabled = running;
  if (ta)   ta.disabled   = running;
  if (stop) stop.classList.toggle('show', running);
  chatState.taskStatus = running ? 'running' : 'idle';
}

function scrollMessages() {
  const msgs = document.getElementById('chat-messages');
  if (msgs) requestAnimationFrame(() => msgs.scrollTop = msgs.scrollHeight);
}

function updateStatusBadge() {
  API.health().then(h => {
    const badge = document.getElementById('topbar-status-badge');
    if (!badge) return;
    if (h.api_key_configured) {
      badge.className = 'topbar-status ts-ok';
      badge.textContent = h.model;
    } else {
      badge.className = 'topbar-status ts-warn';
      badge.textContent = 'API key missing';
    }
  }).catch(() => {
    const badge = document.getElementById('topbar-status-badge');
    if (badge) { badge.className = 'topbar-status ts-err'; badge.textContent = 'Offline'; }
  });
}

function updateWorkspaceLabel(ws) {
  const el = document.getElementById('workspace-label');
  if (el) el.textContent = ws.name || 'workspace';
}

function summarizeArgs(args) {
  if (!args) return '';
  if (args.path) return args.path;
  if (args.command) return args.command;
  if (args.query) return args.query;
  return JSON.stringify(args).slice(0, 50);
}

// ── Settings modal ────────────────────────────────────────────────────────────
let selectedProvider = 'groq';

async function openSettings() {
  document.getElementById('settings-overlay').classList.add('open');
  try {
    const s = await API.getSettings();
    document.getElementById('s-model').value = s.model || '';
    document.getElementById('s-max-iter').value = s.max_iterations || '12';
    document.getElementById('s-timeout').value = s.command_timeout || '30';
    document.getElementById('s-approve-high').checked = s.require_approval_high === 'true';
    document.getElementById('s-approve-med').checked = s.require_approval_medium === 'true';
    selectedProvider = s.provider || 'groq';
    updateProviderTabs();
    updateModelOptions(selectedProvider, s.provider_models, s.model);

    const apiStatus = document.getElementById('s-api-status');
    if (apiStatus) {
      apiStatus.innerHTML = s.api_key_configured
        ? '<span style="color:var(--green)">✓ API key configured</span>'
        : '<span style="color:var(--amber)">⚠ API key not set</span>';
    }

    try { const db = await API.getDbInfo(); document.getElementById('s-db-info').textContent = `${db.path} (${db.size_kb} KB)`; } catch {}
    try { const rag = await API.ragStats(); document.getElementById('s-rag-info').textContent = `${rag.chunk_count} chunks indexed`; } catch {}
  } catch (e) {
    showToast('Failed to load settings', 'err');
  }
}

function closeSettings() {
  document.getElementById('settings-overlay').classList.remove('open');
}

function selectProvider(p) {
  selectedProvider = p;
  updateProviderTabs();
  API.getSettings().then(s => updateModelOptions(p, s.provider_models, '')).catch(() => {});
}

function updateProviderTabs() {
  document.querySelectorAll('.provider-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.provider === selectedProvider));
}

function updateModelOptions(provider, modelsMap, currentModel) {
  const sel = document.getElementById('s-model');
  if (!sel || !modelsMap) return;
  const models = modelsMap[provider] || [];
  sel.innerHTML = models.map(m => `<option value="${m}" ${m === currentModel ? 'selected' : ''}>${m}</option>`).join('');
  if (!models.includes(currentModel) && currentModel) {
    sel.innerHTML += `<option value="${currentModel}" selected>${currentModel}</option>`;
  }
}

async function saveProviderSettings() {
  const apiKey = document.getElementById('s-api-key').value.trim();
  const model  = document.getElementById('s-model').value.trim();
  const baseUrl = document.getElementById('s-base-url').value.trim();

  if (!model) { showToast('Model is required', 'warn'); return; }

  const btn = document.getElementById('btn-save-provider');
  btn.disabled = true; btn.textContent = 'Saving…';
  try {
    await API.updateProvider({ provider: selectedProvider, api_key: apiKey, model, base_url: baseUrl });
    showToast('Provider settings saved', 'ok');
    updateStatusBadge();
  } catch (e) {
    showToast('Failed: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Save Provider';
  }
}

async function saveGeneralSettings() {
  const pairs = [
    ['max_iterations', document.getElementById('s-max-iter').value],
    ['command_timeout', document.getElementById('s-timeout').value],
    ['require_approval_high',  document.getElementById('s-approve-high').checked ? 'true' : 'false'],
    ['require_approval_medium', document.getElementById('s-approve-med').checked ? 'true' : 'false'],
  ];
  try {
    for (const [k, v] of pairs) await API.saveSetting(k, v);
    showToast('Settings saved', 'ok');
  } catch (e) {
    showToast('Failed: ' + e.message, 'err');
  }
}

async function testLLM() {
  const btn = document.getElementById('btn-test-llm');
  btn.disabled = true; btn.textContent = 'Testing…';
  try {
    const r = await API.testLLM();
    if (r.status === 'connected') showToast(`Connected: ${r.model}`, 'ok');
    else showToast(r.message || 'Connection failed', 'err');
  } catch (e) {
    showToast('Connection error: ' + e.message, 'err');
  } finally {
    btn.disabled = false; btn.textContent = 'Test Connection';
  }
}

async function triggerRAGIndex() {
  const btn = document.getElementById('btn-rag-index');
  btn.disabled = true; btn.textContent = 'Indexing…';
  try {
    await API.ragIndex(chatState.workspace);
    showToast('Workspace indexing started in background', 'ok');
    setTimeout(async () => {
      const rag = await API.ragStats().catch(() => ({ chunk_count: 0 }));
      document.getElementById('s-rag-info').textContent = `${rag.chunk_count} chunks indexed`;
      btn.disabled = false; btn.textContent = 'Re-index Workspace';
    }, 3000);
  } catch (e) {
    showToast('RAG index failed: ' + e.message, 'err');
    btn.disabled = false; btn.textContent = 'Re-index Workspace';
  }
}

// ── Logout ───────────────────────────────────────────────────────────────────
async function logout() {
  await API.logout().catch(() => {});
  Auth.clear();
  chatState.initialized = false;
  chatState.convId = null;
  chatState.taskId = null;
  showPage('landing');
  showToast('Logged out', 'ok');
}

// ── Toast ────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'ok') {
  const wrap = document.getElementById('toast-wrap');
  const icons = { ok: '✅', err: '❌', warn: '⚠️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || ''}</span><span>${esc(msg)}</span>`;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Utilities ────────────────────────────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function timestamp() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
