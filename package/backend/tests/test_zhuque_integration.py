import asyncio
import json
from pathlib import Path

import pytest

from app.database import SessionLocal
from app.models.models import CreditTransaction, OptimizationSegment, OptimizationSession, User, ZhuquePromptMemory
from app.services.ai_service import count_text_length
from app.services.optimization_service import OptimizationService
from app.utils.auth import create_user_access_token, get_password_hash


class FakeZhuqueService:
    def __init__(self, rates):
        self.rates = list(rates)
        self.detected_texts = []
        self.detect_contexts = []
        self.start_calls = 0
        self.readiness_calls = []

    async def start(self):
        self.start_calls += 1

    async def readiness(self, text=None):
        self.readiness_calls.append(text)
        return {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 99,
            "button_enabled": True,
            "text_length": len(text or ""),
            "text_length_ok": len(text or "") >= 350 if text is not None else True,
            "estimated_first_round_credits": 10,
            "estimated_max_round_credits": 50,
            "message": "朱雀已就绪",
            "actions": [],
        }

    async def detect(self, text, **context):
        self.detected_texts.append(text)
        self.detect_contexts.append(context)
        next_result = self.rates.pop(0)
        if isinstance(next_result, dict):
            result = dict(next_result)
            result.setdefault("success", True)
            result.setdefault("remaining_uses", 99)
            result.setdefault("text_length", len(text))
            return result

        rate = next_result
        return {
            "success": True,
            "rate": rate,
            "labels_ratio": {"0": rate / 100, "1": max(0, 1 - rate / 100), "2": 0.0},
            "remaining_uses": 99,
            "text_length": len(text),
        }


class FailingZhuqueService:
    def __init__(self, message):
        self.message = message
        self.start_calls = 0
        self.detected_texts = []

    async def start(self):
        self.start_calls += 1

    async def detect(self, text, **_context):
        self.detected_texts.append(text)
        return {
            "success": False,
            "message": self.message,
            "rate": 0,
            "rate_label": "",
            "labels_ratio": {},
            "alert_text": "",
            "alert_title": "",
            "remaining_uses": -1,
            "text_length": len(text),
        }


class UnavailableZhuqueService:
    def __init__(self, port=9223):
        self.start_calls = 0
        self.detect_calls = 0
        self.port = port

    async def start(self):
        self.start_calls += 1
        raise RuntimeError("未找到朱雀微信登录凭证，请先微信扫码授权")

    async def readiness(self, text=None):
        return {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": False,
            "text_length": len(text or ""),
            "text_length_ok": len(text or "") >= 350 if text is not None else True,
            "estimated_first_round_credits": 0,
            "estimated_max_round_credits": 0,
            "message": "未找到朱雀微信登录凭证",
            "actions": ["微信扫码登录朱雀"],
        }

    async def detect(self, text, **_context):
        self.detect_calls += 1
        raise AssertionError("detect should not run when Zhuque preflight fails")


class StatusOnlyZhuqueAPI:
    def __init__(self, status_payload):
        self.status_payload = status_payload
        self.status_calls = 0
        self.peek_calls = []

    async def status(self):
        self.status_calls += 1
        return dict(self.status_payload)

    def credential_status(self):
        self.status_calls += 1
        return dict(self.status_payload)

    async def detect(self, text, timeout=60.0):
        return {
            "success": True,
            "rate": 0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "remaining_uses": 4,
            "text_length": len(text),
        }

    async def peek_remaining_uses(self, timeout=3.0, *, allow_anonymous=False):
        self.peek_calls.append({"timeout": timeout, "allow_anonymous": allow_anonymous})
        return self.status_payload.get("peek_remaining_uses")

    async def peek_quota_status(self, timeout=3.0, *, allow_anonymous=False):
        try:
            remaining = await self.peek_remaining_uses(timeout=timeout, allow_anonymous=allow_anonymous)
        except TypeError:
            remaining = await self.peek_remaining_uses(timeout=timeout)
        return {
            "remaining_uses": remaining if remaining is not None else -1,
            "button_enabled": self.status_payload.get("peek_button_enabled", self.status_payload.get("button_enabled", remaining is not None and remaining > 0)),
            "page_found": self.status_payload.get("peek_page_found", True),
            "quota_text": self.status_payload.get("peek_quota_text", ""),
            "message": self.status_payload.get("peek_message", ""),
        }


class FakeAIService:
    def __init__(self):
        self.polish_calls = []
        self.enhance_calls = []

    async def polish_text(self, text, prompt, history=None, stream=False):
        self.polish_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        if "rewrite_mode: paper_reconstruction" in prompt:
            return json.dumps(
                {
                    "candidates": [
                        {"id": "A", "text": text.replace("具有重要支撑", "提供参考")},
                        {"id": "B", "text": text.replace("进一步为临床辅助诊断提供重要支撑", "可作为临床辅助诊断的参考")},
                        {"id": "C", "text": text.replace("有效提升", "改善").replace("重要支撑", "参考")},
                    ]
                },
                ensure_ascii=False,
            )
        return f"润色后:{text}"

    async def enhance_text(self, text, prompt, history=None, stream=False):
        self.enhance_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        return f"增强后:{text}"

    async def generate(self, prompt):
        raise AssertionError("ai_detect_reduce must reuse polish_text + enhance_text, not a separate reduce prompt")


class FakeBatchAIService(FakeAIService):
    def __init__(self):
        super().__init__()
        self.complete_calls = []

    async def complete(self, messages, temperature=0.7, max_tokens=None, reasoning_effort=None):
        self.complete_calls.append(
            {
                "messages": list(messages or []),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
        )
        payload = json.loads(messages[-1]["content"])
        stage = "增强" if "当前阶段的增强处理" in messages[0]["content"] else "润色"
        prefix = "增强后" if stage == "增强" else "润色后"
        return json.dumps(
            [
                {"id": item["id"], "text": f"{prefix}:{item['text']}"}
                for item in payload
            ],
            ensure_ascii=False,
        )


class BloatedThenLengthRepairAIService(FakeAIService):
    def __init__(self, repaired_text):
        super().__init__()
        self.repaired_text = repaired_text

    async def polish_text(self, text, prompt, history=None, stream=False):
        self.polish_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        return text

    async def enhance_text(self, text, prompt, history=None, stream=False):
        self.enhance_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        if "朱雀长度校正" in prompt:
            return self.repaired_text
        return f"{text}{'额外解释' * 80}"


class PlateauRecoveryAIService(FakeAIService):
    async def polish_text(self, text, prompt, history=None, stream=False):
        self.polish_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        if "卡点候选B" in prompt:
            return f"自动探索B:{text}"
        if "卡点候选C" in prompt:
            return f"自动探索C:{text}"
        if "卡点候选A" in prompt:
            return f"自动探索A:{text}"
        if "逐段候选S2" in prompt:
            return f"局部探索S2:{text}"
        if "逐段候选S1" in prompt:
            return f"局部探索S1:{text}"
        return f"常规:{text}"

    async def enhance_text(self, text, prompt, history=None, stream=False):
        self.enhance_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        return text


class DeepReconstructionAIService(PlateauRecoveryAIService):
    async def polish_text(self, text, prompt, history=None, stream=False):
        self.polish_calls.append(
            {
                "text": text,
                "prompt": prompt,
                "history": list(history or []),
                "stream": stream,
            }
        )
        if "深度重构路线:evidence_first" in prompt:
            return f"深度重构证据优先:{text}"
        if "深度重构路线:method_first" in prompt:
            return f"深度重构方法优先:{text}"
        if "深度重构路线:constraint_first" in prompt:
            return f"深度重构限定优先:{text}"
        return await super().polish_text(text, prompt, history=history, stream=stream)


def _install_fake_ai_services(service, fake_ai):
    service.polish_service = fake_ai
    service.enhance_service = fake_ai


def _joined_segment_starts(segment_texts):
    starts = []
    cursor = 0
    for text in segment_texts:
        starts.append(cursor)
        cursor += len(text) + 2
    return starts


def _zhuque_capture_tool_path() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "tools" / "zhuque_capture_window.py"


def _create_user(*, credit_balance=20, zhuque_free_uses_remaining=20):
    db = SessionLocal()
    try:
        user = User(
            username="zhuque-user",
            password_hash=get_password_hash("Password123!"),
            access_link="http://testserver/access/zhuque-user",
            is_active=True,
            credit_balance=credit_balance,
            zhuque_free_uses_remaining=zhuque_free_uses_remaining,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def test_zhuque_wechat_capture_launches_sync_session_script(monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    script_path = tmp_path / "zhuque_capture_window.py"
    script_path.write_text("print('capture')", encoding="utf-8")
    popen_calls = []

    class FakePopen:
        def __init__(self, args, cwd=None, env=None, stdout=None, stderr=None, start_new_session=None):
            popen_calls.append(
                {
                    "args": args,
                    "cwd": cwd,
                    "env": env,
                    "stdout": stdout,
                    "stderr": stderr,
                    "start_new_session": start_new_session,
                }
            )

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": True,
                "credential_file": str(script_path.parent / "creds_latest.json"),
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_zhuque_capture_script_path", lambda: script_path)
    monkeypatch.setattr(optimization_route.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(optimization_route, "_zhuque_playwright_browser_ready", lambda: True)
    monkeypatch.setattr(optimization_route.subprocess, "Popen", FakePopen)

    fake_user = type("FakeUser", (), {"id": 42})()
    monkeypatch.setattr(optimization_route, "zhuque_user_dir", lambda user_id: tmp_path / "users" / f"user_{user_id}")

    result = optimization_route._start_zhuque_wechat_capture(user=fake_user)

    assert result["status"] == "started"
    assert result["auth_mode"] == "headless_api"
    assert result["login_mode"] == "wechat_qr"
    assert result["credential_file"].endswith("creds_latest.json")
    assert result["sync_session"] is True
    assert "真实网页状态同步" in result["message"]
    assert popen_calls
    assert popen_calls[0]["args"] == [optimization_route.sys.executable, str(script_path), "--sync-session"]
    assert popen_calls[0]["cwd"] == str(script_path.parent)
    assert "PLAYWRIGHT_BROWSERS_PATH" in popen_calls[0]["env"]
    assert popen_calls[0]["env"]["ZHUQUE_CAPTURE_DIR"].endswith("users/user_42")
    assert popen_calls[0]["start_new_session"] is True


def test_zhuque_wechat_capture_sync_session_does_not_clear_stale_credentials(monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    script_path = tmp_path / "zhuque_capture_window.py"
    script_path.write_text("print('capture')", encoding="utf-8")
    creds_file = script_path.parent / "creds_latest.json"
    state_file = script_path.parent / "browser_state.json"
    creds_file.write_text('{"access_token":"old"}', encoding="utf-8")
    state_file.write_text("{}", encoding="utf-8")
    popen_calls = []

    class FakePopen:
        def __init__(self, args, cwd=None, env=None, stdout=None, stderr=None, start_new_session=None):
            popen_calls.append({"args": args, "cwd": cwd, "start_new_session": start_new_session})

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": True,
                "credential_file": str(creds_file),
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_zhuque_capture_script_path", lambda: script_path)
    monkeypatch.setattr(optimization_route.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(optimization_route, "_zhuque_playwright_browser_ready", lambda: True)
    monkeypatch.setattr(optimization_route.subprocess, "Popen", FakePopen)

    result = optimization_route._start_zhuque_wechat_capture(sync_session=True)

    assert result["status"] == "started"
    assert result["sync_session"] is True
    assert popen_calls[0]["args"] == [optimization_route.sys.executable, str(script_path), "--sync-session"]
    assert creds_file.exists()
    assert state_file.exists()


def test_zhuque_wechat_capture_prefers_windows_chrome_on_wsl(monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    script_path = tmp_path / "zhuque_capture_window.py"
    script_path.write_text("print('capture')", encoding="utf-8")
    windows_chrome = tmp_path / "chrome.exe"
    windows_chrome.write_text("", encoding="utf-8")
    popen_calls = []

    class FakePopen:
        def __init__(self, args, cwd=None, env=None, stdout=None, stderr=None, start_new_session=None):
            popen_calls.append(
                {
                    "args": args,
                    "cwd": cwd,
                    "env": env,
                    "start_new_session": start_new_session,
                }
            )

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": False,
                "credential_file": str(script_path.parent / "creds_latest.json"),
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setenv("ZHUQUE_CDP_PORT", "9333")
    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_zhuque_capture_script_path", lambda: script_path)
    monkeypatch.setattr(optimization_route, "_zhuque_local_browser_executable", lambda: windows_chrome)
    monkeypatch.setattr(optimization_route.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(optimization_route.subprocess, "Popen", FakePopen)

    result = optimization_route._start_zhuque_wechat_capture(sync_session=True)

    assert result["status"] == "started"
    assert popen_calls
    assert popen_calls[0]["args"] == [optimization_route.sys.executable, str(script_path), "--sync-session"]
    assert popen_calls[0]["env"]["ZHUQUE_CHROME_EXECUTABLE"] == str(windows_chrome)
    assert popen_calls[0]["env"]["ZHUQUE_CDP_PORT"] == "9333"


def test_zhuque_capture_does_not_fallback_after_windows_chrome_cdp_failure(monkeypatch):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_no_fallback", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakePlaywrightManager:
        async def start(self):
            return self

        @property
        def chromium(self):
            raise AssertionError("Playwright Chromium must not launch when Windows Chrome CDP is unavailable")

        async def stop(self):
            pass

    messages = []
    monkeypatch.setattr(module, "async_playwright", lambda: FakePlaywrightManager())
    monkeypatch.setattr(module, "find_browser_executable", lambda: "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
    monkeypatch.setattr(module, "_is_wsl", lambda: True)
    monkeypatch.setattr(module, "is_windows_browser_executable", lambda executable: True)
    monkeypatch.setattr(
        module,
        "launch_windows_chrome_for_cdp",
        lambda executable: (False, "Windows Chrome 已启动但调试端口 9333 未就绪", ""),
    )
    monkeypatch.setattr(module, "write_logged_out_status", lambda message, auth_state=None: messages.append(message))

    result = asyncio.run(module.capture_flow(sync_session=True))

    assert result == {
        "status": "windows_chrome_cdp_unavailable",
        "message": "Windows Chrome 已启动但调试端口 9333 未就绪",
    }
    assert messages == ["Windows Chrome 已启动但调试端口 9333 未就绪"]


def test_zhuque_capture_uses_windows_powershell_bridge(monkeypatch):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_bridge", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakePlaywrightManager:
        async def start(self):
            raise AssertionError("PowerShell bridge mode must not start Playwright")

    bridge_calls = []
    monkeypatch.setattr(module, "async_playwright", lambda: FakePlaywrightManager())
    monkeypatch.setattr(module, "find_browser_executable", lambda: "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
    monkeypatch.setattr(module, "_is_wsl", lambda: True)
    monkeypatch.setattr(module, "is_windows_browser_executable", lambda executable: True)
    monkeypatch.setattr(
        module,
        "launch_windows_chrome_for_cdp",
        lambda executable: (True, "已启动 Windows Chrome 小窗；将通过 Windows 同步桥读取调试端口 9333", "windows-powershell-bridge"),
    )

    async def fake_bridge(**kwargs):
        bridge_calls.append(kwargs)
        return {"status": "closed"}

    monkeypatch.setattr(module, "sync_windows_chrome_session_until_closed", fake_bridge)

    result = asyncio.run(module.capture_flow(sync_session=True))

    assert result == {"status": "closed"}
    assert bridge_calls == [{"trigger_login_when_missing": True}]


def test_zhuque_capture_powershell_json_decodes_windows_codepage(monkeypatch):
    import importlib.util
    import subprocess

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_powershell_decode", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    payload = '{"ok":false,"error":"中文错误"}\n'.encode("gb18030")
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(args[0], 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module._powershell_json("Write-Output '{}'")

    assert result == {"ok": False, "error": "中文错误"}
    assert calls and calls[0]["text"] is False


def test_zhuque_local_window_and_retry_reset_cached_user_service():
    route_source = (Path(__file__).resolve().parents[1] / "app" / "routes" / "optimization.py").read_text(encoding="utf-8")

    local_window_branch = route_source.split('if mode == "local_window":', 1)[1].split("payload = await zhuque_remote_login_service.start", 1)[0]
    retry_block = route_source.split("async def retry_session", 1)[1].split("db.commit()", 1)[0]

    assert 'getattr(zhuque_service, "reset_user", lambda _user_id: None)(user.id)' in local_window_branch
    assert 'if session.processing_mode == "ai_detect_reduce":' in retry_block
    assert 'getattr(zhuque_service, "reset_user", lambda _user_id: None)(user.id)' in retry_block


def test_zhuque_capture_restarts_stale_windows_debug_profile(monkeypatch):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_restart_profile", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    stopped = []
    launched = []
    cdp_checks = []

    class FakePopen:
        def __init__(self, args, stdout=None, stderr=None, close_fds=None):
            launched.append(args)

    def fake_wait_for_cdp(port, timeout=8.0):
        cdp_checks.append(timeout)
        return "" if len(cdp_checks) == 1 else "http://127.0.0.1:9333"

    monkeypatch.setattr(module, "_is_wsl", lambda: True)
    monkeypatch.setattr(module, "_wait_for_cdp", fake_wait_for_cdp)
    monkeypatch.setattr(module, "_windows_cdp_available", lambda port=None: False)
    monkeypatch.setattr(module, "_windows_chrome_profile_dir", lambda: r"C:\Users\Administrator\AppData\Local\GankAIGC\ZhuqueChromeProfile")
    monkeypatch.setattr(module, "_stop_windows_chrome_debug_profile", lambda profile, port: stopped.append((profile, port)) or 1)
    monkeypatch.setattr(module.subprocess, "Popen", FakePopen)

    ok, message, endpoint = module.launch_windows_chrome_for_cdp(
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
        port=9333,
    )

    assert ok is True
    assert endpoint == "http://127.0.0.1:9333"
    assert "调试端口 9333" in message
    assert stopped == [(r"C:\Users\Administrator\AppData\Local\GankAIGC\ZhuqueChromeProfile", 9333)]
    assert launched and "--remote-debugging-port=9333" in launched[0]


def test_zhuque_capture_logged_out_status_preserves_previous_quota_when_page_quota_flickers(monkeypatch, tmp_path):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_preserve_quota", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "SESSION_STATUS_FILE", tmp_path / "session_status.json")

    module.write_session_status(
        module._logged_out_status_with_previous_quota(
            {"quotaText": "", "submitButtonText": "", "remainingUses": -1},
            message="朱雀网页显示未登录",
            previous_remaining_uses=16,
        )
    )

    status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["remaining_uses"] == 16
    assert status["quota_text"] == ""


def test_zhuque_capture_logged_out_status_prefers_live_page_quota_over_previous(monkeypatch, tmp_path):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_live_quota", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "SESSION_STATUS_FILE", tmp_path / "session_status.json")

    module.write_session_status(
        module._logged_out_status_with_previous_quota(
            {"quotaText": "Detect now(15 left)", "submitButtonText": "", "remainingUses": -1},
            message="朱雀网页显示未登录",
            previous_remaining_uses=20,
        )
    )

    status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["remaining_uses"] == 15
    assert "15 left" in status["quota_text"]


def test_zhuque_capture_session_status_uses_unique_tmp_file(monkeypatch, tmp_path):
    import importlib.util

    script_path = _zhuque_capture_tool_path()
    spec = importlib.util.spec_from_file_location("zhuque_capture_unique_status_tmp", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "SESSION_STATUS_FILE", tmp_path / "session_status.json")
    monkeypatch.setattr(module.os, "getpid", lambda: 4242)
    monkeypatch.setattr(module.time, "time_ns", lambda: 123456789)
    legacy_fixed_tmp = tmp_path / "session_status.tmp"
    legacy_fixed_tmp.write_text("stale", encoding="utf-8")

    module.write_session_status({"connected": True, "ready": True, "message": "ok"})

    status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert status["connected"] is True
    assert legacy_fixed_tmp.read_text(encoding="utf-8") == "stale"
    assert not (tmp_path / "session_status.json.4242.123456789.tmp").exists()


def test_zhuque_wechat_capture_reports_missing_playwright(monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    script_path = tmp_path / "zhuque_capture_window.py"
    script_path.write_text("print('capture')", encoding="utf-8")

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": False,
                "credential_file": str(script_path.parent / "creds_latest.json"),
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_zhuque_capture_script_path", lambda: script_path)
    monkeypatch.setattr(optimization_route.importlib.util, "find_spec", lambda name: None)

    result = optimization_route._start_zhuque_wechat_capture()

    assert result["status"] == "manual_required"
    assert "pip install playwright" in result["command"]
    assert "扫码授权页" in result["message"]


def test_zhuque_wechat_capture_reports_missing_playwright_browser(monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    script_path = tmp_path / "zhuque_capture_window.py"
    script_path.write_text("print('capture')", encoding="utf-8")

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": False,
                "credential_file": str(script_path.parent / "creds_latest.json"),
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_zhuque_capture_script_path", lambda: script_path)
    monkeypatch.setattr(optimization_route.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(optimization_route, "_zhuque_playwright_browser_ready", lambda: False)

    result = optimization_route._start_zhuque_wechat_capture()

    assert result["status"] == "manual_required"
    assert "playwright install chromium" in result["command"]
    assert "状态同步窗口" in result["message"]


def test_zhuque_api_parses_websocket_success_frame():
    from app.services.zhuque_api import parse_zhuque_websocket_result

    payload = json.dumps(
        {
            "status": "success",
            "confidence": 1.0,
            "labels_ratio": {"0": 1.0, "1": 0.0, "2": 0.0},
            "segment_labels": [
                {
                    "text": "检测文本",
                    "label": 0,
                    "conf": 0.9979,
                    "order": 1,
                    "position": [0, 4],
                }
            ],
            "content_type": 0,
            "availableUses": 18,
            "feedback_token": "token",
        },
        ensure_ascii=False,
    )

    result = parse_zhuque_websocket_result(payload, text_length=738)

    assert result == {
        "success": True,
        "rate": 100.0,
        "risk_rate": 100.0,
        "rate_label": "WebSocket检测结果",
        "labels_ratio": {"0": 1.0, "1": 0.0, "2": 0.0},
        "alert_text": "未发现明显的人工创作特征",
        "alert_title": "",
        "message": "",
        "remaining_uses": 18,
        "text_length": 738,
        "confidence": 1.0,
        "segment_labels": [
            {
                "text": "检测文本",
                "label": 0,
                "conf": 0.9979,
                "order": 1,
                "position": [0, 4],
                "position_format": "start_length",
                "position_start": 0,
                "position_length": 4,
                "position_end": 4,
            }
        ],
        "content_type": 0,
        "feedback_token": "token",
        "source": "websocket",
    }


def test_zhuque_api_parses_remaining_uses_from_button_text():
    from app.services.zhuque_api import normalize_zhuque_result

    result = normalize_zhuque_result(
        {
            "confidence": 0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "button_text": "Detect now(18 left)",
        },
        text_length=738,
        source="page_fallback",
    )

    assert result["remaining_uses"] == 18


def test_zhuque_api_does_not_parse_unknown_minus_one_as_quota():
    from app.services.zhuque_api import normalize_zhuque_result

    result = normalize_zhuque_result(
        {
            "confidence": 0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "quotaText": "remaining_uses: -1",
            "button_text": "检测后同步",
        },
        text_length=738,
        source="page_fallback",
    )

    assert result["remaining_uses"] == -1


def test_zhuque_api_invalid_request_is_not_zero_risk_success():
    from app.services.zhuque_api import normalize_zhuque_result

    result = normalize_zhuque_result(
        {
            "success": False,
            "message": "Invalid request",
            "labels_ratio": {},
            "rate": 0,
            "risk_rate": 0,
        },
        text_length=738,
        source="websocket_poll",
    )

    assert result["success"] is False
    assert result["message"] == "Invalid request"
    assert result["rate"] is None
    assert result["risk_rate"] is None
    assert result["labels_ratio"] == {}


def test_zhuque_api_credential_status_parses_remaining_uses_field(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "fp": "fp",
                "userName": "tester",
                "quotaText": "",
                "remainingUses": 17,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["ready"] is True
    assert status["remaining_uses"] == 17


def test_zhuque_api_session_status_logout_overrides_stale_quota(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "fp": "fp",
                "userName": "tester",
                "quotaText": "Detect now(16 left)",
                "remainingUses": 16,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "remaining_uses": -1,
                "message": "朱雀网页显示未登录",
                "updated_at": "2026-06-23T15:00:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["ready"] is False
    assert status["has_token"] is False
    assert status["remaining_uses"] == -1
    assert "未登录" in status["message"]


def test_zhuque_api_session_status_logged_out_preserves_live_free_quota(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "stale-token",
                "fp": "stale-fp",
                "userName": "old-user",
                "quotaText": "Detect now(99 left)",
                "remainingUses": 99,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "remaining_uses": 16,
                "quota_text": "Detect now(16 left)",
                "message": "朱雀网页显示未登录",
                "updated_at": "2026-06-23T15:05:00Z",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["ready"] is False
    assert status["has_token"] is False
    assert status["remaining_uses"] == 16
    assert status["button_enabled"] is True
    assert status["user_name"] == ""
    assert "16 left" in status["quota_text"]


def test_zhuque_api_login_placeholder_does_not_reuse_anonymous_quota(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "localStorage": {"fp": "anonymous-fp"},
                "userName": "Login",
                "quotaText": "Detect now(16 left)",
                "remainingUses": 16,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["has_anonymous_fp"] is True
    assert status["remaining_uses"] == -1
    assert status["button_enabled"] is True
    assert status["user_name"] == ""


def test_zhuque_api_loads_anonymous_fp_from_logged_out_session_status(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "persisted-fp",
                "remaining_uses": -1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["has_anonymous_fp"] is True
    assert status["remaining_uses"] == -1


def test_zhuque_api_seeds_page_probe_with_persisted_anonymous_fp(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "persisted-page-fp",
                "remaining_uses": -1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)
    monkeypatch.setattr(api, "_legacy_browser_state_file", lambda: tmp_path / "missing_legacy_state.json")

    state_file = tmp_path / "browser_state.json"
    assert api._browser_state_has_matrix_local_storage(state_file) is False
    assert api._anonymous_page_storage_state() == {
        "cookies": [],
        "origins": [
            {
                "origin": "https://matrix.tencent.com",
                "localStorage": [
                    {"name": "fp", "value": "persisted-page-fp"},
                    {"name": "language", "value": "en"},
                ],
            }
        ],
    }


def test_zhuque_api_uses_session_fp_before_legacy_browser_state_after_detection(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    user_dir = tmp_path / "user_5"
    legacy_dir = tmp_path / "legacy"
    user_dir.mkdir()
    legacy_dir.mkdir()
    creds_file = user_dir / "creds_latest.json"
    legacy_state_file = legacy_dir / "browser_state.json"
    (user_dir / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "anonymous_fp": "session-fp",
                "remaining_uses": -1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    legacy_state_file.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "legacy-fp"},
                            {"name": "language", "value": "en"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)
    monkeypatch.setattr(api, "_legacy_browser_state_file", lambda: legacy_state_file)

    state = api._anonymous_page_storage_state()

    assert state["origins"][0]["localStorage"][0] == {"name": "fp", "value": "session-fp"}


def test_zhuque_api_uses_current_browser_state_before_session_fp(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    user_dir = tmp_path / "user_5"
    legacy_dir = tmp_path / "legacy"
    user_dir.mkdir()
    legacy_dir.mkdir()
    creds_file = user_dir / "creds_latest.json"
    legacy_state_file = legacy_dir / "browser_state.json"
    (user_dir / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "anonymous_fp": "session-fp",
                "remaining_uses": 3,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (user_dir / "browser_state.json").write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "current-browser-fp"},
                            {"name": "language", "value": "en"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    legacy_state_file.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "legacy-fp"},
                            {"name": "language", "value": "en"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)
    monkeypatch.setattr(api, "_legacy_browser_state_file", lambda: legacy_state_file)

    state = api._anonymous_page_storage_state()

    assert state["origins"][0]["localStorage"][0] == {"name": "fp", "value": "current-browser-fp"}


def test_zhuque_api_ignores_legacy_browser_state_with_token(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    user_dir = tmp_path / "user_5"
    legacy_dir = tmp_path / "legacy"
    user_dir.mkdir()
    legacy_dir.mkdir()
    creds_file = user_dir / "creds_latest.json"
    legacy_state_file = legacy_dir / "browser_state.json"
    (user_dir / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "anonymous_fp": "session-fp",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    legacy_state_file.write_text(
        json.dumps(
            {
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "legacy-fp"},
                            {"name": "aiGenAccessToken", "value": "token"},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)
    monkeypatch.setattr(api, "_legacy_browser_state_file", lambda: legacy_state_file)

    state = api._anonymous_page_storage_state()

    assert state["origins"][0]["localStorage"][0] == {"name": "fp", "value": "session-fp"}


def test_zhuque_api_prefers_existing_browser_state_for_page_probe(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "anonymous_fp": "persisted-page-fp",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    state_file = tmp_path / "browser_state.json"
    state_file.write_text(
        json.dumps(
            {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "browser-state-fp"},
                            {"name": "language", "value": "en"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)

    assert api._browser_state_has_matrix_local_storage(state_file) is True
    assert api._local_storage_from_browser_state(json.loads(state_file.read_text(encoding="utf-8")))["fp"] == "browser-state-fp"


def test_zhuque_api_logged_out_session_status_overrides_stale_token_for_peek(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "stale-token",
                "fp": "stale-fp",
                "userName": "old-user",
                "remainingUses": 99,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "logged-out-fp",
                "remaining_uses": -1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    api = ZhuqueAPI(credentials_file=creds_file)
    sent_payloads = []

    class FakeWS:
        async def send(self, payload):
            sent_payloads.append(json.loads(payload))

        async def recv(self):
            return json.dumps({"availableUses": 12}, ensure_ascii=False)

        async def close(self):
            pass

    async def fake_connect(headers):
        return FakeWS()

    monkeypatch.setattr(api, "_connect", fake_connect)

    remaining = asyncio.run(api.peek_remaining_uses(allow_anonymous=True))

    assert remaining == 12
    assert sent_payloads[0] == {"fp": "logged-out-fp"}


def test_zhuque_api_loads_anonymous_fp_from_browser_state_without_token(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    (tmp_path / "browser_state.json").write_text(
        json.dumps(
            {
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "state-fp"},
                            {"name": "language", "value": "en"},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["has_anonymous_fp"] is True
    assert status["remaining_uses"] == -1


def test_zhuque_api_ignores_browser_state_fp_when_token_is_present(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    (tmp_path / "browser_state.json").write_text(
        json.dumps(
            {
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "fp", "value": "state-fp"},
                            {"name": "aiGenAccessToken", "value": "stale-token"},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = ZhuqueAPI(credentials_file=creds_file).credential_status()

    assert status["connected"] is False
    assert status["has_token"] is False
    assert status["has_anonymous_fp"] is False
    assert status["remaining_uses"] == -1


def test_zhuque_api_missing_access_token_uses_anonymous_fp_before_page_fallback(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "localStorage": {"fp": "anonymous-fp"},
                "userName": "Login",
                "quotaText": "Detect now(16 left)",
                "remainingUses": 16,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    api = ZhuqueAPI(credentials_file=creds_file)
    calls = []
    sent_payloads = []

    class FakeWS:
        async def send(self, payload):
            sent_payloads.append(json.loads(payload))

        async def recv(self):
            await asyncio.sleep(0)
            return json.dumps({"availableUses": 16}, ensure_ascii=False)

        async def close(self):
            pass

    async def fake_connect(headers):
        return FakeWS()

    async def fake_detect_with_page(text, timeout, *, reason="", anonymous=False):
        calls.append({"text": text, "timeout": timeout, "reason": reason, "anonymous": anonymous})
        return {
            "success": True,
            "rate": 0.0,
            "risk_rate": 0.0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "remaining_uses": -1,
            "text_length": len(text),
            "source": "page_fallback",
        }

    monkeypatch.setattr(api, "_connect", fake_connect)
    monkeypatch.setattr(api, "_detect_with_page", fake_detect_with_page)

    remaining = asyncio.run(api.peek_remaining_uses(allow_anonymous=True))

    assert remaining == 16
    assert sent_payloads[0] == {"fp": "anonymous-fp"}
    assert calls == []


def test_zhuque_api_page_injection_uses_raw_local_storage(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "top-level-token",
                "localStorage": {
                    "aiGenAccessToken": json.dumps({"value": "storage-token"}, ensure_ascii=False),
                    "fp": "captured-fp",
                    "language": "en",
                },
                "userName": "tester",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    api = ZhuqueAPI(credentials_file=creds_file)
    creds = api.load_credentials(refresh=True)
    local_storage = api._page_local_storage_from_credentials(creds)

    assert json.loads(local_storage["aiGenAccessToken"])["value"] == "storage-token"
    assert local_storage["fp"] == "captured-fp"
    assert local_storage["language"] == "en"


def test_zhuque_api_treats_websocket_label_one_as_human():
    from app.services.zhuque_api import parse_zhuque_websocket_result

    payload = json.dumps(
        {
            "status": "success",
            "confidence": 0.0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "availableUses": 18,
        },
        ensure_ascii=False,
    )

    result = parse_zhuque_websocket_result(payload, text_length=738)

    assert result["rate"] == 0.0
    assert result["alert_text"] == "人工创作特征较明显"


def test_zhuque_api_extracts_segment_labels_from_poll_result_envelope():
    from app.services.zhuque_api import parse_zhuque_websocket_result

    payload = json.dumps(
        {
            "status": "success",
            "data": json.dumps(
                {
                    "confidence": 100,
                    "labels_ratio": {"0": 1.0, "1": 0.0, "2": 0.0},
                    "segment_labels": [
                        {
                            "text": "朱雀原始段落",
                            "label": 0,
                            "conf": 0.997,
                            "order": 1,
                            "position": [12, 6],
                        }
                    ],
                    "availableUses": 16,
                },
                ensure_ascii=False,
            ),
        },
        ensure_ascii=False,
    )

    result = parse_zhuque_websocket_result(payload, text_length=738)

    assert result["segment_labels"] == [
        {
            "text": "朱雀原始段落",
            "label": 0,
            "conf": 0.997,
            "order": 1,
            "position": [12, 6],
            "position_format": "start_length",
            "position_start": 12,
            "position_length": 6,
            "position_end": 18,
        }
    ]
    assert result["remaining_uses"] == 16


def test_zhuque_api_page_payload_merge_prefers_segment_labels_over_card_summary():
    from app.services.zhuque_api import _merge_zhuque_page_payload, normalize_zhuque_result

    observed_payloads = [
        {
            "confidence": 35.36,
            "labels_ratio": {"0": 0.6464, "1": 0.0085, "2": 0.3451},
            "segment_labels": [
                {
                    "text": "真实朱雀段落",
                    "label": 0,
                    "conf": 0.996,
                    "order": 1,
                    "position": [0, 6],
                }
            ],
            "feedback_token": "real-token",
            "content_type": 0,
        }
    ]

    payload = _merge_zhuque_page_payload(
        observed_payloads=observed_payloads,
        vue={
            "rate": 35.36,
            "rateLabel": "AI content ratio",
            "labelsRatio": {"0": 0.6464, "1": 0.0085, "2": 0.3451},
            "msg": "",
        },
        page_state={
            "button_text": "Detect now(16 left)",
            "alert": "Strong human creation Report",
            "alert_title": "Notice",
        },
    )
    result = normalize_zhuque_result(payload, text_length=31543, source="page_fallback")

    assert result["segment_labels"][0]["text"] == "真实朱雀段落"
    assert result["segment_labels"][0]["position_end"] == 6
    assert result["feedback_token"] == "real-token"
    assert result["content_type"] == 0
    assert result["remaining_uses"] == 16
    assert result["source"] == "page_fallback"


def test_zhuque_api_page_observed_payload_does_not_require_vue_dom_state():
    from app.services.zhuque_api import _normalize_zhuque_observed_page_result

    result = _normalize_zhuque_observed_page_result(
        observed_payloads=[
            {
                "confidence": 64.5,
                "labels_ratio": {"0": 0.645, "1": 0.2, "2": 0.155},
                "segment_labels": [
                    {
                        "text": "朱雀命中段落",
                        "label": 0,
                        "conf": 0.99,
                        "position": [0, 6],
                    }
                ],
            }
        ],
        page_state={
            "button_text": "Detect now(19 left)",
            "alert": "",
            "alert_title": "",
        },
        text_length=805,
    )

    assert result is not None
    assert result["success"] is True
    assert result["rate"] == 64.5
    assert result["remaining_uses"] == 19
    assert result["page_result_payload_count"] == 1
    assert result["page_result_has_segment_labels"] is True
    assert result["segment_labels"][0]["position_end"] == 6


def test_zhuque_api_visible_captcha_wait_budget_is_configurable(monkeypatch):
    from app.services.zhuque_api import (
        _zhuque_detect_failure_retryable,
        _zhuque_visible_captcha_wait_seconds,
    )

    monkeypatch.delenv("ZHUQUE_VISIBLE_CAPTCHA_WAIT_SECONDS", raising=False)
    assert _zhuque_visible_captcha_wait_seconds() == 600.0

    monkeypatch.setenv("ZHUQUE_VISIBLE_CAPTCHA_WAIT_SECONDS", "900")
    assert _zhuque_visible_captcha_wait_seconds() == 900.0

    monkeypatch.setenv("ZHUQUE_VISIBLE_CAPTCHA_WAIT_SECONDS", "bad")
    assert _zhuque_visible_captcha_wait_seconds() == 600.0

    monkeypatch.setenv("ZHUQUE_VISIBLE_CAPTCHA_WAIT_SECONDS", "-1")
    assert _zhuque_visible_captcha_wait_seconds() == 0.0

    assert _zhuque_detect_failure_retryable("检测按钮被禁用，已重开页面重试")
    assert not _zhuque_detect_failure_retryable("次数用尽")


def test_zhuque_api_infers_score_from_segment_labels_when_summary_is_missing():
    from app.services.zhuque_api import normalize_zhuque_result

    result = normalize_zhuque_result(
        {
            "segment_labels": [
                {"text": "AI段落", "label": 0, "conf": 0.99, "position": [0, 200]},
                {"text": "可疑段落", "label": 2, "conf": 0.88, "position": [400, 100]},
            ],
            "button_text": "Detect now(18 left)",
        },
        text_length=1000,
        source="page_fallback",
    )

    assert result["success"] is True
    assert result["score_inferred_from_segment_labels"] is True
    assert result["labels_ratio"] == {"0": 0.2, "1": 0.7, "2": 0.1}
    assert result["rate"] == 20.0
    assert result["risk_rate"] == 20.0
    assert result["remaining_uses"] == 18
    assert result["segment_labels"][0]["position_end"] == 200


def test_zhuque_api_page_observed_labels_wait_while_captcha_visible():
    from app.services.zhuque_api import _normalize_zhuque_observed_page_result

    result = _normalize_zhuque_observed_page_result(
        observed_payloads=[
            {
                "segment_labels": [
                    {"text": "验证码期间段落", "label": 0, "position": [0, 10]},
                ]
            }
        ],
        page_state={
            "captcha_visible": True,
            "captcha_text": "tcaptcha Verification Code",
            "button_text": "Detecting",
            "alert": "",
            "alert_title": "Detecting...",
        },
        text_length=500,
    )

    assert result is None


def test_zhuque_api_page_observed_score_payload_merges_latest_segment_labels():
    from app.services.zhuque_api import _normalize_zhuque_observed_page_result

    result = _normalize_zhuque_observed_page_result(
        observed_payloads=[
            {
                "segment_labels": [
                    {"text": "真实朱雀段落", "label": 0, "position": [10, 6]},
                ]
            },
            {
                "confidence": 0.64,
                "labels_ratio": {"0": 0.64, "1": 0.36, "2": 0.0},
            },
        ],
        page_state={
            "button_text": "Detect now(17 left)",
            "alert": "",
            "alert_title": "",
        },
        text_length=1000,
    )

    assert result is not None
    assert result["success"] is True
    assert result["rate"] == 64.0
    assert result["segment_labels"][0]["position_end"] == 16
    assert result["remaining_uses"] == 17


def test_zhuque_api_page_observed_empty_segment_labels_are_not_terminal():
    from app.services.zhuque_api import (
        _extract_zhuque_terminal_payload,
        _normalize_zhuque_observed_page_result,
    )

    assert _extract_zhuque_terminal_payload({"segment_labels": []}) is None

    result = _normalize_zhuque_observed_page_result(
        observed_payloads=[
            {"segment_labels": []},
            {"segment_labels": [], "remainingUses": 20},
        ],
        page_state={
            "button_text": "Detect now(20 left)",
            "alert": "",
            "alert_title": "",
        },
        text_length=871,
    )

    assert result is None


def test_zhuque_api_connects_to_configured_detect_cdp_endpoint(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    calls = []

    class FakeContext:
        pass

    class FakeBrowser:
        def __init__(self, context):
            self.contexts = [context]

    class FakeChromium:
        def __init__(self, context):
            self.context = context

        async def connect_over_cdp(self, endpoint):
            calls.append(endpoint)
            return FakeBrowser(self.context)

    class FakePlaywright:
        def __init__(self, context):
            self.chromium = FakeChromium(context)

    class FakePlaywrightManager:
        def __init__(self, context):
            self.context = context

        async def start(self):
            return FakePlaywright(self.context)

    context = FakeContext()
    monkeypatch.setenv("ZHUQUE_DETECT_CDP_ENDPOINT", "http://127.0.0.1:9222/")
    api = ZhuqueAPI(credentials_file=tmp_path / "creds_latest.json")

    result = asyncio.run(api._ensure_cdp_context(lambda: FakePlaywrightManager(context), anonymous=False))

    assert result is context
    assert calls == ["http://127.0.0.1:9222"]
    assert api._browser_external_context is True
    assert api._browser_headless is False
    assert api._browser_cdp_endpoint == "http://127.0.0.1:9222"


def test_zhuque_api_prefers_auto_system_browser_when_visible(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(credentials_file=tmp_path / "creds_latest.json")
    monkeypatch.delenv("ZHUQUE_DETECT_CDP_ENDPOINT", raising=False)
    monkeypatch.setenv("ZHUQUE_DETECT_HEADLESS", "false")
    monkeypatch.setenv("ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER", "true")
    monkeypatch.setattr(api, "_ensure_system_browser_cdp_endpoint", lambda: "http://127.0.0.1:9224")

    assert api._preferred_detect_cdp_endpoint() == "http://127.0.0.1:9224"

    monkeypatch.setenv("ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER", "false")
    assert api._preferred_detect_cdp_endpoint() == ""


def test_zhuque_api_focuses_existing_detect_page(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    class FakePage:
        def __init__(self, url):
            self.url = url
            self.focused = False

        def is_closed(self):
            return False

        async def bring_to_front(self):
            self.focused = True

    class FakeContext:
        def __init__(self, pages):
            self.pages = pages

    blank_page = FakePage("about:blank")
    detect_page = FakePage("https://matrix.tencent.com/ai-detect/")
    api = ZhuqueAPI(credentials_file=tmp_path / "creds_latest.json")
    api._browser_headless = False
    api._browser_context = FakeContext([blank_page, detect_page])

    result = asyncio.run(api.focus_cached_page())

    assert result["available"] is True
    assert result["url"] == "https://matrix.tencent.com/ai-detect/"
    assert detect_page.focused is True
    assert api._cached_page is detect_page


def test_zhuque_api_detects_real_page_captcha_challenge():
    from app.services.zhuque_api import _captcha_required_zhuque_result, _zhuque_page_captcha_detected

    assert _zhuque_page_captcha_detected(
        {
            "captcha_visible": True,
            "captcha_text": "Refreshing too often Verification Code will refresh in 2 sec.",
            "captcha_iframe_src": "https://captcha.gtimg.com/static/template/drag_ele.html",
            "button_text": "Detecting",
        }
    )
    assert _zhuque_page_captcha_detected(
        {
            "captcha_visible": False,
            "captcha_text": "Choose all similar images",
            "button_text": "Detecting",
        }
    )
    assert not _zhuque_page_captcha_detected(
        {
            "captcha_visible": False,
            "captcha_text": "",
            "button_text": "Detect now(20 left)",
        }
    )
    result = _captcha_required_zhuque_result("朱雀触发腾讯验证码", 871)
    assert result["success"] is False
    assert result["error_code"] == "zhuque_captcha_required"
    assert result["source"] == "page_fallback"
    assert result["manual_verification_required"] is True
    assert result["manual_verification_mode"] == "local_window"
    assert result["manual_verification_action"] == "open_zhuque_local_window"
    assert result["manual_verification_label"] == "打开朱雀验证窗口"


def test_zhuque_api_ignores_non_terminal_websocket_frames():
    from app.services.zhuque_api import parse_zhuque_websocket_result

    assert parse_zhuque_websocket_result("not-json", text_length=1000) is None
    assert parse_zhuque_websocket_result('{"status":"waiting","remaining":0}', text_length=1000) is None
    assert parse_zhuque_websocket_result('{"code":"1","msg":"OK"}', text_length=1000) is None


def test_zhuque_api_valid_token_uses_real_page_instead_of_ws_bypass(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "localStorage": {"aiGenAccessToken": "token"},
                "userName": "tester",
                "remainingUses": 20,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    api = ZhuqueAPI(credentials_file=creds_file)
    page_fallback_calls = []

    async def fake_connect(headers):
        raise AssertionError("detect() must not use the obsolete WebSocket CAPTCHA bypass")

    async def fake_detect_with_page(text, timeout, *, reason="", anonymous=False):
        page_fallback_calls.append({"text": text, "timeout": timeout, "reason": reason, "anonymous": anonymous})
        return {
            "success": True,
            "rate": 0.0,
            "risk_rate": 0.0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "remaining_uses": 19,
            "text_length": len(text),
            "source": "page_fallback",
        }

    monkeypatch.setattr(api, "_connect", fake_connect)
    monkeypatch.setattr(api, "_detect_with_page", fake_detect_with_page)

    result = asyncio.run(api.detect("汉" * 500, timeout=60.0))

    assert result["success"] is True
    assert result["source"] == "page_fallback"
    assert result["remaining_uses"] == 19
    assert page_fallback_calls
    assert page_fallback_calls[0]["anonymous"] is False
    assert "验证码绕过已失效" in page_fallback_calls[0]["reason"]


def test_zhuque_api_short_text_returns_failure_without_page(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(credentials_file=tmp_path / "creds_latest.json")

    result = asyncio.run(api.detect("太短"))

    assert result["success"] is False
    assert "文本长度不足" in result["message"]
    assert result["text_length"] == 2


def test_zhuque_api_page_fallback_retries_timeout(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "localStorage": {"aiGenAccessToken": "token"},
                "userName": "tester",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    api = ZhuqueAPI(credentials_file=creds_file)
    calls = []

    async def fake_detect_with_page(text, timeout, *, reason="", anonymous=False):
        calls.append({"text": text, "timeout": timeout, "reason": reason, "anonymous": anonymous})
        if len(calls) == 1:
            return {
                "success": False,
                "message": "朱雀真实页面检测超时 (60.0s)",
                "remaining_uses": -1,
                "text_length": len(text),
                "source": "page_fallback",
            }
        return {
            "success": True,
            "rate": 0.0,
            "risk_rate": 0.0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "remaining_uses": 18,
            "text_length": len(text),
            "source": "page_fallback",
        }

    monkeypatch.setattr(api, "_detect_with_page", fake_detect_with_page)

    result = asyncio.run(api.detect("汉" * 500, timeout=60.0))

    assert result["success"] is True
    assert result["remaining_uses"] == 18
    assert len(calls) == 2
    assert calls[0]["anonymous"] is False
    assert api._last_detect_failed is False


def test_zhuque_api_page_fallback_retries_disabled_button(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(
        json.dumps(
            {
                "access_token": "token",
                "localStorage": {"aiGenAccessToken": "token"},
                "userName": "tester",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    api = ZhuqueAPI(credentials_file=creds_file)
    calls = []

    async def fake_detect_with_page(text, timeout, *, reason="", anonymous=False):
        calls.append({"text": text, "timeout": timeout, "reason": reason, "anonymous": anonymous})
        if len(calls) == 1:
            return {
                "success": False,
                "message": "朱雀真实页面检测临时失败：检测按钮被禁用，已重开页面重试",
                "remaining_uses": -1,
                "text_length": len(text),
                "source": "page_fallback",
            }
        return {
            "success": True,
            "rate": 12.0,
            "risk_rate": 12.0,
            "labels_ratio": {"0": 0.12, "1": 0.88, "2": 0.0},
            "remaining_uses": 16,
            "text_length": len(text),
            "source": "page_fallback",
        }

    monkeypatch.setattr(api, "_detect_with_page", fake_detect_with_page)

    result = asyncio.run(api.detect("汉" * 500, timeout=60.0))

    assert result["success"] is True
    assert result["rate"] == 12.0
    assert len(calls) == 2
    assert api._last_detect_failed is False


def test_zhuque_api_missing_credentials_attempts_anonymous_page_fallback(monkeypatch, tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(credentials_file=tmp_path / "creds_latest.json")
    calls = []

    async def fake_detect_with_page(text, timeout, *, reason="", anonymous=False):
        calls.append({"text": text, "timeout": timeout, "reason": reason, "anonymous": anonymous})
        return {
            "success": True,
            "rate": 0.0,
            "risk_rate": 0.0,
            "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            "remaining_uses": -1,
            "text_length": len(text),
            "source": "page_fallback",
        }

    monkeypatch.setattr(api, "_detect_with_page", fake_detect_with_page)

    result = asyncio.run(api.detect("汉" * 500))

    assert result["success"] is True
    assert result["source"] == "page_fallback"
    assert calls
    assert "未找到可用 token" in calls[0]["reason"]
    assert calls[0]["anonymous"] is True


def test_zhuque_api_classify_uses_websocket_label_mapping():
    from app.services.zhuque_api import ZhuqueAPI

    async def classify_with(raw_result):
        api = ZhuqueAPI()

        async def fake_detect(text):
            return raw_result

        api.detect = fake_detect
        return await api.classify("测试文本" * 200)

    ai_result = asyncio.run(
        classify_with(
            {
                "success": True,
                "rate": 100.0,
                "alert_text": "",
                "labels_ratio": {"0": 1.0, "1": 0.0, "2": 0.0},
            }
        )
    )
    human_result = asyncio.run(
        classify_with(
            {
                "success": True,
                "rate": 0.0,
                "alert_text": "",
                "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
            }
        )
    )

    assert ai_result["verdict"] == "AI_generated"
    assert ai_result["verdict_label"] == "AI生成"
    assert human_result["verdict"] == "human_written"
    assert human_result["verdict_label"] == "人工编写"


def test_zhuque_browser_start_endpoint_defaults_to_remote_qr_per_user(client, monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    credential_file = str(tmp_path / "users" / f"user_{user_id}" / "creds_latest.json")
    calls = []

    class FakeRemoteLoginService:
        async def start(self, current_user_id):
            calls.append(current_user_id)
            return {
                "session_id": "remote-session-1",
                "status": "qr_ready",
                "auth_mode": "headless_api",
                "login_mode": "remote_wechat_qr",
                "credential_file": credential_file,
                "connected": False,
                "ready": False,
                "has_token": False,
                "remaining_uses": -1,
                "user_name": "",
                "quota_text": "",
                "qr_image_data": "data:image/png;base64,abc",
                "expires_at": "2026-06-24T00:00:00Z",
                "message": "请使用微信扫描二维码登录朱雀",
            }

    class FakeZhuqueService:
        def reset_user(self, current_user_id):
            calls.append(("reset", current_user_id))

    monkeypatch.setattr(optimization_route, "zhuque_remote_login_service", FakeRemoteLoginService())
    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.post(
        "/api/optimization/zhuque/browser/start",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "qr_ready"
    assert body["login_mode"] == "remote_wechat_qr"
    assert body["credential_file"] == credential_file
    assert body["session_id"] == "remote-session-1"
    assert body["qr_image_data"].startswith("data:image/png;base64,")
    assert body["sync_session"] is True
    assert calls == [user_id, ("reset", user_id)]


def test_zhuque_browser_start_endpoint_reuses_existing_detection_window(client, monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    credential_file = str(tmp_path / "creds_latest.json")
    calls = []

    class FakeUserZhuqueService:
        async def focus_detection_window(self):
            calls.append("focus")
            return {
                "available": True,
                "credential_file": credential_file,
                "url": "https://matrix.tencent.com/ai-detect/",
            }

    class FakeZhuqueService:
        def for_user(self, current_user_id):
            calls.append(("for_user", current_user_id))
            return FakeUserZhuqueService()

        def reset_user(self, current_user_id):
            calls.append(("reset", current_user_id))

    def fail_start_zhuque_wechat_capture(*, sync_session=True, user=None):
        raise AssertionError("local-window capture must not launch when detect window is reusable")

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())
    monkeypatch.setattr(optimization_route, "_start_zhuque_wechat_capture", fail_start_zhuque_wechat_capture)

    response = client.post(
        "/api/optimization/zhuque/browser/start?mode=local_window",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reused"
    assert body["credential_file"] == credential_file
    assert "复用当前朱雀检测窗口" in body["message"]
    assert calls == [("for_user", user_id), "focus"]


def test_zhuque_local_open_endpoint_reuses_or_launches_local_browser(client, monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    calls = []

    class FakeLocalTransport:
        async def open_page(self, *, open_capture=None):
            calls.append("open_page")
            launched = open_capture()
            calls.append(launched["status"])
            return {
                "status": launched["status"],
                "transport": "local_browser",
                "auth_mode": "local_browser",
                "login_mode": "local_browser",
                "credential_file": launched["credential_file"],
                "sync_session": launched["sync_session"],
                "command": launched["command"],
                "message": "已打开本机朱雀页面",
                "connected": False,
                "ready": False,
                "has_token": False,
                "has_anonymous_fp": False,
                "remaining_uses": -1,
                "button_enabled": True,
                "user_name": "",
                "quota_text": "",
            }

    def fake_local_transport(current_user):
        assert current_user.id == user_id
        return FakeLocalTransport()

    def fake_start_zhuque_wechat_capture(*, sync_session=True, user=None):
        assert user.id == user_id
        return {
            "status": "started",
            "credential_file": str(tmp_path / "creds_latest.json"),
            "sync_session": sync_session,
            "command": "python package/backend/app/tools/zhuque_capture_window.py --sync-session",
            "message": "legacy launcher",
        }

    class FakeZhuqueService:
        def reset_user(self, current_user_id):
            calls.append(("reset", current_user_id))

    monkeypatch.setattr(optimization_route, "_zhuque_local_transport_for_user", fake_local_transport)
    monkeypatch.setattr(optimization_route, "_start_zhuque_wechat_capture", fake_start_zhuque_wechat_capture)
    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.post(
        "/api/optimization/zhuque/local/open",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "started"
    assert body["transport"] == "local_browser"
    assert body["login_mode"] == "local_browser"
    assert body["sync_session"] is True
    assert body["command"] == "python package/backend/app/tools/zhuque_capture_window.py --sync-session"
    assert calls == ["open_page", ("reset", user_id), "started"]


def test_zhuque_api_quota_probe_reuses_visible_page_without_headless_browser(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(debug=False, credentials_file=tmp_path / "creds_latest.json")
    calls = []

    class FakePage:
        url = "https://matrix.tencent.com/ai-detect/"

        async def evaluate(self, script, *args):
            calls.append("evaluate")
            return {
                "quota_texts": ["Detect now(20 left)"],
                "submit_button_text": "Detect now(20 left)",
                "button_enabled": True,
                "page_found": True,
                "has_token": True,
                "logged_in": True,
                "user_name": "木木",
            }

        async def wait_for_timeout(self, timeout_ms):
            calls.append(("wait", timeout_ms))

    async def fake_open_detect_page():
        calls.append("open_detect_page")
        api._cached_page = FakePage()
        return {"available": True, "status": "opened"}

    monkeypatch.setattr(api, "open_detect_page", fake_open_detect_page)

    result = asyncio.run(api._peek_quota_status_with_page(timeout=1.0))

    assert result["remaining_uses"] == 20
    assert result["button_enabled"] is True
    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    assert calls[0] == "open_detect_page"


def test_zhuque_api_logout_clears_saved_files_and_live_context(tmp_path):
    from app.services.zhuque_api import ZhuqueAPI

    creds_file = tmp_path / "creds_latest.json"
    creds_file.write_text(json.dumps({"access_token": "token", "localStorage": {"aiGenAccessToken": "token"}}), encoding="utf-8")
    (tmp_path / "browser_state.json").write_text(
        json.dumps({"origins": [{"origin": "https://matrix.tencent.com", "localStorage": [{"name": "aiGenAccessToken", "value": "token"}]}]}),
        encoding="utf-8",
    )
    dedicated_profile = tmp_path / "ZhuqueDetectBrowserProfile"
    dedicated_profile.mkdir()
    (dedicated_profile / "token-cache").write_text("token", encoding="utf-8")

    class FakePage:
        url = "https://matrix.tencent.com/ai-detect/"
        evaluated = False

        def is_closed(self):
            return False

        async def evaluate(self, script, *args):
            self.evaluated = True
            return None

    class FakeContext:
        def __init__(self):
            self.page = FakePage()
            self.pages = [self.page]
            self.cookies_cleared = False
            self.closed = False

        async def clear_cookies(self):
            self.cookies_cleared = True

        async def close(self):
            self.closed = True

    api = ZhuqueAPI(debug=False, credentials_file=creds_file)
    api._find_detect_browser_executable = lambda: "/usr/bin/google-chrome"
    api._detect_system_browser_profile_dir = lambda executable: str(dedicated_profile)
    fake_context = FakeContext()
    api._browser_context = fake_context

    payload = asyncio.run(api.logout_saved_credentials())

    assert payload["connected"] is False
    assert payload["has_token"] is False
    assert payload["cleared_live_context"] is True
    assert fake_context.page.evaluated is True
    assert fake_context.cookies_cleared is True
    assert fake_context.closed is True
    assert not creds_file.exists()
    assert not (tmp_path / "browser_state.json").exists()
    assert not dedicated_profile.exists()
    status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert status["connected"] is False
    assert status["has_token"] is False


def test_zhuque_api_quota_probe_persists_visible_login_credentials(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(debug=False, credentials_file=tmp_path / "creds_latest.json")

    class FakeContext:
        async def cookies(self):
            return [{"name": "session", "value": "cookie-value", "domain": "matrix.tencent.com", "path": "/"}]

        async def storage_state(self):
            return {
                "cookies": [],
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [
                            {"name": "aiGenAccessToken", "value": json.dumps({"value": "token-from-page"})},
                            {"name": "fp", "value": "fp-from-page"},
                        ],
                    }
                ],
            }

    class FakePage:
        url = "https://matrix.tencent.com/ai-detect/"

        def __init__(self):
            self.context = FakeContext()
            self.evaluate_calls = 0

        async def evaluate(self, script, *args):
            self.evaluate_calls += 1
            if self.evaluate_calls == 1:
                return {
                    "quota_texts": ["Detect now(17 left)"],
                    "submit_button_text": "Detect now(17 left)",
                    "button_enabled": True,
                    "page_found": True,
                    "has_token": True,
                    "access_token_present": True,
                    "logged_in": True,
                    "user_name": "木木",
                }
            return {
                "localStorage": {
                    "aiGenAccessToken": json.dumps({"value": "token-from-page"}),
                    "fp": "fp-from-page",
                },
                "userName": "木木",
                "quotaText": "Detect now(17 left)",
                "submitButtonText": "Detect now(17 left)",
                "url": "https://matrix.tencent.com/ai-detect/",
                "timestamp": "2026-07-08T06:40:34.000Z",
            }

        async def wait_for_timeout(self, timeout_ms):
            return None

    async def fake_open_detect_page():
        api._cached_page = FakePage()
        return {"available": True, "status": "opened"}

    monkeypatch.setattr(api, "open_detect_page", fake_open_detect_page)

    result = asyncio.run(api._peek_quota_status_with_page(timeout=1.0))

    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    assert api.credentials_file.exists()
    status = api.credential_status()
    assert status["has_token"] is True
    assert status["user_name"] == "木木"
    assert status["remaining_uses"] == 17
    assert (tmp_path / "browser_state.json").exists()


def test_zhuque_extracts_account_name_from_zhuque_body_preview():
    from app.services.zhuque_api import _extract_account_name_from_body_preview

    preview = """Zhuque AI Detection Assistant
AI Detection Assistant
任意用户123
Free AI Detection Assistant
Text
Image/Video"""

    assert _extract_account_name_from_body_preview(preview) == "任意用户123"


def test_zhuque_does_not_treat_chinese_product_title_as_account_name():
    from app.services.zhuque_api import _extract_account_name_from_body_preview

    preview = """朱雀AI检测助手
AI检测助手
免费AI检测助手
文本
图片/视频
我可以免费使用朱雀AI检测吗？"""

    assert _extract_account_name_from_body_preview(preview) == ""


def test_zhuque_quota_payload_logged_in_flag_without_token_is_not_auth():
    from app.services.zhuque_service import ZhuqueService

    service = ZhuqueService(owner_label="test")
    status = service._quota_status_from_payload(
        {
            "remaining_uses": 3,
            "button_enabled": True,
            "logged_in": True,
            "user_name": "朱雀AI检测助手",
        }
    )

    assert status["has_token"] is False


def test_zhuque_quota_exhausted_state_detects_zero_attempts():
    from app.services.zhuque_api import _zhuque_quota_exhausted_state

    assert _zhuque_quota_exhausted_state({"button_text": "Detect now(0 left)"}) is True
    assert _zhuque_quota_exhausted_state({"alert": "今日剩余 0 次"}) is True
    assert _zhuque_quota_exhausted_state({"message": "朱雀剩余次数不足"}) is True
    assert _zhuque_quota_exhausted_state({"button_text": "Detecting..."}) is False


def test_zhuque_ignores_stale_result_poll_from_cached_page():
    from app.services.zhuque_api import _zhuque_result_response_belongs_to_current_click

    click_ms = 1_800_000
    assert _zhuque_result_response_belongs_to_current_click(
        "https://matrix.tencent.com/user/detect/result?cos=old&startTime=1700000",
        click_ms,
    ) is False
    assert _zhuque_result_response_belongs_to_current_click(
        "https://matrix.tencent.com/user/detect/result?cos=current&startTime=1785001",
        click_ms,
    ) is True
    assert _zhuque_result_response_belongs_to_current_click(
        "https://matrix.tencent.com/user/detect/result?cos=no-start-time",
        click_ms,
    ) is True


def test_zhuque_service_detect_fails_fast_when_cached_quota_zero(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    class FakeAPI:
        credentials_file = tmp_path / "creds_latest.json"
        detect_called = False

        def credential_status(self):
            return {
                "has_token": False,
                "connected": False,
                "ready": True,
                "remaining_uses": 0,
                "button_enabled": False,
                "credential_file": str(self.credentials_file),
            }

        async def peek_quota_status(self, timeout=3.0, allow_anonymous=False):
            return {
                "remaining_uses": 0,
                "button_enabled": False,
                "page_found": True,
                "has_token": False,
                "quota_text": "Detect now(0 left)",
            }

        async def detect(self, text, timeout=60.0):
            self.detect_called = True
            return {"success": True, "remaining_uses": 0}

    service = ZhuqueService(credentials_file=tmp_path / "creds_latest.json", owner_label="test")
    fake_api = FakeAPI()
    service.api = fake_api
    service._ready = True

    result = asyncio.run(service.detect("测试文本" * 200))

    assert result["success"] is False
    assert result["remaining_uses"] == 0
    assert "剩余次数不足" in result["message"]
    assert fake_api.detect_called is False


def test_zhuque_api_peek_quota_status_prefers_visible_login_page_over_cached_anonymous_fp(tmp_path, monkeypatch):
    from app.services.zhuque_api import ZhuqueAPI

    api = ZhuqueAPI(debug=False, credentials_file=tmp_path / "creds_latest.json")
    (tmp_path / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "anonymous-fp",
                "remaining_uses": 4,
                "quota_text": "剩余 4 次",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        api,
        "_peek_quota_status_with_page",
        lambda timeout=3.0: asyncio.sleep(
            0,
            result={
                "remaining_uses": 20,
                "button_enabled": True,
                "page_found": True,
                "has_token": True,
                "user_name": "木木",
                "quota_text": "Detect now(20 left)",
            },
        ),
    )

    async def fail_ws_peek(*args, **kwargs):
        raise AssertionError("anonymous fp WebSocket quota must not override visible logged-in page")

    monkeypatch.setattr(api, "peek_remaining_uses", fail_ws_peek)

    result = asyncio.run(api.peek_quota_status(timeout=1.0, allow_anonymous=True))

    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    assert result["remaining_uses"] == 20


def test_zhuque_service_detect_preserves_visible_login_quota_over_anonymous_result(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    class FakeAPI:
        credentials_file = tmp_path / "creds_latest.json"

        def credential_status(self):
            return {
                "has_token": False,
                "connected": False,
                "ready": False,
                "remaining_uses": -1,
                "button_enabled": False,
                "credential_file": str(self.credentials_file),
            }

        async def peek_quota_status(self, timeout=3.0, allow_anonymous=False):
            assert allow_anonymous is True
            return {
                "remaining_uses": 20,
                "button_enabled": True,
                "page_found": True,
                "has_token": True,
                "user_name": "木木",
                "quota_text": "Detect now(20 left)",
            }

        async def detect(self, text, timeout=60.0):
            return {
                "success": True,
                "rate": 56.5,
                "risk_rate": 56.5,
                "remaining_uses": 4,
                "fp": "anonymous-fp",
            }

    service = ZhuqueService(credentials_file=tmp_path / "creds_latest.json", owner_label="test")
    service.api = FakeAPI()
    service._ready = True

    result = asyncio.run(service.detect("测试文本" * 200))

    assert result["remaining_uses"] == 19
    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    session_status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is True
    assert session_status["user_name"] == "木木"
    assert session_status["remaining_uses"] == 19


def test_zhuque_service_refresh_free_quota_uses_live_visible_login_status(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    class FakeAPI:
        credentials_file = tmp_path / "creds_latest.json"

        def credential_status(self):
            return {
                "has_token": False,
                "connected": False,
                "ready": False,
                "remaining_uses": -1,
                "button_enabled": False,
                "credential_file": str(self.credentials_file),
            }

        async def peek_quota_status(self, timeout=5.0, allow_anonymous=False):
            assert allow_anonymous is True
            return {
                "remaining_uses": 20,
                "button_enabled": True,
                "page_found": True,
                "has_token": True,
                "user_name": "木木",
                "quota_text": "Detect now(20 left)",
                "message": "朱雀页面剩余次数已解析",
            }

    service = ZhuqueService(credentials_file=tmp_path / "creds_latest.json", owner_label="test")
    service.api = FakeAPI()

    result = asyncio.run(service.refresh_free_quota(timeout=1.0))

    assert result["connected"] is True
    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    assert result["remaining_uses"] == 20
    assert result["button_enabled"] is True
    session_status = json.loads((tmp_path / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is True
    assert session_status["has_token"] is True
    assert session_status["user_name"] == "木木"
    assert session_status["remaining_uses"] == 20


def test_local_browser_transport_focus_syncs_visible_login_status():
    from app.services.zhuque_local_browser_transport import LocalBrowserZhuqueTransport

    calls = []

    class FakeService:
        async def focus_detection_window(self):
            calls.append("focus")
            return {"available": True, "page_found": True, "message": "focused"}

        async def refresh_free_quota(self):
            calls.append("sync")
            return {
                "connected": True,
                "ready": True,
                "has_token": True,
                "logged_in": True,
                "page_found": True,
                "remaining_uses": 17,
                "button_enabled": True,
                "user_name": "木木",
                "message": "朱雀账号剩余次数已同步：17 次",
            }

    result = asyncio.run(LocalBrowserZhuqueTransport(FakeService(), user_id=1).open_page())

    assert calls == ["focus", "sync"]
    assert result["status"] == "focused"
    assert result["connected"] is True
    assert result["logged_in"] is True
    assert result["has_token"] is True
    assert result["user_name"] == "木木"
    assert result["remaining_uses"] == 17


def test_local_browser_transport_opens_builtin_page_before_legacy_capture():
    from app.services.zhuque_local_browser_transport import LocalBrowserZhuqueTransport

    calls = []

    class FakeService:
        async def focus_detection_window(self):
            calls.append("focus")
            return {"available": False, "message": "none"}

        async def open_detection_page(self):
            calls.append("open_detection_page")
            return {
                "available": True,
                "status": "opened",
                "credential_file": "creds.json",
                "url": "https://matrix.tencent.com/ai-detect/",
                "message": "opened builtin",
            }

    def fail_legacy_capture():
        raise AssertionError("legacy capture script must not be used when built-in opener works")

    result = asyncio.run(
        LocalBrowserZhuqueTransport(FakeService(), user_id=1).open_page(open_capture=fail_legacy_capture)
    )

    assert result["status"] == "opened"
    assert result["transport"] == "local_browser"
    assert result["page_found"] is True
    assert result["url"] == "https://matrix.tencent.com/ai-detect/"
    assert calls == ["focus", "open_detection_page"]


def test_zhuque_local_sync_endpoint_returns_local_browser_status(client, monkeypatch):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")

    class FakeLocalTransport:
        async def sync_status(self):
            return {
                "status": "synced",
                "transport": "local_browser",
                "auth_mode": "local_browser",
                "login_mode": "local_browser",
                "ready": True,
                "connected": True,
                "page_found": True,
                "has_token": True,
                "has_anonymous_fp": False,
                "remaining_uses": 18,
                "button_enabled": True,
                "user_name": "木木",
                "message": "本机朱雀状态已同步",
            }

    monkeypatch.setattr(optimization_route, "_zhuque_local_transport_for_user", lambda _user: FakeLocalTransport())

    response = client.post(
        "/api/optimization/zhuque/local/sync",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "synced"
    assert body["transport"] == "local_browser"
    assert body["remaining_uses"] == 18
    assert body["user_name"] == "木木"


def test_zhuque_browser_start_endpoint_keeps_local_window_mode(client, monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    credential_file = str(tmp_path / "creds_latest.json")
    captured_sync_values = []

    def fake_start_zhuque_wechat_capture(*, sync_session=True):
        captured_sync_values.append(sync_session)
        return {
            "status": "started",
            "auth_mode": "headless_api",
            "login_mode": "wechat_qr",
            "credential_file": credential_file,
            "sync_session": sync_session,
            "command": "python package/backend/app/tools/zhuque_capture_window.py --sync-session",
            "message": "已打开朱雀真实网页状态同步窗口",
        }

    monkeypatch.setattr(
        optimization_route,
        "_start_zhuque_wechat_capture",
        fake_start_zhuque_wechat_capture,
    )

    response = client.post(
        "/api/optimization/zhuque/browser/start?mode=local_window",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "started"
    assert body["login_mode"] == "wechat_qr"
    assert body["credential_file"] == credential_file
    assert body["sync_session"] is True
    assert body["command"] == "python package/backend/app/tools/zhuque_capture_window.py --sync-session"
    assert captured_sync_values == [True]

    response = client.post(
        "/api/optimization/zhuque/browser/start?sync_session=false&mode=local_window",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["sync_session"] is False
    assert captured_sync_values == [True, False]


def test_zhuque_browser_logout_endpoint_clears_user_credentials(client, monkeypatch, tmp_path):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    calls = []

    class FakeRemoteLoginService:
        async def logout(self, current_user_id):
            calls.append(("logout", current_user_id))
            return {
                "session_id": "logout-session",
                "status": "logged_out",
                "auth_mode": "headless_api",
                "login_mode": "remote_wechat_qr",
                "credential_file": str(tmp_path / f"user_{current_user_id}" / "creds_latest.json"),
                "connected": False,
                "ready": False,
                "has_token": False,
                "remaining_uses": -1,
                "user_name": "",
                "quota_text": "",
                "qr_image_data": "",
                "expires_at": "2026-06-24T00:00:00Z",
                "message": "已退出朱雀登录，未登录时将使用朱雀免费次数",
            }

    class FakeZhuqueService:
        def reset_user(self, current_user_id):
            calls.append(("reset", current_user_id))

    monkeypatch.setattr(optimization_route, "zhuque_remote_login_service", FakeRemoteLoginService())
    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.post(
        "/api/optimization/zhuque/browser/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "logged_out"
    assert body["connected"] is False
    assert body["ready"] is False
    assert body["has_token"] is False
    assert body["button_enabled"] is True
    assert "免费次数" in body["message"]
    assert calls == [("logout", user_id), ("reset", user_id)]


def test_zhuque_remote_login_logout_removes_user_credential_files(tmp_path, monkeypatch):
    import app.services.zhuque_remote_login_service as remote_module

    monkeypatch.setattr(remote_module, "zhuque_user_dir", lambda user_id: tmp_path / f"user_{user_id}")
    user_dir = tmp_path / "user_9"
    user_dir.mkdir(parents=True)
    for filename in ("creds_latest.json", "qrcode_latest.png"):
        (user_dir / filename).write_text("x", encoding="utf-8")
    (user_dir / "browser_state.json").write_text(
        json.dumps(
            {
                "origins": [
                    {
                        "origin": "https://matrix.tencent.com",
                        "localStorage": [{"name": "fp", "value": "anonymous-fp"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = remote_module.ZhuqueRemoteLoginService()
    payload = asyncio.run(service.logout(9))

    assert payload["status"] == "logged_out"
    assert "免费次数" in payload["message"]
    assert payload["has_anonymous_fp"] is True
    assert not (user_dir / "creds_latest.json").exists()
    assert (user_dir / "browser_state.json").exists()
    assert not (user_dir / "qrcode_latest.png").exists()
    session_status = json.loads((user_dir / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is False
    assert session_status["has_token"] is False
    assert session_status["has_anonymous_fp"] is True
    assert session_status["anonymous_fp"] == "anonymous-fp"
    assert "免费次数" in session_status["message"]


def test_zhuque_browser_status_endpoint_reports_ready_credentials(client, monkeypatch):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": True,
                "connected": True,
                "has_token": True,
                "credential_file": "/tmp/creds_latest.json",
                "user_name": "tester",
                "quota_text": "今日剩余 18 次",
                "captured_at": "2026-06-16T00:00:00Z",
                "message": "朱雀微信凭证已就绪，检测将走无头 API",
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.get(
        "/api/optimization/zhuque/browser/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["ready"] is True
    assert body["status"] == "connected"
    assert body["auth_mode"] == "headless_api"
    assert body["login_mode"] == "wechat_qr"
    assert body["credential_file"] == "/tmp/creds_latest.json"
    assert body["user_name"] == "tester"


def test_zhuque_browser_status_endpoint_prefers_live_cache_over_stale_credentials(client, monkeypatch):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": True,
                "connected": True,
                "has_token": True,
                "remaining_uses": 20,
                "button_enabled": True,
                "credential_file": "/tmp/creds_latest.json",
                "user_name": "tester",
                "quota_text": "今日剩余 20 次",
                "captured_at": "2026-06-16T00:00:00Z",
                "message": "朱雀微信凭证已就绪，检测将走无头 API",
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

        def cached_remaining_uses(self):
            return 18

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.get(
        "/api/optimization/zhuque/browser/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["ready"] is True
    assert body["remaining_uses"] == 18
    assert body["button_enabled"] is True
    assert body["quota_text"] == "剩余 18 次"


def test_zhuque_browser_status_endpoint_reports_missing_credentials(client, monkeypatch):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")

    class FakeAPI:
        def credential_status(self):
            return {
                "ready": False,
                "connected": False,
                "has_token": False,
                "credential_file": "/tmp/creds_latest.json",
                "message": "未找到朱雀微信登录凭证",
            }

    class FakeZhuqueService:
        def _ensure_api(self):
            return FakeAPI()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueService())

    response = client.get(
        "/api/optimization/zhuque/browser/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["ready"] is False
    assert body["status"] == "missing_credentials"
    assert "微信登录凭证" in body["message"]


def test_zhuque_free_quota_refresh_endpoint_uses_user_scoped_service(client, monkeypatch):
    import app.routes.optimization as optimization_route

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    calls = []

    class FakeUserZhuqueService:
        async def refresh_free_quota(self):
            calls.append(("refresh_free_quota", user_id))
            return {
                "ready": True,
                "connected": False,
                "page_found": True,
                "has_token": False,
                "remaining_uses": 16,
                "button_enabled": True,
                "text_length": None,
                "text_length_ok": True,
                "estimated_first_round_credits": 0,
                "estimated_max_round_credits": 0,
                "message": "朱雀免费次数已同步：16 次",
                "actions": [],
                "auth_mode": "headless_api",
                "login_mode": "wechat_qr",
                "credential_file": "/tmp/user_1/creds_latest.json",
                "user_name": "",
                "quota_text": "剩余 16 次",
                "captured_at": "",
            }

    class FakeZhuqueServiceManager:
        def for_user(self, current_user_id):
            calls.append(("for_user", current_user_id))
            return FakeUserZhuqueService()

    monkeypatch.setattr(optimization_route, "zhuque_service", FakeZhuqueServiceManager())

    response = client.post(
        "/api/optimization/zhuque/free-quota/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["has_token"] is False
    assert body["remaining_uses"] == 16
    assert body["button_enabled"] is True
    assert "免费次数" in body["message"]
    assert calls == [("for_user", user_id), ("refresh_free_quota", user_id)]


def test_zhuque_service_manager_uses_isolated_user_credential_files(tmp_path, monkeypatch):
    import app.services.zhuque_service as zhuque_service_module

    monkeypatch.setattr(zhuque_service_module.settings, "ZHUQUE_USER_DATA_DIR", str(tmp_path))
    manager = zhuque_service_module.ZhuqueServiceManager()

    user_one = manager.for_user(1)
    user_two = manager.for_user(2)

    assert user_one is manager.for_user(1)
    assert user_two is not user_one
    assert user_one.credentials_file == tmp_path / "user_1" / "creds_latest.json"
    assert user_two.credentials_file == tmp_path / "user_2" / "creds_latest.json"


def test_zhuque_remote_login_service_restarts_after_logged_in_session(tmp_path, monkeypatch):
    import app.services.zhuque_remote_login_service as remote_module

    monkeypatch.setattr(remote_module, "zhuque_user_dir", lambda user_id: tmp_path / f"user_{user_id}")

    created_tasks = []

    class FakeTask:
        pass

    def fake_create_task(coro):
        # Close coroutine to avoid warnings; we only assert scheduling behavior.
        coro.close()
        task = FakeTask()
        created_tasks.append(task)
        return task

    monkeypatch.setattr(remote_module.asyncio, "create_task", fake_create_task)
    service = remote_module.ZhuqueRemoteLoginService()

    first = asyncio.run(service.start(7))
    service._sessions[7].status = "logged_in"
    second = asyncio.run(service.start(7))

    assert first["session_id"] != second["session_id"]
    assert len(created_tasks) == 2
    assert second["credential_file"].endswith("user_7/creds_latest.json")
    assert service._sessions[7].force_login is True


def test_zhuque_remote_login_uses_project_playwright_browser_cache(tmp_path, monkeypatch):
    import app.services.zhuque_remote_login_service as remote_module

    browser_root = tmp_path / ".playwright-browsers"
    chromium = browser_root / "chromium-1223" / "chrome-linux64" / "chrome"
    chromium.parent.mkdir(parents=True)
    chromium.write_text("#!/bin/sh\n", encoding="utf-8")
    chromium.chmod(0o755)

    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr(remote_module, "_playwright_browsers_path", lambda: browser_root)

    assert remote_module._playwright_executable_path() == str(chromium)


def test_zhuque_remote_login_does_not_capture_full_page_without_qr(tmp_path):
    import app.services.zhuque_remote_login_service as remote_module

    class FakePage:
        async def query_selector(self, selector):
            return None

        async def screenshot(self, **kwargs):
            raise AssertionError("full page screenshot must not be used as QR image")

    session = remote_module.ZhuqueRemoteLoginSession(
        session_id="s1",
        user_id=1,
        user_dir=tmp_path,
    )
    service = remote_module.ZhuqueRemoteLoginService()

    asyncio.run(service._refresh_qr_image(session, FakePage()))

    assert session.qr_image_data == ""
    assert not session.qrcode_file.exists()


def test_zhuque_remote_login_inspect_retries_navigation_context_destroyed():
    import app.services.zhuque_remote_login_service as remote_module

    class FakeContext:
        async def cookies(self):
            return []

    class FakePage:
        def __init__(self):
            self.context = FakeContext()
            self.evaluate_calls = 0
            self.waited_for_load = False

        async def evaluate(self, script):
            self.evaluate_calls += 1
            if self.evaluate_calls == 1:
                raise RuntimeError("Page.evaluate: Execution context was destroyed, most likely because of a navigation")
            return {
                "localStorage": {"fp": "retry-fp"},
                "userName": "",
                "userInfoText": "",
                "loginPromptVisible": True,
                "quotaText": "",
                "submitButtonText": "Detect now(4 left)",
                "remainingUses": 4,
                "url": "https://matrix.tencent.com/ai-detect/",
                "timestamp": "2026-07-06T00:00:00Z",
            }

        async def wait_for_load_state(self, state, timeout):
            self.waited_for_load = True

        async def wait_for_timeout(self, timeout):
            pass

    page = FakePage()
    state = asyncio.run(remote_module.inspect_auth_state(page))

    assert page.evaluate_calls == 2
    assert page.waited_for_load is True
    assert state["remainingUses"] == 4
    assert state["fp"] == "retry-fp"


def test_zhuque_trigger_login_flow_clicks_english_login_and_wechat(monkeypatch):
    import app.services.zhuque_remote_login_service as remote_module

    calls = []

    class FakePage:
        async def evaluate(self, script):
            calls.append(script)
            if "some(f => /open\\.weixin" in script:
                return True
            return True

        async def wait_for_timeout(self, timeout):
            calls.append(("wait", timeout))

        async def wait_for_function(self, script, timeout):
            calls.append(("wait_for_function", script, timeout))

    opened = asyncio.run(remote_module.trigger_login_flow(FakePage()))

    assert opened is True
    joined = "\n".join(str(call) for call in calls)
    assert "'Login'" in joined
    assert "wechat|weixin" in joined
    assert "wait_for_function" in joined


def test_zhuque_service_starts_with_wechat_credentials(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    fake_api = StatusOnlyZhuqueAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 5,
            "peek_remaining_uses": 5,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        asyncio.run(service.start())

        assert service.is_ready is True
        assert fake_api.status_calls == 1
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None


def test_zhuque_service_readiness_reports_credential_state_and_text_length(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    fake_api = StatusOnlyZhuqueAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 3,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("短文本"))

        assert result["connected"] is True
        assert result["page_found"] is True
        assert result["has_token"] is True
        assert result["remaining_uses"] == 3
        assert result["button_enabled"] is True
        assert result["text_length"] == 3
        assert result["text_length_ok"] is False
        assert result["ready"] is False
        assert "350" in result["message"]
        assert "补充文本到 350 字以上" in result["actions"]
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None


def test_zhuque_service_readiness_allows_anonymous_free_quota(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0, *, allow_anonymous=False):
            self.peek_calls += 1
            return 16 if allow_anonymous else None

    fake_api = FakeAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "未找到朱雀微信登录凭证",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("汉" * 500))

        assert result["connected"] is False
        assert result["has_token"] is False
        assert fake_api.peek_calls == 1
        assert result["remaining_uses"] == 16
        assert result["button_enabled"] is True
        assert result["ready"] is True
        assert "免费检测次数" in result["message"]
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_allows_hidden_anonymous_quota_when_button_enabled(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0, *, allow_anonymous=False):
            self.peek_calls += 1
            return None

    fake_api = FakeAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "未找到朱雀微信登录凭证",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("汉" * 500))

        assert fake_api.peek_calls == 1
        assert result["connected"] is False
        assert result["has_token"] is False
        assert result["remaining_uses"] == -1
        assert result["button_enabled"] is True
        assert result["ready"] is True
        assert "检测后同步" in result["message"]
        assert "朱雀免费检测入口可用，剩余次数将在检测后同步" in result["actions"]
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_hidden_anonymous_quota_clears_stale_cache(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0, *, allow_anonymous=False):
            self.peek_calls += 1
            return None

    fake_api = FakeAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "未找到朱雀微信登录凭证",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = 16
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("汉" * 500))

        assert fake_api.peek_calls == 1
        assert result["remaining_uses"] == -1
        assert result["button_enabled"] is True
        assert result["ready"] is True
        assert service._last_remaining_uses is None
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_refresh_free_quota_probes_anonymous_and_persists_status(tmp_path, monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    creds_file = tmp_path / "user_5" / "creds_latest.json"
    fake_api = StatusOnlyZhuqueAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": str(creds_file),
            "message": "朱雀网页显示未登录",
            "peek_remaining_uses": 16,
        }
    )
    fake_api.credentials_file = creds_file
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_5")
    service.api = None
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    result = asyncio.run(service.refresh_free_quota())

    assert result["connected"] is False
    assert result["has_token"] is False
    assert result["remaining_uses"] == 16
    assert result["button_enabled"] is True
    assert result["ready"] is True
    assert fake_api.peek_calls == [{"timeout": 5.0, "allow_anonymous": True}]

    session_status = json.loads((tmp_path / "user_5" / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is False
    assert session_status["has_token"] is False
    assert session_status["remaining_uses"] == 16
    assert "免费次数" in session_status["message"]


def test_zhuque_service_refresh_free_quota_hidden_count_keeps_button_ready_without_stale_cache(tmp_path, monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    creds_file = tmp_path / "user_5" / "creds_latest.json"
    fake_api = StatusOnlyZhuqueAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": str(creds_file),
            "message": "朱雀网页显示未登录",
            "peek_remaining_uses": None,
        }
    )
    fake_api.credentials_file = creds_file
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_5")
    service.api = None
    service._last_remaining_uses = 16
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    result = asyncio.run(service.refresh_free_quota())

    assert result["connected"] is False
    assert result["has_token"] is False
    assert result["remaining_uses"] == -1
    assert result["button_enabled"] is True
    assert result["ready"] is True
    assert "检测后同步" in result["message"]
    assert not (tmp_path / "user_5" / "session_status.json").exists()


def test_zhuque_service_refresh_free_quota_persists_anonymous_fp_when_count_hidden(tmp_path, monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    creds_file = tmp_path / "user_5" / "creds_latest.json"

    class HiddenCountAPI(StatusOnlyZhuqueAPI):
        async def peek_quota_status(self, timeout=3.0, *, allow_anonymous=False):
            self.peek_calls.append({"timeout": timeout, "allow_anonymous": allow_anonymous})
            return {
                "remaining_uses": -1,
                "button_enabled": True,
                "page_found": True,
                "quota_text": "Detect now",
                "fp": "fresh-anonymous-fp",
                "anonymous_fp": "fresh-anonymous-fp",
                "has_anonymous_fp": True,
                "probe_state": {"fp": "fresh-anonymous-fp"},
                "message": "朱雀页面检测入口可用，但当前页面未暴露剩余次数数字",
            }

    fake_api = HiddenCountAPI(
        {
            "ready": False,
            "connected": False,
            "page_found": False,
            "has_token": False,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": str(creds_file),
            "message": "朱雀网页显示未登录",
        }
    )
    fake_api.credentials_file = creds_file
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_5")
    service.api = None
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    result = asyncio.run(service.refresh_free_quota())

    assert result["remaining_uses"] == -1
    assert result["button_enabled"] is True
    assert result["ready"] is True
    assert result["has_anonymous_fp"] is True
    session_status = json.loads((tmp_path / "user_5" / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is False
    assert session_status["has_token"] is False
    assert session_status["remaining_uses"] == -1
    assert session_status["has_anonymous_fp"] is True
    assert session_status["anonymous_fp"] == "fresh-anonymous-fp"
    assert session_status["quota_text"] == ""


def test_zhuque_service_detect_persists_anonymous_remaining_uses(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    creds_file = tmp_path / "user_5" / "creds_latest.json"
    (tmp_path / "user_5").mkdir()
    (tmp_path / "user_5" / "session_status.json").write_text(
        json.dumps(
            {
                "connected": False,
                "ready": False,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "old-session-fp",
                "remaining_uses": 4,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class AnonymousDetectAPI:
        def __init__(self):
            self.credentials_file = creds_file
            self.detect_calls = []
            self.forget_calls = 0

        def credential_status(self):
            return {
                "ready": False,
                "connected": False,
                "page_found": True,
                "has_token": False,
                "has_anonymous_fp": True,
                "anonymous_fp": "old-session-fp",
                "remaining_uses": 4,
                "button_enabled": True,
                "credential_file": str(creds_file),
            }

        async def detect(self, text, timeout=60.0):
            self.detect_calls.append({"text": text, "timeout": timeout})
            return {
                "success": True,
                "rate": 12,
                "labels_ratio": {"0": 0.12, "1": 0.88, "2": 0.0},
                "remaining_uses": 3,
                "text_length": len(text),
                "fp": "detected-anonymous-fp",
                "anonymous_fp": "detected-anonymous-fp",
                "has_anonymous_fp": True,
            }

        def forget_credentials_cache(self):
            self.forget_calls += 1

    async def run_detect(service):
        consumer_task = asyncio.create_task(service._consumer())
        try:
            return await asyncio.wait_for(service.detect("汉" * 500), timeout=1.0)
        finally:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

    fake_api = AnonymousDetectAPI()
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_5")
    service.api = fake_api
    service._ready = True

    result = asyncio.run(run_detect(service))

    assert result["success"] is True
    assert result["remaining_uses"] == 3
    assert fake_api.forget_calls == 1
    session_status = json.loads((tmp_path / "user_5" / "session_status.json").read_text(encoding="utf-8"))
    assert session_status["connected"] is False
    assert session_status["has_token"] is False
    assert session_status["remaining_uses"] == 3
    assert session_status["has_anonymous_fp"] is True
    assert session_status["anonymous_fp"] == "detected-anonymous-fp"
    assert "免费次数" in session_status["message"]


def test_zhuque_service_detect_timeout_keeps_cached_credentials_state(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    creds_file = tmp_path / "user_9" / "creds_latest.json"
    creds_file.parent.mkdir(parents=True)

    class TimeoutDetectAPI:
        def __init__(self):
            self.credentials_file = creds_file
            self.forget_calls = 0

        def credential_status(self):
            return {
                "has_token": True,
                "remaining_uses": 5,
                "button_enabled": True,
                "credential_file": str(creds_file),
            }

        async def detect(self, text, timeout=60.0):
            return {
                "success": False,
                "message": f"检测超时 ({timeout}s), 请检查朱雀凭证或网络状态",
                "remaining_uses": -1,
                "text_length": len(text),
            }

        def forget_credentials_cache(self):
            self.forget_calls += 1

    async def run_detect(service):
        consumer_task = asyncio.create_task(service._consumer())
        try:
            return await asyncio.wait_for(service.detect("汉" * 500), timeout=1.0)
        finally:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

    fake_api = TimeoutDetectAPI()
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_9")
    service.api = fake_api
    service._ready = True
    service._last_remaining_uses = 5

    result = asyncio.run(run_detect(service))

    assert result["success"] is False
    assert fake_api.forget_calls == 0
    assert service.is_ready is True
    assert service.cached_remaining_uses() == 5


def test_zhuque_service_detect_auth_failure_resets_cached_credentials_state(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    creds_file = tmp_path / "user_9" / "creds_latest.json"
    creds_file.parent.mkdir(parents=True)

    class AuthFailureDetectAPI:
        def __init__(self):
            self.credentials_file = creds_file
            self.forget_calls = 0

        def credential_status(self):
            return {
                "has_token": True,
                "remaining_uses": 5,
                "button_enabled": True,
                "credential_file": str(creds_file),
            }

        async def detect(self, text, timeout=60.0):
            return {
                "success": False,
                "message": "登录已过期，请重新微信扫码登录",
                "remaining_uses": -1,
                "text_length": len(text),
            }

        def forget_credentials_cache(self):
            self.forget_calls += 1

    async def run_detect(service):
        consumer_task = asyncio.create_task(service._consumer())
        try:
            return await asyncio.wait_for(service.detect("汉" * 500), timeout=1.0)
        finally:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

    fake_api = AuthFailureDetectAPI()
    service = ZhuqueService(credentials_file=creds_file, owner_label="user_9")
    service.api = fake_api
    service._ready = True
    service._last_remaining_uses = 5

    result = asyncio.run(run_detect(service))

    assert result["success"] is False
    assert fake_api.forget_calls == 1
    assert service.is_ready is False
    assert service.cached_remaining_uses() is None


def test_zhuque_service_consumer_survives_cancelled_detect_future(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    creds_file = tmp_path / "user_10" / "creds_latest.json"
    creds_file.parent.mkdir(parents=True)

    class SlowThenFastAPI:
        def __init__(self):
            self.credentials_file = creds_file
            self.calls = 0

        def credential_status(self):
            return {
                "has_token": True,
                "remaining_uses": 5,
                "button_enabled": True,
                "credential_file": str(creds_file),
            }

        async def detect(self, text, timeout=60.0):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.05)
            return {
                "success": True,
                "rate": 0.0,
                "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
                "remaining_uses": max(5 - self.calls, 0),
                "text_length": len(text),
            }

    async def run_flow():
        fake_api = SlowThenFastAPI()
        service = ZhuqueService(credentials_file=creds_file, owner_label="user_10")
        service.api = fake_api
        service._ready = True
        service._consumer_task = asyncio.create_task(service._consumer())
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(service.detect("汉" * 500), timeout=0.01)
            result = await asyncio.wait_for(service.detect("汉" * 500), timeout=1.0)
            return fake_api, service, result
        finally:
            if service._consumer_task:
                service._consumer_task.cancel()
                try:
                    await service._consumer_task
                except asyncio.CancelledError:
                    pass

    fake_api, service, result = asyncio.run(run_flow())

    assert fake_api.calls == 2
    assert result["success"] is True
    assert service.cached_remaining_uses() == 3


def test_zhuque_service_detect_restarts_dead_consumer_task(tmp_path):
    from app.services.zhuque_service import ZhuqueService

    creds_file = tmp_path / "user_11" / "creds_latest.json"
    creds_file.parent.mkdir(parents=True)

    class ImmediateAPI:
        credentials_file = creds_file

        def credential_status(self):
            return {
                "has_token": True,
                "remaining_uses": 5,
                "button_enabled": True,
                "credential_file": str(creds_file),
            }

        async def detect(self, text, timeout=60.0):
            return {
                "success": True,
                "rate": 0.0,
                "labels_ratio": {"0": 0.0, "1": 1.0, "2": 0.0},
                "remaining_uses": 4,
                "text_length": len(text),
            }

    async def run_flow():
        async def already_done():
            return None

        service = ZhuqueService(credentials_file=creds_file, owner_label="user_11")
        service.api = ImmediateAPI()
        service._ready = True
        service._consumer_task = asyncio.create_task(already_done())
        await service._consumer_task
        try:
            result = await asyncio.wait_for(service.detect("汉" * 500), timeout=1.0)
            return service, result
        finally:
            if service._consumer_task:
                service._consumer_task.cancel()
                try:
                    await service._consumer_task
                except asyncio.CancelledError:
                    pass

    service, result = asyncio.run(run_flow())

    assert result["success"] is True
    assert service.cached_remaining_uses() == 4


def test_zhuque_service_readiness_uses_live_quota_probe(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0):
            self.peek_calls += 1
            return 16

    fake_api = FakeAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("汉" * 500))

        assert fake_api.peek_calls == 1
        assert result["remaining_uses"] == 16
        assert result["ready"] is True
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_blocks_logged_in_when_forced_live_probe_unusable(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    fake_api = StatusOnlyZhuqueAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 20,
            "button_enabled": True,
            "peek_remaining_uses": None,
            "peek_button_enabled": False,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness("汉" * 500))

        assert fake_api.peek_calls == [{"timeout": 2.5, "allow_anonymous": False}]
        assert result["remaining_uses"] == -1
        assert result["button_enabled"] is False
        assert result["ready"] is False
        assert "暂未探测到朱雀剩余次数" in result["message"]
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_without_text_skips_live_probe_when_quota_unknown(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0):
            self.peek_calls += 1
            return 16

    fake_api = FakeAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": -1,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness())

        assert fake_api.peek_calls == 0
        assert result["remaining_uses"] == -1
        assert result["connected"] is True
        assert result["ready"] is True
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_without_text_reuses_known_quota_without_live_probe(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0):
            self.peek_calls += 1
            return 16

    fake_api = FakeAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 20,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness())

        assert fake_api.peek_calls == 0
        assert result["remaining_uses"] == 20
        assert result["connected"] is True
        assert result["ready"] is True
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_without_text_prefers_live_cache_over_stale_credentials(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0):
            self.peek_calls += 1
            return 16

    fake_api = FakeAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 20,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = 18
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        result = asyncio.run(service.readiness())

        assert fake_api.peek_calls == 0
        assert result["remaining_uses"] == 18
        assert result["connected"] is True
        assert result["ready"] is True
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_service_readiness_throttles_live_quota_probe(monkeypatch):
    from app.services.zhuque_service import ZhuqueService
    import app.services.zhuque_service as zhuque_service_module

    class FakeAPI(StatusOnlyZhuqueAPI):
        def __init__(self, status_payload):
            super().__init__(status_payload)
            self.peek_calls = 0

        async def peek_remaining_uses(self, timeout=3.0):
            self.peek_calls += 1
            return 15 - self.peek_calls

    fake_api = FakeAPI(
        {
            "ready": True,
            "connected": True,
            "page_found": True,
            "has_token": True,
            "remaining_uses": 12,
            "button_enabled": True,
            "credential_file": "/tmp/creds_latest.json",
            "message": "朱雀微信凭证已就绪，检测将走无头 API",
        }
    )
    service = ZhuqueService()
    service.api = None
    service._ready = False
    service._consumer_task = None
    service._last_remaining_uses = None
    service._last_remaining_checked_at = 0
    monkeypatch.setattr(zhuque_service_module, "ZhuqueAPI", lambda *args, **kwargs: fake_api)

    try:
        first = asyncio.run(service.readiness("汉" * 500))
        second = asyncio.run(service.readiness())

        assert fake_api.peek_calls == 1
        assert first["remaining_uses"] == 14
        assert second["remaining_uses"] == 14
    finally:
        if service._consumer_task:
            service._consumer_task.cancel()
        service._ready = False
        service.api = None
        service._consumer_task = None
        service._last_remaining_uses = None
        service._last_remaining_checked_at = 0


def test_zhuque_readiness_endpoint_returns_actionable_state(client, monkeypatch):
    from app.routes import optimization

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")

    class FakeReadyService:
        async def readiness(self, text=None):
            return {
                "ready": False,
                "connected": True,
                "page_found": True,
                "has_token": False,
                "remaining_uses": 0,
                "button_enabled": False,
                "text_length": len(text or ""),
                "text_length_ok": True,
                "estimated_first_round_credits": 0,
                "estimated_max_round_credits": 0,
                "message": "朱雀次数不足，请登录或切换账号",
                "actions": ["登录或切换朱雀账号"],
            }

    monkeypatch.setattr(optimization, "zhuque_service", FakeReadyService())

    response = client.get(
        "/api/optimization/zhuque/readiness",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["connected"] is True
    assert body["remaining_uses"] == 0
    assert "登录或切换朱雀账号" in body["actions"]


def test_ai_detect_reduce_start_rejects_short_text_before_creating_session(client, monkeypatch):
    from app.routes import optimization

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    monkeypatch.setattr(optimization.settings, "INLINE_TASK_WORKER_ENABLED", False, raising=False)

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "短文本",
            "processing_mode": "ai_detect_reduce",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "350" in response.json()["detail"]

    db = SessionLocal()
    try:
        sessions = db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).all()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
        assert sessions == []
        assert transactions == []
    finally:
        db.close()


def test_ai_detect_reduce_start_rejects_unready_zhuque_before_creating_session(client, monkeypatch):
    from app.routes import optimization

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    monkeypatch.setattr(optimization.settings, "INLINE_TASK_WORKER_ENABLED", False, raising=False)

    class FakeUnreadyService:
        async def readiness(self, text=None):
            return {
                "ready": False,
                "connected": False,
                "page_found": False,
                "has_token": False,
                "remaining_uses": -1,
                "button_enabled": False,
                "text_length": len(text or ""),
                "text_length_ok": True,
                "estimated_first_round_credits": 10,
                "estimated_max_round_credits": 50,
                "message": "未找到朱雀微信登录凭证",
                "actions": ["微信扫码登录朱雀"],
            }

    monkeypatch.setattr(optimization, "zhuque_service", FakeUnreadyService())

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "汉" * 500,
            "processing_mode": "ai_detect_reduce",
            "billing_mode": "platform",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "未找到朱雀微信登录凭证" in response.json()["detail"]
    assert "微信扫码登录朱雀" in response.json()["detail"]

    db = SessionLocal()
    try:
        assert db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).count() == 0
        assert db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).count() == 0
    finally:
        db.close()


def test_ai_detect_reduce_byok_requires_provider_before_zhuque_preflight(client, monkeypatch):
    from app.routes import optimization

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    readiness_calls = []

    class FakeReadyService:
        async def readiness(self, text=None):
            readiness_calls.append(text)
            return {
                "ready": True,
                "connected": True,
                "page_found": True,
                "has_token": True,
                "remaining_uses": 20,
                "button_enabled": True,
                "text_length": len(text or ""),
                "text_length_ok": True,
                "estimated_first_round_credits": 10,
                "estimated_max_round_credits": 50,
                "message": "朱雀已就绪",
                "actions": [],
            }

    monkeypatch.setattr(optimization, "zhuque_service", FakeReadyService())

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "汉" * 500,
            "processing_mode": "ai_detect_reduce",
            "billing_mode": "byok",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"
    assert readiness_calls == []

    db = SessionLocal()
    try:
        assert db.query(OptimizationSession).filter(OptimizationSession.user_id == user_id).count() == 0
    finally:
        db.close()


def test_zhuque_preflight_byok_requires_provider_before_readiness(client, monkeypatch):
    from app.routes import optimization

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    readiness_calls = []

    class FakeReadyService:
        async def readiness(self, text=None):
            readiness_calls.append(text)
            return {"ready": True, "connected": True, "page_found": True, "has_token": True, "remaining_uses": 20, "button_enabled": True, "text_length": len(text or ""), "text_length_ok": True, "estimated_first_round_credits": 10, "estimated_max_round_credits": 50, "message": "朱雀已就绪", "actions": []}

    monkeypatch.setattr(optimization, "zhuque_service", FakeReadyService())

    response = client.post(
        "/api/optimization/zhuque/preflight",
        json={
            "original_text": "汉" * 500,
            "processing_mode": "ai_detect_reduce",
            "billing_mode": "byok",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "请先保存自带 API 配置"
    assert readiness_calls == []


def test_session_detail_includes_zhuque_report_payload(client):
    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    token = create_user_access_token(user_id, "zhuque-user")
    report = {
        "success": True,
        "rate": 18.5,
        "labels_ratio": {"human": 0.815, "ai": 0.185},
        "remaining_uses": 17,
        "text_length": 732,
        "message": "检测完成",
    }

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-detail-report",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="completed",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            progress=100,
        )
        db.add(session)
        db.flush()
        db.add(
            OptimizationSegment(
                session_id=session.id,
                segment_index=0,
                stage="enhance",
                original_text="待检测文本" * 80,
                polished_text="润色后文本",
                enhanced_text="增强后文本",
                status="completed",
                zhuque_detect_rate=18.5,
                zhuque_detect_result=json.dumps(report, ensure_ascii=False),
                zhuque_detect_count=2,
                zhuque_reduce_attempt=1,
                zhuque_reduced_text="增强后文本",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/optimization/sessions/zhuque-detail-report",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "zhuque_agent_trace" in response.json()
    segment = response.json()["segments"][0]
    assert segment["zhuque_detect_result"] == json.dumps(report, ensure_ascii=False)


def test_ai_detect_reduce_fails_when_zhuque_rejects_any_segment(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FailingZhuqueService("文本长度不足 (164<350字), 请提供更长的文本")
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, FakeAIService()))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-detect-rejected",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="太短文本" * 20,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="文本长度不足"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()

        assert session.status == "failed"
        assert "文本长度不足" in session.error_message
        assert segment.zhuque_detect_count == 1
        assert segment.zhuque_detect_rate is None
        assert segment.zhuque_reduce_attempt == 0
        assert user.credit_balance == 20
        assert transactions == []
    finally:
        db.close()


def test_ai_detect_reduce_does_not_complete_on_invalid_zhuque_zero_payload(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([
        {
            "success": False,
            "message": "Invalid request",
            "rate": 0,
            "risk_rate": 0,
            "labels_ratio": {},
            "remaining_uses": 9,
        }
    ])
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, FakeAIService()))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-invalid-request-not-zero",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="这是一段用于触发朱雀全文检测的长文本。" * 40,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="Invalid request"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()

        assert session.status == "failed"
        assert "Invalid request" in session.error_message
        assert segment.status == "failed"
        assert segment.zhuque_detect_count == 1
        assert segment.zhuque_detect_rate is None
        assert segment.zhuque_reduce_attempt == 0
        assert transactions == []
    finally:
        db.close()


def test_ai_detect_reduce_captcha_failure_records_manual_verification_metadata(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([
        {
            "success": False,
            "message": "朱雀触发腾讯验证码，请打开朱雀验证窗口，在真实浏览器手动完成验证后回到本页继续处理",
            "error_code": "zhuque_captcha_required",
            "manual_verification_required": True,
            "manual_verification_mode": "local_window",
            "manual_verification_action": "open_zhuque_local_window",
            "manual_verification_label": "打开朱雀验证窗口",
            "labels_ratio": {},
            "remaining_uses": 9,
        }
    ])
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, FakeAIService()))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-captcha-manual-verification",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="这是一段用于触发朱雀全文检测的长文本。" * 40,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="腾讯验证码"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        result = json.loads(segment.zhuque_detect_result)
        trace = json.loads(session.zhuque_agent_trace)
        detect_event = next(event for event in trace["events"] if event["type"] == "detect")

        assert session.status == "failed"
        assert result["error_code"] == "zhuque_captcha_required"
        assert result["manual_verification_required"] is True
        assert result["manual_verification_mode"] == "local_window"
        assert detect_event["error_code"] == "zhuque_captcha_required"
        assert detect_event["manual_verification_required"] is True
        assert detect_event["manual_verification_action"] == "open_zhuque_local_window"
    finally:
        db.close()


def test_ai_detect_reduce_rewrites_segments_above_threshold_and_records_results(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 12])
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    broadcasts = []

    async def capture_broadcast(session_id, data):
        broadcasts.append({"session_id": session_id, "data": data})

    monkeypatch.setattr(optimization_service_module.stream_manager, "broadcast", capture_broadcast)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    original_text = "待检测文本" * 80

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-session",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text=original_text,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()

        assert session.status == "completed"
        trace = json.loads(session.zhuque_agent_trace)
        assert trace["version"] == 1
        assert trace["threshold"] == 20.0
        assert trace["events"][0]["type"] == "detect"
        assert trace["events"][0]["rate"] == 80
        assert trace["events"][0]["detect_text_source"] == "session_original_text"
        reduce_event = next(event for event in trace["events"] if event["type"] == "reduce")
        assert reduce_event["round"] == 1
        assert reduce_event["strategy"] == "轻度自然化"
        assert reduce_event["selected_segment_indices"] == [0]
        assert reduce_event["old_rate"] == 80
        assert reduce_event["new_rate"] == 12
        for event_index, event in enumerate(trace["events"], start=1):
            assert event["id"] == f"zq-{session.session_id}-{event_index}"
            assert event["seq"] == event_index
            assert event["created_at"]
            assert event["phase"]
            assert event["status"]
            assert event["title"]
            assert event["summary"]
        assert trace["final"]["status"] == "completed"
        assert trace["final"]["rate"] == 12
        agent_events = [
            item["data"]["agent_event"]
            for item in broadcasts
            if item["data"].get("type") == "zhuque_agent_event"
        ]
        assert {event["type"] for event in agent_events} == {"detect", "segment_classification", "reduce"}
        assert next(event for event in agent_events if event["type"] == "detect")["phase"] == "zhuque_detect"
        assert next(event for event in agent_events if event["type"] == "segment_classification")["phase"] == "segment_classification"
        live_reduce_event = next(event for event in agent_events if event["type"] == "reduce")
        assert live_reduce_event["phase"] == "zhuque_reduce"
        assert live_reduce_event["title"] == "第 1 轮降 AI"
        assert any(item["data"].get("type") == "zhuque_detect" for item in broadcasts)
        assert any(item["data"].get("type") == "zhuque_reduce" for item in broadcasts)
        assert segment.zhuque_detect_count == 2
        assert segment.zhuque_reduce_attempt == 1
        assert segment.polished_text == f"润色后:{segment.original_text}"
        assert segment.enhanced_text == f"增强后:{segment.polished_text}"
        assert segment.zhuque_reduced_text == segment.enhanced_text
        assert segment.zhuque_detect_rate == 12
        assert user.zhuque_free_uses_remaining == 99
        assert user.zhuque_total_uses == 2
        assert user.credit_balance == 10
        assert [(txn.reason, txn.delta) for txn in transactions] == [("zhuque_reduce", -10)]
        assert fake_zhuque.detected_texts[0] == segment.original_text
        assert fake_zhuque.detected_texts[1] == segment.zhuque_reduced_text
        assert fake_zhuque.detect_contexts == [
            {"session_id": session.id},
            {"session_id": session.id},
        ]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment.original_text]
        assert [call["text"] for call in fake_ai.enhance_calls] == [segment.polished_text]
    finally:
        db.close()


@pytest.mark.parametrize("batch_enabled", [True, False])
def test_ai_detect_reduce_byok_never_charges_platform_credits(monkeypatch, batch_enabled):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 12])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(
        OptimizationService,
        "_init_ai_services",
        lambda self: _install_fake_ai_services(self, fake_ai),
    )
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(
        optimization_service_module.settings,
        "ZHUQUE_REDUCE_BATCH_ENABLED",
        batch_enabled,
        raising=False,
    )

    original_text = "自带 API 降重文本" * 80
    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id=f"zhuque-byok-no-credit-{int(batch_enabled)}",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="byok",
            credential_source="user_saved",
            charge_status="not_charged",
            charged_credits=0,
        )
        db.add(session)
        db.flush()
        db.add(
            OptimizationSegment(
                session_id=session.id,
                segment_index=0,
                stage="ai_detect_reduce",
                original_text=original_text,
                status="pending",
            )
        )
        db.commit()

        asyncio.run(OptimizationService(db, session).start_optimization())

        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()
        assert session.status == "completed"
        assert session.billing_mode == "byok"
        assert user.credit_balance == 20
        assert transactions == []
    finally:
        db.close()


def test_ai_detect_reduce_repairs_bloated_output_to_within_ten_percent(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 0])
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    original_text = (
        "革命纪念馆展陈更新中，变化最先出现在展品位置和参观路线。"
        "观众的叙事线索、互动方式以及交流节奏也会随着展示空间变化。"
    ) * 4
    repaired_text = original_text.replace("最先出现在展品位置和参观路线", "首先体现在展品位置、参观路线", 1)
    fake_ai = BloatedThenLengthRepairAIService(repaired_text)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-length-guard",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text=original_text,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        original_length = count_text_length(original_text)
        reduced_length = count_text_length(segment.zhuque_reduced_text)

        assert session.status == "completed"
        assert reduced_length <= int(original_length * 1.1)
        assert reduced_length >= int(original_length * 0.9)
        assert segment.zhuque_reduced_text == repaired_text
        assert segment.enhanced_text == repaired_text
        assert len(fake_ai.enhance_calls) == 2
        assert "朱雀长度校正" in fake_ai.enhance_calls[1]["prompt"]
        assert fake_zhuque.detected_texts[1] == repaired_text
    finally:
        db.close()


def test_ai_detect_reduce_length_repair_uses_original_segment_length_on_retry(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 0])
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    original_text = (
        "革命纪念馆展陈更新中，数字展示会改变观众的参观路线。"
        "后续研究仍需要结合现场反馈来判断展示效果。"
    ) * 4
    previous_bloated_text = f"{original_text}{'额外解释' * 90}"
    repaired_text = original_text.replace("改变观众的参观路线", "影响观众参观路线", 1)
    fake_ai = BloatedThenLengthRepairAIService(repaired_text)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-length-retry-original-baseline",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="enhance",
            original_text=original_text,
            polished_text=previous_bloated_text,
            enhanced_text=previous_bloated_text,
            zhuque_reduced_text=previous_bloated_text,
            zhuque_reduce_attempt=1,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)
        original_length = count_text_length(original_text)
        reduced_length = count_text_length(segment.zhuque_reduced_text)

        assert session.status == "completed"
        assert fake_zhuque.detected_texts[0] == previous_bloated_text
        assert fake_zhuque.detected_texts[1] == repaired_text
        assert segment.zhuque_reduced_text == repaired_text
        assert reduced_length <= int(original_length * 1.1)
        assert reduced_length >= int(original_length * 0.9)
    finally:
        db.close()


def test_ai_detect_reduce_rewrites_only_segments_marked_ai_by_zhuque_labels(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    segment_texts = ["短段甲" * 60, "短段乙" * 60, "短段丙" * 60, "短段丁" * 60]
    original_text = "\n\n".join(segment_texts)
    joined_text = original_text
    segment_starts = _joined_segment_starts(segment_texts)

    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 80,
                "labels_ratio": {"0": 0.8, "1": 0.2, "2": 0.0},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": 0,
                        "conf": 0.99,
                        "order": 1,
                        "position": [
                            segment_starts[1],
                            len(segment_texts[1]),
                        ],
                    },
                    {
                        "text": segment_texts[3],
                        "label": 0,
                        "conf": 0.98,
                        "order": 2,
                        "position": [
                            segment_starts[3],
                            len(segment_texts[3]),
                        ],
                    },
                ],
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-full-text-detect",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()

        assert session.status == "completed"
        assert fake_zhuque.detected_texts[0] == joined_text
        assert fake_zhuque.detected_texts[1] == "\n\n".join(
            seg.zhuque_reduced_text or seg.original_text for seg in segments
        )
        assert [seg.zhuque_detect_rate for seg in segments] == [12, 12, 12, 12]
        assert [seg.zhuque_detect_count for seg in segments] == [2, 2, 2, 2]
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 1, 0, 1]
        assert [seg.polished_text for seg in segments] == [
            None,
            f"润色后:{segment_texts[1]}",
            None,
            f"润色后:{segment_texts[3]}",
        ]
        assert [seg.enhanced_text for seg in segments] == [
            None,
            f"增强后:润色后:{segment_texts[1]}",
            None,
            f"增强后:润色后:{segment_texts[3]}",
        ]
        assert [seg.zhuque_reduced_text for seg in segments] == [
            None,
            segments[1].enhanced_text,
            None,
            segments[3].enhanced_text,
        ]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[1], segment_texts[3]]
        assert [call["text"] for call in fake_ai.enhance_calls] == [
            segments[1].polished_text,
            segments[3].polished_text,
        ]
        assert user.credit_balance == 30
        assert [(txn.reason, txn.delta) for txn in transactions] == [
            ("zhuque_reduce", -10),
            ("zhuque_reduce", -10),
        ]
    finally:
        db.close()


def test_ai_detect_reduce_page_fallback_segment_labels_skip_fallback_classifier(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)

    segment_texts = ["page段甲" * 60, "page段乙" * 60, "page段丙" * 60]
    original_text = "\n\n".join(segment_texts)
    starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 35.36,
                "risk_rate": 64.64,
                "rate_label": "AI content ratio",
                "labels_ratio": {"0": 0.6464, "1": 0.0085, "2": 0.3451},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": 0,
                        "conf": 0.996,
                        "order": 1,
                        "position": [starts[1], len(segment_texts[1])],
                    }
                ],
                "remaining_uses": 16,
                "source": "page_fallback",
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-page-fallback-segment-labels",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "completed"
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 1, 0]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[1]]
        trace = json.loads(session.zhuque_agent_trace)
        detect_event = next(event for event in trace["events"] if event["type"] == "detect")
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert detect_event["segment_label_count"] == 1
        assert detect_event["usable_position_count"] == 1
        assert classification["label_source"] == "segment_labels"
        assert classification["selected_segment_indices"] == [1]
    finally:
        db.close()


def test_ai_detect_reduce_uses_original_text_offsets_and_never_fallbacks_to_all_on_labels(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)

    segment_texts = [
        "原文结构段甲包含研究背景和方法说明。" * 8,
        "原文结构段乙才是真正需要降AI的正文段落。" * 8,
        "原文结构段丙属于人工特征较明显的正文段落。" * 8,
    ]
    original_text = f"论文标题\n\n{segment_texts[0]}\n\n{segment_texts[1]}\n\n{segment_texts[2]}\n\n附录说明"
    second_start = original_text.index(segment_texts[1])
    tail_start = original_text.index("附录说明")
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 80,
                "labels_ratio": {"0": 0.8, "1": 0.2, "2": 0.0},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": "0",
                        "conf": 0.99,
                        "order": 1,
                        "position": [second_start, len(segment_texts[1])],
                    },
                    {
                        "text": "附录说明",
                        "label": 0,
                        "conf": 0.188,
                        "order": 2,
                        "position": [tail_start, len("附录说明")],
                    },
                ],
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-original-text-offsets-no-full-fallback",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert fake_zhuque.detected_texts[0] == original_text
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 1, 0]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[1]]
        trace = json.loads(session.zhuque_agent_trace)
        detect_event = next(event for event in trace["events"] if event["type"] == "detect")
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert detect_event["detect_text_source"] == "session_original_text"
        assert classification["detect_text_source"] == "session_original_text"
        assert classification["fallback_classifier_used"] is False
        assert classification["high_ai_span_count"] == 1
        assert classification["selected_segment_indices"] == [1]
    finally:
        db.close()


def test_ai_detect_reduce_treats_suspicious_ratio_as_over_threshold(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 0.0,
                "labels_ratio": {"0": 0.0, "1": 0.275, "2": 0.725},
                "segment_labels": [],
                "remaining_uses": 99,
            }
        ]
    )
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-suspicious-over-threshold",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="疑似AI文本" * 80,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="72.5"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "failed"
        assert segment.zhuque_detect_rate == 72.5
        assert fake_ai.polish_calls == []
        assert fake_ai.enhance_calls == []
    finally:
        db.close()


def test_ai_detect_reduce_rewrites_suspicious_segments_but_keeps_human_segments(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    segment_texts = ["疑似段甲" * 50, "疑似段乙" * 50, "人工段丙" * 50]
    original_text = "\n\n".join(segment_texts)
    segment_starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 0.0,
                "labels_ratio": {"0": 0.0, "1": 0.275, "2": 0.725},
                "segment_labels": [
                    {
                        "text": segment_texts[0],
                        "label": 2,
                        "conf": 0.95,
                        "order": 1,
                        "position": [segment_starts[0], len(segment_texts[0])],
                    },
                    {
                        "text": segment_texts[1],
                        "label": 2,
                        "conf": 0.94,
                        "order": 2,
                        "position": [segment_starts[1], len(segment_texts[1])],
                    },
                    {
                        "text": segment_texts[2],
                        "label": 1,
                        "conf": 0.99,
                        "order": 3,
                        "position": [segment_starts[2], len(segment_texts[2])],
                    },
                ],
            },
            10,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-suspicious-only-selected",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        user = db.query(User).filter(User.id == user_id).one()

        assert session.status == "completed"
        assert [seg.zhuque_reduce_attempt for seg in segments] == [1, 1, 0]
        assert [seg.zhuque_reduced_text for seg in segments] == [
            segments[0].enhanced_text,
            segments[1].enhanced_text,
            None,
        ]
        assert [call["text"] for call in fake_ai.polish_calls] == segment_texts[:2]
        assert user.credit_balance == 30
    finally:
        db.close()


def test_ai_detect_reduce_uses_fallback_classifier_when_zhuque_has_no_segment_labels(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 12])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    segment_texts = ["无标签短段甲" * 40, "无标签短段乙" * 40]

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-fallback-all-segments",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "completed"
        assert [seg.zhuque_reduce_attempt for seg in segments] == [1, 1]
        assert [call["text"] for call in fake_ai.polish_calls] == segment_texts
        assert [call["text"] for call in fake_ai.enhance_calls] == [seg.polished_text for seg in segments]
        trace = json.loads(session.zhuque_agent_trace)
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert classification["label_source"] == "fallback_classifier"
        assert classification["selected_segment_indices"] == [0, 1]
    finally:
        db.close()


def test_zhuque_fallback_classifier_protects_front_matter_and_reduces_body(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=80, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 12])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_SKIP_SHORT_CHARS", 30, raising=False)

    segment_texts = [
        "# 摘要",
        "本文提出了一种面向论文文本的检测方法，并在公开数据集上完成验证。" * 3,
        "**关键词：**深度学习；文本检测；Transformer",
        "引言",
        "随着人工智能技术的发展，文本检测任务在学术写作场景中受到关注。" * 3,
        "# 致谢",
        "感谢课题组成员在数据标注和实验设计阶段提供的帮助。" * 3,
        "# 参考文献",
        "[1] Vaswani A, et al. Attention is all you need. 2017.",
    ]

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-fallback-classifier-headings",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 0, 0, 0, 1, 0, 0, 0, 0]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[4]]
        trace = json.loads(session.zhuque_agent_trace)
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert classification["selected_segment_indices"] == [4]
        assert classification["type_counts"]["ABSTRACT_HEADING"] == 1
        assert classification["type_counts"]["ABSTRACT_BODY"] == 1
        assert classification["type_counts"]["ACK_BODY"] == 1
        assert classification["type_counts"]["REFERENCE_ITEM"] == 1
        assert classification["action_counts"]["skip"] == 8
        assert classification["action_counts"]["reduce"] == 1
    finally:
        db.close()


def test_ai_detect_reduce_segment_labels_protect_front_matter_and_references(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=80, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_SKIP_SHORT_CHARS", 30, raising=False)

    segment_texts = [
        "# 摘要",
        "摘要正文说明研究背景、研究对象、研究方法和主要结论，用于论文前置概览。" * 4,
        "**Keywords:** text detection; academic writing; transformer",
        "目 录",
        "[1 绪论 1](#_Toc227222402)",
        "# 1 绪论",
        "正文段落围绕研究背景、研究问题和方法展开，需要在朱雀高风险命中时执行降重。" * 4,
        "# 致谢",
        "感谢导师、同学和家人在论文写作过程中给予的支持与帮助。" * 4,
        "# 参考文献",
        "1. Vaswani A, et al. Attention is all you need. 2017.",
    ]
    original_text = "\n\n".join(segment_texts)
    starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 82,
                "labels_ratio": {"0": 0.82, "1": 0.18, "2": 0.0},
                "segment_labels": [
                    {"label": 0, "conf": 0.99, "position": [starts[1], len(segment_texts[1])]},
                    {"label": 0, "conf": 0.99, "position": [starts[2], len(segment_texts[2])]},
                    {"label": 0, "conf": 0.99, "position": [starts[4], len(segment_texts[4])]},
                    {"label": 0, "conf": 0.99, "position": [starts[6], len(segment_texts[6])]},
                    {"label": 0, "conf": 0.99, "position": [starts[8], len(segment_texts[8])]},
                    {"label": 0, "conf": 0.99, "position": [starts[10], len(segment_texts[10])]},
                ],
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-segment-labels-protect-front-matter",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[6]]
        trace = json.loads(session.zhuque_agent_trace)
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert classification["label_source"] == "segment_labels"
        assert classification["pre_filter_selected_count"] == 6
        assert classification["classifier_filtered_count"] == 5
        assert classification["selected_segment_indices"] == [6]
        assert classification["type_counts"]["ABSTRACT_BODY"] == 1
        assert classification["type_counts"]["KEYWORDS"] == 1
        assert classification["type_counts"]["TOC_HEADING"] == 1
        assert classification["type_counts"]["TOC_ITEM"] == 1
        assert classification["type_counts"]["ACK_BODY"] == 1
        assert classification["type_counts"]["REFERENCE_ITEM"] == 1
    finally:
        db.close()


def test_ai_detect_reduce_segment_labels_use_stored_semantic_metadata(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=80, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)

    segment_texts = [
        "这是一段由解析器确认的摘要正文，即使没有摘要标题上下文也必须受保护。" * 4,
        "正文段落由解析器确认为 BODY，朱雀命中后应该进入真实降重流程。" * 4,
    ]
    original_text = "\n\n".join(segment_texts)
    starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 88,
                "labels_ratio": {"0": 0.88, "1": 0.12, "2": 0.0},
                "segment_labels": [
                    {"label": "0", "conf": 0.99, "position": [starts[0], len(segment_texts[0])]},
                    {"label": "0", "conf": 0.99, "position": [starts[1], len(segment_texts[1])]},
                ],
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-segment-labels-stored-semantic",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            parse_engine="python_docx",
            parse_fallback_used=False,
        )
        db.add(session)
        db.flush()
        db.add(
            OptimizationSegment(
                session_id=session.id,
                segment_index=0,
                stage="ai_detect_reduce",
                original_text=segment_texts[0],
                status="pending",
                semantic_type="ABSTRACT_BODY",
                semantic_source="docx_style",
                semantic_confidence=0.97,
                reduce_allowed=False,
                semantic_reason="stored_abstract_body",
            )
        )
        db.add(
            OptimizationSegment(
                session_id=session.id,
                segment_index=1,
                stage="ai_detect_reduce",
                original_text=segment_texts[1],
                status="pending",
                semantic_type="BODY",
                semantic_source="docx_style",
                semantic_confidence=0.93,
                reduce_allowed=True,
                semantic_reason="stored_body",
            )
        )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 1]
        assert [call["text"] for call in fake_ai.polish_calls] == [segment_texts[1]]
        trace = json.loads(session.zhuque_agent_trace)
        classification = next(event for event in trace["events"] if event["type"] == "segment_classification")
        assert classification["label_source"] == "segment_labels"
        assert classification["pre_filter_selected_count"] == 2
        assert classification["classifier_filtered_count"] == 1
        assert classification["selected_segment_indices"] == [1]
        assert classification["filtered_semantic_summary"] == {"ABSTRACT_BODY": 1}
        assert classification["protected_samples"][0]["semantic_source"] == "docx_style"
        assert classification["parse_engine"] == "python_docx"
        assert classification["parse_fallback_used"] is False
    finally:
        db.close()


def test_ai_detect_reduce_batch_polish_and_enhance_records_agent_trace(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=80, zhuque_free_uses_remaining=20)
    fake_ai = FakeBatchAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", True, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_SIZE", 3, raising=False)

    segment_texts = [
        "批量降重段落甲包含模型方法、实验数据和结论说明。" * 4,
        "批量降重段落乙描述数据来源、评价指标和对比结果。" * 4,
    ]
    original_text = "\n\n".join(segment_texts)
    starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 80,
                "labels_ratio": {"0": 0.8, "1": 0.2, "2": 0.0},
                "segment_labels": [
                    {"label": 0, "position": [starts[0], len(segment_texts[0])]},
                    {"label": 0, "position": [starts[1], len(segment_texts[1])]},
                ],
            },
            12,
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-batch-trace",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        assert session.status == "completed"
        assert len(fake_ai.complete_calls) == 2
        assert fake_ai.polish_calls == []
        assert fake_ai.enhance_calls == []
        assert [seg.zhuque_reduce_attempt for seg in segments] == [1, 1]
        assert [seg.polished_text for seg in segments] == [f"润色后:{text}" for text in segment_texts]
        assert [seg.zhuque_reduced_text for seg in segments] == [f"增强后:润色后:{text}" for text in segment_texts]
        trace = json.loads(session.zhuque_agent_trace)
        event_types = [event["type"] for event in trace["events"]]
        assert event_types.count("batch_plan") == 2
        assert event_types.count("batch_stage") == 2
        assert any(event["type"] == "batch_plan" and event["saved_llm_calls"] == 1 for event in trace["events"])
        assert all("批量降重段落甲" not in json.dumps(event, ensure_ascii=False) for event in trace["events"])
    finally:
        db.close()


def test_ai_detect_reduce_leaves_original_segments_when_full_text_is_below_threshold(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([10])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    segment_texts = ["人工短段甲" * 20, "人工短段乙" * 20]
    original_text = "\n\n".join(segment_texts)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-full-text-low-ai",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        user = db.query(User).filter(User.id == user_id).one()
        transactions = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id).all()

        assert session.status == "completed"
        assert fake_zhuque.detected_texts == ["\n\n".join(segment_texts)]
        assert [seg.zhuque_detect_rate for seg in segments] == [10, 10]
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 0]
        assert [seg.zhuque_reduced_text for seg in segments] == [None, None]
        assert fake_ai.polish_calls == []
        assert fake_ai.enhance_calls == []
        assert user.credit_balance == 50
        assert transactions == []
    finally:
        db.close()


def test_ai_detect_reduce_fails_when_rate_stays_above_threshold_after_max_rounds(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 100])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 1, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-still-high-after-max-rounds",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="高AI文本" * 80,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="仍高于阈值"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "failed"
        assert "100" in session.error_message
        assert segment.zhuque_detect_rate == 100
        assert segment.zhuque_detect_count == 1
        assert segment.zhuque_reduce_attempt == 1
        assert segment.polished_text is None
        assert segment.enhanced_text is None
        assert segment.zhuque_reduced_text is None
    finally:
        db.close()


def test_ai_detect_reduce_retry_continues_from_latest_reduced_text(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=50, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([80, 10])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    original_text = "原始高AI文本" * 80
    latest_reduced_text = "上一轮最新降重文本" * 40

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-retry-from-latest-reduced",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="enhance",
            original_text=original_text,
            polished_text="上一轮润色文本",
            enhanced_text=latest_reduced_text,
            zhuque_reduced_text=latest_reduced_text,
            zhuque_reduce_attempt=5,
            status="failed",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "completed"
        assert fake_zhuque.detected_texts[0] == latest_reduced_text
        assert fake_ai.polish_calls[0]["text"] == latest_reduced_text
        assert segment.zhuque_reduce_attempt == 6
        assert segment.polished_text == f"润色后:{latest_reduced_text}"
        assert segment.enhanced_text == f"增强后:{segment.polished_text}"
        assert segment.zhuque_reduced_text == segment.enhanced_text
        assert fake_zhuque.detected_texts[1] == segment.zhuque_reduced_text
    finally:
        db.close()


def test_ai_detect_reduce_retry_failure_reports_cumulative_rounds(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([95, 90, 85, 80, 75, 70])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    original_text = "原始高AI文本" * 80
    latest_reduced_text = "失败任务最新降重文本" * 40

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-retry-cumulative-failure",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="enhance",
            original_text=original_text,
            polished_text="上一轮润色文本",
            enhanced_text=latest_reduced_text,
            zhuque_reduced_text=latest_reduced_text,
            zhuque_reduce_attempt=5,
            status="failed",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)

        with pytest.raises(RuntimeError, match="累计 10 轮"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "failed"
        assert "本次已完成 5 轮" in session.error_message
        assert "累计 10 轮" in session.error_message
        assert fake_zhuque.detected_texts[0] == latest_reduced_text
        assert fake_ai.polish_calls[0]["text"] == latest_reduced_text
        assert segment.zhuque_reduce_attempt == 10
        assert fake_zhuque.detected_texts[-1] == segment.zhuque_reduced_text
    finally:
        db.close()


def test_ai_detect_reduce_escalates_humanize_strategy_when_rate_does_not_drop(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 100, 100, 10])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 3, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-evolution-strategy",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "completed"
        assert segment.zhuque_reduce_attempt == 3
        assert len(fake_ai.polish_calls) == 3
        assert "策略：轻度自然化" in fake_ai.polish_calls[0]["prompt"]
        assert "策略：句式重组" in fake_ai.polish_calls[1]["prompt"]
        assert "策略：强结构重写" in fake_ai.polish_calls[2]["prompt"]
        assert "必须保留专业术语" in fake_ai.polish_calls[2]["prompt"]
        assert "不得改变原文意思" in fake_ai.enhance_calls[2]["prompt"]
        assert "朱雀逃逸改写" in fake_ai.polish_calls[2]["prompt"]
        assert "朱雀逃逸改写" in fake_ai.enhance_calls[2]["prompt"]
        assert "原文事实锚点" in fake_ai.polish_calls[2]["prompt"]
        assert "Nature / Science" not in fake_ai.polish_calls[2]["prompt"]
        assert "风格拟态专家" not in fake_ai.enhance_calls[2]["prompt"]

        trace = json.loads(session.zhuque_agent_trace)
        reduce_events = [event for event in trace["events"] if event["type"] == "reduce"]
        assert reduce_events[0]["rewrite_mode"] == "standard"
        assert reduce_events[1]["rewrite_mode"] == "standard"
        assert reduce_events[2]["rewrite_mode"] == "breakthrough"
    finally:
        db.close()


def test_ai_detect_reduce_activates_breakthrough_on_first_strong_stagnation(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 10])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 2, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-breakthrough-no-lag",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps({
                "version": 1,
                "threshold": 20.0,
                "events": [
                    {
                        "type": "reflection",
                        "round": 2,
                        "stagnation_count": 1,
                        "stubborn_segment_indices": [0],
                    }
                ],
            }, ensure_ascii=False),
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            zhuque_reduced_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            zhuque_reduce_attempt=2,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)

        assert session.status == "completed"
        assert len(fake_ai.polish_calls) == 1
        assert "策略：强结构重写" in fake_ai.polish_calls[0]["prompt"]
        assert "朱雀逃逸改写" in fake_ai.polish_calls[0]["prompt"]
        assert "Nature / Science" not in fake_ai.polish_calls[0]["prompt"]

        trace = json.loads(session.zhuque_agent_trace)
        reduce_events = [event for event in trace["events"] if event["type"] == "reduce"]
        assert reduce_events[-1]["rewrite_mode"] == "breakthrough"
    finally:
        db.close()


def test_ai_detect_reduce_uses_paper_reconstruction_for_repeated_paper_stagnation(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 10])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 3, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-paper-reconstruction",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps({
                "version": 1,
                "threshold": 20.0,
                "events": [
                    {
                        "type": "reflection",
                        "round": 5,
                        "stagnation_count": 2,
                        "stubborn_segment_indices": [0],
                    }
                ],
            }, ensure_ascii=False),
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text=(
                "本文围绕深度学习模型在医学影像分割任务中的应用展开研究。"
                "通过构建多尺度特征融合机制，模型能够有效提升边界区域识别能力，"
                "进一步为临床辅助诊断提供重要支撑。"
            ) * 8,
            zhuque_reduced_text=(
                "本文围绕深度学习模型在医学影像分割任务中的应用展开研究。"
                "通过构建多尺度特征融合机制，模型能够有效提升边界区域识别能力，"
                "进一步为临床辅助诊断提供重要支撑。"
            ) * 8,
            zhuque_reduce_attempt=5,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)

        assert session.status == "completed"
        assert len(fake_ai.polish_calls) == 1
        assert "rewrite_mode: paper_reconstruction" in fake_ai.polish_calls[0]["prompt"]
        assert "论文事实卡片" in fake_ai.polish_calls[0]["prompt"]
        assert "中文论文 AI 痕迹规则" in fake_ai.polish_calls[0]["prompt"]
        assert "候选 A" in fake_ai.polish_calls[0]["prompt"]
        assert "本地 AI 痕迹自检" in fake_ai.enhance_calls[0]["prompt"]
        assert "字数控制在原段落 90%-110%" in fake_ai.enhance_calls[0]["prompt"]

        trace = json.loads(session.zhuque_agent_trace)
        paper_events = [event for event in trace["events"] if event.get("rewrite_mode") == "paper_reconstruction"]
        assert paper_events
        paper_event = paper_events[0]
        assert paper_event["paper_language"] == "zh"
        assert "template_transition" in paper_event["paper_ai_patterns"]
        assert paper_event["candidate_count"] == 3
        assert paper_event["candidate_selector"] == "local_ai_pattern_score"
        assert paper_event["fact_card_count"] >= 1
    finally:
        db.close()


def test_ai_detect_reduce_rolls_back_round_when_recheck_rate_regresses(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 35, 100, 35])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 2, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-regression-rollback",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="仍高于阈值"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        first_good_text = fake_zhuque.detected_texts[1]
        assert segment.zhuque_reduced_text == first_good_text
        assert len(fake_zhuque.detected_texts) == 3
        assert fake_zhuque.detected_texts[-1] != first_good_text
        assert segment.zhuque_detect_rate == 35

        trace = json.loads(session.zhuque_agent_trace)
        rollback_events = [event for event in trace["events"] if event.get("rollback_applied")]
        assert rollback_events
        assert rollback_events[0]["rolled_back_from_rate"] == 100
        assert rollback_events[0]["rolled_back_to_rate"] == 35
        assert "回滚保护" in rollback_events[0]["message"]
    finally:
        db.close()


def test_ai_detect_reduce_rejects_equal_rate_rewrite_without_extra_recheck(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([100, 45.1, 45.1])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 2, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-equal-rate-rollback",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="仍高于阈值"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        first_good_text = fake_zhuque.detected_texts[1]
        assert segment.zhuque_reduced_text == first_good_text
        assert len(fake_zhuque.detected_texts) == 3
        assert segment.zhuque_detect_rate == 45.1

        trace = json.loads(session.zhuque_agent_trace)
        rollback_events = [event for event in trace["events"] if event.get("rollback_applied")]
        assert rollback_events
        assert rollback_events[0]["rollback_reason"] == "not_improved"
        assert rollback_events[0]["rolled_back_from_rate"] == 45.1
        assert rollback_events[0]["rolled_back_to_rate"] == 45.1
    finally:
        db.close()


def test_ai_detect_reduce_rollback_restores_full_text_detect_metadata_for_all_segments(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 2, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    segment_texts = ["短段甲" * 60, "短段乙" * 60]
    original_text = "\n\n".join(segment_texts)
    segment_starts = _joined_segment_starts(segment_texts)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 80,
                "labels_ratio": {"0": 0.8, "1": 0.2, "2": 0.0},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": 0,
                        "position": [segment_starts[1], len(segment_texts[1])],
                    }
                ],
            },
            {
                "success": True,
                "rate": 45,
                "labels_ratio": {"0": 0.45, "1": 0.55, "2": 0.0},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": 0,
                        "position": [segment_starts[1], len(segment_texts[1])],
                    }
                ],
            },
            {
                "success": True,
                "rate": 45,
                "labels_ratio": {"0": 0.45, "1": 0.55, "2": 0.0},
                "segment_labels": [
                    {
                        "text": segment_texts[1],
                        "label": 0,
                        "position": [segment_starts[1], len(segment_texts[1])],
                    }
                ],
            },
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-rollback-full-metadata",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="仍高于阈值"):
            asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert [seg.zhuque_detect_rate for seg in segments] == [45, 45]
        assert [seg.zhuque_detect_count for seg in segments] == [2, 2]
        assert [json.loads(seg.zhuque_detect_result)["rate"] for seg in segments] == [45, 45]
        assert segments[0].zhuque_reduced_text is None
        assert segments[1].zhuque_reduced_text == fake_zhuque.detected_texts[1].split("\n\n")[1]

        trace = json.loads(session.zhuque_agent_trace)
        rollback_events = [event for event in trace["events"] if event.get("rollback_applied")]
        assert rollback_events[0]["restored_segment_indices"] == [1]
    finally:
        db.close()


def test_ai_detect_reduce_rescreens_and_only_rewrites_remaining_high_ai_segments(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=80, zhuque_free_uses_remaining=20)
    fake_ai = FakeAIService()
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 2, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_REDUCE_BATCH_ENABLED", False, raising=False)

    segment_texts = ["复筛段甲" * 60, "复筛段乙" * 60, "复筛段丙" * 60]
    original_text = "\n\n".join(segment_texts)
    initial_starts = _joined_segment_starts(segment_texts)
    first_round_outputs = [
        segment_texts[0],
        f"增强后:润色后:{segment_texts[1]}",
        f"增强后:润色后:{segment_texts[2]}",
    ]
    recheck_starts = _joined_segment_starts(first_round_outputs)
    fake_zhuque = FakeZhuqueService(
        [
            {
                "success": True,
                "rate": 80,
                "labels_ratio": {"0": 0.8, "1": 0.2, "2": 0.0},
                "segment_labels": [
                    {"label": 0, "position": [initial_starts[1], len(segment_texts[1])]},
                    {"label": 0, "position": [initial_starts[2], len(segment_texts[2])]},
                ],
            },
            {
                "success": True,
                "rate": 45,
                "labels_ratio": {"0": 0.45, "1": 0.55, "2": 0.0},
                "segment_labels": [
                    {"label": 0, "position": [recheck_starts[2], len(first_round_outputs[2])]},
                ],
            },
            {
                "success": True,
                "rate": 12,
                "labels_ratio": {"0": 0.12, "1": 0.88, "2": 0.0},
                "segment_labels": [],
            },
        ]
    )
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-rescreen-only-remaining",
            original_text=original_text,
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index, text in enumerate(segment_texts):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )
        assert session.status == "completed"
        assert [call["text"] for call in fake_ai.polish_calls] == [
            segment_texts[1],
            segment_texts[2],
            first_round_outputs[2],
        ]
        assert [seg.zhuque_reduce_attempt for seg in segments] == [0, 1, 2]
        trace = json.loads(session.zhuque_agent_trace)
        label_events = [
            event for event in trace["events"]
            if event["type"] == "segment_classification" and event.get("label_source") == "segment_labels"
        ]
        assert [event["selected_segment_indices"] for event in label_events] == [[1, 2], [2]]
        detect_events = [event for event in trace["events"] if event["type"] == "detect"]
        assert detect_events[0]["segment_label_count"] == 2
        assert detect_events[1]["segment_label_count"] == 1
        assert detect_events[1]["position_format"] == "start_length"
    finally:
        db.close()


def test_ai_detect_reduce_plateau_recovery_accepts_best_auto_candidate(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([25, 25, 24, 18])
    fake_ai = PlateauRecoveryAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-plateau-recovery-success",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps(
                {
                    "version": 1,
                    "threshold": 20,
                    "events": [
                        {
                            "type": "reflection",
                            "round": 9,
                            "stagnation_count": 2,
                            "stubborn_segment_indices": [0, 1],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.add(session)
        db.flush()
        for index in range(2):
            text = "自动探索B上一版低风险文本"
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    polished_text=f"上一版润色:{index}",
                    enhanced_text=f"上一版增强:{index}",
                    zhuque_reduced_text=f"上一版低风险文本:{index}",
                    zhuque_reduce_attempt=10,
                    zhuque_detect_rate=25,
                    zhuque_detect_count=10,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "completed"
        assert len(fake_zhuque.detected_texts) == 4
        assert [seg.zhuque_reduced_text for seg in segments] == [
            "自动探索B:上一版低风险文本:0",
            "自动探索B:上一版低风险文本:1",
        ]
        assert any("卡点候选A" in call["prompt"] for call in fake_ai.polish_calls)
        assert any("卡点候选B" in call["prompt"] for call in fake_ai.polish_calls)

        trace = json.loads(session.zhuque_agent_trace)
        recovery_events = [event for event in trace["events"] if event.get("type") == "plateau_recovery"]
        assert recovery_events
        assert recovery_events[0]["status"] == "accepted"
        assert recovery_events[0]["candidate_count"] == 2
        assert recovery_events[0]["selected_candidate_id"] == "B"
        assert trace["final"]["status"] == "completed"
    finally:
        db.close()


def test_ai_detect_reduce_plateau_recovery_sweeps_stubborn_segments_after_bulk_candidates_fail(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=200, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([25, 25, 25, 25, 25, 18])
    fake_ai = PlateauRecoveryAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-plateau-recovery-segment-sweep",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps(
                {
                    "version": 1,
                    "threshold": 20,
                    "events": [
                        {
                            "type": "reflection",
                            "round": 9,
                            "stagnation_count": 2,
                            "stubborn_segment_indices": [0, 1],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.add(session)
        db.flush()
        for index in range(2):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text="局部探索上一版低风险文本",
                    polished_text=f"上一版润色:{index}",
                    enhanced_text=f"上一版增强:{index}",
                    zhuque_reduced_text=f"上一版低风险文本:{index}",
                    zhuque_reduce_attempt=10,
                    zhuque_detect_rate=25,
                    zhuque_detect_count=10,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "completed"
        assert len(fake_zhuque.detected_texts) == 6
        assert [seg.zhuque_reduced_text for seg in segments] == [
            "局部探索S1:上一版低风险文本:0",
            "上一版低风险文本:1",
        ]
        assert any("卡点候选C" in call["prompt"] for call in fake_ai.polish_calls)
        assert any("逐段候选S1" in call["prompt"] for call in fake_ai.polish_calls)

        trace = json.loads(session.zhuque_agent_trace)
        recovery_events = [event for event in trace["events"] if event.get("type") == "plateau_recovery"]
        assert recovery_events
        assert recovery_events[-1]["status"] == "accepted"
        assert recovery_events[-1]["candidate_count"] == 4
        assert recovery_events[-1]["selected_candidate_id"] == "S1:0"
        assert recovery_events[-1]["selected_candidate_phase"] == "segment_sweep"
        assert trace["final"]["status"] == "completed"
    finally:
        db.close()


def test_ai_detect_reduce_exits_plateau_only_after_auto_candidates_fail(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=200, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30])
    fake_ai = PlateauRecoveryAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-plateau-recovery-failed",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps(
                {
                    "version": 1,
                    "threshold": 20,
                    "events": [
                        {
                            "type": "reflection",
                            "round": 9,
                            "stagnation_count": 2,
                            "stubborn_segment_indices": [0, 1],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.add(session)
        db.flush()
        for index in range(2):
            text = "自动探索B上一版低风险文本"
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    polished_text=f"上一版润色:{index}",
                    enhanced_text=f"上一版增强:{index}",
                    zhuque_reduced_text=f"上一版低风险文本:{index}",
                    zhuque_reduce_attempt=10,
                    zhuque_detect_rate=30,
                    zhuque_detect_count=10,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="自动探索候选仍未突破"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "failed"
        assert len(fake_zhuque.detected_texts) == 12
        assert [seg.zhuque_reduced_text for seg in segments] == [
            "上一版低风险文本:0",
            "上一版低风险文本:1",
        ]

        trace = json.loads(session.zhuque_agent_trace)
        recovery_events = [event for event in trace["events"] if event.get("type") == "plateau_recovery"]
        assert recovery_events
        assert recovery_events[-1]["status"] == "failed"
        assert recovery_events[-1]["candidate_count"] == 10
        assert any(
            item.get("phase") == "segment_sweep"
            for item in recovery_events[-1]["candidate_rates"]
        )
        deep_events = [event for event in trace["events"] if event.get("type") == "plateau_deep_reconstruction"]
        assert deep_events
        assert deep_events[-1]["status"] == "failed"
        plateau_events = [event for event in trace["events"] if event.get("type") == "plateau_exit"]
        assert plateau_events
        assert plateau_events[0]["action"] == "auto_recovery_exhausted"
    finally:
        db.close()


def test_ai_detect_reduce_deep_reconstruction_runs_after_plateau_candidates_fail(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=300, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([25, 25, 25, 25, 25, 25, 25, 25, 25, 18])
    fake_ai = DeepReconstructionAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-deep-reconstruction-success",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps(
                {
                    "version": 1,
                    "threshold": 20,
                    "events": [
                        {
                            "type": "reflection",
                            "round": 9,
                            "stagnation_count": 2,
                            "stubborn_segment_indices": [0, 1],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.add(session)
        db.flush()
        for index in range(2):
            text = f"上一版低风险文本{index}" * 14
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=text,
                    polished_text=f"上一版润色:{index}",
                    enhanced_text=f"上一版增强:{index}",
                    zhuque_reduced_text=text,
                    zhuque_reduce_attempt=10,
                    zhuque_detect_rate=25,
                    zhuque_detect_count=10,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "completed"
        assert len(fake_zhuque.detected_texts) == 10
        assert [seg.zhuque_reduced_text for seg in segments] == [
            f"深度重构证据优先:{'上一版低风险文本0' * 14}",
            f"深度重构证据优先:{'上一版低风险文本1' * 14}",
        ]
        assert any("深度重构路线:evidence_first" in call["prompt"] for call in fake_ai.polish_calls)

        trace = json.loads(session.zhuque_agent_trace)
        deep_events = [event for event in trace["events"] if event.get("type") == "plateau_deep_reconstruction"]
        assert deep_events
        assert deep_events[-1]["status"] == "accepted"
        assert deep_events[-1]["selected_route"] == "evidence_first"
        assert deep_events[-1]["candidate_count"] == 1
        assert deep_events[-1]["fact_card_count"] >= 1
        assert trace["final"]["status"] == "completed"
    finally:
        db.close()


def test_ai_detect_reduce_marks_detector_floor_when_all_safe_candidates_flatline(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=300, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([24.52] * 12)
    fake_ai = DeepReconstructionAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 5, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-detector-floor",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
            zhuque_agent_trace=json.dumps(
                {
                    "version": 1,
                    "threshold": 20,
                    "events": [
                        {
                            "type": "reflection",
                            "round": 9,
                            "stagnation_count": 2,
                            "stubborn_segment_indices": [0, 1],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
        db.add(session)
        db.flush()
        for index in range(2):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 12,
                    polished_text=f"上一版润色:{index}",
                    enhanced_text=f"上一版增强:{index}",
                    zhuque_reduced_text=f"上一版低风险文本:{index}",
                    zhuque_reduce_attempt=10,
                    zhuque_detect_rate=24.52,
                    zhuque_detect_count=10,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="检测地板"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        segments = (
            db.query(OptimizationSegment)
            .filter(OptimizationSegment.session_id == session.id)
            .order_by(OptimizationSegment.segment_index)
            .all()
        )

        assert session.status == "failed"
        assert [seg.zhuque_reduced_text for seg in segments] == [
            "上一版低风险文本:0",
            "上一版低风险文本:1",
        ]

        trace = json.loads(session.zhuque_agent_trace)
        floor_events = [event for event in trace["events"] if event.get("type") == "detector_floor"]
        assert floor_events
        assert floor_events[-1]["rate"] == 24.52
        assert floor_events[-1]["recommended_threshold"] == 26.0
        assert floor_events[-1]["rate_spread"] == 0.0
        assert "检测地板" in trace["final"]["diagnosis"]
    finally:
        db.close()


def test_ai_detect_reduce_reflects_minor_drops_and_marks_stubborn_segments(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=100, zhuque_free_uses_remaining=20)
    fake_zhuque = FakeZhuqueService([
        {"rate": 80, "labels_ratio": {"0": 0.2, "1": 0.0, "2": 0.8}},
        {"rate": 79.8, "labels_ratio": {"0": 0.0, "1": 0.202, "2": 0.798}},
        {"rate": 79.6, "labels_ratio": {"0": 0.0, "1": 0.204, "2": 0.796}},
        {"rate": 10, "labels_ratio": {"0": 0.0, "1": 0.9, "2": 0.1}},
    ])
    fake_ai = FakeAIService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: _install_fake_ai_services(self, fake_ai))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_THRESHOLD", 20.0, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_MAX_REDUCE_ROUNDS", 3, raising=False)
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-convergence-reflection",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        segment = OptimizationSegment(
            session_id=session.id,
            segment_index=0,
            stage="ai_detect_reduce",
            original_text="深度学习模型在医学影像分割任务中保持Dice系数稳定。" * 30,
            status="pending",
        )
        db.add(segment)
        db.commit()

        service = OptimizationService(db, session)
        asyncio.run(service.start_optimization())

        db.refresh(session)
        db.refresh(segment)

        assert session.status == "completed"
        assert segment.zhuque_reduce_attempt == 3
        assert "策略：轻度自然化" in fake_ai.polish_calls[0]["prompt"]
        assert "策略：句式重组" in fake_ai.polish_calls[1]["prompt"]
        assert "策略：强结构重写" in fake_ai.polish_calls[2]["prompt"]
        assert "顽固段落强改写策略" in fake_ai.polish_calls[2]["prompt"]

        trace = json.loads(session.zhuque_agent_trace)
        reduce_events = [event for event in trace["events"] if event["type"] == "reduce"]
        reflection_events = [event for event in trace["events"] if event["type"] == "reflection"]
        evolution_events = [event for event in trace["events"] if event["type"] == "prompt_evolution"]

        assert reduce_events[0]["decision"] == "minor_drop_upgrade_strategy"
        assert reduce_events[1]["decision"] == "minor_drop_upgrade_strategy"
        assert len(reflection_events) >= 2
        assert reflection_events[0]["stagnation_count"] == 1
        assert reflection_events[0]["stubborn_segment_indices"] == [0]
        assert reflection_events[0]["next_strategy"] == "句式重组"
        assert reflection_events[1]["stagnation_count"] == 2
        assert reflection_events[1]["action"] == "force_stronger_strategy"
        assert reflection_events[1]["next_strategy"] == "强结构重写"
        assert "连续" in reflection_events[1]["message"]
        assert evolution_events
        assert evolution_events[0]["source"] in {"fallback", "memory"}
        assert evolution_events[0]["safety_status"] == "safe"
        assert evolution_events[0]["failure_signature"]["dominant_label"] == "suspicious"
        assert "顽固段落强改写策略" in evolution_events[0]["prompt_patch"]
        memory = db.query(ZhuquePromptMemory).filter(ZhuquePromptMemory.id == evolution_events[0]["memory_id"]).one()
        assert memory.uses >= 1
    finally:
        db.close()


def test_ai_detect_reduce_preflights_zhuque_before_segment_loop(monkeypatch):
    import app.services.optimization_service as optimization_service_module

    user_id = _create_user(credit_balance=20, zhuque_free_uses_remaining=20)
    fake_zhuque = UnavailableZhuqueService()
    monkeypatch.setattr(optimization_service_module, "zhuque_service", fake_zhuque)

    init_calls = []
    monkeypatch.setattr(OptimizationService, "_init_ai_services", lambda self: init_calls.append(self.session_obj.session_id))
    monkeypatch.setattr(optimization_service_module.settings, "ZHUQUE_DETECT_INTERVAL", 0, raising=False)

    db = SessionLocal()
    try:
        session = OptimizationSession(
            user_id=user_id,
            session_id="zhuque-preflight-fails",
            original_text="原始文本",
            current_stage="ai_detect_reduce",
            status="queued",
            processing_mode="ai_detect_reduce",
            billing_mode="platform",
            charge_status="not_charged",
        )
        db.add(session)
        db.flush()
        for index in range(2):
            db.add(
                OptimizationSegment(
                    session_id=session.id,
                    segment_index=index,
                    stage="ai_detect_reduce",
                    original_text=f"待检测文本{index}" * 50,
                    status="pending",
                )
            )
        db.commit()

        service = OptimizationService(db, session)
        with pytest.raises(RuntimeError, match="微信扫码凭证不可用"):
            asyncio.run(service.start_optimization())

        db.refresh(session)
        assert fake_zhuque.start_calls == 1
        assert fake_zhuque.detect_calls == 0
        assert init_calls == []
        assert session.status == "failed"
        assert "微信扫码凭证不可用" in session.error_message
        assert "微信扫码登录朱雀" in session.error_message
        assert "无头 API" in session.error_message
    finally:
        db.close()
