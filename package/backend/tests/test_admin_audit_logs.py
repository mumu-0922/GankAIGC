import app.config as config_module
from app.database import SessionLocal
from app.models.models import SystemSetting, User


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


def _create_user(username="audit-user"):
    db = SessionLocal()
    try:
        user = User(username=username, access_link=f"access-{username}", credit_balance=0)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _audit_logs(client, headers):
    response = client.get("/api/admin/audit-logs?limit=50", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_audit_logs_require_admin_login(client):
    response = client.get("/api/admin/audit-logs?limit=50")

    assert response.status_code == 401


def test_create_invite_writes_audit_log(client):
    headers = _admin_auth_headers(client)

    response = client.post("/api/admin/invites", json={"code": "INV-AUDIT"}, headers=headers)

    assert response.status_code == 200
    logs = _audit_logs(client, headers)
    assert logs[0]["action"] == "create_invite"
    assert logs[0]["target_type"] == "registration_invite"
    assert logs[0]["target_id"] == response.json()["id"]
    assert logs[0]["admin_username"] == config_module.settings.ADMIN_USERNAME
    assert logs[0]["detail"]["code"] == "INV-AUDIT"


def test_credit_code_recharge_and_ban_logs_are_returned_newest_first(client):
    headers = _admin_auth_headers(client)
    user_id = _create_user()

    credit_code_response = client.post(
        "/api/admin/credit-codes",
        json={"code": "BEER-AUDIT", "credit_amount": 12},
        headers=headers,
    )
    recharge_response = client.post(
        f"/api/admin/users/{user_id}/credits",
        json={"amount": 5, "reason": "admin_recharge"},
        headers=headers,
    )
    ban_response = client.patch(f"/api/admin/users/{user_id}/toggle", headers=headers)
    unban_response = client.patch(f"/api/admin/users/{user_id}/toggle", headers=headers)

    assert credit_code_response.status_code == 200
    assert recharge_response.status_code == 200
    assert ban_response.status_code == 200
    assert unban_response.status_code == 200

    logs = _audit_logs(client, headers)
    actions = [log["action"] for log in logs]
    assert actions[:4] == [
        "unban_user",
        "ban_user",
        "add_user_credits",
        "create_credit_code",
    ]
    assert logs[0]["target_id"] == user_id
    assert logs[2]["detail"] == {"amount": 5, "reason": "admin_recharge"}
    assert logs[3]["detail"]["credit_amount"] == 12


def test_admin_profile_can_update_display_name_and_writes_audit_log(client):
    headers = _admin_auth_headers(client)

    profile_response = client.get("/api/admin/profile", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == config_module.settings.ADMIN_USERNAME
    assert profile_response.json()["display_name"] == config_module.settings.ADMIN_USERNAME
    assert profile_response.json()["role"] == "管理员"

    update_response = client.patch(
        "/api/admin/profile",
        json={"display_name": "魔尊后台"},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "魔尊后台"
    assert update_response.json()["profile_source"] == "system_settings"
    logs = _audit_logs(client, headers)
    assert logs[0]["action"] == "update_admin_profile"
    assert logs[0]["target_type"] == "admin_profile"
    assert logs[0]["detail"] == {"updated_keys": ["display_name"]}


def test_admin_profile_avatar_upload_persists_url_and_audit_log(client, tmp_path, monkeypatch):
    from app.utils import avatar_upload

    monkeypatch.setattr(avatar_upload, "get_upload_root", lambda: tmp_path / "uploads")
    headers = _admin_auth_headers(client)
    png = b"\x89PNG\r\n\x1a\n" + (b"0" * 64)

    response = client.post(
        "/api/admin/profile/avatar",
        headers=headers,
        files={"avatar": ("avatar.png", png, "image/png")},
    )

    assert response.status_code == 200
    avatar_url = response.json()["avatar_url"]
    assert avatar_url.startswith("/uploads/avatars/")
    assert avatar_url.endswith(".png")
    assert (tmp_path / "uploads" / avatar_url.removeprefix("/uploads/")).read_bytes() == png

    db = SessionLocal()
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == "ADMIN_AVATAR_URL").one()
        assert setting.value == avatar_url
    finally:
        db.close()

    logs = _audit_logs(client, headers)
    assert logs[0]["action"] == "update_admin_avatar"
    assert logs[0]["target_type"] == "admin_profile"
    assert logs[0]["detail"] == {"updated_keys": ["avatar_url"], "avatar_url": avatar_url}
    assert str(tmp_path) not in str(logs[0])


def test_admin_profile_avatar_upload_rejects_svg(client, tmp_path, monkeypatch):
    from app.utils import avatar_upload

    monkeypatch.setattr(avatar_upload, "get_upload_root", lambda: tmp_path / "uploads")
    headers = _admin_auth_headers(client)

    response = client.post(
        "/api/admin/profile/avatar",
        headers=headers,
        files={"avatar": ("avatar.svg", b"<svg></svg>", "image/svg+xml")},
    )

    assert response.status_code == 400
    assert "PNG、JPG、WebP" in response.json()["detail"]



def test_admin_profile_password_update_persists_without_leaking_secret(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=test-secret-key\nADMIN_PASSWORD=test-admin-password\n", encoding="utf-8")
    original_password = config_module.settings.ADMIN_PASSWORD
    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    headers = _admin_auth_headers(client)

    try:
        response = client.post(
            "/api/admin/profile/password",
            json={"current_password": "test-admin-password", "new_password": "new-admin-password-123"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["message"] == "管理员密码已更新，请用新密码重新登录"
        assert "ADMIN_PASSWORD=new-admin-password-123" in env_file.read_text(encoding="utf-8")
        assert config_module.settings.ADMIN_PASSWORD == "new-admin-password-123"
        logs = _audit_logs(client, headers)
        assert logs[0]["action"] == "update_admin_password"
        assert logs[0]["detail"] == {"updated_keys": ["ADMIN_PASSWORD"]}
        assert "new-admin-password-123" not in str(logs[0])

        old_login = client.post(
            "/api/admin/login",
            json={"username": config_module.settings.ADMIN_USERNAME, "password": "test-admin-password"},
        )
        new_login = client.post(
            "/api/admin/login",
            json={"username": config_module.settings.ADMIN_USERNAME, "password": "new-admin-password-123"},
        )
        assert old_login.status_code == 401
        assert new_login.status_code == 200
    finally:
        config_module.settings.ADMIN_PASSWORD = original_password


def test_config_update_audit_log_records_only_keys(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_PASSWORD=test-admin-password\nPOLISH_API_KEY=old-secret\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    headers = _admin_auth_headers(client)

    response = client.post(
        "/api/admin/config",
        json={"POLISH_API_KEY": "new-secret-value", "MAX_CONCURRENT_USERS": "5"},
        headers=headers,
    )

    assert response.status_code == 200
    logs = _audit_logs(client, headers)
    assert logs[0]["action"] == "update_config"
    assert logs[0]["target_type"] == "system_config"
    assert logs[0]["detail"] == {"updated_keys": ["POLISH_API_KEY", "MAX_CONCURRENT_USERS"]}
    assert "new-secret-value" not in str(logs[0])


def test_config_update_rejects_unsupported_concurrency_tiers(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_PASSWORD=test-admin-password\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    headers = _admin_auth_headers(client)

    task_response = client.post(
        "/api/admin/config",
        json={"MAX_CONCURRENT_USERS": "7"},
        headers=headers,
    )
    key_response = client.post(
        "/api/admin/config",
        json={"API_KEY_CONCURRENCY": "3"},
        headers=headers,
    )

    assert task_response.status_code == 400
    assert "5 / 8 / 10" in task_response.json()["detail"]
    assert key_response.status_code == 400
    assert "1 / 2 / 4" in key_response.json()["detail"]
    assert env_file.read_text(encoding="utf-8") == "ADMIN_PASSWORD=test-admin-password\n"
