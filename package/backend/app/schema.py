"""Production schema lifecycle helpers.

Alembic owns server-deployment DDL.  Local interactive builds retain the
legacy ``init_db`` compatibility pass, then reconcile and stamp the physical
schema through the same Alembic metadata gate.  Docker/VPS app and worker
processes only verify the expected revision.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from app.config import is_server_deployment, settings
from app.database import Base, check_database_connection, engine, init_db, normalize_database_url


BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"

# Stable signed BIGINT generated for the application schema migration lock.
SCHEMA_ADVISORY_LOCK_ID = 733_265_144_287_873_507
DEFAULT_MIGRATION_LOCK_TIMEOUT_SECONDS = 300

MANAGED_PERFORMANCE_INDEX_PREFIXES = (
    "idx_opt_",
    "idx_change_log_",
    "idx_registration_invites_",
    "idx_zhuque_prompt_memories_",
)


class SchemaStateError(RuntimeError):
    """The database revision or physical schema is not production-safe."""


def include_schema_object(object_, name, type_, reflected, compare_to):
    """Ignore legacy performance indexes that are managed outside metadata."""
    if type_ == "index" and reflected and name:
        return not name.startswith(MANAGED_PERFORMANCE_INDEX_PREFIXES)
    return True


def _load_models() -> None:
    from app.models import models  # noqa: F401


def build_alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option(
        "sqlalchemy.url",
        normalize_database_url(settings.DATABASE_URL).replace("%", "%%"),
    )
    return config


def get_expected_schema_revision(config: Config | None = None) -> str:
    script = ScriptDirectory.from_config(config or build_alembic_config())
    heads = tuple(script.get_heads())
    if len(heads) != 1:
        raise SchemaStateError(f"Alembic 必须只有一个 head，当前为: {', '.join(heads) or '<none>'}")
    return heads[0]


def get_current_schema_revisions(connection: Connection) -> tuple[str, ...]:
    return tuple(MigrationContext.configure(connection).get_current_heads())


def get_schema_differences(connection: Connection) -> list[object]:
    _load_models()
    context = MigrationContext.configure(
        connection,
        opts={
            "compare_type": True,
            "include_object": include_schema_object,
        },
    )
    return list(compare_metadata(context, Base.metadata))


def _format_schema_differences(differences: list[object], limit: int = 12) -> str:
    rendered = [str(item) for item in differences[:limit]]
    remaining = len(differences) - len(rendered)
    if remaining > 0:
        rendered.append(f"... 另有 {remaining} 项")
    return "\n  - ".join(rendered)


def verify_database_schema() -> str:
    """Fail closed unless the database is stamped at the single Alembic head."""
    expected = get_expected_schema_revision()
    with engine.connect() as connection:
        current = get_current_schema_revisions(connection)

    if current != (expected,):
        current_label = ", ".join(current) if current else "<unversioned>"
        raise SchemaStateError(
            "数据库 Schema 未就绪，拒绝启动生产进程。"
            f" 当前 revision={current_label}，期望 revision={expected}。"
            " 请先运行: docker compose --env-file .env.docker run --rm migrate"
        )
    return expected


def prepare_database() -> None:
    """Connect and either verify production schema or initialize local schema."""
    check_database_connection()
    if is_server_deployment():
        revision = verify_database_schema()
        print(f"✓ 数据库 Schema 已就绪: {revision}")
        return
    init_db()
    expected = get_expected_schema_revision()
    with engine.connect() as connection:
        current = get_current_schema_revisions(connection)
    revision = expected if current == (expected,) else upgrade_database_schema()
    print(f"✓ 本地数据库 Schema 已就绪: {revision}")


def _column_factory(
    type_: sa.types.TypeEngine,
    **kwargs,
) -> Callable[[str], sa.Column]:
    return lambda name: sa.Column(name, type_, **kwargs)


# Only known additive changes from historical create_all/manual-DDL databases
# are reconciled. Unknown destructive/type/constraint drift remains a hard
# failure and must be reviewed against a production schema dump.
LEGACY_ADDITIVE_COLUMNS: dict[str, dict[str, Callable[[str], sa.Column]]] = {
    "users": {
        "avatar_url": _column_factory(sa.String(length=512), nullable=True),
        "token_version": _column_factory(sa.Integer(), nullable=True),
        "zhuque_free_uses_remaining": _column_factory(sa.Integer(), nullable=True),
        "zhuque_total_uses": _column_factory(sa.Integer(), nullable=True),
    },
    "user_provider_configs": {
        "api_format": lambda name: sa.Column(
            name,
            sa.String(length=40),
            nullable=False,
            server_default="openai_chat",
        ),
    },
    "optimization_sessions": {
        "queued_at": _column_factory(sa.DateTime(), nullable=True),
        "started_at": _column_factory(sa.DateTime(), nullable=True),
        "finished_at": _column_factory(sa.DateTime(), nullable=True),
        "worker_id": _column_factory(sa.String(length=100), nullable=True),
        "worker_attempt_count": _column_factory(sa.Integer(), nullable=True),
        "polish_api_format": _column_factory(sa.String(length=40), nullable=True),
        "enhance_api_format": _column_factory(sa.String(length=40), nullable=True),
        "emotion_api_format": _column_factory(sa.String(length=40), nullable=True),
        "zhuque_agent_trace": _column_factory(sa.Text(), nullable=True),
        "document_format": _column_factory(sa.String(length=32), nullable=True),
        "parse_engine": _column_factory(sa.String(length=64), nullable=True),
        "parse_fallback_used": _column_factory(sa.Boolean(), nullable=True),
        "parse_trace": _column_factory(sa.Text(), nullable=True),
    },
    "optimization_segments": {
        "zhuque_detect_rate": _column_factory(sa.Float(), nullable=True),
        "zhuque_detect_result": _column_factory(sa.Text(), nullable=True),
        "zhuque_detect_count": _column_factory(sa.Integer(), nullable=True),
        "zhuque_reduce_attempt": _column_factory(sa.Integer(), nullable=True),
        "zhuque_reduced_text": _column_factory(sa.Text(), nullable=True),
        "semantic_type": _column_factory(sa.String(length=64), nullable=True),
        "semantic_source": _column_factory(sa.String(length=64), nullable=True),
        "semantic_confidence": _column_factory(sa.Float(), nullable=True),
        "reduce_allowed": _column_factory(sa.Boolean(), nullable=True),
        "semantic_reason": _column_factory(sa.String(length=128), nullable=True),
        "char_start": _column_factory(sa.Integer(), nullable=True),
        "char_end": _column_factory(sa.Integer(), nullable=True),
        "page_number": _column_factory(sa.Integer(), nullable=True),
        "bbox_json": _column_factory(sa.Text(), nullable=True),
    },
}


def _reconcile_unversioned_schema() -> None:
    """Apply only additive, known-safe repairs to a legacy unversioned DB."""
    _load_models()
    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())

        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                table.create(bind=connection)
                existing_tables.add(table.name)

        for table_name, columns in LEGACY_ADDITIVE_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspect(connection).get_columns(table_name)
            }
            operations = Operations(MigrationContext.configure(connection))
            for column_name, factory in columns.items():
                if column_name in existing_columns:
                    continue
                column = factory(column_name)
                operations.add_column(table_name, column)

        for statement in (
            "UPDATE users SET token_version = 0 WHERE token_version IS NULL",
            "UPDATE users SET zhuque_free_uses_remaining = 20 "
            "WHERE zhuque_free_uses_remaining IS NULL",
            "UPDATE users SET zhuque_total_uses = 0 WHERE zhuque_total_uses IS NULL",
            "UPDATE optimization_sessions SET polish_api_format = 'openai_chat' "
            "WHERE polish_api_format IS NULL",
            "UPDATE optimization_sessions SET enhance_api_format = 'openai_chat' "
            "WHERE enhance_api_format IS NULL",
            "UPDATE optimization_sessions SET emotion_api_format = 'openai_chat' "
            "WHERE emotion_api_format IS NULL",
            "UPDATE optimization_sessions SET worker_attempt_count = 0 "
            "WHERE worker_attempt_count IS NULL",
            "UPDATE optimization_segments SET zhuque_detect_count = 0 "
            "WHERE zhuque_detect_count IS NULL",
            "UPDATE optimization_segments SET zhuque_reduce_attempt = 0 "
            "WHERE zhuque_reduce_attempt IS NULL",
        ):
            connection.execute(text(statement))

        if "user_provider_configs" in existing_tables:
            connection.execute(
                text(
                    "UPDATE user_provider_configs SET api_format = 'openai_chat' "
                    "WHERE api_format IS NULL"
                )
            )
            operations = Operations(MigrationContext.configure(connection))
            operations.alter_column(
                "user_provider_configs",
                "api_format",
                existing_type=sa.String(length=40),
                server_default=None,
            )

        # Add model-owned indexes that are absent. Existing mismatched indexes
        # are not rewritten here; the exact-schema gate below will reject them.
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            for index in table.indexes:
                index.create(bind=connection, checkfirst=True)


def _assert_schema_matches_metadata() -> None:
    with engine.connect() as connection:
        differences = get_schema_differences(connection)
    if differences:
        raise SchemaStateError(
            "数据库物理结构与当前模型不一致，禁止 stamp/启动。差异:\n  - "
            + _format_schema_differences(differences)
        )


def _acquire_migration_lock(connection: Connection, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": SCHEMA_ADVISORY_LOCK_ID},
        ).scalar_one()
        connection.commit()
        if acquired:
            return
        if time.monotonic() >= deadline:
            raise SchemaStateError(
                f"等待数据库迁移锁超时（{timeout_seconds}s），已有迁移进程可能仍在运行"
            )
        time.sleep(1)


def upgrade_database_schema(
    lock_timeout_seconds: int = DEFAULT_MIGRATION_LOCK_TIMEOUT_SECONDS,
) -> str:
    """Upgrade or safely adopt a legacy unversioned schema under one lock."""
    if lock_timeout_seconds < 1:
        raise ValueError("lock_timeout_seconds must be positive")

    check_database_connection()
    _load_models()
    config = build_alembic_config()
    expected = get_expected_schema_revision(config)

    with engine.connect() as lock_connection:
        _acquire_migration_lock(lock_connection, lock_timeout_seconds)
        try:
            with engine.connect() as connection:
                current = get_current_schema_revisions(connection)
                existing_tables = set(inspect(connection).get_table_names())
            application_tables = set(Base.metadata.tables)

            if current:
                command.upgrade(config, "head")
            elif existing_tables & application_tables:
                with engine.connect() as connection:
                    differences = get_schema_differences(connection)
                if differences:
                    _reconcile_unversioned_schema()
                _assert_schema_matches_metadata()
                command.stamp(config, "head")
            else:
                command.upgrade(config, "head")

            _assert_schema_matches_metadata()
            verify_database_schema()
            return expected
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": SCHEMA_ADVISORY_LOCK_ID},
            )
            lock_connection.commit()
