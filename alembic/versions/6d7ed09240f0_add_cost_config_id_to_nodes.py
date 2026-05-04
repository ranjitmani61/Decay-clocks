"""add cost_config_id to nodes

Revision ID: a1b2c3d4e5f6
Revises: 8a7b6c5d4e3f
Create Date: 2026-04-30 19:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'a1b2c3d4e5f6'
down_revision = '9b8c7d6e5f4a'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('nodes', sa.Column('cost_config_id', UUID(as_uuid=True),
                                     sa.ForeignKey('cost_config.id'), nullable=True))

def downgrade() -> None:
    op.drop_column('nodes', 'cost_config_id')
