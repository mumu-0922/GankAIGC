# PostgreSQL 运维指南

GankAIGC 现在只支持 PostgreSQL。迁移、重装或换机器前，先备份数据库和 `.env` / `.env.docker` 配置文件；不要把这些文件提交到 Git。

## Docker 启动 PostgreSQL

复制并编辑 Docker 环境文件：

```powershell
Copy-Item .env.docker.example .env.docker
```

至少修改 `POSTGRES_PASSWORD`、`SECRET_KEY`、`ADMIN_PASSWORD` 和 `ENCRYPTION_KEY`，然后启动：

```powershell
docker compose --env-file .env.docker up -d postgres
docker compose --env-file .env.docker up --build -d
```

Docker Compose 会创建 `ai_polish` 数据库、`ai_polish` 用户和 `postgres_data` 数据卷。

## 新机器创建数据库和用户

如果不用 Docker，在 PostgreSQL 管理账号下执行：

```sql
CREATE USER ai_polish WITH PASSWORD '替换为强密码';
CREATE DATABASE ai_polish OWNER ai_polish;
GRANT ALL PRIVILEGES ON DATABASE ai_polish TO ai_polish;
```

`package/.env` 写法：

```properties
DATABASE_URL=postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish
```

如果密码包含 `@`、`:`、`/`、`#` 等特殊字符，需要先做 URL 编码。

## 备份

脚本会调用 `pg_dump --format=custom`，生成 `gankaigc_ai_polish_YYYYMMDD_HHMMSS.dump`。先设置环境变量：

```powershell
$env:DATABASE_URL="postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish"
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/backup-postgres.ps1
```

Linux/macOS：

```bash
export DATABASE_URL='postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish'
bash scripts/backup-postgres.sh
```

备份文件默认进入 `backups/`，该目录被 `.gitignore` 忽略。

## 恢复

恢复会执行 `pg_restore --clean --if-exists --no-owner`，会覆盖目标库内同名对象。恢复前先停止应用，确认 `DATABASE_URL` 指向正确数据库。

```powershell
$env:DATABASE_URL="postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish"
PowerShell -NoProfile -ExecutionPolicy Bypass -File scripts/restore-postgres.ps1 backups\gankaigc_ai_polish_20260428_120000.dump
```

Linux/macOS：

```bash
export DATABASE_URL='postgresql://ai_polish:数据库密码@127.0.0.1:5432/ai_polish'
bash scripts/restore-postgres.sh backups/gankaigc_ai_polish_20260428_120000.dump
```

恢复后运行迁移并启动应用：

```powershell
cd package/backend
python -m alembic upgrade head
cd ..
python main.py
```

## 常见错误

- `password authentication failed`：`DATABASE_URL` 密码与 PostgreSQL 用户密码不一致；Docker 部署时还要检查 `.env.docker` 的 `POSTGRES_PASSWORD`。
- `connection refused`：PostgreSQL 未启动，或主机、端口写错；Docker 可先运行 `docker compose ps`。
- `database does not exist`：目标库未创建，先执行建库 SQL 或启动 Docker 的 `postgres` 服务。
- `pg_dump` / `pg_restore` 找不到：安装 PostgreSQL 客户端工具，并确认其 `bin` 目录在 `PATH` 中。
