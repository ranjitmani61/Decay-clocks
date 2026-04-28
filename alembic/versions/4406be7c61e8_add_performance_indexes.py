"""add_performance_indexes

Revision ID: 4406be7c61e8
Revises: 2a0778657977
Create Date: 2026-04-28 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '4406be7c61e8'
down_revision = '2a0778657977'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index('ix_nodes_domain_tags_gin', 'nodes', ['domain_tags'],
                    postgresql_using='gin')
    op.create_index('ix_nodes_status', 'nodes', ['status'])
    op.create_index('ix_escalation_tasks_node_id', 'escalation_tasks', ['node_id'])
    op.create_index('ix_escalation_tasks_status', 'escalation_tasks', ['status'])
    op.create_index('ix_audit_log_node_id', 'audit_log', ['node_id'])

def downgrade() -> None:
    op.drop_index('ix_nodes_domain_tags_gin', table_name='nodes')
    op.drop_index('ix_nodes_status', table_name='nodes')
    op.drop_index('ix_escalation_tasks_node_id', table_name='escalation_tasks')
    op.drop_index('ix_escalation_tasks_status', table_name='escalation_tasks')
    op.drop_index('ix_audit_log_node_id', table_name='audit_log')
