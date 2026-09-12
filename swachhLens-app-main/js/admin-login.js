/* =====================================================================
 * Admin / Employee login — matches citizen login design
 * ===================================================================== */
(function () {
  const SESSION_KEY = 'swachlens.admin_session';

  // Already signed in? Go to the right dashboard.
  const existing = getAdminSession();
  if (existing) {
    window.location.href = existing.role === 'admin' ? 'admin.html' : 'admin-task-emp.html';
    return;
  }

  function getAdminSession() {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; }
  }

  // ── Role switching ──────────────────────────────────────────────────────
  const selector = document.querySelector('[data-role-selector]');
  const roleBtns = selector ? Array.from(selector.querySelectorAll('[data-role]')) : [];
  const panels = document.querySelectorAll('[data-role-panel]');
  let currentRole = 'admin';

  function selectRole(role) {
    currentRole = role;
    roleBtns.forEach((b) => {
      const on = b.dataset.role === role;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    panels.forEach((panel) => {
      const on = panel.dataset.rolePanel === role;
      if (on) {
        panel.hidden = false;
        panel.classList.remove('in');
        void panel.offsetWidth;
        panel.classList.add('in');
      } else {
        panel.hidden = true;
      }
    });
  }

  roleBtns.forEach((b) =>
    b.addEventListener('click', () => selectRole(b.dataset.role))
  );

  // Keyboard support for the selector
  if (selector) {
    selector.addEventListener('keydown', (e) => {
      const idx = roleBtns.indexOf(document.activeElement);
      if (idx === -1 || !['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault();
      let next = idx;
      if (e.key === 'ArrowRight') next = (idx + 1) % roleBtns.length;
      if (e.key === 'ArrowLeft') next = (idx - 1 + roleBtns.length) % roleBtns.length;
      if (e.key === 'Home') next = 0;
      if (e.key === 'End') next = roleBtns.length - 1;
      roleBtns[next].focus();
      selectRole(roleBtns[next].dataset.role);
    });
  }

  // ── Auth helper ─────────────────────────────────────────────────────────
  async function doLogin(userId, password) {
    const { user, token } = await API.admin.login(userId, password);
    localStorage.setItem(SESSION_KEY, JSON.stringify({ ...user, authToken: token, issuedAt: Date.now() }));
    if (user.role === 'admin') {
      window.location.href = 'admin.html';
    } else {
      window.location.href = 'admin-task-emp.html';
    }
  }

  // ── Admin form ──────────────────────────────────────────────────────────
  const adminForm = document.getElementById('adminForm');
  const adminErr = document.getElementById('adminErr');
  const adminSubmit = document.getElementById('adminSubmit');

  function setAdminErr(msg) {
    adminErr.textContent = msg || '';
    adminErr.classList.toggle('show', !!msg);
  }

  adminForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    setAdminErr('');
    const userId = document.getElementById('adminIdInput').value.trim().toUpperCase();
    const password = document.getElementById('adminPassInput').value;
    if (!userId || !password) { setAdminErr(t('adm.errFill')); return; }
    adminSubmit.disabled = true;
    adminSubmit.classList.add('loading');
    try {
      const { user } = await API.admin.login(userId, password);
      if (user.role !== 'employee') {
        localStorage.setItem(SESSION_KEY, JSON.stringify({ ...user, authToken: (await API.admin.login(userId, password)).token, issuedAt: Date.now() }));
        window.location.href = 'admin.html';
      } else {
        setAdminErr(t('adm.errEmpTab'));
      }
    } catch (err) {
      setAdminErr(err.message || t('adm.errLogin'));
    } finally {
      adminSubmit.disabled = false;
      adminSubmit.classList.remove('loading');
    }
  });

  // ── Employee form ───────────────────────────────────────────────────────
  const empForm = document.getElementById('employeeForm');
  const empErr = document.getElementById('empErr');
  const empSubmit = document.getElementById('empSubmit');

  function setEmpErr(msg) {
    empErr.textContent = msg || '';
    empErr.classList.toggle('show', !!msg);
  }

  empForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    setEmpErr('');
    const userId = document.getElementById('empIdInput').value.trim().toUpperCase();
    const password = document.getElementById('empPassInput').value;
    if (!userId || !password) { setEmpErr(t('adm.errFill')); return; }
    empSubmit.disabled = true;
    empSubmit.classList.add('loading');
    try {
      const { user } = await API.admin.login(userId, password);
      if (user.role === 'employee') {
        const { token } = await API.admin.login(userId, password);
        localStorage.setItem(SESSION_KEY, JSON.stringify({ ...user, authToken: token, issuedAt: Date.now() }));
        window.location.href = 'admin-task-emp.html';
      } else {
        setEmpErr(t('adm.errAdminTab'));
      }
    } catch (err) {
      setEmpErr(err.message || t('adm.errLogin'));
    } finally {
      empSubmit.disabled = false;
      empSubmit.classList.remove('loading');
    }
  });

  // ── Init ────────────────────────────────────────────────────────────────
  selectRole('admin');
})();
