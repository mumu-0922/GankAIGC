# Docker / VPS Production Target Design

## 1. Current Architecture

```text
Internet ── host:9800 ── app (FastAPI + React, one Uvicorn process)
                            │
worker (one serial loop) ───┼── PostgreSQL (data + task queue)
                            │
backup ─────────────────────┘── host ./backups
```

Current strengths worth retaining:

- PostgreSQL is not published to the host.
- Task claim uses `FOR UPDATE SKIP LOCKED` and processing tasks have a heartbeat/stale recovery mechanism.
- app has no Docker socket and the admin update endpoint cannot execute a host update command.
- frontend uses `npm ci`, route-level lazy loading and production chunking.

The production blockers are boundary problems rather than a need to rewrite the whole system.

## 2. Target Single-VPS Architecture

```text
Internet
   │ 80/443 only
   ▼
1Panel Nginx/OpenResty ── TLS, body limit, SSE, rate limit, admin access policy
   │ loopback/private edge network
   ▼
app ─────────────── PostgreSQL ───── migrate (one-shot, owner role)
 │                       ▲  │
 │ SSE reads outbox      │  └──── worker leases / task queue / durable events
 └───────────────────────┘
                         ▲
worker ── external AI/MinerU/Zhuque browser-agent APIs

Persistent state:
  postgres_data | uploads | optional zhuque_state | validated backups
                                             └── encrypted offsite copy

Release source:
  protected tag -> CI tests/scans -> signed OCI digest + SBOM/provenance
                                      └── VPS deploys digest, never rebuilds main
```

## 3. Network and Service Boundaries

- The existing 1Panel reverse proxy remains the public edge. Only 80/443 are public, and app binds `127.0.0.1:9800`; this prevents direct access from bypassing 1Panel.
- PostgreSQL has no host port and resides on a private data network.
- app and worker may initiate required outbound HTTPS, but only app accepts inbound application traffic.
- `/admin` and `/api/admin` receive a second boundary: VPN/identity-aware proxy or an explicit IP allowlist.
- Trust `X-Forwarded-*` only from the known proxy peer. Direct traffic cannot supply trusted client IPs.

## 4. Durable State Contracts

### Uploads and Zhuque state

- `GANKAIGC_UPLOAD_ROOT=/app/state/uploads` maps to a dedicated persistent volume and is included in backup/restore.
- `ZHUQUE_USER_DATA_DIR=/app/state/zhuque` is mounted only when server-side Zhuque state is enabled. For the recommended VPS `browser_agent` mode, avoid persisting server browser credentials unnecessarily.
- Existing container state is copied to the new volume before mounting it; mounting an empty volume over a live path is forbidden.

### Task events and queue truth

- PostgreSQL remains the queue source of truth.
- A `task_events` outbox stores ordered, durable events. Worker transactions write event rows; `pg_notify` carries only an event ID as a wake-up hint.
- app fetches the row and emits SSE with event IDs. `Last-Event-ID` permits reconnect and replay.
- Queue position/count/age comes from PostgreSQL, not `ConcurrencyManager` in the app process.
- Frontend polls progress every 3–6 seconds only while a task is active, providing a fallback if SSE is unavailable.

### Worker leases

- A `workers` lease records `instance_id`, `boot_id`, version, state, capacity and `last_seen_at` even when idle.
- Worker handles SIGTERM by stopping new claims and draining/checkpointing the active task.
- A dead lease is detected in roughly 90–120 seconds; stale work is retried with bounded attempts and idempotent billing/stage semantics.

PostgreSQL outbox is preferred over adding Redis for the initial single-VPS deployment. Redis Streams becomes justified only after measured event/queue load or multi-VPS scaling.

## 5. Schema Lifecycle

- Schema mutations run once in a dedicated `migrate` service under a migrator/owner DB role and PostgreSQL advisory lock.
- app and worker use a DML-only role and only verify that the database revision is compatible.
- Existing databases created by `create_all` require a schema diff against Alembic head:
  - stamp only when exact equivalence is proven;
  - otherwise run a reconciliation migration before stamping.
- Future migrations follow expand/contract so the previous application digest remains usable during the rollback window.

## 6. Secrets and Identity

- Immutable Secrets are mounted as service-specific files under `/run/secrets`; they are not delivered wholesale through one shared `env_file`.
- Secret files/directories use `0600/0700` and dedicated ownership.
- DB roles are split into migrator, app/worker DML and backup read-only roles. The application must not use the PostgreSQL bootstrap superuser.
- Mutable provider configuration remains encrypted in PostgreSQL. Transient request BYOK Keys are referenced ephemerally or encrypted and erased at every terminal task state.
- Full Token/Cookie/API Key values never enter stdout, Docker logs, access logs, backups manifests or audit responses.
- Admin audit IP is recorded by the backend from a trusted proxy chain; missing values remain unknown and are never fabricated.

## 7. Image and Release Contract

Every production deployment resolves this immutable identity:

```text
release tag -> Git commit -> OCI digest -> schema revision -> SBOM/provenance/signature
```

- Dockerfile uses allowlist COPY and a non-root runtime stage.
- Runtime dependencies are locked with hashes and separated from test, PyInstaller and optional browser dependencies.
- CI builds once, scans, signs and publishes the image; VPS pulls and verifies the digest.
- Existing Release assets are immutable. Manual release cannot attach a different commit to an existing tag or overwrite an existing asset.
- The previous 2–3 verified digests and their compatible schema revisions are retained for rollback.

## 8. Health, Backup and Observability

- `/live` proves process/event-loop life only.
- `/ready` checks PostgreSQL, expected schema revision and required persistent mounts.
- Worker health comes from lease freshness; backup health comes from the most recent validated offsite-capable backup.
- Backup writes `.partial`, validates with `pg_restore --list`, writes SHA-256, fsyncs, then atomically renames. It is encrypted before an offsite upload.
- Restore targets a new/temporary database, validates it, then switches traffic; it never begins by cleaning the live database.
- Docker logs rotate. Required alerts cover 5xx, readiness, queue age/depth, worker lease, task failure/duration, PostgreSQL connectivity/locks, disk, container restarts and backup age.

## 9. Rollout and Rollback Shape

Recommended rollout order:

```text
inventory + verified backup
-> persistent state migration
-> schema reconciliation + one-shot migrator
-> durable events + polling fallback + worker lease
-> edge/secrets/container hardening
-> immutable signed image release
-> readiness/smoke/fault tests
```

Deployment order:

```text
verify backup -> drain worker -> verify signed digest -> migrate
-> start app -> readiness + smoke -> start worker -> observe queue/SLO
```

Rollback normally switches the app/worker to the previous digest. Database restore is reserved for an incompatible/destructive migration and must use the pre-release snapshot. New event and persistence paths roll out by dual-write/copy-first, with the old path retained until verification completes.

## 10. Security Validation Decisions

- PostgreSQL `LISTEN` uses `psycopg.sql.Identifier` even though the channel is an internal constant; no user-controlled SQL identifier reaches the sink.
- The security pattern scan's remaining `random.randint` findings are pre-existing browser-motion/timing jitter in `zhuque_api.py`, not cryptographic randomness, token generation or an authorization control. They are accepted as non-security use under the scanner's documented downgrade rule.
- Trusted client IP resolution ignores forwarding headers unless the direct peer is inside the explicit `TRUSTED_PROXY_IPS` allowlist and walks the chain from the trusted edge inward, preventing a client-supplied leftmost value from becoming audit truth.
- Request-scoped BYOK values are cleared on completed, failed, stopped and bounded-retry terminal paths. Zhuque Token/Cookie values are no longer emitted to stdout; explicit exports write `0600` files.

## 11. Production Role and File-Secret Boundary

- The production overlay requires Docker Compose 2.24.4+ and uses `!reset` /
  `!override` to remove the compatibility `env_file` and `.env.docker` mount.
  `.env.docker` remains host-only interpolation; `.env.runtime` is the mutable
  non-secret app/worker configuration surface.
- Core and platform provider values are mounted as service-specific `0600`
  files. File values are passed directly to Pydantic `Settings` and are not
  copied into `os.environ`, preventing spawned browser/tool processes from
  inheriting database, JWT, admin, encryption or provider credentials.
- File-backed values are authoritative and the admin API rejects attempts to
  overwrite them. Rotation updates the host file and recreates affected
  services; it does not silently write a competing `.env.runtime` value.
- PostgreSQL uses bootstrap, `NOLOGIN` owner, migrator, app/worker DML and
  backup read-only roles. Provisioning is explicit, advisory-locked,
  idempotent, rejects elevated/conflicting existing roles, and rolls back when
  existing objects require ownership changes without
  `POSTGRES_REASSIGN_EXISTING_OBJECTS=true`.
- Alembic assumes the owner role using `psycopg.sql.Identifier`, not URL/query
  interpolation. Default privileges cover owner and migrator; provisioning is
  rerun after migrations to reconcile exact current-object grants.
- `postgres:16-alpine` reads its bootstrap Secret after dropping to uid/gid
  `70:70`; the setup script and deployment guide make this numeric ownership an
  explicit pinned-image contract rather than weakening the file to `0644`.
- Security scanning after these changes reports zero Critical/High findings.
  The nine accepted Medium findings remain non-security browser motion/timing
  jitter in `zhuque_api.py`, as documented in Section 10.

## 12. v2.0.4 Feedback Compatibility Decisions

### What changed

- Browser-agent extension `0.1.8` treats a visible Zhuque login entry as
  optional when the anonymous editor and Detect control are present. Heartbeat
  status carries `button_enabled` without converting guest readiness into a
  logged-in/token state.
- Browser-agent extension `0.1.9` also accepts Zhuque result cards that omit the
  zero-valued suspicious class and render only human + AI percentages. The
  binary layout maps the missing suspicious ratio to zero instead of leaving
  the claimed job waiting after the page has visibly completed.
- One `job_id` owns one pre-click result baseline and one Detect submission.
  CAPTCHA/manual recovery resumes the existing wait, and unchanged pre-click
  snapshots are accepted only after a full busy-to-idle cycle. Background
  cleanup removes terminal per-job state.
- Admin and per-user BYOK model pickers use a shared editable combobox with an
  explicit dropdown affordance and discovered-count header. `/v1/models`
  discovery fills only empty fields and never acts as an allowlist for
  custom/local model names.

### Why

- Zhuque exposes legitimate logged-out guest quota, so login visibility is not
  proof that detection is blocked.
- A manual-verification retry and a stale result-page snapshot are separate
  browser states; treating either as a new job caused duplicate clicks or
  attached the previous result to the current text.
- OpenAI-compatible local gateways may omit aliases or custom deployments from
  `/v1/models`; replacing or rejecting the current value made a multi-model
  gateway appear to support only one automatic model.

### Impact and accepted quality boundary

- The cross-layer status contract now distinguishes `logged_in` from anonymous
  `button_enabled` readiness. Existing logged-in and offline behavior remains
  compatible.
- Normal detect-reduce semantics remain one initial detection plus one recheck
  after each real rewrite; this fix removes duplicate submission of the same
  browser-agent job rather than disabling convergence rounds.
- `content-zhuque.js` remains a 542-code-line page adapter and exceeds the
  quality checker's 500-line heuristic. This is accepted for this hotfix
  because it owns one finite DOM/network state machine and splitting Chrome
  content-script execution order without a browser fixture would raise release
  risk. Pure decision logic was extracted to the separately tested
  `zhuque-job.js`; a later fixture-backed refactor may split DOM parsing from
  job orchestration.

## 13. Cloud Queue and BYOK Hotfix Decisions

### What changed

- Browser-agent extension `0.1.10` replaces invalid sub-30-second MV3 alarm
  periods with Chrome-supported 30-second alarms and performs an immediate
  heartbeat/job claim after install, reload, service-worker initialization,
  and browser startup.
- Zhuque detection queue entries now carry the owning optimization session
  context into the persistent browser-agent job. Stopping a session cancels
  its non-terminal plugin jobs; the waiting transport observes the durable
  stop state and exits promptly; queue error handling preserves `stopped`.
- Zhuque batch and legacy rewrite billing now charge platform beer only when
  `billing_mode="platform"`. BYOK preflight estimates are zero and BYOK
  rewrite paths create no platform credit transactions.

### Why

- Chrome 120+ enforces a 30-second minimum repeating MV3 alarm interval. The
  former `0.25`/`0.1` minute values could leave a paired extension able to
  heartbeat on demand but unable to poll jobs.
- The Docker worker is intentionally serial. A stopped browser-agent task that
  continued waiting for the full transport timeout monopolized that worker and
  made polish, enhance, and emotional-polish sessions remain queued.
- BYOK routes use the user's provider credentials; charging platform beer in
  Zhuque-specific batch/legacy helpers violated the billing-mode boundary even
  though ordinary BYOK stages already skipped platform billing.

### Impact and rollback

- Job claiming may now wait up to 30 seconds between idle polls, but install
  and startup run an immediate claim and Chrome no longer rejects the alarm.
- Cancellation is scoped by the internal optimization-session primary key and
  touches only non-terminal jobs; completed results remain immutable.
- Platform billing behavior is unchanged. Rollback may revert the application
  and extension together, but must not reuse or move an existing release tag.

## 14. v2.1.0 Fair Concurrency and Delivery Decisions

### Capacity and fairness

- The single-VPS target supports roughly 100 registered users with a peak of
  ten concurrently active users. PostgreSQL remains the durable queue; Redis
  is not introduced without measured multi-host or queue-pressure evidence.
- The administrator selects total capacity from `5`, `8`, or `10`. Workers
  observe changes without restart: raising the limit admits new work; lowering
  it lets existing work drain and blocks new claims until the active count is
  below the selected limit.
- A user may own one active session (`processing` or durable external wait) and
  two additional queued sessions. Claiming is oldest-eligible-user first and
  does not prioritize platform billing over BYOK.
- Browser-agent waits are durable suspension points. Creating a plugin job
  moves the session to `waiting_browser_agent` and releases its worker slot.
  Plugin terminal state requeues the session; the resumed transport consumes
  the matching job by session, segment, and payload hash. Waiting still blocks
  another active session for the same user.
- Completed browser jobs remain reusable resume checkpoints. A terminal
  failed/expired/cancelled job fails the current attempt once; an explicit
  later retry is identified by `session.queued_at > job.completed_at` and may
  create a new job instead of being permanently poisoned by the old failure.
- The same per-user active invariant applies to inline source/one-click
  BackgroundTasks. A later same-user task stays queued until the first is
  terminal; row locking must not combine `FOR UPDATE` with a nullable
  `joinedload()` outer join.
- Legacy `.env.docker` values such as `MAX_CONCURRENT_USERS=7` map safely to
  capacity 5 until the administrator explicitly saves 5, 8, or 10.

### Provider pressure boundary

- One in-process provider limiter groups requests by an HMAC fingerprint of
  the API Key; raw Keys never enter logs or persistence. The administrator may
  select `1`, `2`, or `4` concurrent requests per Key, defaulting to `2`.
- Different BYOK Keys receive independent gates. A rate-limit response applies
  bounded exponential cooldown outside the request slot and retries the same
  request without creating another billing transaction. Completed segment and
  stage records remain the resume checkpoints.
- Local document parsing remains bounded separately from network request
  concurrency; the first release changes optimization worker slots, not the
  experimental Word Formatter job manager.

### Release and backup contract

- v2.1.0 Release assets include a tag-bound browser-extension ZIP whose root is
  `manifest.json`, plus its SHA-256 checksum. Extension syntax and Node tests
  gate upload, and the backend/frontend surface the minimum compatible version.
- Offsite restic snapshots include validated PostgreSQL dump/checksum files and
  the read-only uploads tree under distinct tags. A restore proof writes only
  to an isolated directory/database and compares a known upload SHA-256.
- Production rollout uses a short maintenance window: drain active work,
  verify a backup, migrate, replace app/worker, then open at capacity 5 before
  advancing to 8 and 10 using observed CPU, memory, 429, and failure rates.
