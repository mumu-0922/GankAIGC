from sqlalchemy import inspect

from app.database import SessionLocal, engine
from app.models.models import User
from app.utils.auth import create_user_access_token, get_password_hash


def test_project_schema_is_created(client):
    response = client.get("/health")
    assert response.status_code == 200

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "paper_projects" in tables

    session_columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
    assert "project_id" in session_columns
    assert "task_title" in session_columns


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
        return user.id, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_user_can_create_list_update_and_archive_projects(client):
    _, headers = _create_user()

    create_response = client.post(
        "/api/user/projects",
        json={"title": "基于大语言模型的教育应用研究", "description": "投稿前版本"},
        headers=headers,
    )
    assert create_response.status_code == 200
    project = create_response.json()
    assert project["title"] == "基于大语言模型的教育应用研究"
    assert project["description"] == "投稿前版本"
    assert project["is_archived"] is False

    list_response = client.get("/api/user/projects", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [project["id"]]

    update_response = client.patch(
        f"/api/user/projects/{project['id']}",
        json={"title": "新版题目", "description": "二稿"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "新版题目"
    assert update_response.json()["description"] == "二稿"

    archive_response = client.delete(f"/api/user/projects/{project['id']}", headers=headers)
    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    list_after_archive = client.get("/api/user/projects", headers=headers)
    assert list_after_archive.status_code == 200
    assert list_after_archive.json() == []


def test_user_cannot_update_another_users_project(client):
    _, alice_headers = _create_user("alice")
    _, bob_headers = _create_user("bob")
    project = client.post("/api/user/projects", json={"title": "Alice Paper"}, headers=alice_headers).json()

    response = client.patch(
        f"/api/user/projects/{project['id']}",
        json={"title": "Bob Edit"},
        headers=bob_headers,
    )

    assert response.status_code == 404


async def _skip_optimization(self):
    return None


def test_start_optimization_stores_project_and_task_title(client, monkeypatch):
    from app.models.models import OptimizationSession
    from app.services.optimization_service import OptimizationService

    monkeypatch.setattr(OptimizationService, "start_optimization", _skip_optimization)

    user_id, headers = _create_user()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        user.credit_balance = 1
        db.commit()
    finally:
        db.close()

    project = client.post("/api/user/projects", json={"title": "Paper A"}, headers=headers).json()
    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "platform",
            "project_id": project["id"],
            "task_title": "摘要降 AI",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["project_id"] == project["id"]
    assert response.json()["project_title"] == "Paper A"
    assert response.json()["task_title"] == "摘要降 AI"

    db = SessionLocal()
    try:
        session = db.query(OptimizationSession).filter(OptimizationSession.id == response.json()["id"]).one()
        assert session.project_id == project["id"]
        assert session.task_title == "摘要降 AI"
    finally:
        db.close()


def test_start_optimization_rejects_another_users_project(client):
    _, alice_headers = _create_user("alice")
    _, bob_headers = _create_user("bob")
    project = client.post("/api/user/projects", json={"title": "Alice Paper"}, headers=alice_headers).json()

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "byok",
            "project_id": project["id"],
            "task_title": "bad attach",
        },
        headers=bob_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "论文项目不存在"


def test_list_sessions_can_filter_by_project_and_unfiled(client, monkeypatch):
    from app.services.optimization_service import OptimizationService

    monkeypatch.setattr(OptimizationService, "start_optimization", _skip_optimization)
    user_id, headers = _create_user()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        user.credit_balance = 2
        db.commit()
    finally:
        db.close()

    project = client.post("/api/user/projects", json={"title": "Paper A"}, headers=headers).json()
    client.post(
        "/api/optimization/start",
        json={
            "original_text": "project paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "platform",
            "project_id": project["id"],
        },
        headers=headers,
    )
    client.post(
        "/api/optimization/start",
        json={
            "original_text": "unfiled paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "platform",
        },
        headers=headers,
    )

    project_sessions = client.get(f"/api/optimization/sessions?project_id={project['id']}", headers=headers)
    assert project_sessions.status_code == 200
    assert len(project_sessions.json()) == 1
    assert project_sessions.json()[0]["project_id"] == project["id"]

    unfiled_sessions = client.get("/api/optimization/sessions?project_id=0", headers=headers)
    assert unfiled_sessions.status_code == 200
    assert len(unfiled_sessions.json()) == 1
    assert unfiled_sessions.json()[0]["project_id"] is None
