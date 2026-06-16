# Oasis

## Overview

This repository contains the **Oasis Website** – a modern, single‑page web application that blends a Flask backend with a React/Vite frontend.  The app provides an immersive, glass‑morphism‑styled UI where users can explore 3‑D content, track personal progress, and interact with several AI‑powered services.

---

## Table of Contents

1. [Features](#features) 
2. [Architecture Overview](#architecture-overview) 
3. [Backend API Endpoints](#backend-api-endpoints) 
4. [Frontend UI & Navigation](#frontend-ui--navigation) 
5. [Iconography & Glass‑Card Design](#iconography--glass‑card-design) 
6. [AI & Voice Integrations](#ai--voice-integrations) 
7. [Data Persistence](#data-persistence) 
8. [Configuration & Ports](#configuration--ports) 
9. [Development Setup](#development-setup) 
10. [Production Deployment](#production-deployment) 
11. [License](#license) 
12. [Acknowledgements](#acknowledgements)

---

## Features

| Category | Feature | Description |
|---|---|---|
| **Core UI** | **Glass‑morphism cards** | Full‑screen translucent cards that display icons and 3‑D models. Tailored CSS creates a frosted‑glass effect while preserving readability. |
| | **Grid‑only mode** | The previous "Drift Mode" and "Settings" page have been removed. The application now always renders the grid view (`renderGrid()`) for a consistent experience. |
| | **Responsive layout** | The UI adapts to various screen sizes, ensuring a premium look on desktop, tablet, and mobile browsers. |
| **Navigation** | **Sidebar navigation** | Sidebar with icons leading to major sections: *Home*, *Journal*, *Planner*, *Games*, *Counselor*, *Oasis 3D*, *About*, and a newly added *Yoga* endpoint. |
| | **Dynamic routing** | All navigation links are proxied through Vite’s dev server (port 5035) and forwards to Flask endpoints. |
| **Iconography** | **10 custom icons** | Five icons were added in a previous iteration (`summary.png`, `watch.png`, `counsellor.png`, `oasis3d.png`, `about.png`). The next five will be added later. Icons cover the entire glass card and are semi‑transparent so the background is visible. |
| **AI Integrations** | **Google Generative AI (deprecated)** | Uses `google.generativeai` for content generation. The package is deprecated; a migration to `google.genai` is recommended. |
| | **ElevenLabs Text‑to‑Speech** | Provides voice narration for journal entries and guided sessions. Works with Python 3.14 via a compatibility shim. |
| | **Emotion detection** | Endpoint `/detect_emotion` uses a machine‑learning model to infer user emotion from text/audio. |
| **Progress Tracking** | **User progress API** (`/api/user_progress`) | Returns JSON describing the user’s completed activities, journal entries, and analytics. |
| | **Analytics & Recommendations** | Endpoints `/recommend`, `/activities`, `/planner` produce personalized suggestions using the stored user data. |
| **3‑D Content** | **GLB models** | Static 3‑D models are served from `/static/models/*.glb`. The UI loads them into a WebGL canvas when a card is clicked. |
| **Telemetry** | **Track endpoint** (`/track`) | Logs user interactions for later analysis (e.g., button clicks, navigation events). |
| **OAuth & Calendar Sync** | **OAuth callback** (`/oauth2callback`) | Enables users to authorize the app to write events to Google Calendar (`/sync_to_calendar`). |

---

## Architecture Overview

```
+-------------------+          +-------------------+          +-------------------+
|   Frontend (Vite) |  HTTP   |   Flask Backend   |  DB/FS   |   SQLite DB      |
|  React Components| <------> |  server.py        | <------> |  oasis_game.db   |
|  CSS (Glass‑morph)|          |  Routes / API     |          |  CSV logs        |
+-------------------+          +-------------------+          +-------------------+
```

- **Frontend** – Built with **React** and bundled by **Vite**. All static assets (`.png`, `.glb`, CSS) are served through the Vite dev server. Proxy configuration in `vite.config.js` forwards API calls to the Flask backend on **port 5035**.
- **Backend** – **Flask** (`server.py`) hosts the REST API, OAuth handling, AI services, and file serving. It runs in **debug mode** during development (`app.run(debug=True, port=5035)`). Production should use a WSGI server (Gunicorn, uWSGI, etc.).
- **Data Layer** – Two primary stores:
  1. **SQLite (`oasis_game.db`)** – Stores game‑related state and user progress.
  2. **CSV (`user_behaviour.csv`)** – Logs raw telemetry for offline analysis.
- **Credentials** – `credentials.json` holds Google OAuth client secrets; never commit to version control.

---

## Backend API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/user_progress` | Returns JSON with the user’s overall progress, completed activities, and scores. |
| `POST` | `/track` | Records a telemetry event (e.g., card click, navigation). |
| `GET` | `/journal` | Serves the journal UI and data. |
| `GET` | `/planner` | Returns a list of recommended future activities. |
| `GET` | `/activities` | Provides activity catalog JSON. |
| `POST` | `/recommend` | Generates personalized recommendations based on stored data. |
| `GET` | `/counsellor` | Returns a chatbot UI that talks to the user via ElevenLabs TTS. |
| `GET` | `/oasis-home` | Main landing page (grid view). |
| `GET` | `/oauth2callback` | Handles Google OAuth redirect (port 5035). |
| `POST` | `/sync_to_calendar` | Writes an event to the user’s Google Calendar. |
| `POST` | `/detect_emotion` | Returns detected emotion from submitted text/audio. |
| `GET` | `/static/<file>` | Serves static assets (icons, images, GLB models). |
| `GET` | `/manifest.json` & `/service-worker.js` | PWA support files. |

All endpoints are proxied through Vite during development, e.g., `http://127.0.0.1:5035/api/user_progress`.

---

## Frontend UI & Navigation

- **Sidebar** – Persistent navigation on the left side with translucent glass cards. Each icon fills its card, ensuring the background remains subtly visible.
- **Grid View** – The only active UI mode. Cards are generated from `iconsData` (found in `templates/Oasis.html`). Clicking a card loads the associated 3‑D model or launches a dedicated page (journal, planner, etc.).
- **Responsive Design** – CSS variables control card size, glass blur, and gradient backgrounds. Media queries adapt the layout for mobile devices.
- **PWA** – Service worker registers for offline caching of static assets; manifest enables installability.

---

## Iconography & Glass‑Card Design

- **Icon placement** – Icons are placed inside a `<div class="glass-card">` container that applies `backdrop-filter: blur(12px)` and a semi‑transparent background.
- **Translucency** – CSS `rgba(255,255,255,0.15)` gives a frosted look while still allowing the underlying page gradient to show through.
- **Coverage** – Each icon expands to cover the full width and height of the card, matching the user’s request for “cover the whole glass box”.
- **Future icons** – Five additional icons will be added later; the UI automatically adapts to the new entries.

---

## AI & Voice Integrations

1. **Google Generative AI** (`google.generativeai`)
   - Currently imported as `genai_v1`. The library is deprecated; the repo includes a warning and will continue to work but receives no updates. A migration to the new `google.genai` package is recommended.
   - Used for content generation (e.g., AI‑driven recommendations, chatbot responses).

2. **ElevenLabs Text‑to‑Speech**
   - Provides lifelike voice output for journal entries and counselor chat.
   - The package uses a Pydantic V1 compatibility shim; note the warning about Python 3.14.

3. **Emotion Detection**
   - Simple ML model (scikit‑learn / TensorFlow) analyses text or audio to infer emotions; the result is returned by `/detect_emotion`.

---

## Data Persistence

- **SQLite Database (`oasis_game.db`)** – Stores user progress, game state, and timestamps.
- **CSV (`user_behaviour.csv`)** – Appends raw telemetry events; each row includes a timestamp, user ID, event type, and payload.
- **Static Asset Folder** – Located under `static/` for icons (`*.png`), 3‑D models (`*.glb`), and other media.

---

## Configuration & Ports

- **Development Port** – The Flask server runs on **5035** (previously 5034). The redirect URI is `http://localhost:5035/oauth2callback`.
- **Vite Proxy** – All API and static routes in `vite.config.js` point to `http://127.0.0.1:5035`.
- **Environment Variables** – `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ELEVENLABS_API_KEY` are expected in a `.env` file (not version‑controlled).

---

## Development Setup

```bash
# 1. Clone the repository (already done in this workspace)
# 2. Create a virtual environment
python -m venv venv
source venv/Scripts/activate   # Windows PowerShell

# 3. Install Python dependencies
pip install -r requirements.txt   # includes Flask, google-generativeai, elevenlabs, pandas, etc.

# 4. Install Node dependencies for the frontend
cd src   # or the root where package.json lives
npm install

# 5. Run the Flask backend (development mode)
python server.py   # will listen on http://127.0.0.1:5035

# 6. In another terminal, start Vite
npm run dev   # proxies API calls to the Flask backend

# 7. Open http://localhost:5173 (Vite dev server) in a browser.
```

**Note:** The backend prints a warning about the deprecated `google.generativeai` package and the ElevenLabs Pydantic compatibility when the server starts.

---

## Production Deployment

1. **WSGI Server** – Use Gunicorn or uWSGI to serve `server.py` on port 80/443 behind a reverse proxy (Nginx/Apache).
2. **Static Build** – Run `npm run build` to generate a static bundle in `dist/`. Configure Flask to serve files from `dist/`.
3. **Environment Variables** – Set all required secrets in the hosting environment; never store them in the repo.
4. **HTTPS** – Obtain TLS certificates (Let’s Encrypt) and configure the reverse proxy.
5. **Scaling** – The Flask app is lightweight; add a process manager (systemd, supervisor) for reliability.

---
## Licence

- **MIT Licence** - Everyone can use and modify this code. Credit is appreciated.

## Acknowledgements

- **Google Gemini** – for the generative AI APIs (deprecated package).
- **ElevenLabs** – for Text‑to‑Speech services.
- **Vite** – for rapid React development and hot‑module replacement.
- **Flask** – for the simple, extensible backend framework.
- **Open‑source community** – for the many Python and JavaScript libraries used throughout the project.
