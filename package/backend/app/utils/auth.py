import secrets
import string
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.database import get_db
from app.models.models import User
from sqlalchemy.orm import Session


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_card_key(length: int = 16, prefix: str = "") -> str:
    """生成卡密"""
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(length))
    if prefix:
        return f"{prefix}-{random_part}"
    return random_part


def generate_access_link(card_key: str, base_url: Optional[str] = None) -> str:
    """生成访问链接"""
    resolved_base_url = base_url or f"http://localhost:{settings.SERVER_PORT}"
    return f"{resolved_base_url.rstrip('/')}/access/{card_key}"


def generate_session_id() -> str:
    """生成会话ID"""
    return secrets.token_urlsafe(32)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.USER_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_user_access_token(user_id: int, username: str, expires_delta: Optional[timedelta] = None) -> str:
    return create_access_token(
        {"sub": str(user_id), "username": username, "role": "user"},
        expires_delta=expires_delta,
    )


def verify_token(token: str) -> Optional[dict]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_user_token(token: str) -> Optional[dict]:
    payload = verify_token(token)
    if payload and payload.get("role") == "user":
        return payload
    return None


def get_current_user_from_bearer(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    token = authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else None
    payload = verify_user_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    user_id = payload.get("sub")
    if not user_id or not str(user_id).isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    user = db.query(User).filter(User.id == int(user_id), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    user.last_used = datetime.utcnow()
    db.commit()
    return user


def get_current_user_with_legacy_fallback(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = None,
    card_key: Optional[str] = None,
    db: Session = Depends(get_db),
) -> User:
    if authorization and authorization.startswith("Bearer "):
        return get_current_user_from_bearer(authorization, db)

    if access_token:
        payload = verify_user_token(access_token)
        if payload:
            user_id = payload.get("sub")
            if user_id and str(user_id).isdigit():
                user = db.query(User).filter(User.id == int(user_id), User.is_active.is_(True)).first()
                if user:
                    user.last_used = datetime.utcnow()
                    db.commit()
                    return user

    if card_key:
        user = (
            db.query(User)
            .filter(
                (User.legacy_card_key == card_key) | (User.card_key == card_key),
                User.is_active.is_(True),
            )
            .first()
        )
        if user:
            user.last_used = datetime.utcnow()
            db.commit()
            return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少有效用户凭据")
