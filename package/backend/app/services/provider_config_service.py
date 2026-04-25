from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import User, UserProviderConfig
from app.schemas import ProviderConfigResponse, ProviderConfigUpdateRequest
from app.utils.crypto import decrypt_secret, encrypt_secret


class ProviderConfigService:
    def __init__(self, db: Session):
        self.db = db

    def save_config(self, user: User, payload: ProviderConfigUpdateRequest) -> UserProviderConfig:
        config = self.db.query(UserProviderConfig).filter(UserProviderConfig.user_id == user.id).first()
        if not config:
            config = UserProviderConfig(user_id=user.id)
            self.db.add(config)

        config.base_url = payload.base_url.rstrip("/")
        config.api_key_encrypted = encrypt_secret(payload.api_key)
        config.api_key_last4 = payload.api_key[-4:]
        config.polish_model = payload.polish_model
        config.enhance_model = payload.enhance_model
        config.emotion_model = payload.emotion_model
        return config

    def get_masked_config(self, user: User) -> ProviderConfigResponse | None:
        config = self.db.query(UserProviderConfig).filter(UserProviderConfig.user_id == user.id).first()
        if not config:
            return None

        return ProviderConfigResponse(
            base_url=config.base_url,
            api_key_last4=config.api_key_last4,
            polish_model=config.polish_model,
            enhance_model=config.enhance_model,
            emotion_model=config.emotion_model,
        )

    def get_runtime_config(self, user: User) -> dict:
        config = self.db.query(UserProviderConfig).filter(UserProviderConfig.user_id == user.id).first()
        if not config:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先保存自带 API 配置")

        return {
            "base_url": config.base_url,
            "api_key": decrypt_secret(config.api_key_encrypted),
            "polish_model": config.polish_model,
            "enhance_model": config.enhance_model,
            "emotion_model": config.emotion_model,
        }
