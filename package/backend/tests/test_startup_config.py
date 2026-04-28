import pytest

import app.database as database_module


def test_normalize_database_url_rejects_missing_value():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        database_module.normalize_database_url("")


def test_normalize_database_url_rejects_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        database_module.normalize_database_url("sqlite:///ai_polish.db")


def test_normalize_database_url_accepts_postgresql():
    assert database_module.normalize_database_url(
        "postgresql://ai_polish:secret@127.0.0.1:5432/ai_polish"
    ) == "postgresql+psycopg://ai_polish:secret@127.0.0.1:5432/ai_polish"


def test_database_connection_error_hides_password():
    message = database_module.build_database_connection_error(
        RuntimeError("connection refused"),
        "postgresql://ai_polish:super-secret@127.0.0.1:5432/ai_polish",
    )

    assert "super-secret" not in message
    assert "postgresql://ai_polish:***@127.0.0.1:5432/ai_polish" in message
    assert "DATABASE_URL" in message
    assert "docker compose up -d postgres" in message
    assert "POSTGRES_PASSWORD" in message


def test_check_database_connection_raises_actionable_error(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(database_module, "engine", BrokenEngine())

    with pytest.raises(RuntimeError) as exc_info:
        database_module.check_database_connection()

    message = str(exc_info.value)
    assert "PostgreSQL 数据库连接失败" in message
    assert "DATABASE_URL" in message
    assert "docker compose up -d postgres" in message
    assert "POSTGRES_PASSWORD" in message
