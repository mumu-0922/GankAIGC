<div align="center">
  <img src="package/frontend/public/gankaigc-logo.svg" alt="GankAIGC Logo" width="96" />

# GankAIGC

**论文降 AI、学术润色与原创性表达增强工具**

[![Python](https://img.shields.io/badge/Python-3.11%20recommended-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React%2018-Frontend-61DAFB?logo=react&logoColor=111)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Only-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Deploy-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Release](https://img.shields.io/github/v/release/mumu-0922/GankAIGC?label=Release)](https://github.com/mumu-0922/GankAIGC/releases/latest)
[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE)

</div>

---

## ✨ 项目简介

GankAIGC 是一个面向论文文本的降 AI 与学术润色工具，采用 **FastAPI + React/Vite + PostgreSQL** 架构，支持源码运行、Docker 部署和 Windows 一键整合包。

---

## 🧪 降 AI 效果展示

以下来自朱雀 AI 检测，用于展示中文与英文文本处理前后的检测变化；实际效果会受原文质量、模型配置和处理模式影响。

### 中文文本

<table>
  <tr>
    <td width="50%" align="center"><strong>降 AI 前</strong></td>
    <td width="50%" align="center"><strong>降 AI 后</strong></td>
  </tr>
  <tr>
    <td><img src="docs/assets/zhuque-chinese-before.png" alt="中文文本降 AI 前朱雀 AI 检测截图" /></td>
    <td><img src="docs/assets/zhuque-chinese-after.png" alt="中文文本降 AI 后朱雀 AI 检测截图" /></td>
  </tr>
</table>

### 英文文本

<table>
  <tr>
    <td width="50%" align="center"><strong>降 AI 前</strong></td>
    <td width="50%" align="center"><strong>降 AI 后</strong></td>
  </tr>
  <tr>
    <td><img src="docs/assets/zhuque-english-before.png" alt="英文文本降 AI 前朱雀 AI 检测截图" /></td>
    <td><img src="docs/assets/zhuque-english-after.png" alt="英文文本降 AI 后朱雀 AI 检测截图" /></td>
  </tr>
</table>

---

## 🧩 核心功能

| 功能         | 说明                                                                            |
| ------------ | ------------------------------------------------------------------------------- |
| 📝 论文降 AI  | 支持论文润色、原创性增强、润色 + 增强、感情文章润色等模式                       |
| 👤 账号体系   | 用户通过邀请码注册，登录后进入工作台，可修改昵称和查看个人信息                  |
| 📨 邀请机制   | 管理员可创建或批量生成邀请码，支持复制和导出；普通用户只能生成 1 个自己的邀请码 |
| 🍺 啤酒额度   | 用户使用兑换码充值啤酒；平台模式按字符折算啤酒；管理员可批量生成、复制和导出兑换码 |
| 🔑 自带 API   | 用户可保存自己的 OpenAI 兼容接口配置，使用 BYOK 模式处理任务                    |
| 📚 论文项目   | 支持按论文项目归档任务，查看历史会话、分段结果和改写记录                        |
| 📦 结果导出   | 支持导出 Word `.docx` 和 Markdown `.md`                                         |
| 📢 后台公告   | 管理员可发布维护通知、模型切换通知和使用说明；支持 Markdown 编辑、预览和用户工作台渲染 |
| 🖥 Windows 包 | Release 提供一键整合包，内置便携 PostgreSQL，解压后双击 `start.bat`             |
| 🛠 管理后台   | 数据面板、会话监控、用户管理、兑换码、封禁/解封、公告管理、操作日志、系统配置   |

---

## 🏗 技术栈

- **后端**：FastAPI、SQLAlchemy、Alembic、PostgreSQL、JWT、OpenAI Python SDK
- **前端**：React 18、Vite、Tailwind CSS、React Router、Axios、Lucide React
- **任务处理**：PostgreSQL 队列；Docker 部署使用独立 worker
- **部署**：Docker Compose + PostgreSQL；Windows 一键包内置便携 PostgreSQL
- **打包**：PyInstaller、`build-oneclick.ps1`

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
│   ├── build.ps1                # Windows 普通 exe 构建脚本
│   ├── build-oneclick.ps1       # Windows 一键整合包构建脚本
│   ├── windows-oneclick/        # 一键包 start/stop/env 模板
│   └── build.sh                 # Linux/macOS 普通可执行文件构建脚本
├── docker-compose.yml
├── docker-compose.local.yml     # 本地暴露 PostgreSQL 5432 的附加配置
├── Dockerfile
├── scripts/                     # 启动诊断、PostgreSQL 备份/恢复脚本
├── docs/                        # 部署、运维、维护清单和 README 图片资源
└── .env.docker.example          # Docker 环境变量模板，不是真实密钥
```

---

## 🚀 运行与部署

按使用场景选择一种方式：

| 方式 | 适合场景 | 一句话说明 |
| ---- | -------- | ---------- |
| `python main.py` 源码运行 | 本机开发、调试、个人使用 | 需要 Python 和 PostgreSQL，可用 Docker 只启动数据库 |
| Docker Compose 部署 | 本机 Docker、VPS、正式上线 | 一次启动 Web、worker、PostgreSQL 和自动备份 |
| Windows 一键整合包 | Windows 新手直接使用 | Release 下载后解压，双击 `start.bat`，内置便携 PostgreSQL |
| 云端网站运行 | 不想自行部署、直接体验 | 访问云端网站，邀请码进群获得 |

Windows 用户如果只想直接使用，优先下载：

```text
https://github.com/mumu-0922/GankAIGC/releases/latest
```

通用访问地址：

- 🌐 用户首页：<http://localhost:9800>
- 🛠 管理后台：<http://localhost:9800/admin>
- 📖 API 文档：<http://localhost:9800/docs>

<details>
<summary><strong>1. 源码运行：python main.py</strong></summary>

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
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.local.yml up -d --wait postgres
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

推荐使用 Python 3.11。

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

如果你在 Windows 一键包或本机源码运行时使用 `cliproxy`、`new-api` 这类本地代理，
Base URL 请使用 `http://127.0.0.1:8317/v1` 这种 HTTP 地址，并同时满足：

```env
SERVER_HOST=127.0.0.1
ALLOW_LOCAL_MODEL_PROXY=true
POLISH_BASE_URL=http://127.0.0.1:8317/v1
```

修改 `SERVER_HOST` 或 `ALLOW_LOCAL_MODEL_PROXY` 后建议重启服务；本地代理安全边界按服务启动时的绑定地址判断。

不要把本机代理写成 `https://127.0.0.1:8317/v1`。本地代理模式只放行
`http://127.0.0.1:端口/v1`、`http://localhost:端口/v1`、`http://[::1]:端口/v1`
或本地 Docker 场景的 `http://host.docker.internal:端口/v1`。

本地 Docker 访问宿主机代理时，Base URL 可写成
`http://host.docker.internal:8317/v1`。公网或 VPS 部署不要开启本地代理模式；
`SERVER_HOST=0.0.0.0` 时系统会拒绝本地 HTTP 代理，必须使用公网 HTTPS
代理地址，例如 `https://proxy.example.com/v1`。

生成密钥示例：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

第一个填 `SECRET_KEY`，第二个填 `ENCRYPTION_KEY`。

#### 5）启动项目

如果 `9800` 已被旧进程占用，先释放端口：

```bash
lsof -ti :9800 | xargs -r kill
sleep 1
lsof -ti :9800 | xargs -r kill -9
```

启动：

```bash
python main.py
```

访问：

```text
http://localhost:9800
# 或
http://127.0.0.1:9800
```

#### 6）本地测试朱雀 AI 检测/降重

本机源码运行和 Windows 一键包默认不需要安装 Chrome 插件。建议确认 `package/.env` 中朱雀配置如下：

```env
ZHUQUE_DETECT_TRANSPORT=auto
ZHUQUE_DETECT_HEADLESS=false
ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
```

进入工作台后：

```text
选择「AI检测 + 降重」
↓
点击「打开朱雀页面」
↓
系统会打开/聚焦一个本机可见朱雀窗口，默认优先 Windows Chrome / Edge / Brave
↓
在朱雀窗口登录或完成验证码
↓
回到 GankAIGC，点击剩余次数右侧刷新按钮
↓
确认「朱雀账号」和「剩余次数」已同步，再提交任务
```

如果想强制指定浏览器，可在 `package/.env` 写入：

```env
ZHUQUE_DETECT_BROWSER_EXECUTABLE=/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe
# 或
ZHUQUE_DETECT_BROWSER_EXECUTABLE=/mnt/c/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe
```

本地打开的朱雀窗口是 GankAIGC 托管的检测窗口，不是 VPS browser-agent 插件窗口，也不会要求安装插件。

</details>

<details>
<summary><strong>2. Docker Compose 部署</strong></summary>

Docker Compose 会一次启动完整服务：

- `app`：GankAIGC Web 应用。
- `worker`：后台任务处理进程。
- `migrate`：持有 PostgreSQL advisory lock 的一次性 Alembic 迁移任务；成功后 `app` / `worker` 才会启动。
- `postgres`：PostgreSQL 16 数据库。
- `backup`：定时 PostgreSQL 逻辑备份。

数据库数据保存在 Docker volume `postgres_data` 中，头像等上传文件保存在宿主机 `package/uploads/`。重建 `app` / `worker` 容器不会删除这些持久化数据。

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
chmod 600 .env.docker
install -d -m 700 package/uploads backups
nano .env.docker
```

#### 2）修改 `.env.docker`

至少修改：

```env
APP_BIND_IP=127.0.0.1
POSTGRES_PASSWORD=换成强数据库密码
SECRET_KEY=换成随机长字符串
ADMIN_USERNAME=admin
ADMIN_PASSWORD=换成后台强密码
ENCRYPTION_KEY=换成Fernet加密密钥
ALLOWED_ORIGINS=http://localhost:9800
```

VPS 正式部署推荐让 1Panel/Nginx/Caddy 反向代理 `127.0.0.1:9800`，只向公网开放 80/443。绑定域名时：

```env
APP_BIND_IP=127.0.0.1
ALLOWED_ORIGINS=https://你的域名
```

如果 1Panel 的 OpenResty 运行在独立 bridge 容器中，无法访问宿主机 loopback，应把代理与 `app` 接入同一受控 Docker 网络并使用服务名转发；不要为省事重新把 9800 暴露到公网。

审计 IP 只信任明确配置的代理 peer。把 1Panel/OpenResty 直连 `app` 时实际使用的 IP 或最小 CIDR 写入 `TRUSTED_PROXY_IPS`，不要写 `0.0.0.0/0`；其他来源伪造的 `X-Forwarded-For` 会被忽略。生产默认关闭 `/docs`、`/redoc`、`/openapi.json` 和后台数据库管理器。

只有临时排障且已用云防火墙限制来源时，才允许直接用 IP 访问：

```env
APP_BIND_IP=0.0.0.0
ALLOWED_ORIGINS=http://你的服务器IP:9800
```

生成密钥：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Docker 会自动根据 `POSTGRES_PASSWORD` 拼出容器内的 `DATABASE_URL`，一般不要在 `.env.docker` 里手动添加 `DATABASE_URL`。
默认由同一数据库 owner 执行一次性迁移；如果已提前创建专用迁移角色，可同时设置 `POSTGRES_MIGRATOR_USER` 和 `POSTGRES_MIGRATOR_PASSWORD`。

上面是本地/兼容 Compose 路径。VPS 正式部署使用 `docker-compose.prod.yml` 时，
不会把整份 `.env.docker` 注入容器，而是读取 `secrets/` 下按服务拆分的 `0600`
文件，并使用 `owner(NOLOGIN) / migrator / app(DML) / backup(read-only)` 四类角色：

```bash
# 先确保 .env.docker 中现有 POSTGRES_PASSWORD/SECRET_KEY/ADMIN_PASSWORD/
# ENCRYPTION_KEY 是当前真实值；脚本会保留它们，不会在输出中打印。
sudo ./scripts/docker-secrets-init.sh
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml up -d postgres
./scripts/postgres-provision-roles.sh
```

历史数据库首次运行会拒绝自动转移对象 owner。确认备份和对象清单后，临时设置
`POSTGRES_REASSIGN_EXISTING_OBJECTS=true` 再执行一次，成功后立即改回 `false`。
完整生产步骤见 [`docs/docker-deployment.md`](docs/docker-deployment.md)。

还可以在 `.env.docker` 中配置平台 API：

```env
POLISH_MODEL=gpt-5.5
POLISH_API_KEY=你的API密钥
POLISH_BASE_URL=https://api.openai.com/v1
```

Docker/VPS 公网部署必须使用公网 HTTPS Base URL，不要开启本地代理模式：

```env
ALLOW_LOCAL_MODEL_PROXY=false
```

只有本机 Docker 测试需要连接宿主机上的本地代理时，才可以把服务改成本机绑定：

```env
SERVER_HOST=127.0.0.1
ALLOW_LOCAL_MODEL_PROXY=true
POLISH_BASE_URL=http://host.docker.internal:8317/v1
```

修改 `SERVER_HOST` 或 `ALLOW_LOCAL_MODEL_PROXY` 后建议重启服务；本地代理安全边界按服务启动时的绑定地址判断。

VPS 正式部署如果要使用朱雀 `AI检测 + 降重`，不要让服务器无头浏览器跑朱雀检测，建议在 `.env.docker` 明确使用 browser-agent：

```env
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT=900
ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120
ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS=600
ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS=25
INLINE_TASK_WORKER_ENABLED=false
```

> `.env.docker` 是生产私有配置，`git pull` 不会覆盖它。升级后如发现插件状态闪断或剩余次数同步慢，先确认 `ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120` 已写入当前 VPS 的 `.env.docker`。

#### 3）启动

```bash
docker compose --env-file .env.docker up --build -d
```

启动时 `migrate` 会先执行 Alembic。历史上由 `create_all` 创建、没有 `alembic_version` 的数据库会先做结构比对，只在结构等价或已完成显式补列后才 `stamp head`；迁移失败时 `app` / `worker` 不会启动。

任务进度事件写入 PostgreSQL `task_events` outbox，再用 `LISTEN/NOTIFY` 唤醒 SSE；断线后按 event ID 重放，通知丢失时由 1 秒数据库轮询兜底。独立 worker 即使空闲也会刷新 `worker_leases`，默认 120 秒判离线，连续恢复 3 次仍失败的任务停止自动重试。升级已有 `.env.docker` 时同步以下值：

```env
TASK_WORKER_HEARTBEAT_INTERVAL=30
TASK_WORKER_STALE_TIMEOUT_SECONDS=120
TASK_WORKER_LEASE_TIMEOUT_SECONDS=120
TASK_WORKER_MAX_ATTEMPTS=3
TASK_EVENT_POLL_INTERVAL_SECONDS=1
TASK_WORKER_STOP_GRACE_PERIOD=10m
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
docker compose --env-file .env.docker logs migrate
docker compose --env-file .env.docker logs -f backup
```

检查当前数据库迁移状态：

```bash
docker compose --env-file .env.docker run --rm migrate alembic current
docker compose --env-file .env.docker run --rm migrate alembic heads
docker compose --env-file .env.docker run --rm migrate alembic check
```

Docker 部署默认会启动自动数据库备份服务，备份文件保存在宿主机 `backups/`：

```env
BACKUP_RETENTION_DAYS=14
BACKUP_INTERVAL_SECONDS=86400
```

需要立刻手动备份一次：

```bash
docker compose --env-file .env.docker run --rm -e RUN_ONCE=true backup
```

本机 dump 现在先写 `.partial`，经 `pg_restore --list` 校验后原子改名，并生成 SHA-256。它仍和 VPS 同属一个故障域；正式上线应配置独立的加密 restic 仓库。异地快照会同时保存已校验的 PostgreSQL dump 与 `package/uploads/`，先执行一次 uploads 隔离恢复和逐文件 SHA-256 验证，再启用定时 profile：

```bash
docker compose --env-file .env.docker --profile offsite \
  run --rm \
  -e RUN_ONCE=true \
  -e VERIFY_UPLOADS_RESTORE=true \
  backup-offsite
docker compose --env-file .env.docker --profile offsite up -d backup-offsite
```

`RESTIC_REPOSITORY`、`RESTIC_PASSWORD` 及对象存储凭证只传给 `backup-offsite`，不会整份注入 app/worker。至少每周恢复一次 PostgreSQL 到隔离数据库，并重新执行 uploads 恢复校验，记录 RPO/RTO。

停止服务但保留数据库数据：

```bash
docker compose --env-file .env.docker down
```

更新项目：

```bash
# 首次升级到 uploads 持久化版本时，先从旧 app 容器导出已有头像。
mkdir -p package/uploads
APP_CONTAINER="$(docker compose --env-file .env.docker ps -q app)"
if [ -n "$APP_CONTAINER" ] && docker exec "$APP_CONTAINER" test -d /app/package/uploads; then
  docker cp "$APP_CONTAINER":/app/package/uploads/. package/uploads/
fi

git fetch --tags origin main
git checkout main
git pull --ff-only origin main
docker compose --env-file .env.docker up -d --build
```

正式 VPS 推荐不要现场重建 `main`，而是把 CI 已扫描/签名的 release digest 写入 `.env.docker`：

```env
GANKAIGC_IMAGE=ghcr.io/mumu-0922/gankaigc@sha256:<已验证digest>
```

```bash
IMAGE_REF="$(sed -n 's/^GANKAIGC_IMAGE=//p' .env.docker | tail -1)"
cosign verify \
  --certificate-identity-regexp '^https://github.com/mumu-0922/GankAIGC/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "$IMAGE_REF"
# 首次生产部署先执行 Secret/角色初始化；现有 secrets 禁止覆盖。
sudo ./scripts/docker-secrets-init.sh
./scripts/postgres-provision-roles.sh
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
./scripts/postgres-provision-roles.sh
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
curl -fsS http://127.0.0.1:9800/ready
```

回滚时只把 `GANKAIGC_IMAGE` 改回保留的上一条已验证 digest，再执行同一组 `pull/up`；数据库仅在迁移不兼容且已有恢复演练时才回滚。

> **v2.1.0 升级要求短暂维护。** 先等旧任务完成并停止旧 `app` / `worker`，再备份、拉取镜像、执行 migration，最后同时启动新服务。不要让 v2.0.x 的串行 worker 与 v2.1.0 的并发 worker 同时领取任务。完整命令见 [`docs/docker-deployment.md`](docs/docker-deployment.md#v210-short-maintenance-upgrade)。

> 旧 `.env.docker` 如果仍是 `MAX_CONCURRENT_USERS=7`，升级前请改成 `5`；v2.1.0 worker 会把不受支持的旧档位安全降为 5，之后可在后台切到 8/10。

如果这次更新包含 Chrome 插件变更，还需要在用户本机刷新插件：优先从 Release 下载最新版插件 ZIP，解压覆盖原目录，到 `chrome://extensions` 点击「重新加载」并确认版本号。例如当前 VPS browser-agent 推荐插件版本为 `0.1.10`。

进入管理后台，点击左上角版本号，可以检查 GitHub 最新 Release 并复制 SSH 升级命令。后台不会直接控制 Docker；需要 SSH 到 VPS 的项目目录手动执行上面的命令。

> 不要随便执行 `docker compose down -v`、`docker volume rm gankaigc_postgres_data`，也不要在未备份时删除 `package/uploads/`。这些操作会导致数据库或头像文件丢失。

</details>

<details>
<summary><strong>3. Windows 一键整合包</strong></summary>

适合 Windows 用户直接使用：内置便携 PostgreSQL，解压后双击启动。

1. 到 [Releases](https://github.com/mumu-0922/GankAIGC/releases/latest) 下载 `GankAIGC-Windows-OneClick.zip`。
2. 解压到英文路径，双击 `start.bat`。
3. 打开 <http://localhost:9800>；后台为 <http://localhost:9800/admin>。
4. 首次后台账号密码会显示在窗口里，也会写入 `logs/first-run-admin.txt`。
5. 停止服务双击 `stop.bat`。

朱雀检测：一键包默认使用本机可见 Chrome / Edge / Brave，不需要 Chrome 插件，也不需要 `playwright install`。在工作台点击「打开朱雀页面」，登录/验证后刷新「剩余次数」即可。

> 不要删除 `data/`；升级新版时先备份 `.env`、`data/`、`logs/`。更多说明见解压目录里的 `README.txt`。

</details>

<details>
<summary><strong>4. 云端网站运行</strong></summary>

网址：<https://ga.mumubuku.top>

邀请码进群获得，QQ群：`1071743320`

</details>

---

## 👥 v2.1.0 多用户并发说明

`100` 个注册用户不等于让 `100` 个任务同时调用模型。GankAIGC 会接收请求并写入 PostgreSQL durable queue，再按可用处理槽公平领取；这样能承载更多在线用户，同时避免 3 核 4G VPS、模型 API 或同一 API Key 被瞬时打爆。

- **3 核 4G 推荐从 5 并发起步**：后台「系统配置」可热切换全站任务并发 `5 / 8 / 10`。先跑 5，观察 CPU、内存、API `429` 和平均任务耗时，再逐级放到 8、10。
- **降档不强杀任务**：从 10 调回 5 时，已经运行的任务会继续完成，只暂停领取超出新上限的任务。
- **每用户公平排队**：同一用户最多 1 个任务处于运行或等待本机朱雀插件状态，并可再排队 2 个任务，避免单个用户占满全站。
- **相同 API Key 单独限流**：后台可选 `1 / 2 / 4`，默认 2；不同 BYOK Key 独立计算。收到 `429` 时会先释放请求槽，再做有界退避。
- **朱雀等待不占处理槽**：任务显示「等待本机朱雀插件」时已经释放 worker slot；插件回传、失败或超时后由 PostgreSQL 恢复调度。

推荐起始配置：

```properties
MAX_CONCURRENT_USERS=5
API_KEY_CONCURRENCY=2
MAX_PENDING_SESSIONS_PER_USER=3
TASK_WORKER_MAX_CONCURRENCY=10
```

其中 `TASK_WORKER_MAX_CONCURRENCY=10` 是 worker 的容量上限，日常实际并发由后台的 `MAX_CONCURRENT_USERS` 控制，不应直接把上限理解成默认同时运行 10 个任务。

---

## ⚙️ 配置说明

源码运行读取 `package/.env`；打包后的 exe 读取 exe 同目录 `.env`；Docker 读取 `.env.docker`。

项目 **只支持 PostgreSQL**。核心配置示例见下方。

<details>
<summary><strong>展开查看核心配置示例</strong></summary>

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
API_KEY_CONCURRENCY=2
MAX_PENDING_SESSIONS_PER_USER=3
TASK_WORKER_MAX_CONCURRENCY=10
API_REQUEST_INTERVAL=6
REGISTRATION_ENABLED=true
WORD_FORMATTER_ENABLED=false
ADMIN_DATABASE_MANAGER_ENABLED=false
ADMIN_DATABASE_WRITE_ENABLED=false

# 文档解析：PDF 默认使用 MinerU 精准解析；Word(.docx)/Markdown/TXT 使用本地解析。
PDF_STRUCTURE_ENGINE=mineru
MINERU_BASE_URL=https://mineru.net
MINERU_API_TOKEN=
MINERU_MODEL_VERSION=vlm
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_IS_OCR=false
MINERU_LANGUAGE=ch
MINERU_TIMEOUT_SECONDS=300
MINERU_POLL_INTERVAL_SECONDS=2.0

# 朱雀检测传输：本机源码/一键包保持 auto；VPS/Docker 推荐 browser_agent。
ZHUQUE_DETECT_TRANSPORT=auto
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT=900
ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120
ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS=600
ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS=25
```

关键说明：

- `REGISTRATION_ENABLED=false`：关闭邀请码注册，已有用户仍可登录。
- `WORD_FORMATTER_ENABLED=false`：不挂载 Word 排版 API，也不会出现在 OpenAPI 文档中。
- `ADMIN_DATABASE_WRITE_ENABLED=false`：仅控制保留的管理员数据库 API 写入能力；当前后台界面不暴露数据诊断/数据库管理页，生产环境建议保持关闭。
- `ENCRYPTION_KEY`：用于加密用户保存的自带 API 配置，必须妥善保存。
- 后台「系统配置 → 文档解析设置」可直接配置 MinerU Token、Base URL、PDF 解析引擎、OCR/表格/公式等选项；MinerU 当前主要用于 PDF，Word(.docx)、Markdown、TXT 使用本地解析链路。
- `ZHUQUE_DETECT_TRANSPORT=auto`：本机源码/Windows 一键包默认，自动使用本机可见浏览器检测链路。
- `ZHUQUE_DETECT_TRANSPORT=browser_agent`：VPS/Docker 推荐模式，朱雀检测由用户本机 Chrome 插件执行。
- `ZHUQUE_SERVER_HEADLESS_FALLBACK=false`：VPS 推荐保持关闭，避免服务器无头浏览器触发朱雀验证码/风控。

</details>

---

## 🧭 使用流程

1. 管理员访问 `/admin` 登录后台。
2. 在「用户管理」中创建或批量生成注册邀请码，也可复制/导出邀请码。
3. 用户通过邀请码注册并登录。
4. 管理员创建或批量生成啤酒兑换码，用户在前台兑换啤酒。
5. 管理员可在「公告」中用 Markdown 发布维护通知、模型切换通知或使用说明。
6. 用户进入工作台，选择平台啤酒模式或自带 API 模式。
7. 如使用朱雀 AI 检测/降 AI：本机/一键包部署点击「打开朱雀页面」并在本机浏览器完成登录或验证码；VPS/browser-agent 部署先按工作台提示生成配对码并连接 Chrome 插件。
8. 可直接粘贴论文，或上传 PDF、Word(.docx)、Markdown(.md/.markdown)、TXT 文档自动解析到输入框。
9. 提交论文文本，等待任务处理完成。
10. 查看分段结果、改写记录，并导出 `.docx` 或 `.md`。

---

## 🐦 朱雀登录与检测浏览器

GankAIGC 不会读取用户默认 Chrome 的个人 Cookie，而是通过当前 GankAIGC 用户独立保存一份朱雀状态。不同部署方式的朱雀链路不同：

- 本机源码 / Windows 一键包：使用本机可见浏览器托管链路，点击「打开朱雀页面」后自动打开或聚焦一个 GankAIGC 专用朱雀窗口。
- VPS / Docker：使用 browser-agent Chrome 插件，让用户本机 Chrome 执行朱雀检测。

本机/一键包流程：

```text
工作台点击「打开朱雀页面」
↓
后端优先聚焦已存在的本机朱雀检测窗口
↓
没有窗口时自动打开专用 Chrome/Edge/Brave 朱雀窗口
↓
用户在该本机窗口登录朱雀或完成验证码
↓
工作台点击刷新/同步，显示朱雀账号与剩余次数
↓
检测时复用同一个本机朱雀窗口
```

凭证和状态默认保存在：

```text
package/data/zhuque/users/user_<id>/creds_latest.json
package/data/zhuque/users/user_<id>/browser_state.json
```

本机可见检测时，系统会自动探测 Chrome / Edge / Brave：

- Windows / WSL：优先使用可控的 Windows Chrome / Edge / Brave 检测窗口。
- Linux 桌面：自动查找 `/usr/bin/google-chrome`、`chromium`、`microsoft-edge`、`brave-browser` 等常见浏览器。
- Linux 服务器 / 无桌面：会回退到 Playwright/Chromium；如果朱雀要求人工验证码，需要 VNC/X11/远程桌面等可视化环境。

普通用户不需要手动运行 `--remote-debugging-port`，也不需要查 Chrome Profile。日常只需：

1. 在工作台点击「打开朱雀页面」。
2. 在自动打开或聚焦的本机朱雀窗口里登录/过验证码。
3. 回到工作台点击剩余次数右侧刷新按钮，同步 `朱雀账号` / `剩余次数`。
4. 直接提交检测/降 AI；如遇验证码，仍在同一个朱雀窗口里完成。
5. 如果检测窗口卡住或状态异常，关闭该检测窗口后重新点击「打开朱雀页面」即可。

### VPS / Docker：使用 Chrome 插件执行朱雀检测

VPS 上不要把朱雀检测交给服务器无头 Chromium。朱雀会识别 VPS/headless 环境并触发验证码/风控，导致 `AI检测 + 降重` 不稳定。VPS 推荐使用 browser-agent：服务器只创建检测任务，用户本机 Chrome 插件打开/复用朱雀页面并把结果回传。

当前 browser-agent 插件推荐版本：`0.1.10`。该版本会同时读取朱雀页面文本、检测响应和 Vue 运行时配额状态；支持未登录游客检测，并阻止验证码恢复时为同一个作业重复点击检测。朱雀省略零值“疑似 AI”分类、只显示“人工 + AI”两个百分比时也会正常解析并回传。它还修正了 Chrome MV3 低于最小间隔的 alarm 不会创建、导致“已配对/在线但不领取任务”的问题，并在插件启动后立即领取一次任务。页面刷新、手动点击「同步/刷新」和检测任务消耗次数后，都会尽快刷新工作台的 `朱雀账号` / `剩余次数`。

VPS `.env.docker` 推荐配置：

```properties
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT=900
ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120
ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS=600
ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS=25
INLINE_TASK_WORKER_ENABLED=false
```

#### 1. 安装或升级插件

1. 优先到 [GitHub Releases](https://github.com/mumu-0922/GankAIGC/releases/latest) 下载 `GankAIGC-Browser-Extension-v0.1.10.zip`；旁边的 `.zip.sha256` 可用于核对下载完整性。开发者也可直接使用源码里的 `browser-extension/`。
2. 解压 ZIP，确认所选目录的根层直接存在 `manifest.json`，不要选 ZIP 文件或它的上级目录。
3. 在 Chrome 地址栏打开 `chrome://extensions`，开启右上角「开发者模式」。
4. 首次安装点击「加载已解压的扩展程序」，选择刚解压的目录。
5. 已安装旧版本时先用新版文件覆盖原目录，再点击插件卡片上的「重新加载」，不要重复加载第二份插件。
6. 在插件卡片的「详细信息」中确认版本为 `0.1.10` 或更高；升级后同时刷新已打开的朱雀页面，让新版 content script 重新注入。

Linux / macOS 可这样校验插件 ZIP；Windows PowerShell 可使用 `Get-FileHash <zip> -Algorithm SHA256`，并与 `.sha256` 文件中的值比较：

```bash
sha256sum -c GankAIGC-Browser-Extension-v0.1.10.zip.sha256
```

如果 GankAIGC 使用自定义域名，先把站点 Origin 加入 `browser-extension/manifest.json` 的 `host_permissions`，然后重新加载插件。例如：

```json
"https://gankaigc.example.com/*"
```

只填写实际使用的 GankAIGC Origin，不要添加 `<all_urls>`，也不要把 `/api` 拼进 Origin。

#### 2. 将插件与 GankAIGC 配对

1. 登录 GankAIGC，进入工作台并选择 `AI检测 + 降重`。
2. 在「朱雀 AI 检测」卡片中点击「生成配对码」。配对码默认 10 分钟过期且只能成功使用一次；失效后重新生成即可。
3. 点击 Chrome 工具栏中的 GankAIGC 插件图标，在弹窗中填写：
   - **GankAIGC 地址**：完整站点地址，例如 `https://gankaigc.example.com`；本地测试使用 `http://127.0.0.1:9800`。不要填写 `/api`，末尾 `/` 可省略。
   - **配对码**：工作台刚生成的 `GANK-XXXX`。
   - **设备名**：用于区分浏览器，例如 `Chrome on Windows`。
4. 点击「配对插件」。插件弹窗应显示「已配对」，工作台应在数秒内显示「插件在线」。

配对信息保存在当前 Chrome Profile 的 `chrome.storage.local`。正常升级/重新加载插件不会丢失配对；清除浏览器扩展数据或点击「清除本机配对」后需要重新生成配对码。

#### 3. 打开朱雀并执行检测

1. 在工作台点击「打开朱雀页面」，插件会打开或复用本机 `https://matrix.tencent.com/ai-detect/` 标签页。
2. 朱雀页面显示可用编辑器和「立即检测」时，未登录也可使用游客次数；工作台会显示「游客模式」。只有朱雀明确要求时才登录账号。
3. 回到工作台，点击剩余次数右侧的刷新按钮，同步 `朱雀账号`、游客状态和 `剩余次数`。
4. 输入至少 350 个有效字符的自然正文，提交 `AI检测 + 降重` 任务。建议正文中至少有一个 120～200 字的完整段落，避免所有段落被判为短文本。
5. 保持 Chrome 与朱雀标签页打开。插件会领取任务、写入正文并为同一个 browser-agent job 最多点击一次「立即检测」。
6. 如果出现验证码，在同一个朱雀标签页中人工完成；不要再次手动点击「立即检测」。插件会继续等待原任务并在验证后读取结果。
7. 检测完成后，插件会把 AI 率、分类比例和剩余次数回传 GankAIGC；任务随后进入降重，只有发生真实改写时才会再次复检。

正常链路：

```text
工作台显示插件在线
→ 插件领取 browser-agent job
→ 本机朱雀完成检测
→ 插件回传 /api/browser-agent/jobs/<job_id>/complete
→ GankAIGC 进入降重或直接完成
```

#### 4. 本地源码测试插件

本地源码默认使用 `auto`，不会经过 Chrome 插件。需要专门验收 browser-agent 时，把 `package/.env` 临时改为：

```properties
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
INLINE_TASK_WORKER_ENABLED=true
```

重启 `python main.py` 后，在插件中填写：

```text
http://127.0.0.1:9800
```

本地源码测试保留 `INLINE_TASK_WORKER_ENABLED=true`；VPS/Docker 的独立 worker 部署仍使用前文配置的 `false`。

#### 5. 验收标准

- 插件弹窗显示「已配对」，工作台显示「插件在线」。
- 未登录但朱雀游客入口可用时，工作台显示「游客模式」，不会强制要求登录。
- 一次初检通常只减少一次朱雀次数；验证码恢复不会为同一个 job 重复点击检测。
- 朱雀结果页完成后，GankAIGC 不再长时间停留在「处理中 0 秒」。
- 连续执行两条任务时，第二条不会复用第一条的旧结果。

#### 6. 常见问题

- **插件已配对但工作台显示离线**：确认 Chrome 正在运行、插件中的站点地址可访问、当前域名已加入 `host_permissions`；重新加载插件后等待一个 heartbeat 周期，仍离线则撤销旧设备并重新配对。
- **显示插件在线但朱雀未登录**：这是两个独立状态。游客入口可用时可以直接检测；只有朱雀页面要求时才登录。
- **朱雀已出结果但 GankAIGC 没继续**：确认插件版本至少为 `0.1.10`，重新加载插件并刷新朱雀页面后新建测试任务；后端正常会出现 `POST /api/browser-agent/jobs/<job_id>/complete 200`。
- **配对码无效或已使用**：回到工作台重新生成；不要复用已经成功配对过的配对码。
- **本地测试始终走内置浏览器**：确认 `ZHUQUE_DETECT_TRANSPORT=browser_agent` 已写入 `package/.env` 并重启后端。
- **需要升级插件**：更新源码 → `chrome://extensions` 点击「重新加载」→ 确认版本 → 刷新朱雀页面。正常情况下无需重新配对。

如需单独分发或排查插件，可继续查看 [`browser-extension/README.md`](browser-extension/README.md)。

注意：`插件在线` 只代表 Chrome 插件已连接 VPS，不等于朱雀已登录。VPS 模式下朱雀游客可用性、登录、验证码和剩余次数都以用户本机 Chrome 的朱雀页面为准。

安全边界：browser-agent 不需要公开 Chrome DevTools Protocol，不需要在用户电脑上手动启动 `--remote-debugging-port`，插件权限只应覆盖你的 GankAIGC 站点和 `https://matrix.tencent.com/*`，不要配置 `<all_urls>`。

本机源码运行、Windows 一键包或带桌面的个人电脑部署，继续使用 `ZHUQUE_DETECT_TRANSPORT=auto` 或显式 `local_browser`，无需安装插件。

高级部署可通过环境变量覆盖自动行为：

```properties
ZHUQUE_DETECT_HEADLESS=false
ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true
ZHUQUE_DETECT_CDP_ENDPOINT=
ZHUQUE_DETECT_BROWSER_EXECUTABLE=
ZHUQUE_DETECT_BROWSER_USER_DATA_DIR=
```

安全说明：GankAIGC 不会无授权读取用户默认浏览器的个人登录态，避免误读或泄露其他网站 Cookie。

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
- 🛡 **运维状态**：检查数据库、worker、自动备份、版本更新、初始化事项和模型连接。
- 👥 **用户管理**：新版后台分为用户列表、邀请码管理、兑换码、啤酒流水、API 配置；用户列表支持搜索、筛选、封禁/启用、充值啤酒和无限啤酒设置。
- 📢 **公告管理**：发布、启用/隐藏、编辑和删除公告；支持 Markdown 工具栏、实时预览和用户工作台渲染。
- 🧾 **操作日志**：记录创建邀请码、创建兑换码、充值啤酒、公告、封禁/解封、配置变更。
- ⚙️ **系统配置**：模型、Base URL、并发、请求间隔、思考模式等。

<details>
<summary><strong>展开查看用户管理细节</strong></summary>

用户管理内部分为 5 个工作区：

- **用户列表**：按 ID、用户名、昵称搜索，按状态和 API 配置筛选；支持红色封禁、启用、充值啤酒、设置/取消无限啤酒，用户详情右侧只保留左侧未覆盖的补充信息。
- **邀请码管理**：支持单个创建、批量生成 `10/50/100`、多选复制、CSV/TXT 导出和停用/启用。
- **兑换码**：支持单个创建、批量生成 `10/50/100`、多选复制、CSV/TXT 导出。
- **啤酒流水**：查看充值、兑换、降 AI 消耗和失败退款记录。
- **API 配置**：只展示用户自带 API 的 Base URL、模型名和 API Key 后四位，不展示完整密钥。

</details>


<details>
<summary><strong>展开查看公告 Markdown 能力</strong></summary>

公告编辑器支持：

- **基础排版**：标题、加粗、斜体、删除线、引用和分割线。
- **列表结构**：无序列表、有序列表、任务列表。
- **内容组件**：链接、代码块、表格。
- **编辑体验**：撤销、重做、展开编辑区、管理端实时预览。
- **展示安全**：用户工作台复用同一套基础 Markdown 渲染组件，不使用 `dangerouslySetInnerHTML`。

</details>

---

<details>
<summary><strong>🗄 数据库迁移、备份与恢复</strong></summary>

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

</details>

<details>
<summary><strong>❓ 常见问题</strong></summary>

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

如果提示“你正在使用本地/内网模型地址”，按部署方式处理：

- Windows 一键包本机使用：后台把 `SERVER_HOST` 改为 `127.0.0.1`，打开“允许本地 HTTP 模型代理”，Base URL 填 `http://127.0.0.1:端口/v1`。
- 本地 Docker 测试：Base URL 填 `http://host.docker.internal:端口/v1`。
- 云端/VPS/公网部署：不要填 `127.0.0.1`、`localhost`、`192.168.x.x`、`10.x.x.x` 或 `172.16-31.x.x`，必须使用公网 HTTPS 地址，例如 `https://proxy.example.com/v1`。

### AI 调用失败？

检查 API Key、Base URL、模型名称和网络连通性。不要把真实 API Key 提交到仓库。

</details>

## 🔐 安全提醒

发布到公网前必须完成：

- 修改 `ADMIN_PASSWORD`。
- 修改 `SECRET_KEY`。
- 修改 `POSTGRES_PASSWORD`。
- 设置有效的 `ENCRYPTION_KEY`。
- 备份 PostgreSQL 数据库。
- 不要提交 `.env`、`.env.docker`、数据库 dump、日志和真实 API Key。
- 保持默认浏览器安全响应头开启，包括 CSP、点击劫持防护、MIME 嗅探防护、来源策略和权限策略。
- 公网或 VPS 部署不要开启本地 HTTP 模型代理，模型 Base URL 使用公网 HTTPS 地址。

---

## 📄 许可证

本项目基于 BypassAIGC 深度修改，继续采用 **CC BY-NC-SA 4.0** 协议发布。

未经相关版权方授权，禁止商业使用。

完整署名与来源见 [NOTICE](NOTICE)。

---

## 🙏 致谢

[![感谢 linux.do 社区](https://img.shields.io/badge/感谢-linux.do%20社区-00A971?style=for-the-badge)](https://linux.do)

---

## 💬 QQ 群

QQ群：`1071743320`

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=mumu-0922/GankAIGC&type=date&legend=top-left)](https://www.star-history.com/?repos=mumu-0922%2FGankAIGC&type=date&legend=top-left)
