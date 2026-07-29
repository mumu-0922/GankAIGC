"""Zhuque detection transport executed by a user's paired local browser agent."""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from app.config import settings
from app.database import SessionLocal
from app.models.browser_agent_constants import (
    BROWSER_AGENT_STATUS_REVOKED,
    ZHUQUE_AGENT_JOB_STATUS_COMPLETED,
    ZHUQUE_AGENT_JOB_STATUS_FAILED,
    ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
    ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
    ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED,
)
from app.models.models import BrowserAgent, OptimizationSession, ZhuqueAgentJob
from app.services.browser_agent_service import BrowserAgentService, zhuque_runtime_status_from_agent
from app.services.task_control import TaskSuspended
from app.services.zhuque_api import normalize_zhuque_result
from app.utils.time import utcnow


class BrowserAgentUnavailable(RuntimeError):
    pass


class BrowserAgentJobFailed(RuntimeError):
    pass


class BrowserAgentZhuqueTransport:
    source = "browser_agent"

    def __init__(self, user_id: int):
        self.user_id = int(user_id)

    @staticmethod
    def enabled() -> bool:
        return (settings.ZHUQUE_DETECT_TRANSPORT or "auto").strip().lower() == "browser_agent"

    def _latest_online_agent(self, db) -> BrowserAgent | None:
        now = utcnow()
        timeout = max(5, settings.ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT)
        agents = (
            db.query(BrowserAgent)
            .filter(
                BrowserAgent.user_id == self.user_id,
                BrowserAgent.revoked_at.is_(None),
                BrowserAgent.status != BROWSER_AGENT_STATUS_REVOKED,
                BrowserAgent.last_seen_at.isnot(None),
            )
            .order_by(BrowserAgent.last_seen_at.desc(), BrowserAgent.id.desc())
            .all()
        )
        for agent in agents:
            if (now - agent.last_seen_at).total_seconds() <= timeout:
                return agent
        return None

    def status(self) -> dict[str, Any]:
        db = SessionLocal()
        try:
            agent = self._latest_online_agent(db)
            if not agent:
                return {
                    "ready": False,
                    "connected": False,
                    "auth_mode": "browser_agent",
                    "login_mode": "local_browser_agent",
                    "message": "请先连接本机 Chrome 插件，再使用朱雀 AI 检测。",
                    "remaining_uses": -1,
                    "button_enabled": False,
                }
            zhuque_status = zhuque_runtime_status_from_agent(agent)
            zhuque_logged_in = bool(zhuque_status.get("logged_in"))
            zhuque_anonymous_ready = bool(
                zhuque_status.get("page_found")
                and zhuque_status.get("button_enabled")
            )
            zhuque_user_name = str(zhuque_status.get("user_name") or "").strip()
            message = (
                f"本机浏览器插件在线，朱雀已登录：{zhuque_user_name or '朱雀账号'}。"
                if zhuque_logged_in
                else "本机浏览器插件在线，朱雀游客检测可用；也可登录账号使用账号次数。"
                if zhuque_anonymous_ready
                else "本机浏览器插件在线；请打开朱雀页面，游客检测不可用时再登录账号。"
            )
            return {
                "ready": True,
                "connected": True,
                "auth_mode": "browser_agent",
                "login_mode": "local_browser_agent",
                "message": message,
                "remaining_uses": int(zhuque_status.get("remaining_uses", -1)),
                "button_enabled": bool(zhuque_logged_in or zhuque_anonymous_ready),
                "has_token": zhuque_logged_in,
                "user_name": zhuque_user_name,
                "agent_id": agent.agent_id,
                "agent_name": agent.name or "本机浏览器插件",
                "zhuque_status": zhuque_status,
            }
        finally:
            db.close()

    @staticmethod
    def _normalize_completed_job(job: ZhuqueAgentJob, text: str) -> dict:
        payload = json.loads(job.result_json or "{}")
        if isinstance(payload, dict):
            raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else payload
            normalized = normalize_zhuque_result(raw_payload, text_length=len(text), source=BrowserAgentZhuqueTransport.source)
            if normalized.get("success"):
                return normalized
            return {
                **normalized,
                "success": False,
                "source": BrowserAgentZhuqueTransport.source,
                "message": normalized.get("message") or payload.get("message") or "本机浏览器返回了无效朱雀结果",
            }
        return {
            "success": False,
            "source": BrowserAgentZhuqueTransport.source,
            "message": "本机浏览器返回了无效朱雀结果",
        }

    @staticmethod
    def _raise_terminal_job_error(job: ZhuqueAgentJob) -> None:
        if job.status == ZHUQUE_AGENT_JOB_STATUS_FAILED:
            raise BrowserAgentJobFailed(job.error_message or "本机浏览器朱雀检测失败")
        if job.status == ZHUQUE_AGENT_JOB_STATUS_EXPIRED:
            raise TimeoutError(job.error_message or "等待本机浏览器朱雀检测超时")
        if job.status == ZHUQUE_AGENT_JOB_STATUS_CANCELLED:
            raise BrowserAgentJobFailed(job.error_message or "朱雀检测任务已取消")

    def _find_session_job(
        self,
        db,
        *,
        session_id: int,
        segment_id: int | None,
        payload_hash: str,
    ) -> ZhuqueAgentJob | None:
        query = db.query(ZhuqueAgentJob).filter(
            ZhuqueAgentJob.user_id == self.user_id,
            ZhuqueAgentJob.session_id == session_id,
            ZhuqueAgentJob.payload_hash == payload_hash,
        )
        if segment_id is None:
            query = query.filter(ZhuqueAgentJob.segment_id.is_(None))
        else:
            query = query.filter(ZhuqueAgentJob.segment_id == segment_id)
        return query.order_by(ZhuqueAgentJob.id.desc()).first()

    async def detect(self, text: str, *, timeout: float | None = None, session_id: int | None = None, segment_id: int | None = None) -> dict:
        payload_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        db = SessionLocal()
        try:
            job = None
            session = None
            if session_id is not None:
                session = db.get(OptimizationSession, session_id)
                job = self._find_session_job(
                    db,
                    session_id=session_id,
                    segment_id=segment_id,
                    payload_hash=payload_hash,
                )
            if job is not None:
                if job.status == ZHUQUE_AGENT_JOB_STATUS_COMPLETED:
                    return self._normalize_completed_job(job, text)
                terminal_from_previous_retry = bool(
                    job.status
                    in {
                        ZHUQUE_AGENT_JOB_STATUS_FAILED,
                        ZHUQUE_AGENT_JOB_STATUS_EXPIRED,
                        ZHUQUE_AGENT_JOB_STATUS_CANCELLED,
                    }
                    and job.completed_at is not None
                    and session is not None
                    and session.queued_at is not None
                    and session.queued_at > job.completed_at
                )
                if not terminal_from_previous_retry:
                    self._raise_terminal_job_error(job)
                    raise TaskSuspended(
                        "等待本机朱雀插件返回检测结果",
                        reason="browser_agent",
                        external_job_id=job.job_id,
                    )

            if not self._latest_online_agent(db):
                raise BrowserAgentUnavailable("请先连接本机 Chrome 插件，再使用朱雀 AI 检测。")
            job = BrowserAgentService(db).create_zhuque_job(
                user_id=self.user_id,
                text=text,
                session_id=session_id,
                segment_id=segment_id,
                timeout_seconds=int(timeout or settings.ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT),
            )
            job_id = job.job_id
        finally:
            db.close()

        # Durable optimization sessions release the worker immediately. The
        # browser-agent completion transaction requeues the session and the
        # resumed task consumes this exact job by payload hash.
        if session_id is not None:
            raise TaskSuspended(
                "等待本机朱雀插件返回检测结果",
                reason="browser_agent",
                external_job_id=job_id,
            )

        deadline = asyncio.get_running_loop().time() + float(timeout or settings.ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT)
        last_manual_message = ""
        while asyncio.get_running_loop().time() < deadline:
            db = SessionLocal()
            try:
                if session_id is not None:
                    session_status = (
                        db.query(OptimizationSession.status)
                        .filter(OptimizationSession.id == session_id)
                        .scalar()
                    )
                    if session_status == "stopped":
                        BrowserAgentService(db).cancel_zhuque_jobs_for_session(
                            session_id=session_id
                        )
                        raise BrowserAgentJobFailed("任务已取消")
                job = db.query(ZhuqueAgentJob).filter(ZhuqueAgentJob.job_id == job_id).first()
                if not job:
                    raise BrowserAgentJobFailed("本机浏览器检测任务丢失")
                if job.status == ZHUQUE_AGENT_JOB_STATUS_COMPLETED:
                    return self._normalize_completed_job(job, text)
                if job.status == ZHUQUE_AGENT_JOB_STATUS_MANUAL_REQUIRED:
                    with_payload = json.loads(job.progress_json or "{}") if job.progress_json else {}
                    last_manual_message = str(with_payload.get("message") or "请在本机朱雀页面完成验证")
                self._raise_terminal_job_error(job)
            finally:
                db.close()
            await asyncio.sleep(1.0)

        db = SessionLocal()
        try:
            BrowserAgentService(db).expire_stale_jobs()
        finally:
            db.close()
        if last_manual_message:
            raise TimeoutError(f"等待本机浏览器朱雀检测超时：{last_manual_message}")
        raise TimeoutError("等待本机浏览器朱雀检测超时")
