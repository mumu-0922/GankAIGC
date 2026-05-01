<div align="center">
  <img src="package/frontend/public/gankaigc-logo.svg" alt="GankAIGC Logo" width="96" />

# GankAIGC

**论文降 AI、学术润色与原创性表达增强工具**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React%2018-Frontend-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Only-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Deploy-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE)

如果这个项目对你有帮助，欢迎点一个 ⭐ Star。

</div>

---

## ✨ 项目简介

GankAIGC 是一个面向论文文本的降 AI 与学术润色工具，采用 **FastAPI + React/Vite + PostgreSQL** 架构，支持源码运行、Docker 部署和 PyInstaller 打包。

---

## 🧩 核心功能

| 功能        | 说明                                                                        |
| ----------- | --------------------------------------------------------------------------- |
| 📝 论文降 AI | 支持论文润色、原创性增强、润色 + 增强、感情文章润色等模式                   |
| 👤 账号体系  | 用户通过邀请码注册，登录后进入工作台，可修改昵称和查看个人信息              |
| 📨 邀请机制  | 管理员可无限创建邀请码，普通用户只能生成 1 个自己的邀请码                   |
| 🍺 啤酒额度  | 用户使用兑换码充值啤酒；平台模式按字符扣除，约 1000 个非空白字符消耗 1 啤酒 |
| 🔑 自带 API  | 用户可保存自己的 OpenAI 兼容接口配置，使用 BYOK 模式处理任务                |
| 📚 论文项目  | 支持按论文项目归档任务，查看历史会话、分段结果和改写记录                    |
| 📦 结果导出  | 支持导出 Word `.docx` 和 Markdown `.md`                                     |
| 🛠 管理后台  | 数据面板、会话监控、用户管理、兑换码、封禁/解封、操作日志、系统配置         |

---

## 🏗 技术栈

- **后端**：FastAPI、SQLAlchemy、Alembic、PostgreSQL、JWT、OpenAI Python SDK
- **前端**：React 18、Vite、Tailwind CSS、React Router、Axios、Lucide React
- **任务处理**：PostgreSQL 队列；Docker 部署使用独立 worker
- **部署**：Docker Compose + PostgreSQL
- **打包**：PyInstaller

---

## 📁 项目结构

```text
GankAIGC/
├── package/
│   ├── main.py                  # 一体化启动入口，提供 API 与前端静态页面
│   ├── backend/
│   │   ├── app/routes/          # auth、user、admin、optimization 等 API
│   │   ├── app/services/        # AI 调用、啤酒、配置、任务队列等业务逻辑
│   │   ├── app/models/          # SQLAlchemy 数据模型
│   │   ├── migrations/          # Alembic 数据库迁移
│   │   └── tests/               # pytest 测试
│   ├── frontend/
│   │   ├── src/pages/           # 页面
│   │   ├── src/components/      # 组件
│   │   └── src/api/             # 前端 API 封装
│   ├── static/                  # 前端生产构建产物
│   ├── requirements.txt
│   ├── build.ps1                # Windows 可执行文件构建脚本
│   └── build.sh                 # Linux/macOS 可执行文件构建脚本
├── docker-compose.yml
├── Dockerfile
├── scripts/                     # 启动诊断、PostgreSQL 备份/恢复脚本
├── docs/                        # 部署、运维和维护清单
├── .env.docker.example          # Docker 环境变量模板，不是真实密钥
└── AGENTS.md                    # 贡献者/Agent 开发指南
```

---

## 🚀 运行与部署

当前按 3 种方式说明：前两种已经可用，第三种是后续规划占位：

1. **`python main.py` 源码运行**：适合本机开发、调试和自己使用。
2. **Docker Compose 部署**：适合本机 Docker、VPS 和正式上线，自动包含 PostgreSQL。
3. **Windows 一键整合包**：规划中，未来会内置便携 PostgreSQL；当前暂未实现。

通用访问地址：

- 🌐 用户首页：<http://localhost:9800>
- 🛠 管理后台：<http://localhost:9800/admin>
- 📖 API 文档：<http://localhost:9800/docs>

---

### 1. `python main.py` 源码运行（详细步骤）

这种方式需要 **Python + PostgreSQL**。如果不想手动安装 PostgreSQL，推荐用 Docker 只启动数据库，项目本体仍用 `python main.py` 跑。

#### 1）拉取项目

Windows / Linux 都一样：

```bash
git clone https://github.com/mumu-0922/GankAIGC.git
cd GankAIGC
```

#### 2）准备 PostgreSQL 数据库（推荐 Docker 方式）

Windows PowerShell：

```powershell
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

Linux：

```bash
cp .env.docker.example .env.docker
nano .env.docker
```

在 `.env.docker` 里至少修改数据库密码：

```env
POSTGRES_PASSWORD=换成你自己的数据库密码
```

然后只启动 PostgreSQL：

```bash
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.local.yml up -d postgres
```

> 如果你已经自己安装了 PostgreSQL，也可以不用这一步，但需要手动创建 `ai_polish` 用户和 `ai_polish` 数据库。

#### 3）安装 Python 依赖

Windows PowerShell：

```powershell
cd package
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux：

```bash
cd package
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

推荐使用 Python 3.11 或 3.12。

#### 4）生成并修改配置文件

第一次运行会在 `package/.env` 生成配置模板：

```bash
python main.py
```

打开 `package/.env`，重点修改这些配置：

```env
DATABASE_URL=postgresql://ai_polish:你在.env.docker里的POSTGRES_PASSWORD@127.0.0.1:5432/ai_polish
SECRET_KEY=随机长字符串
ADMIN_USERNAME=admin
ADMIN_PASSWORD=你的后台密码
ENCRYPTION_KEY=Fernet加密密钥

POLISH_MODEL=gpt-5.5
POLISH_API_KEY=你的API密钥
POLISH_BASE_URL=https://api.openai.com/v1

ENHANCE_MODEL=gpt-5.5
ENHANCE_API_KEY=你的API密钥
ENHANCE_BASE_URL=https://api.openai.com/v1

EMOTION_MODEL=gpt-5.5
EMOTION_API_KEY=你的API密钥
EMOTION_BASE_URL=https://api.openai.com/v1
```

生成密钥示例：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

第一个填 `SECRET_KEY`，第二个填 `ENCRYPTION_KEY`。

#### 5）启动项目

```bash
python main.py
```

访问：

```text
http://localhost:9800
```

---

### 2. Docker Compose 部署（推荐上线方式）

Docker Compose 会一次启动完整服务：

- `app`：GankAIGC Web 应用。
- `worker`：后台任务处理进程。
- `postgres`：PostgreSQL 16 数据库。

这种方式 **不需要单独安装 PostgreSQL**。

#### 1）拉取项目并复制配置

Windows PowerShell：

```powershell
git clone https://github.com/mumu-0922/GankAIGC.git
cd GankAIGC
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

Linux / VPS：

```bash
git clone https://github.com/mumu-0922/GankAIGC.git
cd GankAIGC
cp .env.docker.example .env.docker
nano .env.docker
```

#### 2）修改 `.env.docker`

至少修改：

```env
POSTGRES_PASSWORD=换成强数据库密码
SECRET_KEY=换成随机长字符串
ADMIN_USERNAME=admin
ADMIN_PASSWORD=换成后台强密码
ENCRYPTION_KEY=换成Fernet加密密钥
ALLOWED_ORIGINS=http://localhost:9800
```

如果部署到 VPS，并直接用 IP 访问：

```env
ALLOWED_ORIGINS=http://你的服务器IP:9800
```

如果绑定域名：

```env
ALLOWED_ORIGINS=https://你的域名
```

生成密钥：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Docker 会自动根据 `POSTGRES_PASSWORD` 拼出容器内的 `DATABASE_URL`，一般不要在 `.env.docker` 里手动添加 `DATABASE_URL`。

还可以在 `.env.docker` 中配置平台 API：

```env
POLISH_MODEL=gpt-5.5
POLISH_API_KEY=你的API密钥
POLISH_BASE_URL=https://api.openai.com/v1
```

#### 3）启动

```bash
docker compose --env-file .env.docker up --build -d
```

#### 4）检查状态

```bash
docker compose --env-file .env.docker ps
curl http://127.0.0.1:9800/health
```

返回类似下面内容表示正常：

```json
{"status":"healthy"}
```

查看日志：

```bash
docker compose --env-file .env.docker logs -f app
docker compose --env-file .env.docker logs -f worker
```

停止服务但保留数据库数据：

```bash
docker compose --env-file .env.docker down
```

更新项目：

```bash
git pull
docker compose --env-file .env.docker up --build -d
```

> 不要随便执行 `docker compose down -v`，`-v` 会删除 PostgreSQL 数据卷。

---

### 3. Windows 一键整合包（占位，暂未实现）

当前普通 Windows exe 已支持打包，但 **仍需要外部 PostgreSQL**，不适合完全零基础用户直接双击使用。

计划中的一键整合包会变成类似结构：

```text
GankAIGC-Windows/
├── start.bat
├── stop.bat
├── GankAIGC.exe
├── postgres/       # 便携 PostgreSQL
├── data/           # 数据库数据
├── logs/
└── .env
```

目标效果：解压后双击 `start.bat`，自动启动内置 PostgreSQL 和 GankAIGC。该方案后续实现后再补充详细说明。

---

## ⚙️ 配置说明

源码运行读取 `package/.env`；打包后的 exe 读取 exe 同目录 `.env`；Docker 读取 `.env.docker`。

项目 **只支持 PostgreSQL**。核心配置示例：

```properties
SERVER_HOST=0.0.0.0
SERVER_PORT=9800
APP_ENV=development
ALLOWED_ORIGINS=http://localhost:9800

DATABASE_URL=postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish

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
API_REQUEST_INTERVAL=6
REGISTRATION_ENABLED=true
WORD_FORMATTER_ENABLED=false
ADMIN_DATABASE_MANAGER_ENABLED=true
ADMIN_DATABASE_WRITE_ENABLED=false
```

关键说明：

- `REGISTRATION_ENABLED=false`：关闭邀请码注册，已有用户仍可登录。
- `WORD_FORMATTER_ENABLED=false`：不挂载 Word 排版 API，也不会出现在 OpenAPI 文档中。
- `ADMIN_DATABASE_WRITE_ENABLED=false`：数据库管理器保持只读，生产环境建议保持关闭。
- `ENCRYPTION_KEY`：用于加密用户保存的自带 API 配置，必须妥善保存。

---

## 🧭 使用流程

1. 管理员访问 `/admin` 登录后台。
2. 在「用户管理」中创建注册邀请码。
3. 用户通过邀请码注册并登录。
4. 管理员创建啤酒兑换码，用户在前台兑换啤酒。
5. 用户进入工作台，选择平台啤酒模式或自带 API 模式。
6. 提交论文文本，等待任务处理完成。
7. 查看分段结果、改写记录，并导出 `.docx` 或 `.md`。

---

## 🛠 管理后台

后台地址：

```text
http://localhost:9800/admin
```

默认账号为 `admin`；默认密码仅适合本地开发，部署前必须通过 `ADMIN_PASSWORD` 修改。

后台包含：

- 📊 **数据面板**：用户、任务、完成率、模式统计等。
- ⏳ **会话监控**：排队、处理中、历史任务。
- 👥 **用户管理**：用户、邀请码、兑换码、啤酒流水、自带 API 摘要、封禁/解封。
- 🧾 **操作日志**：记录创建邀请码、创建兑换码、充值啤酒、封禁/解封、配置变更。
- 🗄 **数据库管理**：默认只读，白名单表可查，敏感字段脱敏。
- ⚙️ **系统配置**：模型、Base URL、并发、请求间隔、思考模式等。

---

## 🗄 数据库迁移、备份与恢复

### 数据库迁移

新库或升级部署时执行：

```powershell
cd package/backend
python -m alembic upgrade head
```

### 备份 PostgreSQL

如果本机安装了 `pg_dump`：

```powershell
$env:DATABASE_URL="postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish"
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/backup-postgres.ps1
Remove-Item Env:\DATABASE_URL
```

如果 PostgreSQL 在 Docker 容器 `gankaigc-postgres` 中，也可以使用容器内的 `pg_dump`：

```powershell
New-Item -ItemType Directory -Force backups
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$file = "gankaigc_ai_polish_$ts.dump"
docker exec gankaigc-postgres pg_dump -U ai_polish -d ai_polish -F c -f "/tmp/$file"
docker cp "gankaigc-postgres:/tmp/$file" ".\backups\$file"
docker exec gankaigc-postgres rm "/tmp/$file"
```

备份、恢复和换机器说明见：[PostgreSQL 运维指南](docs/postgresql-operations.md)。

---

## ❓ 常见问题

### 端口被占用怎么办？

关闭占用 `9800` 的旧进程，或修改 `.env` / `.env.docker` 中的端口配置。

### 启动提示 PostgreSQL 连接失败？

优先检查：

- PostgreSQL 是否启动。
- `DATABASE_URL` 是否以 `postgresql://` 或 `postgresql+psycopg://` 开头。
- 用户名、密码、数据库名和端口是否正确。
- Docker 部署是否使用了 `docker compose --env-file .env.docker ...`。

### 用户无法使用自带 API？

确认用户已保存 Base URL、API Key 和模型名称，并且服务端配置了有效的 `ENCRYPTION_KEY`。

### AI 调用失败？

检查 API Key、Base URL、模型名称和网络连通性。不要把真实 API Key 提交到仓库。

---

## 🔐 安全提醒

发布到公网前必须完成：

- 修改 `ADMIN_PASSWORD`。
- 修改 `SECRET_KEY`。
- 修改 `POSTGRES_PASSWORD`。
- 设置有效的 `ENCRYPTION_KEY`。
- 备份 PostgreSQL 数据库。
- 不要提交 `.env`、`.env.docker`、数据库 dump、日志和真实 API Key。

---

## 📄 许可证

本项目基于 BypassAIGC 深度修改，继续采用 **CC BY-NC-SA 4.0** 协议发布。

未经相关版权方授权，禁止商业使用。

完整署名与来源见 [NOTICE](NOTICE)。

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=mumu-0922/GankAIGC&type=date&legend=top-left)](https://www.star-history.com/?repos=mumu-0922%2FGankAIGC&type=date&legend=top-left)
