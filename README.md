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

## Milestone 4 — AI Digitizer (current scope)

Runs an AI vision analysis over each source image in a job and turns the
sellable inventory units it finds into `DigitizedProduct` drafts, cropped
from the original photo. This milestone intentionally does **not**
include:

- A product review/approval UI (Milestone 7)
- Storefront, cart, checkout, or admin dashboard features
- More than one AI request per source image (never one per detected item)
- Any classical computer-vision object detection

### Why a vision LLM

Product photos in this business are highly varied: a sealed package, a
jar or bottle, a whole tray of loose bulk product, or a close-up filling
the frame with no packaging at all. What counts as "one sellable unit" in
each case depends on genuine scene understanding, not just where an edge
or region happens to be — a tray of many small pieces is one item; a
jar's cap or sticker is not a second item. A vision-capable LLM can
reason about a photo in exactly those terms directly: given one full shop
photo and instructions written around *sellable inventory units* (see
below), it returns the complete package/jar/bottle/tray as one item,
keeps genuinely different products separate, and can additionally supply
a product identity from the same pass.

The output is still just a **draft** (see "Data quality" below); the
architecture is deliberately built around a narrow `AIProductAnalyzer`
interface (`app/services/ai/types.py`) so the specific choice of
provider/model is not baked into the rest of the app -- swapping
providers means writing one new class behind that interface, not touching
the processing pipeline, the API, or the database layer.

### Provider and model: OpenRouter, `google/gemini-2.5-flash-lite`

`OpenRouterVisionDigitizer` (`app/services/ai/openrouter_vision_digitizer.py`)
implements `AIProductAnalyzer` via [OpenRouter](https://openrouter.ai), a
gateway that proxies many providers' vision models behind one
OpenAI-compatible Chat Completions API — reached with the `openai` Python
package purely as a generic HTTP client (`base_url` pointed at
OpenRouter), not for direct OpenAI billing or API usage. The whole point
of the `AIProductAnalyzer` interface is that this specific choice of
gateway/provider/model isn't load-bearing for the rest of the app; this is
the *third* implementation behind that same interface for this project (an
earlier iteration used direct Gemini, then direct OpenAI), and each swap
touched only this one file plus wiring, never the processing pipeline,
the API, or the database.

The model is configurable (`OPENROUTER_MODEL`, default
`google/gemini-2.5-flash-lite`), chosen deliberately on cost grounds and
verified live (via OpenRouter's free, unbilled `GET /api/v1/models`) rather
than assumed:

- Confirmed `structured_outputs` support (strict JSON schema, not just a
  generic "please return JSON" instruction) and image input, directly
  from that listing's `supported_parameters`/`input_modalities` fields.
- An established Google model, already proven in this exact project's
  earlier iterations to handle this task well: vision, structured output,
  English/Arabic bilingual naming, and the "one tray vs. many pieces"
  business judgment — not a tiny/obscure model chosen purely for having
  the lowest price on a list. Several 3-4B-parameter open models and
  OpenRouter's `:free` tier were cheaper on paper but judged unproven for
  reliable bilingual identification and business-rule judgment at *any*
  price, and free-tier models on OpenRouter carry materially stricter
  rate limits — a real risk for a business pipeline (see the rate-limit
  incident further down).
- Priced at $0.10 / $0.40 per million input/output tokens at verification
  time (plus a small flat per-image charge) — cheaper than the
  direct-OpenAI model used in the previous iteration ($0.15/$0.60/M).
- `reasoning.mandatory: false` in that same listing, meaning reasoning (a
  real, billed cost driver on models that support it) can be fully
  disabled rather than merely hidden from the response — see below.
- Deliberately **not** `openrouter/auto`/`auto-beta` (OpenRouter's
  automatic model routing): that could silently route a request to a
  pricier model, which is exactly what pinning an exact model ID avoids.

Cost is bounded further by keeping the system prompt concise, requesting
no explanation/commentary text, capping `max_tokens` (2000 — generous for
a busy multi-item shelf, but not unbounded), and passing OpenRouter's
`reasoning: {"effort": "none"}` extension (via `extra_body`, since it is
not a standard OpenAI field) to fully turn off reasoning-token generation
— OpenRouter's docs are explicit that merely `exclude`-ing reasoning from
the response still bills for computing it, while `effort: "none"`
prevents the computation (and its cost) entirely.

### What the AI is asked to detect

The instructions given to the model tell it it is digitizing inventory
for a nuts/coffee/sweets/snacks/dried-food roastery shop, and to reason
in terms of **sellable inventory units**, not every visually distinct
object:

- a whole package/bag/box is one item (its label/logo is not a separate item)
- a whole jar/container is one item (its lid/sticker/cap is not)
- a whole bottle is one item
- an entire bulk tray/bin of one product is one item (individual pieces
  inside it are not)
- a loose bulk product filling the frame with no packaging is one item
- a shelf of different products returns one item per distinguishable unit
- shelves, dividers, price tags, logos-as-objects, and decorations are
  ignored entirely

The model may visually infer a likely product identity when there is no
readable text at all (common for loose bulk products) — but it must never
present a visual guess as if it were read from text. `identification_basis`
(`visual` / `text` / `visual_and_text`) makes that distinction explicit in
every stored result, and a low `confidence` is expected/accepted when the
model isn't sure, rather than a confident-sounding invented name.

### Structured output & bounding-box convention

The model returns one JSON object per image: `{"items": [...]}`, requested
via the gateway's native structured-output mode (a Pydantic
`response_format` passed straight to `client.beta.chat.completions.parse`
— never parsed from free-form prose) and then re-validated independently
with Pydantic on the server against `app.services.ai.types.DetectedProduct`:
`name_en`, `name_ar`, `category`, `presentation`
(`packaged`/`jar`/`bottle`/`bulk_tray`/`bulk_loose`/`other`), `bbox`,
`confidence` (0-1), `visible_text`, `identification_basis`, `notes`. This
double-checking matters in practice: strict JSON schema mode guarantees
field *shape*, not this project's own cross-field business rules (e.g.
bbox `ymin < ymax`), which are plain Python validators no schema can
express — a schema-valid-but-business-invalid response is treated the
same as a malformed one, not silently accepted.

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

For each source image: one AI request → each returned item's bbox is
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
(`alembic/versions/a1f3c9d4e6b2_*.py`) adds the fields the AI's output
needed that didn't already exist: `category_suggestion` (the model's raw
category text, kept distinct from the human-assigned `category_id` FK),
`presentation`, `identification_basis`, `visible_text`, `notes`, and
pixel-space `bbox_x`/`bbox_y`/`bbox_width`/`bbox_height`. None of these
are provider-specific — the same columns would be populated by any
`AIProductAnalyzer` implementation.

### Error handling & retries

OpenRouter's own [documented error codes](https://openrouter.ai/docs/api-reference/errors)
separate transient failures from permanent ones more cleanly than a
typical single-provider API does, and `OpenRouterVisionDigitizer` mirrors
that separation directly rather than guessing from message text:

- Retried, bounded to 3 attempts with a short backoff: `429` (rate
  limited), `408` (request timeout), and `5xx` — including OpenRouter's
  own `502` ("your chosen model is down") and `503` ("no available
  provider meets your routing requirements"), both plausibly transient.
- Never retried: `402` (insufficient credits — OpenRouter-specific;
  retrying cannot fix an empty balance any faster) and every other client
  error (`400`/`401`/`403`/`404`, bad request/invalid key/unknown model),
  none of which resolve themselves.
- A response that is schema-valid but fails this project's own business
  rules (e.g. bbox `ymin < ymax`), a response cut off by the output-token
  cap, or one blocked by content moderation are all treated as an invalid
  response and not retried either — retrying the identical request is
  unlikely to fix a content problem the way it can a transient one.

Either way, only a client-safe `AIServiceUnavailableError`/
`AIInvalidResponseError` message ever propagates — never a raw SDK
exception or the API key. One source image's AI failure is recorded as a
failed image and does not stop the rest of the job from processing; the
job's `error_message` includes that specific reason (for a known,
client-safe `AIAnalysisError`) rather than only a generic "processing
failed."

### Data quality: drafts, not truth

Every `DigitizedProduct` created here is `review_status=DRAFT` with
`needs_review=True` and `product_id=NULL` — nothing in this milestone
creates or modifies a real, sellable `Product`. The AI's identification
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
│   │       ├── ai/                  # AIProductAnalyzer + OpenRouterVisionDigitizer
│   │       ├── digitizer_service.py            # upload (Milestone 3)
│   │       ├── digitizer_processing_service.py # AI processing (Milestone 4)
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
