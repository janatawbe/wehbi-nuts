"""add milestone 10 order item weight and selling mode fields

Revision ID: cbd8968fc2ee
Revises: a4d1e7c2b9f3
Create Date: 2026-09-15 12:25:32.824117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbd8968fc2ee'
down_revision: Union[str, Sequence[str], None] = 'a4d1e7c2b9f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # `selling_mode` already exists as a Postgres enum type (created for
    # Milestone 5's `digitized_products.selling_mode`) -- reused as-is
    # below, never recreated. checkfirst=True makes this a safe no-op if
    # the type is already present (e.g. on SQLite test databases, which
    # don't use Alembic at all and won't reach this line).
    selling_mode = sa.Enum('weight', 'unit', name='selling_mode')
    selling_mode.create(op.get_bind(), checkfirst=True)

    # Milestone 2's `quantity` was a plain item-count Integer, which
    # cannot represent a fractional-kilogram WEIGHT purchase (e.g. 0.300
    # for 300 g). Widened to Numeric(10, 3) -- the same precision
    # Product.weight already uses -- so it can hold either a kilogram
    # amount (weight-mode line) or a plain item count (unit-mode line,
    # e.g. 2.000) under one column. The existing
    # ck_order_items_quantity_positive CHECK ("quantity > 0") remains
    # valid unchanged across this type change.
    op.alter_column(
        'order_items',
        'quantity',
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=10, scale=3),
        postgresql_using='quantity::numeric(10,3)',
    )

    # No sensible default exists for `selling_mode` (unlike, say,
    # stock_status's natural 'in_stock' default in an earlier migration),
    # so this is added nullable first. The table is empty today (no Order
    # has ever been placed), so the immediate NOT NULL below succeeds as a
    # no-op backfill; if this ever runs against a database that already
    # has real OrderItem rows, the NOT NULL step below will fail loudly
    # instead of silently guessing a selling mode for historical data --
    # exactly the desired behavior.
    op.add_column('order_items', sa.Column('selling_mode', selling_mode, nullable=True))
    op.alter_column('order_items', 'selling_mode', nullable=False)

    # Snapshot of Product.weight (kg) at order time -- only ever set for a
    # UNIT line whose product has a known package weight; always NULL for
    # a WEIGHT line (see the model's own docstring). Purely descriptive,
    # never used in price calculations.
    op.add_column('order_items', sa.Column('package_weight', sa.Numeric(precision=10, scale=3), nullable=True))
    op.create_check_constraint(
        'ck_order_items_package_weight_non_negative',
        'order_items',
        'package_weight IS NULL OR package_weight >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_order_items_package_weight_non_negative', 'order_items', type_='check')
    op.drop_column('order_items', 'package_weight')

    op.drop_column('order_items', 'selling_mode')

    # NOTE: reverses cleanly only while every row's quantity is a whole
    # number (true for unit-mode lines; a genuine weight-mode purchase,
    # e.g. 0.300, cannot be cast back to Integer and this will fail --
    # expected, since Milestone 2's Integer column never could have
    # represented that value in the first place).
    op.alter_column(
        'order_items',
        'quantity',
        existing_type=sa.Numeric(precision=10, scale=3),
        type_=sa.Integer(),
        postgresql_using='quantity::integer',
    )

    # `selling_mode` the Postgres ENUM TYPE is NOT dropped here -- it is
    # shared with (and owned by) Milestone 5's
    # digitized_products.selling_mode column, which continues to need it.
