from app.database import SessionLocal
from app.models.models import User
from app.utils.auth import create_user_access_token, get_password_hash


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


def test_user_token_can_access_prompt_routes(client):
    _, token = _create_user()

    response = client.get("/api/prompts/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_legacy_card_key_no_longer_authenticates_prompt_routes(client):
    _create_user(username="legacy")

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


def test_word_formatter_usage_route_is_unavailable_when_feature_disabled(client):
    _, token = _create_user()

    response = client.get("/api/word-formatter/usage", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


def test_legacy_card_key_cannot_reach_disabled_word_formatter_usage(client):
    _create_user(username="legacy")

    response = client.get("/api/word-formatter/usage", params={"card_key": "legacy-demo-key"})

    assert response.status_code == 404


def test_query_access_token_cannot_reach_disabled_word_formatter_usage(client):
    _, token = _create_user()

    response = client.get("/api/word-formatter/usage", params={"access_token": token})

    assert response.status_code == 404
