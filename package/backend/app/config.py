from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Mapping, Optional
import os
import sys

from app.utils.secret_files import read_secret_file

DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_APP_VERSION = "2.1.0"


def _normalize_app_version(value: str) -> str:
    value = value.strip()
    return value[1:] if value.startswith("v") else value


def _candidate_version_dirs(app_dir: str | None = None) -> list[str]:
    candidates = [
        app_dir,
        os.environ.get("GANKAIGC_APP_DIR"),
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None,
        os.getcwd(),
    ]
    return [path for path in candidates if path]


def read_app_version(app_dir: str | None = None) -> str:
    for search_dir in _candidate_version_dirs(app_dir):
        version_file = os.path.join(search_dir, "VERSION")
        if os.path.exists(version_file):
            try:
                value = open(version_file, encoding="utf-8-sig").read().strip()
            except OSError:
                value = ""
            if value:
                return _normalize_app_version(value)
    env_version = os.environ.get("GANKAIGC_VERSION", "").strip()
    if env_version:
        return _normalize_app_version(env_version)
    return DEFAULT_APP_VERSION


APP_VERSION = read_app_version()
SERVER_DEPLOYMENT_ENVS = {"production", "staging", "server"}
PLACEHOLDER_SECRET_VALUES = {
    "",
    DEFAULT_SECRET_KEY,
    "please-change-this-to-a-random-string-32-chars",
}
PLACEHOLDER_ADMIN_PASSWORD_VALUES = {
    "",
    DEFAULT_ADMIN_PASSWORD,
    "please-change-this-password",
}
PLACEHOLDER_MARKERS = (
    "please-change",
    "change-this",
    "replace-me",
    "your-secret-key",
    "your-admin-password",
)
MIN_SECRET_KEY_LENGTH = 16
MIN_ADMIN_PASSWORD_LENGTH = 8
DEFAULT_DATABASE_URL = "postgresql://ai_polish:postgres@127.0.0.1:5432/ai_polish"
SECRET_FILE_SETTINGS = (
    "DATABASE_URL",
    "SECRET_KEY",
    "ADMIN_PASSWORD",
    "ENCRYPTION_KEY",
    "OPENAI_API_KEY",
    "POLISH_API_KEY",
    "ENHANCE_API_KEY",
    "EMOTION_API_KEY",
    "COMPRESSION_API_KEY",
    "MINERU_API_TOKEN",
)


def get_exe_dir():
    """获取 exe 所在目录，用于定位 .env 文件"""
    if getattr(sys, 'frozen', False):
        # 运行在 PyInstaller 打包的 exe 中
        return os.path.dirname(sys.executable)
    else:
        # 正常 Python 运行
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_env_file_path():
    """获取 .env 文件路径"""
    runtime_env_file = os.environ.get("GANKAIGC_ENV_FILE")
    if runtime_env_file:
        return runtime_env_file
    return os.path.join(get_exe_dir(), '.env')


def read_secret_file_values() -> dict[str, str]:
    """Return allowlisted ``*_FILE`` values, with files authoritative over env."""
    values: dict[str, str] = {}
    for setting_name in SECRET_FILE_SETTINGS:
        file_path = os.environ.get(f"{setting_name}_FILE", "").strip()
        if file_path:
            values[setting_name] = read_secret_file(f"{setting_name}_FILE", file_path)
    return values


def get_file_backed_settings() -> frozenset[str]:
    return frozenset(
        setting_name
        for setting_name in SECRET_FILE_SETTINGS
        if os.environ.get(f"{setting_name}_FILE", "").strip()
    )


class Settings(BaseSettings):
    APP_VERSION: str = APP_VERSION
    RELEASE_REPO: str = "mumu-0922/GankAIGC"

    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 9800
    APP_ENV: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:9800"
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"
    AUTO_OPEN_BROWSER: bool = True
    ALLOW_LOCAL_MODEL_PROXY: bool = False

    # 数据库配置 - 仅支持 PostgreSQL
    DATABASE_URL: str = DEFAULT_DATABASE_URL
    # Optional NOLOGIN owner assumed only by the one-shot migrator.
    DATABASE_SESSION_ROLE: str = ""
    
    # Redis 配置
    REDIS_URL: str = "redis://IP:6379/0"
    ENCRYPTION_KEY: str = ""
    
    # OpenAI API 配置
    OPENAI_API_KEY: str = "pwd"
    OPENAI_BASE_URL: str = "http://IP:PORT/v1"
    MODEL_PROVIDER_NAME: str = ""
    MODEL_API_FORMAT: str = "openai_chat"
    ENABLE_VERBOSE_AI_LOGS: bool = False
    
    # 第一阶段模型配置 (论文润色)
    POLISH_MODEL: str = "gpt-5"
    POLISH_API_KEY: Optional[str] = None
    POLISH_BASE_URL: Optional[str] = None
    
    # 第二阶段模型配置 (原创性增强)
    ENHANCE_MODEL: str = "gpt-5"
    ENHANCE_API_KEY: Optional[str] = None
    ENHANCE_BASE_URL: Optional[str] = None
    
    # 并发配置
    MAX_CONCURRENT_USERS: int = 5
    API_KEY_CONCURRENCY: int = 2
    MAX_PENDING_SESSIONS_PER_USER: int = 3
    TASK_WORKER_MAX_CONCURRENCY: int = 10
    DEFAULT_USAGE_LIMIT: int = 1
    SEGMENT_SKIP_THRESHOLD: int = 15

    # 实验性 Word Formatter 默认关闭，开启后才注册后端路由
    WORD_FORMATTER_ENABLED: bool = False
    # Word Formatter 文件上传限制 (MB)
    MAX_UPLOAD_FILE_SIZE_MB: int = 20
    
    # 会话压缩配置
    HISTORY_COMPRESSION_THRESHOLD: int = 5000  # 汉字数量阈值
    COMPRESSION_MODEL: str = "gpt-5"
    COMPRESSION_API_KEY: Optional[str] = None
    COMPRESSION_BASE_URL: Optional[str] = None
    
    # 感情文章润色模型配置
    EMOTION_MODEL: Optional[str] = None
    EMOTION_API_KEY: Optional[str] = None
    EMOTION_BASE_URL: Optional[str] = None

    # 朱雀AI检测配置
    ZHUQUE_CDP_PORT: int = 9223
    ZHUQUE_USER_DATA_DIR: str = ""
    ZHUQUE_DETECT_THRESHOLD: float = 20.0
    ZHUQUE_MAX_REDUCE_ROUNDS: int = 5
    ZHUQUE_FREE_USES_PER_USER: int = 20
    ZHUQUE_DETECT_TIMEOUT: int = 180
    ZHUQUE_DETECT_INTERVAL: float = 2.0
    ZHUQUE_DETECT_TRANSPORT: str = "auto"
    ZHUQUE_SERVER_HEADLESS_FALLBACK: bool = False
    ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT: int = 900
    ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT: int = 120
    ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS: int = 600
    ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS: int = 25
    ZHUQUE_REDUCE_BATCH_ENABLED: bool = True
    ZHUQUE_REDUCE_BATCH_SIZE: int = 3
    ZHUQUE_REDUCE_BATCH_MAX_CHARS: int = 2500
    ZHUQUE_REDUCE_BATCH_SINGLE_SEGMENT_CHARS: int = 1500
    ZHUQUE_REDUCE_FALLBACK_TOP_N: int = 20
    ZHUQUE_REDUCE_SKIP_SHORT_CHARS: int = 80

    # 文档结构解析配置
    PDF_STRUCTURE_ENGINE: str = "mineru"
    PDF_STRUCTURE_FALLBACK_ENGINE: str = "markitdown"
    DOCX_STRUCTURE_ENGINE: str = "python_docx"
    MINERU_BASE_URL: str = "https://mineru.net"
    MINERU_API_TOKEN: Optional[str] = None
    MINERU_MODEL_VERSION: str = "vlm"
    MINERU_ENABLE_FORMULA: bool = True
    MINERU_ENABLE_TABLE: bool = True
    MINERU_IS_OCR: bool = False
    MINERU_LANGUAGE: str = "ch"
    MINERU_TIMEOUT_SECONDS: int = 300
    MINERU_POLL_INTERVAL_SECONDS: float = 2.0
    
    # 流式输出配置
    USE_STREAMING: bool = False  # 默认使用非流式模式，避免被API阻止

    # API 请求间隔（秒），用于避免触发 RATE_LIMIT
    API_REQUEST_INTERVAL: int = 6

    # 思考模式配置
    THINKING_MODE_ENABLED: bool = True  # 默认启用思考模式
    THINKING_MODE_EFFORT: str = "high"  # 思考强度: none, low, medium, high, xhigh
    
    # JWT 密钥
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    USER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    STREAM_TOKEN_EXPIRE_SECONDS: int = 120
    
    # 管理员账户
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = DEFAULT_ADMIN_PASSWORD
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10
    REDEEM_RATE_LIMIT_PER_MINUTE: int = 20
    REGISTRATION_ENABLED: bool = True
    ADMIN_DATABASE_MANAGER_ENABLED: bool = True
    ADMIN_DATABASE_WRITE_ENABLED: bool = False
    INLINE_TASK_WORKER_ENABLED: bool = True
    TASK_WORKER_POLL_INTERVAL: float = 2.0
    TASK_WORKER_HEARTBEAT_INTERVAL: float = 30.0
    TASK_WORKER_STALE_TIMEOUT_SECONDS: int = 120
    TASK_WORKER_LEASE_TIMEOUT_SECONDS: int = 120
    TASK_WORKER_MAX_ATTEMPTS: int = 3
    TASK_EVENT_POLL_INTERVAL_SECONDS: float = 1.0
    VPS_UPDATE_ENABLED: bool = False
    VPS_UPDATE_WORKDIR: str = "/app/source"
    VPS_UPDATE_LOG_FILE: str = "/app/source/logs/vps-update.log"
    VPS_UPDATE_COMMAND: str = "git fetch --tags origin main && git pull --ff-only origin main && docker compose --env-file .env.docker up -d --build"
    BACKUP_DIR: str = "backups"
    BACKUP_RETENTION_DAYS: int = 14
    BACKUP_INTERVAL_SECONDS: int = 86400
    MODEL_TEST_TIMEOUT_SECONDS: float = 15.0

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )


# 加载 exe 目录下的 .env 文件
_env_path = get_env_file_path()
if os.path.exists(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path, encoding="utf-8-sig")

# Docker/VPS file secrets are loaded after .env so they always win over a
# stale compatibility value. Pass them as init values rather than exporting
# them: spawned browser/tool processes must not inherit application Secrets.
settings = Settings(**read_secret_file_values())


def parse_allowed_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def get_allowed_origins() -> list[str]:
    return parse_allowed_origins(settings.ALLOWED_ORIGINS)


def is_server_deployment() -> bool:
    return settings.APP_ENV.lower() in SERVER_DEPLOYMENT_ENVS


def _normalize_secret_value(value: str) -> str:
    return value.strip().lower()


def _is_placeholder_value(value: str, known_values: set[str]) -> bool:
    normalized = _normalize_secret_value(value)
    if normalized in {_normalize_secret_value(item) for item in known_values}:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def is_placeholder_secret(value: str) -> bool:
    return _is_placeholder_value(value, PLACEHOLDER_SECRET_VALUES)


def is_placeholder_admin_password(value: str) -> bool:
    return _is_placeholder_value(value, PLACEHOLDER_ADMIN_PASSWORD_VALUES)


def is_weak_secret(value: str) -> bool:
    return len(value.strip()) < MIN_SECRET_KEY_LENGTH


def is_weak_admin_password(value: str) -> bool:
    return len(value.strip()) < MIN_ADMIN_PASSWORD_LENGTH


def has_default_runtime_secrets(target_settings: Optional["Settings"] = None) -> bool:
    active_settings = target_settings or settings
    return (
        is_placeholder_secret(active_settings.SECRET_KEY)
        or is_placeholder_admin_password(active_settings.ADMIN_PASSWORD)
    )


def ensure_runtime_secrets_safe(target_settings: Optional["Settings"] = None) -> None:
    active_settings = target_settings or settings
    if active_settings.APP_ENV.lower() not in SERVER_DEPLOYMENT_ENVS:
        return

    if has_default_runtime_secrets(active_settings):
        raise RuntimeError(
            "Non-default SECRET_KEY and ADMIN_PASSWORD are required when APP_ENV "
            "indicates a server deployment"
        )
    if is_weak_secret(active_settings.SECRET_KEY):
        raise RuntimeError(
            f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters in server deployment mode"
        )
    if is_weak_admin_password(active_settings.ADMIN_PASSWORD):
        raise RuntimeError(
            f"ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters in server deployment mode"
        )


def _read_env_file_values() -> dict[str, str]:
    """读取运行时 .env 文件中的 key/value。"""
    env_values: dict[str, str] = {}
    env_path = get_env_file_path()
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_values[key.strip()] = value.strip()
    return env_values


def _normalize_reload_updates(updates: Mapping[str, Any]) -> dict[str, str]:
    """只保留 Settings 已知字段，避免未知 .env 项污染运行配置。"""
    allowed_fields = set(Settings.model_fields)
    normalized: dict[str, str] = {}
    for key, value in updates.items():
        normalized_key = str(key).strip()
        if normalized_key in allowed_fields:
            normalized[normalized_key] = "" if value is None else str(value).strip()
    return normalized


def reload_settings(updates: Optional[Mapping[str, Any]] = None):
    """重新加载配置 - 直接更新现有 settings 对象的属性。

    updates 为 None 时：兼容旧行为，完整读取运行时 .env。
    updates 有值时：只热加载本次后台保存的 key，避免 Docker/.env.docker
    注入的 ADMIN_PASSWORD、SECRET_KEY、DATABASE_URL 等被容器内 .env 默认值覆盖。
    """
    global settings

    pending_updates = _read_env_file_values() if updates is None else _normalize_reload_updates(updates)
    file_updates = read_secret_file_values()
    # Mounted files remain authoritative even when the admin UI persists a
    # compatibility .env value or the worker reloads configuration in-place.
    pending_updates.update(file_updates)
    if not pending_updates:
        return settings

    original_env = {key: os.environ.get(key) for key in pending_updates}
    original_settings = {key: getattr(settings, key) for key in Settings.model_fields}
    try:
        if updates is None:
            for key, value in pending_updates.items():
                if key in file_updates:
                    continue
                os.environ[key] = value
            candidate_settings = Settings(**file_updates)
        else:
            candidate_values = dict(original_settings)
            candidate_values.update(pending_updates)
            candidate_settings = Settings(**candidate_values)
        ensure_runtime_secrets_safe(candidate_settings)
    except Exception:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in original_settings.items():
            setattr(settings, key, value)
        raise

    for key in Settings.model_fields:
        setattr(settings, key, getattr(candidate_settings, key))

    return settings
