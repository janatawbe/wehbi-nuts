"""add ai digitizer fields to digitized_products

Revision ID: a1f3c9d4e6b2
Revises: c02c05b2c953
Create Date: 2026-09-10 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9d4e6b2'
down_revision: Union[str, Sequence[str], None] = 'c02c05b2c953'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    presentation_type = sa.Enum(
        'packaged', 'jar', 'bottle', 'bulk_tray', 'bulk_loose', 'other',
        name='presentation_type',
    )
    identification_basis = sa.Enum(
        'visual', 'text', 'visual_and_text', name='identification_basis',
    )
    presentation_type.create(op.get_bind(), checkfirst=True)
    identification_basis.create(op.get_bind(), checkfirst=True)

    op.add_column('digitized_products', sa.Column('category_suggestion', sa.String(length=255), nullable=True))
    op.add_column('digitized_products', sa.Column('presentation', presentation_type, nullable=True))
    op.add_column('digitized_products', sa.Column('identification_basis', identification_basis, nullable=True))
    op.add_column('digitized_products', sa.Column('visible_text', sa.Text(), nullable=True))
    op.add_column('digitized_products', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('digitized_products', sa.Column('bbox_x', sa.Integer(), nullable=True))
    op.add_column('digitized_products', sa.Column('bbox_y', sa.Integer(), nullable=True))
    op.add_column('digitized_products', sa.Column('bbox_width', sa.Integer(), nullable=True))
    op.add_column('digitized_products', sa.Column('bbox_height', sa.Integer(), nullable=True))

    op.create_check_constraint(
        'ck_digitized_products_bbox_x_non_negative', 'digitized_products', 'bbox_x IS NULL OR bbox_x >= 0'
    )
    op.create_check_constraint(
        'ck_digitized_products_bbox_y_non_negative', 'digitized_products', 'bbox_y IS NULL OR bbox_y >= 0'
    )
    op.create_check_constraint(
        'ck_digitized_products_bbox_width_positive', 'digitized_products', 'bbox_width IS NULL OR bbox_width > 0'
    )
    op.create_check_constraint(
        'ck_digitized_products_bbox_height_positive', 'digitized_products', 'bbox_height IS NULL OR bbox_height > 0'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_digitized_products_bbox_height_positive', 'digitized_products', type_='check')
    op.drop_constraint('ck_digitized_products_bbox_width_positive', 'digitized_products', type_='check')
    op.drop_constraint('ck_digitized_products_bbox_y_non_negative', 'digitized_products', type_='check')
    op.drop_constraint('ck_digitized_products_bbox_x_non_negative', 'digitized_products', type_='check')

    op.drop_column('digitized_products', 'bbox_height')
    op.drop_column('digitized_products', 'bbox_width')
    op.drop_column('digitized_products', 'bbox_y')
    op.drop_column('digitized_products', 'bbox_x')
    op.drop_column('digitized_products', 'notes')
    op.drop_column('digitized_products', 'visible_text')
    op.drop_column('digitized_products', 'identification_basis')
    op.drop_column('digitized_products', 'presentation')
    op.drop_column('digitized_products', 'category_suggestion')

    sa.Enum(name='identification_basis').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='presentation_type').drop(op.get_bind(), checkfirst=True)
