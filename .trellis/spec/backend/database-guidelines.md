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
- The worker must mount `SECRET_KEY_FILE` and `ADMIN_PASSWORD_FILE` even though
  it does not serve admin login. Its polling loop calls `reload_settings()`,
  which validates server deployment secrets globally; omitting the admin secret
  causes noisy reload failures while keeping stale settings.

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

---

## Scenario: Single-VPS fair concurrency and durable browser-agent suspension

### 1. Scope / Trigger

- Trigger: changes to optimization-session statuses, queue claims, Docker
  worker slots, provider request concurrency, browser-agent completion, task
  submission limits, offsite uploads backup, or extension Release packaging.
- This is the v2.1.0 single-VPS contract for roughly 100 registered users and
  a measured peak of about 10 processing users. PostgreSQL remains the queue;
  Redis is not required until multiple VPS workers or measured database load
  justify a distributed primitive.

### 2. Signatures

- Runtime settings:
  - `MAX_CONCURRENT_USERS`: one of `5`, `8`, `10`; unsupported legacy values
    fail safely to 5 in the Docker worker;
  - `TASK_WORKER_MAX_CONCURRENCY=10`: supervisor slot ceiling;
  - `MAX_PENDING_SESSIONS_PER_USER=3`: one active/external wait plus two queued;
  - `API_KEY_CONCURRENCY`: one of `1`, `2`, `4` (default 2).
- Session statuses: `queued -> processing -> waiting_browser_agent -> queued`
  for an external Zhuque round, followed by a terminal status.
- Database invariant:
  `uq_optimization_sessions_one_active_per_user` is a partial unique index on
  `user_id` where status is `processing` or `waiting_browser_agent`.
- Admin config endpoint: `POST /api/admin/config`; unsupported concurrency
  tiers return HTTP 400.
- Browser-agent completion/failure endpoints resume the linked session; in
  inline mode they also enqueue `process_session_by_id(session.id)`.
- Offsite proof command:
  `docker compose --profile offsite run --rm -e RUN_ONCE=true
  -e VERIFY_UPLOADS_RESTORE=true backup-offsite`.
- Release assets:
  `GankAIGC-Browser-Extension-v0.1.10.zip` and its `.zip.sha256` sidecar; the
  ZIP root contains `manifest.json`.

### 3. Contracts

- One worker process owns at most ten logical slots. Each enabled slot has an
  independent lease and database session. Hot downshift stops new claims but
  never cancels an already running slot.
- Queue claims use `FOR UPDATE SKIP LOCKED`, a transaction-scoped per-user
  advisory lock, and a second active-session check. Oldest eligible queued
  work wins regardless of platform/BYOK mode.
- Concurrent submissions use a separate per-user advisory-lock namespace and
  recount unfinished rows inside the transaction. The fourth unfinished task
  is rejected with HTTP 409.
- `waiting_browser_agent` occupies the user's active allowance but not a
  worker slot. Job creation persists that status and raises `TaskSuspended`;
  the queue handler must not fail/refund/clear BYOK credentials on suspension.
- A resumed detector identifies jobs by `session_id + segment_id + SHA-256
  payload_hash`. Completed jobs are reusable. A failed/expired/cancelled job
  from the current queue attempt becomes the task's real error; after an
  explicit retry (`session.queued_at > job.completed_at`) the transport creates
  a new job instead of poisoning every future retry.
- Source/one-click inline tasks still honor the same one-active-per-user index.
  A second background task waits while queued and claims only after the first
  becomes terminal. Do not apply `FOR UPDATE` to a `joinedload()` outer join;
  lock only the `optimization_sessions` row and lazy-load the user as needed.
- Provider concurrency stores only
  `HMAC-SHA256(SECRET_KEY, raw_api_key)` identities in process memory. A 429
  releases the key slot before bounded backoff. Streaming requests are never
  replayed after any content has been emitted.
- The single-process provider gate is valid for the documented one-worker
  Compose topology. A multi-process/multi-VPS worker fleet requires a
  distributed limiter before claiming the same guarantee.
- Restic takes separately tagged snapshots for validated PostgreSQL dumps and
  `/uploads`, applies retention per tag, restores uploads into an isolated
  directory, and compares sorted per-file SHA-256 manifests. Run the proof in
  a maintenance/read-only window so concurrent uploads cannot create a false
  mismatch.
- v2.1.0 migration and worker changes deploy in one short maintenance window;
  v2.0.x and v2.1.0 workers must never claim concurrently.

### 4. Validation & Error Matrix

- Fourth unfinished task for one user -> HTTP 409; no session row or charge is
  created by that request.
- Two slots race for the same user -> advisory lock plus partial unique index
  permits one active row; the other remains queued.
- Browser job pending/running/manual -> `TaskSuspended`; session remains
  `waiting_browser_agent`, credit remains held, worker slot is released.
- Browser job completed -> normalize and consume the exact stored result even
  after worker restart or immediate browser disconnect.
- Browser job failed/expired/cancelled in the current attempt -> fail/refund
  through the normal queue error path; explicit later retry creates a new job.
- Same API Key exceeds configured capacity -> wait; a different BYOK Key may
  enter immediately.
- Provider 429 -> at most three attempts with at most eight seconds per delay;
  no slot is held while sleeping.
- Legacy `MAX_CONCURRENT_USERS=7` -> worker capacity 5 until an administrator
  saves 5, 8, or 10.
- Duplicate active rows before migration -> keep the oldest active row,
  requeue later rows, then create the partial unique index.
- Restored uploads manifest differs -> backup proof exits non-zero and the
  snapshot is not treated as a proven restore.

### 5. Good/Base/Bad Cases

- Good: five users run, a sixth queues, and a Zhuque-waiting session releases
  its slot while blocking only that same user's next queued task.
- Base: 100 accounts may be online while only 5/8/10 tasks call providers;
  account count is not processing concurrency.
- Good retry: an expired Zhuque job fails the resumed task once; the user's
  later retry creates one new browser job for the same payload.
- Bad: keep a worker coroutine polling the browser for 900 seconds, use the raw
  API Key as a limiter-map key, spawn multiple serial worker containers, or run
  old/new worker generations together.
- Bad inline: set a second same-user session to `processing` immediately and
  let the partial index raise `IntegrityError`; the one-shot background task is
  then lost and the session remains stuck.

### 6. Tests Required

- `test_task_queue.py`: five different users overlap, the same user's inline
  tasks serialize, active browser waits block only that user, suspension keeps
  held credit, hot capacity accepts 5/8/10 and safely maps legacy values to 5.
- `test_alembic_migrations.py`: upgrading from revision 0010 requeues duplicate
  active rows and installs the partial unique index with zero schema drift.
- `test_browser_agent.py`: create/suspend, completion requeue, exact-result
  resume, direct no-session compatibility, stop/cancel, and explicit retry
  after a terminal failed job.
- `test_ai_request_limiter.py`: same-key cap, different-key independence,
  HMAC-only state, and slot release before 429 backoff.
- `test_admin_audit_logs.py`: reject unsupported task/API-key tiers without
  mutating the runtime env.
- `test_docker_compose.py` and `test_release_workflow.py`: environment wiring,
  `/uploads` read-only mount, restore/hash proof, extension tests, ZIP root,
  checksum asset, and immutable Release upload behavior.
- Final gate: versioned Vite build synced to `package/static`, extension syntax
  and Node tests, full backend pytest, both Compose models, security scan, and
  `git diff --check`.

### 7. Wrong vs Correct

#### Wrong

```python
# Occupies one global worker for the entire browser wait and stores a secret.
limiter[raw_api_key] += 1
result = await poll_browser_job(timeout=900)
```

```python
# Can violate the partial unique index in inline mode.
session.status = "processing"
db.commit()
```

#### Correct

```python
identity = hmac.new(secret_key, raw_api_key, hashlib.sha256).hexdigest()
job = create_durable_browser_job(session_id=session.id, payload_hash=payload_hash)
raise TaskSuspended("waiting for browser agent", reason="browser_agent")
```

```python
lock_user_claim(db, session.user_id)
if another_active_session(db, session.user_id):
    keep_queued_and_retry_later()
else:
    session.status = "processing"
    db.commit()
```
