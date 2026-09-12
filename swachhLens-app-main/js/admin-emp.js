/* =====================================================================
 * Employee Task Dashboard — with photo upload for task completion
 * ===================================================================== */
(function () {
  const SESSION_KEY = 'swachlens.admin_session';
  const INITIAL_VISIBLE = 5;
  const COMPLETED_INITIAL = 5;

  function getSession() {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
  }
  function getToken() { const s = getSession(); return s ? s.authToken : null; }

  const session = getSession();
  if (!session || session.role !== 'employee') {
    window.location.href = 'admin-login.html';
    return;
  }

  // ── DOM refs ────────────────────────────────────────────────────────────
  const $name = document.getElementById('userName');
  const $id = document.getElementById('userId');
  const $avatar = document.getElementById('userAvatar');
  const $greetName = document.getElementById('greetName');
  const $taskList = document.getElementById('taskList');
  const $sectionTitle = document.getElementById('sectionTitle');
  const $statTotal = document.getElementById('statTotal');
  const $statPending = document.getElementById('statPending');
  const $statAccepted = document.getElementById('statAccepted');
  const $statRejected = document.getElementById('statRejected');
  const $progressPct = document.getElementById('progressPct');
  const $progressFill = document.getElementById('progressFill');
  const $filterAll = document.getElementById('filterAll');
  const $filterPending = document.getElementById('filterPending');
  const $filterAccepted = document.getElementById('filterAccepted');
  const $filterRejected = document.getElementById('filterRejected');
  const $pendingBadge = document.getElementById('pendingBadge');

  const initials = (session.name || 'E').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  $name.textContent = session.name;
  $id.textContent = session.userId;
  $avatar.textContent = initials;
  $greetName.textContent = session.name.split(' ')[0];

  // ── Auth fetch ──────────────────────────────────────────────────────────
  function authFetch(method, path, body) {
    const BASE = window.SW_CONFIG.API_URL;
    return fetch(BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + getToken() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then(res => {
      if (!res.ok) return res.json().then(d => { throw new Error(d.detail || 'Request failed'); });
      if (res.status === 204) return null;
      return res.json();
    });
  }

  const api = {
    combined: () => authFetch('GET', '/admin/employee-tasks'),
    acceptTask: (id) => authFetch('PATCH', '/admin/tasks/' + encodeURIComponent(id) + '/accept'),
    rejectTask: (id) => authFetch('PATCH', '/admin/tasks/' + encodeURIComponent(id) + '/reject'),
    acceptReport: (id) => authFetch('PATCH', '/admin/reports/' + encodeURIComponent(id) + '/emp-accept'),
    rejectReport: (id) => authFetch('PATCH', '/admin/reports/' + encodeURIComponent(id) + '/emp-reject'),
    completeReport: (id, data) => authFetch('PATCH', '/admin/reports/' + encodeURIComponent(id) + '/complete', data),
  };

  let tasks = [];
  let reports = [];
  let activeFilter = 'all';
  let sortBy = 'newest';
  let visibleCount = INITIAL_VISIBLE;
  let completedVisibleCount = COMPLETED_INITIAL;

  // ── Helpers ─────────────────────────────────────────────────────────────
  function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

  function timeAgo(ts) {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + 'm ago';
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    const days = Math.floor(hrs / 24);
    return days + 'd ago';
  }

  function formatDate(ts) {
    return new Date(ts).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function showToast(msg, isErr) {
    const existing = document.querySelector('.toast.show');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.className = 'toast show' + (isErr ? ' toast--err' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  const WASTE_ICONS = { 'Plastic': '🧴', 'Organic': '🥗', 'E-Waste': '🔌', 'Hazardous': '☣️' };

  // ── Load tasks ──────────────────────────────────────────────────────────
  async function loadTasks() {
    try {
      const data = await api.combined();
      tasks = data.adminTasks || [];
      reports = data.reports || [];
      updateStats();
      renderTasks();
      renderCompletedTasks();
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  }

  // ── Stats ───────────────────────────────────────────────────────────────
  function updateStats() {
    const allItems = getAllItems();
    const total = allItems.length;
    const pending = allItems.filter(t => t.status === 'pending').length;
    const accepted = allItems.filter(t => t.status === 'accepted').length;
    const rejected = allItems.filter(t => t.status === 'rejected').length;
    const completed = allItems.filter(t => t.status === 'completed' || t.status === 'resolved').length;

    $statTotal.textContent = total;
    $statPending.textContent = pending;
    $statAccepted.textContent = accepted;
    $statRejected.textContent = rejected;
    const $statCompleted = document.getElementById('statCompleted');
    if ($statCompleted) $statCompleted.textContent = completed;
    // Filter tabs count only active items (excluding completed/resolved)
    const activeTotal = total - completed;
    $filterAll.textContent = activeTotal;
    $filterPending.textContent = pending;
    $filterAccepted.textContent = accepted;
    $filterRejected.textContent = rejected;

    if ($pendingBadge) {
      $pendingBadge.textContent = pending;
      $pendingBadge.style.display = pending > 0 ? 'inline-flex' : 'none';
    }

    const pct = total ? Math.round((accepted / total) * 100) : 0;
    $progressPct.textContent = pct + '%';
    $progressFill.style.width = pct + '%';
  }

  function getAllItems() {
    return [
      ...tasks.map(t => ({
        _type: 'task', _id: t.id, title: t.title, description: t.description,
        status: t.status, createdAt: t.createdAt, createdBy: t.createdBy,
        icon: '🗑️', location: null, severity: null, reporterName: null, wasteType: null,
        photo: null, proofPhoto: null,
      })),
      ...reports.map(r => ({
        _type: 'report', _id: r.id, title: (r.wasteType || 'Waste') + ' waste — ' + r.location,
        description: r.description,
        status: r.status === 'ASSIGNED' ? 'pending' : r.status === 'IN_PROGRESS' ? 'accepted' : r.status === 'VERIFY' ? 'completed' : r.status === 'RESOLVED' ? 'resolved' : r.status.toLowerCase(),
        createdAt: r.createdAt, createdBy: r.reporterName || r.reporter,
        icon: WASTE_ICONS[r.wasteType] || '🗑️', location: r.location, severity: r.severity,
        reporterName: r.reporterName, wasteType: r.wasteType,
        photo: r.photo, proofPhoto: r.proofPhoto,
      })),
    ];
  }

  // ── Badge helper ────────────────────────────────────────────────────────
  function badgeForStatus(status) {
    const map = { pending: 'st-pending', accepted: 'st-progress', completed: 'st-verify', resolved: 'st-resolved', rejected: 'st-cancelled' };
    const labelKeys = { pending: 'st.pending', accepted: 'st.inProgress', completed: 'st.verification', resolved: 'st.resolved', rejected: 'st.cancelled' };
    const label = labelKeys[status] ? (window.t ? t(labelKeys[status]) : labelKeys[status]) : status;
    return `<span class="status-badge ${map[status] || 'st-pending'}">${label}</span>`;
  }

  // ── Render tasks ────────────────────────────────────────────────────────
  function renderTasks() {
    const allItems = getAllItems();
    // Exclude completed/resolved from main list (shown in separate section)
    const activeItems = allItems.filter(t => t.status !== 'completed' && t.status !== 'resolved');
    let filtered = activeFilter === 'all' ? activeItems : activeItems.filter(t => t.status === activeFilter);

    if (sortBy === 'newest') filtered.sort((a, b) => b.createdAt - a.createdAt);
    else filtered.sort((a, b) => a.createdAt - b.createdAt);
    filtered.sort((a, b) => {
      if (a.status === 'pending' && b.status !== 'pending') return -1;
      if (b.status === 'pending' && a.status !== 'pending') return 1;
      return 0;
    });

    const titleKeys = { all: 'emtask.allTasks', pending: 'emtask.pendingTasks', accepted: 'emtask.inProgress', completed: 'emtask.awaitingVerify', resolved: 'emtask.resolvedTasks', rejected: 'emtask.rejectedTasks' };
    $sectionTitle.textContent = window.t && titleKeys[activeFilter] ? t(titleKeys[activeFilter]) : (titleKeys[activeFilter] || 'All Tasks');

    if (!filtered.length) {
      const empties = {
        all: ['📭', 'No tasks yet', 'Tasks assigned by admins will appear here'],
        pending: ['✨', 'No pending tasks', 'All caught up!'],
        accepted: ['🔨', 'No tasks in progress', 'Accept pending tasks to start working'],
        completed: ['📸', 'No tasks awaiting verification', 'Complete tasks to submit proof'],
        resolved: ['🎉', 'No resolved tasks', 'Completed tasks will appear here'],
        rejected: ['🕊️', 'No rejected tasks', 'Nothing rejected — great!'],
      };
      const [ico, text, sub] = empties[activeFilter] || empties.all;
      $taskList.innerHTML = `<div class="empty-state"><span class="empty-state__icon">${ico}</span><b>${text}</b><p style="font-size:14px;color:var(--muted);">${sub}</p></div>`;
      return;
    }

    const shown = filtered.slice(0, visibleCount);
    const hasMore = filtered.length > visibleCount;

    let html = shown.map((t, i) => {
      const canAct = t.status === 'pending';
      const isInProgress = t.status === 'accepted';
      const isCompleted = t.status === 'completed';
      const isResolved = t.status === 'resolved';
      const isRejected = t.status === 'rejected';
      const isDone = isResolved || isRejected;
      const pct = isResolved ? 100 : isCompleted ? 75 : isInProgress ? 50 : isRejected ? 0 : 0;
      const barCol = isResolved ? '#22c55e' : isCompleted ? '#8b5cf6' : isInProgress ? '#3b82f6' : isRejected ? '#ef4444' : '#f59e0b';
      const doneClass = isDone ? ' style="opacity:.75;"' : '';

      let actions = '';
      if (canAct) {
        actions = `
          <div class="rc-assign-row" style="margin-top:12px;">
            <button class="rc-btn" style="font-weight:800;color:var(--green-700);border-color:var(--green-400);flex:1;" data-action="accept">✓ Accept</button>
            <button class="rc-btn rc-btn--cancel" style="font-weight:800;flex:1;" data-action="reject">✕ Reject</button>
          </div>`;
      } else if (isInProgress && t._type === 'report') {
        actions = `
          <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:var(--muted);margin-bottom:8px;">📸 Upload Completion Proof</div>
            <div class="rc-assign-row">
              <label class="rc-btn" style="flex:1;cursor:pointer;text-align:center;font-weight:800;border-style:dashed;" data-action="pick-photo">
                📷 Choose Photo
                <input type="file" accept="image/*" capture="environment" style="display:none;" data-file-input>
              </label>
              <button class="rc-btn" style="font-weight:800;color:var(--green-700);border-color:var(--green-400);flex:1;display:none;" data-action="submit-proof">🚀 Submit Proof</button>
            </div>
            <div class="proof-preview" style="display:none;margin-top:8px;position:relative;">
              <img style="max-height:150px;border-radius:12px;width:100%;object-fit:cover;" data-proof-img>
              <button style="position:absolute;top:6px;right:6px;background:rgba(0,0,0,.6);color:#fff;border:none;border-radius:50%;width:28px;height:28px;cursor:pointer;font-size:14px;" data-action="remove-photo">✕</button>
            </div>
          </div>`;
      } else if (isCompleted) {
        actions = `
          <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:#8b5cf6;margin-bottom:4px;">📸 Proof submitted — awaiting admin verification</div>
            ${t.proofPhoto ? '<img src="' + esc(t.proofPhoto) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin-top:8px;">' : ''}
          </div>`;
      } else if (isResolved) {
        actions = `
          <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:var(--green-600);">✅ Task verified and resolved by admin</div>
            ${t.proofPhoto ? '<img src="' + esc(t.proofPhoto) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin-top:8px;">' : ''}
          </div>`;
      } else if (isRejected) {
        actions = `
          <div class="rc-actions" style="margin-top:12px;">
            <span class="rc-tag">❌ You rejected this task</span>
          </div>`;
      }

      return `
      <article class="report-card reveal in"${doneClass} style="animation-delay:${Math.min(i * 60, 360)}ms" data-id="${t._id}" data-type="${t._type || 'task'}">
        <div class="rc-body">
          <div class="rc-top">
            <h4>${t.icon || '🗑️'} ${esc(t.title)}</h4>
            ${badgeForStatus(t.status)}
          </div>
          ${t.description ? '<div class="rc-meta" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + esc(t.description) + '</div>' : ''}
          ${t.photo ? '<img src="' + esc(t.photo) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin:6px 0;">' : ''}
          <div class="rc-progress"><i style="width:${pct}%;background:${barCol};"></i></div>
          <div class="rc-foot">
            ${t.location ? '<span class="rc-tag" title="' + esc(t.location) + '"><span class="rc-ico">📍</span> ' + esc(t.location.length > 20 ? t.location.slice(0, 20) + '…' : t.location) + '</span>' : ''}
            ${t.severity ? '<span class="rc-tag"><span class="rc-ico">⚠️</span> ' + esc(t.severity) + '</span>' : ''}
            ${t.createdBy ? '<span class="rc-tag" title="' + esc(t.createdBy) + '"><span class="rc-ico">🛠️</span> ' + esc(t.createdBy.length > 10 ? t.createdBy.slice(0, 10) + '…' : t.createdBy) + '</span>' : ''}
            <span class="rc-tag"><span class="rc-ico">📅</span> ${formatDate(t.createdAt)}</span>
            <span class="rc-tag"><span class="rc-ico">⏱️</span> ${timeAgo(t.createdAt)}</span>
          </div>
          ${actions}
        </div>
      </article>`;
    }).join('');

    if (hasMore) {
      const remaining = filtered.length - visibleCount;
      html += `<div class="reports-more"><button class="rc-btn show-more-btn" style="padding:12px 28px;font-weight:800;">Show more (${remaining} remaining)</button></div>`;
    }

    $taskList.innerHTML = html;

    // Bind show more
    $taskList.querySelectorAll('.show-more-btn').forEach(btn => {
      btn.addEventListener('click', () => { visibleCount += INITIAL_VISIBLE; renderTasks(); });
    });

    // Completed section is rendered from loadTasks() after renderTasks()

    // Bind accept buttons
    $taskList.querySelectorAll('[data-action="accept"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        btn.disabled = true;
        btn.textContent = 'Accepting...';
        try {
          if (card.dataset.type === 'report') await api.acceptReport(id);
          else await api.acceptTask(id);
          showToast('✓ Accepted!');
          await loadTasks();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '✓ Accept';
          showToast(err.message, true);
        }
      });
    });

    // Bind reject buttons
    $taskList.querySelectorAll('[data-action="reject"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        if (!confirm('Are you sure you want to reject this task?')) return;
        btn.disabled = true;
        btn.textContent = 'Rejecting...';
        try {
          if (card.dataset.type === 'report') await api.rejectReport(id);
          else await api.rejectTask(id);
          showToast('Task rejected');
          await loadTasks();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '✕ Reject';
          showToast(err.message, true);
        }
      });
    });

    // Bind photo upload
    $taskList.querySelectorAll('[data-file-input]').forEach(input => {
      input.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const card = input.closest('.report-card');
        const preview = card.querySelector('.proof-preview');
        const img = card.querySelector('[data-proof-img]');
        const submitBtn = card.querySelector('[data-action="submit-proof"]');
        try {
          const base64 = await fileToBase64(file);
          img.src = base64;
          preview.style.display = 'block';
          submitBtn.style.display = 'inline-flex';
          submitBtn.dataset.proofPhoto = base64;
        } catch (err) {
          showToast('Failed to load photo', true);
        }
      });
    });

    // Bind remove photo
    $taskList.querySelectorAll('[data-action="remove-photo"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const card = btn.closest('.report-card');
        card.querySelector('.proof-preview').style.display = 'none';
        card.querySelector('[data-action="submit-proof"]').style.display = 'none';
        card.querySelector('[data-file-input]').value = '';
      });
    });

    // Bind submit proof
    $taskList.querySelectorAll('[data-action="submit-proof"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        const proofPhoto = btn.dataset.proofPhoto;
        if (!proofPhoto) { showToast('Please select a photo first', true); return; }
        btn.disabled = true;
        btn.textContent = 'Submitting...';
        try {
          await api.completeReport(id, { proofPhoto });
          showToast('✓ Proof submitted! Admin will verify.');
          await loadTasks();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '🚀 Submit Proof';
          showToast(err.message, true);
        }
      });
    });
  }

  // ── Render completed tasks section ──────────────────────────────────
  function renderCompletedTasks() {
    const allItems = getAllItems();
    const completedItems = allItems.filter(t => t.status === 'completed' || t.status === 'resolved');
    completedItems.sort((a, b) => b.createdAt - a.createdAt);

    const $completedList = document.getElementById('completedList');
    const $completedTitle = document.getElementById('completedTitle');
    if (!$completedList) return;

    $completedTitle.textContent = (window.t ? t('emtask.doneTitle') : 'Completed Tasks') + ' (' + completedItems.length + ')';

    if (!completedItems.length) {
      $completedList.innerHTML = `<div class="empty-state"><span class="empty-state__icon">📭</span><b>No completed tasks yet</b><p style="font-size:14px;color:var(--muted);">Accepted and resolved tasks will appear here</p></div>`;
      return;
    }

    const shown = completedItems.slice(0, completedVisibleCount);
    const hasMore = completedItems.length > completedVisibleCount;

    let html = shown.map((t, i) => {
      const isResolved = t.status === 'resolved';
      const pct = isResolved ? 100 : 75;
      const barCol = isResolved ? '#22c55e' : '#8b5cf6';
      const doneClass = isResolved ? ' style="opacity:.85;border-left:4px solid #22c55e;"' : ' style="border-left:4px solid #8b5cf6;"';

      let statusMsg = '';
      if (isResolved) {
        statusMsg = `<div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:var(--green-600);">✅ Task verified and resolved by admin</div>
            ${t.proofPhoto ? '<img src="' + esc(t.proofPhoto) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin-top:8px;">' : ''}
          </div>`;
      } else {
        statusMsg = `<div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:#8b5cf6;">📸 Proof submitted — awaiting admin verification</div>
            ${t.proofPhoto ? '<img src="' + esc(t.proofPhoto) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin-top:8px;">' : ''}
          </div>`;
      }

      return `
      <article class="report-card reveal in"${doneClass} style="animation-delay:${Math.min(i * 60, 360)}ms">
        <div class="rc-body">
          <div class="rc-top">
            <h4>${t.icon || '🗑️'} ${esc(t.title)}</h4>
            ${badgeForStatus(t.status)}
          </div>
          ${t.description ? '<div class="rc-meta" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + esc(t.description) + '</div>' : ''}
          ${t.photo ? '<img src="' + esc(t.photo) + '" style="max-height:120px;border-radius:12px;width:100%;object-fit:cover;margin:6px 0;">' : ''}
          <div class="rc-progress"><i style="width:${pct}%;background:${barCol};"></i></div>
          <div class="rc-foot">
            ${t.location ? '<span class="rc-tag" title="' + esc(t.location) + '"><span class="rc-ico">📍</span> ' + esc(t.location.length > 20 ? t.location.slice(0, 20) + '…' : t.location) + '</span>' : ''}
            ${t.severity ? '<span class="rc-tag"><span class="rc-ico">⚠️</span> ' + esc(t.severity) + '</span>' : ''}
            ${t.createdBy ? '<span class="rc-tag" title="' + esc(t.createdBy) + '"><span class="rc-ico">🛠️</span> ' + esc(t.createdBy.length > 10 ? t.createdBy.slice(0, 10) + '…' : t.createdBy) + '</span>' : ''}
            <span class="rc-tag"><span class="rc-ico">📅</span> ${formatDate(t.createdAt)}</span>
            <span class="rc-tag"><span class="rc-ico">⏱️</span> ${timeAgo(t.createdAt)}</span>
          </div>
          ${statusMsg}
        </div>
      </article>`;
    }).join('');

    if (hasMore) {
      const remaining = completedItems.length - completedVisibleCount;
      html += `<div class="reports-more"><button class="rc-btn show-more-completed-btn" style="padding:12px 28px;font-weight:800;">Show more (${remaining} remaining)</button></div>`;
    }

    $completedList.innerHTML = html;

    // Bind show more for completed
    $completedList.querySelectorAll('.show-more-completed-btn').forEach(btn => {
      btn.addEventListener('click', () => { completedVisibleCount += COMPLETED_INITIAL; renderCompletedTasks(); });
    });
  }

  // ── Filter tabs ─────────────────────────────────────────────────────────
  document.querySelectorAll('.pill[data-filter]').forEach(tab => {
    tab.addEventListener('click', () => {
      activeFilter = tab.dataset.filter;
      visibleCount = INITIAL_VISIBLE;
      completedVisibleCount = COMPLETED_INITIAL;
      document.querySelectorAll('.pill[data-filter]').forEach(t => t.classList.toggle('active', t === tab));
      renderTasks();
    });
  });

  // ── Sort button ─────────────────────────────────────────────────────────
  document.getElementById('sortBtn')?.addEventListener('click', () => {
    sortBy = sortBy === 'newest' ? 'oldest' : 'newest';
    document.getElementById('sortBtn').textContent = sortBy === 'newest' ? (window.t ? t('emtask.sortNew') : 'Newest first') : (window.t ? t('emtask.sortOld') : 'Oldest first');
    renderTasks();
  });

  // ── Logout ──────────────────────────────────────────────────────────────
  document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem(SESSION_KEY);
    window.location.href = 'admin-login.html';
  });

  // ── Refresh ─────────────────────────────────────────────────────────────
  document.getElementById('refreshBtn').addEventListener('click', async () => {
    await loadTasks();
    showToast('Refreshed');
  });

  // ── Re-render on language change ───────────────────────────────────────
  document.addEventListener('swachlens:lang', () => {
    updateStats();
    renderTasks();
    renderCompletedTasks();
  });

  // ── Auto-refresh ────────────────────────────────────────────────────────
  setInterval(loadTasks, 15000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') loadTasks();
  });

  // ── Init ────────────────────────────────────────────────────────────────
  loadTasks();
})();
