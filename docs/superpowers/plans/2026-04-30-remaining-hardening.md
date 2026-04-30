# GankAIGC Remaining Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or focused worker agents. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增无用产品功能的前提下，补齐当前项目剩余的稳定性、安全性和可维护性缺口。

**Architecture:** 保留现有 FastAPI + React/Vite + PostgreSQL 架构。优先做本地启动诊断，其次完善封禁体验，再增加管理员审计日志，最后补测试与文档收口。已完成的 PostgreSQL 备份恢复、啤酒流水、数据库管理器安全收紧不重复实现。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, React/Vite, Tailwind CSS, pytest, Playwright, PowerShell。

---

## 当前已完成，不再重复

- PostgreSQL-only、Alembic、启动数据库连接自检。
- PostgreSQL 备份/恢复脚本：`scripts/backup-postgres.ps1`、`scripts/restore-postgres.ps1` 及对应 `.sh`。
- 啤酒流水：`CreditTransaction`、用户端流水、后台最近啤酒流水。
- 后台数据库管理器只读、白名单、脱敏和分页限制。
- Word 排版入口默认关闭并从前端隐藏。
- 长任务队列化与 worker。

---

### Task 1: 本地一键启动与诊断脚本

**目的：** 解决“刚才还能跑、现在连不上数据库/端口占用”的本地使用痛点。

**Files:**
- Create: `scripts/start-dev.ps1`
- Modify: `README.md`
- Modify: `docs/postgresql-operations.md`

- [x] 新增 `scripts/start-dev.ps1`，按顺序检查 Docker CLI、PostgreSQL 容器、5432 端口、`package/.env`、`DATABASE_URL`、9800 端口。
- [x] 默认不删除容器、不删除数据卷；发现已有 `gankaigc-postgres` 时优先 `docker start gankaigc-postgres`。
- [x] 支持 `-SkipDocker`、`-NoRun` 参数：只诊断不启动应用。
- [x] 成功后执行 `cd package; python main.py`。
- [x] README 增加“一键本地启动”命令和常见失败解释。

**Validation:**

```powershell
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -NoRun
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/start-dev.ps1 -SkipDocker -NoRun
```

---

### Task 2: 封禁用户体验完善

**目的：** 管理员封禁后，用户端提示清楚，后台操作避免误点。

**Files:**
- Modify: `package/backend/app/routes/auth.py`
- Modify: `package/backend/app/utils/auth.py`
- Modify: `package/backend/tests/test_auth_api.py`
- Modify: `package/frontend/src/api/index.js`
- Modify: `package/frontend/src/pages/AdminDashboard.jsx`
- Modify: `package/backend/tests/test_frontend_redeem_entry.py`

- [x] 登录接口对“账号存在但被封禁”的用户返回 `403` 和 `账号已被封禁，请联系管理员`。
- [x] Bearer token 用户被封禁后继续调用 API，仍返回当前统一的未授权错误，并让前端清理登录态。
- [x] 后台点击“封禁”前弹出确认，解封不强制确认。
- [x] 前端 401/403 拦截保留管理员页面不跳转；普通用户跳回 `/login`。
- [x] 增加后端测试和前端源码断言测试。

**Validation:**

```powershell
cd package/backend
python -m pytest tests/test_auth_api.py tests/test_frontend_redeem_entry.py -q
```

---

### Task 3: 管理员审计日志

**目的：** 记录后台关键操作，方便排查“是谁创建/封禁/充值/改配置”。

**Files:**
- Modify: `package/backend/app/models/models.py`
- Create: `package/backend/migrations/versions/0003_add_admin_audit_logs.py`
- Modify: `package/backend/app/routes/admin.py`
- Modify: `package/backend/tests/test_auth_api.py` 或 Create: `package/backend/tests/test_admin_audit_logs.py`
- Modify: `package/frontend/src/pages/AdminDashboard.jsx`
- Modify: `package/backend/tests/test_frontend_redeem_entry.py`

- [x] 新增 `AdminAuditLog` 表：`id`、`admin_username`、`action`、`target_type`、`target_id`、`detail`、`created_at`。
- [x] 后台关键操作写日志：创建邀请码、切换邀请码、创建兑换码、给用户充值啤酒、切换无限啤酒、封禁/解封用户、保存系统配置。
- [x] 增加 `GET /api/admin/audit-logs?limit=50`，只允许管理员访问。
- [x] 后台增加“操作日志”轻量列表，不增加复杂筛选。
- [x] 测试日志写入和列表返回。

**Validation:**

```powershell
cd package/backend
python -m pytest tests/test_admin_audit_logs.py -q
```

---

### Task 4: 测试补齐与文档收口

**目的：** 把容易回归的问题固化成测试。

**Files:**
- Modify: `package/backend/tests/test_auth_api.py`
- Modify: `package/backend/tests/test_user_invites_api.py`
- Modify: `package/backend/tests/test_optimization_billing.py`
- Modify: `package/frontend/e2e/admin-flow.spec.js`
- Modify: `docs/maintenance-checklist.md`

- [x] 测试注册开关关闭时不能注册、普通用户不能生成第二个邀请码。
- [x] 测试封禁用户不能登录，已登录 token 被封禁后不能继续访问。
- [x] 测试啤酒不足不能提交平台任务，自带 API 不扣啤酒。
- [x] Playwright 后台导航增加“用户管理/系统配置刷新保持当前 tab”的覆盖。
- [x] 维护清单补充：发布前必须跑后端 pytest、前端 build、Playwright。

**Validation:**

```powershell
cd package/backend
python -m pytest tests -q
cd ../frontend
npm run build
npm run test:e2e -- --workers=1
```
