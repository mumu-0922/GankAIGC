import pytest
from cryptography.fernet import Fernet
from starlette.requests import Request

import app.config as config_module
from app.main import _get_rate_limit_key
from app.utils.crypto import decrypt_secret, encrypt_secret
from app.utils.auth import create_access_token


def _admin_auth_headers(client):
    response = client.post(
        "/api/admin/login",
        json={"username": config_module.settings.ADMIN_USERNAME, "password": config_module.settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_endpoints_require_non_default_runtime_secrets(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_register_requires_valid_invite(client):
    response = client.post(
        "/api/auth/register",
        json={
            "invite_code": "bad-code",
            "username": "alice",
            "password": "Password123!",
        },
    )

    assert response.status_code == 400


def test_login_returns_user_token(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import get_password_hash

    db = SessionLocal()
    try:
        db.add(
            User(
                username="alice",
                password_hash=get_password_hash("Password123!"),
                access_link="http://testserver/access/alice",
                is_active=True,
                credit_balance=0,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/auth/login",
        json={
            "username": "alice",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_register_with_invite_creates_user_and_disables_invite(client):
    from app.database import SessionLocal
    from app.models.models import RegistrationInvite

    db = SessionLocal()
    try:
        db.add(RegistrationInvite(code="INVITE123", is_active=True))
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/auth/register",
        json={
            "invite_code": "INVITE123",
            "username": "alice",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["nickname"] == "alice"

    db = SessionLocal()
    try:
        invite = db.query(RegistrationInvite).filter(RegistrationInvite.code == "INVITE123").one()
        assert invite.is_active is False
        assert invite.used_by_user_id == response.json()["id"]
    finally:
        db.close()


def test_register_is_blocked_when_registration_is_disabled(client, monkeypatch):
    from app.database import SessionLocal
    from app.models.models import RegistrationInvite, User

    monkeypatch.setattr(config_module.settings, "REGISTRATION_ENABLED", False, raising=False)

    db = SessionLocal()
    try:
        db.add(RegistrationInvite(code="INVITE123", is_active=True))
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/auth/register",
        json={
            "invite_code": "INVITE123",
            "username": "alice",
            "password": "Password123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "当前已关闭新用户注册"

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.username == "alice").first() is None
        invite = db.query(RegistrationInvite).filter(RegistrationInvite.code == "INVITE123").one()
        assert invite.is_active is True
        assert invite.used_by_user_id is None
    finally:
        db.close()


def test_user_me_returns_profile_for_bearer_token(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import create_user_access_token, get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            nickname="Alice Chen",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=3,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
    finally:
        db.close()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["nickname"] == "Alice Chen"
    assert response.json()["credit_balance"] == 3
    assert response.json()["created_at"]


def test_user_can_update_own_nickname(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import create_user_access_token, get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        user_id = user.id
    finally:
        db.close()

    response = client.patch(
        "/api/auth/me",
        json={"nickname": "小艾"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["nickname"] == "小艾"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.nickname == "小艾"
    finally:
        db.close()


def test_user_nickname_rejects_blank_value(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import create_user_access_token, get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
    finally:
        db.close()

    response = client.patch(
        "/api/auth/me",
        json={"nickname": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400


def test_admin_can_create_list_and_toggle_registration_invites(client):
    headers = _admin_auth_headers(client)

    create_response = client.post(
        "/api/admin/invites",
        json={"code": "INVITE123"},
        headers=headers,
    )

    assert create_response.status_code == 200
    invite = create_response.json()
    assert invite["code"] == "INVITE123"
    assert invite["is_active"] is True

    second_create_response = client.post(
        "/api/admin/invites",
        json={"code": "INVITE456"},
        headers=headers,
    )
    assert second_create_response.status_code == 200
    assert second_create_response.json()["code"] == "INVITE456"

    list_response = client.get("/api/admin/invites", headers=headers)

    assert list_response.status_code == 200
    assert [item["code"] for item in list_response.json()] == ["INVITE456", "INVITE123"]

    toggle_response = client.patch(f"/api/admin/invites/{invite['id']}/toggle", headers=headers)

    assert toggle_response.status_code == 200
    assert toggle_response.json()["is_active"] is False


def test_admin_can_toggle_user_unlimited_flag(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=0,
            is_unlimited=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    headers = _admin_auth_headers(client)
    response = client.patch(
        f"/api/admin/users/{user_id}/unlimited",
        json={"is_unlimited": True},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["is_unlimited"] is True

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.is_unlimited is True
    finally:
        db.close()


def test_server_mode_rejects_sample_placeholder_runtime_secrets(monkeypatch):
    monkeypatch.setattr(config_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "please-change-this-to-a-random-string-32-chars")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "please-change-this-password")

    with pytest.raises(RuntimeError):
        config_module.ensure_runtime_secrets_safe()


def test_server_mode_rejects_trivially_weak_custom_runtime_secrets(monkeypatch):
    monkeypatch.setattr(config_module.settings, "APP_ENV", "production")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "short")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "tiny")

    with pytest.raises(RuntimeError):
        config_module.ensure_runtime_secrets_safe()


def test_reload_settings_rejects_unsafe_server_secrets(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=production",
                "SECRET_KEY=please-change-this-to-a-random-string-32-chars",
                "ADMIN_PASSWORD=please-change-this-password",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(config_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "test-admin-password")

    with pytest.raises(RuntimeError):
        config_module.reload_settings()

    assert config_module.settings.APP_ENV == "development"
    assert config_module.settings.SECRET_KEY == "test-secret-key"
    assert config_module.settings.ADMIN_PASSWORD == "test-admin-password"


def test_env_file_path_prefers_runtime_override(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"

    monkeypatch.setenv("GANKAIGC_ENV_FILE", str(env_file))

    assert config_module.get_env_file_path() == str(env_file)


def test_admin_config_updates_runtime_env_file_from_override(client, monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=development",
                "SECRET_KEY=test-secret-key",
                "ADMIN_PASSWORD=test-admin-password",
                "POLISH_MODEL=old-model",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GANKAIGC_ENV_FILE", str(env_file))
    monkeypatch.setattr(config_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(config_module.settings, "POLISH_MODEL", "old-model")
    admin_token = create_access_token({"sub": config_module.settings.ADMIN_USERNAME, "role": "admin"})

    response = client.post(
        "/api/admin/config",
        json={"POLISH_MODEL": "new-model"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert "POLISH_MODEL=new-model" in env_file.read_text(encoding="utf-8")
    assert config_module.settings.POLISH_MODEL == "new-model"


def test_admin_config_exposes_registration_enabled(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "REGISTRATION_ENABLED", False, raising=False)

    response = client.get("/api/admin/config", headers=_admin_auth_headers(client))

    assert response.status_code == 200
    assert response.json()["system"]["registration_enabled"] is False


def test_admin_database_manager_reports_read_only_and_sanitizes_records(client):
    from app.database import SessionLocal
    from app.models.models import OptimizationSession, User
    from app.utils.auth import get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            nickname="Alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.flush()
        db.add(
            OptimizationSession(
                user_id=user.id,
                session_id="secure-db-view",
                original_text="敏感论文原文",
                error_message="敏感错误堆栈",
                status="failed",
                processing_mode="paper_polish",
            )
        )
        db.commit()
    finally:
        db.close()

    headers = _admin_auth_headers(client)

    tables_response = client.get("/api/admin/database/tables", headers=headers)
    assert tables_response.status_code == 200
    assert tables_response.json()["can_write"] is False

    users_response = client.get("/api/admin/database/users", headers=headers)
    assert users_response.status_code == 200
    user_record = users_response.json()["items"][0]
    assert user_record["username"] == "alice"
    assert "password_hash" not in user_record

    sessions_response = client.get("/api/admin/database/optimization_sessions", headers=headers)
    assert sessions_response.status_code == 200
    session_record = sessions_response.json()["items"][0]
    assert session_record["session_id"] == "secure-db-view"
    assert "original_text" not in session_record
    assert "error_message" not in session_record


def test_admin_database_write_endpoints_are_disabled_by_default(client):
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            nickname="Alice",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/alice",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    headers = _admin_auth_headers(client)

    update_response = client.put(
        f"/api/admin/database/users/{user_id}",
        json={"data": {"nickname": "Changed"}},
        headers=headers,
    )
    assert update_response.status_code == 403

    delete_response = client.delete(f"/api/admin/database/users/{user_id}", headers=headers)
    assert delete_response.status_code == 403

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.nickname == "Alice"
    finally:
        db.close()


def test_word_formatter_routes_are_not_mounted_when_disabled(client):
    usage_response = client.get("/api/word-formatter/usage")
    assert usage_response.status_code == 404

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/api/word-formatter/usage" not in paths
    assert "/api/word-formatter/specs/generate" not in paths


def test_admin_config_rollback_restores_env_file_and_live_settings_on_invalid_update(client, monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    original_env = "\n".join(
        [
            "APP_ENV=development",
            "SECRET_KEY=test-secret-key",
            "ADMIN_PASSWORD=test-admin-password",
        ]
    )
    env_file.write_text(original_env, encoding="utf-8")

    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(config_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "test-admin-password")

    response = client.post(
        "/api/admin/config",
        json={
            "APP_ENV": "production",
            "SECRET_KEY": "weak",
            "ADMIN_PASSWORD": "tiny",
        },
        headers=_admin_auth_headers(client),
    )

    assert response.status_code >= 400
    assert env_file.read_text(encoding="utf-8") == original_env
    assert config_module.settings.APP_ENV == "development"
    assert config_module.settings.SECRET_KEY == "test-secret-key"
    assert config_module.settings.ADMIN_PASSWORD == "test-admin-password"


def test_admin_config_rebuilds_active_cors_middleware(client, monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=development",
                "SECRET_KEY=test-secret-key",
                "ADMIN_PASSWORD=test-admin-password",
                "ALLOWED_ORIGINS=http://old.example",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    monkeypatch.setattr(config_module.settings, "APP_ENV", "development")
    monkeypatch.setattr(config_module.settings, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(config_module.settings, "ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(config_module.settings, "ALLOWED_ORIGINS", "http://old.example")

    before = client.options(
        "/health",
        headers={
            "Origin": "http://new.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert before.status_code == 400

    response = client.post(
        "/api/admin/config",
        json={"ALLOWED_ORIGINS": "http://new.example"},
        headers=_admin_auth_headers(client),
    )
    assert response.status_code == 200

    after = client.options(
        "/health",
        headers={
            "Origin": "http://new.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert after.status_code == 200
    assert after.headers["access-control-allow-origin"] == "http://new.example"


def test_rate_limit_key_uses_direct_client_host(monkeypatch):
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/login",
            "headers": [(b"x-forwarded-for", b"203.0.113.10")],
            "client": ("127.0.0.1", 4567),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
            "http_version": "1.1",
        }
    )

    assert _get_rate_limit_key(request, "auth") == "auth:127.0.0.1"


def test_legacy_admin_card_key_endpoints_are_removed(client):
    headers = _admin_auth_headers(client)

    legacy_requests = [
        ("post", "/api/admin/verify-card-key", {"json": {"card_key": "CARD123"}}),
        ("post", "/api/admin/card-keys", {"json": {"card_key": "CARD123"}, "headers": headers}),
        ("post", "/api/admin/batch-generate-keys?count=1", {"headers": headers}),
        ("post", f"/api/admin/generate-keys?admin_password={config_module.settings.ADMIN_PASSWORD}", {"json": {"count": 1}}),
    ]

    for method, path, kwargs in legacy_requests:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 404


def test_admin_session_lists_include_user_identity(client):
    from app.database import SessionLocal
    from app.models.models import OptimizationSession, User

    db = SessionLocal()
    try:
        user = User(
            username="alice",
            nickname="Alice Chen",
            access_link="http://testserver/access/alice",
        )
        db.add(user)
        db.flush()
        db.add_all([
            OptimizationSession(
                user_id=user.id,
                session_id="session-history",
                original_text="历史会话文本",
                status="completed",
                processing_mode="paper_polish_enhance",
                total_segments=1,
            ),
            OptimizationSession(
                user_id=user.id,
                session_id="session-active",
                original_text="实时会话文本",
                status="processing",
                processing_mode="paper_polish",
                total_segments=1,
            ),
        ])
        db.commit()
    finally:
        db.close()

    headers = _admin_auth_headers(client)

    history_response = client.get("/api/admin/sessions", params={"status": "completed"}, headers=headers)
    assert history_response.status_code == 200
    history_session = history_response.json()[0]
    assert history_session["username"] == "alice"
    assert history_session["nickname"] == "Alice Chen"
    assert history_session["user_display_name"] == "Alice Chen"

    active_response = client.get("/api/admin/sessions/active", headers=headers)
    assert active_response.status_code == 200
    active_session = active_response.json()[0]
    assert active_session["username"] == "alice"
    assert active_session["nickname"] == "Alice Chen"
    assert active_session["user_display_name"] == "Alice Chen"


def test_admin_statistics_count_all_processing_modes(client):
    from app.database import SessionLocal
    from app.models.models import OptimizationSession, User

    db = SessionLocal()
    try:
        user = User(
            username="mode_owner",
            nickname="Mode Owner",
            access_link="http://testserver/access/mode-owner",
        )
        db.add(user)
        db.flush()
        for mode in ("paper_polish", "paper_enhance", "paper_polish_enhance", "emotion_polish"):
            db.add(
                OptimizationSession(
                    user_id=user.id,
                    session_id=f"stats-{mode}",
                    original_text="统计模式文本",
                    status="completed",
                    processing_mode=mode,
                    total_segments=1,
                )
            )
        db.commit()
    finally:
        db.close()

    headers = _admin_auth_headers(client)
    response = client.get("/api/admin/statistics", headers=headers)

    assert response.status_code == 200
    processing = response.json()["processing"]
    assert processing["paper_polish_count"] == 1
    assert processing["paper_enhance_count"] == 1
    assert processing["paper_polish_enhance_count"] == 1
    assert processing["emotion_polish_count"] == 1


def test_admin_statistics_omits_word_formatter_when_feature_disabled(client):
    response = client.get("/api/admin/statistics", headers=_admin_auth_headers(client))

    assert response.status_code == 200
    assert "word_formatter" not in response.json()


def test_crypto_helpers_round_trip_with_test_fernet_key(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())

    encrypted = encrypt_secret("top-secret")

    assert encrypted != "top-secret"
    assert decrypt_secret(encrypted) == "top-secret"
