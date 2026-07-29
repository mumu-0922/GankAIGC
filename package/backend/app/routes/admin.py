import os
import json
import secrets
import csv
from io import StringIO
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, status, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, func, case
from sqlalchemy.orm import Session, defer, joinedload

from app.config import (
    get_file_backed_settings,
    is_placeholder_admin_password,
    is_weak_admin_password,
    reload_settings,
    settings,
)
from app.database import get_db
from app.models.models import (
    AdminAuditLog,
    Announcement,
    ChangeLog,
    CreditCode,
    CreditTransaction,
    OptimizationSegment,
    OptimizationSession,
    RegistrationInvite,
    SessionHistory,
    SystemSetting,
    User,
    UserProviderConfig,
)
from app.runtime import refresh_cors_middleware
from app.schemas import (
    AdminCreditAdjustRequest,
    AnnouncementCreateRequest,
    AnnouncementResponse,
    AnnouncementUpdateRequest,
    CreditCodeBatchCreateRequest,
    CreditCodeCreateRequest,
    CreditCodeResponse,
    DatabaseUpdateRequest,
    InviteBatchCreateRequest,
    InviteCreateRequest,
    UserResponse,
    UserUsageUpdate,
)
from app.services.concurrency import concurrency_manager
from app.services.browser_agent_service import BrowserAgentService
from app.services.credit_service import CreditService, serialize_credit_transaction
from app.services.session_credentials import clear_transient_session_api_keys
from app.services import operations_service, update_service
from app.services.ai_service import normalize_api_format
from app.services.zhuque_api import ZhuqueAPI
from app.services.zhuque_service import zhuque_user_credentials_file
from app.utils.auth import (
    create_access_token,
    verify_token,
)
from app.utils.url_security import validate_model_base_url
from app.utils.time import to_china_naive, utcnow
from app.utils.avatar_upload import save_avatar_upload

router = APIRouter(prefix="/admin", tags=["admin"])


def _coerce_zhuque_remaining_uses(value: Any) -> int:
    try:
        remaining_uses = int(value)
    except (TypeError, ValueError):
        return -1
    return remaining_uses if remaining_uses >= 0 else -1


def _get_cached_zhuque_remaining_uses(user: User) -> int:
    """Return the latest cached Zhuque quota for a user without running a live probe."""
    try:
        status = ZhuqueAPI(credentials_file=zhuque_user_credentials_file(user.id)).credential_status()
    except Exception:
        return _coerce_zhuque_remaining_uses(user.zhuque_free_uses_remaining)

    return _coerce_zhuque_remaining_uses(status.get("remaining_uses"))


class AdminLogin(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class AdminProfileResponse(BaseModel):
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    role: str = "管理员"
    role_key: str = "admin"
    auth_method: str = "password"
    token_expire_minutes: int
    profile_source: str = "system_settings"
    updated_at: Optional[datetime] = None


class AdminProfileUpdateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=32)


class AdminPasswordUpdateRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ModelConnectionTestRequest(BaseModel):
    stage: str
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_format: Optional[str] = None


class ModelListRequest(BaseModel):
    stage: str = "polish"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_format: Optional[str] = None


def _session_user_identity(user: Optional[User]) -> Dict[str, Optional[str]]:
    if not user:
        return {
            "username": None,
            "nickname": None,
            "user_display_name": "未知用户",
        }

    return {
        "username": user.username,
        "nickname": user.nickname,
        "user_display_name": user.nickname or user.username or f"用户 #{user.id}",
    }


class UnlimitedToggleRequest(BaseModel):
    is_unlimited: bool


class InviteResponse(BaseModel):
    id: int
    code: str
    is_active: bool
    expires_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_by_nickname: Optional[str] = None
    created_by_display_name: Optional[str] = None
    created_by_type: str = "admin"
    used_by_user_id: Optional[int] = None
    used_by_username: Optional[str] = None
    used_by_nickname: Optional[str] = None
    used_by_display_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


ALLOWED_TABLES: Dict[str, Type] = {
    "users": User,
    "optimization_sessions": OptimizationSession,
    "optimization_segments": OptimizationSegment,
    "session_history": SessionHistory,
    "change_logs": ChangeLog,
    "system_settings": SystemSetting,
}

DATABASE_MANAGER_MAX_PAGE_SIZE = 100
DATABASE_MANAGER_MAX_TEXT_LENGTH = 240

SENSITIVE_DB_FIELDS = {
    "access_link",
    "password_hash",
    "api_key",
    "api_key_encrypted",
    "polish_api_key",
    "enhance_api_key",
    "emotion_api_key",
    "compression_api_key",
    "original_text",
    "polished_text",
    "enhanced_text",
    "before_text",
    "after_text",
    "changes_detail",
    "history_data",
    "error_message",
    "spec_json",
}
SENSITIVE_SYSTEM_SETTING_MARKERS = (
    "api_key",
    "password",
    "secret",
    "token",
    "encryption_key",
)

MODEL_API_KEY_FIELDS = {
    "POLISH_API_KEY",
    "ENHANCE_API_KEY",
    "EMOTION_API_KEY",
    "COMPRESSION_API_KEY",
}

SECRET_CONFIG_FIELDS = MODEL_API_KEY_FIELDS | {"MINERU_API_TOKEN"}
PDF_STRUCTURE_ENGINE_OPTIONS = {"mineru", "markitdown"}
TASK_CONCURRENCY_OPTIONS = {5, 8, 10}
API_KEY_CONCURRENCY_OPTIONS = {1, 2, 4}

MODEL_BASE_URL_FIELDS = {
    "OPENAI_BASE_URL",
    "POLISH_BASE_URL",
    "ENHANCE_BASE_URL",
    "EMOTION_BASE_URL",
    "COMPRESSION_BASE_URL",
}

ADMIN_DISPLAY_NAME_SETTING_KEY = "ADMIN_DISPLAY_NAME"
ADMIN_AVATAR_URL_SETTING_KEY = "ADMIN_AVATAR_URL"


def _get_system_setting(db: Session, key: str) -> Optional[SystemSetting]:
    return db.query(SystemSetting).filter(SystemSetting.key == key).first()


def _upsert_system_setting(db: Session, key: str, value: str) -> SystemSetting:
    setting = _get_system_setting(db, key)
    if setting:
        setting.value = value
        setting.updated_at = utcnow()
        return setting

    setting = SystemSetting(key=key, value=value)
    db.add(setting)
    return setting


def _get_admin_display_setting(db: Session) -> tuple[str, Optional[datetime]]:
    setting = _get_system_setting(db, ADMIN_DISPLAY_NAME_SETTING_KEY)
    display_name = (setting.value or "").strip() if setting else ""
    return display_name or settings.ADMIN_USERNAME, setting.updated_at if setting else None


def _get_admin_avatar_setting(db: Session) -> tuple[Optional[str], Optional[datetime]]:
    setting = _get_system_setting(db, ADMIN_AVATAR_URL_SETTING_KEY)
    avatar_url = (setting.value or "").strip() if setting else ""
    return avatar_url or None, setting.updated_at if setting else None


def _latest_profile_update_time(*values: Optional[datetime]) -> Optional[datetime]:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _serialize_admin_profile(db: Session, admin_username: str) -> AdminProfileResponse:
    display_name, display_updated_at = _get_admin_display_setting(db)
    avatar_url, avatar_updated_at = _get_admin_avatar_setting(db)
    return AdminProfileResponse(
        username=admin_username,
        display_name=display_name,
        avatar_url=avatar_url,
        token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        updated_at=_latest_profile_update_time(display_updated_at, avatar_updated_at),
    )


def verify_admin_credentials(username: str, password: str) -> bool:
    return username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD


def verify_admin_token(token: str) -> bool:
    payload = verify_token(token)
    if not payload:
        return False
    return payload.get("sub") == settings.ADMIN_USERNAME and payload.get("role") == "admin"


def get_admin_from_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证令牌")

    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload or payload.get("sub") != settings.ADMIN_USERNAME or payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    return str(payload.get("sub"))


def write_admin_audit_log(
    db: Session,
    admin_username: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> AdminAuditLog:
    from app.utils.client_ip import get_current_client_ip

    client_ip = get_current_client_ip()
    audit_detail = dict(detail or {})
    if client_ip:
        audit_detail["ip_address"] = client_ip
    log = AdminAuditLog(
        admin_username=admin_username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=json.dumps(audit_detail, ensure_ascii=False) if audit_detail else None,
    )
    db.add(log)
    return log


def serialize_admin_audit_log(log: AdminAuditLog) -> Dict[str, Any]:
    detail: Any = log.detail
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except json.JSONDecodeError:
            pass
    return {
        "id": log.id,
        "admin_username": log.admin_username,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": detail,
        "created_at": log.created_at,
    }


def _api_key_summary(value: str | None) -> Dict[str, Any]:
    api_key = (value or "").strip()
    return {
        "api_key_set": bool(api_key),
        "api_key_last4": api_key[-4:] if api_key else "",
    }


def _validate_document_parse_updates(updates: Dict[str, str]) -> Dict[str, str]:
    sanitized = dict(updates)
    if "PDF_STRUCTURE_ENGINE" in sanitized:
        engine = str(sanitized["PDF_STRUCTURE_ENGINE"] or "").strip().lower()
        if engine not in PDF_STRUCTURE_ENGINE_OPTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF 解析引擎仅支持 mineru 或 markitdown",
            )
        sanitized["PDF_STRUCTURE_ENGINE"] = engine
    return sanitized


def _validate_concurrency_updates(updates: Dict[str, str]) -> Dict[str, str]:
    sanitized = dict(updates)
    option_sets = {
        "MAX_CONCURRENT_USERS": TASK_CONCURRENCY_OPTIONS,
        "API_KEY_CONCURRENCY": API_KEY_CONCURRENCY_OPTIONS,
    }
    for key, allowed in option_sets.items():
        if key not in sanitized:
            continue
        try:
            value = int(str(sanitized[key]).strip())
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{key} 必须是整数") from exc
        if value not in allowed:
            choices = " / ".join(str(item) for item in sorted(allowed))
            raise HTTPException(status_code=400, detail=f"{key} 仅支持 {choices}")
        sanitized[key] = str(value)
    return sanitized


def _validate_model_base_url_updates(updates: Dict[str, str]) -> Dict[str, str]:
    sanitized = dict(updates)
    allow_local_model_proxy = settings.ALLOW_LOCAL_MODEL_PROXY
    if "ALLOW_LOCAL_MODEL_PROXY" in sanitized:
        allow_local_model_proxy = str(sanitized["ALLOW_LOCAL_MODEL_PROXY"]).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    server_host = str(sanitized.get("SERVER_HOST", settings.SERVER_HOST)).strip()

    for key in MODEL_BASE_URL_FIELDS.intersection(sanitized):
        value = str(sanitized[key] or "").strip()
        if not value:
            sanitized[key] = ""
            continue
        try:
            sanitized[key] = validate_model_base_url(
                value,
                allow_local_model_proxy=allow_local_model_proxy,
                server_host=server_host,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return sanitized


def _persist_runtime_env_updates(updates: Dict[str, str]) -> None:
    """Persist known runtime settings into .env and hot-reload the settings object."""
    from app.config import get_env_file_path

    file_backed_updates = sorted(set(updates).intersection(get_file_backed_settings()))
    if file_backed_updates:
        raise ValueError(
            "以下配置由只读 *_FILE Secret 管理，不能从后台修改: "
            + ", ".join(file_backed_updates)
            + "。请更新对应 /run/secrets 文件并重建 app/worker 容器。"
        )

    normalized_updates: Dict[str, str] = {}
    for key, value in updates.items():
        value_text = str(value)
        if "\n" in value_text or "\r" in value_text:
            raise ValueError(f"{key} 不能包含换行符")
        normalized_updates[key] = value_text
    updates = normalized_updates

    env_path = get_env_file_path()
    env_existed = os.path.exists(env_path)
    if env_existed:
        with open(env_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    else:
        lines = []

    updated_keys = set()
    new_lines: List[str] = []
    for line in lines:
        stripped = line.rstrip("\n")
        if "=" in stripped and not stripped.strip().startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    original_content = "".join(lines)
    new_content = "".join(new_lines)

    try:
        env_dir = os.path.dirname(env_path)
        if env_dir:
            os.makedirs(env_dir, exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write(new_content)
        reload_settings(updates)
    except Exception:
        if env_existed:
            with open(env_path, "w", encoding="utf-8") as handle:
                handle.write(original_content)
        elif os.path.exists(env_path):
            os.remove(env_path)
        raise


def _user_display_name(user: Optional[User], fallback_id: Optional[int] = None) -> Optional[str]:
    if user:
        return user.nickname or user.username or f"用户 #{user.id}"
    if fallback_id is not None:
        return f"用户 #{fallback_id}"
    return None


def serialize_registration_invite(invite: RegistrationInvite) -> Dict[str, Any]:
    creator = invite.created_by_user
    used_by = invite.used_by_user
    return {
        "id": invite.id,
        "code": invite.code,
        "is_active": invite.is_active,
        "expires_at": invite.expires_at,
        "created_by_user_id": invite.created_by_user_id,
        "created_by_username": creator.username if creator else None,
        "created_by_nickname": creator.nickname if creator else None,
        "created_by_display_name": _user_display_name(creator, invite.created_by_user_id),
        "created_by_type": "user" if invite.created_by_user_id else "admin",
        "used_by_user_id": invite.used_by_user_id,
        "used_by_username": used_by.username if used_by else None,
        "used_by_nickname": used_by.nickname if used_by else None,
        "used_by_display_name": _user_display_name(used_by, invite.used_by_user_id),
        "created_at": invite.created_at,
    }


def _generate_unique_credit_code(db: Session, reserved_codes: Optional[set[str]] = None) -> str:
    reserved_codes = reserved_codes or set()
    for _ in range(20):
        code = secrets.token_urlsafe(18)
        if code in reserved_codes:
            continue
        existing_code = db.query(CreditCode).filter(CreditCode.code == code).first()
        if not existing_code:
            return code
    raise HTTPException(status_code=500, detail="兑换码生成失败，请重试")


def _generate_unique_invite_code(db: Session, reserved_codes: Optional[set[str]] = None) -> str:
    reserved_codes = reserved_codes or set()
    for _ in range(20):
        code = secrets.token_urlsafe(18)
        if code in reserved_codes:
            continue
        existing_invite = db.query(RegistrationInvite).filter(RegistrationInvite.code == code).first()
        if not existing_invite:
            return code
    raise HTTPException(status_code=500, detail="邀请码生成失败，请重试")


def _model_to_dict(record: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    mapper = inspect(record).mapper
    for column in mapper.columns:
        data[column.key] = getattr(record, column.key)
    return data


def sanitize_db_record(record: Dict[str, Any]) -> Dict[str, Any]:
    setting_key = str(record.get("key", "")).lower()
    sanitized: Dict[str, Any] = {}

    for key, value in record.items():
        normalized_key = key.lower()
        if normalized_key in SENSITIVE_DB_FIELDS:
            continue
        if normalized_key == "value" and any(marker in setting_key for marker in SENSITIVE_SYSTEM_SETTING_MARKERS):
            continue
        if isinstance(value, str) and len(value) > DATABASE_MANAGER_MAX_TEXT_LENGTH:
            sanitized[key] = f"{value[:DATABASE_MANAGER_MAX_TEXT_LENGTH]}..."
            continue
        sanitized[key] = value

    return sanitized


def _is_sensitive_system_setting_key(key: str) -> bool:
    normalized_key = key.lower()
    return any(marker in normalized_key for marker in SENSITIVE_SYSTEM_SETTING_MARKERS)


def _ensure_database_manager_enabled() -> None:
    if not settings.ADMIN_DATABASE_MANAGER_ENABLED:
        raise HTTPException(status_code=404, detail="数据库管理器已关闭")


def _ensure_database_write_enabled() -> None:
    _ensure_database_manager_enabled()
    if not settings.ADMIN_DATABASE_WRITE_ENABLED:
        raise HTTPException(status_code=403, detail="数据库管理器当前为只读模式")


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(credentials: AdminLogin) -> AdminLoginResponse:
    # 速率限制: 每分钟最多5次登录尝试 (在 main.py 的 limiter 中配置)
    if not verify_admin_credentials(credentials.username, credentials.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": credentials.username, "role": "admin"},
        expires_delta=access_token_expires,
    )
    return AdminLoginResponse(access_token=access_token, username=credentials.username)


@router.post("/verify-token")
async def verify_admin_token_endpoint(authorization: Optional[str] = Header(None)) -> Dict[str, bool]:
    get_admin_from_token(authorization)
    return {"valid": True}


@router.get("/profile", response_model=AdminProfileResponse)
async def get_admin_profile(
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> AdminProfileResponse:
    return _serialize_admin_profile(db, admin_username)


@router.patch("/profile", response_model=AdminProfileResponse)
async def update_admin_profile(
    payload: AdminProfileUpdateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> AdminProfileResponse:
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="管理员昵称不能为空")

    _upsert_system_setting(db, ADMIN_DISPLAY_NAME_SETTING_KEY, display_name)
    write_admin_audit_log(
        db,
        admin_username,
        "update_admin_profile",
        target_type="admin_profile",
        detail={"updated_keys": ["display_name"]},
    )
    db.commit()
    return _serialize_admin_profile(db, admin_username)


@router.post("/profile/avatar", response_model=AdminProfileResponse)
async def upload_admin_profile_avatar(
    avatar: UploadFile = File(...),
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> AdminProfileResponse:
    avatar_url = await save_avatar_upload(avatar)
    _upsert_system_setting(db, ADMIN_AVATAR_URL_SETTING_KEY, avatar_url)
    write_admin_audit_log(
        db,
        admin_username,
        "update_admin_avatar",
        target_type="admin_profile",
        detail={"updated_keys": ["avatar_url"], "avatar_url": avatar_url},
    )
    db.commit()
    return _serialize_admin_profile(db, admin_username)


@router.post("/profile/password")
async def update_admin_password(
    payload: AdminPasswordUpdateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    if payload.current_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能和当前密码相同")
    if is_placeholder_admin_password(payload.new_password) or is_weak_admin_password(payload.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少 8 位，且不能使用默认弱密码")

    try:
        _persist_runtime_env_updates({"ADMIN_PASSWORD": payload.new_password})
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    write_admin_audit_log(
        db,
        admin_username,
        "update_admin_password",
        target_type="admin_profile",
        detail={"updated_keys": ["ADMIN_PASSWORD"]},
    )
    db.commit()
    return {"message": "管理员密码已更新，请用新密码重新登录"}


@router.get("/audit-logs")
async def list_admin_audit_logs(
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    logs = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_admin_audit_log(log) for log in logs]


@router.get("/update/status")
async def get_update_status(_: str = Depends(get_admin_from_token)) -> Dict[str, Any]:
    return await update_service.build_update_status()


@router.post("/update/run")
async def run_vps_update(
    _: str = Depends(get_admin_from_token),
) -> Dict[str, Any]:
    _, disabled_reason = update_service.can_run_vps_update()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=disabled_reason or "请 SSH 到 VPS 执行升级命令。",
    )


@router.get("/operations/status")
async def get_operations_status(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return await operations_service.get_operations_status(db)


@router.get("/operations/backups/{filename}/download")
async def download_backup_file(
    filename: str,
    _: str = Depends(get_admin_from_token),
) -> FileResponse:
    try:
        backup_file = operations_service.resolve_backup_file(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        backup_file,
        filename=backup_file.name,
        media_type="application/octet-stream",
    )


@router.post("/operations/model-test")
async def test_admin_model_connection(
    payload: ModelConnectionTestRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = await operations_service.test_model_connection(
        payload.stage,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        api_format=payload.api_format,
    )
    write_admin_audit_log(
        db,
        admin_username,
        "test_model_connection",
        target_type="system_config",
        detail={
            "stage": payload.stage,
            "ok": result.get("ok"),
            "model": result.get("model"),
            "base_url": result.get("base_url"),
            "api_format": result.get("api_format"),
            "message": result.get("message"),
        },
    )
    db.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return result


@router.post("/operations/model-list")
async def list_admin_provider_models(
    payload: ModelListRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = await operations_service.list_provider_models(
        payload.stage,
        base_url=payload.base_url,
        api_key=payload.api_key,
        api_format=payload.api_format,
    )
    write_admin_audit_log(
        db,
        admin_username,
        "list_provider_models",
        target_type="system_config",
        detail={
            "stage": payload.stage,
            "ok": result.get("ok"),
            "base_url": result.get("base_url"),
            "api_format": result.get("api_format"),
            "model_count": result.get("count"),
            "message": result.get("message"),
        },
    )
    db.commit()
    if not result.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return result



@router.post("/invites", response_model=InviteResponse)
async def create_registration_invite(
    payload: InviteCreateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    code = payload.code or _generate_unique_invite_code(db)
    existing_invite = db.query(RegistrationInvite).filter(RegistrationInvite.code == code).first()
    if existing_invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邀请码已存在")

    expires_at = to_china_naive(payload.expires_at)
    invite = RegistrationInvite(code=code, is_active=True, expires_at=expires_at)
    db.add(invite)
    db.flush()
    write_admin_audit_log(
        db,
        admin_username,
        "create_invite",
        target_type="registration_invite",
        target_id=invite.id,
        detail={"code": invite.code, "expires_at": invite.expires_at.isoformat() if invite.expires_at else None},
    )
    db.commit()
    invite = (
        db.query(RegistrationInvite)
        .options(joinedload(RegistrationInvite.created_by_user), joinedload(RegistrationInvite.used_by_user))
        .filter(RegistrationInvite.id == invite.id)
        .one()
    )
    return serialize_registration_invite(invite)


@router.post("/invites/batch", response_model=List[InviteResponse])
async def batch_create_registration_invites(
    payload: InviteBatchCreateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    reserved_codes: set[str] = set()
    invites: List[RegistrationInvite] = []
    expires_at = to_china_naive(payload.expires_at)
    for _ in range(payload.quantity):
        code = _generate_unique_invite_code(db, reserved_codes)
        reserved_codes.add(code)
        invite = RegistrationInvite(code=code, is_active=True, expires_at=expires_at)
        db.add(invite)
        invites.append(invite)

    db.flush()
    write_admin_audit_log(
        db,
        admin_username,
        "batch_create_invites",
        target_type="registration_invite",
        detail={
            "quantity": payload.quantity,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    db.commit()
    invite_ids = [invite.id for invite in invites]
    created_invites = (
        db.query(RegistrationInvite)
        .options(joinedload(RegistrationInvite.created_by_user), joinedload(RegistrationInvite.used_by_user))
        .filter(RegistrationInvite.id.in_(invite_ids))
        .order_by(RegistrationInvite.created_at.desc(), RegistrationInvite.id.desc())
        .all()
    )
    return [serialize_registration_invite(invite) for invite in created_invites]


@router.get("/invites/export")
async def export_registration_invites(
    export_format: str = Query("csv", alias="format", pattern="^(csv|txt)$"),
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Response:
    invites = (
        db.query(RegistrationInvite)
        .options(joinedload(RegistrationInvite.created_by_user), joinedload(RegistrationInvite.used_by_user))
        .order_by(RegistrationInvite.created_at.desc(), RegistrationInvite.id.desc())
        .all()
    )
    filename = f"gankaigc-registration-invites.{export_format}"

    if export_format == "txt":
        content = "\n".join(invite.code for invite in invites)
        if content:
            content += "\n"
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["code", "is_active", "created_by_type", "used_by_user_id", "created_at"])
    for invite in invites:
        writer.writerow(
            [
                invite.code,
                invite.is_active,
                "user" if invite.created_by_user_id else "admin",
                invite.used_by_user_id or "",
                invite.created_at.isoformat() if invite.created_at else "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/invites", response_model=List[InviteResponse])
async def list_registration_invites(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    invites = (
        db.query(RegistrationInvite)
        .options(joinedload(RegistrationInvite.created_by_user), joinedload(RegistrationInvite.used_by_user))
        .order_by(RegistrationInvite.created_at.desc())
        .all()
    )
    return [serialize_registration_invite(invite) for invite in invites]


@router.patch("/invites/{invite_id}/toggle", response_model=InviteResponse)
async def toggle_registration_invite(
    invite_id: int,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    invite = db.query(RegistrationInvite).filter(RegistrationInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请码不存在")

    invite.is_active = not invite.is_active
    write_admin_audit_log(
        db,
        admin_username,
        "toggle_invite",
        target_type="registration_invite",
        target_id=invite.id,
        detail={"is_active": invite.is_active},
    )
    db.commit()
    invite = (
        db.query(RegistrationInvite)
        .options(joinedload(RegistrationInvite.created_by_user), joinedload(RegistrationInvite.used_by_user))
        .filter(RegistrationInvite.id == invite_id)
        .one()
    )
    return serialize_registration_invite(invite)


@router.get("/announcements", response_model=List[AnnouncementResponse])
async def list_announcements(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[Announcement]:
    return (
        db.query(Announcement)
        .order_by(Announcement.created_at.desc(), Announcement.id.desc())
        .all()
    )


@router.post("/announcements", response_model=AnnouncementResponse)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = Announcement(
        title=payload.title.strip(),
        content=payload.content.strip(),
        category=payload.category,
        is_active=payload.is_active,
    )
    db.add(announcement)
    db.flush()
    write_admin_audit_log(
        db,
        admin_username,
        "create_announcement",
        target_type="announcement",
        target_id=announcement.id,
        detail={
            "title": announcement.title,
            "category": announcement.category,
            "is_active": announcement.is_active,
        },
    )
    db.commit()
    db.refresh(announcement)
    return announcement


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"] is not None:
        announcement.title = updates["title"].strip()
    if "content" in updates and updates["content"] is not None:
        announcement.content = updates["content"].strip()
    if "category" in updates and updates["category"] is not None:
        announcement.category = updates["category"]
    if "is_active" in updates and updates["is_active"] is not None:
        announcement.is_active = updates["is_active"]
    announcement.updated_at = utcnow()

    write_admin_audit_log(
        db,
        admin_username,
        "update_announcement",
        target_type="announcement",
        target_id=announcement.id,
        detail={"updated_keys": list(updates.keys())},
    )
    db.commit()
    db.refresh(announcement)
    return announcement


@router.delete("/announcements/{announcement_id}")
async def delete_announcement(
    announcement_id: int,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")

    write_admin_audit_log(
        db,
        admin_username,
        "delete_announcement",
        target_type="announcement",
        target_id=announcement.id,
        detail={"title": announcement.title, "category": announcement.category},
    )
    db.delete(announcement)
    db.commit()
    return {"message": "公告已删除"}


@router.post("/credit-codes/batch", response_model=List[CreditCodeResponse])
async def batch_create_credit_codes(
    payload: CreditCodeBatchCreateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[CreditCode]:
    reserved_codes: set[str] = set()
    credit_codes: List[CreditCode] = []
    expires_at = to_china_naive(payload.expires_at)
    for _ in range(payload.quantity):
        code = _generate_unique_credit_code(db, reserved_codes)
        reserved_codes.add(code)
        credit_code = CreditCode(
            code=code,
            credit_amount=payload.credit_amount,
            is_active=True,
            expires_at=expires_at,
        )
        db.add(credit_code)
        credit_codes.append(credit_code)

    db.flush()
    write_admin_audit_log(
        db,
        admin_username,
        "batch_create_credit_codes",
        target_type="credit_code",
        detail={
            "quantity": payload.quantity,
            "credit_amount": payload.credit_amount,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    db.commit()
    for credit_code in credit_codes:
        db.refresh(credit_code)
    return credit_codes


@router.get("/credit-codes/export")
async def export_credit_codes(
    export_format: str = Query("csv", alias="format", pattern="^(csv|txt)$"),
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Response:
    credit_codes = db.query(CreditCode).order_by(CreditCode.created_at.desc(), CreditCode.id.desc()).all()
    filename = f"gankaigc-credit-codes.{export_format}"

    if export_format == "txt":
        content = "\n".join(code.code for code in credit_codes)
        if content:
            content += "\n"
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["code", "credit_amount", "is_active", "redeemed_by_user_id", "created_at"])
    for code in credit_codes:
        writer.writerow(
            [
                code.code,
                code.credit_amount,
                code.is_active,
                code.redeemed_by_user_id or "",
                code.created_at.isoformat() if code.created_at else "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/credit-codes", response_model=CreditCodeResponse)
async def create_credit_code(
    payload: CreditCodeCreateRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> CreditCode:
    code = payload.code or _generate_unique_credit_code(db)
    existing_code = db.query(CreditCode).filter(CreditCode.code == code).first()
    if existing_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="兑换码已存在")

    expires_at = to_china_naive(payload.expires_at)
    credit_code = CreditCode(
        code=code,
        credit_amount=payload.credit_amount,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(credit_code)
    db.flush()
    write_admin_audit_log(
        db,
        admin_username,
        "create_credit_code",
        target_type="credit_code",
        target_id=credit_code.id,
        detail={
            "code": credit_code.code,
            "credit_amount": credit_code.credit_amount,
            "expires_at": credit_code.expires_at.isoformat() if credit_code.expires_at else None,
        },
    )
    db.commit()
    db.refresh(credit_code)
    return credit_code


@router.get("/credit-codes", response_model=List[CreditCodeResponse])
async def list_credit_codes(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[CreditCode]:
    return db.query(CreditCode).order_by(CreditCode.created_at.desc()).all()


@router.get("/credit-transactions")
async def list_credit_transactions(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None, ge=1),
) -> List[Dict[str, Any]]:
    query = (
        db.query(CreditTransaction)
        .options(
            joinedload(CreditTransaction.user),
            joinedload(CreditTransaction.related_session),
        )
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
    )
    if user_id is not None:
        query = query.filter(CreditTransaction.user_id == user_id)

    return [
        serialize_credit_transaction(transaction, include_user=True)
        for transaction in query.limit(limit).all()
    ]


@router.post("/users/{user_id}/credits")
async def add_user_credits(
    user_id: int,
    payload: AdminCreditAdjustRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    CreditService(db).add_credits(user, payload.amount, reason=payload.reason)
    write_admin_audit_log(
        db,
        admin_username,
        "add_user_credits",
        target_type="user",
        target_id=user.id,
        detail={"amount": payload.amount, "reason": payload.reason},
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "credit_balance": user.credit_balance or 0,
        "is_unlimited": user.is_unlimited,
    }


@router.patch("/users/{user_id}/unlimited")
async def set_user_unlimited(
    user_id: int,
    payload: UnlimitedToggleRequest,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.is_unlimited = payload.is_unlimited
    write_admin_audit_log(
        db,
        admin_username,
        "set_user_unlimited",
        target_type="user",
        target_id=user.id,
        detail={"is_unlimited": user.is_unlimited},
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "is_unlimited": user.is_unlimited,
        "credit_balance": user.credit_balance or 0,
    }


@router.get("/provider-configs")
async def list_provider_config_summaries(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = (
        db.query(UserProviderConfig, User)
        .join(User, UserProviderConfig.user_id == User.id)
        .order_by(UserProviderConfig.updated_at.desc())
        .all()
    )
    return [
        {
            "user_id": user.id,
            "username": user.username,
            "base_url": config.base_url,
            "api_format": normalize_api_format(config.api_format),
            "api_key_last4": config.api_key_last4,
            "polish_model": config.polish_model,
            "enhance_model": config.enhance_model,
            "emotion_model": config.emotion_model,
            "updated_at": config.updated_at,
        }
        for config, user in rows
    ]


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(_: str = Depends(get_admin_from_token), db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "access_link": user.access_link,
            "is_active": user.is_active,
            "is_unlimited": user.is_unlimited,
            "credit_balance": user.credit_balance,
            "created_at": user.created_at,
            "last_used": user.last_used,
            "last_login_at": user.last_login_at,
            "usage_limit": user.usage_limit,
            "usage_count": user.usage_count,
            "zhuque_free_uses_remaining": _get_cached_zhuque_remaining_uses(user),
            "zhuque_total_uses": user.zhuque_total_uses,
        }
        for user in users
    ]


@router.patch("/users/{user_id}/toggle")
async def toggle_user_status(
    user_id: int,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = not user.is_active
    write_admin_audit_log(
        db,
        admin_username,
        "unban_user" if user.is_active else "ban_user",
        target_type="user",
        target_id=user.id,
        detail={"is_active": user.is_active},
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "is_active": user.is_active,
        "message": f"用户已{'启用' if user.is_active else '禁用'}",
    }


@router.patch("/users/{user_id}/usage")
async def update_user_usage(
    user_id: int,
    payload: UserUsageUpdate,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.usage_limit = payload.usage_limit
    if payload.reset_usage_count:
        user.usage_count = 0
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "usage_limit": user.usage_limit,
        "usage_count": user.usage_count,
        "message": "使用限制已更新",
    }


@router.post("/sessions/{session_id}/stop")
async def admin_stop_session(
    session_id: str,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """管理员停止会话"""
    session = db.query(OptimizationSession).filter(
        OptimizationSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
        
    if session.status not in ["queued", "processing", "waiting_browser_agent"]:
        raise HTTPException(status_code=400, detail="只能停止排队中、处理中的或等待浏览器插件的会话")
        
    session.status = "stopped"
    session.error_message = "管理员手动停止"
    session.finished_at = utcnow()
    clear_transient_session_api_keys(session)
    db.commit()
    BrowserAgentService(db).cancel_zhuque_jobs_for_session(session_id=session.id)
    
    return {"message": "会话已停止"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"message": "用户已删除", "id": user_id}


ADMIN_STATISTICS_RANGE_LABELS = {
    "today": "今日数据",
    "7d": "最近 7 天",
    "30d": "近 30 天",
}

ADMIN_STATISTICS_PROCESSING_MODES = (
    ("paper_polish", "论文润色"),
    ("paper_enhance", "论文增强"),
    ("paper_polish_enhance", "润色 + 增强"),
    ("emotion_polish", "感情文章润色"),
    ("ai_detect_reduce", "AI检测+降重"),
)


def _percentage_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 2)


def _time_window_filter(query, column, start_at: datetime, end_at: datetime):
    return query.filter(column >= start_at, column < end_at)


def _get_statistics_window(range_key: str) -> Dict[str, Any]:
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range_key == "today":
        start_at = today_start
        previous_start_at = today_start - timedelta(days=1)
    elif range_key == "30d":
        start_at = today_start - timedelta(days=29)
        previous_start_at = start_at - timedelta(days=30)
    else:
        start_at = today_start - timedelta(days=6)
        previous_start_at = start_at - timedelta(days=7)

    end_at = now + timedelta(microseconds=1)
    previous_end_at = previous_start_at + (end_at - start_at)

    return {
        "key": range_key,
        "label": ADMIN_STATISTICS_RANGE_LABELS[range_key],
        "start_at": start_at,
        "end_at": end_at,
        "previous_start_at": previous_start_at,
        "previous_end_at": previous_end_at,
    }


def _serialize_statistics_window(window: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": window["key"],
        "label": window["label"],
        "start_at": window["start_at"].isoformat(),
        "end_at": window["end_at"].isoformat(),
        "previous_start_at": window["previous_start_at"].isoformat(),
        "previous_end_at": window["previous_end_at"].isoformat(),
    }


def _build_time_buckets(range_key: str, start_at: datetime, end_at: datetime) -> List[Dict[str, Any]]:
    buckets: List[Dict[str, Any]] = []
    if range_key == "today":
        cursor = start_at
        while cursor < end_at:
            next_at = min(cursor + timedelta(hours=1), end_at)
            buckets.append({
                "label": cursor.strftime("%H:%M"),
                "start_at": cursor,
                "end_at": next_at,
            })
            cursor = next_at
        return buckets or [{"label": start_at.strftime("%H:%M"), "start_at": start_at, "end_at": end_at}]

    day_count = 30 if range_key == "30d" else 7
    for offset in range(day_count):
        cursor = start_at + timedelta(days=offset)
        next_at = min(cursor + timedelta(days=1), end_at)
        buckets.append({
            "label": cursor.strftime("%m/%d"),
            "start_at": cursor,
            "end_at": next_at,
        })
    return buckets


def _bucket_index(timestamp: Optional[datetime], buckets: List[Dict[str, Any]]) -> Optional[int]:
    if not timestamp:
        return None
    for index, bucket in enumerate(buckets):
        if bucket["start_at"] <= timestamp < bucket["end_at"]:
            return index
    return None


def _series_from_bucket_values(buckets: List[Dict[str, Any]], values: List[float]) -> List[Dict[str, Any]]:
    return [
        {
            "label": bucket["label"],
            "start_at": bucket["start_at"].isoformat(),
            "end_at": bucket["end_at"].isoformat(),
            "value": round(values[index], 2),
        }
        for index, bucket in enumerate(buckets)
    ]


def _count_session_series(
    sessions: List[OptimizationSession],
    buckets: List[Dict[str, Any]],
    *,
    status: Optional[str] = None,
    processing_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    values = [0.0 for _ in buckets]
    for session in sessions:
        if status and session.status != status:
            continue
        if processing_mode and session.processing_mode != processing_mode:
            continue
        index = _bucket_index(session.created_at, buckets)
        if index is not None:
            values[index] += 1
    return _series_from_bucket_values(buckets, values)


def _sum_session_text_series(
    sessions: List[OptimizationSession],
    buckets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    values = [0.0 for _ in buckets]
    for session in sessions:
        if session.status != "completed":
            continue
        index = _bucket_index(session.created_at, buckets)
        if index is not None:
            values[index] += len(session.original_text or "")
    return _series_from_bucket_values(buckets, values)


def _average_session_value_series(
    sessions: List[OptimizationSession],
    buckets: List[Dict[str, Any]],
    value_getter,
) -> List[Dict[str, Any]]:
    totals = [0.0 for _ in buckets]
    counts = [0 for _ in buckets]
    for session in sessions:
        value = value_getter(session)
        if value is None:
            continue
        index = _bucket_index(session.created_at, buckets)
        if index is not None:
            totals[index] += float(value)
            counts[index] += 1
    values = [
        (totals[index] / counts[index]) if counts[index] else 0.0
        for index in range(len(buckets))
    ]
    return _series_from_bucket_values(buckets, values)


def _distinct_active_user_series(
    sessions: List[OptimizationSession],
    users: List[User],
    buckets: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    user_sets = [set() for _ in buckets]
    for session in sessions:
        if not session.user_id:
            continue
        index = _bucket_index(session.created_at, buckets)
        if index is not None:
            user_sets[index].add(session.user_id)
    for user in users:
        index = _bucket_index(user.last_used, buckets)
        if index is not None:
            user_sets[index].add(user.id)
    return _series_from_bucket_values(buckets, [len(user_ids) for user_ids in user_sets])


def _success_rate_series(sessions: List[OptimizationSession], buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    totals = [0 for _ in buckets]
    completed = [0 for _ in buckets]
    for session in sessions:
        index = _bucket_index(session.created_at, buckets)
        if index is None:
            continue
        totals[index] += 1
        if session.status == "completed":
            completed[index] += 1

    values = [
        (completed[index] / totals[index] * 100) if totals[index] else 0.0
        for index in range(len(buckets))
    ]
    return _series_from_bucket_values(buckets, values)


def _processing_seconds(session: OptimizationSession) -> Optional[float]:
    if session.status != "completed" or not session.completed_at or not session.created_at:
        return None
    return max((session.completed_at - session.created_at).total_seconds(), 0.0)


def _average_processing_seconds(sessions: List[OptimizationSession]) -> float:
    values = [
        value
        for session in sessions
        if (value := _processing_seconds(session)) is not None
    ]
    return round(sum(values) / len(values), 2) if values else 0.0


def _average_input_chars(sessions: List[OptimizationSession]) -> float:
    if not sessions:
        return 0.0
    return round(sum(len(session.original_text or "") for session in sessions) / len(sessions), 2)


@router.get("/statistics")
async def get_statistics(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
    range_key: str = Query("7d", alias="range", pattern="^(today|7d|30d)$"),
) -> Dict[str, Any]:
    window = _get_statistics_window(range_key)
    current_start = window["start_at"]
    current_end = window["end_at"]
    previous_start = window["previous_start_at"]
    previous_end = window["previous_end_at"]
    buckets = _build_time_buckets(range_key, current_start, current_end)

    total_users = db.query(User).count() or 0
    active_users = db.query(User).filter(User.is_active.is_(True)).count() or 0
    inactive_users = total_users - active_users
    used_users = db.query(User).filter(User.last_used.isnot(None)).count() or 0

    total_sessions = db.query(OptimizationSession).count() or 0
    completed_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "completed").count() or 0
    processing_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "processing").count() or 0
    queued_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "queued").count() or 0
    browser_waiting_sessions = db.query(OptimizationSession).filter(
        OptimizationSession.status == "waiting_browser_agent"
    ).count() or 0
    failed_sessions = db.query(OptimizationSession).filter(OptimizationSession.status == "failed").count() or 0

    total_segments = db.query(OptimizationSegment).count() or 0
    completed_segments = db.query(OptimizationSegment).filter(OptimizationSegment.status == "completed").count() or 0

    seven_days_ago = utcnow() - timedelta(days=7)
    recent_active_users = db.query(User).filter(User.last_used >= seven_days_ago).count() or 0

    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new_users = db.query(User).filter(User.created_at >= today_start).count() or 0
    today_active_users = db.query(User).filter(User.last_used >= today_start).count() or 0
    today_sessions = db.query(OptimizationSession).filter(OptimizationSession.created_at >= today_start).count() or 0

    current_sessions = (
        _time_window_filter(db.query(OptimizationSession), OptimizationSession.created_at, current_start, current_end)
        .all()
    )
    previous_sessions = (
        _time_window_filter(db.query(OptimizationSession), OptimizationSession.created_at, previous_start, previous_end)
        .all()
    )
    users_active_for_series = (
        _time_window_filter(db.query(User), User.last_used, current_start, current_end)
        .all()
    )

    current_session_count = len(current_sessions)
    previous_session_count = len(previous_sessions)
    current_completed_sessions = sum(1 for session in current_sessions if session.status == "completed")
    previous_completed_sessions = sum(1 for session in previous_sessions if session.status == "completed")
    current_processing_sessions = sum(1 for session in current_sessions if session.status == "processing")
    current_queued_sessions = sum(1 for session in current_sessions if session.status == "queued")
    current_browser_waiting_sessions = sum(
        1 for session in current_sessions if session.status == "waiting_browser_agent"
    )
    current_failed_sessions = sum(1 for session in current_sessions if session.status == "failed")
    previous_failed_sessions = sum(1 for session in previous_sessions if session.status == "failed")

    success_rate_in_range = round((current_completed_sessions / current_session_count) * 100, 2) if current_session_count else 0.0
    previous_success_rate = round((previous_completed_sessions / previous_session_count) * 100, 2) if previous_session_count else 0.0

    new_users_in_range = (
        _time_window_filter(db.query(User), User.created_at, current_start, current_end)
        .count()
        or 0
    )
    previous_new_users = (
        _time_window_filter(db.query(User), User.created_at, previous_start, previous_end)
        .count()
        or 0
    )
    active_users_in_range = (
        _time_window_filter(db.query(User), User.last_used, current_start, current_end)
        .count()
        or 0
    )
    previous_active_users = (
        _time_window_filter(db.query(User), User.last_used, previous_start, previous_end)
        .count()
        or 0
    )

    current_segment_query = (
        db.query(OptimizationSegment)
        .join(OptimizationSession, OptimizationSegment.session_id == OptimizationSession.id)
        .filter(OptimizationSession.created_at >= current_start, OptimizationSession.created_at < current_end)
    )
    previous_segment_query = (
        db.query(OptimizationSegment)
        .join(OptimizationSession, OptimizationSegment.session_id == OptimizationSession.id)
        .filter(OptimizationSession.created_at >= previous_start, OptimizationSession.created_at < previous_end)
    )
    total_segments_in_range = current_segment_query.count() or 0
    completed_segments_in_range = current_segment_query.filter(OptimizationSegment.status == "completed").count() or 0
    previous_segments_in_range = previous_segment_query.count() or 0

    total_original_chars = (
        db.query(func.coalesce(func.sum(func.length(OptimizationSession.original_text)), 0))
        .filter(OptimizationSession.status == "completed")
        .scalar()
        or 0
    )
    total_original_chars = int(total_original_chars)
    total_chars_processed_in_range = sum(
        len(session.original_text or "")
        for session in current_sessions
        if session.status == "completed"
    )
    previous_chars_processed = sum(
        len(session.original_text or "")
        for session in previous_sessions
        if session.status == "completed"
    )

    mode_total_counts = {
        mode: count
        for mode, count in db.query(
            OptimizationSession.processing_mode,
            func.count(OptimizationSession.id),
        ).group_by(OptimizationSession.processing_mode).all()
    }
    mode_current_completed_counts = {
        mode: sum(1 for session in current_sessions if session.processing_mode == mode and session.status == "completed")
        for mode, _label in ADMIN_STATISTICS_PROCESSING_MODES
    }
    mode_previous_completed_counts = {
        mode: sum(1 for session in previous_sessions if session.processing_mode == mode and session.status == "completed")
        for mode, _label in ADMIN_STATISTICS_PROCESSING_MODES
    }
    mode_total_in_range = sum(mode_current_completed_counts.values())

    mode_rows = []
    for mode, label in ADMIN_STATISTICS_PROCESSING_MODES:
        current_count = mode_current_completed_counts.get(mode, 0)
        previous_count = mode_previous_completed_counts.get(mode, 0)
        mode_rows.append({
            "id": mode,
            "label": label,
            "count": current_count,
            "total_count": int(mode_total_counts.get(mode, 0) or 0),
            "percent": round((current_count / mode_total_in_range) * 100, 2) if mode_total_in_range else 0.0,
            "trend_percent": _percentage_change(current_count, previous_count),
            "series": _count_session_series(
                current_sessions,
                buckets,
                status="completed",
                processing_mode=mode,
            ),
        })

    avg_processing_time_all = _average_processing_seconds(
        db.query(OptimizationSession).filter(
            OptimizationSession.status == "completed",
            OptimizationSession.completed_at.isnot(None),
            OptimizationSession.created_at.isnot(None),
        ).all()
    )
    avg_processing_time_in_range = _average_processing_seconds(current_sessions)
    previous_avg_processing_time = _average_processing_seconds(previous_sessions)
    avg_input_chars_in_range = _average_input_chars(current_sessions)
    previous_avg_input_chars = _average_input_chars(previous_sessions)

    statistics = {
        "range": _serialize_statistics_window(window),
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "used": used_users,
            "unused": total_users - used_users,
            "today_new": today_new_users,
            "today_active": today_active_users,
            "recent_active_7days": recent_active_users,
            "new_in_range": new_users_in_range,
            "active_in_range": active_users_in_range,
            "previous_new_in_range": previous_new_users,
            "previous_active_in_range": previous_active_users,
            "trend_percent": _percentage_change(active_users_in_range, previous_active_users),
            "new_trend_percent": _percentage_change(new_users_in_range, previous_new_users),
        },
        "sessions": {
            "total": total_sessions,
            "completed": completed_sessions,
            "processing": processing_sessions,
            "queued": queued_sessions,
            "waiting_browser_agent": browser_waiting_sessions,
            "failed": failed_sessions,
            "today": today_sessions,
            "in_range": current_session_count,
            "previous_in_range": previous_session_count,
            "completed_in_range": current_completed_sessions,
            "previous_completed_in_range": previous_completed_sessions,
            "processing_in_range": current_processing_sessions,
            "queued_in_range": current_queued_sessions,
            "waiting_browser_agent_in_range": current_browser_waiting_sessions,
            "failed_in_range": current_failed_sessions,
            "previous_failed_in_range": previous_failed_sessions,
            "success_rate": success_rate_in_range,
            "previous_success_rate": previous_success_rate,
            "trend_percent": _percentage_change(current_session_count, previous_session_count),
            "completed_trend_percent": _percentage_change(current_completed_sessions, previous_completed_sessions),
            "success_rate_trend_percent": _percentage_change(success_rate_in_range, previous_success_rate),
        },
        "requests": {
            "total": total_sessions,
            "in_range": current_session_count,
            "previous_in_range": previous_session_count,
            "trend_percent": _percentage_change(current_session_count, previous_session_count),
        },
        "segments": {
            "total": total_segments,
            "completed": completed_segments,
            "pending": total_segments - completed_segments,
            "in_range": total_segments_in_range,
            "completed_in_range": completed_segments_in_range,
            "pending_in_range": total_segments_in_range - completed_segments_in_range,
            "previous_in_range": previous_segments_in_range,
            "trend_percent": _percentage_change(total_segments_in_range, previous_segments_in_range),
        },
        "processing": {
            "total_chars_processed": total_original_chars,
            "total_chars_processed_in_range": total_chars_processed_in_range,
            "previous_chars_processed": previous_chars_processed,
            "chars_trend_percent": _percentage_change(total_chars_processed_in_range, previous_chars_processed),
            "avg_processing_time": avg_processing_time_all,
            "avg_processing_time_in_range": avg_processing_time_in_range,
            "previous_avg_processing_time": previous_avg_processing_time,
            "avg_processing_time_trend_percent": _percentage_change(avg_processing_time_in_range, previous_avg_processing_time),
            "avg_input_chars": avg_input_chars_in_range,
            "previous_avg_input_chars": previous_avg_input_chars,
            "avg_input_chars_trend_percent": _percentage_change(avg_input_chars_in_range, previous_avg_input_chars),
            "paper_polish_count": int(mode_total_counts.get("paper_polish", 0) or 0),
            "paper_enhance_count": int(mode_total_counts.get("paper_enhance", 0) or 0),
            "paper_polish_enhance_count": int(mode_total_counts.get("paper_polish_enhance", 0) or 0),
            "emotion_polish_count": int(mode_total_counts.get("emotion_polish", 0) or 0),
            "ai_detect_reduce_count": int(mode_total_counts.get("ai_detect_reduce", 0) or 0),
            "mode_total_in_range": mode_total_in_range,
            "mode_rows": mode_rows,
            "series": {
                "sessions": _count_session_series(current_sessions, buckets),
                "active_users": _distinct_active_user_series(current_sessions, users_active_for_series, buckets),
                "completed_sessions": _count_session_series(current_sessions, buckets, status="completed"),
                "success_rate": _success_rate_series(current_sessions, buckets),
                "chars_processed": _sum_session_text_series(current_sessions, buckets),
                "avg_processing_time": _average_session_value_series(current_sessions, buckets, _processing_seconds),
                "avg_input_chars": _average_session_value_series(
                    current_sessions,
                    buckets,
                    lambda session: len(session.original_text or ""),
                ),
            },
        },
    }

    if settings.WORD_FORMATTER_ENABLED:
        from app.word_formatter.services.job_manager import get_job_manager

        statistics["word_formatter"] = get_job_manager().get_stats()

    return statistics


@router.get("/users/{user_id}/details")
async def get_user_details(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user_sessions = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).all()
    total_sessions = len(user_sessions)
    completed_sessions = sum(1 for session in user_sessions if session.status == "completed")

    session_ids = [session.id for session in user_sessions]
    total_segments = 0
    completed_segments = 0
    if session_ids:
        total_segments = db.query(OptimizationSegment).filter(OptimizationSegment.session_id.in_(session_ids)).count()
        completed_segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id.in_(session_ids), OptimizationSegment.status == "completed")
            .count()
        )

    recent_sessions = (
        db.query(OptimizationSession)
        .filter(OptimizationSession.user_id == user_id)
        .order_by(OptimizationSession.created_at.desc())
        .limit(5)
        .all()
    )
    recent_credit_transactions = (
        db.query(CreditTransaction)
        .options(joinedload(CreditTransaction.related_session))
        .filter(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
        .limit(10)
        .all()
    )

    return {
        "user": {
            "id": user.id,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "last_used": user.last_used,
            "usage_limit": user.usage_limit,
            "usage_count": user.usage_count,
        },
        "statistics": {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "processing_sessions": total_sessions - completed_sessions,
            "total_segments": total_segments,
            "completed_segments": completed_segments,
        },
        "recent_sessions": [
            {
                "id": session.id,
                "status": session.status,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in recent_sessions
        ],
        "recent_credit_transactions": [
            serialize_credit_transaction(transaction)
            for transaction in recent_credit_transactions
        ],
    }


@router.get("/sessions")
async def get_all_sessions(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
    limit: int = 100,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """获取所有会话历史"""
    query = db.query(OptimizationSession).options(
        joinedload(OptimizationSession.user),
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).order_by(OptimizationSession.created_at.desc())
    
    if status:
        query = query.filter(OptimizationSession.status == status)
    
    sessions = query.limit(limit).all()
    
    if not sessions:
        return []

    # 批量获取段落统计信息
    session_ids = [s.id for s in sessions]
    # 批量获取会话的原始文本长度
    original_lengths = db.query(
        OptimizationSession.id,
        func.length(OptimizationSession.original_text).label('length')
    ).filter(
        OptimizationSession.id.in_(session_ids)
    ).all()
    
    original_length_map = {item.id: (item.length or 0) for item in original_lengths}

    stats_query = db.query(
        OptimizationSegment.session_id,
        func.count(OptimizationSegment.id).label('total'),
        func.sum(case((OptimizationSegment.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(func.length(func.coalesce(OptimizationSegment.polished_text, ''))).label('polished_chars'),
        func.sum(func.length(func.coalesce(OptimizationSegment.enhanced_text, ''))).label('enhanced_chars')
    ).filter(
        OptimizationSegment.session_id.in_(session_ids)
    ).group_by(OptimizationSegment.session_id).all()
    
    stats_map = {
        stat.session_id: {
            'total': stat.total,
            'completed': stat.completed,
            'polished_chars': stat.polished_chars or 0,
            'enhanced_chars': stat.enhanced_chars or 0
        }
        for stat in stats_query
    }
    
    result = []
    for session in sessions:
        # 计算处理时间
        processing_time = None
        if session.completed_at and session.created_at:
            processing_time = (session.completed_at - session.created_at).total_seconds()
        elif session.status in {'processing', 'waiting_browser_agent'} and session.created_at:
            processing_time = (utcnow() - session.created_at).total_seconds()
        
        # 获取统计信息
        stats = stats_map.get(session.id, {
            'total': 0, 'completed': 0, 'polished_chars': 0, 'enhanced_chars': 0
        })
        
        result.append({
            "session_id": session.id,
            "user_id": session.user_id,
            **_session_user_identity(session.user),
            "status": session.status,
            "processing_mode": session.processing_mode,
            "original_char_count": original_length_map.get(session.id, 0),
            "polished_char_count": int(stats['polished_chars']),
            "enhanced_char_count": int(stats['enhanced_chars']),
            "total_segments": stats['total'],
            "completed_segments": stats['completed'],
            "progress": round((stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0, 1),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "processing_time": processing_time,
            "error_message": None, # 列表页不返回详细错误信息
        })
    
    return result


@router.get("/sessions/active")
async def get_active_sessions(
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """获取所有活跃会话（处理、排队或等待插件）- 使用批量查询避免N+1问题。"""
    # 使用 joinedload 预加载用户信息，避免N+1查询
    active_sessions = db.query(OptimizationSession).options(
        joinedload(OptimizationSession.user),
        defer(OptimizationSession.original_text)  # 延迟加载大文本字段
    ).filter(
        OptimizationSession.status.in_(["processing", "queued", "waiting_browser_agent"])
    ).order_by(OptimizationSession.created_at.desc()).all()

    if not active_sessions:
        return []

    # 批量获取会话ID
    session_ids = [s.id for s in active_sessions]

    # 批量查询原文长度和预览（避免加载完整文本）
    text_info = db.query(
        OptimizationSession.id,
        func.length(OptimizationSession.original_text).label('length'),
        func.substring(OptimizationSession.original_text, 1, 200).label('preview')
    ).filter(
        OptimizationSession.id.in_(session_ids)
    ).all()
    text_info_map = {
        item.id: {'length': item.length or 0, 'preview': item.preview or ""}
        for item in text_info
    }

    # 批量查询已完成段落数
    segments_stats = db.query(
        OptimizationSegment.session_id,
        func.sum(case((OptimizationSegment.status == 'completed', 1), else_=0)).label('completed')
    ).filter(
        OptimizationSegment.session_id.in_(session_ids)
    ).group_by(OptimizationSegment.session_id).all()

    segments_map = {stat.session_id: int(stat.completed or 0) for stat in segments_stats}

    result = []
    now = utcnow()
    for session in active_sessions:
        # 计算处理时间
        processing_time = None
        if session.status in {"processing", "waiting_browser_agent"} and session.created_at:
            processing_time = (now - session.created_at).total_seconds()

        text_data = text_info_map.get(session.id, {'length': 0, 'preview': ""})

        result.append({
            "id": session.id,
            "session_id": session.session_id,
            "user_id": session.user_id,
            **_session_user_identity(session.user),
            "status": session.status,
            "progress": session.progress,
            "current_stage": session.current_stage,
            "current_position": session.current_position,
            "total_segments": session.total_segments,
            "processed_segments": segments_map.get(session.id, 0),
            "original_text": text_data['preview'],
            "original_char_count": text_data['length'],
            "processing_mode": session.processing_mode,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "processing_time": processing_time,
            "error_message": session.error_message
        })

    return result


@router.get("/users/{user_id}/sessions")
async def get_user_sessions(
    user_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """获取指定用户的所有会话历史"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    sessions = db.query(OptimizationSession).options(
        defer(OptimizationSession.original_text),
        defer(OptimizationSession.error_message)
    ).filter(
        OptimizationSession.user_id == user_id
    ).order_by(OptimizationSession.created_at.desc()).limit(50).all()
    
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    
    # 批量获取会话的原始文本长度和预览
    original_info = db.query(
        OptimizationSession.id,
        func.length(OptimizationSession.original_text).label('length'),
        func.substring(OptimizationSession.original_text, 1, 100).label('preview')
    ).filter(
        OptimizationSession.id.in_(session_ids)
    ).all()
    
    original_info_map = {
        item.id: {'length': item.length or 0, 'preview': item.preview or ""}
        for item in original_info
    }

    stats_query = db.query(
        OptimizationSegment.session_id,
        func.count(OptimizationSegment.id).label('total'),
        func.sum(case((OptimizationSegment.status == 'completed', 1), else_=0)).label('completed'),
        func.sum(func.length(func.coalesce(OptimizationSegment.polished_text, ''))).label('polished_chars'),
        func.sum(func.length(func.coalesce(OptimizationSegment.enhanced_text, ''))).label('enhanced_chars')
    ).filter(
        OptimizationSegment.session_id.in_(session_ids)
    ).group_by(OptimizationSegment.session_id).all()
    
    stats_map = {
        stat.session_id: {
            'total': stat.total,
            'completed': stat.completed,
            'polished_chars': stat.polished_chars or 0,
            'enhanced_chars': stat.enhanced_chars or 0
        }
        for stat in stats_query
    }
    
    result = []
    for session in sessions:
        # 计算处理时间
        processing_time = None
        if session.completed_at and session.created_at:
            processing_time = (session.completed_at - session.created_at).total_seconds()
        elif session.status in {"processing", "waiting_browser_agent"} and session.created_at:
            processing_time = (utcnow() - session.created_at).total_seconds()
        
        stats = stats_map.get(session.id, {
            'total': 0, 'completed': 0, 'polished_chars': 0, 'enhanced_chars': 0
        })
        
        orig_info = original_info_map.get(session.id, {'length': 0, 'preview': ""})

        result.append({
            "id": session.id,
            "session_id": session.session_id,
            "status": session.status,
            "processing_mode": session.processing_mode,
            "original_text": orig_info['preview'],
            "original_char_count": orig_info['length'],
            "polished_char_count": int(stats['polished_chars']),
            "enhanced_char_count": int(stats['enhanced_chars']),
            "total_segments": stats['total'],
            "completed_segments": stats['completed'],
            "progress": session.progress,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "processing_time": processing_time,
            "error_message": None # 列表页不返回详细错误信息
        })
    
    return result


@router.get("/config")
async def get_config(_: str = Depends(get_admin_from_token)) -> Dict[str, Any]:
    return {
        "polish": {
            "model": settings.POLISH_MODEL,
            **_api_key_summary(settings.POLISH_API_KEY),
            "base_url": settings.POLISH_BASE_URL or "",
        },
        "enhance": {
            "model": settings.ENHANCE_MODEL,
            **_api_key_summary(settings.ENHANCE_API_KEY),
            "base_url": settings.ENHANCE_BASE_URL or "",
        },
        "emotion": {
            "model": getattr(settings, 'EMOTION_MODEL', settings.POLISH_MODEL),
            **_api_key_summary(getattr(settings, 'EMOTION_API_KEY', settings.POLISH_API_KEY)),
            "base_url": getattr(settings, 'EMOTION_BASE_URL', settings.POLISH_BASE_URL) or "",
        },
        "compression": {
            "model": settings.COMPRESSION_MODEL,
            **_api_key_summary(settings.COMPRESSION_API_KEY),
            "base_url": settings.COMPRESSION_BASE_URL or "",
        },
        "document_parse": {
            "pdf_structure_engine": (settings.PDF_STRUCTURE_ENGINE or "mineru").strip().lower(),
            "mineru_base_url": settings.MINERU_BASE_URL or "",
            "mineru_api_token_set": _api_key_summary(settings.MINERU_API_TOKEN)["api_key_set"],
            "mineru_api_token_last4": _api_key_summary(settings.MINERU_API_TOKEN)["api_key_last4"],
            "mineru_model_version": settings.MINERU_MODEL_VERSION or "",
            "mineru_enable_formula": settings.MINERU_ENABLE_FORMULA,
            "mineru_enable_table": settings.MINERU_ENABLE_TABLE,
            "mineru_is_ocr": settings.MINERU_IS_OCR,
            "mineru_language": settings.MINERU_LANGUAGE or "",
            "mineru_timeout_seconds": settings.MINERU_TIMEOUT_SECONDS,
            "mineru_poll_interval_seconds": settings.MINERU_POLL_INTERVAL_SECONDS,
        },
        "thinking": {
            "enabled": settings.THINKING_MODE_ENABLED,
            "effort": settings.THINKING_MODE_EFFORT,
        },
        "security": {
            "admin_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "user_token_expire_minutes": settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES,
            "auth_rate_limit_per_minute": settings.AUTH_RATE_LIMIT_PER_MINUTE,
            "redeem_rate_limit_per_minute": settings.REDEEM_RATE_LIMIT_PER_MINUTE,
        },
        "system": {
            "model_provider_name": settings.MODEL_PROVIDER_NAME,
            "model_api_format": normalize_api_format(getattr(settings, "MODEL_API_FORMAT", "openai_chat")),
            "max_concurrent_users": settings.MAX_CONCURRENT_USERS,
            "api_key_concurrency": settings.API_KEY_CONCURRENCY,
            "max_pending_sessions_per_user": settings.MAX_PENDING_SESSIONS_PER_USER,
            "history_compression_threshold": settings.HISTORY_COMPRESSION_THRESHOLD,
            "default_usage_limit": settings.DEFAULT_USAGE_LIMIT,
            "segment_skip_threshold": settings.SEGMENT_SKIP_THRESHOLD,
            "use_streaming": settings.USE_STREAMING,
            "max_upload_file_size_mb": settings.MAX_UPLOAD_FILE_SIZE_MB,
            "api_request_interval": settings.API_REQUEST_INTERVAL,
            "registration_enabled": settings.REGISTRATION_ENABLED,
            "server_host": settings.SERVER_HOST,
            "allow_local_model_proxy": settings.ALLOW_LOCAL_MODEL_PROXY,
        },
    }


@router.post("/config")
async def update_config(
    updates: Dict[str, str],
    request: Request,
    admin_username: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    updates = {
        key: value
        for key, value in updates.items()
        if not (key in SECRET_CONFIG_FIELDS and not str(value or "").strip())
    }
    updates = _validate_document_parse_updates(updates)
    updates = _validate_concurrency_updates(updates)
    updates = _validate_model_base_url_updates(updates)
    if "MODEL_API_FORMAT" in updates:
        try:
            updates["MODEL_API_FORMAT"] = normalize_api_format(updates["MODEL_API_FORMAT"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少更新内容")

    try:
        _persist_runtime_env_updates(updates)
        refresh_cors_middleware(request.app)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if "MAX_CONCURRENT_USERS" in updates:
        try:
            await concurrency_manager.update_limit(int(updates["MAX_CONCURRENT_USERS"]))
        except ValueError:
            pass

    write_admin_audit_log(
        db,
        admin_username,
        "update_config",
        target_type="system_config",
        detail={"updated_keys": list(updates.keys())},
    )
    db.commit()

    return {"message": "配置已更新并保存", "updated_keys": list(updates.keys())}


@router.get("/database/tables")
async def list_tables(_: str = Depends(get_admin_from_token)) -> Dict[str, Any]:
    _ensure_database_manager_enabled()
    return {
        "tables": list(ALLOWED_TABLES.keys()),
        "can_write": settings.ADMIN_DATABASE_WRITE_ENABLED,
        "max_page_size": DATABASE_MANAGER_MAX_PAGE_SIZE,
    }


@router.get("/database/{table_name}")
async def fetch_table_records(
    table_name: str,
    skip: int = 0,
    limit: int = 50,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_database_manager_enabled()
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    page_size = max(min(limit, DATABASE_MANAGER_MAX_PAGE_SIZE), 1)
    safe_skip = max(skip, 0)
    query = db.query(model)
    if hasattr(model, "id"):
        query = query.order_by(getattr(model, "id").desc())
    query = query.offset(safe_skip).limit(page_size)
    records = [sanitize_db_record(_model_to_dict(row)) for row in query.all()]
    total = db.query(model).count()
    return {
        "total": total,
        "items": records,
        "skip": safe_skip,
        "limit": page_size,
        "can_write": settings.ADMIN_DATABASE_WRITE_ENABLED,
    }


@router.put("/database/{table_name}/{record_id}")
async def update_table_record(
    table_name: str,
    record_id: int,
    payload: DatabaseUpdateRequest,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ensure_database_write_enabled()
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    record = db.query(model).filter(getattr(model, "id") == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    mapper = inspect(model)
    allowed_columns = {
        column.key
        for column in mapper.columns
        if not column.primary_key and column.key.lower() not in SENSITIVE_DB_FIELDS
    }

    for key, value in payload.data.items():
        if isinstance(record, SystemSetting) and key == "value" and _is_sensitive_system_setting_key(record.key):
            raise HTTPException(status_code=400, detail="敏感系统配置不能通过数据库管理器修改")
        if key in allowed_columns:
            setattr(record, key, value)

    db.commit()
    db.refresh(record)
    return {"message": "记录已更新", "record": sanitize_db_record(_model_to_dict(record))}


@router.delete("/database/{table_name}/{record_id}")
async def delete_table_record(
    table_name: str,
    record_id: int,
    _: str = Depends(get_admin_from_token),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    _ensure_database_write_enabled()
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="表不存在或不允许访问")

    model = ALLOWED_TABLES[table_name]
    record = db.query(model).filter(getattr(model, "id") == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    db.delete(record)
    db.commit()
    return {"message": "记录已删除"}
