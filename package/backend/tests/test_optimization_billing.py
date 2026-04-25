from app.database import SessionLocal
from app.models.models import CreditTransaction, OptimizationSession, User
from app.utils.auth import create_user_access_token, get_password_hash


class NoRunBackgroundTasks:
    def add_task(self, *args, **kwargs):
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


def test_platform_mode_holds_one_credit_before_processing(client, monkeypatch):
    from app.routes import optimization

    user_id, token = _create_user(credit_balance=2)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_polish",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["charge_status"] == "held"
    assert response.json()["charged_credits"] == 1

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        session = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).one()
        transaction = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).one()
        assert user.credit_balance == 1
        assert session.billing_mode == "platform"
        assert transaction.delta == -1
        assert transaction.reason == "optimization_start"
    finally:
        db.close()


def test_byok_mode_does_not_consume_credits(client, monkeypatch):
    from app.routes import optimization

    user_id, token = _create_user(credit_balance=0)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)

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


def test_platform_mode_rejects_user_without_credits(client, monkeypatch):
    from app.routes import optimization

    _, token = _create_user(credit_balance=0)
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_polish",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "平台剩余次数不足"


def test_failed_platform_job_refunds_one_credit_once():
    from app.services.credit_service import CreditService

    user_id, _ = _create_user(credit_balance=2)
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
            charged_credits=1,
        )
        db.add(session)
        db.flush()
        CreditService(db).hold_platform_credit(user, reason="optimization_start", session_id=session.id)
        db.commit()

        CreditService(db).refund_held_platform_credit(session)
        db.commit()
        CreditService(db).refund_held_platform_credit(session)
        db.commit()

        db.refresh(user)
        assert user.credit_balance == 2
        assert session.charge_status == "refunded"
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).all()
        assert [txn.delta for txn in transactions] == [-1, 1]
    finally:
        db.close()
