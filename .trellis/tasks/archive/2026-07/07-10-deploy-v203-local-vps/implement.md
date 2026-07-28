# Deploy v2.0.6 to Local VPS Implementation Plan

## Checklist

- [x] Confirm v2.0.6 commit and tag locally:
      `git rev-parse v2.0.6^{commit}`.
- [x] Confirm the v2.0.6 release workflow, vulnerability scan, and signing
      steps succeeded.
- [x] Resolve and verify the immutable v2.0.6 GHCR digest with Cosign.
- [x] Confirm background queues are empty:
      `optimization_sessions` queued/processing count is 0 and
      `zhuque_agent_jobs` non-terminal count is 0.
- [x] Stop worker with `docker compose --env-file .env.docker stop worker`.
- [x] Create backup directories and back up `.env.docker` to `$HOME`.
- [x] Run custom-format `pg_dump`, validate with `pg_restore --list`, copy dump
      to `backups/`, and write SHA-256.
- [x] Confirm avatar/upload state already uses the persistent host bind; no
      legacy container-only copy is required.
- [x] Preserve the local worker secret-mount fix, fast-forward to `origin/main`,
      reapply the fix, and assert HEAD is
      `460c09781b0ea48fed6525dd9907c2233efd4da8`.
- [x] Update `.env.docker` with production v2.0.6 values without changing
      existing secret values.
- [x] Ensure `package/uploads`, `backups`, and `.env.runtime` ownership/modes.
- [x] Preserve the existing `secrets/`; verify file modes and ownership.
- [x] Verify Cosign signature for the exact GHCR digest and release workflow
      identity.
- [x] Run production Compose config, pull images, and verify PostgreSQL health.
- [x] Provision roles; if prompted by existing objects, temporarily set
      `POSTGRES_REASSIGN_EXISTING_OBJECTS=true`, rerun, then set it back false.
- [x] Run migrator, provision roles again, and start stack with `up -d --wait`.
- [x] Validate `/live`, `/ready`, Compose status, logs, HTTPS domain, and direct
      public `:9800` closure.

## Deployment Evidence

- Release commit: `460c09781b0ea48fed6525dd9907c2233efd4da8`.
- Signed image: `sha256:4a56a1506ed94dc8b49f17498f0288c3427a8ab1ac3faee9aa92fc2314382bf0`.
- Database backup: `backups/gankaigc_ai_polish_20260727_162404.dump` with
  matching `.sha256`; archive listing and checksum both passed.
- Runtime: app reports `2.0.6`; `/live`, `/ready`, HTTPS, non-root execution,
  secret modes, and loopback-only port binding all passed.

## Post-release Main Hotfix Rollout (2026-07-28)

- Fast-forwarded production checkout to commit
  `8f716b6d6b2fed88fbfb5ae2ed9a645a689c1c85` after preserving and restoring
  the local production hardening changes.
- Confirmed zero active optimization sessions and browser-agent jobs before
  stopping the worker.
- Created and verified
  `backups/gankaigc_ai_polish_pre_8f716b6_20260728_091144.dump` plus SHA-256;
  `pg_restore --list` and checksum validation passed inside the backup service.
- Built local image `gankaigc:8f716b6` with OCI revision label matching the
  full commit and deployed it through the existing production Compose overlay
  using a local three-service image override.
- Verified `/live`, `/ready`, HTTPS 200, non-root runtime, clean runtime logs,
  and blocked direct public access to port 9800.

## Validation Commands

```bash
docker compose version
git rev-parse HEAD
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.prod.yml config --quiet
curl -fsS http://127.0.0.1:9800/live
curl -fsS http://127.0.0.1:9800/ready
curl -I https://ga.mumubuku.top
```

## Risky Files And State

- `.env.docker`: must be modified without printing or replacing existing secret
  values.
- `secrets/`: create once, refuse overwrite behavior is expected.
- PostgreSQL `postgres_data` volume: never delete; rely on backup/restore.
- `package/uploads/`: preserve legacy uploaded files.
- Docker Compose project `gankaigc`: service replacement affects production.
