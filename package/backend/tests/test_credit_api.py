from datetime import UTC, datetime

from sqlalchemy import create_engine, inspect, text

import app.database as database_module
from app.database import Base
from app.models.models import User
from app.schemas import UserCreate, UserResponse
from app.utils.auth import create_user_access_token, get_password_hash


def test_user_model_exposes_account_credit_and_provider_tables():
    for field_name in (
        "username",
        "nickname",
        "password_hash",
        "legacy_card_key",
        "is_unlimited",
        "credit_balance",
        "last_login_at",
    ):
        assert hasattr(User, field_name)

    metadata_tables = set(Base.metadata.tables)
    for table_name in (
        "registration_invites",
        "credit_codes",
        "credit_transactions",
        "user_provider_configs",
    ):
        assert table_name in metadata_tables


def test_user_schemas_allow_non_card_key_accounts():
    user_create = UserCreate(access_link="http://testserver/access/account", username="new-account")

    assert user_create.card_key is None
    assert user_create.username == "new-account"

    response = UserResponse(
        id=1,
        card_key=None,
        username="new-account",
        nickname="New Account",
        legacy_card_key=None,
        access_link="http://testserver/access/account",
        is_active=True,
        is_unlimited=False,
        credit_balance=0,
        created_at=datetime.now(UTC),
        last_used=None,
        last_login_at=None,
        usage_limit=5,
        usage_count=0,
    )

    assert response.card_key is None
    assert response.username == "new-account"
    assert response.nickname == "New Account"


def test_sqlite_user_migration_rebuilds_legacy_table_for_nullable_card_key(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-users.db"
    temp_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    with temp_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    card_key VARCHAR(255) NOT NULL,
                    access_link VARCHAR(255) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    last_used DATETIME,
                    usage_limit INTEGER DEFAULT 100,
                    usage_count INTEGER DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO users (id, card_key, access_link, is_active, created_at, last_used, usage_limit, usage_count)
                VALUES (1, 'LEGACY-KEY', 'http://testserver/access/legacy', 1, '2026-04-24 00:00:00', NULL, 7, 2)
                """
            )
        )

    monkeypatch.setattr(database_module, "engine", temp_engine)

    database_module._migrate_database_schema()

    inspector = inspect(temp_engine)
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}

    assert user_columns["card_key"]["nullable"] is True
    assert "nickname" in user_columns
    assert {"registration_invites", "credit_codes", "credit_transactions", "user_provider_configs"}.issubset(
        set(inspector.get_table_names())
    )

    with temp_engine.begin() as conn:
        legacy_user = conn.execute(
            text("SELECT id, card_key, access_link, usage_limit, usage_count FROM users WHERE id = 1")
        ).mappings().one()
        assert legacy_user["card_key"] == "LEGACY-KEY"
        assert legacy_user["access_link"] == "http://testserver/access/legacy"
        assert legacy_user["usage_limit"] == 7
        assert legacy_user["usage_count"] == 2

        conn.execute(
            text(
                """
                INSERT INTO users (
                    id, card_key, username, nickname, access_link, is_active, created_at, usage_limit, usage_count
                ) VALUES (
                    2, NULL, 'new-account', 'New Account', 'http://testserver/access/new', 1, '2026-04-24 00:00:01', 0, 0
                )
                """
            )
        )
        migrated_user = conn.execute(
            text("SELECT id, username, nickname, card_key FROM users WHERE id = 2")
        ).mappings().one()

    temp_engine.dispose()
    assert migrated_user["username"] == "new-account"
    assert migrated_user["nickname"] == "New Account"
    assert migrated_user["card_key"] is None


def _create_user(db, username="alice", credit_balance=0, is_unlimited=False):
    user = User(
        username=username,
        password_hash=get_password_hash("Password123!"),
        access_link=f"http://testserver/access/{username}",
        is_active=True,
        credit_balance=credit_balance,
        is_unlimited=is_unlimited,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _user_auth_headers(user):
    return {"Authorization": f"Bearer {create_user_access_token(user.id, user.username)}"}


def _admin_auth_headers(client):
    import app.config as config_module

    response = client.post(
        "/api/admin/login",
        json={"username": config_module.settings.ADMIN_USERNAME, "password": config_module.settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_user_can_redeem_credit_code_once(client):
    from app.database import SessionLocal
    from app.models.models import CreditCode

    db = SessionLocal()
    try:
        user = _create_user(db)
        db.add(CreditCode(code="CREDIT10", credit_amount=10, is_active=True))
        db.commit()
        headers = _user_auth_headers(user)
    finally:
        db.close()

    response = client.post("/api/user/redeem-code", json={"code": "CREDIT10"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["credit_balance"] == 10

    second_response = client.post("/api/user/redeem-code", json={"code": "CREDIT10"}, headers=headers)

    assert second_response.status_code == 400


def test_admin_can_create_credit_codes_and_recharge_user(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user = _create_user(db)
        user_id = user.id
    finally:
        db.close()

    admin_headers = _admin_auth_headers(client)
    create_response = client.post(
        "/api/admin/credit-codes",
        json={"code": "CREDIT5", "credit_amount": 5},
        headers=admin_headers,
    )

    assert create_response.status_code == 200
    assert create_response.json()["code"] == "CREDIT5"
    assert create_response.json()["credit_amount"] == 5

    recharge_response = client.post(
        f"/api/admin/users/{user_id}/credits",
        json={"amount": 7},
        headers=admin_headers,
    )

    assert recharge_response.status_code == 200
    assert recharge_response.json()["credit_balance"] == 7

    list_response = client.get("/api/admin/credit-codes", headers=admin_headers)

    assert list_response.status_code == 200
    assert [item["code"] for item in list_response.json()] == ["CREDIT5"]
