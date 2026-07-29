import asyncio
from datetime import timedelta

import app.config as config_module
from sqlalchemy import text
from app.database import SessionLocal
from app.models.models import CreditTransaction, OptimizationSession, User, WorkerLease
from app.services.credit_service import CreditService
from app.services import task_queue
from app.services.task_queue import process_next_queued_session, process_session_by_id
from app.services.task_control import TaskSuspended
from app.services.worker_lease import register_worker_lease, update_worker_lease
from app.utils.auth import create_user_access_token, get_password_hash
from app.utils.time import utcnow
import worker as worker_module


def _create_user(credit_balance=0, username="alice"):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
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
    worker_attempt_count=0,
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
            worker_attempt_count=worker_attempt_count,
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


def test_user_can_keep_only_one_active_plus_two_queued_sessions(client, monkeypatch):
    _, token = _create_user(credit_balance=20)
    monkeypatch.setattr(config_module.settings, "INLINE_TASK_WORKER_ENABLED", False, raising=False)
    monkeypatch.setattr(config_module.settings, "MAX_PENDING_SESSIONS_PER_USER", 3, raising=False)
    payload = {
        "original_text": "汉" * 1000,
        "processing_mode": "paper_polish",
        "billing_mode": "platform",
    }

    responses = [
        client.post(
            "/api/optimization/start",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        for _ in range(4)
    ]

    assert [response.status_code for response in responses[:3]] == [200, 200, 200]
    assert responses[3].status_code == 409
    assert "1 个运行、2 个排队" in responses[3].json()["detail"]


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
                last_used=utcnow() - timedelta(seconds=61),
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
        assert older.worker_attempt_count == 1
        assert newer.status == "queued"
        assert newer.worker_id is None
    finally:
        db.close()


def test_claim_skips_user_with_active_external_wait_and_runs_other_user():
    first_user_id, _ = _create_user(username="alice")
    second_user_id, _ = _create_user(username="bob")
    _create_session(
        first_user_id,
        "alice-waiting-plugin",
        status="waiting_browser_agent",
        created_at=utcnow() - timedelta(minutes=10),
    )
    alice_queued_id = _create_session(
        first_user_id,
        "alice-queued",
        created_at=utcnow() - timedelta(minutes=9),
    )
    bob_queued_id = _create_session(
        second_user_id,
        "bob-queued",
        created_at=utcnow() - timedelta(minutes=1),
    )
    processed = []

    async def fake_runner(db, session):
        processed.append(session.session_id)
        session.status = "completed"
        session.completed_at = utcnow()
        db.commit()

    assert asyncio.run(process_next_queued_session("fair-worker", runner=fake_runner)) is True
    assert processed == ["bob-queued"]

    db = SessionLocal()
    try:
        assert db.get(OptimizationSession, alice_queued_id).status == "queued"
        assert db.get(OptimizationSession, bob_queued_id).status == "completed"
    finally:
        db.close()


def test_task_suspension_releases_worker_without_failure_or_refund():
    user_id, _ = _create_user(credit_balance=0)
    session_id = _create_session(
        user_id,
        "suspended-session",
        charged_credits=2,
    )

    async def suspended_runner(db, session):
        raise TaskSuspended(
            "等待本机朱雀插件返回检测结果",
            reason="browser_agent",
            external_job_id="zaj_test",
        )

    assert asyncio.run(
        process_next_queued_session("suspension-worker", runner=suspended_runner)
    ) is True

    db = SessionLocal()
    try:
        session = db.get(OptimizationSession, session_id)
        assert session.status == "waiting_browser_agent"
        assert session.worker_id is None
        assert session.finished_at is None
        assert session.charge_status == "held"
        assert session.charged_credits == 2
    finally:
        db.close()


def test_worker_capacity_hot_setting_is_bounded_to_ten(monkeypatch):
    monkeypatch.setattr(config_module.settings, "TASK_WORKER_MAX_CONCURRENCY", 10, raising=False)
    for configured, expected in ((5, 5), (8, 8), (10, 10), (7, 5), (20, 5)):
        monkeypatch.setattr(config_module.settings, "MAX_CONCURRENT_USERS", configured, raising=False)
        assert worker_module.configured_worker_capacity() == expected


def test_multiple_worker_slots_process_different_users_concurrently():
    for index in range(5):
        user_id, _ = _create_user(username=f"parallel-user-{index}")
        _create_session(user_id, f"parallel-session-{index}")

    active = 0
    maximum_active = 0
    all_entered = asyncio.Event()
    release = asyncio.Event()

    async def blocking_runner(db, session):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        if active == 5:
            all_entered.set()
        await all_entered.wait()
        await release.wait()
        session.status = "completed"
        session.completed_at = utcnow()
        db.commit()
        active -= 1

    async def run_slots():
        tasks = [
            asyncio.create_task(
                process_next_queued_session(f"parallel-worker-{index}", runner=blocking_runner)
            )
            for index in range(5)
        ]
        await asyncio.wait_for(all_entered.wait(), timeout=5)
        release.set()
        return await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)

    assert asyncio.run(run_slots()) == [True] * 5
    assert maximum_active == 5


def test_inline_tasks_for_same_user_wait_in_queue_instead_of_violating_active_guard(monkeypatch):
    monkeypatch.setattr(config_module.settings, "TASK_WORKER_POLL_INTERVAL", 0.01, raising=False)
    user_id, _ = _create_user(username="inline-serial-user")
    first_id = _create_session(user_id, "inline-first")
    second_id = _create_session(user_id, "inline-second")
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order = []

    async def runner(db, session):
        order.append(f"start:{session.session_id}")
        if session.id == first_id:
            first_entered.set()
            await release_first.wait()
        session.status = "completed"
        session.completed_at = utcnow()
        db.commit()
        order.append(f"end:{session.session_id}")

    async def run_inline_tasks():
        first = asyncio.create_task(process_session_by_id(first_id, runner=runner))
        await asyncio.wait_for(first_entered.wait(), timeout=3)
        second = asyncio.create_task(process_session_by_id(second_id, runner=runner))
        await asyncio.sleep(0.1)
        db = SessionLocal()
        try:
            assert db.get(OptimizationSession, second_id).status == "queued"
        finally:
            db.close()
        release_first.set()
        return await asyncio.wait_for(asyncio.gather(first, second), timeout=3)

    assert asyncio.run(run_inline_tasks()) == [True, True]
    assert order == [
        "start:inline-first",
        "end:inline-first",
        "start:inline-second",
        "end:inline-second",
    ]


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
    fresh_user_id, _ = _create_user(username="fresh-worker-user")
    stale_time = utcnow() - timedelta(minutes=30)
    fresh_time = utcnow()
    stale_id = _create_session(
        fresh_user_id,
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


def test_recover_stale_processing_session_stops_after_bounded_attempts(monkeypatch):
    monkeypatch.setattr(config_module.settings, "TASK_WORKER_MAX_ATTEMPTS", 3, raising=False)
    user_id, _ = _create_user()
    stale_time = utcnow() - timedelta(minutes=30)
    session_id = _create_session(
        user_id,
        "dead-letter-session",
        status="processing",
        created_at=stale_time,
        updated_at=stale_time,
        started_at=stale_time,
        worker_id="dead-worker",
        worker_attempt_count=3,
    )
    db = SessionLocal()
    try:
        session = db.get(OptimizationSession, session_id)
        session.billing_mode = "byok"
        session.credential_source = "request"
        session.polish_api_key = "transient-secret"
        session.updated_at = stale_time
        db.commit()
        db.execute(
            text("UPDATE optimization_sessions SET updated_at = :stale WHERE id = :session_id"),
            {"stale": stale_time, "session_id": session_id},
        )
        db.commit()

        assert task_queue.recover_stale_processing_sessions(db, stale_after_seconds=60) == 1
        db.refresh(session)
        assert session.status == "failed"
        assert session.polish_api_key is None
        assert session.finished_at is not None
        assert "最大尝试次数" in session.error_message
    finally:
        db.close()


def test_queue_status_uses_database_order_and_idle_worker_lease(monkeypatch):
    monkeypatch.setattr(config_module.settings, "INLINE_TASK_WORKER_ENABLED", False, raising=False)
    user_id, _ = _create_user()
    _create_session(user_id, "queue-first", created_at=utcnow() - timedelta(minutes=5))
    _create_session(user_id, "queue-second", created_at=utcnow())
    register_worker_lease("lease-worker", "boot-1", version="test", capacity=1)

    db = SessionLocal()
    try:
        status = task_queue.get_persistent_queue_status(
            db,
            user_id=user_id,
            session_id="queue-second",
        )
        lease = db.get(WorkerLease, "lease-worker")
        assert status["queue_length"] == 2
        assert status["your_position"] == 2
        assert status["max_users"] == 1
        assert status["estimated_wait_time"] == 600
        assert lease.state == "idle"
        assert update_worker_lease("lease-worker", "wrong-boot", state="busy") is False
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


def test_worker_preserves_user_stopped_status_when_active_runner_unblocks():
    user_id, _ = _create_user(credit_balance=0)
    session_id = _create_session(
        user_id,
        "externally-stopped-session",
        created_at=utcnow() - timedelta(minutes=1),
    )
    next_session_id = _create_session(user_id, "next-polish-session")

    async def runner_unblocked_by_stop(db, session):
        if session.id == next_session_id:
            session.status = "completed"
            session.progress = 100
            session.completed_at = utcnow()
            db.commit()
            return
        control_db = SessionLocal()
        try:
            controlled_session = control_db.get(OptimizationSession, session.id)
            controlled_session.status = "stopped"
            controlled_session.error_message = "用户手动停止"
            controlled_session.finished_at = utcnow()
            control_db.commit()
        finally:
            control_db.close()
        raise RuntimeError("browser-agent wait cancelled")

    assert asyncio.run(
        process_next_queued_session("stop-aware-worker", runner=runner_unblocked_by_stop)
    ) is True
    assert asyncio.run(
        process_next_queued_session("stop-aware-worker", runner=runner_unblocked_by_stop)
    ) is True

    db = SessionLocal()
    try:
        session = db.get(OptimizationSession, session_id)
        next_session = db.get(OptimizationSession, next_session_id)
        assert session.status == "stopped"
        assert session.error_message == "用户手动停止"
        assert session.finished_at is not None
        assert next_session.status == "completed"
        assert next_session.worker_id == "stop-aware-worker"
    finally:
        db.close()
