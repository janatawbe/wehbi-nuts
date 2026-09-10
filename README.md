# Wehbi Nuts

AI Shop Digitizer & E-commerce Platform.

Wehbi Nuts is a platform that helps small shops digitize their catalog with
AI and sell it online through an e-commerce storefront.

## Milestone 1 — Project Foundation

Established a clean, working project skeleton:

- A React + Vite + TypeScript frontend (`client/`) styled with Tailwind CSS v4,
  showing a placeholder landing page for Wehbi Nuts.
- A FastAPI backend (`server/`) with a modular structure and a single
  `GET /api/health` endpoint.
- Test setups for both apps (Vitest + React Testing Library on the frontend,
  pytest on the backend).

## Milestone 2 — Database & Product Model (current scope)

Adds the persistent data layer and core domain models needed by the future
AI digitizer, catalog, and ordering system. This milestone intentionally
does **not** include:

- Photo upload, product detection, OCR, or barcode scanning logic
- AI model/API integration
- Storefront, search, cart, checkout, or a COD order endpoint
- Admin dashboard, authentication, WhatsApp integration
- Excel/CSV import/export
- Docker or deployment

What it does include:

- **Database**: PostgreSQL, accessed through SQLAlchemy 2.x models, with
  Alembic managing schema migrations.
- **Six core models**: `Category`, `Product`, `DigitizationJob`,
  `DigitizedProduct`, `Order`, `OrderItem` — with relationships, foreign
  keys, and data-integrity constraints (unique SKU/barcode, non-negative
  prices, quantity > 0, AI-confidence bounds, etc).
- **Pydantic schemas** for create/update/read validation of each model.
- An initial Alembic migration creating all Milestone 2 tables.
- A backend test suite covering models, relationships, and constraints,
  running against an isolated in-memory SQLite database (no real
  PostgreSQL server required to run `pytest`).

### Product vs. DigitizedProduct

- **`DigitizedProduct`** is a *draft* produced by a future AI digitization
  step: it holds whatever the AI extracted from a shop photo (name, price
  guess, category suggestion, confidence score, raw AI output, etc.) along
  with a `review_status` (`draft` / `approved` / `rejected` / `merged`).
  It is never sold directly.
- **`Product`** is the actual, persisted catalog item that can be priced,
  stocked, and ordered. A `DigitizedProduct` only becomes linked to a real
  `Product` once a human approves it (`DigitizedProduct.product_id`) —
  nothing in this milestone does that automatically.

This separation ensures AI output is always a suggestion that a person
reviews before it affects the real catalog.

## Project Structure

```
wehbi-nuts/
├── client/                       # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.test.tsx
│   │   ├── main.tsx
│   │   ├── index.css              # Tailwind v4 entrypoint
│   │   └── test/setup.ts
│   └── package.json
├── server/                       # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app, CORS, router registration
│   │   ├── api/                    # Route handlers (e.g. health)
│   │   ├── core/                   # Config / settings
│   │   ├── db/                     # Engine, session, declarative base, GUID type
│   │   ├── models/                 # SQLAlchemy models + enums
│   │   ├── schemas/                # Pydantic create/update/read schemas
│   │   └── services/                # Business logic (empty for now)
│   ├── alembic/                    # Migration environment
│   │   └── versions/                # Migration scripts
│   ├── tests/
│   ├── alembic.ini
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

No frontend environment variables are required yet.

## Backend Setup (Windows)

```powershell
cd server
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Then edit `server/.env` and set `DATABASE_URL` to point at your local
PostgreSQL database (see below). Never commit real credentials — `.env` is
gitignored and only `.env.example` (with placeholder values) is tracked.

### Setting up a local PostgreSQL database

PostgreSQL is **not** installed automatically by this project. To run the
backend against a real database:

1. Install PostgreSQL locally (e.g. from https://www.postgresql.org/download/windows/).
2. Create a database and a user, for example using `psql`:

   ```sql
   CREATE DATABASE wehbi_nuts;
   CREATE USER wehbi_nuts WITH PASSWORD 'changeme';
   GRANT ALL PRIVILEGES ON DATABASE wehbi_nuts TO wehbi_nuts;
   ```

3. Set `DATABASE_URL` in `server/.env` accordingly:

   ```
   DATABASE_URL=postgresql+psycopg://wehbi_nuts:changeme@localhost:5432/wehbi_nuts
   ```

4. Apply migrations (see below).

If you don't have PostgreSQL installed yet, the backend test suite still
runs fully against an isolated in-memory SQLite database — you only need
real PostgreSQL to run the app itself against real data.

### Running Alembic migrations

From `server/`, with the virtual environment activated and `DATABASE_URL`
configured (via `.env` or the environment):

```powershell
alembic upgrade head      # apply all migrations
alembic downgrade -1      # roll back the most recent migration
```

Alembic always reads the connection string from `DATABASE_URL` (via the
app's settings) — it is never hardcoded in `alembic.ini`.

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

Backend tests use an isolated in-memory SQLite database created and torn
down per test — a real local PostgreSQL server is **not** required to run
`pytest`.

## Docker

Docker is **intentionally not used** at this stage of the project. Both apps
run directly on the host using Node.js and a Python virtual environment.
Containerization may be introduced in a later milestone.
