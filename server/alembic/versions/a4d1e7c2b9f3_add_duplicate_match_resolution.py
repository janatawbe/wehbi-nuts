"""add per-relationship resolution to digitized_product_duplicate_matches

Milestone 7 audit fix: `DigitizedProduct.duplicate_resolution` is a single
flag per PRODUCT, which cannot correctly represent "A/B is resolved but
A/C is still unresolved" -- resolving one relationship was incorrectly
silencing warnings for every relationship that product was part of. The
smallest correct fix is to track resolution per PAIRWISE RELATIONSHIP
instead, on the table that already models relationships:
`digitized_product_duplicate_matches`. See
DigitizedProductDuplicateMatch.resolution and
DigitizedProduct.has_unresolved_duplicates.

Revision ID: a4d1e7c2b9f3
Revises: f2c6a4e9b1d5
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d1e7c2b9f3'
down_revision: Union[str, Sequence[str], None] = 'f2c6a4e9b1d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Reuses the `duplicate_resolution` enum type created by
    # f2c6a4e9b1d5 for DigitizedProduct.duplicate_resolution -- same three
    # values (unresolved/kept_separate/merged) apply per-relationship here.
    # checkfirst=True makes this a safe no-op given the type already
    # exists.
    duplicate_resolution = sa.Enum(
        'unresolved', 'kept_separate', 'merged', name='duplicate_resolution'
    )
    duplicate_resolution.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'digitized_product_duplicate_matches',
        sa.Column(
            'resolution', duplicate_resolution, nullable=False, server_default='unresolved'
        ),
    )
    op.alter_column('digitized_product_duplicate_matches', 'resolution', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('digitized_product_duplicate_matches', 'resolution')
    # The `duplicate_resolution` enum type itself is NOT dropped here --
    # it is still in use by DigitizedProduct.duplicate_resolution (created
    # by f2c6a4e9b1d5, which owns that type's lifecycle).
