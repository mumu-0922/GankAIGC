import asyncio
import inspect
import contextlib
import logging
import math
import statistics
from datetime import timedelta
from typing import Awaitable, Callable

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.database import SessionLocal
from app.models.models import OptimizationSession, WorkerLease
from app.services.credit_service import CreditService
from app.services.error_messages import build_task_error_message
from app.services.optimization_service import MAX_ERROR_MESSAGE_LENGTH, OptimizationService
from app.services.provider_config_service import ProviderConfigService
from app.services.session_credentials import clear_transient_session_api_keys
from app.services.stream_manager import stream_manager
from app.services.task_control import TaskSuspended
from app.services.browser_agent_service import BrowserAgentService
from app.utils.time import utcnow

TaskRunner = Callable[[Session, OptimizationSession], Awaitable[None] | None]
ClaimCallback = Callable[[OptimizationSession], None]
logger = logging.getLogger(__name__)

ACTIVE_SESSION_STATUSES = ("processing", "waiting_browser_agent")
UNFINISHED_SESSION_STATUSES = ("queued", *ACTIVE_SESSION_STATUSES)
USER_SUBMISSION_LOCK_NAMESPACE = 0x47414E4B  # "GANK"
USER_CLAIM_LOCK_NAMESPACE = 0x51455545  # "QUEUE"


def _truncate_error_message(error: Exception) -> str:
    return build_task_error_message(error, max_length=MAX_ERROR_MESSAGE_LENGTH)


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


def _postgres_advisory_lock(
    db: Session,
    namespace: int,
    user_id: int,
    *,
    wait: bool,
) -> bool:
    """Acquire a transaction-scoped per-user lock without adding Redis.

    PostgreSQL is the only supported database, but returning True on another
    dialect keeps isolated unit doubles usable. The partial unique index still
    remains the final invariant in production.
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return True
    function = func.pg_advisory_xact_lock if wait else func.pg_try_advisory_xact_lock
    result = db.execute(select(function(namespace, int(user_id)))).scalar()
    return True if wait else bool(result)


def lock_user_submission(db: Session, user_id: int) -> None:
    _postgres_advisory_lock(
        db,
        USER_SUBMISSION_LOCK_NAMESPACE,
        user_id,
        wait=True,
    )


def count_unfinished_sessions_for_user(
    db: Session,
    user_id: int,
    *,
    exclude_session_id: int | None = None,
) -> int:
    query = db.query(func.count(OptimizationSession.id)).filter(
        OptimizationSession.user_id == user_id,
        OptimizationSession.status.in_(UNFINISHED_SESSION_STATUSES),
    )
    if exclude_session_id is not None:
        query = query.filter(OptimizationSession.id != exclude_session_id)
    return int(query.scalar() or 0)


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
        attempts = int(session.worker_attempt_count or 0)
        if attempts >= max(1, settings.TASK_WORKER_MAX_ATTEMPTS):
            session.status = "failed"
            session.finished_at = now
            session.error_message = (
                f"worker 心跳连续超时，达到最大尝试次数 {attempts}，任务已停止重试。"
                f"上次 worker={previous_worker_id}"
            )
            CreditService(db).refund_held_platform_credit(session)
            clear_transient_session_api_keys(session)
        else:
            session.status = "queued"
            session.queued_at = now
            session.started_at = None
            session.finished_at = None
            session.worker_id = None
            session.error_message = (
                f"[自动恢复] worker 心跳超时，已重新排队。"
                f"上次 worker={previous_worker_id}，尝试 {attempts}/"
                f"{max(1, settings.TASK_WORKER_MAX_ATTEMPTS)}"
            )
        session.updated_at = now

    if stale_sessions:
        db.commit()

    return len(stale_sessions)


def claim_next_queued_session(db: Session, worker_id: str) -> OptimizationSession | None:
    active_session = aliased(OptimizationSession)
    candidates = (
        db.query(OptimizationSession)
        .filter(
            OptimizationSession.status == "queued",
            ~exists().where(
                and_(
                    active_session.user_id == OptimizationSession.user_id,
                    active_session.status.in_(ACTIVE_SESSION_STATUSES),
                )
            ),
        )
        .order_by(
            OptimizationSession.queued_at.asc().nullsfirst(),
            OptimizationSession.created_at.asc(),
            OptimizationSession.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(100)
        .all()
    )

    session = None
    for candidate in candidates:
        if not _postgres_advisory_lock(
            db,
            USER_CLAIM_LOCK_NAMESPACE,
            candidate.user_id,
            wait=False,
        ):
            continue
        already_active = (
            db.query(OptimizationSession.id)
            .filter(
                OptimizationSession.user_id == candidate.user_id,
                OptimizationSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
            .first()
        )
        if already_active:
            continue
        session = candidate
        break

    if session is None:
        return None

    now = utcnow()
    session.status = "processing"
    session.worker_id = worker_id
    session.worker_attempt_count = int(session.worker_attempt_count or 0) + 1
    session.started_at = now
    session.finished_at = None
    session.updated_at = now
    db.commit()
    db.refresh(session)
    return session


def _recent_median_task_seconds(db: Session) -> int:
    samples = (
        db.query(OptimizationSession.started_at, OptimizationSession.completed_at)
        .filter(
            OptimizationSession.status == "completed",
            OptimizationSession.started_at.isnot(None),
            OptimizationSession.completed_at.isnot(None),
        )
        .order_by(OptimizationSession.completed_at.desc())
        .limit(50)
        .all()
    )
    durations = [
        max(1, int((completed_at - started_at).total_seconds()))
        for started_at, completed_at in samples
        if completed_at >= started_at
    ]
    return max(30, min(3600, int(statistics.median(durations)))) if durations else 300


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
        while True:
            session = (
                db.query(OptimizationSession)
                .filter(OptimizationSession.id == session_id)
                .first()
            )
            if not session or session.status != "queued":
                return False

            # Inline source/one-click requests can overlap just like Docker
            # slots. Keep a later task queued until this user's active task is
            # terminal instead of violating the partial unique index and
            # losing its one-shot BackgroundTask.
            _postgres_advisory_lock(
                db,
                USER_CLAIM_LOCK_NAMESPACE,
                session.user_id,
                wait=True,
            )
            session = (
                db.query(OptimizationSession)
                .filter(OptimizationSession.id == session_id)
                .with_for_update()
                .populate_existing()
                .first()
            )
            if not session or session.status != "queued":
                db.rollback()
                return False
            already_active = (
                db.query(OptimizationSession.id)
                .filter(
                    OptimizationSession.user_id == session.user_id,
                    OptimizationSession.id != session.id,
                    OptimizationSession.status.in_(ACTIVE_SESSION_STATUSES),
                )
                .first()
            )
            if already_active:
                db.rollback()
                await asyncio.sleep(max(0.05, float(settings.TASK_WORKER_POLL_INTERVAL or 0.05)))
                continue

            now = utcnow()
            session.started_at = now
            session.status = "processing"
            session.worker_id = "inline-worker"
            session.worker_attempt_count = int(session.worker_attempt_count or 0) + 1
            session.updated_at = now
            db.commit()
            break

        await _run_with_error_handling(db, session, runner or run_session)
        return True
    finally:
        db.close()


async def process_next_queued_session(
    worker_id: str,
    runner: TaskRunner | None = None,
    on_claimed: ClaimCallback | None = None,
) -> bool:
    db = SessionLocal()
    try:
        BrowserAgentService(db).expire_stale_jobs()
        recover_stale_processing_sessions(db)
        session = claim_next_queued_session(db, worker_id)
        if not session:
            return False
        if on_claimed:
            on_claimed(session)
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
        await _broadcast_status_safely(session, "processing")
        result = runner(db, session)
        if inspect.isawaitable(result):
            await result
        db.refresh(session)
        session.finished_at = session.finished_at or session.completed_at or utcnow()
        if session.status in {"completed", "failed", "stopped"}:
            clear_transient_session_api_keys(session)
        db.commit()
        await _broadcast_status_safely(session, session.status)
    except TaskSuspended as suspended:
        db.rollback()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session_db_id).one()
        if session.status == "stopped":
            session.finished_at = session.finished_at or utcnow()
            session.updated_at = session.finished_at
            clear_transient_session_api_keys(session)
            db.commit()
            await _broadcast_status_safely(session, "stopped")
            return
        if session.status == "processing":
            session.status = "waiting_browser_agent"
            session.worker_id = None
            session.updated_at = utcnow()
            session.error_message = str(suspended)
        db.commit()
        await _broadcast_status_safely(session, session.status)
    except Exception as error:
        db.rollback()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session_db_id).one()
        if session.status == "stopped":
            session.finished_at = session.finished_at or utcnow()
            session.updated_at = session.finished_at
            clear_transient_session_api_keys(session)
            db.commit()
            await _broadcast_status_safely(session, "stopped")
            return
        session.status = "failed"
        session.error_message = _truncate_error_message(error)
        session.finished_at = utcnow()
        session.updated_at = session.finished_at
        CreditService(db).refund_held_platform_credit(session)
        clear_transient_session_api_keys(session)
        db.commit()
        await _broadcast_status_safely(session, "failed")
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task


async def _broadcast_status_safely(session: OptimizationSession, status: str) -> None:
    try:
        await stream_manager.broadcast(
            session.session_id,
            {
                "type": "status",
                "status": status,
                "progress": float(session.progress or 0),
                "current_position": int(session.current_position or 0),
                "total_segments": int(session.total_segments or 0),
                "error_message": session.error_message if status == "failed" else None,
            },
        )
    except Exception as exc:
        logger.warning("Failed to persist task status event for %s: %s", session.session_id, exc)


def get_persistent_queue_status(
    db: Session,
    *,
    user_id: int,
    session_id: str | None = None,
) -> dict:
    """Read queue/capacity truth from PostgreSQL, not process-local memory."""
    current_users = (
        db.query(func.count(OptimizationSession.id))
        .filter(OptimizationSession.status == "processing")
        .scalar()
        or 0
    )
    queued_query = (
        db.query(OptimizationSession.id, OptimizationSession.session_id)
        .filter(OptimizationSession.status == "queued")
        .order_by(
            OptimizationSession.queued_at.asc().nullsfirst(),
            OptimizationSession.created_at.asc(),
            OptimizationSession.id.asc(),
        )
    )
    queued = queued_query.all()

    if settings.INLINE_TASK_WORKER_ENABLED:
        capacity = max(1, int(settings.MAX_CONCURRENT_USERS or 1))
    else:
        lease_cutoff = utcnow() - timedelta(
            seconds=max(1, settings.TASK_WORKER_LEASE_TIMEOUT_SECONDS)
        )
        capacity = (
            db.query(func.coalesce(func.sum(WorkerLease.capacity), 0))
            .filter(
                WorkerLease.last_seen_at >= lease_cutoff,
                WorkerLease.state.in_(("idle", "busy")),
            )
            .scalar()
            or 0
        )
        capacity = max(1, int(capacity), int(current_users))

    your_position = None
    if session_id:
        owned_session = (
            db.query(OptimizationSession.id)
            .filter(
                OptimizationSession.session_id == session_id,
                OptimizationSession.user_id == user_id,
                OptimizationSession.status == "queued",
            )
            .first()
        )
        if owned_session:
            for position, item in enumerate(queued, start=1):
                if item.id == owned_session.id:
                    your_position = position
                    break

    estimated_wait_time = None
    if your_position:
        estimated_wait_time = math.ceil(your_position / capacity) * _recent_median_task_seconds(db)

    return {
        "current_users": int(current_users),
        "max_users": capacity,
        "queue_length": len(queued),
        "your_position": your_position,
        "estimated_wait_time": estimated_wait_time,
    }
