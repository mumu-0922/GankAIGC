from sqlalchemy import inspect
import base64
import re

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


def _create_completed_session(user_id, project_id=None, task_title=None, session_id="export-session"):
    from app.models.models import OptimizationSegment, OptimizationSession

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id=session_id,
            original_text="original paragraph",
            current_stage="enhance",
            status="completed",
            progress=100,
            current_position=1,
            total_segments=1,
            processing_mode="paper_enhance",
            project_id=project_id,
            task_title=task_title,
        )
        db.add(session)
        db.flush()
        db.add(
            OptimizationSegment(
                session_id=session.id,
                segment_index=0,
                stage="enhance",
                original_text="original paragraph",
                enhanced_text="final paragraph",
                status="completed",
            )
        )
        db.commit()
    finally:
        db.close()


def test_export_supports_markdown_and_word_with_project_task_filename(client):
    user_id, headers = _create_user()
    project = client.post(
        "/api/user/projects",
        json={"title": "基于大语言模型的教育应用研究"},
        headers=headers,
    ).json()
    _create_completed_session(
        user_id,
        project_id=project["id"],
        task_title="摘要降 AI",
        session_id="export-project-task",
    )

    markdown_response = client.post(
        "/api/optimization/sessions/export-project-task/export",
        json={
            "session_id": "export-project-task",
            "acknowledge_academic_integrity": True,
            "export_format": "md",
        },
        headers=headers,
    )

    assert markdown_response.status_code == 200
    markdown_payload = markdown_response.json()
    assert markdown_payload["format"] == "md"
    assert markdown_payload["content"] == "final paragraph"
    assert markdown_payload["mime_type"] == "text/markdown;charset=utf-8"
    assert re.fullmatch(
        r"基于大语言模型的教育应用研究_摘要降 AI_\d{8}_\d{6}\.md",
        markdown_payload["filename"],
    )

    word_response = client.post(
        "/api/optimization/sessions/export-project-task/export",
        json={
            "session_id": "export-project-task",
            "acknowledge_academic_integrity": True,
            "export_format": "docx",
        },
        headers=headers,
    )

    assert word_response.status_code == 200
    word_payload = word_response.json()
    assert word_payload["format"] == "docx"
    assert word_payload["mime_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert re.fullmatch(
        r"基于大语言模型的教育应用研究_摘要降 AI_\d{8}_\d{6}\.docx",
        word_payload["filename"],
    )
    assert base64.b64decode(word_payload["content_base64"]).startswith(b"PK")


def test_export_filename_uses_project_without_task_or_unfiled(client):
    user_id, headers = _create_user()
    project = client.post(
        "/api/user/projects",
        json={"title": "论文项目A"},
        headers=headers,
    ).json()
    _create_completed_session(user_id, project_id=project["id"], session_id="export-project-only")
    _create_completed_session(user_id, task_title="孤立任务", session_id="export-unfiled")

    project_response = client.post(
        "/api/optimization/sessions/export-project-only/export",
        json={
            "session_id": "export-project-only",
            "acknowledge_academic_integrity": True,
            "export_format": "md",
        },
        headers=headers,
    )
    unfiled_response = client.post(
        "/api/optimization/sessions/export-unfiled/export",
        json={
            "session_id": "export-unfiled",
            "acknowledge_academic_integrity": True,
            "export_format": "md",
        },
        headers=headers,
    )

    assert project_response.status_code == 200
    assert re.fullmatch(r"论文项目A_\d{8}_\d{6}\.md", project_response.json()["filename"])
    assert unfiled_response.status_code == 200
    assert re.fullmatch(r"未归档_\d{8}_\d{6}\.md", unfiled_response.json()["filename"])
    assert "孤立任务" not in unfiled_response.json()["filename"]


def test_export_rejects_removed_txt_and_pdf_formats(client):
    user_id, headers = _create_user()
    _create_completed_session(user_id, session_id="export-format-check")

    for export_format in ("txt", "pdf"):
        response = client.post(
            "/api/optimization/sessions/export-format-check/export",
            json={
                "session_id": "export-format-check",
                "acknowledge_academic_integrity": True,
                "export_format": export_format,
            },
            headers=headers,
        )

        assert response.status_code == 422
