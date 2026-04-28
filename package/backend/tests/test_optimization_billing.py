from app.database import SessionLocal
from app.models.models import CreditTransaction, OptimizationSession, User
from app.utils.auth import create_user_access_token, get_password_hash


class NoRunBackgroundTasks:
    def add_task(self, *args, **kwargs):
        return None


async def _noop_run_optimization(*args, **kwargs):
    return None


def _create_user(credit_balance=0, is_unlimited=False):
    db = SessionLocal()
    try:
        user = User(
            username="alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=credit_balance,
            is_unlimited=is_unlimited,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        return user.id, token
    finally:
        db.close()


def test_calculate_optimization_credits_uses_billable_characters_and_stage_multiplier():
    from app.services.credit_service import calculate_optimization_credits, count_billable_characters

    assert count_billable_characters("a b\nc") == 3
    assert calculate_optimization_credits("短文本", "paper_enhance") == 1
    assert calculate_optimization_credits("汉" * 1000, "paper_enhance") == 1
    assert calculate_optimization_credits("汉" * 1001, "paper_enhance") == 2
    assert calculate_optimization_credits("汉" * 3000, "paper_polish_enhance") == 6


def test_platform_mode_holds_character_based_credits_before_processing(client, monkeypatch):
    from app.routes import optimization

    user_id, token = _create_user(credit_balance=8)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)
    monkeypatch.setattr(optimization, "run_optimization", _noop_run_optimization)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "汉" * 3000,
            "processing_mode": "paper_polish_enhance",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["charge_status"] == "held"
    assert response.json()["charged_credits"] == 6

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        session = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).one()
        transaction = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).one()
        assert user.credit_balance == 2
        assert session.billing_mode == "platform"
        assert transaction.delta == -6
        assert transaction.reason == "optimization_start"
    finally:
        db.close()


def test_byok_mode_does_not_consume_credits(client, monkeypatch):
    from app.routes import optimization

    user_id, token = _create_user(credit_balance=0)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)
    monkeypatch.setattr(optimization, "run_optimization", _noop_run_optimization)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_polish",
            "billing_mode": "byok",
            "polish_config": {
                "model": "gpt-5.4",
                "api_key": "sk-test",
                "base_url": "https://api.example/v1",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["charge_status"] == "not_charged"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
        assert user.credit_balance == 0
        assert transactions == []
    finally:
        db.close()


def test_platform_mode_rejects_user_with_insufficient_credits(client, monkeypatch):
    from app.routes import optimization

    _, token = _create_user(credit_balance=5)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)
    monkeypatch.setattr(optimization, "run_optimization", _noop_run_optimization)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "汉" * 3000,
            "processing_mode": "paper_polish_enhance",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "平台剩余啤酒不足，本次需要 6 啤酒，当前剩余 5 啤酒"


def test_credit_service_public_error_messages_use_beer_unit():
    from fastapi import HTTPException
    from app.services.credit_service import CreditService

    user_id, _ = _create_user(credit_balance=0)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        service = CreditService(db)

        error_checks = [
            (lambda: service.hold_platform_credit(user, reason="test", amount=0), "扣除啤酒必须大于 0"),
            (lambda: service.refund_platform_credit(user, reason="test", amount=0), "退回啤酒必须大于 0"),
            (lambda: service.add_credits(user, amount=0, reason="test"), "充值啤酒必须大于 0"),
        ]

        for action, expected_detail in error_checks:
            try:
                action()
            except HTTPException as exc:
                assert exc.detail == expected_detail
            else:
                raise AssertionError("expected HTTPException")
    finally:
        db.close()


def test_failed_platform_job_refunds_held_credits_once():
    from app.services.credit_service import CreditService

    user_id, _ = _create_user(credit_balance=5)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        session = OptimizationSession(
            user_id=user.id,
            session_id="session-1",
            original_text="test paragraph",
            current_stage="polish",
            status="queued",
            billing_mode="platform",
            charge_status="held",
            charged_credits=3,
        )
        db.add(session)
        db.flush()
        CreditService(db).hold_platform_credit(user, reason="optimization_start", session_id=session.id, amount=3)
        db.commit()

        CreditService(db).refund_held_platform_credit(session)
        db.commit()
        CreditService(db).refund_held_platform_credit(session)
        db.commit()

        db.refresh(user)
        assert user.credit_balance == 5
        assert session.charge_status == "refunded"
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).all()
        assert [txn.delta for txn in transactions] == [-3, 3]
    finally:
        db.close()
