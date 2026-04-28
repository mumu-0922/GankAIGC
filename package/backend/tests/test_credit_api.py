from datetime import UTC, datetime

from app.database import Base
from app.models.models import User
from app.schemas import UserCreate, UserResponse
from app.utils.auth import create_user_access_token, get_password_hash


def test_user_model_exposes_account_credit_and_provider_tables():
    for field_name in (
        "username",
        "nickname",
        "password_hash",
        "is_unlimited",
        "credit_balance",
        "last_login_at",
    ):
        assert hasattr(User, field_name)

    assert not hasattr(User, "card_key")
    assert not hasattr(User, "legacy_card_key")

    metadata_tables = set(Base.metadata.tables)
    for table_name in (
        "registration_invites",
        "credit_codes",
        "credit_transactions",
        "user_provider_configs",
    ):
        assert table_name in metadata_tables


def test_user_schemas_do_not_expose_card_key_fields():
    user_create = UserCreate(access_link="http://testserver/access/account", username="new-account")

    assert "card_key" not in UserCreate.model_fields
    assert "legacy_card_key" not in UserCreate.model_fields
    assert "card_key" not in UserResponse.model_fields
    assert "legacy_card_key" not in UserResponse.model_fields
    assert user_create.username == "new-account"

    response = UserResponse(
        id=1,
        username="new-account",
        nickname="New Account",
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

    assert response.username == "new-account"
    assert response.nickname == "New Account"


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
