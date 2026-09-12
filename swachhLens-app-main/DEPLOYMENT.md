# SwachhLens — Deployment & Update Guide

## 🚀 Quick Start

### Local Development
```bash
# Start dev server (static frontend)
node dev-server.js
# → http://127.0.0.1:3000

# Start backend (if needed)
powershell .\launch-backend.ps1
```

### Test Before Deploying
```bash
python test-deployment.py
```

---

## 🔄 How to Update Your Web App

### Step 1: Make Changes
Edit your HTML, CSS, or JS files:
- `*.html` — Page structure and content
- `css/landing.css` — Main styles and design system
- `css/i18n.css` — Internationalization styles
- `css/info.css` — Info page styles
- `js/*.js` — Application logic

### Step 2: Test Locally
```bash
# Start the dev server
node dev-server.js

# Open in browser
# http://127.0.0.1:3000
```

### Step 3: Commit Changes
```bash
git add .
git commit -m "Description of your changes"
```

### Step 4: Deploy
```bash
# Push to deploy (Netlify auto-deploys on push)
git push origin main
```

---

## 📋 Deployment Options

### Option A: Git-Based (Recommended)
Netlify watches your Git repository and auto-deploys on push.

```bash
# Just push your changes
git push origin main
# Netlify builds and deploys automatically
```

### Option B: Manual Deploy via Netlify CLI
```bash
# Install Netlify CLI (one time)
npm install -g netlify-cli

# Deploy to production
netlify deploy --prod

# Deploy to staging
netlify deploy
```

### Option C: Drag & Drop
1. Go to [Netlify Dashboard](https://app.netlify.com)
2. Drag your project folder to the deploy area

---

## 🛡️ Pre-Deploy Checklist

- [ ] Test locally with `node dev-server.js`
- [ ] Check all pages load correctly
- [ ] Verify forms and interactive elements work
- [ ] Test on mobile/responsive view
- [ ] Run `python test-deployment.py`
- [ ] Back up database if making backend changes

## 🔐 Required environment variables (production)

The backend has **no hard-coded credentials** anymore — set these on the
host (Railway/Render/Netlify dashboard, or `backend/.env` locally):

```
JWT_SECRET=<long random string>   # generate: python -c "import secrets; print(secrets.token_hex(32))"
ADMIN_PASSWORD=<strong password>  # admin bootstrap password; re-apply on every restart
ADMIN_USER_ID=ADMIN               # optional, default ADMIN
ADMIN_NAME=Municipal Administrator # optional
DATABASE_URL=postgresql://...     # REQUIRED on ephemeral hosts (Railway wipes SQLite files)
```

Behavior:
- **JWT_SECRET unset** → a random secret is generated at startup and
  sessions are invalidated on every restart (safe, but annoying — set it).
- **ADMIN_PASSWORD unset** → the first start generates a strong random
  admin password and prints it to the server log (no leaked default).
- **ADMIN_PASSWORD set** → it is applied on **every** startup, so rotating
  the admin password is just "change the env var + restart".

⚠️ If your host uses an ephemeral filesystem (Railway default), SQLite data
is lost on redeploy — point `DATABASE_URL` at managed Postgres instead.

---

## 🔧 Backend Updates

If you have a separate backend server:

```bash
# 1. Stop current backend
# 2. Update backend files in /backend folder
# 3. Restart backend
powershell .\launch-backend.ps1

# 4. Update API URL in js/config.js if needed
# 5. Deploy frontend changes
git push origin main
```

---

## 📁 Project Structure

```
swachlens/
├── index.html              # Landing page
├── admin.html              # Admin dashboard
├── employee.html           # Employee dashboard
├── user.html               # Citizen dashboard
├── login.html              # Citizen login
├── admin-login.html        # Admin/Employee login
├── register.html           # Registration
├── forgot-password.html    # Password recovery
├── admin-task-emp.html     # Admin task management
├── about.html              # About page
├── blog.html               # Blog
├── contact.html            # Contact
├── faq.html                # FAQ
├── help.html               # Help desk
├── api-docs.html           # API documentation
├── terms.html              # Terms of service
├── privacy.html            # Privacy policy
├── css/
│   ├── landing.css         # Main design system
│   ├── i18n.css            # Internationalization
│   └── info.css            # Info page styles
├── js/
│   ├── lang.js             # Language support
│   ├── config.js           # Configuration
│   ├── api.js              # API client
│   ├── ui.js               # Shared UI helpers
│   ├── admin.js            # Admin dashboard logic
│   ├── employee.js         # Employee dashboard logic
│   ├── user.js             # Citizen dashboard logic
│   ├── auth.js             # Authentication
│   ├── login.js            # Login logic
│   ├── admin-login.js      # Admin login logic
│   ├── landing.js          # Landing page logic
│   ├── hero-type.js        # Hero typewriter effect
│   └── state.js            # State management
├── backend/                # Backend server (if separate)
├── dev-server.js           # Local dev server
├── swachlens.db            # SQLite database
├── netlify.toml            # Netlify config
├── test-deployment.py      # Deployment test
└── launch-backend.ps1      # Backend launcher (Windows)
```

---

## 🎨 Design System

### Color Tokens (css/landing.css)
```css
--bg-primary: #0a0f1a      /* Main background */
--bg-secondary: #111827    /* Secondary background */
--bg-card: #1a2234         /* Card background */
--green-500: #22c55e       /* Primary green */
--green-400: #4ade80       /* Light green */
--purple-500: #a855f7      /* Primary purple */
--purple-400: #c084fc      /* Light purple */
--text-primary: #ffffff    /* White text */
--text-secondary: #94a3b8  /* Gray text */
--text-muted: #64748b      /* Muted text */
```

### Adding New Pages
1. Create `new-page.html`
2. Copy structure from existing page (e.g., `about.html`)
3. Add to footer links in all pages
4. Test locally before deploying

---

## 🚆 Railway Redeployment Checklist (backend + PostgreSQL)

### 1. Service root = `backend/`
In Railway, open your backend service → **Settings → Service root** and set it
to `backend/`. Confirmed files already in place:

- `backend/run.py` — launcher (reads `PORT`, `HOST`, `RELOAD`)
- `backend/railway.toml` — build/deploy config:
  `startCommand = "python run.py"`, `healthcheckPath = "/health"`
- `backend/Procfile` — `web: python run.py` (fallback for other hosts)
- `backend/requirements.txt` — pinned deps (FastAPI, uvicorn, psycopg2)

### 2. Start command
Keep `python run.py` (already set in `railway.toml`). The healthcheck
`/health` endpoint is served by the app itself.

### 3. Environment variables (Railway → Variables)
| Variable | Value | Required? |
|---|---|---|
| `DATABASE_URL` | Connection string from the Railway **PostgreSQL plugin** (Settings → Variables → copy into `DATABASE_URL`) | ✅ |
| `JWT_SECRET` | Long random string — `python -c "import secrets; print(secrets.token_hex(32))"` | ✅ |
| `ADMIN_PASSWORD` | Your chosen admin bootstrap password | ✅ |
| `HOST` | `0.0.0.0` (already in `railway.toml`) | — |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | Only if you want OTP by SMS | Optional |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | Only if you want OTP by email | Optional |

`PORT` is provided automatically by Railway — do not set it manually.

### 4. Frontend API URL (Netlify)
`js/config.js` currently contains a **placeholder**:

```js
var PRODUCTION_API_URL = 'https://<NEW-RAILWAY-URL>.up.railway.app/api';
```

After your Railway service is live, replace `<NEW-RAILWAY-URL>` with the
actual URL (e.g. `https://your-app-name.up.railway.app`) and commit —
Netlify redeploys automatically. The frontend falls back to
`http://localhost:8000/api` when opened on localhost, so local dev is
unaffected.

---

## ✉️ Enabling real OTP delivery (forgot password)

The forgot-password flow generates a 6-digit OTP and verifies it, but by
default the code is **returned in the API response** (dev mode) because no
email/SMS provider is configured. To actually send the code to the user:

1. **Email (recommended):** set these env vars on the backend (copy
   `backend/.env.example` → `backend/.env` locally, or set them in your
   Railway/Netlify dashboard):

   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=you@gmail.com
   SMTP_PASS=<app password>
   ```

   Gmail tip: enable 2-Step Verification, then create an **App password**
   under Google Account → Security → App passwords — use it as `SMTP_PASS`.
   Any SMTP provider works (Outlook, Zoho, your own server).

2. **SMS (for phone numbers):** set Twilio credentials:

   ```
   TWILIO_ACCOUNT_SID=...
   TWILIO_AUTH_TOKEN=...
   TWILIO_FROM_NUMBER=+15017122661
   ```

3. Once a channel is configured and the send succeeds, the API stops
   returning `otp` in the response (safer) and the user receives the code
   by email/SMS. If the send fails or nothing is configured, the API logs a
   warning and falls back to dev mode so the flow still works locally.

---

## 🐛 Troubleshooting

### Page not loading
- Check browser console for errors
- Verify file paths in HTML are correct
- Ensure dev server is running

### Styles not updating
- Hard refresh: `Ctrl + Shift + R` (Windows) or `Cmd + Shift + R` (Mac)
- Clear browser cache
- Check CSS file is linked correctly in HTML

### Backend connection issues
- Verify backend is running: `powershell .\launch-backend.ps1`
- Check API URL in `js/config.js`
- Check CORS settings on backend

---

## 📞 Support

- **Documentation:** Check `README.md` and `api-docs.html`
- **FAQ:** Visit `faq.html` on your deployed site
- **Contact:** Use `contact.html` form

---

**Last Updated:** September 2026
**Version:** 1.0.0
