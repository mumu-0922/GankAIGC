import importlib.util
import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_MAIN = PACKAGE_ROOT / "main.py"


def _load_package_main():
    previous_cwd = os.getcwd()
    spec = importlib.util.spec_from_file_location("gankaigc_package_main_for_tests", PACKAGE_MAIN)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(previous_cwd)


def test_browser_host_uses_localhost_for_wildcard_bind_addresses():
    package_main = _load_package_main()

    assert package_main.get_browser_host("0.0.0.0") == "localhost"
    assert package_main.get_browser_host("::") == "localhost"
    assert package_main.get_browser_host("") == "localhost"


def test_browser_host_keeps_specific_bind_addresses():
    package_main = _load_package_main()

    assert package_main.get_browser_host("127.0.0.1") == "127.0.0.1"
    assert package_main.get_browser_host("localhost") == "localhost"
    assert package_main.get_browser_host("192.168.1.20") == "192.168.1.20"


def test_uvicorn_host_uses_localhost_for_wildcard_in_local_mode():
    package_main = _load_package_main()

    assert package_main.get_uvicorn_host("0.0.0.0", server_deployment=False) == "localhost"
    assert package_main.get_uvicorn_host("::", server_deployment=False) == "localhost"


def test_uvicorn_host_preserves_wildcard_in_server_mode():
    package_main = _load_package_main()

    assert package_main.get_uvicorn_host("0.0.0.0", server_deployment=True) == "0.0.0.0"
    assert package_main.get_uvicorn_host("::", server_deployment=True) == "::"


def test_main_uses_display_host_for_prints_and_uvicorn_host_for_binding():
    package_main_source = PACKAGE_MAIN.read_text(encoding="utf-8")

    assert "server_deployment = is_server_deployment()" in package_main_source
    assert "browser_host = get_browser_host(host)" in package_main_source
    assert "uvicorn_host = get_uvicorn_host(host, server_deployment)" in package_main_source
    assert "host=uvicorn_host" in package_main_source
