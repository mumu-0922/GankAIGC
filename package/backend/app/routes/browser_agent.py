import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.routes.auth import get_current_user_from_bearer
from app.schemas import (
    BrowserAgentClaimRequest,
    BrowserAgentClaimResponse,
    BrowserAgentHeartbeatRequest,
    BrowserAgentHeartbeatResponse,
    BrowserAgentJobClaimRequest,
    BrowserAgentJobClaimResponse,
    BrowserAgentJobCompleteRequest,
    BrowserAgentJobFailRequest,
    BrowserAgentJobPayload,
    BrowserAgentJobProgressRequest,
    BrowserAgentOkResponse,
    BrowserAgentPairingResponse,
    BrowserAgentRevokeRequest,
    BrowserAgentStatusResponse,
)
from app.services.browser_agent_service import BrowserAgentService, bearer_token_from_authorization
from app.services.task_queue import process_session_by_id
from app.config import settings
from app.utils.time import utcnow

router = APIRouter(prefix="/browser-agent", tags=["browser-agent"])


@router.post("/pairings", response_model=BrowserAgentPairingResponse)
async def create_browser_agent_pairing(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    pairing, pairing_code = BrowserAgentService(db).create_pairing(current_user)
    return BrowserAgentPairingResponse(
        pairing_id=pairing.id,
        pairing_code=pairing_code,
        expires_at=pairing.expires_at,
    )


@router.get("/status", response_model=BrowserAgentStatusResponse)
async def get_browser_agent_status(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    return BrowserAgentService(db).list_agent_status(current_user)


@router.post("/revoke")
async def revoke_browser_agent(
    payload: BrowserAgentRevokeRequest,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    BrowserAgentService(db).revoke_agent(user=current_user, agent_id=payload.agent_id)
    return {"ok": True}


@router.post("/claim", response_model=BrowserAgentClaimResponse)
async def claim_browser_agent_pairing(
    payload: BrowserAgentClaimRequest,
    db: Session = Depends(get_db),
):
    agent, issued_token = BrowserAgentService(db).claim_pairing(
        pairing_code=payload.pairing_code,
        agent_id=payload.agent_id,
        name=payload.name,
        extension_version=payload.extension_version,
        capabilities=payload.capabilities,
        user_agent=payload.user_agent,
    )
    return BrowserAgentClaimResponse(
        agent_token=issued_token.token,
        agent_id=agent.agent_id,
        user_id=agent.user_id,
        heartbeat_interval_seconds=max(5, settings.ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT // 3),
        job_poll_seconds=max(1, settings.ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS),
    )


@router.post("/heartbeat", response_model=BrowserAgentHeartbeatResponse)
async def browser_agent_heartbeat(
    payload: BrowserAgentHeartbeatRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    service = BrowserAgentService(db)
    agent = service.authenticate_agent(bearer_token_from_authorization(authorization))
    service.heartbeat(agent=agent, agent_id=payload.agent_id, reported_status=payload.status, metadata=payload.metadata)
    return BrowserAgentHeartbeatResponse(ok=True, server_time=utcnow())


@router.post("/jobs/claim", response_model=BrowserAgentJobClaimResponse)
async def claim_browser_agent_job(
    payload: BrowserAgentJobClaimRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    service = BrowserAgentService(db)
    agent = service.authenticate_agent(bearer_token_from_authorization(authorization))
    wait_seconds = payload.wait_seconds
    if wait_seconds is None:
        wait_seconds = settings.ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS
    wait_seconds = max(0, min(wait_seconds, settings.ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS, 60))
    deadline = asyncio.get_running_loop().time() + wait_seconds
    job = None
    while True:
        job = service.claim_next_zhuque_job(agent=agent, agent_id=payload.agent_id)
        if job is not None or wait_seconds <= 0 or asyncio.get_running_loop().time() >= deadline:
            break
        await asyncio.sleep(0.5)
    if not job:
        return BrowserAgentJobClaimResponse(job=None)
    timeout_seconds = max(30, int((job.expires_at - utcnow()).total_seconds()))
    return BrowserAgentJobClaimResponse(
        job=BrowserAgentJobPayload(
            job_id=job.job_id,
            text=job.payload_text,
            timeout_seconds=timeout_seconds,
            session_id=job.session_id,
            segment_id=job.segment_id,
        )
    )


@router.post("/jobs/{job_id}/progress", response_model=BrowserAgentOkResponse)
async def update_browser_agent_job_progress(
    job_id: str,
    payload: BrowserAgentJobProgressRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    service = BrowserAgentService(db)
    agent = service.authenticate_agent(bearer_token_from_authorization(authorization))
    service.update_zhuque_job_progress(
        agent=agent,
        job_id=job_id,
        next_status=payload.status,
        message=payload.message,
        progress=payload.progress,
        metadata=payload.metadata,
    )
    return BrowserAgentOkResponse(ok=True)


@router.post("/jobs/{job_id}/complete", response_model=BrowserAgentOkResponse)
async def complete_browser_agent_job(
    job_id: str,
    payload: BrowserAgentJobCompleteRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    service = BrowserAgentService(db)
    agent = service.authenticate_agent(bearer_token_from_authorization(authorization))
    job = service.complete_zhuque_job(agent=agent, job_id=job_id, result=payload.result)
    if settings.INLINE_TASK_WORKER_ENABLED and job.session_id is not None:
        background_tasks.add_task(process_session_by_id, job.session_id)
    return BrowserAgentOkResponse(ok=True)


@router.post("/jobs/{job_id}/fail", response_model=BrowserAgentOkResponse)
async def fail_browser_agent_job(
    job_id: str,
    payload: BrowserAgentJobFailRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    service = BrowserAgentService(db)
    agent = service.authenticate_agent(bearer_token_from_authorization(authorization))
    job = service.fail_zhuque_job(
        agent=agent,
        job_id=job_id,
        error_code=payload.error_code,
        message=payload.message,
        retryable=payload.retryable,
    )
    if settings.INLINE_TASK_WORKER_ENABLED and job.session_id is not None:
        background_tasks.add_task(process_session_by_id, job.session_id)
    return BrowserAgentOkResponse(ok=True)
