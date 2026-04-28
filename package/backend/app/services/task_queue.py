import inspect
from datetime import datetime
from typing import Awaitable, Callable

from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.models import OptimizationSession
from app.services.credit_service import CreditService
from app.services.optimization_service import MAX_ERROR_MESSAGE_LENGTH, OptimizationService
from app.services.provider_config_service import ProviderConfigService

TaskRunner = Callable[[Session, OptimizationSession], Awaitable[None] | None]


def _truncate_error_message(error: Exception) -> str:
    message = str(error)
    if len(message) > MAX_ERROR_MESSAGE_LENGTH:
        return message[: MAX_ERROR_MESSAGE_LENGTH - 50] + "... [错误信息已截断]"
    return message


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

    now = datetime.utcnow()
    session.status = "processing"
    session.worker_id = worker_id
    session.started_at = now
    session.finished_at = None
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
            session.started_at = datetime.utcnow()
        session.status = "processing"
        db.commit()
        await _run_with_error_handling(db, session, runner or run_session)
        return True
    finally:
        db.close()


async def process_next_queued_session(worker_id: str, runner: TaskRunner | None = None) -> bool:
    db = SessionLocal()
    try:
        session = claim_next_queued_session(db, worker_id)
        if not session:
            return False
        await _run_with_error_handling(db, session, runner or run_session)
        return True
    finally:
        db.close()


async def _run_with_error_handling(db: Session, session: OptimizationSession, runner: TaskRunner) -> None:
    try:
        result = runner(db, session)
        if inspect.isawaitable(result):
            await result
        db.refresh(session)
        session.finished_at = session.finished_at or session.completed_at or datetime.utcnow()
        db.commit()
    except Exception as error:
        db.rollback()
        session = db.query(OptimizationSession).filter(OptimizationSession.id == session.id).one()
        session.status = "failed"
        session.error_message = _truncate_error_message(error)
        session.finished_at = datetime.utcnow()
        CreditService(db).refund_held_platform_credit(session)
        db.commit()
