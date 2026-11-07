# ⚽ KickoffXI — FIFA World Cup 2026 Player Database & Match Simulator

A full-featured web application for browsing every player in the **FIFA World Cup 2026** tournament, building custom squads, simulating matches, and saving squad configurations.

Built with **Python / Flask**, backed by **Firebase Authentication** and **Cloud Firestore** for user accounts and saved squads, with static football tournament data served from CSV datasets.

---

## ✨ Features

- **🏠 Home Page** — Hero banner, randomly featured players, and tournament teams overview.
- **🔍 Player Database** — Searchable, filterable roster across all tournament teams.
- **🏳️ Teams Browser & Detail** — Explore full squads for every participating nation.
- **⚽ Match Simulator** — Pick a formation, build starting XI + bench, and simulate matches against AI difficulty tiers.
- **📋 Saved Squads** — Authenticated users can save, edit, duplicate, and delete custom squads.
- **🔐 Secure Authentication** — Username or email login, Remember Me support, and secure email password resets via Firebase.
- **🌙 Dark / Light Theme** — Seamless theme toggle with persistent preferences.
- **📡 REST API** — JSON endpoints for squads, validation, players, and simulation.

---

## 🛠️ Architecture & Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Backend** | Python 3.11+ / Flask 3.1 | Application factory, REST APIs, and Jinja2 server-rendered views |
| **Authentication** | Firebase Authentication | Off-server secure credential storage and identity management |
| **User Data Store** | Cloud Firestore (`asia-southeast1`) | User profiles, username reservations, and saved squad subcollections |
| **Session Security** | Firebase Session Cookies | HttpOnly, SameSite=Lax, Secure in production |
| **Tournament Data** | Static CSVs (`data/teams/*.csv`) | Preloaded into memory via `CSVDataLoader` with stable player identity keys |
| **Frontend** | HTML5, Tailwind utility styles, Vanilla JS | Interactive pitch view, modal pickers, and live search |

---

## 📂 Project Structure

```
KickoffXI/
├── main.py                  # Entry point for local dev & production
├── config.py                # Environment configurations (dev / prod)
├── firestore.rules          # Firestore deny-all security rules (server-side only)
├── render.yaml              # Render deployment configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development & testing dependencies (pytest)
│
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── auth_routes.py       # Authentication routes (/signup, /signin, /profile, /reset)
│   ├── routes.py            # Main application & saved-squad REST routes
│   ├── firebase_client.py   # Lazy Firebase Admin SDK initialization
│   ├── identity_rest.py     # Identity Toolkit REST API client (passwords, resets)
│   ├── session_auth.py      # Firebase session cookie verification & decorators
│   ├── user_store.py        # Firestore access for users & usernames
│   ├── squad_store.py       # Firestore access for user-owned saved squads
│   ├── email_sender.py      # SMTP password reset email delivery
│   ├── data_loader.py       # CSV data loader with stable player keys
│   ├── match_validation.py  # Squad composition validation rules
│   └── formations.py        # Tactical formations and slot mappings
│
├── data/teams/              # National team CSV datasets
├── templates/               # Jinja2 HTML templates
├── static/                  # CSS, JS, and image assets
├── scripts/
│   ├── check_firebase.py                # Firebase connectivity verification tool
│   └── enrich_overall_ratings.py        # Player rating dataset utility
└── tests/                   # Pytest test suite
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Virtual environment tool (`venv`)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/SadmanSakibKhan11/KickoffXI.git
cd KickoffXI

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your development values:
```bash
cp .env.example .env
```

Key environment variables:
| Variable | Description |
|---|---|
| `FLASK_CONFIG` | `development` or `production` |
| `SECRET_KEY` | Flask session secret (random string in production) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Path to service account JSON key (or raw JSON string) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Alternative path to service account JSON key |
| `FIREBASE_WEB_API_KEY` | Firebase Web API Key for REST authentication |
| `APP_BASE_URL` | Base URL for password reset links (e.g. `http://localhost:5000`) |
| `AUTH_SESSION_COOKIE_NAME` | Cookie name (default: `kxi_session`) |
| `AUTH_REMEMBER_DAYS` | Remember Me session duration in days (max 14) |
| `MAIL_USERNAME` | Gmail address for password reset emails |
| `MAIL_PASSWORD` | 16-character Google App Password |

### 4. Running the Application
```bash
python main.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🧪 Running Tests

The test suite runs completely offline with in-memory fakes and mocked network boundaries:
```bash
python -m pytest -v
```

---

## 🔍 Diagnostics & Health Check

To test connection to your configured Firebase project:
```bash
python scripts/check_firebase.py
```

---

## 📄 License & Disclaimer

Educational student project created for learning purposes. Not affiliated with FIFA. All player and team trademarks belong to their respective owners.
