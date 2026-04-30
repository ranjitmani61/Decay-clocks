"""add hazard_mode and dominant_axes to cost_config

Revision ID: 9b8c7d6e5f4a
Revises: 8a7b6c5d4e3f
Create Date: 2026-04-30 18:15:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = '9b8c7d6e5f4a'
down_revision = '8a7b6c5d4e3f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('cost_config', sa.Column('hazard_mode', sa.String(), server_default='linear'))
    op.add_column('cost_config', sa.Column('dominant_axes', JSON, server_default='[]'))

def downgrade() -> None:
    op.drop_column('cost_config', 'hazard_mode')
    op.drop_column('cost_config', 'dominant_axes')
