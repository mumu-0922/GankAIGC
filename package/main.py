#!/usr/bin/env python3
"""
GankAIGC - 统一入口
将前后端整合为一个可执行文件
"""

import os
import sys
import webbrowser
import threading
import time
import signal
from contextlib import asynccontextmanager
from typing import Optional

# 获取应用运行目录
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的 exe 运行
    APP_DIR = os.path.dirname(sys.executable)
    # 静态文件在 exe 内部的 _internal 目录或与 exe 同级目录
    STATIC_DIR = os.path.join(sys._MEIPASS, 'static')
else:
    # 正常 Python 运行
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(APP_DIR, 'static')

# 设置工作目录为应用目录（确保配置文件在正确位置）
os.chdir(APP_DIR)

# 默认读取程序目录下的 .env；Docker/VPS 可提前注入 GANKAIGC_ENV_FILE
# 指向 bind mount 的 .env.docker，后台系统配置也会写回同一个文件。
ENV_FILE = os.environ.get('GANKAIGC_ENV_FILE') or os.path.join(APP_DIR, '.env')
os.environ['GANKAIGC_ENV_FILE'] = ENV_FILE

# 加载环境变量
if os.path.exists(ENV_FILE):
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE, encoding="utf-8-sig")

# 添加 backend 到 Python 路径
backend_path = os.path.join(APP_DIR, 'backend') if not getattr(sys, 'frozen', False) else APP_DIR
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

# 导入后端应用组件
from app.config import (
    ensure_runtime_secrets_safe,
    is_placeholder_admin_password,
    is_placeholder_secret,
    is_server_deployment,
    settings,
)
from app.database import check_database_connection, init_db
from app.routes import admin, auth, prompts, optimization, user
from app.runtime import refresh_cors_middleware
from app.services.rate_limit import SlidingWindowLimiter
from app.models.models import CustomPrompt
from app.database import SessionLocal
from app.services.ai_service import get_default_polish_prompt, get_default_enhance_prompt

# 检查默认密钥（仅警告，不退出）
if is_placeholder_secret(settings.SECRET_KEY):
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认 SECRET_KEY!")
    print("="*60)
    print("生产环境必须修改 SECRET_KEY,否则 JWT token 可被伪造!")
    print(f"请在 {ENV_FILE} 文件中设置强密钥:")
    print("  使用命令生成: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    print("="*60 + "\n")

if is_placeholder_admin_password(settings.ADMIN_PASSWORD):
    print("\n" + "="*60)
    print("⚠️  安全警告: 检测到默认管理员密码!")
    print("="*60)
    print("生产环境必须修改 ADMIN_PASSWORD!")
    print(f"请在 {ENV_FILE} 文件中设置强密码 (建议12位以上)")
    print("="*60 + "\n")

ensure_runtime_secrets_safe()

auth_rate_limiter = SlidingWindowLimiter()
redeem_rate_limiter = SlidingWindowLimiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    try:
        yield
    finally:
        await shutdown_event()


# 创建 FastAPI 应用
app = FastAPI(
    title="GankAIGC",
    description="高质量论文润色与原创性学术表达增强",
    version="1.0.0",
    lifespan=lifespan,
)

# 添加 Gzip 压缩中间件以减少响应体积
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS 配置
refresh_cors_middleware(app)

# 添加中间件：为所有 API 响应添加禁止缓存的头部
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """为 API 请求添加禁止缓存的响应头"""
    response = await call_next(request)
    
    # 只对 API 路径添加禁止缓存头，静态资源可以缓存
    if request.url.path.startswith('/api/'):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

# 注册 API 路由（添加 /api 前缀，与 backend/app/main.py 保持一致）
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(optimization.router, prefix="/api")
if settings.WORD_FORMATTER_ENABLED:
    from app.word_formatter import router as word_formatter_router

    app.include_router(word_formatter_router, prefix="/api")


def _get_rate_limit_key(request: Request, scope: str) -> str:
    client_host = request.client.host if request.client else ""
    return f"{scope}:{client_host or 'unknown'}"


@app.middleware("http")
async def enforce_sensitive_endpoint_rate_limits(request: Request, call_next):
    limiter = None
    scope = ""
    limit = 0

    if request.method == "POST" and request.url.path in {
        "/api/admin/login",
        "/api/auth/login",
        "/api/auth/register",
    }:
        limiter = auth_rate_limiter
        scope = "auth"
        limit = settings.AUTH_RATE_LIMIT_PER_MINUTE
    elif request.method == "POST" and request.url.path in {
        "/api/user/redeem-code",
    }:
        limiter = redeem_rate_limiter
        scope = "redeem"
        limit = settings.REDEEM_RATE_LIMIT_PER_MINUTE

    if limiter and limit > 0:
        key = _get_rate_limit_key(request, scope)
        if not limiter.check(key, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )

    return await call_next(request)


async def startup_event():
    """启动时初始化"""
    print(f"\n📁 应用目录: {APP_DIR}")
    print(f"📁 配置文件: {ENV_FILE}")
    print("📁 数据库: PostgreSQL")
    print(f"📁 静态文件目录: {STATIC_DIR}")
    
    # 先检查连接，再初始化数据库结构
    check_database_connection()
    init_db()
    
    # 创建系统默认提示词
    db = SessionLocal()
    try:
        # 检查是否已存在系统提示词
        polish_prompt = db.query(CustomPrompt).filter(
            CustomPrompt.is_system.is_(True),
            CustomPrompt.stage == "polish"
        ).first()
        
        if not polish_prompt:
            polish_prompt = CustomPrompt(
                name="默认润色提示词",
                stage="polish",
                content=get_default_polish_prompt(),
                is_default=True,
                is_system=True
            )
            db.add(polish_prompt)
        
        enhance_prompt = db.query(CustomPrompt).filter(
            CustomPrompt.is_system.is_(True),
            CustomPrompt.stage == "enhance"
        ).first()
        
        if not enhance_prompt:
            enhance_prompt = CustomPrompt(
                name="默认增强提示词",
                stage="enhance",
                content=get_default_enhance_prompt(),
                is_default=True,
                is_system=True
            )
            db.add(enhance_prompt)
        
        db.commit()
    finally:
        db.close()


async def shutdown_event():
    """关闭时清理资源"""
    if settings.WORD_FORMATTER_ENABLED:
        from app.word_formatter.services import get_job_manager

        job_manager = get_job_manager()
        await job_manager.shutdown()


@app.get("/health")
async def health_check():
    """健康检查"""
    return JSONResponse(
        content={"status": "healthy"},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


def _check_url_format(base_url: Optional[str]) -> tuple:
    """检查 URL 格式是否正确
    
    Returns:
        tuple: (is_valid, error_message)
    """
    import re
    
    if not base_url or not base_url.strip():
        return False, "Base URL 未配置"
    
    # 验证 base_url 是否符合 OpenAI API 格式
    # 使用更严格的 URL 验证模式
    url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    if not url_pattern.match(base_url):
        return False, "Base URL 格式不正确，应为有效的 HTTP/HTTPS URL"
    
    return True, None


# 缓存已检查的 URL 结果，避免重复检查
_url_check_cache: dict = {}


async def _check_model_health(model_name: str, model: str, api_key: Optional[str], base_url: Optional[str]) -> dict:
    """检查单个模型的健康状态 - 只验证URL格式，不测试实际连接"""
    
    try:
        # 检查必需的配置项
        if not model or not model.strip():
            return {
                "status": "unavailable",
                "model": model,
                "base_url": base_url,
                "error": "模型名称未配置"
            }
        
        # 先检查 URL 格式是否有效
        is_valid, error_msg = _check_url_format(base_url)
        
        if not is_valid:
            return {
                "status": "unavailable",
                "model": model,
                "base_url": base_url,
                "error": error_msg
            }
        
        # URL 有效时才检查缓存（此时 base_url 不为 None）
        if base_url in _url_check_cache:
            cached_result = _url_check_cache[base_url]
            result = {
                "status": cached_result["status"],
                "model": model,
                "base_url": base_url
            }
            if cached_result["status"] == "unavailable":
                result["error"] = cached_result.get("error")
            return result
        
        # URL 格式正确，认为配置有效
        result = {
            "status": "available",
            "model": model,
            "base_url": base_url
        }
        # 缓存检查结果
        _url_check_cache[base_url] = {"status": "available"}
        return result
        
    except Exception as e:
        error_msg = str(e) if str(e) else "未知错误"
        return {
            "status": "unavailable",
            "model": model,
            "base_url": base_url,
            "error": error_msg
        }


@app.get("/api/health/models")
async def check_models_health():
    """检查 AI 模型可用性 - 只验证URL格式，如果URL相同则只检查一次"""
    global _url_check_cache
    # 清空缓存以确保每次请求都重新检查
    _url_check_cache = {}
    
    results = {
        "overall_status": "healthy",
        "models": {}
    }
    
    # 检查润色模型
    results["models"]["polish"] = await _check_model_health(
        "polish",
        settings.POLISH_MODEL,
        settings.POLISH_API_KEY,
        settings.POLISH_BASE_URL
    )
    if results["models"]["polish"]["status"] == "unavailable":
        results["overall_status"] = "degraded"
    
    # 检查增强模型
    results["models"]["enhance"] = await _check_model_health(
        "enhance",
        settings.ENHANCE_MODEL,
        settings.ENHANCE_API_KEY,
        settings.ENHANCE_BASE_URL
    )
    if results["models"]["enhance"]["status"] == "unavailable":
        results["overall_status"] = "degraded"
    
    # 检查感情润色模型（如果配置了）
    if settings.EMOTION_MODEL:
        results["models"]["emotion"] = await _check_model_health(
            "emotion",
            settings.EMOTION_MODEL,
            settings.EMOTION_API_KEY,
            settings.EMOTION_BASE_URL
        )
        if results["models"]["emotion"]["status"] == "unavailable":
            results["overall_status"] = "degraded"
    
    # 返回带缓存控制头的响应，确保数据始终是最新的
    return JSONResponse(
        content=results,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# 挂载静态文件（前端构建产物）
# 路由无条件注册，请求时再检查文件是否存在，避免 Docker/PyInstaller 场景下
# 导入时机导致静态目录判断过早。
assets_dir = os.path.join(STATIC_DIR, 'assets')
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


def _serve_spa_index_or_api_info(error_message: str | None = None):
    index_file = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_file):
        return FileResponse(index_file)
    if error_message:
        return {"error": error_message}
    return {
        "message": "GankAIGC API",
        "version": "1.0.0",
        "docs": "/docs",
        "note": "静态文件目录不存在，仅 API 可用"
    }


@app.get("/")
async def serve_root():
    """服务根路径"""
    return _serve_spa_index_or_api_info()


@app.head("/")
async def head_root():
    """允许 curl -I / 这类 VPS 可达性探测。"""
    return Response(status_code=200)


@app.get("/admin")
@app.get("/admin/{path:path}")
async def serve_admin(path: str = ""):
    """服务管理后台页面"""
    return _serve_spa_index_or_api_info("Admin page not found")


@app.get("/workspace")
@app.get("/workspace/{path:path}")
async def serve_workspace(path: str = ""):
    """服务工作区页面"""
    return _serve_spa_index_or_api_info("Workspace page not found")


@app.get("/word-formatter")
@app.get("/word-formatter/{path:path}")
async def serve_word_formatter(path: str = ""):
    """服务 Word 格式化页面"""
    return _serve_spa_index_or_api_info("Word formatter page not found")


@app.get("/session/{session_id}")
async def serve_session(session_id: str):
    """服务会话详情页面"""
    return _serve_spa_index_or_api_info("Session page not found")


# 处理其他静态文件
@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    """服务其他静态文件"""
    # 如果是 API 路径，抛出 404 让 FastAPI 正确处理
    if file_path.startswith('api/') or file_path.startswith('docs') or file_path.startswith('openapi'):
        raise HTTPException(status_code=404, detail="Not found")

    full_path = os.path.join(STATIC_DIR, file_path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FileResponse(full_path)

    # 对于 SPA 路由，返回 index.html
    index_file = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_file):
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="File not found")


def get_browser_host(bind_host: str | None) -> str:
    """Return a browser-friendly host for a server bind address."""
    if not bind_host or bind_host in {"0.0.0.0", "::"}:
        return "localhost"
    return bind_host


def get_uvicorn_host(bind_host: str | None, server_deployment: bool) -> str:
    """Return the host uvicorn should bind to for the current runtime mode."""
    if not bind_host:
        return "0.0.0.0" if server_deployment else "localhost"
    if server_deployment:
        return bind_host
    if bind_host in {"0.0.0.0", "::"}:
        return "localhost"
    return bind_host


def open_browser(port: int, host: str | None = None):
    """延迟打开浏览器"""
    time.sleep(2)  # 等待服务器启动
    url = f"http://{get_browser_host(host)}:{port}"
    print(f"\n🌐 正在打开浏览器: {url}")
    webbrowser.open(url)


def pause_before_exit_if_frozen(prompt: str = "\n按 Enter 退出..."):
    """Windows exe 需要保留窗口，方便用户看到提示。"""
    if (
        getattr(sys, 'frozen', False)
        and os.name == 'nt'
        and os.environ.get('GANKAIGC_NO_EXIT_PAUSE') != '1'
    ):
        try:
            input(prompt)
        except (EOFError, KeyboardInterrupt):
            pass


def create_sample_env():
    """创建示例 .env 文件（如果不存在）"""
    if is_server_deployment():
        # Docker/VPS 部署应以 .env.docker / 环境变量为准。
        # 不自动生成带默认密钥的 .env，避免后续后台热加载时混淆配置来源。
        return False

    if not os.path.exists(ENV_FILE):
        sample_content = """# GankAIGC配置文件
# 请根据实际情况修改以下配置

# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=9800

# 数据库配置 (仅支持 PostgreSQL)
DATABASE_URL=postgresql://ai_polish:replace-with-postgres-password@127.0.0.1:5432/ai_polish

# Redis 配置 (用于并发控制和队列)
REDIS_URL=redis://localhost:6379/0

# Web 部署配置
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:9800
AUTO_OPEN_BROWSER=true
ENABLE_VERBOSE_AI_LOGS=false
ENCRYPTION_KEY=
AUTH_RATE_LIMIT_PER_MINUTE=10
REDEEM_RATE_LIMIT_PER_MINUTE=20
REGISTRATION_ENABLED=true
WORD_FORMATTER_ENABLED=false
ADMIN_DATABASE_MANAGER_ENABLED=true
ADMIN_DATABASE_WRITE_ENABLED=false
INLINE_TASK_WORKER_ENABLED=true
TASK_WORKER_POLL_INTERVAL=2

# OpenAI API 配置
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# 第一阶段模型配置 (论文润色) - 推荐使用 gemini-2.5-pro
POLISH_MODEL=gemini-2.5-pro
POLISH_API_KEY=your-api-key-here
POLISH_BASE_URL=https://api.openai.com/v1

# 第二阶段模型配置 (原创性增强) - 推荐使用 gemini-2.5-pro
ENHANCE_MODEL=gemini-2.5-pro
ENHANCE_API_KEY=your-api-key-here
ENHANCE_BASE_URL=https://api.openai.com/v1

# 感情文章润色模型配置 - 推荐使用 gemini-2.5-pro
EMOTION_MODEL=gemini-2.5-pro
EMOTION_API_KEY=your-api-key-here
EMOTION_BASE_URL=https://api.openai.com/v1

# 并发配置
MAX_CONCURRENT_USERS=7

# API 请求间隔 (秒，每段落处理后等待，避免触发频率限制)
API_REQUEST_INTERVAL=6

# 会话压缩配置
HISTORY_COMPRESSION_THRESHOLD=2000
COMPRESSION_MODEL=gemini-2.5-pro
COMPRESSION_API_KEY=your-api-key-here
COMPRESSION_BASE_URL=https://api.openai.com/v1

# JWT 密钥 (请修改为随机字符串)
SECRET_KEY=please-change-this-to-a-random-string-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
USER_ACCESS_TOKEN_EXPIRE_MINUTES=10080

# 管理员账户 (请修改默认密码)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=please-change-this-password
DEFAULT_USAGE_LIMIT=1
SEGMENT_SKIP_THRESHOLD=15
"""
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(sample_content)
        print(f"✅ 已创建示例配置文件: {ENV_FILE}")
        return True
    return False


def print_first_run_instructions():
    """首次运行 exe 时给新手看的简明配置说明。"""
    print("\n" + "=" * 60)
    print("🎉 首次运行准备完成")
    print("=" * 60)
    print(f"已在程序同目录创建配置文件：{ENV_FILE}")
    print("")
    print("下一步只需要做两件事：")
    print("1. 用记事本打开上面的 .env 文件。")
    print("2. 修改 DATABASE_URL，把数据库密码改成你的 PostgreSQL 密码。")
    print("")
    print("示例：")
    print("DATABASE_URL=postgresql://ai_polish:你的数据库密码@127.0.0.1:5432/ai_polish")
    print("")
    print("如果你还没有 PostgreSQL，推荐用 README 里的 Docker 部署方式。")
    print("修改保存后，再重新双击 GankAIGC.exe。")
    print("=" * 60)


def print_database_connection_help(error: Exception):
    """数据库连接失败时显示新手友好的错误提示，避免 traceback 刷屏。"""
    error_text = str(error)
    print("\n" + "=" * 60)
    print("❌ 数据库连接失败，程序没有启动")
    print("=" * 60)
    print(f"配置文件位置：{ENV_FILE}")
    print("")

    if "password authentication failed" in error_text:
        print("原因：数据库密码不对。")
        print("")
        print("请打开 .env，找到这一行：")
        print("DATABASE_URL=postgresql://ai_polish:密码@127.0.0.1:5432/ai_polish")
        print("")
        print("把中间的“密码”改成你 PostgreSQL 的真实密码。")
    elif "Connection refused" in error_text or "connection refused" in error_text:
        print("原因：PostgreSQL 没有启动，或 5432 端口不通。")
        print("")
        print("如果你用 Docker，可以先启动数据库：")
        print("docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.local.yml up -d postgres")
    else:
        print("请优先检查：")
        print("1. PostgreSQL 是否已启动。")
        print("2. .env 里的 DATABASE_URL 是否正确。")
        print("3. 用户名、密码、数据库名、端口是否正确。")

    print("")
    print("DATABASE_URL 正确格式：")
    print("postgresql://ai_polish:你的数据库密码@127.0.0.1:5432/ai_polish")
    print("=" * 60)


def main():
    """主入口函数"""
    port = settings.SERVER_PORT
    host = settings.SERVER_HOST
    server_deployment = is_server_deployment()
    browser_host = get_browser_host(host)
    uvicorn_host = get_uvicorn_host(host, server_deployment)
    
    print("\n" + "="*60)
    print("🚀 GankAIGC - 启动中...")
    print("="*60)
    
    # 创建示例配置文件。首次创建后先退出，让新手有机会编辑 .env。
    if create_sample_env():
        print_first_run_instructions()
        pause_before_exit_if_frozen("\n配置好 .env 后重新双击 GankAIGC.exe。按 Enter 退出...")
        return

    # 启动浏览器和 uvicorn 前先做数据库预检查，避免配置错误时刷出长 traceback。
    try:
        check_database_connection()
    except RuntimeError as e:
        print_database_connection_help(e)
        pause_before_exit_if_frozen("\n请修改 .env 后重试。按 Enter 退出...")
        sys.exit(1)
    
    print(f"\n📍 服务地址: http://{browser_host}:{port}")
    print(f"📍 管理后台: http://{browser_host}:{port}/admin")
    print(f"📍 API 文档: http://{browser_host}:{port}/docs")
    print("\n按 Ctrl+C 停止服务")
    print("="*60 + "\n")
    
    # 仅在本地交互式运行时自动打开浏览器
    if settings.AUTO_OPEN_BROWSER and not server_deployment:
        browser_thread = threading.Thread(target=open_browser, args=(port, host))
        browser_thread.daemon = True
        browser_thread.start()
    
    # 启动 uvicorn 服务器
    try:
        uvicorn.run(
            app,
            host=uvicorn_host,
            port=port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
        sys.exit(0)
    except SystemExit as e:
        if e.code not in (0, None):
            pause_before_exit_if_frozen("\n❌ 启动失败，请根据上面的错误提示修改 .env 后重试。按 Enter 退出...")
        raise
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        pause_before_exit_if_frozen("\n❌ 启动失败，请根据上面的错误提示修改 .env 后重试。按 Enter 退出...")
        raise


if __name__ == "__main__":
    main()
