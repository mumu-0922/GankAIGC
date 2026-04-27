# GankAIGC

GankAIGC 是一个面向论文文本的 AI 降重、学术润色与原创性表达增强工具。项目采用 FastAPI + React/Vite 架构，支持源码运行、Docker 部署和 PyInstaller 打包为单个可执行文件。

当前稳定主线聚焦「账号注册 + 用户登录 + 邀请码注册 + 兑换码充值次数 + 降 AI 工作台」。文档排版相关代码仍保留在后端实验模块中，但不是当前主流程功能。

## 主要功能

- 论文文本降 AI：支持论文润色、原创性增强、润色 + 增强、感情文章润色等处理模式。
- 账号体系：用户通过邀请码注册，登录后进入工作台；用户可修改昵称并查看个人信息。
- 邀请机制：管理员可创建多个邀请码，普通用户只能生成一个自己的邀请码用于邀请他人注册。
- 次数体系：管理员创建兑换码，用户在前台兑换次数；平台次数模式按任务扣除次数。
- 自带 API：用户可保存自己的 OpenAI 兼容接口配置，使用 BYOK 模式处理任务。
- 论文项目与历史：支持按论文项目归档任务，查看会话进度、处理结果和改写记录。
- 结果导出：处理完成后可导出 Word (`.docx`) 或 Markdown (`.md`) 文件。
- 管理后台：提供数据面板、会话监控、账号与兑换码管理、数据库管理、系统配置等能力。

## 技术栈

- 后端：FastAPI、SQLAlchemy、SQLite/PostgreSQL、JWT、OpenAI Python SDK
- 前端：React 18、Vite、Tailwind CSS、React Router、Axios、Lucide React
- 打包：PyInstaller
- 部署：Docker Compose + PostgreSQL

## 项目结构

```text
GankAIGC/
├── package/
│   ├── main.py                  # 一体化启动入口，挂载 API 与前端静态文件
│   ├── backend/
│   │   ├── app/
│   │   │   ├── routes/          # auth、user、admin、optimization 等 API
│   │   │   ├── services/        # AI 调用、并发、次数、配置等业务逻辑
│   │   │   ├── models/          # SQLAlchemy 数据模型
│   │   │   ├── utils/           # 认证、加密等工具
│   │   │   └── word_formatter/  # 实验性文档工具模块
│   │   └── tests/               # pytest 测试
│   ├── frontend/
│   │   ├── src/pages/           # 页面
│   │   ├── src/components/      # 组件
│   │   └── src/api/             # 前端 API 封装
│   ├── static/                  # 前端生产构建产物，由 main.py 提供服务
│   ├── requirements.txt         # 打包运行所需 Python 依赖
│   ├── build.ps1                # Windows 可执行文件构建脚本
│   └── build.sh                 # Linux/macOS 可执行文件构建脚本
├── docker-compose.yml
├── Dockerfile
├── .env.docker.example
└── AGENTS.md                    # 贡献者/Agent 开发指南
```

## 快速运行

### 一体化源码运行

适合直接使用当前已构建的前端静态文件。

```powershell
cd package
pip install -r requirements.txt
python main.py
```

启动后访问：

- 用户首页：http://localhost:9800
- 管理后台：http://localhost:9800/admin
- API 文档：http://localhost:9800/docs

### 前端开发模式

适合修改前端页面时使用。后端仍运行在 `9800`，Vite 默认运行在 `5174`，并将 `/api` 代理到后端。

```powershell
cd package
python main.py
```

另开终端：

```powershell
cd package/frontend
npm ci
npm run dev
```

### 修改前端后更新生产静态文件

```powershell
cd package/frontend
npm run build
cd ../..
Copy-Item -Path .\package\frontend\dist\* -Destination .\package\static -Recurse -Force
```

注意：`package/static/` 在 `.gitignore` 中，若确实要提交新的静态 bundle，需要对新增 hash 文件使用 `git add -f`。

## 配置说明

源码运行时，配置文件位于 `package/.env`；打包后的可执行文件会在 exe 同目录读取 `.env`。首次运行会自动按默认值初始化数据库。

核心配置示例：

```properties
SERVER_HOST=0.0.0.0
SERVER_PORT=9800
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:9800

DATABASE_URL=sqlite:///./ai_polish.db
REDIS_URL=redis://IP:6379/0

ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-strong-password
SECRET_KEY=replace-with-random-secret
ENCRYPTION_KEY=replace-with-fernet-key

POLISH_MODEL=gpt-5.5
POLISH_API_KEY=KEY
POLISH_BASE_URL=https://api.openai.com/v1

ENHANCE_MODEL=gpt-5.5
ENHANCE_API_KEY=KEY
ENHANCE_BASE_URL=https://api.openai.com/v1

COMPRESSION_MODEL=gpt-5.5
COMPRESSION_API_KEY=KEY
COMPRESSION_BASE_URL=https://api.openai.com/v1

MAX_CONCURRENT_USERS=5
SEGMENT_SKIP_THRESHOLD=15
API_REQUEST_INTERVAL=6
USE_STREAMING=false
```

`ENCRYPTION_KEY` 用于加密用户保存的自带 API 配置，建议使用 Fernet key：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

生产环境必须修改默认 `ADMIN_PASSWORD` 和 `SECRET_KEY`。当 `APP_ENV=production`、`staging` 或 `server` 时，项目会拒绝使用明显的占位密钥。

## 使用流程

1. 管理员访问 `/admin` 登录后台。
2. 在「账号次数」中创建注册邀请码。
3. 用户通过邀请码注册并登录。
4. 管理员创建次数兑换码，用户在前台兑换次数。
5. 用户进入工作台，选择平台次数模式或自带 API 模式，提交论文文本。
6. 任务完成后查看分段结果、改写记录，并导出 `.docx` 或 `.md` 文件。

## 管理后台

后台地址为 `http://localhost:9800/admin`。默认账号为 `admin`，默认密码为 `admin123`，仅适合本地开发，部署前必须修改。

后台包含：

- 数据面板：查看用户、任务、完成率等统计。
- 会话监控：查看任务队列、处理中会话和历史任务。
- 账号次数：管理用户、邀请码、次数兑换码和用户自带 API 摘要。
- 数据库管理：查看、编辑、删除允许管理的数据表记录。
- 系统配置：在线调整模型、Base URL、并发、请求间隔、思考模式等配置。

## Docker 部署

Docker Compose 会启动应用容器和 PostgreSQL。

```powershell
Copy-Item .env.docker.example .env.docker
# 编辑 .env.docker，至少修改 POSTGRES_PASSWORD、SECRET_KEY、ADMIN_PASSWORD、ENCRYPTION_KEY
docker compose up --build -d
```

默认对外端口为 `9800`，可通过 `.env.docker` 中的 `APP_PORT` 修改。

## 构建可执行文件

Windows：

```powershell
cd package
.\build.ps1
```

Linux/macOS：

```bash
cd package
chmod +x build.sh
./build.sh
```

构建产物位于 `package/dist/`。推送 `v*` 标签也会触发 GitHub Actions 构建各平台可执行文件。

## 测试

后端测试：

```powershell
cd package/backend
python -m pytest -q
```

前端生产构建检查：

```powershell
cd package/frontend
npm run build
```

## 常见问题

**端口被占用**
修改 `.env` 中的 `SERVER_PORT`，或关闭占用 `9800` 端口的进程。

**管理后台刷新后回到数据面板**
当前后台通过 URL 参数保存 tab，例如 `/admin?tab=config`。如果手动删除参数，刷新会回到默认数据面板。

**用户无法使用自带 API**
确认用户已在「API 设置」保存 Base URL、API Key 和模型名称，并且服务端配置了有效的 `ENCRYPTION_KEY`。

**AI 调用失败**
检查 API Key、Base URL、模型名称和网络连通性。Google AI Studio 等服务商的 Key 在文档中统一写作 `Google API Key`，不要把真实密钥提交到仓库。

## 许可证

本项目基于 BypassAIGC 深度修改，继续采用 CC BY-NC-SA 4.0 协议发布。

未经相关版权方授权，禁止商业使用。

完整署名与来源见 [NOTICE](NOTICE)。

[![Star History Chart](https://api.star-history.com/svg?repos=mumu-0922/GankAIGC&type=Date)](https://www.star-history.com/?repos=mumu-0922%2FGankAIGC)
