import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import CreditTransaction, PaperProject, RegistrationInvite, User
from app.routes.auth import get_current_user_from_bearer
from app.schemas import (
    CreditBalanceResponse,
    CreditTransactionResponse,
    PaperProjectCreate,
    PaperProjectResponse,
    PaperProjectUpdate,
    ProviderConfigResponse,
    ProviderConfigUpdateRequest,
    RedeemCodeRequest,
    UserInviteResponse,
)
from app.services.credit_service import CreditService
from app.services.provider_config_service import ProviderConfigService

router = APIRouter(prefix="/user", tags=["user"])


def _generate_unique_invite_code(db: Session) -> str:
    for _ in range(10):
        code = secrets.token_urlsafe(18)
        existing_invite = db.query(RegistrationInvite).filter(RegistrationInvite.code == code).first()
        if not existing_invite:
            return code
    raise HTTPException(status_code=500, detail="邀请码生成失败，请重试")


@router.get("/invites/my", response_model=UserInviteResponse | None)
async def get_my_registration_invite(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> RegistrationInvite | None:
    return (
        db.query(RegistrationInvite)
        .filter(
            RegistrationInvite.created_by_user_id == current_user.id,
            RegistrationInvite.is_active.is_(True),
            RegistrationInvite.used_by_user_id.is_(None),
        )
        .order_by(RegistrationInvite.created_at.desc())
        .first()
    )


@router.post("/invites", response_model=UserInviteResponse)
async def create_my_registration_invite(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> RegistrationInvite:
    existing_invite = (
        db.query(RegistrationInvite)
        .filter(
            RegistrationInvite.created_by_user_id == current_user.id,
            RegistrationInvite.is_active.is_(True),
            RegistrationInvite.used_by_user_id.is_(None),
        )
        .order_by(RegistrationInvite.created_at.desc())
        .first()
    )
    if existing_invite:
        return existing_invite

    invite = RegistrationInvite(
        code=_generate_unique_invite_code(db),
        is_active=True,
        created_by_user_id=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/projects", response_model=List[PaperProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> List[PaperProject]:
    return (
        db.query(PaperProject)
        .filter(PaperProject.user_id == current_user.id, PaperProject.is_archived.is_(False))
        .order_by(PaperProject.updated_at.desc(), PaperProject.created_at.desc())
        .all()
    )


@router.post("/projects", response_model=PaperProjectResponse)
async def create_project(
    payload: PaperProjectCreate,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> PaperProject:
    project = PaperProject(
        user_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}", response_model=PaperProjectResponse)
async def update_project(
    project_id: int,
    payload: PaperProjectUpdate,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> PaperProject:
    project = (
        db.query(PaperProject)
        .filter(PaperProject.id == project_id, PaperProject.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="论文项目不存在")

    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived

    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", response_model=PaperProjectResponse)
async def archive_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> PaperProject:
    project = (
        db.query(PaperProject)
        .filter(PaperProject.id == project_id, PaperProject.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="论文项目不存在")

    project.is_archived = True
    db.commit()
    db.refresh(project)
    return project


@router.post("/redeem-code", response_model=CreditBalanceResponse)
async def redeem_code(
    payload: RedeemCodeRequest,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> CreditBalanceResponse:
    CreditService(db).redeem_code(current_user, payload.code)
    db.commit()
    db.refresh(current_user)
    return CreditBalanceResponse(
        credit_balance=current_user.credit_balance or 0,
        is_unlimited=current_user.is_unlimited,
    )


@router.get("/credits", response_model=CreditBalanceResponse)
async def get_credits(current_user: User = Depends(get_current_user_from_bearer)) -> CreditBalanceResponse:
    return CreditBalanceResponse(
        credit_balance=current_user.credit_balance or 0,
        is_unlimited=current_user.is_unlimited,
    )


@router.get("/credit-transactions", response_model=List[CreditTransactionResponse])
async def list_credit_transactions(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> List[CreditTransaction]:
    return (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .all()
    )


@router.get("/provider-config", response_model=ProviderConfigResponse | None)
async def get_provider_config(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    return ProviderConfigService(db).get_masked_config(current_user)


@router.put("/provider-config", response_model=ProviderConfigResponse)
async def save_provider_config(
    payload: ProviderConfigUpdateRequest,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
) -> ProviderConfigResponse:
    service = ProviderConfigService(db)
    service.save_config(current_user, payload)
    db.commit()
    return service.get_masked_config(current_user)


@router.post("/provider-config/test")
async def test_provider_config(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    ProviderConfigService(db).get_runtime_config(current_user)
    return {"valid": True}
