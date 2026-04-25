import atexit
import os
from pathlib import Path
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(TEST_DB_FD)
_ORIGINAL_ENV = {
    "DATABASE_URL": os.environ.get("DATABASE_URL"),
    "SECRET_KEY": os.environ.get("SECRET_KEY"),
    "ADMIN_PASSWORD": os.environ.get("ADMIN_PASSWORD"),
}


def _cleanup_test_db():
    if os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)


def _restore_env():
    for key, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


atexit.register(_cleanup_test_db)
atexit.register(_restore_env)

os.environ["DATABASE_URL"] = "sqlite:///" + TEST_DB_PATH
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
    _cleanup_test_db()
