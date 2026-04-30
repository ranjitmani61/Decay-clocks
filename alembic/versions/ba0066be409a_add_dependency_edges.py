"""add_dependency_edges

Revision ID: 9f1e2d3c4b5a
Revises: 610b8e789ec2
Create Date: 2026-04-30 08:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = '9f1e2d3c4b5a'
down_revision = '610b8e789ec2'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'dependency_edges',
        sa.Column('edge_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parent_node_id', UUID(as_uuid=True), sa.ForeignKey('nodes.node_id'), nullable=False),
        sa.Column('child_node_id', UUID(as_uuid=True), sa.ForeignKey('nodes.node_id'), nullable=False),
        sa.Column('edge_type', sa.String(50), nullable=False),
        sa.Column('propagation_coeffs', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

def downgrade() -> None:
    op.drop_table('dependency_edges')
