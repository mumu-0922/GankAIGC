# Database Guidelines

> Executable PostgreSQL production contracts for GankAIGC.

---

## Scenario: Docker/VPS schema authority and least-privilege roles

### 1. Scope / Trigger

- Trigger: any change to `docker-compose*.yml`, `app/database.py`,
  `app/schema.py`, `migrations/`, database Secrets, backup credentials, or
  application/worker database permissions.
- PostgreSQL is the only supported database. SQLAlchemy owns runtime data
  access; Alembic is the only production DDL authority.

### 2. Signatures

- Schema commands: `python schema_migrate.py upgrade` and
  `python schema_migrate.py verify`.
- Role command: `python provision_db_roles.py`; host wrapper:
  `scripts/postgres-provision-roles.sh`.
- Required production file inputs:
  - runtime: `DATABASE_URL_FILE`;
  - provisioner: `POSTGRES_MIGRATOR_PASSWORD_FILE`,
    `POSTGRES_APP_PASSWORD_FILE`, `POSTGRES_BACKUP_PASSWORD_FILE`.
- Role names: `POSTGRES_OWNER_ROLE` (`NOLOGIN`),
  `POSTGRES_MIGRATOR_ROLE`, `POSTGRES_APP_ROLE`, and
  `POSTGRES_BACKUP_ROLE`.
- `DATABASE_SESSION_ROLE` is set only on the migrator and must name the
  provisioned owner role.

### 3. Contracts

- Production order is `postgres -> explicit role provision -> migrate -> role
  reconciliation -> app/worker/backup`.
- `app` and `worker` call `prepare_database()` and verify the single Alembic
  head; they never run production `create_all` or handwritten DDL.
- Role privileges:
  - bootstrap superuser: role provisioning only;
  - owner: owns `public` objects and cannot log in;
  - migrator: member of owner and the only login allowed to run Alembic DDL;
  - app/worker: `SELECT/INSERT/UPDATE/DELETE` on tables and
    `USAGE/SELECT/UPDATE` on sequences; no persistent DDL;
  - backup: `SELECT` on tables/sequences only and must run `pg_dump`.
- Default privileges are reconciled for owner and migrator so new migration
  objects immediately inherit app and backup grants.
- Existing public objects are never re-owned unless
  `POSTGRES_REASSIGN_EXISTING_OBJECTS=true` is explicitly set after a verified
  backup and object review.
- File Secrets must be regular UTF-8 files, at most 64 KiB, with no group/world
  permission (`0600` is the deployment standard). File values override env and
  `.env`, are passed directly into `Settings`, and are not exported to
  `os.environ` where child browser/tool processes could inherit them.
- File-backed keys are immutable from the admin UI. Rotation means updating the
  host file and recreating only affected services.

### 4. Validation & Error Matrix

- Multiple Alembic heads -> `SchemaStateError`; runtime must not start.
- Revision differs from head -> `SchemaStateError`; run the one-shot migrator.
- Unknown physical drift -> reject stamp/start; inspect a schema dump.
- Existing public objects with reassignment disabled -> rollback provisioning
  and report an object sample without changing ownership.
- Existing named role has elevated attributes, wrong login mode, or unexpected
  memberships -> fail closed; never silently downgrade/reuse it.
- Secret file is missing, empty, non-regular, oversized, undecodable, or
  group/world-readable -> fail before `Settings()` or role provisioning.
- App attempts `CREATE TABLE public.*` -> PostgreSQL
  `InsufficientPrivilege`.
- Backup attempts `INSERT/UPDATE/DELETE` -> PostgreSQL
  `InsufficientPrivilege`.

### 5. Good/Base/Bad Cases

- Good: signed production Compose mounts only service-required files,
  provisioner creates roles, migrator assumes owner, and app/backup access a
  newest-migration table with their exact grants.
- Base compatibility: local/base Compose may derive one owner URL from
  `.env.docker`; this is not the Internet-facing production contract.
- Bad: app uses the bootstrap superuser; app/worker run `create_all`; backup
  receives the application env file; a legacy database is blindly stamped;
  file Secrets are copied into process environment or command arguments.

### 6. Tests Required

- `test_postgres_roles.py`: fail-closed owner transition, app DML/DDL boundary,
  backup read-only boundary, fresh migrator upgrade, and access to
  migration-created tables.
- `test_secret_files.py`: permission/import-order gates, file precedence,
  child-process environment isolation, and admin-update rejection.
- `test_docker_compose.py`: production removes shared `env_file`; each service
  has only its required secret names and database role.
- Runtime smoke: `/ready`, non-root app/worker, actual `0600` mounts, role
  provisioning, migration, backup dump/checksum, and backup-role `pg_dump`.

### 7. Wrong vs Correct

#### Wrong

```yaml
app:
  env_file: .env.docker
  environment:
    DATABASE_URL: postgresql://superuser:${POSTGRES_PASSWORD}@postgres/app
```

#### Correct

```yaml
app:
  env_file: !reset []
  environment:
    DATABASE_URL_FILE: /run/secrets/database_url
  secrets:
    - source: app_database_url
      target: database_url
```

---

## Scenario: Local source startup adopts legacy schemas before serving traffic

### 1. Scope / Trigger

- Trigger: changes to `app/schema.py`, `app/database.py`, Alembic revisions,
  `app.spec`, `python main.py` local/Windows one-click startup, or workspace
  task-start error handling.
- This protects source/one-click users who reuse an unversioned database from
  an older release. `create_all()` alone does not add columns to existing
  tables and must not be treated as a completed upgrade.

### 2. Signatures

- Local startup: `prepare_database()` -> `init_db()` compatibility pass ->
  revision check -> `upgrade_database_schema()` when not at head -> exact
  metadata comparison -> Alembic head.
- Manual recovery/verification: `python schema_migrate.py upgrade` and
  `python schema_migrate.py verify` from `package/backend`.
- Frozen one-file paths: `schema.py` resolves `alembic.ini` and `migrations/`
  from the PyInstaller `_MEIPASS` root. `app.spec` therefore maps
  `backend/alembic.ini -> .` and `backend/migrations -> migrations`.
- Task-start UI: `WorkspacePage.jsx` must decode FastAPI string/list details
  and provide explicit timeout, HTTP-status, and network fallbacks.

### 3. Contracts

- Local interactive startup may apply only the known additive legacy repairs
  declared in `LEGACY_ADDITIVE_COLUMNS`, then stamp an exact physical schema.
- Production startup remains verify-only and must never call `init_db()` or
  perform compatibility DDL.
- Adopting an unversioned/outdated local schema requires an exact SQLAlchemy
  metadata comparison before stamping head. An already-current local schema
  takes the idempotent revision-only fast path after the compatibility pass.
- A Windows one-file build must contain `alembic.ini`, `migrations/env.py`,
  `migrations/script.py.mako`, and every revision under
  `migrations/versions/`; bundling only `backend/app` is incomplete because
  Alembic loads its script directory as runtime data.
- Frontend errors must never concatenate an absent `detail` into user-visible
  `undefined`; a detail-less HTTP 500 reports its status and directs the user
  to backend logs without exposing SQL or credentials.

### 4. Validation & Error Matrix

- Unversioned legacy DB with a known missing additive column -> add/backfill,
  metadata diff becomes empty, then stamp head.
- Unknown type/constraint/destructive drift -> `SchemaStateError`; do not
  stamp or start.
- Production DB is unversioned/outdated -> reject startup and require the
  one-shot migrator.
- Frozen executable lacks `migrations/` -> Alembic raises `CommandError: Path
  doesn't exist` after database initialization; reject the artifact and fix
  `app.spec` instead of bypassing revision verification.
- FastAPI validation list -> join its `msg` entries for the task-start toast.
- Axios timeout -> show an explicit backend/database timeout message.
- Detail-less HTTP error -> show `HTTP <status>`; no response -> show the
  Axios/network fallback.

### 5. Good/Base/Bad Cases

- Good: an older local `optimization_sessions` table lacks
  `worker_attempt_count`; startup adds it, backfills zero, stamps head, and a
  rollback-only start-route probe can insert a queued session.
- Base: a current local DB is already exact; startup verifies idempotently.
- Good one-click: `pyi-archive-viewer` lists the Alembic config, environment,
  template, and head revision inside the packaged `GankAIGC.exe`.
- Bad: local startup prints success after `create_all()` while an existing
  table still lacks a model column, causing task creation to fail with SQL 500
  and the browser to display `undefined`; or a frozen build omits migration
  runtime data and dies immediately after that compatibility pass.

### 6. Tests Required

- `test_alembic_migrations.py`: drop `worker_attempt_count` from an
  unversioned current-schema fixture, run local `prepare_database()`, then
  assert head revision and zero physical differences.
- `test_frontend_redeem_entry.py`: assert task-start has validation, timeout,
  HTTP-status, and network fallbacks and that the old `undefined` concatenation
  is absent.
- `test_release_workflow.py`: assert `app.spec` retains both Alembic data
  mappings. After a real Windows build, inspect the executable and assert the
  head revision file is present before publishing the ZIP.
- Manual smoke: execute the start route inside a rolled-back transaction and
  assert it returns a queued `SessionResponse` without running the worker.

### 7. Wrong vs Correct

#### Wrong

```python
def prepare_database():
    init_db()  # create_all does not alter an existing table
```

```python
# app.spec: bundling backend/app alone omits Alembic's runtime script directory.
datas=[('backend/app', 'app')]
```

```jsx
toast.error('Start failed: ' + error.response?.data?.detail);
```

#### Correct

```python
init_db()
revision = expected if current == (expected,) else upgrade_database_schema()
```

```python
datas=[
    ('backend/app', 'app'),
    ('backend/alembic.ini', '.'),
    ('backend/migrations', 'migrations'),
]
```

```jsx
const detail = error.response?.data?.detail;
toast.error(detail || `Service returned HTTP ${error.response?.status}`);
```
