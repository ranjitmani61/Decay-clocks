"""add status_changed_at to nodes

Revision ID: 610b8e789ec2
Revises: 4406be7c61e8
Create Date: 2026-04-28 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '610b8e789ec2'
down_revision = '4406be7c61e8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('nodes', sa.Column('status_changed_at', sa.DateTime(timezone=True),
                                     server_default=sa.text('now()'), nullable=True))
    op.execute("UPDATE nodes SET status_changed_at = registration_time WHERE status_changed_at IS NULL")

def downgrade() -> None:
    op.drop_column('nodes', 'status_changed_at')
