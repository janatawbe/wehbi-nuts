"""add milestone 7 human review fields (price, stock_status, reviewed_at,
approved_at, merged_into_id, duplicate_resolution, review_status.pending_review)

Revision ID: f2c6a4e9b1d5
Revises: e5b2f9a1c3d7
Create Date: 2026-09-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'f2c6a4e9b1d5'
down_revision: Union[str, Sequence[str], None] = 'e5b2f9a1c3d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    duplicate_resolution = sa.Enum(
        'unresolved', 'kept_separate', 'merged', name='duplicate_resolution'
    )
    duplicate_resolution.create(op.get_bind(), checkfirst=True)

    # `stock_status` already exists as a Postgres enum type (created for
    # Milestone 2's `products` table) -- reused as-is for the new column
    # below, not recreated. checkfirst=True makes this a safe no-op if the
    # type is already present (e.g. on SQLite test databases, which don't
    # use Alembic at all and won't reach this line).
    stock_status = sa.Enum('in_stock', 'low_stock', 'out_of_stock', name='stock_status')
    stock_status.create(op.get_bind(), checkfirst=True)

    # PostgreSQL cannot add a new enum VALUE and then use it in the same
    # transaction (pre-PG12 rejects it outright; even on PG12+ it is not
    # guaranteed safe within one transaction block) -- run this one
    # statement in its own autocommit block so the value is durably
    # committed before the data migration below references it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE review_status ADD VALUE IF NOT EXISTS 'pending_review'")

    op.add_column('digitized_products', sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_check_constraint(
        'ck_digitized_products_price_non_negative', 'digitized_products', 'price IS NULL OR price >= 0'
    )
    op.add_column(
        'digitized_products',
        sa.Column('stock_status', stock_status, nullable=False, server_default='in_stock'),
    )
    op.alter_column('digitized_products', 'stock_status', server_default=None)

    op.add_column(
        'digitized_products', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'digitized_products', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'digitized_products',
        sa.Column(
            'duplicate_resolution', duplicate_resolution, nullable=False, server_default='unresolved'
        ),
    )
    op.alter_column('digitized_products', 'duplicate_resolution', server_default=None)

    op.add_column(
        'digitized_products', sa.Column('merged_into_id', app.db.types.GUID(), nullable=True)
    )
    op.create_index(
        op.f('ix_digitized_products_merged_into_id'), 'digitized_products', ['merged_into_id']
    )
    op.create_foreign_key(
        'fk_digitized_products_merged_into_id_digitized_products',
        'digitized_products',
        'digitized_products',
        ['merged_into_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Every existing row currently sitting at the M2-era default ('draft')
    # was created by M4 and has never actually been touched by a human
    # reviewer (Milestone 7 -- the first thing to ever set DRAFT
    # deliberately -- did not exist before this migration). Reclassify
    # them to the new, more accurate 'pending_review' so DRAFT keeps its
    # new, narrower meaning ("a human explicitly saved this as
    # incomplete") from this point on.
    op.execute("UPDATE digitized_products SET review_status = 'pending_review' WHERE review_status = 'draft'")


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse the data migration first (best-effort: any row a human has
    # since moved to a real 'draft' during normal M7 usage is left alone,
    # since it is no longer distinguishable from a pre-M7 default row and
    # reverting it would be incorrect).
    op.execute("UPDATE digitized_products SET review_status = 'draft' WHERE review_status = 'pending_review'")

    op.drop_constraint(
        'fk_digitized_products_merged_into_id_digitized_products', 'digitized_products', type_='foreignkey'
    )
    op.drop_index(op.f('ix_digitized_products_merged_into_id'), table_name='digitized_products')
    op.drop_column('digitized_products', 'merged_into_id')

    op.drop_column('digitized_products', 'duplicate_resolution')
    op.drop_column('digitized_products', 'approved_at')
    op.drop_column('digitized_products', 'reviewed_at')
    op.drop_column('digitized_products', 'stock_status')

    op.drop_constraint('ck_digitized_products_price_non_negative', 'digitized_products', type_='check')
    op.drop_column('digitized_products', 'price')

    sa.Enum(name='duplicate_resolution').drop(op.get_bind(), checkfirst=True)

    # NOTE: PostgreSQL has no `ALTER TYPE ... DROP VALUE` -- the
    # 'pending_review' value added to the existing `review_status` enum
    # type in upgrade() cannot be cleanly removed here. This is a known,
    # accepted PostgreSQL limitation for enum-value additions (as opposed
    # to whole new enum types, which this project's other migrations
    # create and drop wholesale). The stray value is harmless once no row
    # references it (enforced by the data-migration reversal above).
