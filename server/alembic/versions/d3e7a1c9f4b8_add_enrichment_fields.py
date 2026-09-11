"""add milestone 5 enrichment fields (selling_mode, package_weight,
flavor_variant, field_review, enrichment_status)

Revision ID: d3e7a1c9f4b8
Revises: a1f3c9d4e6b2
Create Date: 2026-09-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e7a1c9f4b8'
down_revision: Union[str, Sequence[str], None] = 'a1f3c9d4e6b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    selling_mode = sa.Enum('weight', 'unit', name='selling_mode')
    enrichment_status = sa.Enum('pending', 'enriched', name='enrichment_status')
    selling_mode.create(op.get_bind(), checkfirst=True)
    enrichment_status.create(op.get_bind(), checkfirst=True)

    # `weight` and `unit` have existed since Milestone 2 but no code has
    # ever written to them (Milestone 4 doesn't populate them, and this is
    # the first migration that does) -- they are always NULL in any
    # existing database, so dropping them needs no data migration. They are
    # replaced outright rather than repurposed in place: the prior design
    # conflated HOW a product is sold with whether it happens to have a
    # printed package weight (a packaged 500g bag is still sold as one
    # UNIT, not "by weight"), which `selling_mode` + `package_weight` below
    # correct by keeping those two questions in separate, independent
    # columns.
    op.drop_column('digitized_products', 'weight')
    op.drop_column('digitized_products', 'unit')

    op.add_column('digitized_products', sa.Column('selling_mode', selling_mode, nullable=True))
    op.add_column('digitized_products', sa.Column('package_weight', sa.Numeric(10, 3), nullable=True))
    op.add_column('digitized_products', sa.Column('flavor_variant', sa.String(length=255), nullable=True))
    op.add_column('digitized_products', sa.Column('field_review', sa.JSON(), nullable=True))
    op.add_column(
        'digitized_products',
        sa.Column('enrichment_status', enrichment_status, nullable=False, server_default='pending'),
    )
    # Drop the server-side default once existing rows are backfilled by it --
    # matches how this project's other enum columns (e.g. review_status)
    # rely on the Python-side model default rather than a DB-level one.
    op.alter_column('digitized_products', 'enrichment_status', server_default=None)

    op.create_check_constraint(
        'ck_digitized_products_package_weight_non_negative',
        'digitized_products',
        'package_weight IS NULL OR package_weight >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_digitized_products_package_weight_non_negative', 'digitized_products', type_='check'
    )

    op.drop_column('digitized_products', 'enrichment_status')
    op.drop_column('digitized_products', 'field_review')
    op.drop_column('digitized_products', 'flavor_variant')
    op.drop_column('digitized_products', 'package_weight')
    op.drop_column('digitized_products', 'selling_mode')

    op.add_column('digitized_products', sa.Column('unit', sa.String(length=32), nullable=True))
    op.add_column('digitized_products', sa.Column('weight', sa.Numeric(precision=10, scale=3), nullable=True))

    sa.Enum(name='enrichment_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='selling_mode').drop(op.get_bind(), checkfirst=True)
