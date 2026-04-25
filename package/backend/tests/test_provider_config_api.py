from cryptography.fernet import Fernet

import app.config as config_module
from app.database import SessionLocal
from app.models.models import OptimizationSession, User, UserProviderConfig
from app.utils.auth import create_user_access_token, get_password_hash


def _admin_auth_headers(client):
    response = client.post(
        "/api/admin/login",
        json={"username": config_module.settings.ADMIN_USERNAME, "password": config_module.settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class NoRunBackgroundTasks:
    def add_task(self, *args, **kwargs):
        return None


def _create_user(username="alice"):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        return user.id, token
    finally:
        db.close()


def test_saved_provider_config_is_not_returned_in_plaintext(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    user_id, token = _create_user()

    payload = {
        "base_url": "https://api.example/v1/",
        "api_key": "sk-test-secret",
        "polish_model": "gpt-5.4",
        "enhance_model": "gpt-5.4",
        "emotion_model": "gpt-5.4-mini",
    }

    put_response = client.put(
        "/api/user/provider-config",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert put_response.status_code == 200
    assert put_response.json() == {
        "base_url": "https://api.example/v1",
        "api_key_last4": "cret",
        "polish_model": "gpt-5.4",
        "enhance_model": "gpt-5.4",
        "emotion_model": "gpt-5.4-mini",
    }

    get_response = client.get("/api/user/provider-config", headers={"Authorization": f"Bearer {token}"})

    assert get_response.status_code == 200
    assert "sk-test-secret" not in get_response.text
    assert get_response.json()["api_key_last4"] == "cret"

    db = SessionLocal()
    try:
        config = db.query(UserProviderConfig).filter(UserProviderConfig.user_id == user_id).one()
        assert config.api_key_encrypted != "sk-test-secret"
        assert config.api_key_last4 == "cret"
    finally:
        db.close()


def test_admin_provider_config_summary_masks_user_api_key(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    _, token = _create_user()
    client.put(
        "/api/user/provider-config",
        json={
            "base_url": "https://api.example/v1/",
            "api_key": "sk-test-secret",
            "polish_model": "gpt-5.4",
            "enhance_model": "gpt-5.4",
            "emotion_model": "gpt-5.4-mini",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get("/api/admin/provider-configs", headers=_admin_auth_headers(client))

    assert response.status_code == 200
    assert "sk-test-secret" not in response.text
    assert response.json() == [
        {
            "user_id": 1,
            "username": "alice",
            "base_url": "https://api.example/v1",
            "api_key_last4": "cret",
            "polish_model": "gpt-5.4",
            "enhance_model": "gpt-5.4",
            "emotion_model": "gpt-5.4-mini",
            "updated_at": response.json()[0]["updated_at"],
        }
    ]


def test_byok_start_requires_saved_user_provider(client):
    _, token = _create_user()

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_polish",
            "billing_mode": "byok",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"


def test_byok_start_optimization_uses_saved_user_provider(client, monkeypatch):
    from app.routes import optimization

    monkeypatch.setattr(config_module.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(optimization, "BackgroundTasks", NoRunBackgroundTasks)
    user_id, token = _create_user()
    client.put(
        "/api/user/provider-config",
        json={
            "base_url": "https://api.example/v1/",
            "api_key": "sk-test-secret",
            "polish_model": "gpt-5.4",
            "enhance_model": "gpt-5.4",
            "emotion_model": "gpt-5.4-mini",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_polish",
            "billing_mode": "byok",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["credential_source"] == "user_saved"
    assert response.json()["charge_status"] == "not_charged"

    db = SessionLocal()
    try:
        session = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).one()
        user = db.query(User).filter(User.id == user_id).one()
        assert user.credit_balance == 0
        assert session.polish_model == "gpt-5.4"
        assert session.polish_base_url == "https://api.example/v1"
        assert session.polish_api_key is None
        assert session.credential_source == "user_saved"
    finally:
        db.close()
