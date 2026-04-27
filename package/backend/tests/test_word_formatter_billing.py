from cryptography.fernet import Fernet

import app.config as config_module
from app.database import SessionLocal
from app.models.models import User
from app.utils.auth import create_user_access_token, get_password_hash


def _create_user(username="alice", credit_balance=0, is_unlimited=False):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
            is_active=True,
            is_unlimited=is_unlimited,
            credit_balance=credit_balance,
            usage_limit=0,
            usage_count=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        return user.id, token
    finally:
        db.close()


def _save_provider_config(client, token):
    return client.put(
        "/api/user/provider-config",
        json={
            "base_url": "https://api.example/v1/",
            "api_key": "sk-test-secret",
            "polish_model": "gpt-5.5",
            "enhance_model": "gpt-5.5",
            "emotion_model": "gpt-5.5",
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def _format_text(client, token, billing_mode="platform"):
    return client.post(
        "/api/word-formatter/format/text",
        json={
            "text": "测试论文标题\n\n这是用于 Word 排版计费测试的正文段落。",
            "billing_mode": billing_mode,
            "include_cover": False,
            "include_toc": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def _generate_spec(client, token, billing_mode="platform"):
    return client.post(
        "/api/word-formatter/specs/generate",
        json={
            "requirements": "标题三号黑体居中，正文小四号宋体，一级标题三号黑体，段落首行缩进两字符。",
            "billing_mode": billing_mode,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def _preprocess_text(client, token, billing_mode="platform"):
    return client.post(
        "/api/word-formatter/preprocess/text",
        json={
            "text": "测试论文标题\n\n这是用于 Word 预处理计费测试的正文段落，长度满足校验要求。",
            "billing_mode": billing_mode,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_word_formatter_platform_mode_requires_credit_balance(client):
    _, token = _create_user(credit_balance=0)

    response = _format_text(client, token, billing_mode="platform")

    assert response.status_code == 403
    assert response.json()["detail"] == "平台剩余额度不足，本次需要 1 额度，当前剩余 0 额度"


def test_word_formatter_spec_generation_platform_mode_requires_credit_balance(client):
    _, token = _create_user(username="spec_platform", credit_balance=0)

    response = _generate_spec(client, token, billing_mode="platform")

    assert response.status_code == 403
    assert response.json()["detail"] == "平台剩余额度不足，本次需要 1 额度，当前剩余 0 额度"


def test_word_formatter_preprocess_platform_mode_requires_credit_balance(client):
    _, token = _create_user(username="preprocess_platform", credit_balance=0)

    response = _preprocess_text(client, token, billing_mode="platform")

    assert response.status_code == 403
    assert response.json()["detail"] == "平台剩余额度不足，本次需要 1 额度，当前剩余 0 额度"


def test_word_formatter_platform_mode_consumes_one_credit(client):
    user_id, token = _create_user(credit_balance=1)

    response = _format_text(client, token, billing_mode="platform")

    assert response.status_code == 200
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.credit_balance == 0
        assert user.usage_count == 0
    finally:
        db.close()


def test_word_formatter_byok_requires_saved_provider_config(client):
    _, token = _create_user(credit_balance=0)

    response = _format_text(client, token, billing_mode="byok")

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"


def test_word_formatter_spec_generation_byok_requires_saved_provider_config(client):
    _, token = _create_user(username="spec_byok", credit_balance=0)

    response = _generate_spec(client, token, billing_mode="byok")

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"


def test_word_formatter_preprocess_byok_requires_saved_provider_config(client):
    _, token = _create_user(username="preprocess_byok", credit_balance=0)

    response = _preprocess_text(client, token, billing_mode="byok")

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"


def test_word_formatter_byok_does_not_consume_platform_credit(client, monkeypatch):
    monkeypatch.setattr(config_module.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    user_id, token = _create_user(credit_balance=0)
    save_response = _save_provider_config(client, token)
    assert save_response.status_code == 200

    response = _format_text(client, token, billing_mode="byok")

    assert response.status_code == 200
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.credit_balance == 0
        assert user.usage_count == 0
    finally:
        db.close()
