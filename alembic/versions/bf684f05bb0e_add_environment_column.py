"""add environment column

Revision ID: 8a7b6c5d4e3f
Revises: 1a2b3c4d5e6f
Create Date: 2026-04-30 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '8a7b6c5d4e3f'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('nodes', sa.Column('environment', sa.String(), server_default='production'))
    op.add_column('cost_config', sa.Column('environment', sa.String(), server_default='production'))

def downgrade() -> None:
    op.drop_column('nodes', 'environment')
    op.drop_column('cost_config', 'environment')
