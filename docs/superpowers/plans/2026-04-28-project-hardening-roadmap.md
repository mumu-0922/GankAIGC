# GankAIGC Project Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按顺序完成 GankAIGC 后续稳定性、安全性、测试、部署与架构优化，让项目更适合长期维护和公开部署。

**Architecture:** 先补启动自检和数据库迁移基础，再补测试与后台安全边界，随后清理已关闭功能、完善部署运维，最后推进长任务队列化。每个任务单独测试、单独提交、单独推送，避免一次性大改造成回滚困难。

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, React/Vite, Tailwind CSS, pytest, Playwright, Docker Compose, Alembic。

---

## 执行原则

- 每个任务完成后单独提交，例如 `fix: add startup configuration checks`。
- 后端改动优先补 pytest；前端改动至少跑 `npm run build`，涉及用户流程时补 Playwright。
- 不重新引入 SQLite、卡密、未完成的 Word 排版入口。
- 不提交 `.env`、`.env.docker`、数据库导出、日志和真实 API Key。
- 涉及生产部署默认值时，默认保守：宁可关闭危险功能，也不要默认开放。

---

### Task 1: 启动配置自检

**目的：** 启动时对 PostgreSQL、密钥、环境变量给出明确错误，避免用户只看到数据库连接栈信息。

**Files:**
- Modify: `package/backend/app/config.py`
- Modify: `package/backend/app/database.py`
- Modify: `package/main.py`
- Modify: `package/backend/app/main.py`
- Test: `package/backend/tests/test_startup_config.py`
- Docs: `README.md`

- [x] **Step 1: 增加配置校验测试**

新增 `package/backend/tests/test_startup_config.py`，覆盖：

```python
import pytest

from app.database import normalize_database_url


def test_normalize_database_url_rejects_missing_value():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        normalize_database_url("")


def test_normalize_database_url_rejects_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_database_url("sqlite:///ai_polish.db")


def test_normalize_database_url_accepts_postgresql():
    assert normalize_database_url(
        "postgresql://ai_polish:secret@127.0.0.1:5432/ai_polish"
    ).startswith("postgresql+psycopg://")
```

- [x] **Step 2: 增加可读启动错误**

在 `package/backend/app/database.py` 中新增 `check_database_connection()`，使用 `SELECT 1` 验证连接。捕获连接失败时抛出 `RuntimeError`，提示：

- 当前仅支持 PostgreSQL。
- 检查 `package/.env` 的 `DATABASE_URL`。
- Docker 用户先运行 `docker compose up -d postgres`。
- 密码需与 `.env.docker` 的 `POSTGRES_PASSWORD` 一致。

- [x] **Step 3: 启动时先自检再建表**

在 `package/main.py` 和 `package/backend/app/main.py` 的 startup 流程中，`init_db()` 前调用数据库连接自检。生产环境仍保留默认密钥强校验。

- [x] **Step 4: 运行测试**

```powershell
cd package/backend
python -m pytest tests/test_startup_config.py -q
python -m pytest tests -q
```

Expected: 全部通过。

- [x] **Step 5: 更新 README 并提交**

README 的配置说明补一段“启动失败排查”。提交：

```powershell
git add package/backend/app/config.py package/backend/app/database.py package/main.py package/backend/app/main.py package/backend/tests/test_startup_config.py README.md
git commit -m "fix: add startup configuration checks"
git push
```

---

### Task 2: 接入 Alembic 正式迁移

**目的：** 替代长期依赖 `create_all + 手写 ALTER TABLE` 的方式，让 PostgreSQL 表结构变更可追踪、可回滚、可部署。

**Files:**
- Modify: `package/backend/requirements.txt`
- Create: `package/backend/alembic.ini`
- Create: `package/backend/migrations/env.py`
- Create: `package/backend/migrations/script.py.mako`
- Create: `package/backend/migrations/versions/0001_initial_postgresql_schema.py`
- Modify: `package/backend/app/database.py`
- Test: `package/backend/tests/test_alembic_migrations.py`
- Docs: `README.md`

- [x] **Step 1: 添加 Alembic 依赖**

在 `requirements.txt` 加 `alembic`，安装依赖后验证：

```powershell
cd package/backend
pip install -r requirements.txt
python -m alembic --version
```

- [x] **Step 2: 建立迁移目录**

配置 `migrations/env.py` 从 `app.config.settings.DATABASE_URL` 读取 PostgreSQL 连接，并导入 `app.models.models` 的 `Base.metadata`。

- [x] **Step 3: 生成初始迁移**

将当前核心表写入 `0001_initial_postgresql_schema.py`，覆盖用户、邀请码、兑换码、会话、分段、改写记录、系统配置、用户 API 配置、论文项目等当前表。

- [x] **Step 4: 调整启动策略**

短期保留 `create_all` 作为兼容保护，但新增 README 说明：生产部署以 `alembic upgrade head` 为准。后续确认无旧库后，再删除手写迁移函数。

- [x] **Step 5: 测试迁移**

```powershell
cd package/backend
python -m pytest tests/test_alembic_migrations.py -q
python -m alembic upgrade head
```

Expected: 测试库可从空库升级到最新结构。

- [x] **Step 6: 提交**

```powershell
git add package/backend/requirements.txt package/backend/alembic.ini package/backend/migrations package/backend/app/database.py package/backend/tests/test_alembic_migrations.py README.md
git commit -m "feat: add alembic migrations"
git push
```

---

### Task 3: 前端自动化主流程测试

**目的：** 用浏览器自动化覆盖真实用户路径，避免 UI 改动后登录、兑换、工作台、后台入口静默坏掉。

**Files:**
- Modify: `package/frontend/package.json`
- Create: `package/frontend/playwright.config.js`
- Create: `package/frontend/e2e/main-flow.spec.js`
- Create: `package/frontend/e2e/admin-flow.spec.js`
- Docs: `README.md`

- [x] **Step 1: 安装 Playwright**

```powershell
cd package/frontend
npm install -D @playwright/test
npx playwright install chromium
```

Current implementation uses `@playwright/test` with the system Chrome channel by default, so local runs do not require downloading Playwright's bundled Chromium. Set `PLAYWRIGHT_CHANNEL=chromium` if a CI environment installs the bundled browser.

- [x] **Step 2: 增加测试脚本**

在 `package.json` 增加：

```json
"test:e2e": "playwright test",
"test:e2e:headed": "playwright test --headed"
```

- [x] **Step 3: 编写用户主流程**

`main-flow.spec.js` 覆盖：

- 首页能打开。
- 邀请码注册入口存在。
- 用户登录后能进入工作台。
- 兑换码入口展示“啤酒”。
- 论文排版入口不可见。

- [x] **Step 4: 编写后台主流程**

`admin-flow.spec.js` 覆盖：

- `/admin` 登录页可打开。
- 登录后左侧导航存在。
- 数据面板、会话监控、账号啤酒、系统配置可切换。
- 不显示卡密管理和排版任务。

- [x] **Step 5: 运行验证**

```powershell
cd package
python main.py
```

另开终端：

```powershell
cd package/frontend
npm run test:e2e
npm run build
```

- [x] **Step 6: 提交**

```powershell
git add package/frontend/package.json package/frontend/package-lock.json package/frontend/playwright.config.js package/frontend/e2e README.md
git commit -m "test: add frontend main flow e2e coverage"
git push
```

---

### Task 4: 后台数据库管理器安全收紧

**目的：** 保留排障能力，但降低误删、越权查看敏感内容、生产环境误开放的风险。

**Files:**
- Modify: `package/backend/app/routes/admin.py`
- Modify: `package/backend/app/config.py`
- Modify: `package/frontend/src/components/DatabaseManager.jsx`
- Test: `package/backend/tests/test_admin_database_manager.py`
- Docs: `README.md`

- [x] **Step 1: 补安全测试**

覆盖：

- 未登录不能访问数据库管理器。
- 普通用户不能访问。
- `ADMIN_DATABASE_MANAGER_ENABLED=false` 返回 404。
- `ADMIN_DATABASE_WRITE_ENABLED=false` 时写操作返回 403。
- `password_hash`、`api_key`、长文本内容统一脱敏。
- 单次查询页大小超过上限时被截断。

- [x] **Step 2: 统一脱敏函数**

在 `admin.py` 保留一个公共函数：

```python
def sanitize_db_record(record: dict) -> dict:
    ...
```

所有数据库管理器读接口都从这个函数返回，新增敏感字段只改一处。

- [x] **Step 3: 增加查询限制**

限制 `page_size` 最大值，例如 100；默认按 `id desc` 或创建时间倒序。禁止用户从前端指定任意 SQL。

- [x] **Step 4: 前端提示只读状态**

`DatabaseManager.jsx` 显示“只读模式”或“写入已启用”，但不要展示敏感配置值。

- [x] **Step 5: 运行测试并提交**

```powershell
cd package/backend
python -m pytest tests/test_admin_database_manager.py -q
python -m pytest tests -q
```

```powershell
git add package/backend/app/routes/admin.py package/backend/app/config.py package/frontend/src/components/DatabaseManager.jsx package/backend/tests/test_admin_database_manager.py README.md
git commit -m "fix: harden admin database manager"
git push
```

---

### Task 5: 清理 Word 排版残留入口

**目的：** 当前产品主线只做降 AI，彻底避免用户看到或误触未完成的论文排版功能。

**Files:**
- Modify: `package/frontend/src/App.jsx`
- Modify: `package/frontend/src/pages/WelcomePage.jsx`
- Modify: `package/frontend/src/pages/UserDashboard.jsx`
- Delete or archive: `package/frontend/src/pages/WordFormatterPage.jsx`
- Keep gated: `package/backend/app/word_formatter/`
- Test: `package/backend/tests/test_frontend_redeem_entry.py`
- Docs: `README.md`, `AGENTS.md`

- [ ] **Step 1: 确认入口清单**

搜索：

```powershell
rg -n "WordFormatter|word-formatter|论文排版|Word 排版|文档排版" package/frontend/src package/backend/app
```

- [ ] **Step 2: 删除前端路由和菜单入口**

移除 `WordFormatterPage` 的 import、route、按钮、菜单项。后端模块继续由 `WORD_FORMATTER_ENABLED=false` 条件挂载保护，不在本任务中删除后端模块。

- [ ] **Step 3: 保留测试断言**

确保 `test_frontend_redeem_entry.py` 继续断言前台和后台不出现排版入口。

- [ ] **Step 4: 构建前端并同步静态包**

```powershell
cd package/frontend
npm run build
cd ../..
Copy-Item -Path .\package\frontend\dist\* -Destination .\package\static -Recurse -Force
```

- [ ] **Step 5: 测试并提交**

```powershell
cd package/backend
python -m pytest tests/test_frontend_redeem_entry.py -q
```

```powershell
git add package/frontend/src package/backend/tests/test_frontend_redeem_entry.py README.md AGENTS.md
git add -f package/static
git commit -m "fix: remove word formatter frontend remnants"
git push
```

---

### Task 6: 部署文档、备份和恢复脚本

**目的：** 换机器、重装、升级时能明确恢复 PostgreSQL 数据和配置，不靠口头记录。

**Files:**
- Create: `docs/postgresql-operations.md`
- Create: `scripts/backup-postgres.ps1`
- Create: `scripts/restore-postgres.ps1`
- Create: `scripts/backup-postgres.sh`
- Create: `scripts/restore-postgres.sh`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: 编写备份脚本**

PowerShell 脚本使用 `pg_dump`，输出文件名：

```text
gankaigc_ai_polish_YYYYMMDD_HHMMSS.dump
```

脚本读取环境变量 `DATABASE_URL`，不在脚本中写死密码。

- [ ] **Step 2: 编写恢复脚本**

恢复脚本使用 `pg_restore --clean --if-exists`，要求用户显式传入 dump 文件路径。

- [ ] **Step 3: 编写运维文档**

`docs/postgresql-operations.md` 包含：

- Docker 启动 PostgreSQL。
- 新机器创建数据库和用户。
- `.env` 中 `DATABASE_URL` 的写法。
- 备份命令。
- 恢复命令。
- 常见错误：密码错误、端口占用、数据库不存在。

- [ ] **Step 4: 验证脚本语法**

```powershell
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/backup-postgres.ps1 -WhatIf
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/restore-postgres.ps1 -Help
```

- [ ] **Step 5: 提交**

```powershell
git add docs/postgresql-operations.md scripts README.md .gitignore
git commit -m "docs: add postgresql backup and restore guide"
git push
```

---

### Task 7: 长任务队列化

**目的：** 降 AI 是长耗时任务，应从请求线程中剥离，提升并发、失败恢复和任务状态可观测性。

**Files:**
- Modify: `package/backend/app/models/models.py`
- Modify: `package/backend/app/routes/optimization.py`
- Create: `package/backend/app/services/task_queue.py`
- Create: `package/backend/worker.py`
- Modify: `package/backend/app/config.py`
- Modify: `docker-compose.yml`
- Test: `package/backend/tests/test_task_queue.py`
- Frontend: `package/frontend/src/pages/WorkspacePage.jsx`
- Docs: `README.md`

- [ ] **Step 1: 明确任务状态模型**

会话状态至少包含：

- `queued`
- `processing`
- `completed`
- `failed`
- `cancelled`

保留现有会话表，必要时增加 `queued_at`、`started_at`、`finished_at`、`worker_id`。

- [ ] **Step 2: 后端提交任务只入队**

`POST /api/optimization/start` 创建会话后立即返回 `session_id` 和 `queued` 状态，不在请求中直接跑完整降 AI。

- [ ] **Step 3: Worker 消费任务**

`package/backend/worker.py` 读取队列并调用现有优化服务。异常写入会话 `error_message`，并释放或修正啤酒扣费状态。

- [ ] **Step 4: 前端轮询状态**

工作台提交后进入任务状态页或当前结果区域轮询 `/api/optimization/sessions/{id}`，显示排队、处理中、完成、失败。

- [ ] **Step 5: 并发和恢复测试**

pytest 覆盖：

- 新任务进入 queued。
- worker 能处理并变 completed。
- worker 失败后任务变 failed。
- 用户只能查看自己的任务。
- 平台啤酒扣费不会重复扣。

- [ ] **Step 6: Docker 增加 worker 服务**

`docker-compose.yml` 增加 `worker`，与 web 共用镜像和环境变量。

- [ ] **Step 7: 提交**

```powershell
git add package/backend package/frontend/src/pages/WorkspacePage.jsx docker-compose.yml README.md
git commit -m "feat: add optimization task queue"
git push
```

---

### Task 8: AGENTS 与维护文档收口

**目的：** 保证贡献指南、README、部署文档和当前项目事实一致，避免以后继续按旧 SQLite、卡密、排版功能维护。

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `package/README.md`
- Create: `docs/maintenance-checklist.md`

- [ ] **Step 1: 修正 AGENTS 不准确描述**

移除或改写：

- “当前检出目录不包含 Git 历史”
- 任何 SQLite 测试说明
- 任何卡密作为主流程的描述

明确：

- PostgreSQL-only。
- 测试库用 `GANKAIGC_TEST_DATABASE_URL`。
- 前端构建后如需提交静态 bundle，要 `git add -f package/static`。

- [ ] **Step 2: 更新 README 与 package README**

保证二者都说明当前主线：

```text
账号注册 + 用户登录 + 邀请码注册 + 兑换码充值啤酒 + 降 AI 工作台
```

并说明 Word 排版是关闭的实验模块。

- [ ] **Step 3: 新增维护清单**

`docs/maintenance-checklist.md` 包含发布前检查：

- 后端 pytest 全量通过。
- 前端 build 通过。
- Playwright 主流程通过。
- `.env.example` 或 `.env.docker.example` 没有真实密钥。
- PostgreSQL 备份已完成。
- README 与配置项同步。

- [ ] **Step 4: 文档检索校验**

```powershell
rg -n -i "sqlite|card_key|卡密|临时 SQLite|ai_polish.db" AGENTS.md README.md package/README.md docs package/backend package/frontend/src
```

Expected: 只允许出现在兼容测试、历史说明或明确“已移除”的上下文中。

- [ ] **Step 5: 提交**

```powershell
git add AGENTS.md README.md package/README.md docs/maintenance-checklist.md
git commit -m "docs: align maintenance guides with current project"
git push
```

---

## 总体验收

全部任务完成后运行：

```powershell
cd package/backend
python -m pytest tests -q
```

```powershell
cd package/frontend
npm run build
npm run test:e2e
```

```powershell
docker compose --env-file .env.docker config --quiet
```

最终检查：

- 用户可注册、登录、兑换啤酒、提交降 AI、导出 Word/Markdown。
- 管理员可查看数据面板、会话监控、账号啤酒、系统配置。
- 后台数据库管理器默认只读且脱敏。
- Word 排版入口不可见，关闭时 API 文档也不出现相关路由。
- PostgreSQL 连接、迁移、备份、恢复都有明确文档。

---

## 当前推荐执行顺序

1. Task 1：启动配置自检。
2. Task 2：Alembic 正式迁移。
3. Task 3：前端自动化主流程测试。
4. Task 4：后台数据库管理器安全收紧。
5. Task 5：清理 Word 排版残留入口。
6. Task 6：部署文档、备份和恢复脚本。
7. Task 7：长任务队列化。
8. Task 8：AGENTS 与维护文档收口。

这个顺序先解决“跑不起来”和“表结构不可控”，再解决“改 UI 容易坏”和“后台安全”，最后做架构升级，风险最可控。
