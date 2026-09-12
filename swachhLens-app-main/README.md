# 🌿 SwachhLens — Smart Waste Management Platform

> A citizen-first waste management platform for Indian municipalities. Report waste with a photo, dispatch the right crew via AI, verify each cleanup — one civic loop, from citizen to every street.

---

## 📸 Features

### For Citizens
- 📷 **Photo-based waste reporting** — snap a photo and AI auto-detects waste type & severity
- 🗺️ **Location tracking** — pinpoint waste location on map
- 📊 **Report tracking** — monitor status from submitted to resolved
- 🔔 **OTP verification** — secure phone-based registration & login
- 🌐 **29 Indian languages** — Hindi, Bengali, Tamil, Telugu, and more

### For Employees (Cleaning Crew)
- 📋 **Task management** — view, accept, reject assigned tasks
- 📸 **Proof of work** — upload completion photos
- 📱 **Mobile-friendly** — works on any device

### For Admin (Municipal Corporation)
- 📊 **Dashboard** — real-time stats on reports, tasks, and workforce
- 👥 **Employee management** — register crew members with phone-based accounts
- ✅ **Report verification** — approve or reject completed work
- 🗺️ **GIS integration** — view waste hotspots on map
- 🤖 **AI-powered analysis** — automatic waste classification

---

## 🏗️ Project Structure

```
swachhLens-app/
├── index.html                  # Landing page
├── login.html                  # Citizen login
├── register.html               # Citizen registration (OTP-based)
├── admin-login.html            # Admin & Employee login
├── admin.html                  # Admin dashboard
├── employee.html               # Employee dashboard
├── user.html                   # Citizen dashboard
├── forgot-password.html        # Password recovery (email/phone OTP)
│
├── css/
│   ├── landing.css             # Main design system & all styles
│   ├── i18n.css                # Internationalization styles
│   └── info.css                # Info page styles (about, blog, etc.)
│
├── js/
│   ├── config.js               # API URL configuration
│   ├── api.js                  # REST API client
│   ├── auth.js                 # Authentication logic
│   ├── login.js                # Citizen login/register logic
│   ├── admin-login.js          # Admin/Employee login logic
│   ├── admin.js                # Admin dashboard logic
│   ├── employee.js             # Employee dashboard logic
│   ├── user.js                 # Citizen dashboard logic
│   ├── lang.js                 # 29-language i18n support
│   ├── landing.js              # Landing page interactions
│   ├── hero-type.js            # Hero typewriter effect
│   ├── ui.js                   # Shared UI helpers
│   └── state.js                # Client-side state management
│
├── backend/
│   ├── run.py                  # Backend launcher
│   ├── Procfile                # Railway deployment config
│   ├── railway.toml            # Railway build/deploy config
│   ├── requirements.txt        # Python dependencies
│   └── app/
│       ├── main.py             # FastAPI application
│       ├── config.py           # Environment configuration
│       ├── database.py         # SQLite/PostgreSQL database layer
│       ├── security.py         # Password hashing & JWT tokens
│       ├── models.py           # Pydantic request/response models
│       ├── analyzer.py         # AI waste analysis bridge
│       ├── notify.py           # OTP delivery (Email/SMS)
│       ├── dependencies.py     # Auth middleware
│       ├── constants.py        # App constants
│       └── routes/
│           ├── auth.py         # Register, login, OTP, forgot password
│           ├── reports.py      # Citizen report CRUD
│           ├── admin_tasks.py  # Admin & employee task management
│           ├── analyze.py      # AI waste analysis endpoint
│           ├── community.py    # Community initiatives
│           ├── gis.py          # GIS/map data
│           ├── stats.py        # Dashboard statistics
│           └── constants.py    # Waste types, severity levels
│
├── ai/
│   ├── models/                 # Trained AI models
│   │   ├── waste_types_best.pt
│   │   └── waste_gate_v2_best.pth
│   └── inference/
│       └── analyze_image.py    # Real-time inference
│
├── netlify.toml                # Netlify deployment config
├── dev-server.js               # Local development server
├── DEPLOYMENT.md               # Detailed deployment guide
└── .gitignore                  # Git ignore rules
```

---

## 🚀 Quick Start

### Prerequisites
- [Node.js](https://nodejs.org/) (for frontend dev server)
- [Python 3.10+](https://python.org/) (for backend)

### Frontend (Local Development)

```bash
# Start the dev server
node dev-server.js

# Open in browser
# http://127.0.0.1:3000
```

### Backend (Local Development)

```bash
# Navigate to backend folder
cd backend

# Install dependencies
pip install -r requirements.txt

# Start the server
python run.py

# API docs available at
# http://127.0.0.1:8000/docs
```

### Full Stack (Both Together)

```bash
# Terminal 1 - Backend
cd backend
python run.py

# Terminal 2 - Frontend
node dev-server.js
```

---

## 🌐 Deployment

### Frontend → Netlify

1. Push code to GitHub
2. Go to [app.netlify.com](https://app.netlify.com)
3. **Add new site** → **Import from GitHub**
4. Select your repo
5. Build command: *(leave empty)*
6. Publish directory: `.`
7. Click **Deploy site**

### Backend → Railway

1. Go to [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub Repo**
3. Set service root to `backend`
4. Add environment variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (add Railway PostgreSQL plugin) |
| `JWT_SECRET` | Random secret for JWT tokens |
| `ADMIN_USER_ID` | Admin login ID (default: `ADMIN`) |
| `ADMIN_PASSWORD` | Admin login password |
| `FRONTEND_ORIGINS` | Your Netlify URL (e.g., `https://swachhlenss-app.netlify.app`) |

### Connect Frontend to Backend

Update `js/config.js` with your Railway URL:

```javascript
var PRODUCTION_API_URL = 'https://your-railway-url.up.railway.app/api';
```

---

## 🔐 Default Credentials

### Admin Login
- **Admin ID:** `ADMIN` (or set via `ADMIN_USER_ID` env var)
- **Password:** Set via `ADMIN_PASSWORD` env variable

### Employee Login
Employees are registered by the admin through the Admin Dashboard.

---

## 🌍 Supported Languages

SwachhLens supports **29 Indian languages**:

English, हिन्दी, বাংলা, தமிழ், తెలుగు, मराठी, ಕನ್ನಡ, മലയാളം, ਪੰਜਾਬી, ગુજરાતી, اردو, অসমীয়ा, मैथिली, नेपाली, संस्कृत, डोगरी, कोंकणी, सिंधी, मणिपुरी, बोडो, कश्मीरी, तिब्बती, मिज़ो, रोइंग, हो, तुर्की, मैतिली, and more.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Backend** | Python, FastAPI, Uvicorn |
| **Database** | SQLite (local) / PostgreSQL (production) |
| **Auth** | JWT tokens, scrypt password hashing |
| **AI** | PyTorch, YOLO (optional), fallback demo classifier |
| **Hosting** | Netlify (frontend), Railway (backend) |
| **Languages** | 29 Indian languages via i18n system |

---

## 📝 API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register citizen account |
| POST | `/api/auth/register-otp` | Phone-verified registration |
| POST | `/api/auth/verify-register-otp` | Verify registration OTP |
| POST | `/api/auth/login` | Login (email/phone/username) |
| POST | `/api/auth/forgot-password` | Send password reset OTP |
| POST | `/api/auth/verify-otp` | Verify reset OTP |
| POST | `/api/auth/reset-password` | Set new password |

### Admin & Employee
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/login` | Admin/Employee login |
| GET | `/api/admin/tasks` | List tasks |
| POST | `/api/admin/tasks` | Create task (admin) |
| PATCH | `/api/admin/tasks/:id/assign` | Assign task (admin) |
| PATCH | `/api/admin/tasks/:id/accept` | Accept task (employee) |
| POST | `/api/admin/register-employee` | Register employee (admin) |
| GET | `/api/admin/reports` | List citizen reports |
| POST | `/api/admin/forgot-password` | Employee password reset |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports` | List all reports |
| POST | `/api/reports` | Create new report |
| PATCH | `/api/reports/:id/assign` | Assign to employee |
| PATCH | `/api/reports/:id/complete` | Mark as completed |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Could not reach server" | Check `js/config.js` has correct Railway URL |
| Login fails | Verify `ADMIN_PASSWORD` env var in Railway |
| 502 error | Check Railway logs for Python errors |
| CORS error | Add Netlify URL to `FRONTEND_ORIGINS` env var |
| OTP not sending | Configure `SMTP_*` or `TWILIO_*` env vars |
| Database errors | Ensure `DATABASE_URL` points to PostgreSQL |

---

## 📄 License

This project is built for Indian Municipal Corporations (Nagar Nigam).

---

## 🙏 Acknowledgments

- Built for smart city initiatives
- Designed for Indian municipalities
- Supports 29+ Indian languages
- AI-powered waste classification

---

**Made with ❤️ for cleaner cities**
