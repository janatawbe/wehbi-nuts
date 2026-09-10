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

## Milestone 2 — Database & Product Model

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

## Milestone 3 — Digitizer Upload System (current scope)

Adds the first functional stage of the AI Digitizer workflow: uploading
shelf/product photos and turning them into a `DigitizationJob`. This
milestone intentionally does **not** include:

- Product detection, cropping, OCR, or barcode extraction
- Any multimodal AI / model API integration
- Bilingual product generation or AI confidence scoring
- Creating `DigitizedProduct` records or a review workflow
- Storefront, cart, checkout, admin dashboard, or WhatsApp integration

What it does include:

- **Upload endpoint** — `POST /api/digitizer/jobs` accepts one or more
  images (`multipart/form-data`, field name `files`) and creates a single
  `DigitizationJob` for the whole batch.
- **Job endpoints** — `GET /api/digitizer/jobs` (history, newest first) and
  `GET /api/digitizer/jobs/{job_id}` (single job, 404 if unknown).
- **Server-side image validation** using Pillow — the actual image bytes
  are decoded and checked, not just the filename or `Content-Type` header.
  Supported formats: **JPEG, PNG, WEBP**.
- **Safe local storage** under `server/uploads/digitizer/<job-id>/source/`,
  with every file renamed to a random, server-generated filename — the
  client-supplied filename is never used to build a filesystem path.
- **Cleanup on failure** — if any file in a batch is invalid, the whole
  request is rejected, no job row is created, and any files already saved
  for that batch are deleted.
- No database schema changes were needed: the existing `total_items` field
  (from Milestone 2) already records how many images were uploaded, and
  each job's storage directory is derived from its own `id`, so no new
  columns or migration were required.

### Upload limits (configurable via `server/.env`)

| Setting                          | Default    | Meaning                              |
|-----------------------------------|-----------|---------------------------------------|
| `DIGITIZER_UPLOAD_DIR`             | `uploads/digitizer` | Storage root (relative to `server/`, or absolute) |
| `DIGITIZER_MAX_FILE_SIZE_BYTES`    | `10485760` (10 MB) | Max size per image |
| `DIGITIZER_MAX_IMAGES_PER_JOB`     | `20`      | Max images accepted in one upload |
| `DIGITIZER_MAX_IMAGE_DIMENSION`    | `8000`    | Max width/height in pixels |

The frontend mirrors these same limits (`client/src/config/digitizer.ts`)
for fast client-side feedback, but the backend always re-validates —
client-side checks are UX only, never authoritative.

### Runtime uploads and Git

Uploaded files are written under `server/uploads/digitizer/<job-id>/...` at
runtime and are **not** committed — `.gitignore` excludes everything under
that path except a `.gitkeep` placeholder that keeps the folder present in
a fresh clone.

## Project Structure

```
wehbi-nuts/
├── client/                       # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.test.tsx
│   │   ├── main.tsx
│   │   ├── index.css              # Tailwind v4 entrypoint
│   │   ├── pages/                  # DigitizerPage (+ its tests)
│   │   ├── components/digitizer/   # FileDropzone, SelectedFileList, JobHistory
│   │   ├── api/digitizer.ts        # Typed fetch client for the digitizer API
│   │   ├── types/digitizer.ts      # Shared frontend types
│   │   ├── config/                 # API base URL + upload limits (UX only)
│   │   └── test/setup.ts
│   ├── .env.example
│   └── package.json
├── server/                       # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app, CORS, router registration
│   │   ├── api/                    # Route handlers (health, digitizer)
│   │   ├── core/                   # Config / settings
│   │   ├── db/                     # Engine, session, declarative base, GUID type
│   │   ├── models/                 # SQLAlchemy models + enums
│   │   ├── schemas/                # Pydantic create/update/read schemas
│   │   └── services/                # digitizer_service.py, storage.py
│   ├── alembic/                    # Migration environment
│   │   └── versions/                # Migration scripts
│   ├── uploads/digitizer/          # Runtime upload storage (gitignored)
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
copy .env.example .env
```

`VITE_API_BASE_URL` (default `http://localhost:8000`) tells the frontend
where the FastAPI backend is running.

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

Open `http://localhost:5173` and use the **AI Product Digitizer** section to
drag-and-drop or browse for JPEG/PNG/WEBP photos, review the selection, and
upload it — a digitization job is created and appears in "Recent digitization
jobs" below.

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
`pytest`. Digitizer upload tests also use a temporary directory (via
pytest's `tmp_path`) instead of the real `server/uploads/` folder.

New Python dependencies added in Milestone 3: `Pillow` (server-side image
validation) and `python-multipart` (required by FastAPI/Starlette to parse
`multipart/form-data` uploads).

## Docker

Docker is **intentionally not used** at this stage of the project. Both apps
run directly on the host using Node.js and a Python virtual environment.
Containerization may be introduced in a later milestone.
