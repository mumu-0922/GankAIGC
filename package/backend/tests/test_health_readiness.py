from sqlalchemy import text

from app.database import engine
from app.schema import upgrade_database_schema


def test_live_is_process_only_and_ready_checks_schema_and_upload_mount(client, monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setenv("GANKAIGC_UPLOAD_ROOT", str(upload_root))
    upgrade_database_schema(lock_timeout_seconds=5)

    live = client.get("/live")
    ready = client.get("/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["schema_revision"].startswith("0011")


def test_ready_fails_closed_for_unversioned_database(client, monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setenv("GANKAIGC_UPLOAD_ROOT", str(upload_root))
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    response = client.get("/ready")

    assert response.status_code == 503
    assert "Schema 未就绪" in response.json()["detail"]
