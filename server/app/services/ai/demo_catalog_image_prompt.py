"""DEVELOPMENT/DEMO-ONLY prompt for generating catalog images for the
seeded `WN-DEMO-*` products (see app.scripts.reset_dev_catalog) that have
no real source photograph.

This is a deliberately SEPARATE prompt from
app.services.ai.image_refinement_prompt (Milestone 6's real Digitizer
image-editing prompt). The real Digitizer workflow (real shop photo ->
detection/crop -> AI refinement -> review) is completely unchanged and
never touches this module. This one is pure TEXT-TO-IMAGE generation --
there is no source photo to preserve, so none of Milestone 6's
"preserve the real input product" rules apply. Everything else (pure
white background, centered, generous whitespace, consistent scale,
soft studio lighting, subtle natural shadow, realistic, no hands/people/
props/text/price/watermark/invented branding) is reused so a generated
demo image visually matches the real Digitizer's catalog-image style.

Every one of the 18 demo products is presented as a natural, standalone
ingredient/product photograph (a clean pile for loose goods, a small
realistic grouping for discrete pieces) REGARDLESS of `selling_mode`.
This is a deliberate simplification: none of the demo records have any
real packaging design, label, or logo to preserve, and inventing one
would violate the "no invented branding/logo/label text" rule below --
so no demo product is ever rendered as packaged merchandise.
"""
from dataclasses import dataclass

SYSTEM_PROMPT = """\
You are generating a DEVELOPMENT/DEMO catalog product photograph for
Wehbi Nuts, a nuts, coffee, seeds, dried-fruit, confectionery, and
specialty-food store.

There is NO real source photograph for this product. Generate a
realistic, appetizing, professional product photograph purely from the
product information provided below -- as if it were shot in the same
studio, on the same day, by the same photographer, as the rest of this
store's catalog.

STYLE (must match the rest of the catalog):
- realistic professional e-commerce product photography
- pure clean white background (#FFFFFF)
- isolated product, nothing else in frame
- centered composition
- generous, consistent whitespace/margin around the product
- use the same slightly elevated, front-facing studio camera angle for
  every product in this catalog -- never a top-down flat-lay, never a
  low/dramatic angle
- maintain a consistent apparent product scale and framing across the
  catalog, as if every product were shot in the same session with the
  same lens and camera distance
- keep approximately the same amount of whitespace around each product,
  and have the product occupy roughly the same proportion of the canvas
  across images (see the 60-75% target below)
- soft, professional studio-style lighting
- a subtle, natural contact shadow beneath the product -- never dramatic
- appetizing but realistic: true-to-life colors and texture
- square output; the product should occupy roughly 60-75% of the frame

PRESENTATION
Present the product as a clean, natural, standalone pile or small
realistic grouping of the real item -- physically plausible, not a
rectangular block, not a flat texture pasted onto white, not stacked in
an artificial grid. A loose ingredient (nuts, seeds, dried fruit, ground
spice, coffee beans) should look like a small heap or mound. A discrete
packaged-style treat (a chocolate-coated piece, a candy) should look like
a few realistic pieces grouped together, not wrapped or boxed.

Do not depict this product inside any packaging, bag, box, jar, bottle,
or container of any kind.

Show ONLY the actual product itself -- nothing else mixed in. Even if the
product's description mentions a flavoring, spice, or ingredient used in
its preparation (e.g. cardamom in a coffee blend), do NOT render that
flavoring as a separate, visible whole piece (a pod, seed, leaf, sprig,
etc.) sitting in or beside the pile. A flavoring that has already been
ground/blended into the product may influence its color, but it must
never appear as its own distinct object in the frame.

REALISM
Avoid: illustration, painting, CGI appearance, plastic-looking texture,
excessive sharpening or smoothing, artificial symmetry, repeated cloned
pieces, obvious AI artifacts, impossible geometry, unrealistic colors.

STRICTLY FORBIDDEN -- never include:
- hands, people
- tables, counters, shop scenery, props
- plates, bowls, scoops, serving boards, napkins
- decorative leaves, garnish, herbs, or unrelated ingredients
- any green elements whatsoever -- no green pods, seeds, leaves, sprigs,
  herbs, or garnish of any kind, even if a green ingredient is mentioned
  in the product's description as a flavoring
- any text, price, promotional badge, or watermark
- any invented brand name, logo, or label

This is a plain product catalog image, not an advertisement or lifestyle
photograph.

FINAL CHECK BEFORE RETURNING THE IMAGE
- Is the background pure white?
- Is the product centered with generous, consistent whitespace?
- Does it look like real, professional e-commerce food photography --
  not an illustration?
- Is it free of any packaging, text, price, logo, or watermark?
- Is it free of any green elements, garnish, herbs, leaves, or unrelated
  ingredients -- does it show ONLY the actual product?
- Would this look visually consistent next to the rest of this catalog?

If any answer is no, correct the image before returning it.
"""


@dataclass(frozen=True)
class DemoProductImageContext:
    """Non-sensitive product metadata used to build the generation
    prompt. Deliberately excludes price, SKU, and every internal ID --
    matches RefinementProductContext's own exclusions (Milestone 6)."""

    name_en: str
    category: str | None
    selling_mode: str | None
    description_en: str | None


def build_product_context_text(context: DemoProductImageContext) -> str:
    """Short per-product instruction built from the Product's own
    catalog fields. Deliberately excludes price -- the AI must never see,
    invent, or be influenced by pricing."""
    lines = [f"Product: {context.name_en}"]
    if context.category:
        lines.append(f"Category: {context.category}")
    if context.selling_mode:
        lines.append(f"Selling mode: {context.selling_mode}")
    if context.description_en:
        lines.append(f"Description: {context.description_en}")
    lines.append(
        "Generate a standalone catalog product image of this product following "
        "the system instructions above."
    )
    return "\n".join(lines)


def build_prompt_text(context: DemoProductImageContext) -> str:
    """The full prompt text sent as the Images API's single `prompt`
    field -- system style rules, then the short per-product instruction."""
    return "\n\n".join([SYSTEM_PROMPT, build_product_context_text(context)])
