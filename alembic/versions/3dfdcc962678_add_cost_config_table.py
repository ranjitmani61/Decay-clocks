"""add_cost_config_table

Revision ID: 1a2b3c4d5e6f
Revises: 9f1e2d3c4b5a
Create Date: 2026-04-30 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = '1a2b3c4d5e6f'
down_revision = '9f1e2d3c4b5a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cost_config',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('active', sa.Boolean, default=True),
        sa.Column('weights', JSON, nullable=False),
        sa.Column('C_err', sa.Float, nullable=False),
        sa.Column('C_int', sa.Float, nullable=False),
        sa.Column('provisional_hazard', sa.Float, nullable=False),
        sa.Column('floor_axes', JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    # Set the first row as active default
    pass  # INSERT removed for safety
