from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.database import Base, engine


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def _reset_schema_for_migration_test() -> None:
    database_name = engine.url.database or ""
    assert "test" in database_name.lower()

    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_alembic_upgrade_creates_current_schema():
    _reset_schema_for_migration_test()

    command.upgrade(_alembic_config(), "head")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {
        "users",
        "registration_invites",
        "credit_codes",
        "credit_transactions",
        "user_provider_configs",
        "paper_projects",
        "optimization_sessions",
        "optimization_segments",
        "session_history",
        "change_logs",
        "queue_status",
        "custom_prompts",
        "system_settings",
        "saved_specs",
        "alembic_version",
    }.issubset(tables)

    session_columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
    assert {
        "billing_mode",
        "project_id",
        "task_title",
        "charged_credits",
        "queued_at",
        "started_at",
        "finished_at",
        "worker_id",
    }.issubset(session_columns)

    session_indexes = {index["name"] for index in inspector.get_indexes("optimization_sessions")}
    assert {
        "idx_opt_session_user_id",
        "idx_opt_session_status",
        "idx_opt_session_created_at",
        "ix_optimization_sessions_queued_at",
        "ix_optimization_sessions_worker_id",
    }.issubset(session_indexes)
