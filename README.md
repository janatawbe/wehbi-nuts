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
  step: it holds whatever the AI extracted from a shop photo (name,
  category suggestion, confidence score, raw AI output, etc. -- **never a
  price**, see Milestone 7) along with a `review_status` (`pending_review`
  / `draft` / `approved` / `rejected` / `merged` -- see Milestone 7 for the
  full lifecycle). It is never sold directly.
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

**Bounding-box quality (added after manual testing surfaced boxes that
mostly captured a neighboring item's lid, empty shelf, or straddled two
adjacent jars):** the instructions now explicitly tell the model each box
must tightly enclose exactly one complete unit, prioritize the product's
body over its lid/cap, never straddle two adjacent items or include a
neighboring product/shelf/background, never return a tiny sliver, and to
**omit** an item entirely rather than guess a poor box when it's too
occluded to localize reliably. This is a prompt-instruction change, not an
architecture change — M4 still detects multiple physical units of the
same product separately; only the box *quality* is targeted.

This can only meaningfully improve model behavior, not fully guarantee it
— a vision-language model's pixel-level localization on a cluttered shelf
with closely-packed, similar-looking items is a known soft spot versus a
dedicated object detector, and no prompt wording can eliminate that
category of error. As defense in depth,
`digitizer_processing_service._is_bbox_plausible` deterministically drops
a detection with degenerate geometry (near-zero area relative to the
source image, or an extreme aspect ratio) the same way an invalid bbox is
already silently dropped — this is a narrow, generic safety net against
pathological output, **not** a crop-quality filter: it cannot detect a
normally-sized box that simply landed on the wrong object, since that
requires scene understanding no geometry check can provide.

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

## Milestone 6 — Image Refinement & Duplicate Detection

Turns each Milestone 4 crop into a catalog-ready image, and flags likely
duplicate candidates *within a single digitization job* (e.g. five
identical packages photographed on one shelf) for a human to resolve
later. Duplicate detection is entirely local, $0 cost. Image refinement
has **two implementations** behind one interface — a free local one and
an approved, paid AI one — see below.

### Image refinement: `ProductImageRefiner`, two implementations, three preserved files

Every `DigitizedProduct` keeps **three** distinct images on disk: the
original source photo (Milestone 3), the M4 crop (Milestone 4), and — once
refined — a separate `refined_image` (Milestone 6). Refinement never
overwrites either of the first two, and a failed refinement attempt never
touches a previous valid `refined_image` either (see "Failure handling"
below).

`app/services/image_refinement_service.py` defines the
`ProductImageRefiner` interface (one `refine(request) -> RefinementResult`
method, mirroring `AIProductAnalyzer` from Milestone 4) with two
implementations, selected once per request by
`api/digitizer.get_product_image_refiner`:

- **`AIProductImageRefiner`** (`app/services/ai/image_editing_refiner.py`)
  — the active refiner whenever `OPENROUTER_API_KEY` is configured. A
  **paid** AI image-editing call (see "AI provider & cost" below).
- **`LocalBackgroundRefiner`** — free, local, always available; used only
  when no API key is configured at all. Wraps the original Tier 1
  (Pillow) + Tier 2 (`rembg`) pipeline described below. This is a
  *configuration* fallback (what runs when AI isn't set up), never a
  *runtime* one — once AI is configured, a failed AI call is recorded as
  a failed refinement, **never** silently swapped for a `rembg` result
  and presented as if it had succeeded.

### AI provider & cost — `google/gemini-2.5-flash-image` ("Nano Banana")

Manual visual testing of the `rembg`-only pipeline showed it wasn't good
enough for the storefront — a tray of mixed nuts became an awkward
rectangular cutout on white rather than a natural standalone pile.
Achieving the target presentation (loose nuts as a natural clean pile,
matching premium nut-store catalog photography) needs actual generative
image editing, not just background masking.

The existing M4/M5 model (`google/gemini-2.5-flash-lite`) was checked
live against OpenRouter's model catalog and confirmed to have **no image
output capability at all** (`output_modalities: ["text"]`) — it cannot do
this. After live investigation of OpenRouter's dedicated Images API
(`POST /api/v1/images`, distinct from the Chat Completions endpoint
M4/M5 use), **`google/gemini-2.5-flash-image`** was selected and
approved:

- Confirmed (live, via OpenRouter's free model-metadata endpoints) to
  support `input_references` (up to 3 images per request) for
  image-to-image editing, `1:1` aspect ratio output, and is one of the
  best-documented models for exactly this identity-preserving,
  reference-guided editing task.
- **Paid.** Estimated **~$0.03–$0.05 per refined image**, from
  OpenRouter's published `image_output` rate ($0.00003/token) — not a
  measured figure, since no real call was made until this was approved.
- Uses the **same `OPENROUTER_API_KEY`** as Milestone 4/5 — a different
  OpenRouter endpoint/model on the same account, not a new provider or
  credential. Configured model name: `OPENROUTER_IMAGE_REFINEMENT_MODEL`
  (default `google/gemini-2.5-flash-image`).
- **Exactly one attempt per manual "Refine" click** — deliberately no
  retry loop (unlike M4/M5's transient-error retries) and no fallback to
  a different/cheaper paid model, since every attempt is billed
  regardless of outcome.

**Request structure**: at most 3 images total — the real M4 crop is
always image 1 (`input_references[0]`), followed by up to 2 style
reference images (see "Reference images" below). The prompt text (the
Images API has no separate system/user roles, just one `prompt` string)
explicitly labels image 1 as `SOURCE PRODUCT IMAGE -- THIS IS THE PRODUCT
TO PRESERVE AND EDIT` and every following image as `STYLE/PRESENTATION
REFERENCE ONLY -- DO NOT COPY THE PRODUCT`.

**Output handling**: the response's `data[0].b64_json` is base64-decoded,
validated as a genuine, decodable image (Pillow), and rejected — raising
`AIImageRefinementError`, turned into `image_refinement_status=failed` —
if missing, empty, malformed, or undecodable. A valid result is always
re-composed through the *same* deterministic canvas step Tier 1 uses
(exact 1200×1200, centered, padded) regardless of what size the model
actually returned, so the final geometric contract never depends on the
model obeying the "1200×1200" instruction exactly.

**Usage/cost logging**: OpenRouter's `usage.cost`/`usage.total_tokens` are
logged server-side only (`logger.info`, never in an API response) for
every real call — the API key and `Authorization` header are never
logged, and a failed-request exception is logged without its traceback
(`exc_info=False`) since an `httpx` exception can carry the outgoing
request/headers.

### System prompt & per-product context

The full image-refinement system prompt is stored once, centrally, in
`app/services/ai/image_refinement_prompt.py` (`SYSTEM_PROMPT`) — never
duplicated across routes/services. It defines the truthfulness/
product-preservation rules (never invent a different product, never
redesign real packaging, remove only the shop/tray/background context,
pure white 1200×1200 output, no invented text/logos/props/prices, etc.)
and is combined with a short **per-product instruction** built from
Milestone 4/5 metadata (`build_product_context_text`): name, category,
presentation, selling mode, brand, flavor/variant, plus a presentation-
specific emphasis (bulk: "create a natural standalone pile... do not keep
the rectangular tray shape"; packaged: "preserve the exact real package...
do not redesign packaging"). **Price, barcode, and every internal ID are
deliberately never included** — `RefinementProductContext` has no price
field at all, so this is a structural guarantee, not a filter that could
be forgotten.

### Reference images

`server/reference-images/product-refinement/` holds **local-only style/
presentation reference photographs** (composition, lighting, whitespace,
natural arrangement) — never application/product data, never committed to
git (see `server/reference-images/README.md`; typically third-party
photography with no redistribution rights). `app/services/reference_images.py`
selects up to 2 references by filename **prefix**, matched to a product's
`presentation` (`bulk-`/`seeds-` for `bulk_tray`/`bulk_loose`, `packaged-`
for `packaged`/`jar`/`bottle`; `other`/unknown gets none) — extensible by
just dropping a correctly-prefixed file in, no code change needed. The
directory is optional; if absent (e.g. a fresh clone or CI), selection
returns an empty list rather than erroring.

### Failure handling

If the AI request fails outright, or returns something that isn't a
valid image, `digitizer_refinement_service.refine_digitized_product`:
leaves the original crop and any previous `refined_image` (both the DB
field and the file on disk) **completely untouched**, sets
`image_refinement_status=failed`, and returns a client-safe `502` — never
retried automatically, never corrupting product data. A human can retry
explicitly via "Re-refine" at any time.

### The local Tier 1 + Tier 2 (`rembg`) pipeline

Still fully implemented, tested, and used whenever no `OPENROUTER_API_KEY`
is configured (see `LocalBackgroundRefiner` above) — kept as a real,
working fallback/helper, not deleted, but it is never presented as the
successful *AI catalog refinement* when the AI provider is configured and
available.

**Tier 1 (always runs, pure Pillow)**: composes the crop onto a fixed
**1200×1200** square canvas with consistent padding (~8% margin),
centered, on a solid neutral (white) background; resizes with `LANCZOS`
resampling (up when the crop is small, down when it's large, aspect ratio
always preserved — never stretched); finishes with a conservative
`UnsharpMask` pass. **Important terminology**: this is high-quality
resizing/layout, **not** AI super-resolution — it never invents detail
that wasn't already in the source crop.

**Tier 2** (attempted for every "suitable" presentation — `packaged`,
`jar`, `bottle`, `bulk_tray`, `bulk_loose`; `other`/unclassified always
skip it): background isolation via [`rembg`](https://github.com/danielgatis/rembg)
(MIT license) running the small `u2netp` ONNX model locally on CPU
(~4.7MB, cached by `rembg` on first use). Every isolation attempt is
validated before being trusted — `_is_isolation_usable` rejects a result
retaining less than `MIN_RETAINED_AREA_RATIO` (15%) of the original
crop's pixel area (a purely quantitative guard against an
over-aggressive segmentation), falling back to Tier-1-only output and
recording `background_isolation_status=rejected`. This local path is
isolation only, never generative recreation — it can only keep or
discard pixels that were already in the source crop, which is exactly
why it can't achieve the "natural standalone pile" look the AI path can.

### Refinement endpoints & state

`POST /api/digitizer/products/{id}/refine` (single item, always retriable
as "Re-refine") and `POST /api/digitizer/jobs/{id}/refine` (bulk — skips
`image_refinement_status=refined` products so a repeat call never redoes
work that already succeeded; a product with no crop to refine from is
marked `skipped` rather than retried forever). `image_refinement_status`
(`pending` / `refined` / `failed` / `skipped`) and `background_isolation_status`
(`not_attempted` / `applied` / `rejected`) are separate fields, and both
are separate again from Milestone 5's `enrichment_status` and
Milestone 7's `review_status` — independent pipeline stages, independent
outcomes.

### Duplicate detection: deterministic, layered, within-job only

`app/services/duplicate_detection_service.py` flags likely duplicates
**within one digitization job** (catalog-wide matching across jobs is
deferred to Milestone 7). Never uses an AI/OpenRouter call.

**Eligibility — enrichment is a hard prerequisite, and this is now made
explicit rather than silent.** A candidate can only be compared once
Milestone 5 enrichment has set its `selling_mode` (M4 never does) — an
un-enriched candidate is left at `duplicate_status = not_checked`, never
silently downgraded to `none` (which would look identical to "compared,
found nothing"). `detect-duplicates` never triggers enrichment itself and
never spends an AI call on its own initiative — the user decides when to
enrich. Every job read includes a `duplicate_summary`
(`total_candidates`, `eligible_candidates`, `skipped_not_enriched`,
`likely_count`, `possible_count`, `none_count`), computed fresh each time,
so "nothing flagged because nothing was comparable yet" is always
distinguishable from "compared and genuinely found nothing."

Three layers, most to least trusted, applied only to eligible pairs:

1. **Hard compatibility filters** — a pair failing any of these is never
   scored, no matter how similar anything else looks: `selling_mode` must
   match; for `unit` products, a known, differing `package_weight` (e.g.
   250g vs 500g) disqualifies the pair; a known, differing
   `flavor_variant` disqualifies the pair; a known, differing `barcode`
   disqualifies the pair. Missing data (nulls) is treated as
   *inconclusive*, never as proof of a match — two null flavors don't
   count as "the same flavor."
2. **Exact non-null barcode match** — the strongest possible signal;
   short-circuits straight to a maximal score once the hard filters above
   already passed.
3. Otherwise, a score **normalized over only the metadata fields
   applicable to that specific pair** (known on both sides), plus a
   **capped** perceptual-hash (`imagehash`, phash) image-similarity
   contribution that can only ever *nudge* an already-plausible metadata
   match — image similarity alone can never reach the "possible"
   threshold by itself. Normalizing over applicable evidence (rather than
   always dividing by the full brand+name+category+flavor+weight total)
   is a deliberate fix: previously, a pair with a legitimately null
   brand/flavor/package_weight on both sides (a common, honest outcome —
   e.g. a bulk item with no legible brand) could never mathematically
   reach the "possible" threshold even with a perfect name+category
   match, since the achievable ceiling (0.55) sat below it (0.60). Now
   the ceiling scales with what's actually knowable for that pair, so
   null fields no longer permanently penalize a real match.

Scores map to `duplicate_status`: `not_checked` (not yet eligible) →
`none` (compared, no qualifying match) → `possible` (score ≥ 0.60) →
`likely` (score ≥ 0.90, or any barcode match). Every qualifying pair is
stored as a directed pairwise row (`digitized_product_duplicate_matches`,
both directions) with its own `score` and `reasons` (e.g.
`["barcode_match"]` or `["brand_match", "name_similarity:0.88"]`), and
transitively-linked candidates (e.g. five identical packages) share one
`duplicate_group_id` via a union-find grouping pass.

**Milestone 6 only FLAGS — it never merges or deletes anything.**
`POST /api/digitizer/jobs/{id}/detect-duplicates` is safe to call
repeatedly (always recomputes that job's results from scratch, never
accumulates stale rows) and never mutates a `DigitizedProduct`'s core
fields. **Milestone 7 owns the actual human decision** (merge vs. keep
separate) — nothing here implements that.

### Dependencies added

`imagehash` (pure Python + Pillow/numpy/scipy, no model file — supporting
evidence only) and `rembg` + `onnxruntime` (CPU build) for the optional
Tier 2 isolation. No `torch`/`torchvision`/CLIP/embedding model was added
anywhere. `rembg` itself pulls in `opencv-python-headless` as its own
transitive dependency (internal array/image utilities) — this project's
own code never imports `cv2` directly, and this is unrelated to the
classical-CV *detection* approach (contour/MSER) removed before
Milestone 4's merge.

## Milestone 7 — Human Review & Approval

Turns AI drafts into an actual catalog: a reviewer inspects each
`DigitizedProduct`, edits it, resolves any duplicate flags, and approves it
into a real `Product`. Every review/edit/approve/reject/merge/keep-separate
action in this milestone costs **$0** — nothing here calls OpenRouter or
any other AI service. This milestone intentionally does **not** include:

- User/account auditing on review actions (who approved what) — that
  belongs to Milestone 11, once real authentication exists.
- Cart/checkout calculations for weight-based pricing (Milestone 9/10).
- A general Category management UI (only a read-only picker is added here).
- Automatically triggering enrichment/refinement/OpenRouter from the review
  page — a reviewer can still trigger those *existing* Milestone 5/6 manual
  actions, but nothing in Milestone 7 calls them on its own.

### Review lifecycle (`ReviewStatus`)

`PENDING_REVIEW` → (`DRAFT` ⇄ `PENDING_REVIEW`) → `APPROVED` | `REJECTED`,
plus a separate terminal `MERGED` state. `PENDING_REVIEW` is where every
candidate starts (Milestone 4 creates it; no human has looked at it yet) —
**deliberately distinct from `DRAFT`**, which means a human explicitly
opened the product and saved it as knowingly incomplete. A "Needs Review"
filter means `PENDING_REVIEW`, never `DRAFT`. This reuses the
`review_status` column and `DRAFT`/`APPROVED`/`REJECTED`/`MERGED` values
that have existed since Milestone 2 (only `PENDING_REVIEW` is new), rather
than introducing a second, competing status field — see
`app/models/enums.py::ReviewStatus`. A dedicated `reviewed_at` timestamp is
stamped by **any** human action on a product's own content (field edit,
draft save, approve, reject) and `approved_at` by approval specifically;
neither is a user/account audit trail (see scope above).

Migration `alembic/versions/f2c6a4e9b1d5_add_m7_review_fields.py` adds
`PENDING_REVIEW` to the existing Postgres `review_status` enum type (via
`autocommit_block`, since Postgres cannot add and use a new enum value in
the same transaction) and reclassifies every pre-existing `draft` row to
`pending_review` — those rows were created by Milestone 4 and never
actually touched by a human reviewer, since Milestone 7 is the first thing
that ever set `DRAFT` deliberately.

### Human-editable fields, and why AI edits stop mattering once a human touches one

A reviewer can edit: `name_en`, `name_ar`, `description_en`,
`description_ar`, `category_id`, `brand`, `flavor_variant`, `selling_mode`,
`package_weight`, `barcode`, plus the two fields Milestone 7 itself adds
(`price`, `stock_status`) — via `DigitizedProductReviewUpdate`
(`app/schemas/digitized_product.py`), deliberately narrower than the
full model so a reviewer can never touch AI-confidence/bbox/raw-result/
status-machine fields by mistake.

**Human edits are authoritative.** Saving any edit through this schema
stamps `reviewed_at`, and `digitizer_enrichment_service.enrich_digitized_product`
refuses outright (`409`) once `reviewed_at` is set — re-enrichment is
disabled rather than silently overwriting a human's reviewed changes. The
existing per-item/per-job "Enrich" actions still work normally for
never-reviewed products.

### Pricing and stock — AI never sets a price

`DigitizedProduct.price` (and the mirrored `Product.price`) is a single
field whose **meaning depends on `selling_mode`**, exactly like
`Product.price` already worked before this milestone:

- **`WEIGHT`** products: `price` is the price **per kilogram**;
  `package_weight` must be `NULL` (enforced at approval — a loose/bulk good
  has no fixed package to weigh).
- **`UNIT`** products: `price` is the **fixed price for one unit/package**;
  `package_weight` may optionally describe the item's physical net weight
  (e.g. a printed "500g" on a bag) but carries no pricing meaning by
  itself.

No AI service in this project ever populates `price` — it is absent from
every Milestone 4/5 AI response schema, and `EnrichmentStatus`/
`DetectedProduct` have no price field for it to occupy even accidentally.
`stock_status` reuses the exact `StockStatus` enum `Product` already had
since Milestone 2 (`in_stock`/`low_stock`/`out_of_stock`), not a second
competing enum.

For a future storefront, this shop's own weight convention is: **1 ounce
≈ 100g, 5 oz ≈ 0.5kg, 10 oz ≈ 1kg** — documented here for later milestones
(cart/checkout, Milestone 9/10); nothing in Milestone 7 performs this
conversion.

### Reviewing images: three files, never destroyed

The review UI shows all three images a `DigitizedProduct` can have side by
side — the original source photo, the Milestone 4 crop, and the Milestone
6 refined image (when it exists) — so a reviewer can always fall back to
inspecting the crop even when refinement failed, was skipped (no crop to
refine from), or was simply never run. Nothing in this milestone deletes
or overwrites any of the three; approval prefers the refined image when
present, falling back to the crop otherwise (see "Approval" below).
**The review page never auto-triggers a refinement call** — "Refine"/
"Re-refine" remain explicit, existing, separately-billed Milestone 6
actions.

### Approval validation — stricter than draft, looser than "complete"

`digitizer_review_service.validate_for_approval` requires: English name,
Arabic name, category, selling mode, a valid positive price, at least one
product image (crop or refined), and — for `WEIGHT` products only —
`package_weight` must be empty. It never requires barcode, brand, or
flavor/variant, since plenty of real products genuinely lack one. Every
failure reason is a plain English sentence returned together (`422`), e.g.
*"English name is required. A valid, positive price is required."* — never
a single generic "invalid" error. `DRAFT` saves go through the much looser
`DigitizedProductReviewUpdate` schema instead and can be arbitrarily
incomplete; `REJECT` has no completeness requirement at all.

**The frontend's required-field asterisks (`*`) mirror this list exactly**
— English name, Arabic name, Category, Selling mode, Price, and a "Product
Image *" note near the image section — and nothing else
(`client/src/components/review/ReviewProductDetail.tsx::RequiredMark`).
There is deliberately no second, hand-rolled frontend validator: on a
failed approval, the backend's exact reason sentences are shown as a
bulleted list in the detail panel, and the user's in-progress edits are
never reset or lost (the failed approve attempt still auto-saves the
current field edits via the same PATCH the "Save" button uses — only the
approval step itself fails).

### `DigitizedProduct` → `Product`: transactional, idempotent, traceable

Approval reuses the `DigitizedProduct.product_id` foreign key that has
existed, unused, since Milestone 2 — not a second, competing link.
`digitizer_review_service._upsert_catalog_product`:

- If `product_id` is unset, creates a new `Product` (SKU derived
  deterministically from the `DigitizedProduct`'s own UUID: `DP-<hex>` —
  guaranteed unique without a separate generation/retry scheme) and links
  it back.
- If `product_id` is already set, **updates that same row** instead.

This makes approval **idempotent**: clicking "Approve" twice (or
re-approving after an edit) never creates a second `Product` — it always
targets the same linked row, inside one DB transaction alongside the
`DigitizedProduct`'s own status/timestamp update. A barcode collision with
a *different* existing `Product` is rejected (`409`) before either row is
touched, rather than surfacing as a raw database integrity error.
`Product.image`/`source_image` store the existing safe digitizer media
endpoint URL (`/api/digitizer/jobs/{job_id}/media/...`) rather than
copying files into a separate Product-owned media tree — a deliberate,
documented Milestone 7 simplification revisitable in a later milestone.
`Product.unit` (a plain string, pre-existing Milestone 2 gap, not
redesigned here) stores the `selling_mode` value; `Product.weight` stores
`package_weight`.

### Duplicate resolution: per-relationship, not per-product

**Audit fix (post-initial-M7): resolution is tracked per pairwise
relationship, not as a single flag on each product.** The first M7 cut put
`duplicate_resolution` on `DigitizedProduct` itself; that cannot represent
"A/B is resolved but A/C is still unresolved" — resolving one relationship
incorrectly silenced the warning for *every* relationship that product was
part of. `DuplicateResolution` (`unresolved` / `kept_separate` / `merged`)
now lives on `DigitizedProductDuplicateMatch.resolution` — the row that
already models one specific relationship — and is set on **both** directed
rows for a resolved pair (or every pairwise combination within a resolved
group). `DigitizedProduct.duplicate_resolution` still exists but is now
only ever meaningfully `MERGED` (a fact about the product itself, set
alongside `review_status=MERGED`); it is no longer read for gating
anything.

**The single source of truth** is `DigitizedProduct.has_unresolved_duplicates`
(a computed property, exposed on every `DigitizedProductRead`): true iff at
least one of a product's match rows still has `resolution=UNRESOLVED`.
Every consumer — the review list's badges, the "Duplicates" filter tab
(`client/src/components/review/ReviewFilterTabs.tsx::isUnresolvedDuplicate`),
the detail panel's warning section, and bulk-approve's gating check — reads
this one property (plus `review_status != MERGED`, since a merged-away
record is locked/terminal regardless of what its own matches say) rather
than each re-deriving its own version from `duplicate_status` or the
historical existence of a match.

Resolving a pair as **Keep Separate** marks both directed rows for that
pair `kept_separate`; a relationship with a product *outside* the resolved
set is untouched. Both products remain fully, independently reviewable and
approvable, and no historical `DigitizedProductDuplicateMatch` evidence is
ever deleted — the review detail panel shows resolved matches in a
separate, non-actionable "Duplicate history" section rather than hiding
them outright.

**Merging never deletes anything.** A reviewer opens one candidate and
merges a compared match into it (that open candidate becomes the
canonical survivor for that action — a simple, deterministic choice that
avoids a separate canonical-picker widget); the merged-away record is kept
in full, flipped to `review_status=MERGED` (a terminal state) and linked
back via `merged_into_id` — this is exactly what stops it from later being
approved *or edited* independently (`409` from both the approve and review
endpoints). The specific relationship(s) the merge settles (canonical↔each
merged candidate, and candidate↔candidate when merging more than one at
once) are marked `resolution=MERGED`; any *other* relationship either
product has with a third product is untouched and, if still unresolved,
keeps that warning showing on its own. The canonical record itself is not
otherwise modified by the merge — the reviewer edits it normally
afterward, same as any other product; a full field-by-field merge UI was
judged unnecessary complexity for this milestone. A candidate that is
**already `APPROVED`** (has its own linked `Product`) cannot be merged
away — this is refused outright (`409`) rather than silently leaving two
independently-approved catalog products.

One known, accepted interaction: Milestone 6's `detect-duplicates` rerun
still clears and recomputes a job's match rows from scratch (unchanged,
per this audit's scope) — a resolution recorded against a match row is
naturally cleared along with it on a rerun, requiring fresh review. This
is judged *more* correct than the pre-audit behavior (a per-product flag
that silently kept applying to a since-changed match), not a regression.

### Bulk approval: stricter than one-by-one, not more lenient

`POST /api/digitizer/products/bulk-approve` runs the **same**
`validate_for_approval` check per product as single approval, plus one
bulk-only safety rule: a product that **still has an unresolved duplicate
relationship** (`has_unresolved_duplicates`) is refused in bulk, even
though a single, deliberate "Approve" click on that exact product (a
reviewer looking right at it) is still allowed — a batch action must never
make that judgment call on the reviewer's behalf. A product whose only
duplicate relationship was already merged or explicitly kept separate is
**not** blocked — only a genuinely outstanding one is. A product that
fails any
check is left **completely unchanged** and reported in the response's
`failed` list with its specific reasons; one product's failure never
blocks or rolls back another's approval in the same batch. Bulk-approve
never merges duplicates itself.

### API endpoints added

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/digitizer/products` | Cross-job listing (bounded, limit 200) for the review admin UI — client-side tab filtering, a deliberate simplification at this milestone's scale. |
| `GET` | `/api/digitizer/categories` | Read-only category listing for the review edit form's category picker. |
| `PATCH` | `/api/digitizer/products/{id}/review` | Human field edit; may set `review_status` to `DRAFT` only. |
| `POST` | `/api/digitizer/products/{id}/approve` | Validate, then create/update the linked `Product` (idempotent). |
| `POST` | `/api/digitizer/products/{id}/reject` | No completeness requirement. |
| `POST` | `/api/digitizer/products/duplicates/keep-separate` | Marks a set of products' duplicate flags resolved. |
| `POST` | `/api/digitizer/products/duplicates/merge` | `{canonical_id, merge_ids}` — merges candidates into one survivor. |
| `POST` | `/api/digitizer/products/bulk-approve` | `{product_ids}` — approves everything that individually passes. |

### Admin UI: a second top-level view, not a redesign

`client/src/App.tsx` gained a small nav switcher between the existing
Digitizer page and a new **Review & Approval** page
(`client/src/pages/ReviewPage.tsx`) — no router library was introduced, in
keeping with the existing app's simple component-switching approach. The
review page has filter tabs (**All / Needs Review / Draft / Approved /
Rejected / Duplicates**), a checkbox-selectable product list (badges make
review status, human-reviewed-vs-AI-only, unresolved duplicate flags, and
missing enrichment/refinement all visible at a glance), and a detail panel
per selected product with the structured edit form, the three-image
comparison, an inline duplicate-comparison-and-resolution section when
applicable, and Save / Save as Draft / Approve / Reject actions. A bulk
action bar reports exactly which selected products were approved and why
any others were not.

## Project Structure

```
wehbi-nuts/
├── client/                       # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.test.tsx
│   │   ├── main.tsx
│   │   ├── index.css              # Tailwind v4 entrypoint
│   │   ├── pages/                  # DigitizerPage, ReviewPage (+ their tests)
│   │   ├── components/digitizer/   # FileDropzone, SelectedFileList, JobHistory
│   │   ├── components/review/      # Review filter tabs, product list, detail/edit panel (Milestone 7)
│   │   ├── api/digitizer.ts        # Typed fetch client for the digitizer + review API
│   │   ├── types/digitizer.ts      # Shared frontend types
│   │   ├── config/                 # API base URL + upload limits (UX only)
│   │   └── test/setup.ts
│   ├── .env.example
│   └── package.json
├── server/                       # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app, CORS, router registration
│   │   ├── api/                    # Route handlers (health, digitizer, review)
│   │   ├── core/                   # Config / settings
│   │   ├── db/                     # Engine, session, declarative base, GUID type
│   │   ├── models/                 # SQLAlchemy models + enums
│   │   ├── schemas/                # Pydantic create/update/read schemas
│   │   └── services/
│   │       ├── ai/                  # AIProductAnalyzer + OpenRouterVisionDigitizer
│   │       ├── digitizer_service.py            # upload (Milestone 3)
│   │       ├── digitizer_processing_service.py # AI processing (Milestone 4)
│   │       ├── digitizer_enrichment_service.py # AI enrichment (Milestone 5)
│   │       ├── image_refinement_service.py     # Tier 1/2 refinement (Milestone 6)
│   │       ├── digitizer_refinement_service.py # refinement orchestration (Milestone 6)
│   │       ├── duplicate_detection_service.py  # duplicate flagging (Milestone 6)
│   │       ├── digitizer_review_service.py     # review/approval/merge (Milestone 7)
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

### Seeding initial categories (Milestone 7, dev convenience)

Milestone 7 approval requires a real `category_id` (see "Approval
validation" under Milestone 7 below), but a fresh database has no
`Category` rows at all — nothing before Milestone 7 ever created one — so
approval could never be completed end-to-end without first creating some.
After migrating, from `server/` with the virtual environment activated and
`DATABASE_URL` configured:

```powershell
python -m app.scripts.seed_categories
```

Creates a practical starting set (Nuts, Seeds, Dried Fruits, Coffee,
Spices & Herbs, Sweets & Chocolate, Spreads, Syrups & Molasses, Snacks,
Other) as real `Category` rows — never a hardcoded frontend list or a
closed code enum, since categories are meant to become admin-manageable
later. **Idempotent**: matched by `slug` (already unique in the schema);
running it again creates nothing new and never modifies or deletes a
category that already exists, including one an admin has since renamed.
See `app/scripts/seed_categories.py` for the exact list and behavior.

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
