from __future__ import annotations

import os
from pathlib import Path
import secrets
import subprocess
import sys

import psycopg
from psycopg import sql
import pytest
from sqlalchemy.engine import make_url

from app.config import settings
from provision_db_roles import (
    RoleNames,
    RolePasswords,
    RoleProvisionError,
    provision_roles,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _psycopg_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _connection_url(base_url: str, *, database: str, user: str, password: str) -> str:
    url = make_url(base_url).set(database=database, username=user, password=password)
    return _psycopg_url(url.render_as_string(hide_password=False))


def _isolated_role_state():
    suffix = secrets.token_hex(4)
    database_name = f"gankaigc_roles_{suffix}"
    roles = RoleNames(
        owner=f"ga_owner_{suffix}",
        migrator=f"ga_migrator_{suffix}",
        app=f"ga_app_{suffix}",
        backup=f"ga_backup_{suffix}",
    )
    passwords = RolePasswords(
        migrator=secrets.token_urlsafe(24),
        app=secrets.token_urlsafe(24),
        backup=secrets.token_urlsafe(24),
    )
    return database_name, roles, passwords


def _admin_url(database: str = "postgres") -> str:
    url = make_url(settings.DATABASE_URL).set(database=database)
    return _psycopg_url(url.render_as_string(hide_password=False))


def _require_superuser() -> None:
    with psycopg.connect(_admin_url()) as connection:
        is_superuser = connection.execute(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()[0]
    if not is_superuser:
        pytest.skip("role provisioning integration test requires the test bootstrap superuser")


def _create_database(database_name: str) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))


def _cleanup_database_and_roles(database_name: str, roles: RoleNames) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database_name,),
        )
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
        )
        for role in (roles.migrator, roles.app, roles.backup, roles.owner):
            connection.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def test_role_provisioning_fails_closed_then_enforces_dml_and_read_only_contracts():
    _require_superuser()
    database_name, roles, passwords = _isolated_role_state()
    _create_database(database_name)
    bootstrap_url = _admin_url(database_name)
    try:
        with psycopg.connect(bootstrap_url) as connection:
            connection.execute(
                "CREATE TABLE public.legacy_items "
                "(id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.commit()

        with pytest.raises(RoleProvisionError, match="explicit owner transition"):
            provision_roles(bootstrap_url, roles, passwords, allow_reassign=False)

        provision_roles(bootstrap_url, roles, passwords, allow_reassign=True)

        migrator_url = _connection_url(
            bootstrap_url,
            database=database_name,
            user=roles.migrator,
            password=passwords.migrator,
        )
        with psycopg.connect(migrator_url) as connection:
            connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles.owner)))
            connection.execute(
                "CREATE TABLE public.future_items "
                "(id BIGSERIAL PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.commit()

        app_url = _connection_url(
            bootstrap_url,
            database=database_name,
            user=roles.app,
            password=passwords.app,
        )
        with psycopg.connect(app_url) as connection:
            connection.execute("INSERT INTO legacy_items(value) VALUES ('ok')")
            connection.execute("INSERT INTO future_items(value) VALUES ('ok')")
            connection.commit()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute("CREATE TABLE forbidden_app_ddl(id INTEGER)")
            connection.rollback()

        backup_url = _connection_url(
            bootstrap_url,
            database=database_name,
            user=roles.backup,
            password=passwords.backup,
        )
        with psycopg.connect(backup_url) as connection:
            assert connection.execute("SELECT count(*) FROM future_items").fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute("INSERT INTO future_items(value) VALUES ('forbidden')")
            connection.rollback()
    finally:
        _cleanup_database_and_roles(database_name, roles)


def test_migrator_role_upgrades_fresh_database_and_grants_new_table_access():
    _require_superuser()
    database_name, roles, passwords = _isolated_role_state()
    _create_database(database_name)
    bootstrap_url = _admin_url(database_name)
    try:
        provision_roles(bootstrap_url, roles, passwords)
        migrator_url = _connection_url(
            bootstrap_url,
            database=database_name,
            user=roles.migrator,
            password=passwords.migrator,
        )
        environment = {
            **os.environ,
            "DATABASE_URL": migrator_url,
            "DATABASE_SESSION_ROLE": roles.owner,
            "APP_ENV": "production",
            "SECRET_KEY": "migration-test-secret-key-32-characters",
            "ADMIN_PASSWORD": "migration-test-admin-password",
        }
        completed = subprocess.run(
            [sys.executable, "schema_migrate.py", "upgrade"],
            cwd=BACKEND_DIR,
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "0011_fair_concurrency_guard" in completed.stdout

        app_url = _connection_url(
            bootstrap_url,
            database=database_name,
            user=roles.app,
            password=passwords.app,
        )
        with psycopg.connect(app_url) as connection:
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            assert revision == "0011_fair_concurrency_guard"
            assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 0
    finally:
        _cleanup_database_and_roles(database_name, roles)
