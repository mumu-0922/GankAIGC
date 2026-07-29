# Docker / VPS Production Optimization Implementation Plan

The user reviewed the plan and authorized implementation on 2026-07-10. The task is `in_progress`; execute phases in order and keep production-side operations outside this repository change.

## Progress — 2026-07-10

- [x] Task activated under developer `mumu`.
- [x] Docker build context rejects env files, local state, venvs, browser caches and generated artifacts.
- [x] Runtime image uses explicit source COPY entries instead of copying all of `package/`.
- [x] app published port defaults to loopback for the 1Panel reverse-proxy deployment.
- [x] uploads use a durable host bind at `package/uploads/`, with migration instructions for existing containers.
- [x] Local ignored env/Zhuque credential files were tightened to `0600` and local state directories to `0700`; VPS instructions now create the same baseline.
- [x] Static Docker/Compose regression tests and resolved Compose validation pass.
- [x] Full Docker build completed successfully; runtime allowlist checks passed and the resulting image is 246.32 MiB (`gankaigc:phase1`).
- [!] Frontend build reported 12 `npm audit` findings (1 low, 5 moderate, 6 high). Advisory and compatibility review is required before dependency changes; do not run `npm audit fix --force` blindly.
- [x] Upload bind persistence was verified across two fresh app containers with the same SHA-256.
- [x] Phase 2 now has a one-shot Alembic migrator, PostgreSQL advisory locking, exact legacy-schema comparison/reconciliation and production revision-only startup.
- [x] Empty install, unversioned current schema, missing 0007 columns, repeated migration, forced failure, downgrade/re-upgrade and Compose migrator checks passed.
- [x] Full backend regression suite passed at the Phase 4 checkpoint: 543 tests; subsequent least-secret/log-redaction changes passed their targeted suites.
- [x] Phase 3 adds a PostgreSQL task-event outbox, event-ID replay, `LISTEN/NOTIFY` wakeups with polling fallback, database-backed queue status and reconnecting frontend SSE.
- [x] Independent idle worker leases, boot IDs, SIGTERM drain, 120-second stale recovery, three-attempt stop semantics and terminal request-BYOK scrubbing are implemented.
- [x] Cross-manager PostgreSQL notification/replay tests and an actual Docker worker `idle -> stopped` lease integration check passed.
- [x] Trusted-proxy client IP capture replaces fabricated audit IPs; Zhuque tooling no longer prints Token/Cookie values.
- [x] App/worker/migrator drop Linux capabilities, set `no-new-privileges` and PID limits; production docs/database-manager defaults are closed.
- [x] Local PostgreSQL backups are partial-first, archive-validated, atomically published and checksummed; optional restic offsite encryption is service-scoped.
- [x] Immutable GHCR release workflow, SBOM/provenance, Trivy gate, keyless Cosign signing, digest-only Compose overlay and non-clobbering release assets are implemented but not yet executed in remote CI.
- [x] `/live` and `/ready` split process liveness from PostgreSQL/schema/upload readiness.
- [x] Final Docker smoke proved non-root UID, read-only rootfs, writable tmpfs, dropped capabilities, PID limit, production docs 404 and readiness at revision `0010`.
- [x] Local backup drills proved atomic dump/checksum validation, encrypted restic backup/file restore and PostgreSQL restore into an isolated database.
- [x] Uvicorn access logging redacts query credentials; migrator/backup/offsite services no longer receive the whole application env file.
- [x] Production Compose removes the app/worker compatibility `env_file`, mounts
  service-specific `0600` Secrets, keeps file values out of child-process
  environment, and blocks admin writes to file-backed settings.
- [x] PostgreSQL bootstrap/owner/migrator/app/backup roles are provisioned by an
  explicit fail-closed job with default-privilege reconciliation and opt-in
  legacy object ownership transition.
- [x] Isolated role tests proved app DML succeeds/DDL fails, backup SELECT and
  `pg_dump` succeed/INSERT fails, and the migrator upgrades a fresh database to
  `0010` with app-readable new tables.
- [x] Full backend regression now passes 557 tests; production overlay smoke
  proved file-secret auth, exact service mounts, non-root app/worker, readiness,
  migration, and backup dump/checksum.
- [x] `v2.0.1` remained immutable after its OCI run failed before build because
  the Trivy action ref omitted the required `v` prefix. The action is now
  pinned to the verified `v0.36.0` commit. The immutable `v2.0.2` run then
  correctly blocked three HIGH Python findings before signing; fixed
  `python-multipart`, `setuptools` and vendored `wheel` versions are pinned in
  both manifests for the `v2.0.3` candidate. Publication rejects
  tag/`package/VERSION` mismatch.
- [x] The local `v2.0.3` candidate passes 558 backend tests, the frontend
  production build, dependency consistency checks, Docker build, and a Trivy
  `HIGH,CRITICAL --ignore-unfixed` image scan with zero findings.
- [x] VPS validation exposed a browser-agent quota refresh regression: after a
  detection, the Zhuque result view could hide the quota from the first 8,000
  characters of DOM text, so the plugin reported login success with
  `remaining_uses=-1` until the tab was reopened. The `v2.0.4` candidate reads
  quota from terminal payloads, targeted DOM text and Vue runtime state, keeps
  the latest observed numeric value across result-page rerenders, and no longer
  reports a numeric sync success when the plugin returned no count. Extension
  regression tests pass, the frontend production bundle is synchronized, all
  558 backend tests pass, and a no-cache/pulled Docker rebuild passes the Trivy
  `HIGH,CRITICAL --ignore-unfixed` gate with zero findings.
- [x] After two visually rejected generic passes, the public homepage now uses
  the `frontend-design` editorial review-desk direction: a real manuscript,
  interactive detect/rewrite modes, one compact glass review panel, ruled
  content sections, subject-specific typography, and restrained Apple blue/white
  system styling. Responsive and accessibility fallbacks remain mandatory.

## v2.0.4 Feedback Follow-up — 2026-07-27

- [x] Triage confirmed the browser-agent extension treats a visible Zhuque
  login entry as a hard blocker even when the anonymous detect input/button is
  usable, so logged-out/free detection regressed behind mandatory login copy.
- [x] Triage confirmed one browser-agent job can click Detect again after a
  CAPTCHA/manual-required loop, and stale result-page snapshots are accepted
  without proving they belong to the current click. Both paths can spend or
  appear to spend multiple Zhuque detections for one job.
- [x] Triage confirmed the admin model picker renders only the current model
  before `/v1/models` succeeds, and probed lists replace manual entry with a
  closed select. This makes local/custom model gateways look limited to one
  model.
- [x] Allow usable anonymous Zhuque pages, preserve login/CAPTCHA guidance only
  when detection is actually blocked, and keep status copy honest.
- [x] Make one browser-agent job submit at most one Detect click across manual
  verification, and reject stale pre-click snapshot/DOM results.
- [x] Keep model fields editable while offering probed models as suggestions;
  never overwrite a non-empty custom model merely because `/v1/models` omits it.
- [x] Add extension, backend/static frontend regressions; rebuild/sync frontend
  production assets; run targeted and full quality gates.
- [x] Local manual validation exposed an unversioned legacy database where
  `create_all()` left `optimization_sessions.worker_attempt_count` absent.
  Local startup now runs the compatibility pass and the exact Alembic
  reconcile/stamp gate before serving traffic; the repaired local DB verifies
  at `0010_task_events_worker_leases`, and a rollback-only start-route probe
  creates a queued session successfully.
- [x] Workspace task-start errors no longer concatenate a missing FastAPI
  `detail` into `undefined`; validation lists, timeouts, detail-less HTTP
  failures, and network failures have explicit fallbacks. The frontend bundle
  was rebuilt/synced and 75 static frontend contracts pass.
- [x] Manual BYOK validation confirmed native `<datalist>` can report seven
  discovered models without rendering a visible dropdown affordance in Chrome.
  Admin and BYOK fields now share an editable combobox with an explicit
  chevron, discovered-count header, automatic opening after a successful probe,
  keyboard/ARIA list semantics, and preservation of custom model names.
- [x] Browser-agent manual validation exposed a frontend effect loop: every
  fresh status response changed `browserAgentStatus` object identity, restarted
  initial synchronization, and forced another heartbeat plus three status
  reads. The effect now depends on stable scalar state, performs one initial
  sync, and polls only the aggregate browser-agent status endpoint in plugin
  mode.
- [x] Browser-agent manual validation then exposed a result-parser gap: Zhuque
  completed a binary `0% human / 100% AI` result but omitted the zero suspicious
  category, while extension `0.1.8` required three percentages and never
  completed the backend job. Extension `0.1.9` parses both binary and
  three-class layouts, with pure regression coverage for the boundary case.
  Chrome manual acceptance confirmed the result now returns to GankAIGC and
  releases the task from the detection wait state.
- [x] Windows one-click manual startup exposed a frozen-runtime packaging gap:
  local schema preparation reached Alembic, but `GankAIGC.exe` did not contain
  `alembic.ini` or `migrations/` and aborted after database initialization.
  `app.spec` now bundles the complete Alembic runtime tree, a release regression
  locks both mappings, and the rebuilt executable was inspected through
  `pyi-archive-viewer` to prove `env.py`, `script.py.mako`, and revision `0010`
  exist inside the final ZIP.
- [x] The accepted feedback fixes are prepared as the `v2.0.6` release
  candidate. Backend/frontend fallback versions, workflow defaults, packaging
  docs, and committed production assets are synchronized; the final local
  Windows one-click candidate reports `v2.0.6` from inside the frozen EXE.
- [x] Cloud follow-up traced an online-but-idle plugin to invalid sub-30-second
  Chrome MV3 alarms. Extension `0.1.10` uses 30-second alarms and performs an
  immediate heartbeat/job claim after install, reload, worker initialization,
  and browser startup.
- [x] Session stop now cancels linked persistent browser-agent jobs, the
  waiting transport observes the durable stop state, and task-queue exception
  handling preserves `stopped`, releasing the serial Docker worker for queued
  polish/enhance/emotional-polish work.
- [x] BYOK Zhuque batch and legacy reduce paths no longer charge platform beer;
  BYOK preflight estimates return zero while platform billing remains intact.
- [x] Cloud acceptance confirmed the browser-agent handoff, queue release, and
  BYOK billing fixes in production. The accepted code is prepared as the
  immutable `v2.0.7` release candidate with synchronized backend/frontend
  fallback versions, package metadata, workflow defaults, release notes, and
  committed production assets.

Validation:

- Chrome extension Node regression suites: 2/2 passed; all four changed JS
  files pass `node --check`.
- Backend suite: 568 tests passed against the PostgreSQL test container.
- Frontend: Vite production build passed and `package/frontend/dist` was synced
  into `package/static`; 75 direct static-contract tests passed.
- Security pattern scan: zero Critical/High findings in the extension, frontend,
  and backend services. The nine Medium `random` findings are the pre-existing
  non-cryptographic Zhuque browser-motion/timing jitter already accepted in
  `design.md`.
- Windows one-click release contracts: 8/8 passed; rebuilt ZIP integrity passed,
  and frozen Alembic runtime assets were verified inside the packaged EXE.
- `v2.0.6` release gate: 89 targeted version/release/static contracts passed,
  the Windows one-click build completed, and the frozen version plus Alembic
  assets were inspected before tag publication.
- `git diff --check` passed. The quality scanner's single warning is the
  documented 542-code-line Zhuque page adapter; job decision logic is isolated
  in the tested `zhuque-job.js` helper.
- Cloud hotfix regressions: 75 frontend/static contracts passed; extension
  syntax and both Node suites passed; stop/cancellation and BYOK batch/legacy
  coverage passed inside the full 568-test backend suite. Security scanning
  found zero Critical/High issues; the nine accepted Medium findings remain
  non-cryptographic Zhuque browser-motion/timing jitter.
- `v2.0.7` pre-tag gate: 568 backend tests passed; 106 targeted
  release/Docker/static contracts passed; eight extension Node cases and all
  extension syntax checks passed; the versioned Vite build was synchronized
  into `package/static`; a pulled-base Docker image built successfully and
  reported `VERSION=v2.0.7`; Trivy found zero fixed HIGH/CRITICAL issues.
- `v2.1.0` full backend gate: 581 tests passed against the isolated PostgreSQL
  test database. This includes five-slot overlap, same-user inline
  serialization, revision-0010 duplicate-active migration, durable browser
  suspension/resume/retry, admin tier validation, and per-Key limiter tests.
- Release/Docker/static gate: 169 targeted contracts passed; base and
  production Compose models validated; `sh -n` passed for the restic script;
  the Vite `v2.1.0` build was synchronized into `package/static`.
- Browser extension gate: every JavaScript file passed `node --check`, all
  eight Node cases passed, and a local `v0.1.10` ZIP/checksum proof confirmed
  exactly one root `manifest.json`; the CI-generated sidecar remains the
  authoritative Release checksum.
- Security pattern scans reported zero Critical/High findings in backend app,
  frontend source, and extension. The nine accepted Medium browser jitter
  findings remain unchanged and documented in `design.md`.
- `git diff --check`, Python compile, frontend production build, extension
  packaging, and README/deployment/release-note synchronization passed.

## Phase 0 — Containment and Baseline (S, before public go-live)

- [ ] Inventory any locally/registry-built images that may contain `package/data`; rotate Zhuque sessions/API credentials if exposure is possible.
- [ ] Record current production tag/commit/image ID, actual schema, volume list, queue state and backup age without printing secret values.
- [ ] Create a verified pre-change PostgreSQL dump and export existing uploads/Zhuque state from live containers.
- [ ] Validate the existing 1Panel domain proxy: force HTTPS, proxy to `127.0.0.1:9800`, disable SSE buffering, allow the configured upload size, and use bounded long-request timeouts.
- [ ] Restrict VPS ingress to 22 (allowlisted), 80 and 443; block public 9800/5432/CDP ports. Do not rely on the 1Panel/firewall rule alone when Docker still publishes 9800 to all interfaces.
- [ ] Put admin routes behind VPN/identity-aware proxy or an explicit allowlist.
- [ ] Set secret directories/files to `0700/0600`; configure Docker log rotation and disk alerts.

**Gate:** no public launch while 9800 is directly reachable, state is not backed up, or possible leaked credentials remain valid.

## Phase 1 — Image Context and Persistent Data (S–M)

- [x] Expand `.dockerignore` for root `.env*`, backups, venvs, browser caches, data, uploads and build/test artifacts.
- [x] Replace `COPY package/ ./` with an explicit runtime allowlist.
- [x] Add dedicated uploads persistence; do not add server Zhuque state for the recommended `browser_agent` deployment.
- [ ] Copy existing data into the new volumes before switching paths.
- [x] Add uploads to encrypted backup scope.

**Validation**

```bash
docker compose --env-file .env.docker config --quiet
trivy image --scanners secret,vuln <image-ref>
docker run --rm <image-ref> sh -c 'test ! -e /app/package/venv && test ! -e /app/package/data/zhuque'
```

- Upload an avatar, record its SHA-256, force-recreate app, and verify the same URL/hash.
- Verify app/worker see the same optional state volume where required.

**Rollback:** copy-first migration; retain the old exported state until one restore drill passes.

## Phase 2 — Schema Authority (M, highest correctness risk)

- [ ] Dump production schema and compare it to SQLAlchemy metadata and Alembic head.
- [x] Write and test reconciliation for databases created by `create_all`; never blindly `stamp head`.
- [x] Add a one-shot `migrate` service with advisory locking and migrator credentials.
- [x] Make app/worker depend on successful migration and remove production startup DDL.
- [x] Test empty install, previous snapshot upgrade, repeat run and forced migration failure.

**Validation**

```bash
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic heads
docker compose run --rm migrate alembic check
```

**Rollback:** retain pre-migration dump and previous image digest; use expand/contract. Restore DB only for an incompatible migration.

## Phase 3 — Cross-Process Correctness (L)

- [x] Add durable task event outbox and event IDs.
- [x] Dual-write existing stream events, wake app with `LISTEN/NOTIFY`, replay by `Last-Event-ID`.
- [x] Query queue state from PostgreSQL.
- [x] Add active-task polling fallback and SSE reconnect handling.
- [x] Add independent worker leases, unique boot IDs, drain/SIGTERM handling, bounded retries and DLQ semantics.
- [x] Clear or securely dereference transient BYOK Keys on every terminal path.

**Validation**

- Worker-container events arrive at app SSE.
- Disconnect/restart app for 30 seconds; replay is complete and duplicate-free.
- Kill worker during a task; work recovers inside the lease target without duplicate charge or segment.
- Idle worker stays healthy; stopped worker becomes unhealthy inside the lease timeout.

**Rollback:** feature-flag new SSE delivery; keep database polling as the safe fallback.

## Phase 4 — Edge, Secrets and Container Hardening (M)

- [x] Bind app to loopback by default; document the shared-network option for a bridge-container 1Panel proxy.
- [ ] Configure TLS, SSE no-buffering, upload body limit, trusted proxy handling and query-token log redaction.
- [x] Split Secrets per service; use migrator/app/backup DB roles and a DML-only application connection.
- [x] Run app/worker as non-root with all capabilities dropped, `no-new-privileges`, read-only rootfs, explicit writable mounts/tmpfs and PID/resource limits.
- [x] Remove full credential output from Zhuque tooling/logs and replace fake audit IP fallback with trusted backend capture.
- [x] Disable or separately protect production docs and database-manager endpoints.

**Validation**

- External `VPS_IP:9800` fails while domain 443 succeeds.
- `id -u` in app/worker is non-zero; writes outside explicit state paths fail.
- `docker inspect` shows only service-required secret names; backup cannot see JWT/admin/model secrets.
- Login rate-limit and audit IP tests work through the real proxy and reject spoofed forwarding headers.

**Rollback:** enable hardening per service. Fix explicit ownership/mounts on write failures; do not restore root or world-readable Secrets.

## Phase 5 — Recoverable Release and Backup (M)

- [ ] Build/publish a tag- and commit-bound OCI image with digest, SBOM, provenance and signature.
- [ ] VPS deploys verified digest rather than building mutable `main`.
- [x] Remove release asset clobber and reject version/tag/ref mismatches.
- [ ] Make backup atomic, validated and encrypted; upload to a separate failure domain.
- [ ] Restore weekly to an isolated database and record actual RPO/RTO.
- [x] Add `live/ready`, migration/volume checks and deployment smoke tests.

**Validation**

```bash
cosign verify <image-ref>@sha256:<digest>
docker compose --env-file .env.docker up -d --wait
pg_restore --list <validated.dump>
```

- A deliberately unhealthy image must fail the gate and leave the previous digest available.
- Interrupted dump leaves only `.partial`; it is never shown as a successful backup.

**Rollback:** retain two or three verified digests; run old/new backup chains in parallel for one retention cycle.

## Phase 6 — Performance and Maintainability (P1/P2 after production gates)

### v2.1.0 fair-concurrency delivery

- [x] Add migration/runtime status support for one active session per user and durable `waiting_browser_agent` suspension.
- [x] Enforce one active plus two queued sessions per user and oldest-eligible-user claims under concurrent worker slots.
- [x] Replace the serial Docker worker loop with ten logical slots governed by hot-reloaded `5 / 8 / 10` capacity and per-slot leases.
- [x] Add HMAC-keyed provider request gates with admin-selectable `1 / 2 / 4` concurrency and bounded 429 cooldown/retry.
- [x] Requeue suspended sessions on browser-agent completion/failure/expiry and prove restart-safe resume without duplicate clicks or billing.
- [x] Expose capacity controls/status in the admin UI and update queue labels for external waits.
- [x] Package the tagged browser extension plus SHA-256 as immutable Release assets and cover the workflow contract.
- [x] Add uploads to encrypted offsite restic scope, add an isolated restore/hash proof, and update README/deployment docs.
- [x] Prepare synchronized v2.1.0 version identity, frontend static assets and release notes; run full backend/frontend/extension/release/security gates.

- [ ] Stop committing `User.last_used` on every authenticated request; throttle/batch presence writes.
- [ ] Move blocking synchronous ORM work away from async request paths or adopt a consistent sync/async execution model.
- [ ] Rewrite admin statistics as SQL aggregates/cache; do not load complete paper bodies every 30 seconds.
- [ ] Remove duplicate/PK indexes only after `pg_stat_user_indexes` and query-plan verification.
- [ ] Close/reuse `AsyncOpenAI/httpx` clients and bound stream queues.
- [ ] Split runtime/dev/package dependency locks; remove test/PyInstaller/optional Playwright from production image.
- [ ] Add history pagination and decompose the largest backend/frontend modules after behavior is protected by tests.

## Required Review Gates

1. Security: secret scan, least-privilege service inventory, proxy spoof test.
2. Data: state persistence and isolated restore proof.
3. Correctness: empty/upgrade migration, cross-process SSE, worker-kill recovery.
4. Release: tag/commit/digest/schema identity and rollback rehearsal.
5. Capacity: collect p95 task duration, queue age, RSS/CPU/DB pool data before increasing worker count.

## High-Risk Files for Future Work

- `.dockerignore`, `Dockerfile`, `docker-compose.yml`
- `package/backend/app/database.py`, `package/backend/migrations/`
- `package/backend/worker.py`, `package/backend/app/services/task_queue.py`
- `package/backend/app/services/stream_manager.py`, `concurrency.py`, `optimization_service.py`
- `package/backend/app/routes/optimization.py`, `admin.py`
- `scripts/docker-postgres-backup.sh`, restore scripts
- `.github/workflows/ci.yml`, `.github/workflows/build-exe.yml`
