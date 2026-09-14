import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, JSON, Numeric, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import DuplicateResolution
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DigitizedProductDuplicateMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One directed pairwise duplicate-match record produced by Milestone
    6's within-job duplicate detection (app.services.duplicate_detection_service).

    Stored in BOTH directions per qualifying pair (a row from A to B and
    another from B to A) so "all matches for product X" is a single
    indexed lookup on `product_id` -- the small amount of duplicated data
    is trivial at this table's scale (at most a handful of candidates per
    job) and keeps every consumer (API, tests, a future Milestone 7 review
    UI) from having to special-case which side of a pair it's looking at.

    Never implies a merge -- this table only records evidence for a human
    to review later; nothing in Milestone 6 deletes or mutates a
    DigitizedProduct based on its presence.

    `resolution` (Milestone 7) is the HUMAN decision about THIS SPECIFIC
    pairwise relationship -- the actual source of truth for "does this
    product currently have an unresolved duplicate conflict" (see
    DigitizedProduct.has_unresolved_duplicates). This is deliberately
    per-relationship rather than a single flag on DigitizedProduct itself:
    a product can simultaneously have one resolved and one still-unresolved
    duplicate relationship (e.g. A/B merged, A/C still pending), which a
    single product-level field cannot represent correctly. A resolution
    action (merge or keep-separate) updates BOTH directed rows for the
    resolved pair(s), so a lookup from either side agrees. Rows are never
    deleted by a resolution action -- only detect_duplicates_for_job's own
    from-scratch recompute (Milestone 6, unchanged) replaces them, which is
    also the only way a resolution can go stale (see README).
    """

    __tablename__ = "digitized_product_duplicate_matches"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="ck_duplicate_matches_score_range"),
        CheckConstraint(
            "product_id != matched_product_id", name="ck_duplicate_matches_not_self_match"
        ),
        UniqueConstraint("product_id", "matched_product_id", name="uq_duplicate_matches_pair"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("digitized_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matched_product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("digitized_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    # Ordered list of short evidence tags, e.g. ["barcode_match"] or
    # ["brand_match", "name_similarity:0.88", "image_phash_similarity:0.71"]
    # -- see duplicate_detection_service for the exact vocabulary. Always a
    # non-empty explanation of why this pair was flagged.
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resolution: Mapped[DuplicateResolution] = mapped_column(
        SAEnum(
            DuplicateResolution,
            name="duplicate_resolution",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=DuplicateResolution.UNRESOLVED,
    )

    matched_product: Mapped["DigitizedProduct"] = relationship(  # noqa: F821
        "DigitizedProduct", foreign_keys=[matched_product_id]
    )

    @property
    def matched_name_en(self) -> str | None:
        """Convenience read-only accessor so the API schema can surface
        the matched product's name without the frontend needing a second
        lookup -- purely for display, never used by matching logic itself."""
        return self.matched_product.name_en if self.matched_product is not None else None
