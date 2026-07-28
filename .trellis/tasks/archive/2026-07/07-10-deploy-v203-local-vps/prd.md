# Deploy v2.0.6 to local VPS

## Goal

Deploy GankAIGC v2.0.6 on the current VPS from the signed GHCR release image,
preserving existing PostgreSQL data and production secrets while moving the app
behind the existing 1Panel reverse proxy.

## Requirements

- The deployment target is this server and the existing repository at
  `/home/mumu/GankAIGC`.
- Only deploy v2.0.6 commit `460c09781b0ea48fed6525dd9907c2233efd4da8` and
  production image
  `ghcr.io/mumu-0922/gankaigc@sha256:4a56a1506ed94dc8b49f17498f0288c3427a8ab1ac3faee9aa92fc2314382bf0`.
- Do not deploy a mutable tag or any image whose release workflow or Cosign
  verification failed.
- Existing secrets from `.env.docker` must be preserved; do not print secret
  values.
- Before service changes, confirm no active background work is running, stop the
  worker, and create a verified PostgreSQL custom-format backup with SHA-256.
- Preserve the production Compose hardening introduced in v2.0.3:
  `APP_BIND_IP=127.0.0.1`, non-root runtime UID/GID, service-scoped secrets,
  split PostgreSQL roles, and `POSTGRES_REASSIGN_EXISTING_OBJECTS=false` after
  the one-time reassign step.
- Existing 1Panel reverse proxy points `ga.mumubuku.top` to
  `http://127.0.0.1:9800`; use `ALLOWED_ORIGINS=https://ga.mumubuku.top`.
- Validate Cosign signature for the exact digest and workflow identity before
  pulling/running the image.
- Finish with local health checks, Compose status/log review, HTTPS check, and a
  direct public-IP port check proving port 9800 is not reachable externally.

## Acceptance Criteria

- [x] `git rev-parse HEAD` equals
      `460c09781b0ea48fed6525dd9907c2233efd4da8`.
- [x] A pre-v2.0.6 PostgreSQL dump exists under `backups/` with a matching
      `.sha256`, and `pg_restore --list` passed before deployment.
- [x] `.env.docker` contains the v2.0.6 production keys and preserves existing
      secret values.
- [x] `secrets/` exists with mode `0700`; secret files are mode `0600`;
      `postgres_password` is owned by `70:70`, and other app secrets are owned by
      `1000:1000`.
- [x] Cosign verifies the exact production image digest for tag `v2.0.6`.
- [x] `docker compose --env-file .env.docker -f docker-compose.yml -f
      docker-compose.prod.yml up -d --wait` succeeds.
- [x] `curl -fsS http://127.0.0.1:9800/live` and
      `curl -fsS http://127.0.0.1:9800/ready` succeed.
- [x] `curl -I https://ga.mumubuku.top` succeeds.
- [x] Direct access to public `:9800` fails after `APP_BIND_IP=127.0.0.1`.

## Notes

- Current pre-deployment app runs the signed v2.0.4 digest
  `sha256:996019d789d52eaeb7794c618c3b632805858fb72936f503455b0a75fb9d664c`
  and already publishes only `127.0.0.1:9800`.
- Background queues must be checked again immediately before stopping the
  worker because the earlier v2.0.3 preflight is stale.
