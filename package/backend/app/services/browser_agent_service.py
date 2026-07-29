"""Browser-agent pairing and status service for VPS Zhuque detection."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.browser_agent_constants import (
    BROWSER_AGENT_STATUS_OFFLINE,
    BROWSER_AGENT_STATUS_ONLINE,
    BROWSER_AGENT_STATUS_REVOKED,
    ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
    ZHUQUE_AGENT_JOB_STATUS_CLAIMED,
    ZHUQUE_AGENT_JOB_STATUS_COMPLETED,
    ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
    ZHUQUE_AGENT_JOB_STATUS_FAILED,
    ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED,
    ZHUQUE_AGENT_JOB_STATUS_PENDING,
    ZHUQUE_AGENT_JOB_STATUS_RUNNING,
    ZHUQUE_AGENT_JOB_TERMINAL_STATUSES,
)
from app.models.models import BrowserAgent, BrowserAgentPairing, OptimizationSession, User, ZhuqueAgentJob
from app.utils.time import utcnow


@dataclass(frozen=True)
class IssuedAgentToken:
    token: str
    token_hash: str


def _hash_secret(value: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_pairing_code(pairing_code: str) -> str:
    return _hash_secret(normalize_pairing_code(pairing_code))


def hash_agent_token(agent_token: str) -> str:
    return _hash_secret(agent_token)


def normalize_pairing_code(pairing_code: str) -> str:
    return (pairing_code or "").strip().upper().replace(" ", "")


def generate_pairing_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "GANK-" + "".join(secrets.choice(alphabet) for _ in range(4))


def issue_agent_token() -> IssuedAgentToken:
    token = "gba_" + secrets.token_urlsafe(32)
    return IssuedAgentToken(token=token, token_hash=hash_agent_token(token))


def _coerce_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_agent_capabilities(agent: BrowserAgent) -> dict[str, Any]:
    try:
        payload = json.loads(agent.capabilities_json or "{}")
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def sanitize_zhuque_runtime_status(payload: Any, *, updated_at: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    user_name = str(payload.get("user_name") or payload.get("userName") or payload.get("nickname") or "").strip()[:80]
    status_value = str(payload.get("status") or "unknown").strip()[:40] or "unknown"
    logged_in = bool(payload.get("logged_in") or payload.get("connected") or payload.get("has_token"))
    page_found = bool(payload.get("page_found") or payload.get("pageFound"))
    button_enabled = bool(payload.get("button_enabled") or payload.get("buttonEnabled"))
    remaining_uses = _coerce_int(payload.get("remaining_uses", payload.get("remainingUses")), -1)
    message = str(payload.get("message") or "").strip()[:240]
    sanitized = {
        "page_found": page_found,
        "logged_in": logged_in,
        "connected": logged_in,
        "has_token": logged_in,
        "status": "logged_in" if logged_in else status_value,
        "user_name": user_name if logged_in else "",
        "remaining_uses": remaining_uses,
        "button_enabled": button_enabled,
        "message": message,
    }
    if updated_at:
        sanitized["updated_at"] = updated_at
    return sanitized


def zhuque_runtime_status_from_agent(agent: BrowserAgent) -> dict[str, Any]:
    capabilities = _load_agent_capabilities(agent)
    runtime = capabilities.get("_runtime") if isinstance(capabilities.get("_runtime"), dict) else {}
    return sanitize_zhuque_runtime_status(runtime.get("zhuque"), updated_at=runtime.get("updated_at"))


class BrowserAgentService:
    def __init__(self, db: Session):
        self.db = db

    def create_pairing(self, user: User) -> tuple[BrowserAgentPairing, str]:
        now = utcnow()
        expires_at = now + timedelta(seconds=max(60, settings.ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS))
        for _ in range(20):
            pairing_code = generate_pairing_code()
            pairing = BrowserAgentPairing(
                user_id=user.id,
                pairing_code_hash=hash_pairing_code(pairing_code),
                expires_at=expires_at,
                created_at=now,
            )
            self.db.add(pairing)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                continue
            self.db.refresh(pairing)
            return pairing, pairing_code
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="浏览器插件配对码生成失败")

    def claim_pairing(
        self,
        *,
        pairing_code: str,
        agent_id: str,
        name: str | None = None,
        extension_version: str | None = None,
        capabilities: dict[str, Any] | None = None,
        user_agent: str | None = None,
    ) -> tuple[BrowserAgent, IssuedAgentToken]:
        code_hash = hash_pairing_code(pairing_code)
        now = utcnow()
        pairing = (
            self.db.query(BrowserAgentPairing)
            .filter(
                BrowserAgentPairing.pairing_code_hash == code_hash,
                BrowserAgentPairing.claimed_at.is_(None),
                BrowserAgentPairing.expires_at > now,
            )
            .first()
        )
        if not pairing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="配对码无效或已过期")

        existing_agent = self.db.query(BrowserAgent).filter(BrowserAgent.agent_id == agent_id).first()
        if existing_agent and existing_agent.user_id != pairing.user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该浏览器插件已绑定其他用户")

        issued_token = issue_agent_token()
        capabilities_json = json.dumps(capabilities or {}, ensure_ascii=False, sort_keys=True)
        agent = existing_agent or BrowserAgent(user_id=pairing.user_id, agent_id=agent_id)
        agent.name = (name or "").strip() or agent.name
        agent.token_hash = issued_token.token_hash
        agent.status = BROWSER_AGENT_STATUS_ONLINE
        agent.last_seen_at = now
        agent.updated_at = now
        agent.revoked_at = None
        agent.capabilities_json = capabilities_json
        agent.user_agent = user_agent
        agent.extension_version = extension_version
        if existing_agent is None:
            agent.created_at = now
            self.db.add(agent)

        pairing.claimed_at = now
        pairing.claimed_by_agent_id = agent_id
        self.db.commit()
        self.db.refresh(agent)
        return agent, issued_token

    def authenticate_agent(self, agent_token: str | None) -> BrowserAgent:
        if not agent_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少浏览器插件令牌")
        token_hash = hash_agent_token(agent_token)
        agent = self.db.query(BrowserAgent).filter(BrowserAgent.token_hash == token_hash).first()
        if not agent or agent.revoked_at is not None or agent.status == BROWSER_AGENT_STATUS_REVOKED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="浏览器插件令牌无效或已撤销")
        return agent

    def heartbeat(
        self,
        *,
        agent: BrowserAgent,
        agent_id: str,
        reported_status: str = BROWSER_AGENT_STATUS_ONLINE,
        metadata: dict[str, Any] | None = None,
    ) -> BrowserAgent:
        if agent.agent_id != agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="浏览器插件身份不匹配")
        if agent.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="浏览器插件已撤销")
        now = utcnow()
        agent.last_seen_at = now
        agent.updated_at = now
        agent.status = BROWSER_AGENT_STATUS_ONLINE if reported_status != BROWSER_AGENT_STATUS_OFFLINE else BROWSER_AGENT_STATUS_OFFLINE
        if isinstance(metadata, dict) and metadata.get("zhuque") is not None:
            capabilities = _load_agent_capabilities(agent)
            runtime = capabilities.get("_runtime") if isinstance(capabilities.get("_runtime"), dict) else {}
            runtime["zhuque"] = sanitize_zhuque_runtime_status(metadata.get("zhuque"), updated_at=now.isoformat())
            runtime["updated_at"] = now.isoformat()
            capabilities["_runtime"] = runtime
            agent.capabilities_json = json.dumps(capabilities, ensure_ascii=False, sort_keys=True)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def list_agent_status(self, user: User) -> dict[str, Any]:
        agents = (
            self.db.query(BrowserAgent)
            .filter(BrowserAgent.user_id == user.id)
            .order_by(BrowserAgent.last_seen_at.desc().nullslast(), BrowserAgent.created_at.desc())
            .all()
        )
        now = utcnow()
        timeout = max(5, settings.ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT)
        items = []
        online = False
        current_zhuque_status: dict[str, Any] = {}
        for agent in agents:
            is_revoked = agent.revoked_at is not None or agent.status == BROWSER_AGENT_STATUS_REVOKED
            is_online = bool(
                not is_revoked
                and agent.last_seen_at
                and (now - agent.last_seen_at).total_seconds() <= timeout
            )
            zhuque_status = zhuque_runtime_status_from_agent(agent)
            if is_online:
                online = True
                if not current_zhuque_status and zhuque_status:
                    current_zhuque_status = zhuque_status
            display_status = BROWSER_AGENT_STATUS_REVOKED if is_revoked else (BROWSER_AGENT_STATUS_ONLINE if is_online else BROWSER_AGENT_STATUS_OFFLINE)
            items.append(
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "status": display_status,
                    "online": is_online,
                    "last_seen_at": agent.last_seen_at,
                    "extension_version": agent.extension_version,
                    "revoked_at": agent.revoked_at,
                    "zhuque_status": zhuque_status,
                }
            )
        transport = (settings.ZHUQUE_DETECT_TRANSPORT or "auto").strip().lower()
        required = transport == "browser_agent"
        zhuque_logged_in = bool(current_zhuque_status.get("logged_in"))
        zhuque_anonymous_ready = bool(
            current_zhuque_status.get("page_found")
            and current_zhuque_status.get("button_enabled")
        )
        if online and zhuque_logged_in:
            user_name = current_zhuque_status.get("user_name") or "朱雀账号"
            message = f"本机浏览器插件在线，朱雀已登录：{user_name}"
        elif online and zhuque_anonymous_ready:
            message = "本机浏览器插件在线，朱雀游客检测可用；也可登录账号使用账号次数"
        elif online:
            message = "本机浏览器插件在线；请打开朱雀页面，游客检测不可用时再登录账号"
        elif items:
            message = "本机浏览器插件离线，请打开 Chrome 并保持插件在线"
        else:
            message = "本机浏览器插件未连接"
        return {
            "required": required,
            "transport": transport,
            "online": online,
            "agents": items,
            "message": message,
            "zhuque": current_zhuque_status,
        }

    def create_zhuque_job(
        self,
        *,
        user_id: int,
        text: str,
        session_id: int | None = None,
        segment_id: int | None = None,
        timeout_seconds: int | None = None,
    ) -> ZhuqueAgentJob:
        now = utcnow()
        timeout = timeout_seconds or settings.ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT
        job = ZhuqueAgentJob(
            job_id="zaj_" + uuid.uuid4().hex,
            user_id=user_id,
            session_id=session_id,
            segment_id=segment_id,
            status=ZHUQUE_AGENT_JOB_STATUS_PENDING,
            payload_text=text,
            payload_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            created_at=now,
            expires_at=now + timedelta(seconds=max(30, timeout)),
            attempt_count=0,
        )
        self.db.add(job)
        if session_id is not None:
            session = self.db.get(OptimizationSession, session_id)
            if session and session.status == "processing":
                session.status = "waiting_browser_agent"
                session.worker_id = None
                session.updated_at = now
                session.error_message = "等待本机朱雀插件返回检测结果"
        self.db.commit()
        self.db.refresh(job)
        return job

    @staticmethod
    def _resume_waiting_session(job: ZhuqueAgentJob, now) -> bool:
        session = job.session
        if not session or session.status != "waiting_browser_agent":
            return False
        session.status = "queued"
        session.queued_at = now
        session.started_at = None
        session.finished_at = None
        session.worker_id = None
        session.updated_at = now
        return True

    def expire_stale_jobs(self) -> int:
        now = utcnow()
        jobs = (
            self.db.query(ZhuqueAgentJob)
            .filter(
                ZhuqueAgentJob.status.notin_(ZHUQUE_AGENT_JOB_TERMINAL_STATUSES),
                ZhuqueAgentJob.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
            .all()
        )
        for job in jobs:
            job.status = ZHUQUE_AGENT_JOB_STATUS_EXPIRED
            job.error_code = job.error_code or "zhuque_browser_agent_job_expired"
            job.error_message = job.error_message or "等待本机浏览器插件检测超时"
            job.completed_at = now
            self._resume_waiting_session(job, now)
        if jobs:
            self.db.commit()
        return len(jobs)

    def claim_next_zhuque_job(self, *, agent: BrowserAgent, agent_id: str) -> ZhuqueAgentJob | None:
        if agent.agent_id != agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="浏览器插件身份不匹配")
        if agent.revoked_at is not None or agent.status == BROWSER_AGENT_STATUS_REVOKED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="浏览器插件已撤销")
        now = utcnow()
        self.expire_stale_jobs()
        query = (
            self.db.query(ZhuqueAgentJob)
            .filter(
                ZhuqueAgentJob.user_id == agent.user_id,
                ZhuqueAgentJob.status == ZHUQUE_AGENT_JOB_STATUS_PENDING,
                ZhuqueAgentJob.expires_at > now,
            )
            .order_by(ZhuqueAgentJob.created_at.asc(), ZhuqueAgentJob.id.asc())
        )
        job = query.with_for_update(skip_locked=True).first()
        if not job:
            return None
        job.status = ZHUQUE_AGENT_JOB_STATUS_CLAIMED
        job.claimed_by_agent_id = agent.agent_id
        job.claimed_at = now
        job.heartbeat_at = now
        job.attempt_count = int(job.attempt_count or 0) + 1
        agent.last_seen_at = now
        agent.updated_at = now
        agent.status = BROWSER_AGENT_STATUS_ONLINE
        self.db.commit()
        self.db.refresh(job)
        return job

    def _get_owned_job(self, *, agent: BrowserAgent, job_id: str) -> ZhuqueAgentJob:
        job = (
            self.db.query(ZhuqueAgentJob)
            .filter(
                ZhuqueAgentJob.job_id == job_id,
                ZhuqueAgentJob.user_id == agent.user_id,
                ZhuqueAgentJob.claimed_by_agent_id == agent.agent_id,
            )
            .first()
        )
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="浏览器插件任务不存在")
        return job

    def update_zhuque_job_progress(
        self,
        *,
        agent: BrowserAgent,
        job_id: str,
        next_status: str,
        message: str = "",
        progress: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ZhuqueAgentJob:
        if next_status not in {ZHUQUE_AGENT_JOB_STATUS_RUNNING, ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的任务进度状态")
        job = self._get_owned_job(agent=agent, job_id=job_id)
        if job.status in ZHUQUE_AGENT_JOB_TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已结束，不能更新进度")
        now = utcnow()
        job.status = next_status
        job.started_at = job.started_at or now
        job.heartbeat_at = now
        job.progress_json = json.dumps(
            {"message": message, "progress": progress, "metadata": metadata or {}, "updated_at": now.isoformat()},
            ensure_ascii=False,
        )
        agent.last_seen_at = now
        agent.updated_at = now
        self.db.commit()
        self.db.refresh(job)
        return job

    def complete_zhuque_job(self, *, agent: BrowserAgent, job_id: str, result: dict[str, Any]) -> ZhuqueAgentJob:
        job = self._get_owned_job(agent=agent, job_id=job_id)
        if job.status in ZHUQUE_AGENT_JOB_TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已结束，不能重复完成")
        now = utcnow()
        job.status = ZHUQUE_AGENT_JOB_STATUS_COMPLETED
        job.result_json = json.dumps(result or {}, ensure_ascii=False)
        job.completed_at = now
        job.heartbeat_at = now
        agent.last_seen_at = now
        agent.updated_at = now
        self._resume_waiting_session(job, now)
        self.db.commit()
        self.db.refresh(job)
        return job

    def fail_zhuque_job(
        self,
        *,
        agent: BrowserAgent,
        job_id: str,
        error_code: str,
        message: str,
        retryable: bool = True,
    ) -> ZhuqueAgentJob:
        job = self._get_owned_job(agent=agent, job_id=job_id)
        if job.status in ZHUQUE_AGENT_JOB_TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已结束，不能重复失败")
        now = utcnow()
        job.status = ZHUQUE_AGENT_JOB_STATUS_FAILED
        job.error_code = error_code
        job.error_message = message
        job.progress_json = json.dumps({"retryable": retryable, "updated_at": now.isoformat()}, ensure_ascii=False)
        job.completed_at = now
        job.heartbeat_at = now
        agent.last_seen_at = now
        agent.updated_at = now
        self._resume_waiting_session(job, now)
        self.db.commit()
        self.db.refresh(job)
        return job

    def cancel_zhuque_jobs_for_session(self, *, session_id: int) -> int:
        now = utcnow()
        jobs = (
            self.db.query(ZhuqueAgentJob)
            .filter(
                ZhuqueAgentJob.session_id == session_id,
                ZhuqueAgentJob.status.notin_(ZHUQUE_AGENT_JOB_TERMINAL_STATUSES),
            )
            .all()
        )
        for job in jobs:
            job.status = ZHUQUE_AGENT_JOB_STATUS_CANCELLED
            job.error_code = job.error_code or "zhuque_browser_agent_job_cancelled"
            job.error_message = job.error_message or "任务已取消"
            job.completed_at = now
        if jobs:
            self.db.commit()
        return len(jobs)

    def revoke_agent(self, *, user: User, agent_id: str) -> None:
        agent = (
            self.db.query(BrowserAgent)
            .filter(BrowserAgent.user_id == user.id, BrowserAgent.agent_id == agent_id)
            .first()
        )
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="浏览器插件不存在")
        now = utcnow()
        agent.status = BROWSER_AGENT_STATUS_REVOKED
        agent.revoked_at = now
        agent.updated_at = now
        self.db.commit()


def bearer_token_from_authorization(authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1]
    return None
