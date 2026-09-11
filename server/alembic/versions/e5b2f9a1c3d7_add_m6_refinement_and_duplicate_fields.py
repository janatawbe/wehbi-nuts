"""add milestone 6 image-refinement (incl. background_isolation_status)
and duplicate-detection fields

Revision ID: e5b2f9a1c3d7
Revises: d3e7a1c9f4b8
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types


# revision identifiers, used by Alembic.
revision: str = 'e5b2f9a1c3d7'
down_revision: Union[str, Sequence[str], None] = 'd3e7a1c9f4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    image_refinement_status = sa.Enum(
        'pending', 'refined', 'failed', 'skipped', name='image_refinement_status'
    )
    background_isolation_status = sa.Enum(
        'not_attempted', 'applied', 'rejected', name='background_isolation_status'
    )
    duplicate_status = sa.Enum('not_checked', 'none', 'possible', 'likely', name='duplicate_status')
    image_refinement_status.create(op.get_bind(), checkfirst=True)
    background_isolation_status.create(op.get_bind(), checkfirst=True)
    duplicate_status.create(op.get_bind(), checkfirst=True)

    op.add_column('digitized_products', sa.Column('refined_image', sa.String(length=512), nullable=True))
    op.add_column(
        'digitized_products',
        sa.Column(
            'image_refinement_status', image_refinement_status, nullable=False, server_default='pending'
        ),
    )
    op.add_column(
        'digitized_products',
        sa.Column(
            'background_isolation_status',
            background_isolation_status,
            nullable=False,
            server_default='not_attempted',
        ),
    )
    op.add_column(
        'digitized_products',
        sa.Column('duplicate_status', duplicate_status, nullable=False, server_default='not_checked'),
    )
    op.add_column(
        'digitized_products', sa.Column('duplicate_group_id', app.db.types.GUID(), nullable=True)
    )
    # Drop the server-side defaults once existing rows are backfilled by
    # them -- matches how this project's other enum columns (review_status,
    # enrichment_status) rely on the Python-side model default rather than
    # a DB-level one.
    op.alter_column('digitized_products', 'image_refinement_status', server_default=None)
    op.alter_column('digitized_products', 'background_isolation_status', server_default=None)
    op.alter_column('digitized_products', 'duplicate_status', server_default=None)

    op.create_index(
        op.f('ix_digitized_products_duplicate_group_id'), 'digitized_products', ['duplicate_group_id']
    )

    op.create_table(
        'digitized_product_duplicate_matches',
        sa.Column('product_id', app.db.types.GUID(), nullable=False),
        sa.Column('matched_product_id', app.db.types.GUID(), nullable=False),
        sa.Column('score', sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column('reasons', sa.JSON(), nullable=False),
        sa.Column('id', app.db.types.GUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.CheckConstraint('score >= 0 AND score <= 1', name='ck_duplicate_matches_score_range'),
        sa.CheckConstraint(
            'product_id != matched_product_id', name='ck_duplicate_matches_not_self_match'
        ),
        sa.ForeignKeyConstraint(['product_id'], ['digitized_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['matched_product_id'], ['digitized_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'matched_product_id', name='uq_duplicate_matches_pair'),
    )
    op.create_index(
        op.f('ix_digitized_product_duplicate_matches_product_id'),
        'digitized_product_duplicate_matches',
        ['product_id'],
    )
    op.create_index(
        op.f('ix_digitized_product_duplicate_matches_matched_product_id'),
        'digitized_product_duplicate_matches',
        ['matched_product_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_digitized_product_duplicate_matches_matched_product_id'),
        table_name='digitized_product_duplicate_matches',
    )
    op.drop_index(
        op.f('ix_digitized_product_duplicate_matches_product_id'),
        table_name='digitized_product_duplicate_matches',
    )
    op.drop_table('digitized_product_duplicate_matches')

    op.drop_index(op.f('ix_digitized_products_duplicate_group_id'), table_name='digitized_products')

    op.drop_column('digitized_products', 'duplicate_group_id')
    op.drop_column('digitized_products', 'duplicate_status')
    op.drop_column('digitized_products', 'background_isolation_status')
    op.drop_column('digitized_products', 'image_refinement_status')
    op.drop_column('digitized_products', 'refined_image')

    sa.Enum(name='duplicate_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='background_isolation_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='image_refinement_status').drop(op.get_bind(), checkfirst=True)
