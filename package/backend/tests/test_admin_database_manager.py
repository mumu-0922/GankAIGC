import app.config as config_module
from app.database import SessionLocal
from app.models.models import OptimizationSession, SystemSetting, User
from app.routes.admin import sanitize_db_record
from app.utils.auth import create_user_access_token, get_password_hash


def _admin_auth_headers(client):
    response = client.post(
        "/api/admin/login",
        json={
            "username": config_module.settings.ADMIN_USERNAME,
            "password": config_module.settings.ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_database_manager_requires_admin_token(client):
    assert client.get("/api/admin/database/tables").status_code == 401

    user_headers = {"Authorization": f"Bearer {create_user_access_token(1, 'alice')}"}
    response = client.get("/api/admin/database/tables", headers=user_headers)

    assert response.status_code == 401


def test_database_manager_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ADMIN_DATABASE_MANAGER_ENABLED", False)
    headers = _admin_auth_headers(client)

    tables_response = client.get("/api/admin/database/tables", headers=headers)
    records_response = client.get("/api/admin/database/users", headers=headers)
    write_response = client.put(
        "/api/admin/database/users/1",
        json={"data": {"nickname": "Changed"}},
        headers=headers,
    )

    assert tables_response.status_code == 404
    assert records_response.status_code == 404
    assert write_response.status_code == 404


def test_database_manager_sanitizes_sensitive_and_long_records(client):
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
        db.add(SystemSetting(key="POLISH_API_KEY", value="secret-api-key"))
        db.commit()
    finally:
        db.close()

    headers = _admin_auth_headers(client)

    users_response = client.get("/api/admin/database/users", headers=headers)
    assert users_response.status_code == 200
    user_record = users_response.json()["items"][0]
    assert user_record["username"] == "alice"
    assert "password_hash" not in user_record
    assert "access_link" not in user_record

    sessions_response = client.get("/api/admin/database/optimization_sessions", headers=headers)
    assert sessions_response.status_code == 200
    session_record = sessions_response.json()["items"][0]
    assert session_record["session_id"] == "secure-db-view"
    assert "original_text" not in session_record
    assert "error_message" not in session_record

    settings_response = client.get("/api/admin/database/system_settings", headers=headers)
    assert settings_response.status_code == 200
    settings_by_key = {item["key"]: item for item in settings_response.json()["items"]}
    assert "value" not in settings_by_key["POLISH_API_KEY"]

    long_record = sanitize_db_record({"id": 1, "notes": "x" * 500})
    assert long_record["notes"].endswith("...")
    assert len(long_record["notes"]) == 243


def test_database_manager_limits_page_size_and_orders_by_latest_id(client):
    db = SessionLocal()
    try:
        db.add_all(
            SystemSetting(key=f"setting_{index:03d}", value="value")
            for index in range(130)
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/admin/database/system_settings",
        params={"limit": 500},
        headers=_admin_auth_headers(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 130
    assert payload["limit"] == 100
    assert len(payload["items"]) == 100
    assert payload["items"][0]["key"] == "setting_129"
    assert payload["items"][-1]["key"] == "setting_030"


def test_database_write_is_read_only_by_default(client):
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
    delete_response = client.delete(f"/api/admin/database/users/{user_id}", headers=headers)

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_sensitive_system_settings_cannot_be_changed_through_database_manager(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ADMIN_DATABASE_WRITE_ENABLED", True)
    db = SessionLocal()
    try:
        setting = SystemSetting(key="SECRET_KEY", value="old-secret")
        db.add(setting)
        db.commit()
        db.refresh(setting)
        setting_id = setting.id
    finally:
        db.close()

    response = client.put(
        f"/api/admin/database/system_settings/{setting_id}",
        json={"data": {"value": "new-secret"}},
        headers=_admin_auth_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "敏感系统配置不能通过数据库管理器修改"

    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.id == setting_id).one()
        assert setting.value == "old-secret"
    finally:
        db.close()
