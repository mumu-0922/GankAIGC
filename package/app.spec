# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GankAIGC
用于将前后端项目打包为单个可执行文件
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 获取 spec 文件所在目录
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# 收集所需的隐式导入
hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'httptools',
    'websockets',
    'sqlalchemy.dialects.postgresql',
    'psycopg',
    'pydantic',
    'pydantic_settings',
    'passlib.handlers.bcrypt',
    'jose',
    'openai',
    'httpx',
    'socksio',
    'aiofiles',
    'sse_starlette',
    'redis',
    'dotenv',
    # Zhuque 本机可见浏览器控制依赖
    'playwright',
    'playwright.async_api',
    # Word 格式化模块依赖
    'mistune',
    'docx',
    'markitdown',
    'lxml',
    'lxml.etree',
    'lxml._elementpath',
    # pkg_resources / setuptools 依赖 (Linux 必需)
    'jaraco',
    'jaraco.text',
    'jaraco.functools',
    'jaraco.context',
    'platformdirs',
    'pkg_resources',
    'pkg_resources.extern',
]

# 收集 uvicorn 和其他依赖的子模块
hidden_imports += collect_submodules('uvicorn')
hidden_imports += collect_submodules('sqlalchemy')
hidden_imports += collect_submodules('pydantic')
hidden_imports += collect_submodules('pydantic_settings')
hidden_imports += collect_submodules('fastapi')
hidden_imports += collect_submodules('starlette')
hidden_imports += collect_submodules('playwright')
# Word 格式化模块子模块
hidden_imports += collect_submodules('mistune')
hidden_imports += collect_submodules('docx')
hidden_imports += collect_submodules('markitdown')
hidden_imports += collect_submodules('magika')
hidden_imports += collect_submodules('mammoth')
hidden_imports += collect_submodules('markdownify')
hidden_imports += collect_submodules('bs4')
hidden_imports += collect_submodules('onnxruntime')
hidden_imports += collect_submodules('pdfplumber')
hidden_imports += collect_submodules('pdfminer')
hidden_imports += collect_submodules('pypdfium2')
hidden_imports += collect_submodules('PIL')
hidden_imports += collect_submodules('lxml')
# pkg_resources / jaraco 子模块 (Linux 必需)
hidden_imports += collect_submodules('jaraco')
hidden_imports += collect_submodules('pkg_resources')

# 分析主入口文件
a = Analysis(
    ['main.py'],
    pathex=[spec_dir, os.path.join(spec_dir, 'backend')],
    binaries=[],
    datas=[
        # 包含前端静态文件
        ('static', 'static'),
        # 包含构建版本号
        ('VERSION', '.'),
        # 包含后端 app 目录
        ('backend/app', 'app'),
        # 本地/一键包启动会用 Alembic 对旧数据库补迁移并校验 head。
        # schema.py 在冻结运行时从 _MEIPASS 根目录查找这两项。
        ('backend/alembic.ini', '.'),
        ('backend/migrations', 'migrations'),
        # Playwright Python package includes its driver/runtime resources.
        *collect_data_files('playwright'),
        # MarkItDown 依赖 magika 的本地模型/配置文件
        *collect_data_files('magika'),
        # MarkItDown PDF 解析依赖 pypdfium2 的运行时资源
        *collect_data_files('pypdfium2'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 创建 PYZ 归档
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GankAIGC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 设置为 True 以显示控制台窗口（可以看到日志）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)
