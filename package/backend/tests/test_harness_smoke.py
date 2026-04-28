import pytest
from sqlalchemy import inspect

import app.database as database_module
from app.main import app
from app.database import SessionLocal, engine
from app.models.models import CustomPrompt
from fastapi.testclient import TestClient


def _system_prompt_stages(db):
    prompts = db.query(CustomPrompt).filter(CustomPrompt.is_system.is_(True)).all()
    return prompts, {prompt.stage for prompt in prompts}


def test_startup_initializes_database_and_system_prompts(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"users", "custom_prompts", "optimization_sessions"}.issubset(tables)

    db = SessionLocal()
    try:
        system_prompts, prompt_stages = _system_prompt_stages(db)
    finally:
        db.close()

    assert len(system_prompts) >= 2
    assert prompt_stages == {"polish", "enhance"}


def test_repeated_startup_does_not_duplicate_system_prompts():
    with TestClient(app) as first_client:
        response = first_client.get("/health")
        assert response.status_code == 200

    with TestClient(app) as second_client:
        response = second_client.get("/health")
        assert response.status_code == 200

    db = SessionLocal()
    try:
        system_prompts, prompt_stages = _system_prompt_stages(db)
    finally:
        db.close()

    assert len(system_prompts) == len(prompt_stages)
    assert prompt_stages == {"polish", "enhance"}


def test_reset_db_recreates_clean_seed_state(client):
    db = SessionLocal()
    try:
        prompts, prompt_stages = _system_prompt_stages(db)
    finally:
        db.close()

    assert len(prompts) >= 2
    assert prompt_stages == {"polish", "enhance"}


def test_reset_db_leaves_direct_db_tests_with_valid_schema():
    db = SessionLocal()
    try:
        prompts, prompt_stages = _system_prompt_stages(db)
    finally:
        db.close()

    assert prompts == []
    assert prompt_stages == set()


def test_normalize_database_url_uses_psycopg_for_plain_postgres_urls():
    assert database_module.normalize_database_url("postgresql://user:pass@localhost/dbname") == (
        "postgresql+psycopg://user:pass@localhost/dbname"
    )
    assert database_module.normalize_database_url("postgresql+psycopg://user:pass@localhost/dbname") == (
        "postgresql+psycopg://user:pass@localhost/dbname"
    )


def test_database_url_rejects_non_postgresql_urls():
    with pytest.raises(ValueError, match="PostgreSQL"):
        database_module.normalize_database_url("mysql://user:pass@localhost/dbname")
