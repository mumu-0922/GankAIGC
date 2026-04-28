from pydantic_settings import BaseSettings
from typing import Optional
import os
import sys

DEFAULT_SECRET_KEY = "your-secret-key-change-this-in-production"
DEFAULT_ADMIN_PASSWORD = "admin123"
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


class Settings(BaseSettings):
    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 9800
    APP_ENV: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:9800"
    AUTO_OPEN_BROWSER: bool = True

    # 数据库配置 - 仅支持 PostgreSQL
    DATABASE_URL: str = DEFAULT_DATABASE_URL
    
    # Redis 配置
    REDIS_URL: str = "redis://IP:6379/0"
    ENCRYPTION_KEY: str = ""
    
    # OpenAI API 配置
    OPENAI_API_KEY: str = "pwd"
    OPENAI_BASE_URL: str = "http://IP:PORT/v1"
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
    DEFAULT_USAGE_LIMIT: int = 1
    SEGMENT_SKIP_THRESHOLD: int = 15

    # 实验性 Word Formatter 默认关闭，开启后才注册后端路由
    WORD_FORMATTER_ENABLED: bool = False
    # Word Formatter 文件上传限制 (MB)，0 表示无限制
    MAX_UPLOAD_FILE_SIZE_MB: int = 0
    
    # 会话压缩配置
    HISTORY_COMPRESSION_THRESHOLD: int = 5000  # 汉字数量阈值
    COMPRESSION_MODEL: str = "gpt-5"
    COMPRESSION_API_KEY: Optional[str] = None
    COMPRESSION_BASE_URL: Optional[str] = None
    
    # 感情文章润色模型配置
    EMOTION_MODEL: Optional[str] = None
    EMOTION_API_KEY: Optional[str] = None
    EMOTION_BASE_URL: Optional[str] = None
    
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
    
    class Config:
        env_file = get_env_file_path()
        case_sensitive = True


# 加载 exe 目录下的 .env 文件
_env_path = get_env_file_path()
if os.path.exists(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path)

settings = Settings()


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


def reload_settings():
    """重新加载配置 - 直接更新现有 settings 对象的属性"""
    global settings

    pending_updates = {}
    env_path = get_env_file_path()
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    pending_updates[key.strip()] = value.strip()

    original_env = {key: os.environ.get(key) for key in pending_updates}
    try:
        for key, value in pending_updates.items():
            os.environ[key] = value

        candidate_settings = Settings()
        ensure_runtime_secrets_safe(candidate_settings)
    except Exception:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        raise

    for key in candidate_settings.model_fields:
        setattr(settings, key, getattr(candidate_settings, key))

    return settings

