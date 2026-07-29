from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_release_workflow_builds_and_uploads_windows_oneclick_package():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "build-exe.yml").read_text(encoding="utf-8")
    release_notes = PROJECT_ROOT / ".github" / "release-notes" / "v2.1.0.md"

    assert "tags:" in workflow
    assert "- 'v*'" in workflow
    assert "build-oneclick.ps1" in workflow
    assert "-PostgresZipUrl" in workflow
    assert "GankAIGC-Windows-OneClick.zip" in workflow
    assert "name: GankAIGC-Windows-OneClick" in workflow
    assert "gh release upload" in workflow
    assert "--clobber" not in workflow
    assert "Refusing to overwrite immutable release asset" in workflow
    assert 'notes_file=".github/release-notes/${TAG_NAME}.md"' in workflow
    assert '--notes-file "$notes_file"' in workflow
    assert release_notes.exists()
    assert "多用户并发" in release_notes.read_text(encoding="utf-8")
    assert "Verify tag and commit identity" in workflow
    assert "ref: ${{ github.event.inputs.version || github.ref }}" in workflow
    assert "GankAIGC-Browser-Extension-v0.1.10.zip" in workflow
    assert "GankAIGC-Browser-Extension-v0.1.10.zip.sha256" in workflow
    assert "node --test browser-extension/tests/*.test.cjs" in workflow
    assert "sha256sum \"$asset\"" in workflow
    assert "-o -name '*.sha256'" in workflow


def test_oci_release_publishes_scans_attests_and_signs_one_digest():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "release-image.yml").read_text(
        encoding="utf-8"
    )
    production_compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )

    assert "docker/build-push-action@v6" in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "sbom: true" in workflow
    assert "provenance: mode=max" in workflow
    assert "aquasecurity/trivy-action" in workflow
    assert "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25" in workflow
    assert "sigstore/cosign-installer" in workflow
    assert "cosign sign --yes" in workflow
    assert "@${{ steps.build.outputs.digest }}" in workflow
    assert "git show-ref --verify" in workflow
    assert "tr -d '\\r\\n' < package/VERSION" in workflow
    assert '"$TAG_NAME"' in workflow
    assert "GANKAIGC_IMAGE" in production_compose
    assert "build: null" in production_compose
    assert "pull_policy: always" in production_compose


def test_release_dependency_manifests_pin_trivy_clean_python_packages():
    expected_pins = {
        "python-multipart==0.0.32",
        "setuptools==83.0.0",
        "wheel==0.46.3",
    }

    for relative_path in ("package/requirements.txt", "package/backend/requirements.txt"):
        requirements = {
            line.strip()
            for line in (PROJECT_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        assert expected_pins <= requirements, f"{relative_path} must retain the release security pins"


def test_windows_oneclick_defaults_to_local_zhuque_browser_flow():
    env_template = (PROJECT_ROOT / "package" / "windows-oneclick" / ".env.template").read_text(encoding="utf-8-sig")
    start_script = (PROJECT_ROOT / "package" / "windows-oneclick" / "runtime" / "start.ps1").read_text(encoding="utf-8-sig")
    readme = (PROJECT_ROOT / "package" / "windows-oneclick" / "README.txt").read_text(encoding="utf-8-sig")
    app_spec = (PROJECT_ROOT / "package" / "app.spec").read_text(encoding="utf-8")
    zhuque_api = (PROJECT_ROOT / "package" / "backend" / "app" / "services" / "zhuque_api.py").read_text(encoding="utf-8")
    zhuque_service = (PROJECT_ROOT / "package" / "backend" / "app" / "services" / "zhuque_service.py").read_text(encoding="utf-8")
    local_transport = (PROJECT_ROOT / "package" / "backend" / "app" / "services" / "zhuque_local_browser_transport.py").read_text(encoding="utf-8")
    capture_tool = PROJECT_ROOT / "package" / "backend" / "app" / "tools" / "zhuque_capture_window.py"

    expected_defaults = {
        "ZHUQUE_DETECT_TRANSPORT": "auto",
        "ZHUQUE_DETECT_HEADLESS": "false",
        "ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER": "true",
        "ZHUQUE_SERVER_HEADLESS_FALLBACK": "false",
        "ZHUQUE_USER_DATA_DIR": "data\\zhuque\\users",
    }
    for key, value in expected_defaults.items():
        assert f"{key}={value}" in env_template
        assert f"Set-Default $settings '{key}' '{value}'" in start_script
        assert f"(EnvLine '{key}')" in start_script

    assert "ZHUQUE_DETECT_BROWSER_EXECUTABLE=" in env_template
    assert "Set-Default $settings 'ZHUQUE_DETECT_BROWSER_EXECUTABLE' ''" in start_script
    assert "一键包默认走本机可见浏览器链路" in readme
    assert "不需要安装 GankAIGC Chrome 插件" in readme
    assert "不需要执行 playwright install" in readme
    assert "朱雀账号" in readme
    assert "剩余次数" in readme
    assert "Get-NetTCPConnection -LocalPort 9800" in readme
    assert "Assert-AppPortAvailable" in start_script
    assert "Get-NetTCPConnection -LocalPort $port -State Listen" in start_script
    assert "端口 127.0.0.1:$port 已被占用" in start_script
    assert "collect_submodules('playwright')" in app_spec
    assert "collect_data_files('playwright')" in app_spec
    assert "open_detect_page" in zhuque_api
    assert "open_detection_page" in zhuque_service
    assert '"data" / "zhuque" / "users"' in zhuque_service
    assert capture_tool.exists()
    assert not (PROJECT_ROOT / "zhuque_pkg").exists()
    assert "open_detection_page = getattr" in local_transport
    assert "zhuque_capture_window.py" not in local_transport.split("open_detection_page = getattr", 1)[0]


def test_windows_oneclick_bundles_alembic_schema_assets():
    app_spec = (PROJECT_ROOT / "package" / "app.spec").read_text(encoding="utf-8")

    assert "('backend/alembic.ini', '.')" in app_spec
    assert "('backend/migrations', 'migrations')" in app_spec


def test_windows_build_script_uses_dedicated_windows_venv():
    script = (PROJECT_ROOT / "package" / "build.ps1").read_text(encoding="utf-8-sig")

    assert '$BuildCacheRoot = Join-Path $env:LOCALAPPDATA "GankAIGC"' in script
    assert '$VenvDir = Join-Path $BuildCacheRoot "build-venv"' in script
    assert 'Scripts\\python.exe' in script
    assert '& $VenvPython -m pip --version *> $null' in script
    assert '& $VenvPython -m ensurepip --upgrade' in script
    assert '& $VenvPython -m pip install -r requirements.txt' in script
    assert '$FrontendBuildDir = Join-Path $BuildCacheRoot "frontend-build"' in script
    assert 'robocopy $FrontendSource $FrontendBuildDir /MIR /XD node_modules dist .vite' in script
    assert 'Push-Location $FrontendBuildDir' in script
    assert '& $VenvPython -m PyInstaller app.spec --clean' in script
    assert '.\\venv\\Scripts\\Activate.ps1' not in script
    assert 'python -m pip install -r requirements.txt' not in script


def test_windows_powershell_scripts_use_utf8_bom_for_legacy_powershell():
    scripts = [
        PROJECT_ROOT / "package" / "build.ps1",
        PROJECT_ROOT / "package" / "build-oneclick.ps1",
        PROJECT_ROOT / "package" / "windows-oneclick" / "runtime" / "start.ps1",
        PROJECT_ROOT / "package" / "windows-oneclick" / "runtime" / "stop.ps1",
    ]

    for script in scripts:
        assert script.read_bytes().startswith(b"\xef\xbb\xbf"), f"{script} must be UTF-8 with BOM for Windows PowerShell 5.1"


def test_oneclick_builder_validates_portable_postgres_tool_versions():
    script = (PROJECT_ROOT / "package" / "build-oneclick.ps1").read_text(encoding="utf-8")

    assert "Test-PortablePostgresVersions" in script
    assert "bin\\initdb.exe" in script
    assert "bin\\postgres.exe" in script
    assert "--version" in script
    assert "PostgreSQL 可执行文件版本不一致" in script
