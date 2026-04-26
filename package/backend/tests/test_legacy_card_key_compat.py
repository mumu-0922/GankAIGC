from app.database import SessionLocal
from app.models.models import User
from app.utils.auth import create_user_access_token, get_password_hash


def _create_user(username="alice", card_key=None, legacy_card_key=None):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=get_password_hash("Password123!"),
            card_key=card_key,
            legacy_card_key=legacy_card_key,
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


def test_user_token_can_access_prompt_routes(client):
    _, token = _create_user()

    response = client.get("/api/prompts/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_legacy_card_key_no_longer_authenticates_prompt_routes(client):
    _create_user(username="legacy", card_key="legacy-demo-key")

    response = client.get("/api/prompts/", params={"card_key": "legacy-demo-key"})

    assert response.status_code == 401


def test_bearer_token_is_preferred_over_invalid_card_key(client):
    _, token = _create_user()

    response = client.get(
        "/api/prompts/",
        params={"card_key": "wrong-key"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_user_token_can_access_word_formatter_usage(client):
    _, token = _create_user()

    response = client.get("/api/word-formatter/usage", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["usage_count"] == 0


def test_legacy_card_key_no_longer_authenticates_word_formatter_usage(client):
    _create_user(username="legacy", card_key="legacy-demo-key")

    response = client.get("/api/word-formatter/usage", params={"card_key": "legacy-demo-key"})

    assert response.status_code == 401


def test_query_access_token_supports_browser_direct_urls(client):
    _, token = _create_user()

    response = client.get("/api/word-formatter/usage", params={"access_token": token})

    assert response.status_code == 200
    assert response.json()["usage_count"] == 0
