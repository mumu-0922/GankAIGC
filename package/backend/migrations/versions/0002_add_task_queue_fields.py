"""add task queue fields

Revision ID: 0002_add_task_queue_fields
Revises: 0001_initial_postgresql_schema
Create Date: 2026-04-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_task_queue_fields"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("optimization_sessions", sa.Column("queued_at", sa.DateTime(), nullable=True))
    op.add_column("optimization_sessions", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("optimization_sessions", sa.Column("finished_at", sa.DateTime(), nullable=True))
    op.add_column("optimization_sessions", sa.Column("worker_id", sa.String(length=100), nullable=True))
    op.execute("UPDATE optimization_sessions SET queued_at = created_at WHERE queued_at IS NULL")
    op.create_index(op.f("ix_optimization_sessions_queued_at"), "optimization_sessions", ["queued_at"], unique=False)
    op.create_index(op.f("ix_optimization_sessions_worker_id"), "optimization_sessions", ["worker_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_optimization_sessions_worker_id"), table_name="optimization_sessions")
    op.drop_index(op.f("ix_optimization_sessions_queued_at"), table_name="optimization_sessions")
    op.drop_column("optimization_sessions", "worker_id")
    op.drop_column("optimization_sessions", "finished_at")
    op.drop_column("optimization_sessions", "started_at")
    op.drop_column("optimization_sessions", "queued_at")
