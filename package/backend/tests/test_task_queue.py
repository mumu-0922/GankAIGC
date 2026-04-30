import asyncio
from datetime import timedelta

import app.config as config_module
from app.database import SessionLocal
from app.models.models import CreditTransaction, OptimizationSession, User
from app.services.credit_service import CreditService
from app.services import task_queue
from app.services.task_queue import process_next_queued_session
from app.utils.auth import create_user_access_token, get_password_hash
from app.utils.time import utcnow


def _create_user(credit_balance=0):
    db = SessionLocal()
    try:
        user = User(
            username="alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=credit_balance,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        return user.id, token
    finally:
        db.close()


def _create_session(
    user_id,
    session_id,
    *,
    status="queued",
    created_at=None,
    updated_at=None,
    started_at=None,
    worker_id=None,
    charged_credits=0,
):
    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id=session_id,
            original_text="测试正文",
            current_stage="polish",
            status=status,
            progress=0,
            processing_mode="paper_polish",
            billing_mode="platform",
            charge_status="held" if charged_credits else "not_charged",
            charged_credits=charged_credits,
            created_at=created_at or utcnow(),
            updated_at=updated_at or created_at or utcnow(),
            started_at=started_at,
            worker_id=worker_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id
    finally:
        db.close()


def test_start_optimization_can_enqueue_without_inline_background_processing(client, monkeypatch):
    from app.routes import optimization

    _, token = _create_user(credit_balance=5)
    calls = []

    async def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("optimization should stay queued when inline worker is disabled")

    monkeypatch.setattr(config_module.settings, "INLINE_TASK_WORKER_ENABLED", False, raising=False)
    monkeypatch.setattr(optimization, "run_optimization", fail_if_called)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "汉" * 1000,
            "processing_mode": "paper_polish",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert calls == []


def test_queue_status_includes_recent_online_user_count(client):
    _, token = _create_user(credit_balance=0)
    db = SessionLocal()
    try:
        db.add(
            User(
                username="stale-user",
                password_hash=get_password_hash("Password123!"),
                access_link="http://testserver/access/stale-user",
                is_active=True,
                credit_balance=0,
                last_used=utcnow() - timedelta(minutes=10),
            )
        )
        db.add(
            User(
                username="inactive-recent-user",
                password_hash=get_password_hash("Password123!"),
                access_link="http://testserver/access/inactive-recent-user",
                is_active=False,
                credit_balance=0,
                last_used=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/optimization/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["online_users"] == 1


def test_process_next_queued_session_runs_oldest_queued_session():
    user_id, _ = _create_user()
    older_id = _create_session(user_id, "older-session", created_at=utcnow() - timedelta(minutes=5))
    newer_id = _create_session(user_id, "newer-session", created_at=utcnow())
    processed = []

    async def fake_runner(db, session):
        processed.append(session.session_id)
        session.status = "completed"
        session.progress = 100
        session.completed_at = utcnow()
        db.commit()

    assert asyncio.run(process_next_queued_session("test-worker", runner=fake_runner)) is True

    db = SessionLocal()
    try:
        older = db.query(OptimizationSession).filter(OptimizationSession.id == older_id).one()
        newer = db.query(OptimizationSession).filter(OptimizationSession.id == newer_id).one()
        assert processed == ["older-session"]
        assert older.status == "completed"
        assert older.worker_id == "test-worker"
        assert older.started_at is not None
        assert older.finished_at is not None
        assert newer.status == "queued"
        assert newer.worker_id is None
    finally:
        db.close()


def test_process_next_queued_session_refreshes_heartbeat_while_running(monkeypatch):
    monkeypatch.setattr(config_module.settings, "TASK_WORKER_HEARTBEAT_INTERVAL", 0.01, raising=False)

    user_id, _ = _create_user()
    session_id = _create_session(user_id, "heartbeat-session")
    heartbeat_seen = {}

    async def slow_runner(db, session):
        heartbeat_seen["initial"] = session.updated_at
        await asyncio.sleep(0.05)

        probe_db = SessionLocal()
        try:
            current = probe_db.query(OptimizationSession).filter(OptimizationSession.id == session_id).one()
            heartbeat_seen["current"] = current.updated_at
        finally:
            probe_db.close()

        session.status = "completed"
        session.progress = 100
        session.completed_at = utcnow()
        db.commit()

    assert asyncio.run(process_next_queued_session("heartbeat-worker", runner=slow_runner)) is True

    assert heartbeat_seen["current"] > heartbeat_seen["initial"]


def test_recover_stale_processing_sessions_requeues_dead_worker_session():
    user_id, _ = _create_user()
    stale_time = utcnow() - timedelta(minutes=30)
    fresh_time = utcnow()
    stale_id = _create_session(
        user_id,
        "stale-processing-session",
        status="processing",
        created_at=stale_time,
        updated_at=stale_time,
        started_at=stale_time,
        worker_id="dead-worker",
    )
    fresh_id = _create_session(
        user_id,
        "fresh-processing-session",
        status="processing",
        created_at=fresh_time,
        updated_at=fresh_time,
        started_at=fresh_time,
        worker_id="live-worker",
    )

    db = SessionLocal()
    try:
        recovered = task_queue.recover_stale_processing_sessions(db, stale_after_seconds=60)
        stale = db.query(OptimizationSession).filter(OptimizationSession.id == stale_id).one()
        fresh = db.query(OptimizationSession).filter(OptimizationSession.id == fresh_id).one()

        assert recovered == 1
        assert stale.status == "queued"
        assert stale.worker_id is None
        assert stale.started_at is None
        assert stale.finished_at is None
        assert "dead-worker" in stale.error_message
        assert fresh.status == "processing"
        assert fresh.worker_id == "live-worker"
    finally:
        db.close()


def test_process_next_queued_session_marks_failed_and_refunds_held_credit_once():
    user_id, _ = _create_user(credit_balance=5)
    session_id = _create_session(user_id, "failing-session", charged_credits=3)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session_id).one()
        CreditService(db).hold_platform_credit(
            user,
            reason="optimization_start",
            session_id=session.id,
            amount=3,
        )
        db.commit()
    finally:
        db.close()

    async def failing_runner(db, session):
        raise RuntimeError("worker failed")

    assert asyncio.run(process_next_queued_session("test-worker", runner=failing_runner)) is True

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
        assert session.status == "failed"
        assert session.charge_status == "refunded"
        assert session.error_message == "worker failed"
        assert session.finished_at is not None
        assert user.credit_balance == 5
        assert [transaction.delta for transaction in transactions] == [-3, 3]
    finally:
        db.close()
