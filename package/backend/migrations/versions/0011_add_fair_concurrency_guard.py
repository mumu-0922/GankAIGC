"""add fair-concurrency active-session guard

Revision ID: 0011_fair_concurrency_guard
Revises: 0010_task_events_worker_leases
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_fair_concurrency_guard"
down_revision = "0010_task_events_worker_leases"
branch_labels = None
depends_on = None


ACTIVE_STATUSES_SQL = "'processing', 'waiting_browser_agent'"


def upgrade() -> None:
    # Historical releases used one serial worker, so duplicate active sessions
    # should not normally exist. Requeue all but the oldest defensively before
    # installing the database-level invariant required by concurrent slots.
    op.execute(
        sa.text(
            f"""
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY user_id
                           ORDER BY started_at NULLS LAST, created_at, id
                       ) AS active_rank
                FROM optimization_sessions
                WHERE status IN ({ACTIVE_STATUSES_SQL})
            )
            UPDATE optimization_sessions AS sessions
            SET status = 'queued',
                queued_at = CURRENT_TIMESTAMP,
                started_at = NULL,
                finished_at = NULL,
                worker_id = NULL,
                updated_at = CURRENT_TIMESTAMP,
                error_message = '[v2.1.0 migration] duplicate active task requeued'
            FROM ranked
            WHERE sessions.id = ranked.id
              AND ranked.active_rank > 1
            """
        )
    )
    op.create_index(
        "uq_optimization_sessions_one_active_per_user",
        "optimization_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(f"status IN ({ACTIVE_STATUSES_SQL})"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_optimization_sessions_one_active_per_user",
        table_name="optimization_sessions",
    )
