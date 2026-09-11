# Reference images (local development asset — not committed)

This directory holds **style/presentation reference photographs** used by
Milestone 6's AI image-refinement step to understand the *look* a refined
catalog image should have (composition, lighting, white background,
whitespace, natural pile arrangement, etc.).

**These are not application data.** They are never treated as products,
never stored in the database, and never sent to a customer. They are only
ever used as style guidance when calling an image-editing AI model — the
actual product shown in a refined image always comes from the real
Milestone 4 crop, never from a reference image.

**They are not committed to git** (`.gitignore` excludes everything in
this directory except this file) because they are typically third-party
product photography with no redistribution rights — only *style*, never
the pictured product itself, is meant to be referenced.

## Expected layout

```
server/reference-images/product-refinement/
    bulk-<description>.png      # loose/bulk nuts, seeds, dried fruit, etc.
    seeds-<description>.png     # loose seeds specifically
    packaged-<description>.png  # bags, boxes, jars, bottles
```

`app/services/reference_images.py` selects files by **filename prefix**,
matched against a product's `presentation`:

| Presentation | Matches filenames starting with |
|---|---|
| `bulk_tray`, `bulk_loose` | `bulk-`, `seeds-` |
| `packaged`, `jar`, `bottle` | `packaged-` |
| `other` / unknown | (none — no references are sent) |

To add more references, just drop a correctly-prefixed image file
(`.png`/`.jpg`/`.jpeg`/`.webp`) into `product-refinement/` — no code
change is required. A small, fixed number of references are selected per
request (see `MAX_REFERENCE_IMAGES` in `reference_images.py`) rather than
sending every matching file every time.

## Setting this up locally

This directory (and `product-refinement/` inside it) is not created
automatically. If you want to exercise the reference-image-selection code
path locally, create `server/reference-images/product-refinement/` and
add your own correctly-prefixed image files — they will never be picked
up by git.
