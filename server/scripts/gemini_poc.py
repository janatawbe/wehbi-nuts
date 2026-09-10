"""Gemini Vision proof-of-concept for Milestone 4 (branch: milestone-4-gemini-digitizer).

Standalone, throwaway evaluation script -- NOT wired into the FastAPI app,
the database, or the Milestone 3 upload flow. Sends each image in
test-data/generated-shop-images/ to Gemini and asks it to identify complete
SELLABLE INVENTORY UNITS (a whole package/jar/bottle/tray, never a label,
logo, or individual piece inside one), returning structured JSON that is
then schema-validated on the client side as well (never trust an LLM's
"structured output" mode alone).

This script is intentionally not tuned to any specific image: the same
system instruction and schema are used for every file in the input
directory, and nothing here references a filename, expected count, or
expected product name.

Usage (from server/):
    venv/Scripts/python.exe scripts/gemini_poc.py

Requires GEMINI_API_KEY in server/.env. The key is read into memory only
and never printed/logged/written to any output file.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, ValidationError, field_validator

# --- Paths --------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVER_ROOT.parent

TEST_IMAGES_DIR = REPO_ROOT / "test-data" / "generated-shop-images"
OUTPUT_DIR = SCRIPT_DIR / "gemini_poc_output"  # gitignored; local review artifacts only

# --- Model --------------------------------------------------------------
#
# Verified live against the installed google-genai SDK (do not assume this
# without checking -- an earlier hardcoded guess, "gemini-1.5-flash", is no
# longer offered to new users at all, and even "gemini-2.5-flash" returned
# a 404 telling callers to move to "gemini-3.6-flash"). "gemini-3.6-flash"
# is confirmed available via client.models.get() and supports image input
# + generateContent as of this writing.
MODEL_NAME = "gemini-3.6-flash"

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5

# --- Structured output schema --------------------------------------------
#
# bbox coordinate convention: [ymin, xmin, ymax, xmax], each an integer in
# [0, 1000], normalized to the full image regardless of its actual pixel
# size (0,0 = top-left corner, 1000,1000 = bottom-right corner). This is
# stated explicitly in the prompt below (not left as an undocumented
# default) and is checked in `_validate_bbox`.

PRESENTATION_VALUES = ("packaged", "jar", "bottle", "bulk_tray", "bulk_loose", "other")
IDENTIFICATION_BASIS_VALUES = ("visual", "text", "visual_and_text")


class DetectedItem(BaseModel):
    name_en: str
    name_ar: str
    category: str
    presentation: Literal[PRESENTATION_VALUES]
    bbox: list[int] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)
    visible_text: str | None = None
    identification_basis: Literal[IDENTIFICATION_BASIS_VALUES]
    notes: str | None = None

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, value: list[int]) -> list[int]:
        for coordinate in value:
            if not (0 <= coordinate <= 1000):
                raise ValueError(f"bbox coordinate {coordinate} outside documented [0, 1000] range")
        ymin, xmin, ymax, xmax = value
        if ymin >= ymax or xmin >= xmax:
            raise ValueError(f"degenerate bbox {value}: min must be strictly less than max")
        return value


class DigitizationResult(BaseModel):
    items: list[DetectedItem]


# --- Prompt ---------------------------------------------------------------

SYSTEM_INSTRUCTION = """\
You are analyzing a photo for Wehbi Nuts, a nuts / coffee / sweets / \
snacks / dried-food and related roastery-shop inventory digitization \
system. The output will become product DRAFTS for an e-commerce catalog, \
so identify SELLABLE INVENTORY UNITS -- complete physical items a shop \
would sell as one unit -- not every visually distinct object in the \
photo.

Definition of one sellable unit, by physical presentation:
- Packaged product (bag/box/pouch/wrapped package): the WHOLE package is \
one item. Its label, logo, or printed panel is NOT a separate item.
- Jar or other container: the WHOLE jar/container is one item. Its lid, \
cap, sticker, or handwritten label is NOT a separate item.
- Bottle: the WHOLE bottle (body + neck + cap) is one item.
- Bulk product displayed in a tray/bin/container: the ENTIRE tray/bin of \
that product is one item. Individual nuts/snacks/pieces inside it are \
NOT separate items.
- Loose bulk product filling most/all of the photo with no visible \
packaging or container: return ONE item for the whole pile, not one \
item per nut/seed/bean/piece.
- A shelf/display with multiple different products: return each \
distinguishable complete sellable unit as its own item.
- Multiple separately visible physical units of the same product (e.g. \
two identical bags side by side): each physically separate unit may be \
returned as its own item.

Ignore entirely -- do not return any of these as items: shelves, shelf \
dividers, shelf edges, background, price tags that are not themselves a \
product, logos as separate objects, labels as separate objects, \
individual contents visible inside a package, individual pieces inside a \
bulk tray, decorations.

Product identification:
Many Wehbi Nuts products are sold loose/bulk with no barcode, no visible \
product name, no packaging, and no readable text at all. You may \
visually infer the likely product (from color, shape, texture) when \
there is no text to read. However:
- Never present a visually-inferred guess as if it had been read from \
text.
- Set "identification_basis" accurately: "visual" if inferred purely \
from appearance, "text" if read from visible printed/handwritten text, \
"visual_and_text" if both contributed.
- If not confident, give a low "confidence" score rather than inventing \
a confident-sounding identity. A generic category-level name (e.g. \
"Mixed Nuts") is fine when a more specific one is not visually \
justified.
- Put any actually visible/readable text (brand, product name, weight, \
etc.) in "visible_text", verbatim, in whatever language it is written. \
Set it to null if no legible text is visible on that item.
- "name_en" and "name_ar" are the product name in English and Arabic \
regardless of what script the visible text (if any) uses.

Bounding boxes:
Return "bbox" as [ymin, xmin, ymax, xmax], each an integer from 0 to \
1000, normalized to the full image regardless of its actual pixel \
dimensions (0,0 is the top-left corner, 1000,1000 is the bottom-right \
corner). The box must enclose the COMPLETE physical unit (e.g. the whole \
jar, not just its sticker) -- do not shrink it to just a label, logo, or \
visible content when the complete object is larger than that.

Only return items that are genuinely sellable inventory units by the \
definitions above. If the image contains no sellable product, return an \
empty items list.
"""

USER_PROMPT = "Analyze this shop photo and return the sellable inventory units as instructed."

_MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


@dataclass
class ImageResult:
    filename: str
    raw_json: dict | None = None
    parsed: DigitizationResult | None = None
    error: str | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    attempts: int = 0


def _call_gemini(client: genai.Client, image_path: Path) -> types.GenerateContentResponse:
    mime_type = _MIME_TYPES.get(image_path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"Unsupported image extension: {image_path.suffix}")
    image_bytes = image_path.read_bytes()

    return client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            USER_PROMPT,
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=DigitizationResult,
            temperature=0.2,
        ),
    )


def analyze_image(client: genai.Client, image_path: Path) -> ImageResult:
    result = ImageResult(filename=image_path.name)
    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result.attempts = attempt
        try:
            response = _call_gemini(client, image_path)
        except genai_errors.ServerError as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue
            result.error = f"Server error after {attempt} attempts: {exc}"
            return result
        except genai_errors.ClientError as exc:
            result.error = f"Client error (not retried): {exc}"
            return result
        except Exception as exc:  # noqa: BLE001 -- record and move on to the next image
            result.error = f"Unexpected error: {exc!r}"
            return result

        usage = response.usage_metadata
        if usage is not None:
            result.prompt_tokens = usage.prompt_token_count
            result.output_tokens = usage.candidates_token_count
            result.total_tokens = usage.total_token_count

        raw_text = response.text
        if not raw_text:
            result.error = "Empty response text from Gemini."
            return result

        try:
            result.raw_json = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            result.error = f"Response was not valid JSON: {exc}"
            return result

        try:
            result.parsed = DigitizationResult.model_validate(result.raw_json)
        except ValidationError as exc:
            result.error = f"Response did not match the expected schema: {exc}"
            return result

        return result

    if last_error is not None:
        result.error = f"Failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    return result


def _bbox_to_pixels(bbox: list[int], width: int, height: int) -> tuple[int, int, int, int]:
    ymin, xmin, ymax, xmax = bbox
    return (
        round(xmin / 1000 * width),
        round(ymin / 1000 * height),
        round(xmax / 1000 * width),
        round(ymax / 1000 * height),
    )


def annotate_image(image_path: Path, result: DigitizationResult, output_path: Path) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for index, item in enumerate(result.items, start=1):
        x1, y1, x2, y2 = _bbox_to_pixels(item.bbox, image.width, image.height)
        draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=3)
        label = f"{index}. {item.name_en} ({item.confidence:.2f})"
        text_y = max(0, y1 - 16)
        draw.rectangle([x1, text_y, x1 + 8 * len(label), text_y + 14], fill=(255, 0, 0))
        draw.text((x1 + 2, text_y), label, fill=(255, 255, 255))
    image.save(output_path)


def _print_ascii_summary(result: ImageResult) -> None:
    print(f"\n=== {result.filename} ===")
    if result.error:
        print(f"  ERROR: {result.error}")
        return
    assert result.parsed is not None
    print(f"  items: {len(result.parsed.items)}  (attempts: {result.attempts}, "
          f"tokens: prompt={result.prompt_tokens} output={result.output_tokens} total={result.total_tokens})")
    for index, item in enumerate(result.parsed.items, start=1):
        print(
            f"   {index}. [{item.presentation}] {item.name_en} / {item.name_ar}"
            f" -- category={item.category} confidence={item.confidence:.2f}"
            f" basis={item.identification_basis} bbox={item.bbox}"
        )
        if item.visible_text:
            print(f"      visible_text: {item.visible_text}")
        if item.notes:
            print(f"      notes: {item.notes}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console default (cp1252) cannot print Arabic

    load_dotenv(SERVER_ROOT / ".env")
    import os

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not set in server/.env")

    if not TEST_IMAGES_DIR.is_dir():
        raise SystemExit(f"Test image directory not found: {TEST_IMAGES_DIR}")

    image_paths = sorted(
        p for p in TEST_IMAGES_DIR.iterdir() if p.suffix.lower() in _MIME_TYPES
    )
    if not image_paths:
        raise SystemExit(f"No supported images found in {TEST_IMAGES_DIR}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    annotated_dir = OUTPUT_DIR / "annotated"
    annotated_dir.mkdir(exist_ok=True)
    raw_dir = OUTPUT_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)

    client = genai.Client(api_key=api_key)

    results: list[ImageResult] = []
    for image_path in image_paths:
        result = analyze_image(client, image_path)
        results.append(result)
        _print_ascii_summary(result)

        (raw_dir / f"{image_path.stem}.json").write_text(
            json.dumps(result.raw_json, ensure_ascii=False, indent=2) if result.raw_json is not None else "null",
            encoding="utf-8",
        )

        if result.parsed is not None:
            try:
                annotate_image(image_path, result.parsed, annotated_dir / f"{image_path.stem}_annotated.png")
            except Exception as exc:  # noqa: BLE001 -- annotation is best-effort, never fatal
                print(f"  (could not annotate: {exc!r})")

    total_prompt = sum(r.prompt_tokens or 0 for r in results)
    total_output = sum(r.output_tokens or 0 for r in results)
    total_all = sum(r.total_tokens or 0 for r in results)
    error_count = sum(1 for r in results if r.error)

    print("\n=== SUMMARY ===")
    print(f"images processed: {len(results)}")
    print(f"images with errors: {error_count}")
    print(f"total tokens: prompt={total_prompt} output={total_output} total={total_all}")
    print(f"raw responses written to: {raw_dir}")
    print(f"annotated images written to: {annotated_dir}")


if __name__ == "__main__":
    main()
