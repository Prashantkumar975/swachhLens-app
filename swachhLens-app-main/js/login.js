/* =====================================================================
 * SwachhLens — login page (nested role experience)
 * ---------------------------------------------------------------------
 * A progressive role flow: role selector → role deep-dive panel → a
 * contextual Login/Register form that inherits the selected role's
 * identity. Preserves the existing Auth API (Auth.login / Auth.register),
 * error handling and session redirection.
 * ===================================================================== */
(function () {
  // Already signed in? Go straight to your dashboard.
  const existing = Auth.session();
  if (existing) {
    nav((Auth.ROLE_META[existing.role] || Auth.ROLE_META.USER).path);
    return;
  }

  const ROLE_LABEL = { USER: 'Citizen', EMPLOYEE: 'Employee' };
  const ROLE_KEY = { USER: 'citizen', EMPLOYEE: 'employee' };
  // Which auth page are we on? login.html → "login", register.html → "register".
  const PAGE_MODE = document.body.dataset.authMode || 'login';

  const selector = document.querySelector('[data-role-selector]');
  const roleBtns = selector ? Array.from(selector.querySelectorAll('[data-role]')) : [];
  const panels = document.querySelectorAll('[data-role-panel]');
  let currentRole = 'USER';

  /* ---------------- Role switching (nested dive) ---------------- */
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
        panel.classList.remove('in'); // re-trigger panel-in animation
        void panel.offsetWidth;
        panel.classList.add('in');
      } else {
        panel.hidden = true;
      }
    });
    // Keep the hash in sync for deep-linking / back button.
    const want = '#' + ROLE_KEY[role];
    if (window.location.hash !== want && window.location.hash && window.location.hash !== '#choose') {
      try { history.replaceState(null, '', want); } catch { /* ignore */ }
    }
    // Update cross-page links so the role persists across navigation.
    updateRoleLinks(role);
  }

  roleBtns.forEach((b) =>
    b.addEventListener('click', () => selectRole(b.dataset.role))
  );

  /* Keyboard support for the selector (arrow keys behave like tabs). */
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

  /* ---------------- Per-panel auth forms ---------------- */
  panels.forEach((panel) => {
    const role = panel.dataset.rolePanel;
    const form = panel.querySelector('[data-form]');
    if (!form) return; // skip panels without a form (e.g. redirect panels)
    const seg = panel.querySelector('[data-seg]');
    const err = panel.querySelector('[data-err]');
    const submitBtn = panel.querySelector('[data-submit]');
    const submitLabel = panel.querySelector('[data-submit-label]');
    let mode = PAGE_MODE;

    function setErr(msg) {
      err.textContent = msg || '';
      err.classList.toggle('show', !!msg);
    }
    function setFieldErr(field, msg) {
      const el = form.querySelector('[data-field-err="' + field + '"]') || document.querySelector('[data-field-err="' + field + '"]');
      if (!el) { setErr(msg); return; }
      el.textContent = msg || '';
      el.hidden = !msg;
      const input = form.querySelector('[data-' + field + ']') || form.querySelector('[data-name]');
      if (input) input.classList.toggle('is-invalid', !!msg);
    }
    function clearAllFieldErrs() {
      form.querySelectorAll('[data-field-err]').forEach(e => { e.textContent = ''; e.hidden = true; });
      form.querySelectorAll('.is-invalid').forEach(e => e.classList.remove('is-invalid'));
    }

    function setMode(m) {
      mode = m;
      if (seg) seg.querySelectorAll('button').forEach((b) => {
        const on = b.dataset.mode === m;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      form.querySelectorAll('[data-name], [data-confirm-pass]').forEach((n) => (n.closest('.lv-field').style.display = m === 'register' ? '' : 'none'));
      const passInput = form.querySelector('[data-pass]');
      if (passInput) passInput.setAttribute('autocomplete', m === 'register' ? 'new-password' : 'current-password');
      const confirmInput = form.querySelector('[data-confirm-pass]');
      if (confirmInput) {
        confirmInput.value = '';
        confirmInput.setAttribute('aria-invalid', 'false');
        const ce = panel.querySelector('[data-confirm-err]');
        if (ce) ce.hidden = true;
      }
      submitLabel.textContent = m === 'register'
        ? t(role === 'USER' ? 'auth.regCit' : 'auth.regEmp')
        : t(role === 'USER' ? 'auth.logCit' : 'auth.logEmp');
      setErr('');
    }

    if (seg) seg.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
    setMode(PAGE_MODE); // initialize this page's fields, autocomplete + submit label

    // Password-confirmation check (frontend only — confirmPassword is never sent).
    // The message only appears AFTER the user has finished filling the confirm
    // field (blur / submit) — never mid-typing.
    const confirmInput = form.querySelector('[data-confirm-pass]');
    const confirmErr = panel.querySelector('[data-confirm-err]');
    function clearConfirmErr() {
      confirmInput.setAttribute('aria-invalid', 'false');
      confirmErr.hidden = true;
    }
    function showConfirmErr() {
      if (mode !== 'register' || !confirmInput.value) return;
      confirmInput.setAttribute('aria-invalid', 'true');
      confirmErr.hidden = false;
    }
    function validateConfirm() {
      const pass = form.querySelector('[data-pass]').value;
      if (confirmInput.value === pass || !confirmInput.value) clearConfirmErr();
    }
    if (confirmInput) {
      confirmInput.addEventListener('input', validateConfirm);
      confirmInput.addEventListener('blur', () => {
        const pass = form.querySelector('[data-pass]').value;
        if (confirmInput.value && confirmInput.value !== pass) showConfirmErr();
      });
      form.querySelector('[data-pass]').addEventListener('input', validateConfirm);
    }

    // ---- Phone-OTP registration step (register pages only) ----
    const otpSection = panel.querySelector('[data-otp-section]');
    let pendingPhone = '';

    function showOtpErr(msg) {
      const el = otpSection ? otpSection.querySelector('[data-otp-err]') : null;
      if (el) { el.textContent = msg || ''; el.hidden = !msg; }
    }

    if (otpSection) {
      const otpInput = otpSection.querySelector('[data-otp]');
      const otpVerifyBtn = otpSection.querySelector('[data-otp-verify]');
      const resendLink = otpSection.querySelector('[data-otp-resend]');
      const changeLink = otpSection.querySelector('[data-otp-change]');
      const switchLine = panel.querySelector('[data-switch-line]');

      function showOtpStep(res) {
        pendingPhone = res.phone || pendingPhone;
        form.hidden = true;
        if (switchLine) switchLine.hidden = true;
        otpSection.hidden = false;
        otpSection.classList.remove('in');
        void otpSection.offsetWidth;
        otpSection.classList.add('in');
        setErr('');
        if (otpInput) { otpInput.value = ''; otpInput.focus(); }
      }
      function showFormStep() {
        otpSection.hidden = true;
        form.hidden = false;
        if (switchLine) switchLine.hidden = false;
        const ph = form.querySelector('[data-phone]');
        if (ph) ph.focus();
      }

      otpVerifyBtn.addEventListener('click', async () => {
        const code = (otpInput ? otpInput.value : '').trim();
        if (!/^\d{6}$/.test(code)) { showOtpErr(t('fp.errOtp')); return; }
        showOtpErr('');
        otpVerifyBtn.disabled = true;
        otpVerifyBtn.classList.add('loading');
        try {
          const { user, token } = await API.auth.verifyRegisterOtp({ phone: pendingPhone, otp: code });
          const session = Auth._establish(user, token);
          toast(t('auth.welcomeBack', { name: session.name || session.phone }));
          setTimeout(() => nav(Auth.ROLE_META[role].path), 350);
        } catch (error) {
          const msg = (error.message || '').toLowerCase();
          showOtpErr(/otp|code|expired|invalid/.test(msg)
            ? (t('auth.otpNoMatch') || 'The OTP does not match. Please check the code and try again.')
            : (error.message || t('fp.invalidOtp')));
          if (otpInput) { otpInput.value = ''; otpInput.focus(); }
          otpVerifyBtn.disabled = false;
          otpVerifyBtn.classList.remove('loading');
        }
      });

      if (otpInput) otpInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); otpVerifyBtn.click(); }
      });

      resendLink.addEventListener('click', async (e) => {
        e.preventDefault();
        resendLink.disabled = true;
        try {
          await API.auth.resendRegisterOtp({ phone: pendingPhone });
          toast(t('fp.otpSent'));
        } catch (error) {
          showOtpErr(error.message || t('fp.invalidOtp'));
        }
        resendLink.disabled = false;
      });

      changeLink.addEventListener('click', (e) => {
        e.preventDefault();
        showFormStep();
      });
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      setErr('');
      const email = form.querySelector('[data-email]').value.trim();
      const password = form.querySelector('[data-pass]').value;
      const name = (form.querySelector('[data-name]')?.value || '').trim();
      const rawPhone = (form.querySelector('[data-phone]')?.value || '').replace(/\D/g, '');
      const phone = rawPhone ? '+91' + rawPhone : '';

      clearAllFieldErrs();
      if (mode === 'login') {
        if (!email) { setFieldErr('email', t('auth.errEmailRequired') || 'Please enter your email or username.'); return; }
        if (!password) { setFieldErr('pass', t('auth.errPassRequired') || 'Please enter your password.'); return; }
      } else {
        if (!name) { setFieldErr('name', t('auth.errNameRequired') || 'Please enter your full name.'); return; }
        if (!phone && !email) { setFieldErr('phone', t('auth.errPhoneEmailRequired') || 'Please provide a phone number or email.'); return; }
        if (phone && phone.replace(/\D/g, '').length !== 12) { setFieldErr('phone', t('auth.errPhoneLen') || 'Please enter a valid 10-digit phone number.'); return; }
        if (!password) { setFieldErr('pass', t('auth.errPassRequired') || 'Please enter a password.'); return; }
        if (password.length < 6) { setFieldErr('pass', t('auth.errPassLen')); return; }
        if (confirmInput && confirmInput.value !== password) {
          confirmInput.setAttribute('aria-invalid', 'true');
          confirmErr.hidden = false;
          confirmErr.textContent = t('auth.errMatch');
          confirmInput.focus();
          return;
        }
      }

      submitBtn.disabled = true;
      submitBtn.classList.add('loading');
      try {
        if (mode === 'login') {
          const session = await Auth.login(email, password, role);
          toast(t('auth.welcomeBack', { name: session.name || session.email }));
          setTimeout(() => nav(Auth.ROLE_META[role].path), 350);
        } else if (otpSection && role === 'USER') {
          const res = await API.auth.registerOtp({ email, password, name, phone, role });
          showOtpStep(res);
        } else {
          const session = await Auth.register({ email, password, name, phone }, role);
          toast(t('auth.welcomeBack', { name: session.name || session.email }));
          setTimeout(() => nav(Auth.ROLE_META[role].path), 350);
        }
      } catch (error) {
        setErr(error.message || t('auth.errGeneric'));
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
      }
    });
  });

  /* ---- Cross-page role links: update all data-role-link hrefs ---- */
  function updateRoleLinks(role) {
    const key = ROLE_KEY[role] || 'citizen';
    document.querySelectorAll('[data-role-link]').forEach((a) => {
      const page = a.dataset.roleLink;                     // "register" or "login"
      const target = a.href.replace(/\?.*$/, '');           // strip any existing query
      a.href = target + '?role=' + key;
    });
  }

  /* ---- URL-init: respect ?role=employee or #employee on first load ---- */
  const hashRoleMap = { citizen: 'USER', employee: 'EMPLOYEE' };
  const qs = new URLSearchParams(window.location.search);
  const qsRole  = hashRoleMap[(qs.get('role') || '').toLowerCase()];
  const hashRole = hashRoleMap[(window.location.hash || '').replace('#', '').toLowerCase()];
  const initialRole = qsRole || hashRole || 'USER';

  selectRole(initialRole);

  // Clean the query string so reloads don't re-trigger the switch.
  if (qsRole) {
    try { history.replaceState(null, '', window.location.pathname + (window.location.hash || '')); } catch { /* ignore */ }
  }
})();
