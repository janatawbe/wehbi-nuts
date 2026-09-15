"""add order_items.product_name_ar snapshot

Revision ID: 4bdb5473d1b7
Revises: cbd8968fc2ee
Create Date: 2026-09-15 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bdb5473d1b7'
down_revision: Union[str, Sequence[str], None] = 'cbd8968fc2ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable snapshot of Product.name_ar at order time, alongside the
    # existing product_name (English) snapshot -- fixes a regression where
    # the storefront's Order Success page had no Arabic name to localize
    # with, since checkout only ever persisted the English name.
    op.add_column('order_items', sa.Column('product_name_ar', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('order_items', 'product_name_ar')
