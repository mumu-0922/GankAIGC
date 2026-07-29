from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from app.database import Base, SessionLocal, engine
from app.models.models import OptimizationSession, User
from app import schema as schema_module
from app.schema import (
    SchemaStateError,
    get_current_schema_revisions,
    get_expected_schema_revision,
    get_schema_differences,
    prepare_database,
    upgrade_database_schema,
)


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


def _create_unversioned_current_schema() -> None:
    _reset_schema_for_migration_test()
    Base.metadata.create_all(bind=engine)


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
        "announcements",
        "zhuque_prompt_memories",
        "task_events",
        "worker_leases",
        "alembic_version",
    }.issubset(tables)

    session_columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
    assert {
        "billing_mode",
        "project_id",
        "task_title",
        "charged_credits",
        "zhuque_agent_trace",
        "document_format",
        "parse_engine",
        "parse_fallback_used",
        "parse_trace",
        "queued_at",
        "started_at",
        "finished_at",
        "worker_id",
        "worker_attempt_count",
        "polish_api_format",
        "enhance_api_format",
        "emotion_api_format",
    }.issubset(session_columns)

    segment_columns = {column["name"] for column in inspector.get_columns("optimization_segments")}
    assert {
        "semantic_type",
        "semantic_source",
        "semantic_confidence",
        "reduce_allowed",
        "semantic_reason",
        "char_start",
        "char_end",
        "page_number",
        "bbox_json",
        "zhuque_detect_rate",
        "zhuque_detect_result",
        "zhuque_detect_count",
        "zhuque_reduce_attempt",
        "zhuque_reduced_text",
    }.issubset(segment_columns)

    session_indexes = {index["name"] for index in inspector.get_indexes("optimization_sessions")}
    assert {
        "idx_opt_session_user_id",
        "idx_opt_session_status",
        "idx_opt_session_created_at",
        "ix_optimization_sessions_queued_at",
        "ix_optimization_sessions_worker_id",
        "uq_optimization_sessions_one_active_per_user",
    }.issubset(session_indexes)

    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == (get_expected_schema_revision(),)
        assert get_schema_differences(conn) == []


def test_fair_concurrency_migration_requeues_duplicate_active_sessions():
    _reset_schema_for_migration_test()
    command.upgrade(_alembic_config(), "0010_task_events_worker_leases")

    db = SessionLocal()
    try:
        user = User(username="migration-active-user", access_link="migration-active-user")
        db.add(user)
        db.flush()
        db.add_all(
            [
                OptimizationSession(
                    user_id=user.id,
                    session_id="migration-active-1",
                    original_text="测试正文一",
                    processing_mode="paper_polish",
                    current_stage="polish",
                    status="processing",
                    progress=20,
                ),
                OptimizationSession(
                    user_id=user.id,
                    session_id="migration-active-2",
                    original_text="测试正文二",
                    processing_mode="paper_polish",
                    current_stage="polish",
                    status="waiting_browser_agent",
                    progress=40,
                ),
            ]
        )
        db.commit()
        user_id = user.id
    finally:
        db.close()

    command.upgrade(_alembic_config(), "head")

    db = SessionLocal()
    try:
        sessions = (
            db.query(OptimizationSession)
            .filter(OptimizationSession.user_id == user_id)
            .order_by(OptimizationSession.id.asc())
            .all()
        )
        assert [session.status for session in sessions] == ["processing", "queued"]
        assert sessions[1].worker_id is None
        assert sessions[1].started_at is None
        assert "duplicate active task requeued" in sessions[1].error_message
    finally:
        db.close()


def test_unversioned_current_schema_is_verified_before_stamp():
    _create_unversioned_current_schema()

    revision = upgrade_database_schema(lock_timeout_seconds=5)

    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == (revision,)
        assert get_schema_differences(conn) == []


def test_unversioned_schema_missing_document_columns_is_reconciled():
    _create_unversioned_current_schema()
    with engine.begin() as conn:
        for column_name in (
            "document_format",
            "parse_engine",
            "parse_fallback_used",
            "parse_trace",
        ):
            conn.execute(text(f"ALTER TABLE optimization_sessions DROP COLUMN {column_name}"))
        for column_name in (
            "semantic_type",
            "semantic_source",
            "semantic_confidence",
            "reduce_allowed",
            "semantic_reason",
            "char_start",
            "char_end",
            "page_number",
            "bbox_json",
        ):
            conn.execute(text(f"ALTER TABLE optimization_segments DROP COLUMN {column_name}"))

    first_revision = upgrade_database_schema(lock_timeout_seconds=5)
    second_revision = upgrade_database_schema(lock_timeout_seconds=5)

    assert first_revision == second_revision == get_expected_schema_revision()
    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == (first_revision,)
        assert get_schema_differences(conn) == []


def test_local_prepare_reconciles_and_stamps_unversioned_legacy_schema(monkeypatch):
    _create_unversioned_current_schema()
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE optimization_sessions "
                "DROP COLUMN worker_attempt_count"
            )
        )

    monkeypatch.setattr(schema_module, "is_server_deployment", lambda: False)
    monkeypatch.setattr(schema_module, "init_db", lambda: None)

    prepare_database()

    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == (get_expected_schema_revision(),)
        assert get_schema_differences(conn) == []


def test_production_prepare_rejects_unversioned_schema_without_running_ddl(monkeypatch):
    _create_unversioned_current_schema()
    monkeypatch.setattr(schema_module, "is_server_deployment", lambda: True)
    monkeypatch.setattr(
        schema_module,
        "init_db",
        lambda: pytest.fail("production startup must not execute init_db"),
    )

    with pytest.raises(SchemaStateError, match="拒绝启动生产进程"):
        prepare_database()

    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == ()


def test_failed_fresh_migration_does_not_stamp_database(monkeypatch):
    _reset_schema_for_migration_test()

    def fail_upgrade(*args, **kwargs):
        raise RuntimeError("forced migration failure")

    monkeypatch.setattr(schema_module.command, "upgrade", fail_upgrade)

    with pytest.raises(RuntimeError, match="forced migration failure"):
        upgrade_database_schema(lock_timeout_seconds=5)

    with engine.connect() as conn:
        assert get_current_schema_revisions(conn) == ()
