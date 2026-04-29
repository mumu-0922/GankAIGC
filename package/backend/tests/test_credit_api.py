from datetime import timedelta

from app.database import Base
from app.models.models import CreditTransaction, OptimizationSession, User
from app.schemas import UserCreate, UserResponse
from app.utils.auth import create_user_access_token, get_password_hash
from app.utils.time import utcnow


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
        created_at=utcnow(),
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


def test_user_credit_transactions_are_limited_labeled_and_private(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user = _create_user(db, username="alice")
        other_user = _create_user(db, username="bob")
        now = utcnow()
        db.add_all(
            [
                CreditTransaction(
                    user_id=user.id,
                    delta=10,
                    balance_after=10,
                    reason="redeem_code",
                    created_at=now - timedelta(minutes=3),
                ),
                CreditTransaction(
                    user_id=user.id,
                    delta=-3,
                    balance_after=7,
                    reason="optimization_start",
                    created_at=now - timedelta(minutes=2),
                ),
                CreditTransaction(
                    user_id=user.id,
                    delta=3,
                    balance_after=10,
                    reason="optimization_refund",
                    created_at=now - timedelta(minutes=1),
                ),
                CreditTransaction(
                    user_id=other_user.id,
                    delta=99,
                    balance_after=99,
                    reason="admin_recharge",
                    created_at=now,
                ),
            ]
        )
        db.commit()
        headers = _user_auth_headers(user)
    finally:
        db.close()

    response = client.get("/api/user/credit-transactions?limit=2", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert [item["reason"] for item in payload] == ["optimization_refund", "optimization_start"]
    assert [item["reason_label"] for item in payload] == ["任务失败退款", "降 AI 消耗"]
    assert [item["transaction_type"] for item in payload] == ["credit", "debit"]
    assert all("user_id" not in item for item in payload)
    assert all(item["balance_after"] in {7, 10} for item in payload)


def test_admin_can_view_recent_credit_transactions_with_user_and_session_context(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user = _create_user(db, username="alice")
        user.nickname = "Alice 昵称"
        session = OptimizationSession(
            user_id=user.id,
            session_id="public-session-id",
            original_text="测试正文",
            current_stage="polish",
            status="completed",
            progress=100,
            processing_mode="paper_polish",
            billing_mode="platform",
            charge_status="charged",
            charged_credits=2,
            task_title="第一章",
        )
        db.add(session)
        db.flush()
        db.add(
            CreditTransaction(
                user_id=user.id,
                delta=-2,
                balance_after=8,
                reason="optimization_start",
                related_session_id=session.id,
            )
        )
        db.commit()
    finally:
        db.close()

    admin_headers = _admin_auth_headers(client)
    response = client.get("/api/admin/credit-transactions?limit=10", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["username"] == "alice"
    assert payload[0]["nickname"] == "Alice 昵称"
    assert payload[0]["user_display_name"] == "Alice 昵称"
    assert payload[0]["reason_label"] == "降 AI 消耗"
    assert payload[0]["transaction_type"] == "debit"
    assert payload[0]["related_session_public_id"] == "public-session-id"
    assert payload[0]["related_session_title"] == "第一章"


def test_admin_user_details_include_recent_credit_transactions(client):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user = _create_user(db, username="alice")
        db.add(
            CreditTransaction(
                user_id=user.id,
                delta=7,
                balance_after=7,
                reason="admin_recharge",
            )
        )
        db.commit()
        user_id = user.id
    finally:
        db.close()

    admin_headers = _admin_auth_headers(client)
    response = client.get(f"/api/admin/users/{user_id}/details", headers=admin_headers)

    assert response.status_code == 200
    transactions = response.json()["recent_credit_transactions"]
    assert transactions[0]["reason_label"] == "管理员充值"
    assert transactions[0]["delta"] == 7
    assert transactions[0]["balance_after"] == 7
