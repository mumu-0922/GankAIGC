# 维护发布清单

发布、打包或部署前按顺序检查：

## 代码与测试

- 发布前必须跑后端全量测试：`cd package/backend; python -m pytest tests -q`。
- 前端必须通过生产构建：`cd package/frontend; npm run build`。
- Playwright 必须单 worker 跑主流程：`cd package/frontend; npm run test:e2e -- --workers=1`。
- 涉及管理后台创建邀请码、创建兑换码、充值啤酒、封禁/解封、配置变更等关键操作时，确认审计/操作日志可用且能查询到对应记录。
- 涉及数据库结构时，新增 Alembic migration，并确认 `python -m alembic upgrade head` 可执行。
- 涉及前端生产包时，同步 `package/frontend/dist` 到 `package/static`，并用 `git add -f package/static` 加入新的 hash 文件。

## 配置与安全

- `.env`、`.env.docker`、数据库 dump、日志和真实 API Key 没有进入 Git。
- `.env.docker.example` 只包含占位值，不包含真实 `POSTGRES_PASSWORD`、`SECRET_KEY`、`ADMIN_PASSWORD`、`ENCRYPTION_KEY`。
- 生产环境已替换默认 `SECRET_KEY` 和 `ADMIN_PASSWORD`。
- `DATABASE_URL` 指向 PostgreSQL，测试库使用 `GANKAIGC_TEST_DATABASE_URL` 或默认派生的 `gankaigc_test`。
- 后台数据库管理器保持默认只读，生产写入需显式打开 `ADMIN_DATABASE_WRITE_ENABLED=true`。

## 产品事实

- 当前主线只包含账号注册、用户登录、邀请码注册、兑换码充值啤酒、啤酒流水和降 AI 工作台。
- 卡密和旧访问链接不再作为主流程维护。
- Word 排版是关闭的实验模块；前端入口不应重新出现，后端关闭时不应进入 OpenAPI 文档。
- Docker Compose 应包含 `app`、`worker` 和 `postgres`，生产默认 `INLINE_TASK_WORKER_ENABLED=false`，并保留 worker 心跳和卡死恢复配置。

## 数据与部署

- 发布前完成 PostgreSQL 备份：`scripts/backup-postgres.ps1` 或 `scripts/backup-postgres.sh`。
- 恢复演练使用 `scripts/restore-postgres.ps1` 或 `scripts/restore-postgres.sh`，确认 dump 文件可用。
- README、`package/README.md`、`docs/postgresql-operations.md` 与当前配置项同步。
- GitHub Issues、README Star History 和项目地址仍指向 `mumu-0922/GankAIGC`。
