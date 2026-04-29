import asyncio
import inspect
import contextlib
from datetime import timedelta
from typing import Awaitable, Callable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models.models import OptimizationSession
from app.services.credit_service import CreditService
from app.services.optimization_service import MAX_ERROR_MESSAGE_LENGTH, OptimizationService
from app.services.provider_config_service import ProviderConfigService
from app.utils.time import utcnow

TaskRunner = Callable[[Session, OptimizationSession], Awaitable[None] | None]


def _truncate_error_message(error: Exception) -> str:
    message = str(error)
    if len(message) > MAX_ERROR_MESSAGE_LENGTH:
        return message[: MAX_ERROR_MESSAGE_LENGTH - 50] + "... [错误信息已截断]"
    return message


def touch_session_heartbeat(session_id: int, worker_id: str) -> bool:
    """刷新正在处理任务的心跳时间。"""
    db = SessionLocal()
    try:
        session = (
            db.query(OptimizationSession)
            .filter(
                OptimizationSession.id == session_id,
                OptimizationSession.status == "processing",
            )
            .first()
        )
        if not session:
            return False

        session.worker_id = worker_id
        session.updated_at = utcnow()
        db.commit()
        return True
    finally:
        db.close()


async def _heartbeat_loop(session_id: int, worker_id: str, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        touch_session_heartbeat(session_id, worker_id)


def recover_stale_processing_sessions(
    db: Session,
    stale_after_seconds: int | None = None,
) -> int:
    """把长时间无心跳的 processing 任务重新放回队列。"""
    timeout = (
        settings.TASK_WORKER_STALE_TIMEOUT_SECONDS
        if stale_after_seconds is None
        else stale_after_seconds
    )
    if timeout <= 0:
        return 0

    now = utcnow()
    cutoff = now - timedelta(seconds=timeout)
    stale_sessions = (
        db.query(OptimizationSession)
        .filter(
            OptimizationSession.status == "processing",
            OptimizationSession.finished_at.is_(None),
            or_(
                OptimizationSession.updated_at < cutoff,
                and_(
                    OptimizationSession.updated_at.is_(None),
                    OptimizationSession.started_at < cutoff,
                ),
                and_(
                    OptimizationSession.updated_at.is_(None),
                    OptimizationSession.started_at.is_(None),
                    OptimizationSession.created_at < cutoff,
                ),
            ),
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    for session in stale_sessions:
        previous_worker_id = session.worker_id or "unknown"
        session.status = "queued"
        session.queued_at = now
        session.started_at = None
        session.finished_at = None
        session.worker_id = None
        session.error_message = (
            f"[自动恢复] worker 心跳超时，已重新排队。"
            f"上次 worker={previous_worker_id}"
        )
        session.updated_at = now

    if stale_sessions:
        db.commit()

    return len(stale_sessions)


def claim_next_queued_session(db: Session, worker_id: str) -> OptimizationSession | None:
    session = (
        db.query(OptimizationSession)
        .filter(OptimizationSession.status == "queued")
        .order_by(OptimizationSession.queued_at.asc().nullsfirst(), OptimizationSession.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not session:
        return None

    now = utcnow()
    session.status = "processing"
    session.worker_id = worker_id
    session.started_at = now
    session.finished_at = None
    session.updated_at = now
    db.commit()
    db.refresh(session)
    return session


def _runtime_provider_config(db: Session, session: OptimizationSession) -> dict:
    if session.billing_mode == "byok" and session.credential_source == "user_saved":
        return ProviderConfigService(db).get_runtime_config(session.user)
    return {}


async def run_session(db: Session, session: OptimizationSession) -> None:
    runtime_provider_config = _runtime_provider_config(db, session)
    service = OptimizationService(db, session, runtime_provider_config=runtime_provider_config)
    await service.start_optimization()


async def process_session_by_id(session_id: int, runner: TaskRunner | None = None) -> bool:
    db = SessionLocal()
    try:
        session = (
            db.query(OptimizationSession)
            .options(joinedload(OptimizationSession.user))
            .filter(OptimizationSession.id == session_id)
            .first()
        )
        if not session or session.status not in {"queued", "processing"}:
            return False

        if not session.started_at:
            session.started_at = utcnow()
        session.status = "processing"
        session.worker_id = session.worker_id or "inline-worker"
        session.updated_at = utcnow()
        db.commit()
        await _run_with_error_handling(db, session, runner or run_session)
        return True
    finally:
        db.close()


async def process_next_queued_session(worker_id: str, runner: TaskRunner | None = None) -> bool:
    db = SessionLocal()
    try:
        recover_stale_processing_sessions(db)
        session = claim_next_queued_session(db, worker_id)
        if not session:
            return False
        await _run_with_error_handling(db, session, runner or run_session)
        return True
    finally:
        db.close()


async def _run_with_error_handling(db: Session, session: OptimizationSession, runner: TaskRunner) -> None:
    session_db_id = session.id
    worker_id = session.worker_id or "inline-worker"
    heartbeat_task = None
    heartbeat_interval = settings.TASK_WORKER_HEARTBEAT_INTERVAL
    if heartbeat_interval > 0:
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(session_db_id, worker_id, heartbeat_interval)
        )

    try:
        result = runner(db, session)
        if inspect.isawaitable(result):
            await result
        db.refresh(session)
        session.finished_at = session.finished_at or session.completed_at or utcnow()
        db.commit()
    except Exception as error:
        db.rollback()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session_db_id).one()
        session.status = "failed"
        session.error_message = _truncate_error_message(error)
        session.finished_at = utcnow()
        session.updated_at = session.finished_at
        CreditService(db).refund_held_platform_credit(session)
        db.commit()
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task
