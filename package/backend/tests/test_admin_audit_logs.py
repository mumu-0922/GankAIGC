import app.config as config_module
from app.database import SessionLocal
from app.models.models import User


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


def test_config_update_audit_log_records_only_keys(client, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ADMIN_PASSWORD=test-admin-password\nPOLISH_API_KEY=old-secret\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "get_env_file_path", lambda: str(env_file))
    headers = _admin_auth_headers(client)

    response = client.post(
        "/api/admin/config",
        json={"POLISH_API_KEY": "new-secret-value", "MAX_CONCURRENT_USERS": "3"},
        headers=headers,
    )

    assert response.status_code == 200
    logs = _audit_logs(client, headers)
    assert logs[0]["action"] == "update_config"
    assert logs[0]["target_type"] == "system_config"
    assert logs[0]["detail"] == {"updated_keys": ["POLISH_API_KEY", "MAX_CONCURRENT_USERS"]}
    assert "new-secret-value" not in str(logs[0])
