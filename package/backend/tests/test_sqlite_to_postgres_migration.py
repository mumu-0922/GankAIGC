from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.models import models  # noqa: F401
from migrate_sqlite_to_postgres import (
    build_postgres_sequence_reset_sql,
    migrate_sqlite_to_target,
    migration_table_names,
)


def test_migration_table_order_preserves_foreign_key_dependencies():
    table_names = migration_table_names()

    assert table_names.index("users") < table_names.index("registration_invites")
    assert table_names.index("users") < table_names.index("credit_codes")
    assert table_names.index("users") < table_names.index("paper_projects")
    assert table_names.index("paper_projects") < table_names.index("optimization_sessions")
    assert table_names.index("optimization_sessions") < table_names.index("optimization_segments")
    assert table_names.index("optimization_sessions") < table_names.index("session_history")
    assert table_names.index("optimization_sessions") < table_names.index("change_logs")
    assert table_names.index("optimization_sessions") < table_names.index("credit_transactions")


def test_migration_skips_removed_legacy_card_key_columns(tmp_path):
    source_db = tmp_path / "legacy.sqlite"
    target_db = tmp_path / "target.sqlite"
    source_engine = create_engine(f"sqlite:///{source_db}", connect_args={"check_same_thread": False})

    with source_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    card_key VARCHAR(255),
                    username VARCHAR(100),
                    nickname VARCHAR(100),
                    password_hash VARCHAR(255),
                    legacy_card_key VARCHAR(255),
                    access_link VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    is_unlimited BOOLEAN DEFAULT 0,
                    credit_balance INTEGER DEFAULT 0,
                    created_at DATETIME,
                    last_used DATETIME,
                    last_login_at DATETIME,
                    usage_limit INTEGER DEFAULT 0,
                    usage_count INTEGER DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO users (
                    id, card_key, username, nickname, password_hash, legacy_card_key,
                    access_link, is_active, is_unlimited, credit_balance, created_at, usage_limit, usage_count
                ) VALUES (
                    7, 'OLD-CARD', 'alice', 'Alice', 'hash', 'OLD-LEGACY',
                    'http://testserver/access/alice', 1, 0, 12, '2026-04-28 10:00:00', 0, 3
                )
                """
            )
        )

    result = migrate_sqlite_to_target(
        source_url=f"sqlite:///{source_db}",
        target_url=f"sqlite:///{target_db}",
        replace_target=True,
        allow_sqlite_target=True,
    )

    assert result["users"] == 1

    target_engine = create_engine(f"sqlite:///{target_db}", connect_args={"check_same_thread": False})
    inspector = inspect(target_engine)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert "card_key" not in user_columns
    assert "legacy_card_key" not in user_columns

    with target_engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, username, nickname, credit_balance, usage_count FROM users")
        ).mappings().one()

    assert row["id"] == 7
    assert row["username"] == "alice"
    assert row["nickname"] == "Alice"
    assert row["credit_balance"] == 12
    assert row["usage_count"] == 3

    source_engine.dispose()
    target_engine.dispose()


def test_postgres_sequence_reset_sql_uses_table_primary_key():
    users_table = Base.metadata.tables["users"]

    sql = build_postgres_sequence_reset_sql(users_table)

    assert "pg_get_serial_sequence('users', 'id')" in sql
    assert 'MAX("id") FROM "users"' in sql
    assert 'COUNT(*) FROM "users"' in sql
