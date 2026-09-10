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

## Milestone 3 — Digitizer Upload System

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

## Milestone 4 — Gemini AI Digitizer (current scope)

Runs Gemini vision analysis over each source image in a job and turns the
sellable inventory units it finds into `DigitizedProduct` drafts, cropped
from the original photo. This milestone intentionally does **not**
include:

- A product review/approval UI (Milestone 7)
- Storefront, cart, checkout, or admin dashboard features
- More than one AI request per source image (never one per detected item)

### Why Gemini

Product photos in this business are highly varied: a sealed package, a
jar or bottle, a whole tray of loose bulk product, or a close-up filling
the frame with no packaging at all. What counts as "one sellable unit" in
each case depends on genuine scene understanding, not just where an edge
or region happens to be — a tray of many small pieces is one item; a
jar's cap or sticker is not a second item. A vision-capable LLM can
reason about a photo in exactly those terms directly: given one full shop
photo and instructions written around *sellable inventory units* (see
below), Gemini returns the complete package/jar/bottle/tray as one item,
keeps genuinely different products separate, and can additionally supply
a product identity from the same pass.

Gemini output is still just a **draft** (see "Data quality" below); the
architecture is deliberately built around a narrow `AIProductAnalyzer`
interface (`app/services/ai/types.py`) so this specific choice of
provider/model is not baked into the rest of the app.

### What Gemini is asked to detect

The system instruction (`app/services/ai/gemini_vision_digitizer.py`)
tells Gemini it is digitizing inventory for a nuts/coffee/sweets/snacks/
dried-food roastery shop, and to reason in terms of **sellable inventory
units**, not every visually distinct object:

- a whole package/bag/box is one item (its label/logo is not a separate item)
- a whole jar/container is one item (its lid/sticker/cap is not)
- a whole bottle is one item
- an entire bulk tray/bin of one product is one item (individual pieces
  inside it are not)
- a loose bulk product filling the frame with no packaging is one item
- a shelf of different products returns one item per distinguishable unit
- shelves, dividers, price tags, logos-as-objects, and decorations are
  ignored entirely

Gemini may visually infer a likely product identity when there is no
readable text at all (common for loose bulk products) — but it must never
present a visual guess as if it were read from text. `identification_basis`
(`visual` / `text` / `visual_and_text`) makes that distinction explicit in
every stored result, and a low `confidence` is expected/accepted when the
model isn't sure, rather than a confident-sounding invented name.

### Structured output & bounding-box convention

Gemini is asked for one JSON object per image: `{"items": [...]}`, each
item validated (both by Gemini's structured-output mode *and* again
independently with Pydantic on the server, since a model's "structured
output" is a strong hint, not a guarantee) against
`app.services.ai.types.DetectedProduct`: `name_en`, `name_ar`, `category`,
`presentation` (`packaged`/`jar`/`bottle`/`bulk_tray`/`bulk_loose`/`other`),
`bbox`, `confidence` (0-1), `visible_text`, `identification_basis`, `notes`.

`bbox` is `[ymin, xmin, ymax, xmax]`, each an integer normalized to
**0-1000** relative to the full image regardless of its actual pixel size
(0,0 = top-left, 1000,1000 = bottom-right) — validated to be 4 integers in
range with `min < max`. `digitizer_processing_service._bbox_to_pixels`
converts this to pixel-space `(x, y, width, height)`, clamped to the
image's actual bounds, before cropping; a box that collapses to zero area
after clamping/rounding is dropped rather than turned into a degenerate
crop.

### Processing pipeline & rerun behavior

`POST /api/digitizer/jobs/{job_id}/process`
(`app/services/digitizer_processing_service.py`) is a separate endpoint
from upload, not an automatic step of it: an AI call per image is slow
and can fail independently of upload validation, so upload stays fast/
synchronous while processing is an explicit, separately-retriable action.
No background worker is introduced — it runs synchronously within the
request, which is sufficient at this milestone's scale.

For each source image: one Gemini request → each returned item's bbox is
converted to pixel space and clamped → cropped from the **original**
image (`Image.crop`, no resizing/upscaling/resampling, so the crop's
aspect ratio always matches its bbox exactly) → encoded as JPEG and
re-decoded to confirm it is genuinely renderable before being trusted →
persisted as a `DigitizedProduct` (`review_status=DRAFT`,
`needs_review=True`, `product_id=NULL`).

Job status: `pending` (at upload) → `processing` → `completed`, or
`failed` if every source image's AI call failed. A partial failure (some
images succeed, some don't) is still `completed`, with the failure count
and a note in `error_message` — a job is never silently reported as a
full success when part of it wasn't. Rerunning a job is safe: previous
`DigitizedProduct` rows and crop files for that job are replaced, never
accumulated.

### Crop storage structure

```
server/uploads/digitizer/<job-id>/
    source/            # original uploaded images (Milestone 3, never modified)
    products/           # cropped product images, one per DigitizedProduct
```

Crop filenames are random, server-generated 32-hex-character names
(`<uuid>.jpg`), matching the existing source-image naming convention —
never derived from any AI-provided text.

### Safe media serving

`GET /api/digitizer/jobs/{job_id}/media/{source|products}/{filename}`
serves a source or crop image without ever exposing the filesystem: the
filename must exactly match the safe pattern this app itself generates,
and the resolved path is re-checked to stay inside the expected
directory. An invalid filename, an unknown job, or an unknown `kind` are
all indistinguishable from "not found" in the response.

### Database changes

Milestone 2's `DigitizedProduct` model already had `job_id`,
`source_image`, `crop_image`, `ai_confidence`, `ai_raw_result`,
`needs_review`, and `review_status` — all reused as-is. One migration
(`alembic/versions/a1f3c9d4e6b2_*.py`) adds the fields Gemini's output
needed that didn't already exist: `category_suggestion` (Gemini's raw
category text, kept distinct from the human-assigned `category_id` FK),
`presentation`, `identification_basis`, `visible_text`, `notes`, and
pixel-space `bbox_x`/`bbox_y`/`bbox_width`/`bbox_height`.

### Error handling & retries

`GeminiVisionDigitizer` retries a transient server error (e.g. `503`) up
to 3 times with a short backoff; **a `429` rate-limit/quota error is
retried the same way** (see below); any other client error (bad request,
invalid key, unknown model) is never retried, since it will not resolve
itself. Either way, only a client-safe
`AIServiceUnavailableError`/`AIInvalidResponseError` message ever
propagates — never a raw SDK exception or the API key. One source
image's AI failure (unreachable service, malformed/invalid response,
corrupt/unreadable image) is recorded as a failed image and does not stop
the rest of the job from processing; the job's `error_message` includes
that specific reason (for a known, client-safe `AIAnalysisError`) rather
than only the generic "processing failed."

**Production incident, root-caused and fixed:** some real jobs failed
immediately (~5s) with only "Digitization failed for all source images."
and no further detail. Root cause: the Gemini free tier enforces a low
per-model daily request quota (observed: 20 requests/day for
`gemini-3.6-flash`) and responds with HTTP `429`, which the SDK
classifies as a `ClientError` — the same exception class used for a
genuinely bad request. The code treated every `ClientError` as
non-retryable, so a rate-limited image failed instantly with a message
that gave no indication it was a quota issue rather than a bug. Fixed by
retrying a `429` the same way as a `503` (bounded, same attempt count),
and by having the exhausted-retries message explicitly name the free-tier
rate limit as the cause, surfaced all the way to the job's
`error_message`. Retrying cannot make a fully-exhausted *daily* quota
succeed sooner, by definition — if every attempt still reports 429, wait
for the quota to reset (or reduce concurrent processing) rather than
retrying the job repeatedly.

### Data quality: drafts, not truth

Every `DigitizedProduct` created here is `review_status=DRAFT` with
`needs_review=True` and `product_id=NULL` — nothing in this milestone
creates or modifies a real, sellable `Product`. Gemini's identification
(including a purely visual guess for an unlabeled bulk product) is always
a draft for a human to confirm, never treated as verified fact.

### Manually testing detection

`test-data/generated-shop-images/` (gitignored, not committed) holds
synthetic validation photos used during development — see git history for
how they were generated. `test-data/real-shop-images/` is a held-out,
never-inspected-during-development real-photo validation set.

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
│   │   └── services/
│   │       ├── ai/                  # AIProductAnalyzer + GeminiVisionDigitizer
│   │       ├── digitizer_service.py            # upload (Milestone 3)
│   │       ├── digitizer_processing_service.py # Gemini processing (Milestone 4)
│   │       └── storage.py
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
