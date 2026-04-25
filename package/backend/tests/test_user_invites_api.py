def _create_user_token(username: str = "alice") -> str:
    from app.database import SessionLocal
    from app.models.models import User
    from app.utils.auth import create_user_access_token, get_password_hash

    db = SessionLocal()
    try:
        user = User(
            username=username,
            nickname=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return create_user_access_token(user.id, user.username)
    finally:
        db.close()


def test_user_can_create_only_one_registration_invite(client):
    token = _create_user_token("alice")
    headers = {"Authorization": f"Bearer {token}"}

    initial_response = client.get("/api/user/invites/my", headers=headers)
    assert initial_response.status_code == 200
    assert initial_response.json() is None

    create_response = client.post("/api/user/invites", headers=headers)
    assert create_response.status_code == 200
    invite = create_response.json()
    assert invite["code"]
    assert invite["is_active"] is True
    assert invite["created_by_user_id"] is not None
    assert invite["used_by_user_id"] is None

    repeat_response = client.post("/api/user/invites", headers=headers)
    assert repeat_response.status_code == 200
    assert repeat_response.json()["id"] == invite["id"]
    assert repeat_response.json()["code"] == invite["code"]


def test_user_created_invite_can_register_another_user_but_not_regenerate(client):
    token = _create_user_token("alice")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post("/api/user/invites", headers=headers)
    assert create_response.status_code == 200
    first_invite = create_response.json()

    register_response = client.post(
        "/api/auth/register",
        json={
            "invite_code": first_invite["code"],
            "username": "bob",
            "password": "Password123!",
        },
    )
    assert register_response.status_code == 200

    from app.database import SessionLocal
    from app.models.models import RegistrationInvite

    db = SessionLocal()
    try:
        stored_invite = db.query(RegistrationInvite).filter(RegistrationInvite.id == first_invite["id"]).one()
        assert stored_invite.is_active is False
        assert stored_invite.used_by_user_id == register_response.json()["id"]
        assert stored_invite.created_by_user_id == first_invite["created_by_user_id"]
    finally:
        db.close()

    get_response = client.get("/api/user/invites/my", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == first_invite["id"]
    assert get_response.json()["code"] == first_invite["code"]
    assert get_response.json()["is_active"] is False

    next_response = client.post("/api/user/invites", headers=headers)
    assert next_response.status_code == 200
    next_invite = next_response.json()
    assert next_invite["id"] == first_invite["id"]
    assert next_invite["code"] == first_invite["code"]
    assert next_invite["is_active"] is False
