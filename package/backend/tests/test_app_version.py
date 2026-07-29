from pathlib import Path

import tempfile

from app.config import APP_VERSION, read_app_version


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_packaged_app_version_matches_release_tag():
    assert APP_VERSION == "2.1.0"


def test_app_version_prefers_version_file_when_present():
    with tempfile.TemporaryDirectory() as temp_dir:
        version_file = Path(temp_dir) / "VERSION"
        version_file.write_text("v9.8.7\n", encoding="utf-8")

        assert read_app_version(temp_dir) == "9.8.7"


def test_app_version_falls_back_to_environment_variable(monkeypatch):
    monkeypatch.setenv("GANKAIGC_VERSION", "v8.7.6")

    assert read_app_version("__missing_version_dir__") == "8.7.6"


def test_admin_dashboard_fallback_version_uses_build_environment_variable():
    admin_dashboard = (
        PROJECT_ROOT / "package" / "frontend" / "src" / "pages" / "AdminDashboard.jsx"
    ).read_text(encoding="utf-8")

    assert "import.meta.env.VITE_APP_VERSION" in admin_dashboard


def test_pyinstaller_bundle_includes_version_file():
    spec = (PROJECT_ROOT / "package" / "app.spec").read_text(encoding="utf-8")

    assert "VERSION" in spec


def test_release_workflow_writes_tag_to_version_file_before_building():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-exe.yml").read_text(encoding="utf-8")

    assert "Set package version" in workflow
    assert "VERSION" in workflow
    assert "VITE_APP_VERSION" in workflow
