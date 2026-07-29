# Docker / PostgreSQL Deployment

This deployment runs the FastAPI/static frontend app, a separate task worker, a one-shot Alembic migrator, PostgreSQL, and a scheduled PostgreSQL backup service.

## Local / compatibility Compose quick start

This path keeps `.env.docker` compatibility for local builds. For an Internet-facing
VPS, complete the file-secret and least-privilege production procedure below instead.

1. Copy the example environment file:

   ```bash
   cp .env.docker.example .env.docker
   chmod 600 .env.docker
   install -d -m 700 package/uploads backups
   ```

2. Fill required secrets in `.env.docker`:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Put the first value into `SECRET_KEY`, the second into `ENCRYPTION_KEY`, and set strong values for `ADMIN_PASSWORD` and `POSTGRES_PASSWORD`. Keep `APP_BIND_IP=127.0.0.1` when a 1Panel/Nginx/Caddy reverse proxy is used.

   If your server can pull Docker Hub directly, set `DOCKER_IMAGE_PREFIX=`. The default uses a Docker Hub mirror prefix for networks where Docker Hub is slow or unavailable.

3. Start the stack:

   ```bash
   docker compose --env-file .env.docker up --build -d
   ```

   The `migrate` service acquires a PostgreSQL advisory lock and must finish successfully before `app` or `worker` starts. An unversioned legacy database is compared with the current metadata and is never blindly stamped.

   Existing deployments should also merge the worker/outbox defaults from `.env.docker.example`: a 30-second heartbeat, 120-second stale/lease timeouts, three maximum attempts, one-second event polling fallback, and a ten-minute Docker stop grace period.

4. Verify:

   ```bash
   curl -fsS http://127.0.0.1:9800/live
   curl -fsS http://127.0.0.1:9800/ready
   docker compose --env-file .env.docker run --rm migrate alembic current
   docker compose --env-file .env.docker run --rm migrate alembic check
   ```

   On a 3-core/4-GB VPS, start with these queue limits. The admin panel can hot-switch
   the first two settings within their supported choices without restarting services:

   ```env
   MAX_CONCURRENT_USERS=5       # admin choices: 5 / 8 / 10
   API_KEY_CONCURRENCY=2        # admin choices: 1 / 2 / 4
   MAX_PENDING_SESSIONS_PER_USER=3
   TASK_WORKER_MAX_CONCURRENCY=10
   ```

   One user can have one processing/browser-agent-waiting task plus two queued tasks.
   Reducing global concurrency drains existing work instead of killing it. A task in
   `waiting_browser_agent` releases its worker slot and resumes through PostgreSQL after
   the extension completes, fails, or expires.

5. Open:

   ```text
   http://127.0.0.1:9800
   ```

## Production file Secrets and PostgreSQL roles

The production overlay requires Docker Compose 2.24.4 or newer because it uses
`!reset` / `!override` to remove the compatibility `env_file` and its bind mount.
It loads immutable values from service-specific `0600` files under `/run/secrets`.
`.env.docker` remains host-only Compose interpolation; `.env.runtime` contains only
mutable runtime settings and is mounted read/write into app and read-only into worker.

Before changing an existing VPS, verify a PostgreSQL dump and preserve the current
`POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_PASSWORD`, and `ENCRYPTION_KEY` values in
`.env.docker`. The initializer reuses non-placeholder values so JWTs and encrypted
provider configuration remain readable; changing them is a separate rotation event.

```bash
cp .env.docker.example .env.docker   # skip when the real file already exists
chmod 600 .env.docker
install -d -m 700 package/uploads backups
sudo ./scripts/docker-secrets-init.sh
find secrets -maxdepth 1 -type f -printf '%m %u:%g %f\n'
```

Expected ownership is the configured `GANKAIGC_RUNTIME_UID:GID` for application
Secrets and `70:70` for `secrets/postgres_password` because the pinned
`postgres:16-alpine` image drops to that numeric identity. Every file must be `0600`;
the app and one-shot tools fail closed on group/world-readable files.

| Service | Mounted secret names |
|---|---|
| `postgres` | bootstrap `postgres_password` only |
| `provision-roles` | bootstrap URL plus migrator/app/backup role passwords |
| `migrate` | migrator database URL only |
| `app` | app database URL, JWT/admin/encryption keys, platform provider keys |
| `worker` | app database URL, JWT/admin/encryption keys, platform provider keys |
| `backup` | backup-role password only |
| `backup-offsite` | independent restic password only |

The role contract is:

- `ai_polish` (bootstrap): initialization and explicit role reconciliation only;
- `gankaigc_owner` (`NOLOGIN`): owns the `public` schema and migration objects;
- `gankaigc_migrator`: can assume owner for Alembic DDL;
- `gankaigc_app`: table CRUD and sequence use, but no persistent DDL;
- `gankaigc_backup`: table/sequence read only for `pg_dump`.

The worker mounts the admin password even though it does not serve admin login.
Its polling loop reloads and validates the complete server secret set; omitting
that file causes reload failures and leaves stale settings active.

Start only PostgreSQL, then provision roles. Existing objects are not silently
re-owned; the first command fails with an object sample until the operator opts in:

```bash
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml up -d postgres

./scripts/postgres-provision-roles.sh
# Existing database only, after reviewing the object list and verified backup:
# set POSTGRES_REASSIGN_EXISTING_OBJECTS=true in .env.docker
./scripts/postgres-provision-roles.sh
# immediately restore POSTGRES_REASSIGN_EXISTING_OBJECTS=false
```

Run Alembic with the migrator URL, then rerun provisioning once to reconcile exact
grants on every current object. Neither command prints passwords.

```bash
docker compose --env-file .env.docker \
  -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
./scripts/postgres-provision-roles.sh
```

`DATABASE_URL_FILE`, `SECRET_KEY_FILE`, `ADMIN_PASSWORD_FILE`,
`ENCRYPTION_KEY_FILE`, the platform `*_API_KEY_FILE` values, and
`MINERU_API_TOKEN_FILE` are supported by the settings loader. Mounted files are
authoritative and cannot be overwritten from the admin UI; update the source file,
keep mode `0600`, and recreate only the affected app/worker containers. MinerU and
object-storage credentials are optional: mount their files only when those providers
are enabled. The restic script also accepts `RESTIC_PASSWORD_FILE`,
`AWS_ACCESS_KEY_ID_FILE`, and `AWS_SECRET_ACCESS_KEY_FILE`.

## Reverse Proxy

For Nginx, proxy your domain to `127.0.0.1:9800`:

```nginx
location / {
    proxy_pass http://127.0.0.1:9800;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    client_max_body_size 25m;
}
```

If the 1Panel OpenResty instance runs in a separate bridge container and cannot reach host loopback, attach the proxy and app to a controlled shared Docker network and proxy by service name. Do not publish 9800 publicly as a workaround.

Then update `.env.docker`:

```env
ALLOWED_ORIGINS=https://your-domain.com
TRUSTED_PROXY_IPS=127.0.0.1,::1
```

`TRUSTED_PROXY_IPS` must contain only the real peer IP/CIDR used by 1Panel/OpenResty to reach the app. If the proxy is a bridge container, replace the loopback example with that controlled network's smallest practical CIDR. Never use `0.0.0.0/0`; forwarding headers from untrusted peers are ignored.

Restart:

```bash
   docker compose --env-file .env.docker up -d
```

## Notes

- `.env.docker` is intentionally ignored by git and must not be committed.
- PostgreSQL data is persisted in the `postgres_data` Docker volume.
- Production app and worker processes only verify the Alembic revision; they do not run startup DDL.
- App, worker and migrator drop all Linux capabilities, set `no-new-privileges`, and enforce PID limits. Production API docs and the database-manager endpoint are disabled by default.
- SSE progress uses the PostgreSQL `task_events` outbox with event-ID replay. `LISTEN/NOTIFY` is only a wake-up hint; polling preserves correctness after missed notifications or app restarts.
- Queue position/count comes from PostgreSQL. Idle worker health comes from `worker_leases`, not from the presence of a currently processing task.
- Uploaded avatars are persisted on the host under `package/uploads/`. Before the first upgrade from an older deployment, copy `/app/package/uploads/` out of the old app container into that directory.
- Port 9800 binds to loopback by default so public clients cannot bypass the reverse proxy.
- Platform mode uses the configured platform API keys and consumes user credits.
- BYOK mode uses each user's saved API config and does not consume platform credits.

Local dumps are written as `.partial`, validated with `pg_restore --list`, atomically renamed, and accompanied by SHA-256. They still share the VPS failure domain. Configure `RESTIC_REPOSITORY` and provider credentials for a separate encrypted restic repository; the production overlay reads the independent password from `secrets/restic_password`. The offsite job snapshots both validated PostgreSQL dumps and `/uploads`. Validate an isolated uploads restore with per-file SHA-256 comparison once, then enable the optional profile:

```bash
docker compose --env-file .env.docker --profile offsite \
  run --rm \
  -e RUN_ONCE=true \
  -e VERIFY_UPLOADS_RESTORE=true \
  backup-offsite
docker compose --env-file .env.docker --profile offsite up -d backup-offsite
```

Run a weekly PostgreSQL restore into an isolated database and rerun the uploads restore
verification. A successful upload alone is not restore proof.

## v2.1.0 short-maintenance upgrade

Revision `0011_fair_concurrency_guard` and the multi-slot worker must be deployed together.
Do not let a v2.0.x worker and a v2.1.0 worker claim jobs at the same time. On a single VPS,
wait for active jobs to finish, then use a short maintenance window:

Before starting, change a legacy `MAX_CONCURRENT_USERS=7` in `.env.docker` to
`MAX_CONCURRENT_USERS=5`. v2.1.0 workers fail safely to 5 for unsupported legacy
values, but the file should still be made explicit.

```bash
COMPOSE="docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.prod.yml"

# Keep PostgreSQL running, but stop both old schedulers/API entry points.
$COMPOSE stop app worker

# Create a validated local dump and an independently restorable offsite snapshot.
$COMPOSE run --rm -e RUN_ONCE=true backup
$COMPOSE --profile offsite run --rm \
  -e RUN_ONCE=true -e VERIFY_UPLOADS_RESTORE=true backup-offsite

git fetch --tags origin main
git pull --ff-only origin main

# Set GANKAIGC_IMAGE to the verified v2.1.0 digest before pull.
$COMPOSE pull
$COMPOSE run --rm migrate
./scripts/postgres-provision-roles.sh
$COMPOSE up -d --wait
curl -fsS http://127.0.0.1:9800/ready
```

Start at global concurrency 5. Verify normal polish, enhancement, emotional polish,
BYOK, browser-agent return, stop/cancel, and queue fairness before increasing to 8 or 10.

## Signed immutable release deployment

Release CI publishes a multi-architecture GHCR image with SBOM/provenance, blocks HIGH/CRITICAL Trivy findings, and signs the exact digest with GitHub OIDC. Pin that digest instead of rebuilding a mutable branch on the VPS:

```env
GANKAIGC_IMAGE=ghcr.io/mumu-0922/gankaigc@sha256:<verified-digest>
```

```bash
IMAGE_REF="$(sed -n 's/^GANKAIGC_IMAGE=//p' .env.docker | tail -1)"
cosign verify \
  --certificate-identity-regexp '^https://github.com/mumu-0922/GankAIGC/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "$IMAGE_REF"
docker compose version  # must be >= 2.24.4
sudo ./scripts/docker-secrets-init.sh  # first deployment only; never overwrite existing files
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

Retain two or three previously verified digests. Roll back by restoring the previous `GANKAIGC_IMAGE` value and rerunning the same pull/up commands.
