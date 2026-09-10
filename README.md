# Wehbi Nuts

AI Shop Digitizer & E-commerce Platform.

Wehbi Nuts is a platform that helps small shops digitize their catalog with
AI and sell it online through an e-commerce storefront.

## Milestone 1 — Project Foundation (current scope)

This milestone only establishes a clean, working project skeleton. It
intentionally does **not** include:

- AI / OCR features
- Database models
- Storefront or admin dashboard screens
- WhatsApp integration
- Docker

What it does include:

- A React + Vite + TypeScript frontend (`client/`) styled with Tailwind CSS v4,
  showing a placeholder landing page for Wehbi Nuts.
- A FastAPI backend (`server/`) with a modular structure and a single
  `GET /api/health` endpoint.
- Test setups for both apps (Vitest + React Testing Library on the frontend,
  pytest on the backend).

## Project Structure

```
wehbi-nuts/
├── client/                 # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.test.tsx
│   │   ├── main.tsx
│   │   ├── index.css        # Tailwind v4 entrypoint
│   │   └── test/setup.ts
│   └── package.json
├── server/                 # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app, CORS, router registration
│   │   ├── api/              # Route handlers (e.g. health)
│   │   ├── core/             # Config / settings
│   │   └── services/         # Business logic (empty for now)
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

## Frontend Setup (Windows)

```powershell
cd client
npm install
```

Copy environment variables if/when needed (none required yet):

```powershell
# no .env required for Milestone 1
```

## Backend Setup (Windows)

```powershell
cd server
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

## Running Locally (Windows)

**Frontend** (from `client/`):

```powershell
npm run dev
```

Runs at `http://localhost:5173`.

**Backend** (from `server/`, with the virtual environment activated):

```powershell
uvicorn app.main:app --reload
```

Runs at `http://localhost:8000`. Check `http://localhost:8000/api/health`,
which returns `{"status": "ok"}`.

The backend's CORS configuration already allows requests from the frontend's
local dev server (`http://localhost:5173`).

## Running Tests

**Frontend** (from `client/`):

```powershell
npm run test
```

**Frontend build check** (from `client/`):

```powershell
npm run build
```

**Backend** (from `server/`, with the virtual environment activated):

```powershell
pytest
```

## Docker

Docker is **intentionally not used** at this stage of the project. Both apps
run directly on the host using Node.js and a Python virtual environment.
Containerization may be introduced in a later milestone.
