import atexit
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_ORIGINAL_ENV = {
    "DATABASE_URL": os.environ.get("DATABASE_URL"),
    "SECRET_KEY": os.environ.get("SECRET_KEY"),
    "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
}


def _restore_env():
    for key, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


atexit.register(_restore_env)

TEST_DATABASE_URL = os.environ.get(
    "GANKAIGC_TEST_DATABASE_URL",
    "postgresql://ai_polish:postgres@127.0.0.1:5432/gankaigc_test",
)
test_database_name = make_url(TEST_DATABASE_URL).database or ""
if "test" not in test_database_name.lower():
    raise RuntimeError("GANKAIGC_TEST_DATABASE_URL must point to a dedicated PostgreSQL test database")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"

from app.models import models  # noqa: F401
from app.main import app, auth_rate_limiter, redeem_rate_limiter
from app.database import Base, engine


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    auth_rate_limiter.reset()
    redeem_rate_limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _restore_env()
