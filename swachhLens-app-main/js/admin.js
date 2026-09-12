/* =====================================================================
 * Admin Dashboard — citizen-style layout
 * ===================================================================== */
(function () {
  const SESSION_KEY = 'swachlens.admin_session';
  const BASE = window.SW_CONFIG.API_URL;

  function getSession() {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
  }
  function getToken() { const s = getSession(); return s ? s.authToken : null; }

  const session = getSession();
  if (!session || session.role !== 'admin') {
    window.location.href = 'admin-login.html';
    return;
  }

  // ── DOM refs ────────────────────────────────────────────────────────────
  const $name = document.getElementById('userName');
  const $id = document.getElementById('userId');
  const $avatar = document.getElementById('userAvatar');
  const $greetName = document.getElementById('greetName');
  const $awaitingList = document.getElementById('awaitingList');
  const $assignedList = document.getElementById('assignedList');
  const $inProgressList = document.getElementById('inProgressList');
  const $taskList = document.getElementById('taskList');
  const $sectionIncoming = document.getElementById('incomingReports');
  const $sectionTasks = document.getElementById('taskSection');
  const $tabIncoming = document.getElementById('tabIncoming');
  const $tabTasks = document.getElementById('tabTasks');
  const $statReports = document.getElementById('statReports');
  const $statAssigned = document.getElementById('statAssigned');
  const $statInProgress = document.getElementById('statInProgress');
  const $statResolved = document.getElementById('statResolved');
  const $countAwaiting = document.getElementById('countAwaiting');
  const $countAssigned = document.getElementById('countAssigned');
  const $countInProgress = document.getElementById('countInProgress');
  const $countVerify = document.getElementById('countVerify');
  const $verifyList = document.getElementById('verifyList');
  const $statVerify = document.getElementById('statVerify');

  const initials = (session.name || 'A').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  $name.textContent = session.name;
  $id.textContent = session.userId;
  $avatar.textContent = initials;
  $greetName.textContent = session.name.split(' ')[0];

  // ── Auth fetch ──────────────────────────────────────────────────────────
  function authFetch(method, path, body) {
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
    reports: {
      list: () => authFetch('GET', '/admin/reports'),
      assign: (id, data) => authFetch('PATCH', '/admin/reports/' + encodeURIComponent(id) + '/assign', data),
      verify: (id, data) => authFetch('PATCH', '/admin/reports/' + encodeURIComponent(id) + '/verify', data),
    },
    tasks: {
      list: () => authFetch('GET', '/admin/tasks'),
      create: (data) => authFetch('POST', '/admin/tasks', data),
      remove: (id) => authFetch('DELETE', '/admin/tasks/' + encodeURIComponent(id)),
      assign: (id, data) => authFetch('PATCH', '/admin/tasks/' + encodeURIComponent(id) + '/assign', data),
    },
    employees: () => authFetch('GET', '/admin/employees'),
  };

  // ── State ───────────────────────────────────────────────────────────────
  let reports = [];
  let tasks = [];
  let employees = [];
  let activeTab = 'incoming';
  const INITIAL_VISIBLE = 3;
  let awaitingVisible = INITIAL_VISIBLE;
  let assignedVisible = INITIAL_VISIBLE;
  let inProgressVisible = INITIAL_VISIBLE;

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

  const WASTE_ICONS = { 'Plastic': '🧴', 'Organic': '🥗', 'E-Waste': '🔌', 'Hazardous': '☣️' };

  function showToast(msg, isErr) {
    const existing = document.querySelector('.toast.show');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.className = 'toast show' + (isErr ? ' toast--err' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
  }

  // ── Load data ───────────────────────────────────────────────────────────
  async function loadAll() {
    try {
      const [reportsData, tasksData, employeesData] = await Promise.all([
        api.reports.list(),
        api.tasks.list(),
        api.employees(),
      ]);
      reports = reportsData.reports || [];
      tasks = tasksData.tasks || [];
      employees = employeesData.employees || [];
      updateStats();
      renderReports();
      renderTasks();
      populateEmployeeDropdown();
    } catch (err) {
      console.error('Load failed:', err);
    }
  }

  // ── Stats ───────────────────────────────────────────────────────────────
  function updateStats() {
    const incoming = reports.filter(r => r.status === 'PENDING').length;
    const assigned = reports.filter(r => r.status === 'ASSIGNED').length + tasks.filter(t => t.status === 'pending').length;
    const inProg = reports.filter(r => r.status === 'IN_PROGRESS').length + tasks.filter(t => t.status === 'accepted').length;
    const verify = reports.filter(r => r.status === 'VERIFY').length;
    const resolved = reports.filter(r => r.status === 'RESOLVED').length + tasks.filter(t => t.status === 'rejected').length;

    $statReports.textContent = incoming;
    $statAssigned.textContent = assigned;
    $statInProgress.textContent = inProg;
    $statVerify.textContent = verify;
    $statResolved.textContent = resolved;
    $tabIncoming.textContent = incoming;
    $tabTasks.textContent = tasks.length;
  }

  // ── Render citizen reports ──────────────────────────────────────────────
  const PROGRESS = { 'Pending': 0, 'In Progress': 50, 'Verification': 75, 'Resolved': 100 };
  const BAR_COLOR = { 'Pending': '#f59e0b', 'In Progress': '#3b82f6', 'Verification': '#8b5cf6', 'Resolved': '#22c55e' };

  function badgeForAdmin(r) {
    const map = {
      PENDING: 'st-pending', ASSIGNED: 'st-pending', IN_PROGRESS: 'st-progress',
      VERIFY: 'st-verify', RESOLVED: 'st-resolved', CANCELLED: 'st-cancelled'
    };
    const labelMap = {
      PENDING: 'st.pending', ASSIGNED: 'st.assigned', IN_PROGRESS: 'st.inProgress',
      VERIFY: 'st.verification', RESOLVED: 'st.resolved', CANCELLED: 'st.cancelled'
    };
    const cls = map[r.status] || 'st-pending';
    const label = labelMap[r.status] ? (window.t ? t(labelMap[r.status]) : labelMap[r.status]) : r.status;
    return `<span class="status-badge ${cls}">${label}</span>`;
  }

  function renderReports() {
    const pending = reports.filter(r => r.status === 'PENDING');
    const assigned = reports.filter(r => r.status === 'ASSIGNED');
    const inProg = reports.filter(r => r.status === 'IN_PROGRESS');
    const verify = reports.filter(r => r.status === 'VERIFY');

    // Update section counts
    if ($countAwaiting) $countAwaiting.textContent = pending.length;
    if ($countAssigned) $countAssigned.textContent = assigned.length;
    if ($countInProgress) $countInProgress.textContent = inProg.length;
    if ($countVerify) $countVerify.textContent = verify.length;

    // Show/hide sections based on content
    const $secAwaiting = document.getElementById('sectionAwaiting');
    const $secAssigned = document.getElementById('sectionAssigned');
    const $secInProgress = document.getElementById('sectionInProgress');
    const $secVerify = document.getElementById('sectionVerify');
    if ($secAwaiting) $secAwaiting.hidden = !pending.length;
    if ($secAssigned) $secAssigned.hidden = !assigned.length;
    if ($secInProgress) $secInProgress.hidden = !inProg.length;
    if ($secVerify) $secVerify.hidden = !verify.length;

    function renderCard(r, i) {
      const icon = WASTE_ICONS[r.wasteType] || '🗑️';
      const assignee = employees.find(e => e.userId === r.assignedTo);
      const assigneeName = assignee ? assignee.name : (r.assignedTo || '');
      const canAssign = r.status === 'PENDING';
      const stKey = r.status === 'ASSIGNED' ? 'Pending' : r.status === 'IN_PROGRESS' ? 'In Progress' : r.status === 'VERIFY' ? 'Verification' : r.status.charAt(0) + r.status.slice(1).toLowerCase();
      const pct = PROGRESS[stKey] ?? 0;
      const barCol = BAR_COLOR[stKey] ?? '#f59e0b';

      return `
      <article class="report-card admin-card reveal in" style="animation-delay:${Math.min(i * 60, 360)}ms" data-id="${r.id}">
        <div class="rc-body">
          <div class="rc-top">
            <h4>${icon} ${esc(r.wasteType)} waste report</h4>
            ${badgeForAdmin(r)}
          </div>
          <div class="rc-meta">📍 ${esc(r.location)}</div>
          ${r.description ? '<div class="rc-meta" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + esc(r.description) + '</div>' : ''}
          <div class="rc-progress"><i style="width:${pct}%;background:${barCol};"></i></div>
          <div class="rc-foot">
            <span class="rc-tag"><span class="rc-ico">👤</span> ${esc((r.reporterName || r.reporter || '').length > 10 ? (r.reporterName || r.reporter).slice(0, 10) + '…' : (r.reporterName || r.reporter))}</span>
            <span class="rc-tag"><span class="rc-ico">⚠️</span> ${esc(r.severity || 'Medium')}</span>
            <span class="rc-tag" style="font-variant-numeric:tabular-nums;"><span class="rc-ico">🏷️</span> ${r.id}</span>
            <span class="rc-tag"><span class="rc-ico">⏱️</span> ${timeAgo(r.createdAt)}</span>
          </div>
          ${canAssign ? `
          <div class="rc-assign-row">
            <select class="adm-assign-select" data-emp-select>
              <option value="">👷 Assign to employee…</option>
              ${employees.map(e => '<option value="' + e.userId + '">' + esc(e.name) + ' (' + e.userId + ') — ' + e.workload + ' task' + (e.workload !== 1 ? 's' : '') + '</option>').join('')}
            </select>
            <button class="rc-btn" style="font-weight:800;color:var(--green-700);border-color:var(--green-400);" data-action="assign">Assign</button>
          </div>` : r.status === 'VERIFY' ? `
          <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;">
            <div style="font-size:12px;font-weight:700;color:#8b5cf6;margin-bottom:8px;">📸 Employee submitted proof — compare with original</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
              <div><div style="font-size:10px;font-weight:700;color:var(--muted);margin-bottom:4px;">BEFORE (original)</div>${r.photo ? '<img src="' + esc(r.photo) + '" style="width:100%;height:120px;object-fit:cover;border-radius:10px;">' : '<div style="height:120px;background:var(--line);border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:12px;">No photo</div>'}</div>
              <div><div style="font-size:10px;font-weight:700;color:#8b5cf6;margin-bottom:4px;">AFTER (proof)</div>${r.proofPhoto ? '<img src="' + esc(r.proofPhoto) + '" style="width:100%;height:120px;object-fit:cover;border-radius:10px;">' : '<div style="height:120px;background:var(--line);border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:12px;">No proof</div>'}</div>
            </div>
            <div class="rc-assign-row">
              <button class="rc-btn" style="font-weight:800;color:var(--green-700);border-color:var(--green-400);flex:1;" data-action="verify-approve">✅ Approve</button>
              <button class="rc-btn rc-btn--cancel" style="font-weight:800;flex:1;" data-action="verify-reject">↩️ Send Back</button>
            </div>
          </div>` : `
          <div class="rc-assign-row">
            <span class="rc-tag" style="flex:1;">👷 ${assigneeName ? 'Assigned to ' + esc(assigneeName) : 'No assignment yet'}</span>
            <select class="adm-assign-select" data-reassign-select>
              <option value="">🔄 Reassign…</option>
              ${employees.map(e => '<option value="' + e.userId + '">' + esc(e.name) + ' (' + e.userId + ') — ' + e.workload + ' task' + (e.workload !== 1 ? 's' : '') + '</option>').join('')}
            </select>
          </div>`}
        </div>
      </article>`;
    }

    // Render into separate sections with show-more
    function renderSection(listEl, items, type) {
      if (!listEl) return;
      if (!items.length) {
        const msgs = { awaiting: ['✅', 'All caught up', 'No reports waiting for assignment'], assigned: ['📭', 'No assigned reports', ''], inProgress: ['📭', 'No reports in progress', ''], verify: ['📸', 'No reports awaiting verification', 'Completed reports will appear here'] };
        const [ico, title, sub] = msgs[type];
        listEl.innerHTML = `<div class="empty-state"><span class="empty-state__icon">${ico}</span><b>${title}</b>${sub ? '<p style="font-size:14px;color:var(--muted);">' + sub + '</p>' : ''}</div>`;
        return;
      }
      const visible = type === 'awaiting' ? awaitingVisible : type === 'assigned' ? assignedVisible : inProgressVisible;
      const shown = items.slice(0, visible);
      const hasMore = items.length > visible;
      let html = shown.map((r, i) => renderCard(r, i)).join('');
      if (hasMore) {
        const remaining = items.length - visible;
        html += `<div class="reports-more"><button class="rc-btn show-more-btn" data-more="${type}" style="padding:12px 28px;font-weight:800;">Show more (${remaining} remaining)</button></div>`;
      }
      listEl.innerHTML = html;
      // Bind show-more buttons
      listEl.querySelectorAll('.show-more-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const t = btn.dataset.more;
          if (t === 'awaiting') awaitingVisible += INITIAL_VISIBLE;
          else if (t === 'assigned') assignedVisible += INITIAL_VISIBLE;
          else inProgressVisible += INITIAL_VISIBLE;
          renderReports();
        });
      });
    }
    renderSection($awaitingList, pending, 'awaiting');
    renderSection($assignedList, assigned, 'assigned');
    renderSection($inProgressList, inProg, 'inProgress');
    renderSection($verifyList, verify, 'verify');

    // Bind all assign buttons
    document.querySelectorAll('[data-action="assign"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        const select = card.querySelector('[data-emp-select]');
        const empId = select.value;
        if (!empId) { showToast('Please select an employee', true); return; }
        btn.disabled = true;
        try {
          await api.reports.assign(id, { assignedTo: empId });
          showToast('✓ Report assigned!');
          await loadAll();
        } catch (err) {
          btn.disabled = false;
          showToast(err.message, true);
        }
      });
    });

    // Bind all reassign dropdowns
    document.querySelectorAll('[data-reassign-select]').forEach(sel => {
      sel.addEventListener('change', async () => {
        const card = sel.closest('.report-card');
        const id = card.dataset.id;
        const empId = sel.value;
        if (!empId) return;
        try {
          await api.reports.assign(id, { assignedTo: empId });
          showToast('✓ Reassigned!');
          await loadAll();
        } catch (err) { showToast(err.message, true); }
        sel.value = '';
      });
    });

    // Bind verify approve/reject
    document.querySelectorAll('[data-action="verify-approve"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        btn.disabled = true;
        btn.textContent = 'Approving...';
        try {
          await api.reports.verify(id, { approved: true });
          showToast('✓ Report verified and resolved!');
          await loadAll();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '✅ Approve';
          showToast(err.message, true);
        }
      });
    });

    document.querySelectorAll('[data-action="verify-reject"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const card = btn.closest('.report-card');
        const id = card.dataset.id;
        if (!confirm('Send back to employee? The proof photo will be removed.')) return;
        btn.disabled = true;
        btn.textContent = 'Sending back...';
        try {
          await api.reports.verify(id, { approved: false });
          showToast('↩️ Sent back to employee');
          await loadAll();
        } catch (err) {
          btn.disabled = false;
          btn.textContent = '↩️ Send Back';
          showToast(err.message, true);
        }
      });
    });
  }

  // ── Render admin tasks ──────────────────────────────────────────────────
  let tasksVisible = INITIAL_VISIBLE;
  function renderTasks() {
    if (!tasks.length) {
      $taskList.innerHTML = `
        <div class="empty-state">
          <span class="empty-state__icon">📭</span>
          <b>No tasks yet</b>
          <p style="font-size:14px;color:var(--muted);">Create one above</p>
        </div>`;
      return;
    }
    const shownTasks = tasks.slice(0, tasksVisible);
    const hasMoreTasks = tasks.length > tasksVisible;

    $taskList.innerHTML = shownTasks.map((t, i) => {
      const assignee = employees.find(e => e.userId === t.assignedTo);
      const assigneeName = assignee ? assignee.name : (t.assignedTo || 'Unassigned');
      const taskBadge = t.status === 'accepted' ? 'st-resolved' : t.status === 'rejected' ? 'st-cancelled' : 'st-pending';
      return `
      <article class="report-card admin-card reveal in" style="animation-delay:${Math.min(i * 60, 360)}ms" data-id="${t.id}">
        <div class="rc-body">
          <div class="rc-top">
            <h4>${esc(t.title)}</h4>
            <span class="status-badge ${taskBadge}">${t.status}</span>
          </div>
          ${t.description ? '<div class="rc-meta" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + esc(t.description) + '</div>' : ''}
          <div class="rc-progress"><i style="width:${t.status === 'accepted' ? 100 : t.status === 'rejected' ? 0 : 20}%;background:${t.status === 'accepted' ? '#22c55e' : t.status === 'rejected' ? '#ef4444' : '#f59e0b'};"></i></div>
          <div class="rc-foot">
            <span class="rc-tag">👷 ${esc(assigneeName)}</span>
            <span class="rc-tag">🛠️ ${esc(t.createdBy)}</span>
            <span class="rc-tag" style="font-variant-numeric:tabular-nums;">${timeAgo(t.createdAt)}</span>
          </div>
          <div class="rc-assign-row">
            <select class="adm-assign-select" data-reassign-select>
              <option value="">🔄 Reassign…</option>
              ${employees.map(e => '<option value="' + e.userId + '">' + esc(e.name) + ' (' + e.userId + ') — ' + e.workload + ' task' + (e.workload !== 1 ? 's' : '') + '</option>').join('')}
            </select>
            <button class="rc-btn rc-btn--delete" type="button" data-action="delete">Delete</button>
          </div>
        </div>
      </article>`;
    }).join('');
    if (hasMoreTasks) {
      $taskList.innerHTML += `<div class="reports-more"><button class="rc-btn show-more-btn" data-more="tasks" style="padding:12px 28px;font-weight:800;">Show more (${tasks.length - tasksVisible} remaining)</button></div>`;
      $taskList.querySelectorAll('.show-more-btn').forEach(btn => {
        btn.addEventListener('click', () => { tasksVisible += INITIAL_VISIBLE; renderTasks(); });
      });
    }

    $taskList.querySelectorAll('[data-action="delete"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.closest('.report-card').dataset.id;
        if (!confirm('Delete this task?')) return;
        try {
          await api.tasks.remove(id);
          showToast('Task deleted');
          await loadAll();
        } catch (err) { showToast(err.message, true); }
      });
    });

    $taskList.querySelectorAll('[data-reassign-select]').forEach(sel => {
      sel.addEventListener('change', async () => {
        const card = sel.closest('.report-card');
        const id = card.dataset.id;
        const empId = sel.value;
        if (!empId) return;
        try {
          await api.tasks.assign(id, { assignedTo: empId });
          showToast('✓ Task reassigned!');
          await loadAll();
        } catch (err) { showToast(err.message, true); }
        sel.value = '';
      });
    });
  }

  // ── Populate employee dropdown ──────────────────────────────────────────
  function populateEmployeeDropdown() {
    const sel = document.getElementById('taskAssign');
    sel.innerHTML = '<option value="">' + esc(window.t ? t('admin.taskAssignPh') : '— Select Employee —') + '</option>';
    employees.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.userId;
      opt.textContent = e.name + ' (' + e.userId + ')';
      sel.appendChild(opt);
    });
  }

  // ── Create task form ────────────────────────────────────────────────────
  document.getElementById('createForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const title = document.getElementById('taskTitle').value.trim();
    const description = document.getElementById('taskDesc').value.trim();
    const assignedTo = document.getElementById('taskAssign').value || undefined;
    if (!title) { showToast('Please enter a task title', true); return; }
    try {
      await api.tasks.create({ title, description, assignedTo });
      document.getElementById('createForm').reset();
      showToast('✓ Task created!');
      await loadAll();
    } catch (err) { showToast(err.message, true); }
  });

  // ── Tab switching ───────────────────────────────────────────────────────
  document.querySelectorAll('.pill[data-tab]').forEach(tab => {
    tab.addEventListener('click', () => {
      activeTab = tab.dataset.tab;
      document.querySelectorAll('.pill[data-tab]').forEach(t => t.classList.toggle('active', t === tab));
      $sectionIncoming.hidden = activeTab !== 'incoming';
      $sectionTasks.hidden = activeTab !== 'tasks';
    });
  });

  // ── Logout ──────────────────────────────────────────────────────────────
  document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem(SESSION_KEY);
    window.location.href = 'admin-login.html';
  });



  document.getElementById('refreshBtn').addEventListener('click', async () => {
    await loadAll();
    showToast('Refreshed');
  });

  // ── Register Employee form ──────────────────────────────────────────
  document.getElementById('empRegForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const userId = document.getElementById('empUserId').value.trim();
    const name = document.getElementById('empName').value.trim();
    const phone = document.getElementById('empPhone').value.trim();
    const password = document.getElementById('empPassword').value;
    if (!userId || !phone || !password) { showToast('Please fill all required fields', true); return; }
    if (password.length < 6) { showToast('Password must be at least 6 characters', true); return; }
    try {
      const token = getToken();
      const res = await fetch(BASE + '/admin/register-employee', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
        body: JSON.stringify({ userId, name, phone, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed');
      document.getElementById('empRegForm').reset();
      showToast('✓ Employee ' + userId + ' registered! They can now log in.');
    } catch (err) { showToast(err.message, true); }
  });

  // ── Auto-refresh ────────────────────────────────────────────────────────
  setInterval(loadAll, 15000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') loadAll();
  });

  // ── Re-render on language change ───────────────────────────────────────
  document.addEventListener('swachlens:lang', () => {
    updateStats();
    renderReports();
    renderTasks();
    populateEmployeeDropdown();
  });

  // ── Init ────────────────────────────────────────────────────────────────
  loadAll();
})();
