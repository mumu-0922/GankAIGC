from cryptography.fernet import Fernet

from app.config import settings


def get_cipher() -> Fernet:
    if not settings.ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY is required for saved provider configs")
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_secret(value: str) -> str:
    return get_cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return get_cipher().decrypt(value.encode()).decode()
