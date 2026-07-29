import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy import inspect

import app.config as config_module

from app.database import SessionLocal, engine
from app.models.browser_agent_constants import (
    BROWSER_AGENT_STATUS_OFFLINE,
    BROWSER_AGENT_STATUS_ONLINE,
    BROWSER_AGENT_STATUS_REVOKED,
    BROWSER_AGENT_STATUSES,
    ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
    ZHUQUE_AGENT_JOB_STATUS_CLAIMED,
    ZHUQUE_AGENT_JOB_STATUS_COMPLETED,
    ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
    ZHUQUE_AGENT_JOB_STATUS_FAILED,
    ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED,
    ZHUQUE_AGENT_JOB_STATUS_PENDING,
    ZHUQUE_AGENT_JOB_STATUS_RUNNING,
    ZHUQUE_AGENT_JOB_STATUSES,
    ZHUQUE_AGENT_JOB_TERMINAL_STATUSES,
)
from app.models.models import BrowserAgent, BrowserAgentPairing, OptimizationSession, User, ZhuqueAgentJob
from app.services.browser_agent_service import BrowserAgentService, hash_agent_token, hash_pairing_code
from app.services.zhuque_browser_agent_transport import BrowserAgentZhuqueTransport
from app.services.zhuque_service import ZhuqueService
from app.services.task_control import TaskSuspended
from app.utils.auth import create_user_access_token, get_password_hash
from app.utils.time import utcnow


def _create_user(username="agent-user"):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            nickname=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username, token_version=user.token_version or 0)
        return user.id, token
    finally:
        db.close()


def test_browser_agent_schema_tables_and_indexes_exist():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "browser_agent_pairings" in tables
    assert "browser_agents" in tables
    assert "zhuque_agent_jobs" in tables

    pairing_columns = {column["name"] for column in inspector.get_columns("browser_agent_pairings")}
    assert {
        "id",
        "user_id",
        "pairing_code_hash",
        "expires_at",
        "claimed_at",
        "claimed_by_agent_id",
        "created_at",
    }.issubset(pairing_columns)

    agent_columns = {column["name"] for column in inspector.get_columns("browser_agents")}
    assert {
        "id",
        "user_id",
        "agent_id",
        "name",
        "token_hash",
        "status",
        "last_seen_at",
        "created_at",
        "updated_at",
        "revoked_at",
        "capabilities_json",
        "user_agent",
        "extension_version",
    }.issubset(agent_columns)

    job_columns = {column["name"] for column in inspector.get_columns("zhuque_agent_jobs")}
    assert {
        "id",
        "job_id",
        "user_id",
        "session_id",
        "segment_id",
        "status",
        "payload_text",
        "payload_hash",
        "result_json",
        "progress_json",
        "error_code",
        "error_message",
        "claimed_by_agent_id",
        "created_at",
        "claimed_at",
        "started_at",
        "completed_at",
        "expires_at",
        "heartbeat_at",
        "attempt_count",
    }.issubset(job_columns)

    indexes_by_table = {
        table: {index["name"] for index in inspector.get_indexes(table)}
        for table in ("browser_agent_pairings", "browser_agents", "zhuque_agent_jobs")
    }
    assert "ix_browser_agent_pairings_user_id" in indexes_by_table["browser_agent_pairings"]
    assert "ix_browser_agents_agent_id" in indexes_by_table["browser_agents"]
    assert "ix_zhuque_agent_jobs_status" in indexes_by_table["zhuque_agent_jobs"]
    assert "ix_zhuque_agent_jobs_claimed_by_agent_id" in indexes_by_table["zhuque_agent_jobs"]


def test_browser_agent_status_constants_are_complete():
    assert BROWSER_AGENT_STATUSES == {
        BROWSER_AGENT_STATUS_ONLINE,
        BROWSER_AGENT_STATUS_OFFLINE,
        BROWSER_AGENT_STATUS_REVOKED,
    }
    assert ZHUQUE_AGENT_JOB_STATUSES == {
        ZHUQUE_AGENT_JOB_STATUS_PENDING,
        ZHUQUE_AGENT_JOB_STATUS_CLAIMED,
        ZHUQUE_AGENT_JOB_STATUS_RUNNING,
        ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED,
        ZHUQUE_AGENT_JOB_STATUS_COMPLETED,
        ZHUQUE_AGENT_JOB_STATUS_FAILED,
        ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
        ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
    }
    assert ZHUQUE_AGENT_JOB_TERMINAL_STATUSES == {
        ZHUQUE_AGENT_JOB_STATUS_COMPLETED,
        ZHUQUE_AGENT_JOB_STATUS_FAILED,
        ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
        ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
    }


def test_browser_agent_pairing_claim_heartbeat_status_and_revoke(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, token = _create_user("pairing-user")

    pairing_response = client.post(
        "/api/browser-agent/pairings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pairing_response.status_code == 200
    pairing_body = pairing_response.json()
    assert pairing_body["pairing_code"].startswith("GANK-")

    claim_response = client.post(
        "/api/browser-agent/claim",
        json={
            "pairing_code": pairing_body["pairing_code"],
            "agent_id": "agent-flow-1",
            "name": "Chrome on Windows",
            "extension_version": "0.1.0",
            "capabilities": {"zhuque_detect": True},
            "user_agent": "Chrome/131",
        },
    )
    assert claim_response.status_code == 200
    claim_body = claim_response.json()
    assert claim_body["agent_id"] == "agent-flow-1"
    assert claim_body["user_id"] == user_id
    assert claim_body["agent_token"].startswith("gba_")

    status_response = client.get(
        "/api/browser-agent/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["required"] is True
    assert status_body["transport"] == "browser_agent"
    assert status_body["online"] is True
    assert status_body["agents"][0]["agent_id"] == "agent-flow-1"

    heartbeat_response = client.post(
        "/api/browser-agent/heartbeat",
        headers={"Authorization": f"Bearer {claim_body['agent_token']}"},
        json={
            "agent_id": "agent-flow-1",
            "status": "online",
            "metadata": {
                "zhuque": {
                    "page_found": True,
                    "logged_in": True,
                    "user_name": "木木",
                    "remaining_uses": 7,
                    "message": "朱雀已登录：木木",
                }
            },
        },
    )
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["ok"] is True

    status_after_heartbeat = client.get(
        "/api/browser-agent/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_after_heartbeat.status_code == 200
    heartbeat_status_body = status_after_heartbeat.json()
    assert heartbeat_status_body["zhuque"]["logged_in"] is True
    assert heartbeat_status_body["zhuque"]["user_name"] == "木木"
    assert heartbeat_status_body["agents"][0]["zhuque_status"]["remaining_uses"] == 7

    revoke_response = client.post(
        "/api/browser-agent/revoke",
        headers={"Authorization": f"Bearer {token}"},
        json={"agent_id": "agent-flow-1"},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["ok"] is True

    heartbeat_after_revoke = client.post(
        "/api/browser-agent/heartbeat",
        headers={"Authorization": f"Bearer {claim_body['agent_token']}"},
        json={"agent_id": "agent-flow-1", "status": "online"},
    )
    assert heartbeat_after_revoke.status_code == 401


def test_browser_agent_status_preserves_anonymous_detection_readiness(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, token = _create_user("anonymous-agent-user")
    agent_token = "gba_anonymous_agent"
    db = SessionLocal()
    try:
        db.add(
            BrowserAgent(
                user_id=user_id,
                agent_id="agent-anonymous",
                name="Anonymous Chrome",
                token_hash=hash_agent_token(agent_token),
                status=BROWSER_AGENT_STATUS_ONLINE,
                last_seen_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    heartbeat_response = client.post(
        "/api/browser-agent/heartbeat",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "agent_id": "agent-anonymous",
            "status": "online",
            "metadata": {
                "zhuque": {
                    "page_found": True,
                    "logged_in": False,
                    "button_enabled": True,
                    "remaining_uses": 3,
                    "message": "朱雀游客检测可用",
                }
            },
        },
    )
    assert heartbeat_response.status_code == 200

    status_response = client.get(
        "/api/browser-agent/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["zhuque"]["logged_in"] is False
    assert body["zhuque"]["button_enabled"] is True
    assert body["zhuque"]["remaining_uses"] == 3
    assert "游客检测可用" in body["message"]

    transport_status = BrowserAgentZhuqueTransport(user_id).status()
    assert transport_status["ready"] is True
    assert transport_status["has_token"] is False
    assert transport_status["button_enabled"] is True
    assert "游客检测可用" in transport_status["message"]


def test_browser_agent_claim_rejects_expired_or_reused_pairing(client):
    user_id, _ = _create_user("expired-pairing-user")
    db = SessionLocal()
    try:
        expired_code = "GANK-OLD1"
        db.add(
            BrowserAgentPairing(
                user_id=user_id,
                pairing_code_hash=hash_pairing_code(expired_code),
                expires_at=utcnow() - timedelta(seconds=1),
            )
        )
        claimed_code = "GANK-USED"
        db.add(
            BrowserAgentPairing(
                user_id=user_id,
                pairing_code_hash=hash_pairing_code(claimed_code),
                expires_at=utcnow() + timedelta(minutes=5),
                claimed_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    for code in (expired_code, claimed_code):
        response = client.post(
            "/api/browser-agent/claim",
            json={"pairing_code": code, "agent_id": f"agent-{code}", "capabilities": {}},
        )
        assert response.status_code == 400
        assert "配对码无效" in response.json()["detail"]


def test_browser_agent_status_marks_stale_heartbeat_offline(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT", 30, raising=False)
    user_id, token = _create_user("stale-agent-user")
    db = SessionLocal()
    try:
        db.add(
            BrowserAgent(
                user_id=user_id,
                agent_id="agent-stale",
                name="Stale Chrome",
                token_hash="stale-token-hash",
                status=BROWSER_AGENT_STATUS_ONLINE,
                last_seen_at=utcnow() - timedelta(seconds=120),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/browser-agent/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["online"] is False
    assert body["agents"][0]["status"] == BROWSER_AGENT_STATUS_OFFLINE


def test_browser_agent_job_claim_progress_complete_and_fail(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS", 0, raising=False)
    user_id, _ = _create_user("job-user")
    agent_token = "gba_job_token"
    db = SessionLocal()
    try:
        agent = BrowserAgent(
            user_id=user_id,
            agent_id="agent-job-1",
            name="Job Chrome",
            token_hash=hash_agent_token(agent_token),
            status=BROWSER_AGENT_STATUS_ONLINE,
            last_seen_at=utcnow(),
        )
        db.add(agent)
        db.commit()
        job = BrowserAgentService(db).create_zhuque_job(
            user_id=user_id,
            text="需要检测的正文",
            timeout_seconds=120,
        )
        job_id = job.job_id
    finally:
        db.close()

    claim_response = client.post(
        "/api/browser-agent/jobs/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"agent_id": "agent-job-1", "wait_seconds": 0},
    )
    assert claim_response.status_code == 200
    claim_body = claim_response.json()
    assert claim_body["job"]["job_id"] == job_id
    assert claim_body["job"]["text"] == "需要检测的正文"

    progress_response = client.post(
        f"/api/browser-agent/jobs/{job_id}/progress",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "status": "manual_required",
            "message": "请在本机朱雀页面完成验证码",
            "progress": 0.5,
            "metadata": {"reason": "captcha"},
        },
    )
    assert progress_response.status_code == 200

    complete_response = client.post(
        f"/api/browser-agent/jobs/{job_id}/complete",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"result": {"success": True, "source": "browser_agent", "rate": 12.3}},
    )
    assert complete_response.status_code == 200

    duplicate_complete = client.post(
        f"/api/browser-agent/jobs/{job_id}/complete",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"result": {"success": True}},
    )
    assert duplicate_complete.status_code == 400

    db = SessionLocal()
    try:
        stored_job = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.job_id == job_id).one()
        assert stored_job.status == ZHUQUE_AGENT_JOB_STATUS_COMPLETED
        assert json.loads(stored_job.result_json)["source"] == "browser_agent"
        assert json.loads(stored_job.progress_json)["metadata"]["reason"] == "captcha"
    finally:
        db.close()

    db = SessionLocal()
    try:
        failed_job = BrowserAgentService(db).create_zhuque_job(
            user_id=user_id,
            text="失败正文",
            timeout_seconds=120,
        )
        failed_job_id = failed_job.job_id
    finally:
        db.close()

    assert client.post(
        "/api/browser-agent/jobs/claim",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"agent_id": "agent-job-1", "wait_seconds": 0},
    ).status_code == 200
    fail_response = client.post(
        f"/api/browser-agent/jobs/{failed_job_id}/fail",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"error_code": "zhuque_not_logged_in", "message": "请先登录朱雀", "retryable": True},
    )
    assert fail_response.status_code == 200
    db = SessionLocal()
    try:
        stored_failed_job = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.job_id == failed_job_id).one()
        assert stored_failed_job.status == ZHUQUE_AGENT_JOB_STATUS_FAILED
        assert stored_failed_job.error_code == "zhuque_not_logged_in"
    finally:
        db.close()


def test_browser_agent_job_claim_enforces_user_ownership(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS", 0, raising=False)
    user_a_id, _ = _create_user("job-owner-a")
    user_b_id, _ = _create_user("job-owner-b")
    token_a = "gba_owner_a"
    token_b = "gba_owner_b"
    db = SessionLocal()
    try:
        db.add_all(
            [
                BrowserAgent(
                    user_id=user_a_id,
                    agent_id="agent-owner-a",
                    token_hash=hash_agent_token(token_a),
                    status=BROWSER_AGENT_STATUS_ONLINE,
                    last_seen_at=utcnow(),
                ),
                BrowserAgent(
                    user_id=user_b_id,
                    agent_id="agent-owner-b",
                    token_hash=hash_agent_token(token_b),
                    status=BROWSER_AGENT_STATUS_ONLINE,
                    last_seen_at=utcnow(),
                ),
            ]
        )
        db.commit()
        job = BrowserAgentService(db).create_zhuque_job(user_id=user_a_id, text="A 的正文", timeout_seconds=120)
        job_id = job.job_id
    finally:
        db.close()

    user_b_claim = client.post(
        "/api/browser-agent/jobs/claim",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"agent_id": "agent-owner-b", "wait_seconds": 0},
    )
    assert user_b_claim.status_code == 200
    assert user_b_claim.json()["job"] is None

    user_a_claim = client.post(
        "/api/browser-agent/jobs/claim",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"agent_id": "agent-owner-a", "wait_seconds": 0},
    )
    assert user_a_claim.status_code == 200
    assert user_a_claim.json()["job"]["job_id"] == job_id

    user_b_complete = client.post(
        f"/api/browser-agent/jobs/{job_id}/complete",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"result": {"success": True}},
    )
    assert user_b_complete.status_code == 404


def test_browser_agent_job_cancel_marks_session_jobs_cancelled():
    user_id, _ = _create_user("cancel-job-user")
    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="cancel-session-1",
            original_text="测试正文",
            current_stage="ai_detect_reduce",
            status="processing",
            processing_mode="ai_detect_reduce",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        job = BrowserAgentService(db).create_zhuque_job(
            user_id=user_id,
            session_id=session.id,
            text="取消正文",
            timeout_seconds=120,
        )
        assert BrowserAgentService(db).cancel_zhuque_jobs_for_session(session_id=session.id) == 1
        db.refresh(job)
        assert job.status == ZHUQUE_AGENT_JOB_STATUS_CANCELLED
        assert job.error_code == "zhuque_browser_agent_job_cancelled"
    finally:
        db.close()


def test_browser_agent_job_expiry_marks_pending_job_expired():
    user_id, _ = _create_user("expired-job-user")
    db = SessionLocal()
    try:
        job = ZhuqueAgentJob(
            job_id="expired-job-1",
            user_id=user_id,
            status=ZHUQUE_AGENT_JOB_STATUS_PENDING,
            payload_text="过期正文",
            payload_hash="expired-hash",
            expires_at=utcnow() - timedelta(seconds=1),
        )
        db.add(job)
        db.commit()
        assert BrowserAgentService(db).expire_stale_jobs() == 1
        db.refresh(job)
        assert job.status == ZHUQUE_AGENT_JOB_STATUS_EXPIRED
        assert job.error_code == "zhuque_browser_agent_job_expired"
    finally:
        db.close()


def test_browser_agent_transport_status_requires_online_agent(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, _ = _create_user("transport-offline-user")

    status = BrowserAgentZhuqueTransport(user_id).status()

    assert status["ready"] is False
    assert status["connected"] is False
    assert status["auth_mode"] == "browser_agent"
    assert "插件" in status["message"]


async def _complete_first_browser_agent_job(user_id, agent_token, agent_id):
    for _ in range(50):
        db = SessionLocal()
        try:
            pending = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.user_id == user_id).first()
        finally:
            db.close()
        if pending:
            break
        await asyncio.sleep(0.1)
    db = SessionLocal()
    try:
        service = BrowserAgentService(db)
        agent = service.authenticate_agent(agent_token)
        job = service.claim_next_zhuque_job(agent=agent, agent_id=agent_id)
        assert job is not None
        service.update_zhuque_job_progress(
            agent=agent,
            job_id=job.job_id,
            next_status=ZHUQUE_AGENT_JOB_STATUS_RUNNING,
            message="本机浏览器正在检测",
            progress=0.5,
            metadata={},
        )
        service.complete_zhuque_job(
            agent=agent,
            job_id=job.job_id,
            result={
                "success": True,
                "rate": 18.5,
                "labels_ratio": {"0": 0.185, "1": 0.8, "2": 0.015},
                "segment_labels": [],
            },
        )
    finally:
        db.close()


def test_browser_agent_transport_suspends_requeues_and_resumes_exact_result(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT", 10, raising=False)
    user_id, _ = _create_user("transport-detect-user")
    agent_token = "gba_transport_token"
    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="transport-detect-session",
            original_text="本机浏览器检测正文",
            current_stage="ai_detect_reduce",
            status="processing",
            processing_mode="ai_detect_reduce",
        )
        db.add(
            BrowserAgent(
                user_id=user_id,
                agent_id="agent-transport-1",
                token_hash=hash_agent_token(agent_token),
                status=BROWSER_AGENT_STATUS_ONLINE,
                last_seen_at=utcnow(),
            )
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_db_id = session.id
    finally:
        db.close()

    with pytest.raises(TaskSuspended, match="等待本机朱雀插件"):
        asyncio.run(
            BrowserAgentZhuqueTransport(user_id).detect(
                "本机浏览器检测正文",
                timeout=10,
                session_id=session_db_id,
            )
        )

    db = SessionLocal()
    try:
        waiting_session = db.get(OptimizationSession, session_db_id)
        assert waiting_session.status == "waiting_browser_agent"
        service = BrowserAgentService(db)
        agent = service.authenticate_agent(agent_token)
        job = service.claim_next_zhuque_job(agent=agent, agent_id="agent-transport-1")
        assert job is not None
        service.complete_zhuque_job(
            agent=agent,
            job_id=job.job_id,
            result={
                "success": True,
                "rate": 18.5,
                "labels_ratio": {"0": 0.185, "1": 0.8, "2": 0.015},
                "segment_labels": [],
            },
        )
        db.refresh(waiting_session)
        assert waiting_session.status == "queued"
        assert waiting_session.worker_id is None
    finally:
        db.close()

    result = asyncio.run(
        BrowserAgentZhuqueTransport(user_id).detect(
            "本机浏览器检测正文",
            timeout=10,
            session_id=session_db_id,
        )
    )

    assert result["success"] is True
    assert result["source"] == "browser_agent"
    assert result["rate"] == 18.5
    db = SessionLocal()
    try:
        stored_job = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.user_id == user_id).one()
        assert stored_job.session_id == session_db_id
    finally:
        db.close()


def test_browser_agent_transport_retry_creates_new_job_after_previous_terminal_failure(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, _ = _create_user("transport-retry-user")
    agent_token = "gba_transport_retry"
    text = "重试时需要重新检测的正文"
    db = SessionLocal()
    try:
        agent = BrowserAgent(
            user_id=user_id,
            agent_id="agent-transport-retry",
            token_hash=hash_agent_token(agent_token),
            status=BROWSER_AGENT_STATUS_ONLINE,
            last_seen_at=utcnow(),
        )
        session = OptimizationSession(
            user_id=user_id,
            session_id="transport-retry-session",
            original_text=text,
            current_stage="ai_detect_reduce",
            status="processing",
            processing_mode="ai_detect_reduce",
        )
        db.add_all([agent, session])
        db.commit()
        db.refresh(session)

        service = BrowserAgentService(db)
        old_job = service.create_zhuque_job(
            user_id=user_id,
            session_id=session.id,
            text=text,
            timeout_seconds=120,
        )
        claimed = service.claim_next_zhuque_job(agent=agent, agent_id=agent.agent_id)
        assert claimed is not None
        old_job = service.fail_zhuque_job(
            agent=agent,
            job_id=old_job.job_id,
            error_code="temporary_failure",
            message="临时检测失败",
            retryable=True,
        )

        # Emulate the user retrying after the resumed worker consumed the
        # terminal failure. A retry must not be poisoned forever by that job.
        session = db.get(OptimizationSession, session.id)
        session.status = "processing"
        session.queued_at = old_job.completed_at + timedelta(seconds=1)
        session.started_at = session.queued_at
        db.commit()
        session_db_id = session.id
    finally:
        db.close()

    with pytest.raises(TaskSuspended, match="等待本机朱雀插件"):
        asyncio.run(
            BrowserAgentZhuqueTransport(user_id).detect(
                text,
                session_id=session_db_id,
            )
        )

    db = SessionLocal()
    try:
        jobs = (
            db.query(ZhuqueAgentJob)
            .filter(ZhuqueAgentJob.session_id == session_db_id)
            .order_by(ZhuqueAgentJob.id.asc())
            .all()
        )
        assert [job.status for job in jobs] == [
            ZHUQUE_AGENT_JOB_STATUS_FAILED,
            ZHUQUE_AGENT_JOB_STATUS_PENDING,
        ]
        assert db.get(OptimizationSession, session_db_id).status == "waiting_browser_agent"
    finally:
        db.close()


def test_stopping_suspended_session_cancels_browser_agent_job(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT", 30, raising=False)
    user_id, user_token = _create_user("transport-stop-user")
    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="transport-stop-session",
            original_text="等待插件的检测正文",
            current_stage="ai_detect_reduce",
            status="processing",
            processing_mode="ai_detect_reduce",
        )
        db.add_all(
            [
                BrowserAgent(
                    user_id=user_id,
                    agent_id="agent-transport-stop",
                    token_hash=hash_agent_token("gba_transport_stop"),
                    status=BROWSER_AGENT_STATUS_ONLINE,
                    last_seen_at=utcnow(),
                ),
                session,
            ]
        )
        db.commit()
        db.refresh(session)
        session_db_id = session.id
    finally:
        db.close()

    async def run_and_stop():
        with pytest.raises(TaskSuspended):
            await BrowserAgentZhuqueTransport(user_id).detect(
                "等待插件的检测正文",
                timeout=30,
                session_id=session_db_id,
            )

        stop_response = await asyncio.to_thread(
            client.post,
            "/api/optimization/sessions/transport-stop-session/stop",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert stop_response.status_code == 200

    asyncio.run(run_and_stop())
    db = SessionLocal()
    try:
        stopped_session = db.query(OptimizationSession).filter(OptimizationSession.id == session_db_id).one()
        job = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.session_id == session_db_id).one()
        assert stopped_session.status == "stopped"
        assert job.status == ZHUQUE_AGENT_JOB_STATUS_CANCELLED
    finally:
        db.close()


def test_browser_agent_transport_without_session_keeps_direct_wait_compatibility(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    monkeypatch.setattr(config_module.settings, "ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT", 10, raising=False)
    user_id, _ = _create_user("transport-direct-user")
    agent_token = "gba_transport_direct"
    db = SessionLocal()
    try:
        db.add(
            BrowserAgent(
                user_id=user_id,
                agent_id="agent-transport-direct",
                token_hash=hash_agent_token(agent_token),
                status=BROWSER_AGENT_STATUS_ONLINE,
                last_seen_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    async def run_direct_detect():
        completer = asyncio.create_task(
            _complete_first_browser_agent_job(user_id, agent_token, "agent-transport-direct")
        )
        result = await BrowserAgentZhuqueTransport(user_id).detect(
            "无会话直接检测正文",
            timeout=10,
        )
        await completer
        return result

    result = asyncio.run(run_direct_detect())
    assert result["success"] is True

def test_zhuque_service_browser_agent_readiness_and_start(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, _ = _create_user("service-browser-agent-user")
    db = SessionLocal()
    try:
        db.add(
            BrowserAgent(
                user_id=user_id,
                agent_id="agent-service-1",
                token_hash=hash_agent_token("gba_service_token"),
                status=BROWSER_AGENT_STATUS_ONLINE,
                last_seen_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()
    service = ZhuqueService(owner_label=f"user_{user_id}", user_id=user_id)

    readiness = asyncio.run(service.readiness("汉" * 400))
    assert readiness["ready"] is True
    assert readiness["auth_mode"] == "browser_agent"
    assert readiness["text_length_ok"] is True

    asyncio.run(service.start())
    assert service.is_ready is True
    asyncio.run(service.close())


def test_zhuque_service_browser_agent_start_allows_durable_result_resume(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ZHUQUE_DETECT_TRANSPORT", "browser_agent", raising=False)
    user_id, _ = _create_user("service-browser-agent-offline-user")
    service = ZhuqueService(owner_label=f"user_{user_id}", user_id=user_id)

    asyncio.run(service.start())
    assert service.is_ready is True
    readiness = asyncio.run(service.readiness("汉" * 400))
    assert readiness["ready"] is False
    asyncio.run(service.close())


def test_browser_agent_models_persist_relationships():
    db = SessionLocal()
    try:
        user = User(
            username="agent-user",
            password_hash="hash",
            access_link="http://testserver/access/agent-user",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        pairing = BrowserAgentPairing(
            user_id=user.id,
            pairing_code_hash="pairing-hash",
            expires_at=utcnow() + timedelta(minutes=10),
        )
        agent = BrowserAgent(
            user_id=user.id,
            agent_id="agent-1",
            name="Chrome on Windows",
            token_hash="token-hash",
            status=BROWSER_AGENT_STATUS_ONLINE,
            last_seen_at=utcnow(),
            capabilities_json='{"zhuque_detect": true}',
            user_agent="Chrome/131",
            extension_version="0.1.0",
        )
        session = OptimizationSession(
            user_id=user.id,
            session_id="session-agent-1",
            original_text="测试正文",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
        )
        db.add_all([pairing, agent, session])
        db.commit()
        db.refresh(session)

        job = ZhuqueAgentJob(
            job_id="job-1",
            user_id=user.id,
            session_id=session.id,
            status=ZHUQUE_AGENT_JOB_STATUS_PENDING,
            payload_text="需要朱雀检测的正文",
            payload_hash="payload-hash",
            claimed_by_agent_id=agent.agent_id,
            expires_at=utcnow() + timedelta(minutes=15),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        assert job.user.username == "agent-user"
        assert job.session.session_id == "session-agent-1"
        assert job.claimed_agent.agent_id == "agent-1"
        assert user.browser_agent_pairings[0].pairing_code_hash == "pairing-hash"
        assert user.browser_agents[0].agent_id == "agent-1"
        assert user.zhuque_agent_jobs[0].job_id == "job-1"
    finally:
        db.close()
