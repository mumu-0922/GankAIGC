# Utils package

__all__ = [
    "generate_session_id",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "verify_token",
]


def __getattr__(name):
    if name in __all__:
        from app.utils import auth

        return getattr(auth, name)
    raise AttributeError(f"module 'app.utils' has no attribute {name!r}")
