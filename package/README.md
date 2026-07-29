# GankAIGC - 可执行文件打包

本目录包含将前后端项目打包为普通可执行文件和 Windows 一键整合包的代码与配置。

当前稳定主线是「账号注册 + 用户登录 + 邀请码注册 + 兑换码充值啤酒 + 啤酒流水 + 降 AI 工作台 + 后台运维状态」。Word 排版相关后端代码仍作为实验模块保留，但默认关闭，前端不暴露排版入口。

当前应用版本写在 `VERSION`，后台左上角版本号和 Docker 镜像内版本显示都会读取这个文件。

## 目录结构

```
package/
├── backend/           # 后端代码（修改版，支持 exe 模式）
├── frontend/          # 前端代码（修改版，生产环境配置）
├── static/            # 前端生产构建产物，python main.py 和 exe 会读取这里
├── main.py            # 统一入口文件
├── VERSION            # 应用版本号
├── app.spec           # PyInstaller 打包配置
├── requirements.txt   # Python 依赖
├── build.sh           # Linux/macOS 构建脚本
├── build.ps1          # Windows 普通 exe 构建脚本
├── build-oneclick.ps1 # Windows 一键整合包构建脚本
├── windows-oneclick/  # 一键包 start/stop/env 模板
└── README.md          # 本文件
```

## 本地构建

<details>
<summary><strong>展开查看普通 exe 和一键包构建命令</strong></summary>

### 前置条件

- Python 3.11 或 3.12（推荐 3.11，避免 Python 3.13 与旧版 PyInstaller 兼容问题）
- Node.js 18+
- pip 和 npm

### 构建步骤

**Linux/macOS:**
```bash
cd package
chmod +x build.sh
./build.sh
```

**Windows 普通 exe:**
```powershell
cd package
.\build.ps1
```

普通 exe 位于 `dist/GankAIGC.exe`，运行时仍需要外部 PostgreSQL。

**Windows 一键整合包（内置便携 PostgreSQL）:**
```powershell
cd package

# 传入已解压 PostgreSQL 目录
.\build-oneclick.ps1 -PostgresRoot C:\pgsql -CreateZip

# 或传入 PostgreSQL Windows binaries ZIP
.\build-oneclick.ps1 -PostgresZip C:\Downloads\postgresql-windows-x64-binaries.zip -CreateZip
```

一键包位于 `dist/GankAIGC-Windows/`，压缩包位于 `dist/GankAIGC-Windows-OneClick.zip`。一键包默认写入本机朱雀浏览器配置：`ZHUQUE_DETECT_TRANSPORT=auto`、`ZHUQUE_DETECT_HEADLESS=false`、`ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true`、`ZHUQUE_SERVER_HEADLESS_FALLBACK=false`，无需安装 browser-agent 插件。

</details>

### 前端生产静态包

修改 `frontend/src/` 后，需要重新构建并同步到 `static/`，否则 `python main.py`、Docker 和 exe 仍会使用旧页面：

```powershell
cd package/frontend
npm ci
npm run build
cd ../..
robocopy package\frontend\dist package\static /MIR
git add package/frontend
git add -f package/static
```

`package/static` 被 `.gitignore` 忽略，提交生产包时需要 `git add -f package/static`。

## 发布方式

当前公开 Release 主要发布 Windows 一键整合包：

```text
GankAIGC-Windows-OneClick.zip
GankAIGC-Browser-Extension-v0.1.10.zip
GankAIGC-Browser-Extension-v0.1.10.zip.sha256
```

Chrome 插件 ZIP 仅用于 VPS/browser-agent 模式，解压后根目录直接包含 `manifest.json`。本机源码和 Windows 一键包默认走本机可见浏览器，不需要安装插件。

上传前建议本地重新构建：

```powershell
cd package
.\build-oneclick.ps1 -PostgresZip C:\Downloads\postgresql-windows-x64-binaries.zip -CreateZip
```

构建后建议在 `dist\GankAIGC-Windows\` 里双击 `start.bat` 做一次本机验收：进入工作台选择「AI检测 + 降重」→「打开朱雀页面」→确认打开/聚焦 Windows Chrome/Edge/Brave 且不要求安装插件。

然后用 GitHub CLI 覆盖 Release 附件：

```powershell
gh release upload v2.1.0 .\dist\GankAIGC-Windows-OneClick.zip
```

GitHub Actions 工作流会在推送 `v*` 标签时构建普通 Windows/Linux/macOS 可执行文件；当前公开 Release 仍优先使用本地构建并上传的 Windows 一键整合包。

### 标签发布

```bash
git tag -a v2.1.0 -m "GankAIGC v2.1.0"
git push origin v2.1.0
```

发布新版本时同时更新：

- `VERSION`
- `backend/app/config.py` 中的 `DEFAULT_APP_VERSION`
- 根目录 README 的使用说明，如部署或后台行为有变化

### 常见构建产物

- `GankAIGC-Windows.zip` - GitHub Actions 自动构建的 Windows 普通可执行文件，需要外部 PostgreSQL
- `GankAIGC-Windows-OneClick.zip` - Windows 一键整合包，内置便携 PostgreSQL
- `GankAIGC-Linux.tar.gz` - GitHub Actions 自动构建的 Linux 可执行文件
- `GankAIGC-macOS.tar.gz` - GitHub Actions 自动构建的 macOS 可执行文件
- `GankAIGC-Browser-Extension-v0.1.10.zip` - VPS/browser-agent Chrome 插件，解压后加载包含 `manifest.json` 的目录
- `GankAIGC-Browser-Extension-v0.1.10.zip.sha256` - 插件 ZIP 的 SHA-256 完整性校验文件

## 运行说明

普通 exe：

1. 下载对应平台的可执行文件。
2. 解压到任意目录。
3. 首次运行会自动创建 `.env` 配置文件模板。
4. 编辑 `.env`，填入 PostgreSQL `DATABASE_URL`、API Key、管理员密码和密钥。
5. 再次运行程序。

Windows 一键整合包：

1. 解压 `GankAIGC-Windows-OneClick.zip`。
2. 双击 `start.bat`。
3. 首次运行会自动初始化 `data/` 下的 PostgreSQL，并生成 `.env`。
4. 后台密码会显示在窗口中，并保存到 `logs/first-run-admin.txt`。
5. 停止服务双击 `stop.bat`。

源码本地测试常用命令：

```bash
cd /home/dev/code/GankAIGC
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.local.yml up -d --wait postgres

cd /home/dev/code/GankAIGC/package
source venv/bin/activate
lsof -ti :9800 | xargs -r kill
sleep 1
lsof -ti :9800 | xargs -r kill -9
python main.py
```

访问：

```text
http://127.0.0.1:9800
```

### 配置文件说明

`.env` 文件会保存在可执行文件同目录下。数据库只支持 PostgreSQL，请在 `.env` 中配置 `DATABASE_URL`。

源码运行时降 AI 任务会先进入 PostgreSQL 队列。exe / `python main.py` 默认启用 inline worker；Docker 部署则由独立 worker 服务消费队列。worker 会定期刷新心跳，长时间无心跳的处理中任务会自动恢复为排队状态。

v2.1.0 支持全站 `5 / 8 / 10` 并发热切换，3 核 4G 默认从 5 开始；降档不会强杀运行任务。同一用户最多 1 个运行或等待朱雀插件的任务，并可再排队 2 个任务。相同 API Key 并发可选 `1 / 2 / 4`、默认 2，不同 BYOK Key 独立限流；等待插件回传时不占 worker slot。推荐配置为：

```properties
MAX_CONCURRENT_USERS=5
API_KEY_CONCURRENCY=2
MAX_PENDING_SESSIONS_PER_USER=3
TASK_WORKER_MAX_CONCURRENCY=10
```

Docker 部署会先运行一次性 `migrate` 服务，迁移成功后才启动 `app` / `worker`；生产进程本身不再执行启动 DDL。任务进度通过 PostgreSQL outbox + `LISTEN/NOTIFY` 跨进程传递，断线可按 event ID 重放；worker 空闲时也会刷新独立 lease。默认还会启动 `backup` 服务，每天自动备份 PostgreSQL 到宿主机 `backups/`。头像等上传文件持久化在宿主机 `package/uploads/`，升级重建容器前不要删除；启用 offsite restic profile 后会同时备份已校验 dump 与 uploads，并可做隔离恢复/SHA-256 比对。后台「运维状态」可以查看数据库、worker、备份、版本更新和初始化检查。

模型 Base URL 默认要求公网 HTTPS 地址。Windows 一键包本机使用 `cliproxy`、`new-api` 等本地代理时，后台把 `SERVER_HOST` 设为 `127.0.0.1`，打开“允许本地 HTTP 模型代理”，Base URL 填 `http://127.0.0.1:端口/v1`。不要写成 `https://127.0.0.1:端口/v1`。公网或 VPS 部署不要开启本地代理模式，必须使用公网 HTTPS Base URL。

### 朱雀登录与检测浏览器

GankAIGC 不读取用户默认 Chrome 的个人登录态。本机源码运行和 Windows 一键包默认使用本机可见浏览器托管链路：工作台点击「打开朱雀页面」后，后端会优先聚焦已存在的朱雀窗口，没有窗口才自动打开一个专用 Chrome/Edge/Brave 朱雀窗口。用户在该窗口里登录或完成验证码后，工作台同步 `朱雀账号` / `剩余次数`。

朱雀 cookie/localStorage 与页面状态保存在当前 GankAIGC 用户目录：

```text
package/data/zhuque/users/user_<id>/creds_latest.json
package/data/zhuque/users/user_<id>/browser_state.json
```

后续朱雀检测会复用同一个可见检测窗口。Windows/WSL 会优先使用可控的 Windows Chrome/Edge/Brave；Linux 桌面会自动查找常见系统浏览器。

VPS / Docker 不建议使用服务器无头 Chromium 做朱雀检测，因为容易触发朱雀验证码或风控。正式 VPS 部署推荐改用 Chrome 插件 browser-agent：GankAIGC 服务器创建检测任务，用户本机 Chrome 插件打开/复用朱雀页面完成检测并回传结果。当前推荐插件版本为 `0.1.10`，支持游客/未登录检测、从页面文本/检测响应/Vue 状态同步剩余次数、解析朱雀省略零值疑似分类的双百分比结果页，并保证单个插件作业跨验证码恢复时只提交一次检测；同时使用 Chrome 支持的 30 秒 MV3 alarm 并在启动后立即领取任务，避免“在线但不领取”。

VPS `.env.docker` 推荐：

```properties
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT=900
ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT=120
ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS=600
ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS=25
INLINE_TASK_WORKER_ENABLED=false
```

本机源码运行、Windows 一键包或带桌面的个人电脑部署继续使用 `ZHUQUE_DETECT_TRANSPORT=auto` 或 `local_browser`，无需安装插件。

插件安装优先从 GitHub Release 下载 `GankAIGC-Browser-Extension-v0.1.10.zip` 与对应 `.sha256`，校验后解压，在 Chrome `chrome://extensions` 开启开发者模式并加载根层含 `manifest.json` 的目录。开发者也可直接加载源码中的 `browser-extension/`。进入工作台选择 `AI检测 + 降重`，点击「生成配对码」，在插件弹窗填写站点地址、配对码和设备名。工作台显示「插件在线」后，点击「打开朱雀页面」；游客次数可直接检测，只有页面要求时才需登录或完成验证码。`插件在线` 不等于 `朱雀已登录`；未登录但页面可用时，工作台会显示 `游客模式`。

普通用户不需要手动设置 Chrome `--remote-debugging-port` 或 Profile。VPS browser-agent 模式也不要公开 CDP 端口；插件权限只应包含你的 GankAIGC 站点和 `https://matrix.tencent.com/*`。高级本机部署可在 `.env` 中覆盖：

```properties
ZHUQUE_DETECT_HEADLESS=false
ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true
ZHUQUE_DETECT_CDP_ENDPOINT=
ZHUQUE_DETECT_BROWSER_EXECUTABLE=
ZHUQUE_DETECT_BROWSER_USER_DATA_DIR=
```

GankAIGC 不会无授权读取默认浏览器的个人 Cookie，避免误读或泄露其他网站登录态。

文档上传支持 PDF、Word(.docx)、Markdown(.md/.markdown)、TXT。后台「系统配置 → 文档解析设置」可直接配置 MinerU Token、Base URL、PDF 解析引擎、OCR/表格/公式等选项；MinerU 当前主要用于 PDF 高精度解析，Word(.docx)、Markdown、TXT 默认使用本地解析链路。

Docker 更新采用手动 SSH 模式：后台只检测 GitHub Release 并提供复制命令，不直接控制 Docker，也不挂载 Docker socket。VPS 上升级通常执行：

```bash
# 首次升级到 uploads 持久化版本时先导出旧容器内的头像。
mkdir -p package/uploads
APP_CONTAINER="$(docker compose --env-file .env.docker ps -q app)"
if [ -n "$APP_CONTAINER" ] && docker exec "$APP_CONTAINER" test -d /app/package/uploads; then
  docker cp "$APP_CONTAINER":/app/package/uploads/. package/uploads/
fi

git fetch --tags origin main
git pull --ff-only origin main
docker compose --env-file .env.docker up -d --build
```

### 访问地址

- 用户界面: http://localhost:9800
- 管理后台: http://localhost:9800/admin
- API 文档: http://localhost:9800/docs

## 与原项目的区别

1. **运行方式**：原项目需要分别启动前端和后端服务，exe 版本一键启动
2. **配置位置**：exe 版本的 `.env` 在 exe 同目录，数据库连接由 `DATABASE_URL` 指向 PostgreSQL
3. **前端访问**：exe 版本前后端在同一端口，无需代理

## 技术细节

### 前端修改
- 修改 `vite.config.js` 添加生产环境构建配置
- 修改 API 配置，生产环境直接使用根路径
- 后台用户管理分为用户列表、邀请码管理、兑换码、啤酒流水和 API 配置；用户列表支持搜索、状态筛选、API 配置筛选、封禁/启用、充值和无限啤酒。

### 后端修改
- 修改 `config.py`，支持动态获取 exe 目录下的配置文件
- 数据库统一使用 PostgreSQL
- 增加浏览器安全响应头、模型 Base URL 安全校验、Docker 手动升级边界和 PostgreSQL 备份状态读取。

### 统一入口
- `main.py` 创建 FastAPI 应用
- 挂载静态文件服务前端页面
- 处理 SPA 路由（admin、workspace 等）
- 自动打开浏览器

### PyInstaller 配置
- 包含所有必要的隐式导入
- 包含前端静态文件
- 包含后端应用代码
- 排除不必要的大型库
