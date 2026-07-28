# Deploy v2.0.6 to Local VPS Design

## Boundaries

This task is primarily an operational deployment. Source code comes from
`origin/main` at v2.0.6. Runtime edits are limited to ignored state such as
`.env.docker`, `.env.runtime`, `secrets/`, `backups/`, and `package/uploads/`;
the only tracked deployment fix mounts the already-required admin secret into
the worker and keeps its contract test/spec documentation synchronized.

## Current State

- Repository is on `main` at v2.0.4 and is ten commits behind v2.0.6.
- Running containers are `app`, `worker`, `postgres`, and `backup`.
- Current app publishes `127.0.0.1:9800`, preventing bypass of 1Panel.
- 1Panel OpenResty config for `ga.mumubuku.top` proxies to
  `http://127.0.0.1:9800`.
- Active background queues were checked and are empty.

## Deployment Shape

Use the v2.0.6 image with the hardened production Compose overlay:

- Base `docker-compose.yml` supplies volumes, health dependencies, migrator,
  backup service, hardening, and loopback port binding.
- `docker-compose.prod.yml` replaces local builds with the signed GHCR digest
  and consumes service-scoped secret files.
- `scripts/docker-secrets-init.sh` migrates existing `.env.docker` secret values
  into `secrets/` without printing them.
- `scripts/postgres-provision-roles.sh` runs the bootstrap profile to create
  owner, migrator, app, and backup roles.

## Data And Secrets

- Before stopping/upgrading app services, stop the worker to avoid claiming new
  work.
- Keep PostgreSQL running for `pg_dump --format=custom`.
- Copy the dump out of the container, verify with `pg_restore --list`, and write
  a SHA-256 sidecar.
- Preserve legacy `.env.docker` secrets by backing up the file to `$HOME` and by
  using `docker-secrets-init.sh` only when `secrets/` does not already exist.
- Copy legacy `/app/package/uploads` from the old app container to
  `package/uploads/` when present, because the hardened Compose stack mounts
  uploads at `/app/state/uploads`.

## Rollout And Rollback

Rollout order:

1. Preflight checks and backup.
2. Preserve the local worker secret-mount fix, then fast-forward repository to
   the exact v2.0.6 tag commit and reapply the fix.
3. Patch ignored runtime env values with the verified v2.0.6 digest.
4. Initialize secrets and runtime env.
5. Verify image signature.
6. Start PostgreSQL, provision roles, run one-time object reassignment if needed,
   run migrator, provision roles again, then start the full stack.
7. Validate health, logs, reverse proxy, and direct-port closure.

Rollback point:

- If migration or startup fails after backup, keep the dump and previous
  `.env.docker` backup. Roll back by restoring the previous commit/config and
  PostgreSQL dump, then restart Compose. Do not delete current backups.

## Risks

- Existing `.trellis` planning files make `git status --short` non-empty. They
  are local task metadata created for this deployment and should not be reset.
- The one-time `POSTGRES_REASSIGN_EXISTING_OBJECTS=true` step must only run
  after a verified backup and must be returned to `false`.
- Direct public-IP validation depends on discovering the VPS public IP locally.
