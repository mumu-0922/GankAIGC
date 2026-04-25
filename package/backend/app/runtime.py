from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware

from app.config import get_allowed_origins


def refresh_cors_middleware(app: FastAPI) -> None:
    app.user_middleware = [middleware for middleware in app.user_middleware if middleware.cls is not CORSMiddleware]
    app.user_middleware.insert(
        0,
        Middleware(
            CORSMiddleware,
            allow_origins=get_allowed_origins(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    )
    if app.middleware_stack is not None:
        app.middleware_stack = app.build_middleware_stack()
