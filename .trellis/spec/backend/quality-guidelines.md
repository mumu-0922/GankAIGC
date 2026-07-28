# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

<!--
Document your project's quality standards here.

Questions to answer:
- What patterns are forbidden?
- What linting rules do you enforce?
- What are your testing requirements?
- What code review standards apply?
-->

(To be filled by the team)

---

## Forbidden Patterns

<!-- Patterns that should never be used and why -->

(To be filled by the team)

---

## Required Patterns

<!-- Patterns that must always be used -->

(To be filled by the team)

---

## Testing Requirements

<!-- What level of testing is expected -->

(To be filled by the team)

---

## Code Review Checklist

<!-- What reviewers should check -->

(To be filled by the team)

---

## Scenario: Backend Pytest Must Not Touch Production Compose Databases

### 1. Scope / Trigger

- Trigger: any backend pytest run started from a production Docker Compose
  service, a VPS shell with `.env.docker`, or an environment that contains
  `DATABASE_URL_FILE` / `SECRET_KEY_FILE` / `ADMIN_PASSWORD_FILE`.

### 2. Signatures

- Test database selector: `GANKAIGC_TEST_DATABASE_URL`.
- Production file-backed settings: `DATABASE_URL_FILE`, `SECRET_KEY_FILE`, and
  `ADMIN_PASSWORD_FILE`.
- Autouse fixture: `package/backend/tests/conftest.py::reset_db`.

### 3. Contracts

- `GANKAIGC_TEST_DATABASE_URL` must point to a dedicated PostgreSQL database
  whose database name contains `test`.
- Never run pytest with production `DATABASE_URL_FILE` or production secret-file
  environment inherited from `docker compose run app`.
- Compose-only text tests may be verified by directly invoking their test
  functions without loading pytest `conftest.py` when no isolated PostgreSQL
  test database is available.

### 4. Validation & Error Matrix

- Test database name lacks `test` -> `conftest.py` raises before app import.
- Pytest inherits production app role -> `reset_db` attempts `drop_all()` and
  PostgreSQL rejects DDL with `InsufficientPrivilege`; stop and rerun with an
  isolated test database.
- Pytest inherits production superuser or owner credentials -> abort before
  running tests; that path can delete production tables.

### 5. Good/Base/Bad Cases

- Good: run backend pytest with `GANKAIGC_TEST_DATABASE_URL` set to a disposable
  PostgreSQL test database.
- Base: for pure file-content tests such as `test_docker_compose.py`, manually
  invoke the test functions to avoid `conftest.py` database setup.
- Bad: run `docker compose --env-file .env.docker ... run app python -m pytest`
  without overriding production database and secret-file environment.

### 6. Tests Required

- Keep `conftest.py` refusing non-test database names.
- For production Compose contract changes, verify `docker compose ... config
  --quiet` and the compose text assertions without touching production data.

### 7. Wrong vs Correct

#### Wrong

```bash
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm app python -m pytest package/backend/tests/test_docker_compose.py -q
```

#### Correct

```bash
GANKAIGC_TEST_DATABASE_URL=postgresql://.../gankaigc_test \
  python -m pytest package/backend/tests/test_docker_compose.py -q
```

---

## Scenario: Local Hotfix Images Must Preserve the Production Compose Overlay

### 1. Scope / Trigger

- Trigger: an operator must deploy an unreleased commit to an existing hardened
  VPS before a signed GHCR release image exists.

### 2. Signatures

- Build: `docker build --label org.opencontainers.image.revision=<commit> -t gankaigc:<short-commit> .`.
- Rollout: merge `docker-compose.yml`, `docker-compose.prod.yml`, and a local
  override that changes only `image`, `build`, and `pull_policy` for
  `app`, `worker`, and `migrate`.

### 3. Contracts

- The final Compose model must retain the production overlay's file-backed
  Secrets, split database roles, non-root users, and loopback-only app port.
- The local override uses `pull_policy: never`; each application container's
  image ID and OCI revision label must match the requested commit.
- Stop the worker only after active queue counts are zero, and create a verified
  custom-format PostgreSQL backup before migration or service replacement.

### 4. Validation & Error Matrix

- Dirty checkout blocks fast-forward -> stash all tracked/untracked state,
  fast-forward, then restore and resolve without discarding local hardening.
- Backup checksum or `pg_restore --list` fails -> do not migrate or recreate.
- Merged config loses a Secret, non-root user, or loopback bind -> reject the
  override and keep the previous production image running.
- Container image ID/revision differs from the requested commit -> fail rollout.

### 5. Good/Base/Bad Cases

- Good: a three-service override deploys one labeled local image while the
  signed PostgreSQL image and all production hardening remain unchanged.
- Base: a signed release exists; update `GANKAIGC_IMAGE` to its verified digest
  and use the normal two-file production Compose command.
- Bad: run base Compose alone with `up -d --build` on the Internet-facing VPS;
  this drops service-scoped Secret and split-role contracts.

### 6. Tests Required

- `docker compose ... config --quiet` passes with all three files.
- Assert merged config contains `DATABASE_URL_FILE`, `ADMIN_PASSWORD_FILE`,
  `user: 1000:1000`, and `127.0.0.1:9800`.
- Smoke `/live`, `/ready`, HTTPS, runtime error logs, and blocked public `:9800`.

### 7. Wrong vs Correct

#### Wrong

```bash
docker compose --env-file .env.docker up -d --build
```

#### Correct

```bash
docker build --label org.opencontainers.image.revision=<commit> -t gankaigc:<commit> .
docker compose --env-file .env.docker -f docker-compose.yml \
  -f docker-compose.prod.yml -f docker-compose.local-image.yml up -d --wait
```

---

## Scenario: Signed OCI Release Vulnerability Gate

### 1. Scope / Trigger

- Trigger: any change to `package/requirements.txt`,
  `package/backend/requirements.txt`, `package/VERSION`, Docker release
  dependencies, or `.github/workflows/release-image.yml`.

### 2. Signatures

- Release identity: protected Git tag `vX.Y.Z` must equal the exact contents
  of `package/VERSION` and point at the checked-out commit.
- Published image: `ghcr.io/<owner>/gankaigc:<tag>` plus its immutable OCI
  digest.
- Security floor retained in both Python manifests:
  `python-multipart==0.0.32`, `setuptools==83.0.0`, and `wheel==0.46.3` or
  later reviewed versions that pass the same gate.

### 3. Contracts

- Build and push one multi-architecture digest with SBOM and provenance, scan
  that digest for fixed `HIGH`/`CRITICAL` vulnerabilities, and only then sign
  the same digest with keyless Cosign.
- Pin the Trivy Action to a reviewed full commit SHA. A release tag syntax
  mistake or mutable Action ref is not an acceptable supply-chain boundary.
- A failed release tag is immutable. Fix the cause in a new commit and publish
  a new tag; never move, delete, or reuse the failed tag.
- An image pushed before a failed scan is unsigned and must not be deployed.
  Production consumes a verified `name@sha256:<digest>`, never a mutable tag.
- Keep the root and backend dependency manifests synchronized because Docker,
  CI, and Windows packaging do not all install from the same path.
- A release version bump is one atomic identity update: `package/VERSION`,
  `DEFAULT_APP_VERSION`, the frontend fallback/build version, workflow-dispatch
  defaults, package publishing examples, the current release-contract test,
  and `.github/release-notes/<tag>.md` must all name the same new tag. Rebuild
  the frontend with `VITE_APP_VERSION=<tag>` and synchronize the committed
  `package/static` tree before tagging.

### 4. Validation & Error Matrix

- Tag differs from `package/VERSION` -> identity step fails before build.
- Trivy Action cannot resolve -> release fails; keep the tag immutable and fix
  the Action reference in the next release.
- Trivy reports fixed `HIGH`/`CRITICAL` findings -> signing is skipped and the
  pushed digest is rejected for deployment.
- Cosign signing or verification fails -> do not update the production digest.
- One dependency manifest loses a security pin ->
  `test_release_dependency_manifests_pin_trivy_clean_python_packages` fails.
- Version files, fallback constants, release notes, generated static assets, or
  the annotated tag disagree -> do not publish; fix and create the tag only
  after the complete release identity commit is pushed.

### 5. Good/Base/Bad Cases

- Good: tag, commit, version, digest, SBOM, provenance, clean Trivy result and
  Cosign identity all resolve to one immutable release.
- Base: an image was pushed but the vulnerability gate failed; retain it as an
  unsigned failed candidate and release the fix under a new tag.
- Bad: move a failed tag, sign before scanning, deploy by tag, or suppress a
  fixed `HIGH` finding without a reviewed exception.

### 6. Tests Required

- `test_oci_release_publishes_scans_attests_and_signs_one_digest` must assert
  the pinned Trivy Action, digest scan, SBOM/provenance, Cosign signing and
  production digest-only Compose contract.
- `test_release_dependency_manifests_pin_trivy_clean_python_packages` must
  assert the security floor in both dependency manifests.
- `test_app_version.py` and `test_release_workflow.py` must assert the current
  application version and matching release-notes file/content. Static-contract
  tests must run after the versioned frontend build and asset synchronization.
- Before tagging, run the full backend suite, frontend build, Docker build and
  a Trivy image scan with `--exit-code 1 --severity HIGH,CRITICAL
  --ignore-unfixed`.
- After CI succeeds, verify the remote digest and Cosign signature before
  providing the production `GANKAIGC_IMAGE` value.

### 7. Wrong vs Correct

#### Wrong

```yaml
uses: aquasecurity/trivy-action@0.36.0
```

```bash
docker compose pull  # GANKAIGC_IMAGE points to :latest or an unsigned tag
```

#### Correct

```yaml
uses: aquasecurity/trivy-action@<reviewed-full-commit-sha>
```

```bash
cosign verify ghcr.io/<owner>/gankaigc@sha256:<verified-digest>
```

## Scenario: Starlette TestClient Requires httpx2

### 1. Scope / Trigger

- Trigger: any change to backend test dependencies, `fastapi`, `starlette`, `httpx`, `httpx2`, or tests using `fastapi.testclient.TestClient`.

### 2. Contract

- Keep `httpx2` declared in both backend dependency manifests while the project uses `fastapi==0.136.1` / `starlette==1.3.1`.
- `httpx[socks]` is still used by runtime services; do not replace it with `httpx2`.
- `httpx2` is required by Starlette's `testclient` path and prevents:
  - `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`

### 3. Validation

```bash
package/venv/bin/python - <<'PY'
import warnings
from starlette.exceptions import StarletteDeprecationWarning
warnings.simplefilter("error", StarletteDeprecationWarning)
from fastapi.testclient import TestClient  # noqa: F401
print("TestClient import OK")
PY
```

---

## Scenario: Admin Operations Status Must Report Real Runtime Metrics

### 1. Scope / Trigger

- Trigger: any change to `package/backend/app/services/operations_service.py`, `GET /api/admin/operations/status`, or the admin operations panel data contract.
- This endpoint is an operations/observability surface; it must report real collected state or explicit unavailability, never invented demo values.

### 2. Signatures

- API:
  - `GET /api/admin/operations/status`.
- Response top-level fields:
  - `collected_at`, `system`, `database`, `worker`, `models`, `jobs`, `events`, `backup`, `onboarding`, `update`, `app`.
- Real metrics:
  - `system.cpu.percent`, `physical_cores`, `logical_cpus`.
  - `system.memory.percent`, `used_label`, `total_label`.
  - `system.disk.percent`, `used_label`, `total_label`, `backup_file_count`.
  - `system.network.rx_rate_label`, `tx_rate_label`, `available`.
  - `system.load.load1`, `load5`, `load15`.
  - `database.average_latency_ms`, `latency_samples_ms`, `slow_query_count`.
  - `models.items[]` with `stage`, `label`, `model`, `base_url`, `ok`, `message`.
  - `jobs.scheduled_count`, `completed_count`, `processing_count`, `queued_count`, `failed_count`.
  - `events[]` with `text`, `badge`, `tone`, `timestamp`.

### 3. Contracts

- Use real runtime sources:
  - Linux `/proc` for CPU, memory, network and uptime when available.
  - `shutil.disk_usage()` for disk usage.
  - `os.getloadavg()` for load when available.
  - PostgreSQL `SELECT 1` timing samples for database latency.
  - `pg_stat_activity` for slow active query count when permission allows; otherwise return `None`/`不可用`.
  - SQLAlchemy queries for worker/session/job/event counts.
- Do not add heavy dependencies such as `psutil` unless the project explicitly accepts the packaging cost; stdlib/procfs collection is preferred.
- First CPU/network requests may take a tiny local sample window; never fabricate stable placeholders.
- If a runtime source is unavailable, return `available=false`, `ok=false` where appropriate, and `不可用` labels. Do not substitute pretty constants.
- If database queries fail after the basic connection check fails, worker/job/event/onboarding helpers must catch the error, roll back the session, and return unavailable/partial status instead of turning the operations endpoint into HTTP 500.
- Model readiness in this endpoint means configuration completeness and placeholder detection only. Actual network/API connectivity remains the explicit `/operations/model-test` action.

### 4. Validation & Error Matrix

- `/proc` missing -> affected `system.*.available=false` or load `available=false`, endpoint still 200.
- PostgreSQL connection fails -> `database.ok=false`; endpoint should still include `system`, `models`, `backup`, `update`, and partial worker/job/onboarding status.
- `pg_stat_activity` permission/query fails -> `database.slow_query_count=null`, not endpoint failure.
- Model API key/base URL has placeholder values (`pwd`, `IP:PORT`, etc.) -> corresponding `models.items[].ok=false`.

### 5. Good/Base/Bad Cases

- Good: page shows current host CPU/memory/disk/load, real DB latency samples, real worker queue counts, and recent task/backup events.
- Base: Windows/non-Linux runtime has no `/proc`; page shows explicit unavailable states for procfs-only metrics.
- Bad: API or frontend hardcodes `18%`, `46%`, `3.6 GB / 7.8 GB`, `↑ 1.2 MB/s ↓ 2.4 MB/s`, `2.42 ms`, static model provider rows, or fake recovery events.

### 6. Tests Required

- Backend tests should assert `/operations/status` includes `collected_at`, `system`, `database.average_latency_ms`, `latency_samples_ms`, `worker.capacity`, `models.items`, `jobs`, and `events`.
- Backend tests should assert helper functions return unavailable/partial status when DB query calls raise.
- Frontend static tests should assert operations panel reads backend status fields and rejects fake constants.

### 7. Wrong vs Correct

#### Wrong

```jsx
{ icon: Cpu, title: 'CPU 使用率', value: '18%', meta: '4 核 / 8 线程' }
{ icon: Globe2, title: '网络状态', value: '正常', meta: '↑ 1.2 MB/s ↓ 2.4 MB/s' }
```

#### Correct

```jsx
value: percentValue(status?.system?.cpu?.percent)
meta: `↑ ${status?.system?.network?.tx_rate_label || '不可用'} ↓ ${status?.system?.network?.rx_rate_label || '不可用'}`
```

---

## Scenario: Zhuque AI Detect-Reduce Pipeline Contract

### 1. Scope / Trigger

- Trigger: any change to `ai_detect_reduce`, Zhuque 无头 API integration, optimization billing, retry flow, SSE progress, or session export.
- This is a cross-layer contract: database fields, backend service flow, API schemas, legacy credential endpoint URLs, frontend report rendering, and tests must stay aligned.

### 2. Signatures

- API:
  - `POST /api/optimization/start` accepts `processing_mode="ai_detect_reduce"`.
  - `PATCH /api/optimization/sessions/{session_id}/project` accepts `{project_id: int | null}` and moves one session into an active paper project or back to unfiled.
  - `POST /api/optimization/sessions/{session_id}/retry` must preserve Zhuque retry state.
  - `POST /api/optimization/zhuque/browser/start` is a legacy URL name; by default it starts a VPS-safe remote QR session with `mode="remote_qr"` and `sync_session=true`, returning `{status, auth_mode="headless_api", login_mode="remote_wechat_qr", credential_file, sync_session, message, session_id, qr_image_data, expires_at, connected, ready, has_token, remaining_uses, user_name, quota_text}`. `mode="local_window"` is the explicit compatibility path for the old server-local Chrome sync window and may return `login_mode="wechat_qr"` plus `command`.
  - `GET /api/optimization/zhuque/browser/status` is a legacy URL name; it returns the current GankAIGC user's isolated credential status `{status, connected, ready, has_token, remaining_uses, button_enabled, auth_mode, login_mode, credential_file, user_name, quota_text, captured_at, message}`. `GET /api/optimization/zhuque/browser/login-status?session_id=...` polls the remote QR session and may include `qr_image_data`; `POST /api/optimization/zhuque/browser/cancel?session_id=...` cancels it.
  - `GET /api/optimization/zhuque/readiness` returns Zhuque credential/API readiness without consuming a detection use.
  - `POST /api/optimization/zhuque/preflight` accepts `{original_text, processing_mode, billing_mode}` and returns readiness plus cost estimates without creating a session.
- DB:
  - `users.zhuque_free_uses_remaining`, `users.zhuque_total_uses`.
  - `optimization_sessions.zhuque_agent_trace` stores compact JSON trace for Zhuque Agent decisions.
  - `optimization_segments.zhuque_detect_rate`, `zhuque_detect_result`, `zhuque_detect_count`, `zhuque_reduce_attempt`, `zhuque_reduced_text`.
  - `zhuque_prompt_memories` stores Prompt Evolution metadata: failure signature, prompt patch, source, before/after rates, success/failure counters, and enabled state.
- Service:
  - `OptimizationService._process_ai_detect_reduce()` owns the full-text detect → selective reduce → full-text recheck loop.
  - `ZhuqueService.detect(text, session_id=None, segment_id=None)` is serialized per user through `zhuque_service.for_user(user.id)`. The manager keeps independent service instances and queues so one user's Zhuque credential/quota cannot overwrite another user's session. Browser-agent calls must preserve the optimization session context so cancellation can release the waiting transport.

### 3. Contracts

- Detection is a Zhuque-side quota operation and must not create GankAIGC beer transactions.
- Login/setup from the workspace button defaults to remote QR mode for VPS deployments: the backend opens Tencent Zhuque in headless Chromium, extracts/screenshots the WeChat QR area, returns `qr_image_data` to the frontend modal, polls until login succeeds, then writes credentials under the current user's isolated directory. The old `package/backend/app/tools/zhuque_capture_window.py --sync-session` real-window flow is retained only behind `mode="local_window"` for local development or explicit troubleshooting.
- Zhuque credentials are per GankAIGC user, not global. The default source/local path is `package/data/zhuque/users/user_<id>/creds_latest.json` with sibling `browser_state.json`, `session_status.json`, and `qrcode_latest.png`. `ZHUQUE_USER_DATA_DIR` may override the root directory. `OptimizationService`, readiness, preflight, status, and detect calls must use `zhuque_service.for_user(user.id)` / `zhuque_service.for_user(session.user_id)`. The `mode="local_window"` compatibility launcher must pass `ZHUQUE_CAPTURE_DIR=<that user dir>` so even local-window sync cannot write a global credential file. Never use a repo-level shared `creds_latest.json` for authenticated user tasks unless explicitly running the compatibility service without a user.
- Clicking GankAIGC's already-logged-in button must not pre-delete credentials or auto-logout the page. In remote QR mode it opens a new per-user QR/login session; in `local_window` mode only a real logout observed inside the Tencent Zhuque page counts as logout. After a per-user `creds_latest.json` exists, detection must use that user's isolated `ZhuqueAPI` instance. Current text detection must not rely on the obsolete WebSocket CAPTCHA shortcut (`code=21` / `msg=diff`); use a persistent Playwright real-page session that injects the captured per-user `localStorage`, captures terminal Zhuque WebSocket/HTTP result payloads from the page, and keeps anonymous and logged-in browser contexts separated. The real-page detector must cache and reuse the same Playwright page inside a credential/mode-stable context, clearing the previous input before each detect; closing and recreating a page for every detect loses the browser continuity that reduces Tencent CAPTCHA/rate-limit challenges. Refresh/close the cached page only when credentials are reset, the anonymous/logged-in mode changes, the page is closed, or the browser/context crashes. Do not resurrect global local page-control/CDP detection logic.
- Zhuque remaining-use values are not guaranteed to exist in `quotaText`; current live pages can expose quota via `availableUses`, `remainingUses`, `remaining_uses`, button text such as `Detect now(18 left)`, Chinese quota copy, or Vue page state such as `aiGenTxtRemainingCount`. Backend code must normalize all numeric sources and must also preserve real-page `button_enabled` when the numeric count is hidden. `creds_latest.json` captures quota at login time and is stale after detections; `ZhuqueService.readiness()` and `start()` must refresh quota through `ZhuqueAPI.peek_quota_status()` / `peek_remaining_uses()` when a token exists or when anonymous free detection is requested. The peek/probe must not click the Detect button or consume a detection use. Throttle passive workspace probes (current guard: `ZHUQUE_QUOTA_REFRESH_INTERVAL_SECONDS`) and force-refresh preflight/start paths with valid real text. A displayed `-1` means unknown, not zero; `remaining_uses < 0` must never be shown as a numeric quota, but it may still be ready when the live Zhuque page exposes a clickable detection button (`button_enabled=true`). Explicit `remaining_uses == 0` remains a hard block.
- Anonymous/free quota page probes must also return the real `localStorage.fp` as `fp`/`anonymous_fp`/`has_anonymous_fp`. `refresh_free_quota()` must persist logged-out `session_status.json` when a fresh anonymous fp is present even if `remaining_uses=-1`, because the next refresh/start should use `{"fp": "<persisted>"}` for the no-consume WebSocket quota peek instead of opening a new anonymous page and losing the just-issued fp. Successful anonymous `ZhuqueService.detect()` calls must also persist the detection fp and returned/deduced `remaining_uses` to the current user's logged-out `session_status.json`; otherwise the next workspace refresh may bounce back to a different legacy anonymous identity.
- Anonymous/free quota page probes must initialize Playwright with an existing token-free Zhuque anonymous identity before navigation. Priority is: current user's token-free sibling `browser_state.json` -> current user's logged-out `session_status.json.anonymous_fp` / logged-out `creds_latest.json`. Any `browser_state.json` candidate must be sanitized to `cookies: []` and only `localStorage.fp`/`language`; ignore it entirely if the top-level payload, localStorage, or cookies contain access/auth token material. Never seed cookies or tokens into anonymous page probes.
- During real-page logout sync, Zhuque can briefly hide the anonymous quota while the page rerenders. If the current logged-out auth snapshot has no quota, the capture script may preserve the last known non-negative quota in non-secret `session_status.json` so the workspace does not flash an unknown/free placeholder. This preserved value is UI state only: do not write it into `creds_latest.json`, do not treat it as a logged-in token, and prefer a newly parsed logged-out page quota or live `button_enabled` state as soon as it appears.
- Workspace passive Zhuque polling must stay fast and must not block the UI on WebSocket close/connect hangs. `ZhuqueService.readiness(text=None)` should reuse a recent live quota cache or a non-negative quota from `creds_latest.json` / `session_status.json` without a live `peek_remaining_uses()` call; unknown quota should remain `-1` instead of probing from the status panel. Preflight/start paths with valid real text (`text is not None` and length is valid) must force a live no-consume quota/page-state probe. `POST /zhuque/free-quota/refresh` is an explicit user action: if the live anonymous probe parses a non-negative number, return it; if the number is hidden but the real Zhuque detect button is clickable, return `ready=true`, `button_enabled=true`, `remaining_uses=-1`, and copy that says the remaining count will sync after detection; if neither number nor clickable button is available, return `ready=false`, `button_enabled=false`, `remaining_uses=-1`, and an actionable message instead of preserving a previous `16 次` cache.
- Real-page detection must keep the previous traffic-payload terminal-result normalization: if the page observes a terminal Zhuque payload in WebSocket frames or `/user/detect/result`, return it without requiring the old `.ai-detection-result.__vue__.type/rate` DOM shape. This prevents a false timeout after Zhuque has already consumed a detection use. Empty transient payloads such as `{"segment_labels":[]}` are not terminal results and must not be normalized into `"朱雀检测响应缺少有效检测分数"`; keep polling until a payload contains `confidence`/`rate`/`labels_ratio` or non-empty `segment_labels`, or until timeout.
- Real-page detection must fail fast when Tencent CAPTCHA UI is visible (`tcaptcha`, `captcha.gtimg.com`, `Verification Code`, `Choose all similar`, or Chinese captcha copy). In headless mode there is no human to solve the challenge, so the pipeline must return an actionable Zhuque failure instead of waiting for the full detect timeout or retrying the same blocked click three times. CAPTCHA failures must carry compact action metadata: `error_code="zhuque_captcha_required"`, `manual_verification_required=true`, `manual_verification_mode="local_window"`, and `manual_verification_action="open_zhuque_local_window"`. `_detect_full_text_once()` must persist these fields in `zhuque_detect_result` and include them in compact trace/SSE metadata so the detail page can open the explicit real-browser verification path.
- `POST /zhuque/browser/start?mode=local_window` must first ask the current user's `ZhuqueService.focus_detection_window()` to bring the cached real-page detector tab forward. If a visible detector page exists, return `status="reused"` and do not launch `zhuque_capture_window.py`, reset credentials, or open a second Chrome window. Only fall back to the compatibility capture window when no visible cached detect page is available.
- In visible local detection (`ZHUQUE_DETECT_HEADLESS=false`), `ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true` should automatically discover Chrome/Edge/Brave and connect through CDP before falling back to Playwright-launched Chromium. This auto path must use a dedicated reusable browser data directory (`ZHUQUE_DETECT_BROWSER_USER_DATA_DIR` override, otherwise per-user/project default) and may also honor `ZHUQUE_DETECT_CDP_ENDPOINT` / `ZHUQUE_DETECT_BROWSER_EXECUTABLE` for advanced deployments. It must not require ordinary users to manually run PowerShell or edit Chrome profile flags.
- `POST /zhuque/browser/start` may return `manual_required` when the Python `playwright` package or a controllable Chromium/Chrome browser is missing. On WSL, a Windows-installed Chrome/Edge/Brave under `/mnt/c/.../*.exe` counts as controllable: the capture script must launch it as a small app window with a dedicated `--remote-debugging-port` and connect via Chrome DevTools Protocol so the visible QR window appears on the user's Windows desktop while GankAIGC can still sync cookies/localStorage. It must not return `started` if the real-page sync window cannot open; otherwise users see a false positive while no login/logout state can be synced.
- If WSL cannot reach the Windows Chrome CDP port directly but Windows itself can access `http://127.0.0.1:<ZHUQUE_CDP_PORT>`, `zhuque_capture_window.py --sync-session` must switch to the Windows PowerShell CDP bridge instead of falling back to Playwright's Chromium. The bridge reads the real Windows Chrome page state, cookies, and localStorage from the Windows side and writes scoped `creds_latest.json` plus non-secret `session_status.json`.
- Windows Chrome may ignore a new `--remote-debugging-port` launch when the dedicated GankAIGC profile is already open without CDP. The capture script may stop only Chrome processes whose command line references the dedicated `ZHUQUE_WINDOWS_CHROME_USER_DATA_DIR`/`GankAIGC\ZhuqueChromeProfile` profile or the configured debug port, then relaunch with CDP. It must never kill the user's normal Chrome profile.
- Start/retry in `platform` mode for `ai_detect_reduce` must leave `charge_status="not_charged"` and `charged_credits=0`; only actual LLM reduce calls create `reason="zhuque_reduce"` transactions.
- BYOK means all LLM rewrite stages use the user's provider credentials and must never spend platform beer. Both the batch and legacy per-segment Zhuque reduce paths must skip `hold_platform_credit()` when `billing_mode="byok"`, and Zhuque preflight must report `estimated_first_round_credits=0` / `estimated_max_round_credits=0`. Platform-mode estimates and actual per-segment charges remain unchanged.
- Session project assignment is a metadata move only: it must verify the session belongs to the current user, verify the target `PaperProject` belongs to the same user and is not archived, update only `OptimizationSession.project_id/updated_at`, and never mutate segment text, billing fields, or task status. `project_id=null` means move the session back to unfiled.
- `ai_detect_reduce` start must run a preflight before creating a session:
  - text shorter than 350 chars -> HTTP 400, no session, no transaction
  - Zhuque unready -> HTTP 400 with actionable message, no session, no transaction
  - `byok` without saved/request provider config -> HTTP 400 before touching Zhuque readiness
- In `platform` mode, each reduce operation charges 10 beers per segment before calling polish/enhance. If the user lacks enough beers, the LLM call must not run. In `byok` mode the same batch/legacy rewrite flow runs without any `CreditTransaction`.
- The pipeline detects the joined full text once first. Risk rate is `max(labels_ratio["0"], labels_ratio["2"]) * 100` when `labels_ratio` is present; fallback to `rate`. Zhuque payload normalization maps `0=AI`, `1=human`, `2=suspicious/mixed`; do not reuse the old `0=human,1=AI` mapping.
- Zhuque `segment_labels[].position` is relative to the joined text using `"\n\n"` separators and live Zhuque payloads use `[start, length]`, not `[start, end]`. Only labels `0` (AI) and `2` (suspicious) select segments for rewrite. If usable positions are absent, run the fallback segment classifier instead of trusting stale/guessed positions.
- When Zhuque positions are absent, the safe fallback must first run the Zhuque fallback segment classifier instead of blindly rewriting every segment. The classifier may skip heading rows, references, formulas/metric-only lines, metadata, and very short fragments, but it must not skip section bodies: `ABSTRACT_HEADING` / `ACK_HEADING` / `SECTION_HEADING` are skipped while `ABSTRACT_BODY`, `ACK_BODY`, conclusion/discussion content, `BODY`, and conservative `UNKNOWN` candidates remain reducible. `REFERENCE_HEADING` enters reference-zone handling and reference items remain skipped. Classification trace must be compact metadata only: type codes, actions, reasons, lengths, selected indices, and counts; never full text.
- Zhuque batch reduce may group selected segments for the existing `polish` and `enhance` stages, but it must preserve the two-stage contract unless an explicit single-pass feature flag is introduced later. Batch prompts must require JSON array output keyed by segment id, independent per-segment rewriting, no merge/split/continuation, and preservation of numbers, citations, terminology, research objects, conditions, and conclusions. JSON/ID/empty-text structural failures fall back to the old single-segment path. Length violations are not batch failures; they continue through the service-side ±10% length repair contract. Batch trace/logs must include batch id, stage, selected indices, durations, validation status, fallback counts, and estimated saved calls without storing full text.
- Retry after failure must detect `zhuque_reduced_text` first when present and continue from `max(zhuque_reduce_attempt) + 1`; it must not restart from original text. When queuing the retry, clear only the stale `zhuque_agent_trace.final` diagnosis while preserving prior compact `events`, so the detail page does not keep showing the previous failed final diagnosis during the new queued/processing attempt.
- Export and session detail final text must prefer `zhuque_reduced_text`, then `enhanced_text`, then `polished_text`, then `original_text`.
- `POST /api/optimization/sessions/{session_id}/export` also supports `export_format="aigc_report_docx"` and `export_format="aigc_report_md"` for completed `ai_detect_reduce` sessions. The report must not replace the final-text export; it is a separate AIGC report artifact. It must include a summary and a per-segment table with segment index, length, risk/AI rate, AI-label rate, suspicious-label rate, human-label rate, and status. If Zhuque `segment_labels[].position` exists, map positions back to final exported segment text using the same `"\n\n"` separator convention; if positions are absent, fall back to the full-text risk/labels ratio for each segment and mark it as fallback-derived.
- Zhuque reduce output length is a hard service-side contract, not prompt-only guidance. For each rewritten segment, compare the final reduced text against `original_text` with `count_text_length`; accepted output must stay within ±10%. Retry may still start detection/rewrite from latest `zhuque_reduced_text`, but the length baseline remains the original segment to avoid carrying forward already-bloated text. If polish/enhance output exceeds the bound, run one `enhance_text` length-repair call using a "Zhuque length correction" prompt, still preserving facts, terminology, data, citations, and conclusions. If the repair still fails, fall back to the length-compliant polished result, original segment, or original round input; do not blindly truncate text.
- `zhuque_agent_trace` must be compact metadata only: event kind, round, strategy, rates, selected segment indices, decision, convergence reflection, message, and final diagnosis. Do not store full text in trace.
- Reduce trace/SSE events may include `length_adjustments`, containing compact per-segment metadata only: segment index, round, original length, before/after lengths, bounds, and repair acceptance. Do not store full original or repaired text in trace.
- Convergence reflection treats `old_rate - new_rate >= 1.0` as meaningful progress. Smaller positive drops and non-drops are stagnation signals, increment `stagnation_count`, mark repeated `stubborn_segment_indices`, and force the next stronger Zhuque strategy.
- Reflection trace events use `type="reflection"` and may include `rate_delta`, `stagnation_count`, `current_strategy`, `next_strategy`, `selected_segment_indices`, `stubborn_segment_indices`, `action`, and `message`.
- Reflection prompt notes may be appended to existing polish/enhance prompts when stagnation is observed, but the pipeline must still call the existing `polish_text` and `enhance_text` methods; do not add a separate planner/reducer LLM call for this agent.
- Prompt Evolution Agent may generate or reuse a safe `prompt_patch` when repeated stagnation/stubborn segments are present. It must derive a compact failure signature from trace/result metadata and must not store full original/reduced paper text in `zhuque_prompt_memories`.
- Prompt Evolution trace events use `type="prompt_evolution"` and may include `failure_signature`, `root_causes`, `prompt_patch`, `memory_id`, `source`, `safety_status`, and `blocked_reasons`.
- Prompt patch safety validation must reject detector-hacking tactics: zero-width/invisible characters, deliberate typos, homoglyphs, random punctuation, intentional grammar errors, and changing data/citations/conclusions. Unsafe generated patches fall back to the built-in safe strong-rewrite patch.
- Breakthrough Rewrite mode must activate after repeated stagnation reaches the strongest Zhuque strategy. In this mode the pipeline still calls `polish_text` and `enhance_text`, but it must use Zhuque-specific anti-template base prompts instead of the default "Nature/Science editor" or "style mimicry" prompts, because those default prompts can reinforce the exact regular academic tone Zhuque flags. Reduce trace/SSE events should include `rewrite_mode="breakthrough"` when active.
- Paper Reconstruction mode must activate after deeper repeated stagnation in the strongest Zhuque strategy. It is still implemented through the existing `polish_text` and `enhance_text` calls: `polish_text` generates paper-specific candidates, local scoring selects a candidate, and `enhance_text` finalizes it. It must not introduce a separate body-rewrite API. Trace/SSE events should include `rewrite_mode="paper_reconstruction"` plus compact metadata only: `paper_language`, `paper_section`, `paper_ai_patterns`, `candidate_count`, `candidate_selector`, selected candidate ids, and `fact_card_count`.
- Paper Reconstruction must support Chinese and English academic writing without casualizing the paper. It should preserve terms, numbers, citations, formulas, methods, results, and conclusions; identify common paper AI patterns such as template transitions, inflated significance, abstract noun stacks, generic contribution claims, and uniform sentence rhythm; and keep the existing ±10% Zhuque length contract.
- Zhuque reduce must be strictly monotonic-protected across rounds. Before each rewrite round, snapshot the selected segments. Accept the new rewrite only when the full-text recheck risk rate is lower than the previous round's risk rate. If the rate is equal or higher, restore the snapshot and record compact rollback metadata (`rollback_applied`, `rollback_reason="not_improved"`, `rolled_back_from_rate`, `rolled_back_to_rate`, `restored_segment_indices`). Do not spend an extra Zhuque detection just to recheck the restored snapshot; restore the previous saved text and previous detection metadata.
- If a task is already on the strongest strategy, has repeated stagnation, and a strict rollback still leaves the risk above threshold, run Plateau Auto-Recovery before giving up. The recovery pass must first generate up to three safe bulk candidates (`A/B/C`) through the existing `polish_text` + `enhance_text` path, run a full-text Zhuque recheck after each candidate, and accept only candidates with a lower risk rate than the current saved best. If all bulk candidates fail to lower risk, run a bounded segment-sweep phase over stubborn segments (highest-priority stubborn indices first, limited to the configured small segment count) with safe single-segment candidates, rechecking the joined full text after each attempt. Stop candidate search early when a candidate reaches the threshold; otherwise continue the main loop with the best lower-risk candidate.
- If bulk and segment-sweep candidates still cannot lower the risk, run Deep Reconstruction v2 before final exit. Deep Reconstruction must rebuild the paragraph from protected paper fact cards instead of synonym-level editing, using safe routes such as `evidence_first`, `method_first`, and `constraint_first`; it must still call the existing `polish_text` + `enhance_text` path, enforce the ±10% length contract, and record only compact trace metadata (`type="plateau_deep_reconstruction"`, routes, selected route, local scores, fact-card count, candidate rates, and status). It may accept only a candidate whose full-text Zhuque recheck rate is lower than the current saved best.
- If Plateau Auto-Recovery plus Deep Reconstruction v2 all flatline near the threshold, calibrate a detector floor instead of continuing to spend Zhuque uses and beer. A detector floor may be recorded when the current rate remains just above threshold, enough safe candidates have been tried, and candidate rates have near-zero spread. Trace must include `type="detector_floor"`, `rate`, `threshold`, `recommended_threshold`, `candidate_count`, `rate_spread`, and a message explaining that the best saved reduced text was preserved. The task remains `failed` unless the rate reaches the configured threshold; `plateau_exit.action` should be `detector_floor` when this diagnosis applies.

### 4. Validation & Error Matrix

- 微信扫码凭证 missing/expired -> task `failed`, error mentions WeChat QR login and credential capture guidance.
- Readiness endpoint credential missing/browser setup incomplete -> HTTP 200 with `ready=false`, `connected=false`, message/actions; it must not throw a blocking 500 for normal user setup issues.
- Start default remote QR session with missing Playwright package -> `{status:"manual_required", login_mode:"remote_wechat_qr"}` and the frontend modal shows an actionable error instead of pretending a QR exists.
- Start default remote QR session succeeds -> response includes a per-user `session_id`, `credential_file` under `package/data/zhuque/users/user_<id>/` or `ZHUQUE_USER_DATA_DIR`, and later `login-status` returns `qr_image_data` until `status="logged_in"`; once logged in, `browser/status` reports connected from that same per-user credential file. Zhuque can navigate during WeChat OAuth; transient `Page.evaluate: Execution context was destroyed` errors must be retried after `domcontentloaded` instead of failing the QR session.
- Start real-page session sync with missing Playwright package in `mode="local_window"` -> `{status:"manual_required"}` and command includes `pip install playwright`.
- Start real-page session sync with missing Chromium/Chrome -> `{status:"manual_required"}` and command includes `playwright install chromium`; do not report `started`. On WSL with Windows Chrome installed, this case should not fire; the launch env should include `ZHUQUE_CHROME_EXECUTABLE=/mnt/c/.../chrome.exe` and `ZHUQUE_CDP_PORT`.
- Start real-page session sync on WSL with Windows Chrome installed but WSL cannot connect to CDP while Windows can -> enter `windows-powershell-bridge`, keep the Windows Chrome window, and synchronize `connected/ready/user_name/remaining_uses` from PowerShell CDP snapshots.
- Dedicated Windows Chrome profile already open without CDP -> stop only that dedicated profile, relaunch with `--remote-debugging-port=<ZHUQUE_CDP_PORT>`, and do not fall back to Playwright Chromium.
- `mode="local_window"` while a visible real-page detector tab is alive -> return `status="reused"` and focus that tab; do not call the capture script or reset the user's cached detector context. No cached visible detector tab -> fall back to the old local-window capture path.
- Visible local detection with no configured CDP endpoint -> auto-launch/connect system Chrome/Edge/Brave through CDP when available; if no supported browser is found or CDP does not become ready, fall back to the existing Playwright persistent-profile path instead of failing startup.
- Workspace passive readiness with saved `remaining_uses=20` -> return immediately with `remaining_uses=20`; unknown saved quota -> return `-1` immediately; do not run `peek_remaining_uses()` just to render the status panel. Preflight with valid text -> force a live peek and use the live value when available.
- User clicks the workspace `已登录` button -> backend starts a remote QR session by default; the current user's `creds_latest.json` remains until a new logged-in snapshot replaces it. Only `mode="local_window"` uses `zhuque_capture_window.py --sync-session` and deletes credentials after a real Zhuque-page logout.
- Zhuque page is observed logged out but the immediate snapshot has no quota text -> write logged-out `session_status.json` with the previous known non-negative quota for UI smoothing only; once `Detect now(16 left)` or similar appears, replace it with the live parsed anonymous quota. If the current page only shows a clickable `Detect now` button with no number, treat it as usable-but-sync-pending (`remaining_uses=-1`, `button_enabled=true`) rather than inventing a count.
- Anonymous page probe returns `button_enabled=true`, `remaining_uses=-1`, and `fp=f743...` -> persist `session_status.json` with `anonymous_fp=f743...`, `has_token=false`, `quota_text=""`; do not require a numeric quota before persisting fp. A follow-up probe should load that fp and send it over WebSocket before falling back to another page probe.
- Per-user `session_status.json` was just updated by anonymous detection with `anonymous_fp=detected...` and `remaining_uses=3`, while another token-free browser state still shows an older fp with `Detect now(4 left)` -> refresh/page probe must keep the current user's fp first and must not report the legacy `4 次`.
- User logs in inside the Zhuque page and closes the sync window -> latest observed logged-in state remains saved, and the workspace status endpoint should continue to report logged in from `creds_latest.json`.
- Preflight endpoint must not click Zhuque detect or consume Zhuque quota.
- Zhuque page/button unusable or quota exhausted -> task `failed`, error tells the user to login/switch accounts/wait for quota restoration.
- Initial full-text detection returns `success=false` -> task `failed`; do not initialize or call LLM services.
- Full-text risk rate <= threshold -> complete without beer transactions and without modifying segment text.
- Risk rate remains above threshold after `ZHUQUE_MAX_REDUCE_ROUNDS` -> task `failed`; error includes current rate, threshold, per-run round count, and cumulative round count; trace final diagnosis should include stubborn segment indices when reflection identified them. Repeated strongest-strategy strict rollbacks must first try Plateau Auto-Recovery, Deep Reconstruction v2, and detector-floor calibration before final failure.
- Platform beer balance below 10 during an actual reduce call -> fail before polish/enhance; no partial LLM output should be written for that segment.
- Zhuque reduce output length drifts beyond ±10% -> length-repair call must run before saving `zhuque_reduced_text`; the recheck must detect the repaired/fallback text, not the bloated intermediate output.
- A reduce round lowers risk and a later round is equal or higher -> rollback protection restores the previous segment text/detection metadata and the trace marks `rollback_applied=true`.
- Trace JSON invalid/missing on older sessions -> session detail API still returns `zhuque_agent_trace=null`; frontend handles it as absent.
- Moving a session into another user's or archived project -> HTTP 404 "论文项目不存在"; moving another user's session -> HTTP 404 "会话不存在".
- AIGC report export requested for a non-`ai_detect_reduce` session -> HTTP 400 with a clear message; requested before any Zhuque detection metadata exists -> HTTP 400. `txt` and `pdf` remain rejected by schema unless explicitly reintroduced with tests.
- Prompt memory must survive startup schema creation and Alembic upgrade; missing table on existing deployments should be created by `Base.metadata.create_all()` during startup before migrations add indexes/columns.

### 5. Good/Base/Bad Cases

- Good: full text returns labels for only segments 1 and 3; only those segments run polish/enhance, two `zhuque_reduce` transactions are recorded, and the recheck writes the final report to all segments.
- Good: Workspace preflight sees ready Zhuque credentials and returns estimates, then start creates an `ai_detect_reduce` session with no `optimization_start` hold.
- Good: an unfiled session can be moved into `test1` through `PATCH /sessions/{session_id}/project`, disappears from `project_id=0`, appears under `project_id=<test1>`, and can be moved back with `project_id=null`.
- Good: On a VPS, Workspace `扫码登录` opens an in-app modal with a live QR image; scanning from any computer logs in only the current GankAIGC user and writes the scoped `creds_latest.json` under `ZHUQUE_USER_DATA_DIR`.
- Good: Two users scan different Zhuque accounts; their `credential_file` paths, `session_status.json`, quota cache, and serialized detect queues stay isolated, and one user's login cannot overwrite another user's token.
- Good: Workspace `已登录` opens a fresh remote QR session without deleting the old credential. In `mode="local_window"`, if the user only closes the Zhuque page, GankAIGC remains logged in; if the user logs out in the Zhuque page, that user's `creds_latest.json` is removed and the workspace becomes logged out.
- Good: logout sync removes `creds_latest.json` only after real page logout, but keeps `session_status.json.remaining_uses=16` during a transient quota-text gap so the workspace immediately shows `16 次`.
- Good: WSL launches Windows Chrome, WSL cannot access `127.0.0.1:<port>`, Windows PowerShell can; the bridge reads `userName`, `aiGenAccessToken`, `fp`, cookies, and quota from the Windows page and the workspace updates to connected without opening a second Playwright browser.
- Good: a Tencent CAPTCHA appears in the visible real-page detector window; clicking the manual verification action focuses that same detector tab and returns `status="reused"` instead of opening a separate Zhuque sync window.
- Good: on a normal local computer, visible Zhuque detection automatically opens one reusable system Chrome/Edge/Brave CDP window with a stable GankAIGC data directory; the user does not need to know CDP, profile names, or PowerShell commands.
- Good: passive workspace polling returns the saved quota instantly and does not hang on WebSocket close; task preflight still refreshes the quota before creating a session.
- Good: QR capture is needed only before credentials exist; subsequent detections use WebSocket API and never need a local browser/debug port.
- Good: A high-risk session records trace events for initial detect and each reduce/recheck round, including strategy and risk-rate change.
- Good: A high-risk session whose first reduced output is too long records `length_adjustments`, saves a repaired/fallback text within ±10%, and rechecks that text.
- Good: A session with repeated minor drops records reflection events, upgrades strategy despite nominal rate decreases, and shows stubborn segments in final diagnosis if still above threshold.
- Good: A session with repeated stagnation records a `prompt_evolution` trace event, appends a safe strong-rewrite prompt patch to existing polish/enhance prompts, and records a compact prompt memory.
- Good: A session stuck at 100% for multiple rounds enters `rewrite_mode="breakthrough"`, stops using the default polish/enhance base prompts for that round, and records the rewrite mode in trace.
- Good: A session that remains stuck after breakthrough enters `rewrite_mode="paper_reconstruction"`, records Chinese/English paper pattern metadata, selects among 2-3 candidates by local AI-pattern score, preserves facts, and still enforces the ±10% length contract before Zhuque recheck.
- Good: A session reaches 34.9% and the next rewrite rechecks at 100%; the pipeline restores the 34.9% text instead of saving the 100% rewrite.
- Good: A session stuck near 25% after repeated strongest-strategy rollbacks records `type="plateau_recovery"` candidate rates, tries bulk candidates first, then bounded stubborn-segment sweep candidates, and accepts a lower-risk candidate when found. If those fail, it records `type="plateau_deep_reconstruction"` and may accept a lower-risk route such as `evidence_first`.
- Good: A session flatlining at `24.52%` against a `20%` threshold after bulk, segment-sweep, and deep-reconstruction candidates records `type="detector_floor"`, recommends a threshold such as `26%`, exits with `plateau_exit.action="detector_floor"`, and preserves the best saved text.
- Good: a completed `ai_detect_reduce` export with `aigc_report_docx`/`aigc_report_md` returns a separate "AIGC检测报告" filename, includes each final segment's text and per-segment AI rate, and still lets normal `docx`/`md` export return only the final paper text.
- Base: full text risk rate is below threshold; all segments keep original text, detect count is 1, and no beer transaction exists.
- Bad: retrying a failed `ai_detect_reduce` session with 0 beers pre-holds `optimization_start` or redetects original text; both violate the contract.
- Bad: retrying a failed `ai_detect_reduce` session leaves the old `zhuque_agent_trace.final.diagnosis` in place, causing the detail page to show the previous failure as the current attempt's diagnosis.
- Bad: AIGC report export uses `labels_ratio[1]` as AI, writes the report over the final paper export, omits segment rows, or reports raw `-1` remaining uses as a negative quota.
- Bad: `byok` start with no provider config calls Zhuque readiness first; this leaks setup order and can produce confusing Zhuque errors before the API config error.

### 6. Tests Required

- Billing: start and retry do not pre-hold platform credit for `ai_detect_reduce`; actual reduce charges `zhuque_reduce`.
- Retry trace: retrying a failed/stopped `ai_detect_reduce` session removes stale `zhuque_agent_trace.final` but preserves existing compact trace `events`.
- Pipeline: low-risk skip, high-risk selective rewrite by `segment_labels`, suspicious-label rewrite, no-label fallback, max-round failure, retry from latest reduced text, cumulative retry rounds, and length repair for bloated reduce output.
- Zhuque API: WebSocket success parsing, label mapping (`0=AI`, `1=human`, `2=suspicious`), and non-terminal frame ignore.
- Remote QR login: default `browser/start` returns `login_mode="remote_wechat_qr"`, `session_id`, and per-user `credential_file`; `login-status` returns QR image and terminal logged-in/error/expired states; `cancel` closes the session; tests must prove user A/B paths are isolated and OAuth navigation-time `Execution context was destroyed` evaluate failures are retried.
- Local-window compatibility capture: missing script, missing Playwright, missing browser runtime, subprocess env (`PLAYWRIGHT_BROWSERS_PATH`, per-user `ZHUQUE_CAPTURE_DIR`), explicit `mode="local_window"`, and credential status endpoint connected/disconnected shapes.
- WSL Windows Chrome capture: test the PowerShell bridge branch does not start Playwright, the dedicated GankAIGC Chrome profile restart targets only that profile/debug port, and no fallback to Playwright occurs after Windows Chrome CDP setup fails.
- Local-window reuse: test `ZhuqueAPI.focus_cached_page()` selects the live `matrix.tencent.com/ai-detect` tab and that `POST /zhuque/browser/start?mode=local_window` returns `status="reused"` without invoking the capture launcher when a visible detect page exists.
- Auto system browser detection: test configured `ZHUQUE_DETECT_CDP_ENDPOINT` wins, visible local mode can prefer auto system browser CDP, and disabling `ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER` returns to the previous persistent-profile fallback.
- API/detail/export: `zhuque_detect_result` is serialized and final text prefers `zhuque_reduced_text`.
- Project assignment: tests must cover unfiled -> project, project -> unfiled, and rejection of another user's/archived project.
- AIGC report export: `aigc_report_docx` and `aigc_report_md` return distinct filenames, MIME types, and per-segment AI-rate rows mapped from `segment_labels[].position`; non-Zhuque sessions and missing report metadata return HTTP 400.
- Readiness/preflight: actionable response fields, 350-char blocking, no session/transaction on failure, `byok` config checked before Zhuque readiness.
- Remaining-use parsing: numeric API fields, `quotaText`, English button text (`left`), credential `remainingUses`, and live `peek_remaining_uses()` fallback. Tests must prove stale credential quota is replaced by live peek quota in readiness, and that repeated passive readiness calls are throttled instead of opening a WebSocket on every poll. Tests must also prove `remaining_uses=-1`/unknown copy is not parsed as `1`, unknown logged-out quota blocks readiness/start, and forced refresh clears stale in-memory quota instead of reusing it.
- Detection transport: tests must prove valid logged-in credentials go through real-page detection instead of the obsolete WebSocket CAPTCHA bypass, timeout/reset page failures retry, repeated detects reuse one cached Playwright page while removing stale listeners, empty `segment_labels` payloads are ignored as non-terminal, visible Tencent CAPTCHA state is detected as a fast actionable failure, and page localStorage injection reads the original captured `raw.localStorage` rather than only the normalized `access_token`.
- Logged-out quota smoothing: tests must prove `_logged_out_status_with_previous_quota()` preserves a previous non-negative quota when the logged-out page snapshot temporarily lacks quota text, while still returning `connected=false` and `has_token=false`.
- Remaining-use responsiveness: tests must prove `readiness(text=None)` reuses recent live cache or known credential/session quota without a live peek, unknown quota returns `-1` without blocking the status panel, and valid-text preflight forces a bounded live peek.
- Trace: schema/migration includes `zhuque_agent_trace`; high-risk flow records detect + reduce + reflection + prompt_evolution events; repeated-stagnation reduce events include `rewrite_mode`; detail response includes trace.
- Paper Reconstruction: repeated paper stagnation records `rewrite_mode="paper_reconstruction"`, language/section/pattern metadata, candidate selection metadata, and fact-card counts without storing full candidate text in trace.
- Rollback protection: regression after a previously improved round restores saved text and records rollback metadata in trace/SSE.
- Plateau Auto-Recovery: repeated strongest-strategy rollback first evaluates bulk automatic candidates, then bounded stubborn-segment sweep candidates if bulk fails, accepts the best lower-risk candidate, restores snapshots when candidates fail, and only exits after Deep Reconstruction v2 and detector-floor calibration have also been evaluated.
- Deep Reconstruction / Detector Floor: bulk+segment-sweep failure can still be rescued by `plateau_deep_reconstruction`; when all safe candidates flatline near threshold, trace records `detector_floor` with recommended threshold and keeps the session failed but diagnosable.
- Prompt Evolution: memory table exists after Alembic/startup; signature builder, safety validator, memory selection, and pipeline prompt patch insertion have regression tests.

### 7. Wrong vs Correct

#### Wrong

```python
# Pre-holds beers at start/retry even though Zhuque may pass without LLM rewrite.
required_credits = calculate_optimization_credits(session.original_text, session.processing_mode)
CreditService(db).hold_platform_credit(user, reason="optimization_start", amount=required_credits)
```

#### Correct

```python
# Detect stage is free in GankAIGC; charge only immediately before an LLM reduce call.
if session.processing_mode == "ai_detect_reduce":
    session.charge_status = "not_charged"
    session.charged_credits = 0

CreditService(db).hold_platform_credit(
    user,
    reason="zhuque_reduce",
    session_id=session.id,
    amount=10,
)
```

#### Wrong

```python
def _start_zhuque_wechat_capture(*, switch_account: bool = False):
    if switch_account:
        Path("package/data/zhuque/creds_latest.json").unlink()  # GankAIGC click is not a real Zhuque logout
    subprocess.Popen([sys.executable, "package/backend/app/tools/zhuque_capture_window.py", "--switch"])
```

#### Correct

```python
def _start_zhuque_wechat_capture(*, sync_session: bool = True):
    args = ["--sync-session"] if sync_session else []
    subprocess.Popen([sys.executable, "package/backend/app/tools/zhuque_capture_window.py", *args])
# capture script deletes creds_latest.json only after the Zhuque page is observed as logged out.
```

#### Wrong

```python
# Passive workspace status refresh: can hang the UI on WebSocket connect/close.
if has_token:
    remaining_uses = await api.peek_remaining_uses(timeout=2.5)
```

#### Correct

```python
# Passive status uses saved quota; preflight/start force a bounded live probe.
if text is None and credential_remaining_uses >= 0:
    remaining_uses = credential_remaining_uses
else:
    remaining_uses = await self._refresh_live_remaining_uses(
        api,
        current_remaining=credential_remaining_uses,
        force=bool(text is not None and text_length_ok),
        timeout=2.5,
    )
```

---

## Scenario: Model Gateway API Format Contract

### 1. Scope / Trigger

- Trigger: any change to model provider routing, `AIService`, admin model test/list APIs, BYOK provider config, model gateway UI payloads, or optimization session model fields.
- This is a cross-layer contract: env config, DB columns, schemas, services, routes, frontend selectors, tests, and static bundle must stay aligned.

### 2. Signatures

- Env/system config:
  - `MODEL_API_FORMAT=openai_chat|anthropic` with default `openai_chat`.
- API:
  - `GET /api/admin/config` returns `system.model_api_format`.
  - `POST /api/admin/config` accepts `MODEL_API_FORMAT` and rejects unsupported formats.
  - `POST /api/admin/operations/model-test` accepts optional `api_format`.
  - `POST /api/admin/operations/model-list` accepts optional `api_format`.
  - `PUT /api/user/provider-config` accepts `api_format` and returns it masked with the rest of the config.
  - `POST /api/user/provider-config/test` tests using the saved `api_format`.
- DB:
  - `user_provider_configs.api_format VARCHAR(40) DEFAULT 'openai_chat'`.
  - `optimization_sessions.polish_api_format`, `enhance_api_format`, `emotion_api_format` preserve per-session routing.
- Internal values:
  - `openai_chat` = OpenAI-compatible `/v1/chat/completions`.
  - `anthropic` = Anthropic Messages native `/v1/messages`.

### 3. Contracts

- OpenAI-compatible behavior remains the default for old env files, old DB rows, and omitted UI payload fields.
- Anthropic native requests must use:
  - URL: `{base}/v1/messages`, or `{base}/messages` when `base` already ends with `/v1`.
  - Headers: `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`.
  - Body: `model`, `max_tokens`, `messages`, optional `system`, optional `temperature`, and `stream` when streaming.
- Anthropic response extraction reads generated text from `content[].text`; streaming reads `content_block_delta.delta.text` where `delta.type == "text_delta"`.
- Anthropic native model discovery must call the configured gateway `GET /v1/models` with Anthropic headers, then show only returned IDs that start with `claude-`; never return a curated fallback list for a GPT-only gateway.
- Audit logs and API responses must never contain plaintext API keys.

### 4. Validation & Error Matrix

- Unsupported `api_format` -> HTTP 400 for admin config or provider config save.
- Missing/placeholder API key -> structured failure from model test/list.
- Private/unsafe base URL -> existing Base URL validation error before network calls.
- `api_format=anthropic` model list -> real `GET /v1/models`; zero `claude-` IDs returns structured failure instead of fake choices.
- Old rows/sessions with NULL or missing format -> normalize to `openai_chat`.

### 5. Good/Base/Bad Cases

- Good: user selects `Anthropic Messages（原生）`, saves `https://api.anthropic.com`, tests connection, and optimization calls `/v1/messages`.
- Base: existing OpenAI-compatible config omits `api_format`; all tests and optimization calls keep current `/chat/completions` behavior.
- Bad: frontend shows fake Claude models from OpenAI fallback, sends no `api_format`, or tests a model successfully through the wrong protocol.

### 6. Tests Required

- Unit: `extract_completion_content()` accepts Anthropic message dict/object payloads.
- Operations: Anthropic model test posts to `/v1/messages` with required headers/body.
- Operations: Anthropic model list calls real `/v1/models`, filters `claude-` IDs, and fails when a gateway returns only GPT/non-Claude models.
- Provider config: save/get masks keys while preserving `api_format`; saved provider test uses the selected protocol.
- Optimization: BYOK start/retry stores per-stage `*_api_format` on `OptimizationSession`.
- Frontend static: admin `ConfigManager.jsx` and user `ApiSettingsPage.jsx` expose selectors and include `api_format` in test/list/save payloads.

### 7. Wrong vs Correct

#### Wrong

```python
client = AsyncOpenAI(api_key=api_key, base_url="https://api.anthropic.com")
await client.chat.completions.create(model="claude-sonnet-4-5", messages=messages)
```

#### Correct

```python
response = await client.post(
    anthropic_messages_url("https://api.anthropic.com"),
    headers=anthropic_headers(api_key),
    json=build_anthropic_messages_payload(
        model="claude-sonnet-4-5",
        messages=messages,
        max_tokens=4096,
    ),
)
```

## Scenario: Structure-Aware Document Parsing for Zhuque Reduce Selection

### 1. Scope / Trigger

- Trigger: any change to document upload parsing, `POST /api/optimization/documents/parse`, `POST /api/optimization/start`, admin document-parse config (`GET/POST /api/admin/config` `document_parse` block), Zhuque detect/reduce segment selection, `OptimizationSession`/`OptimizationSegment` metadata, PDF/DOCX/TXT dependencies, or trace events for `ai_detect_reduce`.
- This is a cross-layer contract: backend config, API payloads, DB columns, service selection logic, frontend start payloads, static bundle sync, and tests must stay aligned.

### 2. Signatures

- Config keys:
  - `DOCX_STRUCTURE_ENGINE=python_docx`.
  - `PDF_STRUCTURE_ENGINE=mineru` by default, with `markitdown` as the supported bypass/fallback engine.
  - MinerU settings are `MINERU_BASE_URL`, `MINERU_API_TOKEN`, `MINERU_MODEL_VERSION`, `MINERU_ENABLE_FORMULA`, `MINERU_ENABLE_TABLE`, `MINERU_IS_OCR`, `MINERU_LANGUAGE`, `MINERU_TIMEOUT_SECONDS`, and `MINERU_POLL_INTERVAL_SECONDS`.
  - Admin `GET /api/admin/config` exposes these under `document_parse` with token summary fields only: `mineru_api_token_set` and `mineru_api_token_last4`. Full `MINERU_API_TOKEN` must never be returned to the frontend. Admin `POST /api/admin/config` accepts the raw Settings names; an empty `MINERU_API_TOKEN` is a no-op and must not clear the stored token.
- API response from `POST /api/optimization/parse-document` includes:
  - `text`, `parser`, `segments`, `structure_summary`, `document_format`, `parse_engine`, `parse_fallback_used`, `parse_trace`.
  - Each segment includes `text`, `semantic_type`, `semantic_source`, `semantic_confidence`, `reduce_allowed`, `semantic_reason`, `char_start`, `char_end`, optional `page_number`, optional `bbox_json`.
- API request to `POST /api/optimization/start` may include `document_parse` with the same compact segment metadata returned by parse-document.
- DB fields:
  - `optimization_sessions.document_format`, `parse_engine`, `parse_fallback_used`, `parse_trace`.
  - `optimization_segments.semantic_type`, `semantic_source`, `semantic_confidence`, `reduce_allowed`, `semantic_reason`, `char_start`, `char_end`, `page_number`, `bbox_json`.
- Dependency contract:
  - MinerU integration uses the existing runtime `httpx` dependency; no local ML parser dependency is required.
  - `markitdown[docx,pdf]` and `python-docx` remain document parsing dependencies for fallback/DOCX paths.
  - `docling`, `torch`, and `torchvision` are not product dependencies after the Docling removal. Do not re-add them unless a new approved parser task explicitly restores them.
  - Alembic revision identifiers must be no longer than 32 characters because the project stores versions in a `varchar(32)` column.

### 3. Contracts

- Zhuque detection must still receive the complete joined document text. Do not remove abstract, TOC, references, acknowledgements, headings, or other protected content before the Zhuque full-text check.
- PDF parsing defaults to MinerU precise API v4 when `PDF_STRUCTURE_ENGINE=mineru` and `MINERU_API_TOKEN` is configured. The client must use the official upload-url -> PUT file -> poll extract-result -> download `full_zip_url` -> read `*_content_list.json` flow.
- MinerU extract-result polling is a batch endpoint: `data.extract_result` may be either a single object or a single-item array for this product's one-file upload. Accept only those explicit shapes; reject zero/multi-item arrays with a clear type/count error instead of silently falling back.
- MinerU `content_list.json` items are mapped into the existing segment contract: `text_level > 0` headings are protected, normal text goes through text rules, tables/equations/captions/reference lists/header/footer/meta items are protected, and `page_idx`/`bbox` are preserved as `page_number`/compact `bbox_json`.
- Real MinerU v4 evidence from `IJOSSER-7-9-28-33.pdf` shows references can arrive as top-level `{"type": "ref_text", "text": ...}` items, not only `{"type": "list", "sub_type": "ref_text", "list_items": [...]}`. Both observed shapes must map to protected `REFERENCE_ITEM`; do not rely on `full.md` fallback to recover references that were dropped by mapper logic.
- MinerU missing token, timeout, failed state, invalid zip, missing `content_list.json`, or empty parsed text must visibly fallback to MarkItDown with `parse_fallback_used=true`, warning text mentioning MinerU, and compact trace fields `fallback_from`, `fallback_reason`, and `fallback_message`.
- MarkItDown PDF fallback text can emit rendered soft-wrapped lines. The parser must merge single-newline body lines into paragraph-like segments while preserving blank-line paragraph boundaries and protected structural lines.
- DOCX parsing uses `python-docx` paragraph styles before text rules:
  - `Title` -> `TITLE`.
  - `Heading 1` through `Heading 4` -> `SECTION_HEADING` unless text rules identify a more specific protected semantic type.
  - `TOC 1` through `TOC 4` -> `TOC_ITEM`.
  - headers/footers -> `HEADER_FOOTER`.
- TXT uploads are first-class lightweight document uploads. They decode via `utf-8-sig`, `utf-8`, then `gb18030`, then replacement mode, and return `parser="plain_text"`, `document_format="txt"`, and `parse_engine="plain_text"`. TXT must not call MinerU or MarkItDown.
- Old Word `.doc` uploads remain unsupported; reject them with a conversion hint to save as `.docx` rather than introducing LibreOffice or speculative MinerU handling.
- Allowed rewrite semantic types are only `BODY` and `MIXED_HEADING_BODY`.
- Protected semantic types include `TITLE`, `SECTION_HEADING`, `ABSTRACT_HEADING`, `ABSTRACT_BODY`, `KEYWORDS`, `TOC_HEADING`, `TOC_ITEM`, `ACK_HEADING`, `ACK_BODY`, `REFERENCE_HEADING`, `REFERENCE_ITEM`, `TABLE`, `CAPTION`, `FORMULA`, `META`, `HEADER_FOOTER`, `SHORT_TEXT`, and `UNKNOWN_PROTECTED`.
- Zhuque `segment_labels` remain the first gate. Local semantic metadata is the second gate. A segment may be rewritten only when Zhuque maps it as AI/suspicious and `reduce_allowed=true`.
- If Zhuque hits only protected segments, the pipeline must not fallback to full-document rewriting. It should report no reducible body segments or continue only through safe plateau/stubborn-segment paths that already have explicit rewrite history and trace evidence.
- Trace must stay compact metadata only: parser engine, fallback flag/reason, hit/selected/filtered counts, selected segment indices, filtered semantic summary, protected sample indices/reasons. Never store full paper text in trace.
- Frontend must send `document_parse` returned by upload parsing into start. If the user manually edits the textarea after upload, clear `document_parse` so stale spans/styles are not applied to changed text.

### 4. Validation & Error Matrix

- PDF MinerU succeeds -> `parse_engine="mineru"`, `parse_fallback_used=false`, segments carry MinerU/text-rule semantic metadata and compact parse trace.
- PDF MinerU fails -> `parse_engine="markitdown"`, `parse_fallback_used=true`, warning mentions MinerU and MarkItDown fallback, segments carry text-rule semantic metadata.
- PDF with `PDF_STRUCTURE_ENGINE=markitdown` -> MarkItDown succeeds with `parse_fallback_used=false`. MarkItDown extraction errors should return the existing PDF parse failure.
- DOCX with Word styles -> styled headings/TOC/header/footer are protected even when the raw text could look like ordinary short paragraphs.
- TXT upload -> local plain-text parse succeeds with `parse_engine="plain_text"`; a `.doc` upload fails with a specific `.docx` conversion hint.
- Admin document-parse config -> `GET /api/admin/config` returns no full MinerU token; `POST /api/admin/config` with empty `MINERU_API_TOKEN` preserves the existing token and validates `PDF_STRUCTURE_ENGINE` as `mineru` or `markitdown`.
- Manual text or legacy sessions without stored semantic fields -> classify with reusable text-rule semantics at runtime; historical sessions must still process.
- Zhuque label maps to `ABSTRACT_BODY`/`TOC_ITEM`/`REFERENCE_ITEM` only -> selected count is zero and no full-document fallback rewrite occurs.
- Zhuque label maps to `BODY` with sufficient confidence/overlap -> only that body segment is charged and rewritten.
- User edits upload text after parse -> start payload must not include stale `document_parse`; backend uses fallback text parsing/classification.
- Migration upgrade -> revision id length must fit `varchar(32)`; long natural-language revision ids are forbidden.

### 5. Good/Base/Bad Cases

- Good: a PDF upload parses through MinerU into paragraph/structure-aware segments; Zhuque reports high AI over the whole document, but only `BODY`/`MIXED_HEADING_BODY` Zhuque-hit segments run polish/enhance.
- Good: MinerU is unavailable or unconfigured; the UI explicitly shows MarkItDown fallback and lower structure precision instead of hiding the downgrade.
- Good: a DOCX `Heading 2` paragraph and `TOC 1` entries are protected from rewrite while following body paragraphs remain eligible.
- Good: a TXT upload imports plain text through the same segment contract without MinerU cost, while `.doc` receives a clear “save as .docx” error.
- Base: pasted plain text has no structure metadata; start creates fallback parsed segments and applies text-rule semantics.
- Bad: joining the whole paper as one paragraph before Zhuque selection, then treating one full-text Zhuque hit as permission to rewrite the entire paper.
- Bad: filtering out abstract/references before Zhuque detection and then presenting the result as the full-text Zhuque rate.
- Bad: using `a.xxx || b.xxx` style speculative field fallback for unknown Zhuque or parser payloads instead of tracing the real field contract.
- Bad: reintroducing Docling/Torch dependency pins without an explicit parser migration task.

### 6. Tests Required

- Parse API tests:
  - DOCX style classification for title/headings/TOC/header-footer/body.
  - PDF MinerU mocked success maps `content_list.json` into protected and reducible semantic segments.
  - PDF MinerU regression covers top-level `type="ref_text"` reference items, preserving `[1]...` references while still dropping headers and isolated page numbers.
  - PDF MinerU mocked failure falls back to MarkItDown with `parse_fallback_used=true` and warning/trace.
  - MinerU service protocol test covers v4 upload URL, PUT upload, poll result, ZIP download, and `*_content_list.json` extraction without real network.
  - PDF MarkItDown explicit mode returns `parse_engine="markitdown"` and `parse_fallback_used=false`.
  - PDF soft-wrap line merge preserves paragraph-like body segments.
  - TXT upload returns `parser="plain_text"`, `document_format="txt"`, and `parse_engine="plain_text"`; `.doc` upload returns the `.docx` conversion hint.
  - Manual/plain text fallback classification.
  - Admin config tests cover `document_parse` token masking, empty `MINERU_API_TOKEN` no-op behavior, and `PDF_STRUCTURE_ENGINE` validation.
- Zhuque integration tests:
  - `segment_labels` AI/suspicious mapping plus semantic gate selects only body segments.
  - Protected front/back matter is filtered and summarized in trace.
  - Mixed heading+body remains rewrite-eligible.
  - No-label or legacy fallback does not rewrite titles/references/short fragments blindly.
  - Plateau/stubborn recovery does not bypass semantic protection except the explicit trace-backed stubborn history case.
- Migration/schema tests:
  - New session/segment metadata columns exist.
  - Alembic version ids fit the configured version table.
- Frontend/build tests:
  - upload stores `documentParse`, manual edit clears it, start sends `document_parse`, and production static bundle is rebuilt/synced.
- Dependency smoke:
  - `python -m pip check` when dependency manifests change.
  - No `docling`, `torch`, or `torchvision` parser dependency remains in runtime manifests unless intentionally restored by a future task.

### 7. Wrong vs Correct

#### Wrong

```python
# One joined paper paragraph destroys paragraph-level selection and makes Zhuque hits look like full-document rewrite permission.
text_for_detection = " ".join(all_paragraphs)
segments = [OptimizationSegment(index=0, original_text=text_for_detection)]
```

#### Correct

```python
# Keep full-text detection semantics while preserving local segment spans for selection.
joined_text = "\n\n".join(segment.original_text for segment in segments)
label_hits = map_zhuque_positions_to_segments(joined_text, segments, segment_labels)
selected = [seg for seg in label_hits if semantic_decision(seg).reduce_allowed]
```

#### Wrong

```text
pip install docling torch torchvision
```

#### Correct

```text
# Current product parser chain uses MinerU API plus lightweight local fallback.
httpx[socks]==0.27.0
markitdown[docx,pdf]>=0.1.3,<1.0.0
python-docx>=1.1.0
```

---

## Scenario: Zhuque Browser-Agent Transport for VPS

### 1. Scope / Trigger

- Trigger: any backend change to Zhuque transport selection, local-browser routes, browser-agent pairing/job APIs, extension polling contracts, or VPS Docker configuration.
- This is an infra and cross-layer contract spanning environment keys, FastAPI routes, SQLAlchemy models, worker transport, Chrome extension payloads, and workspace status UI.

### 2. Signatures

- Env:
  - `ZHUQUE_DETECT_TRANSPORT`: `auto | local_browser | browser_agent | server_headless`.
  - `ZHUQUE_SERVER_HEADLESS_FALLBACK`: boolean; VPS browser-agent mode should keep this `false`.
  - `ZHUQUE_BROWSER_AGENT_JOB_TIMEOUT`, `ZHUQUE_BROWSER_AGENT_HEARTBEAT_TIMEOUT`, `ZHUQUE_BROWSER_AGENT_PAIRING_TTL_SECONDS`, `ZHUQUE_BROWSER_AGENT_LONG_POLL_SECONDS`.
- Local-browser web-user API:
  - `POST /api/optimization/zhuque/local/open` opens or focuses the managed local Zhuque visible browser page and returns a `transport="local_browser"` status payload.
  - `POST /api/optimization/zhuque/local/sync` refreshes local Zhuque login/quota status without submitting detection text.
  - `POST /api/optimization/zhuque/local/focus` focuses an existing local Zhuque detect page when present.
- Browser-agent web-user API:
  - `POST /api/browser-agent/pairings` -> `{pairing_id, pairing_code, expires_at}` for the authenticated GankAIGC user.
  - `GET /api/browser-agent/status` -> `{required, transport, online, agents, message, zhuque}`; anonymous readiness is represented by `zhuque.page_found=true`, `zhuque.logged_in=false`, and `zhuque.button_enabled=true`.
  - `POST /api/browser-agent/revoke` accepts `{agent_id}` and revokes only the current user's agent.
- Extension API:
  - `POST /api/browser-agent/claim` accepts `{pairing_code, name?, extension_version?, capabilities?}` and returns `{agent_id, agent_token}` exactly once per pairing.
  - `POST /api/browser-agent/heartbeat` authenticates with the agent token.
  - `POST /api/browser-agent/jobs/claim` long-polls pending Zhuque jobs for the paired user.
  - `POST /api/browser-agent/jobs/{job_id}/progress|complete|fail` updates only jobs owned by that agent/user.
- DB:
  - `browser_agent_pairings`, `browser_agents`, `zhuque_agent_jobs` are persistent handoff tables. Docker app/worker must never depend on an in-memory queue for browser-agent Zhuque work.

### 3. Contracts

- VPS mode must use `ZHUQUE_DETECT_TRANSPORT=browser_agent` and `ZHUQUE_SERVER_HEADLESS_FALLBACK=false`; do not silently launch server-side Playwright/Chromium for Zhuque detection in this mode.
- Local desktop/source/one-click deployments keep `auto` or `local_browser` so ordinary local users are not forced to install the extension. Local routes must prefer focusing/reusing an existing Zhuque page, then use the built-in `ZhuqueAPI.open_detect_page()` local opener, before invoking the legacy visible-window launcher. Login/quota sync must reuse that visible page too; it must not launch Playwright's bundled headless Chromium in one-click/local mode. They must not require users to manually run PowerShell/CDP/Profile commands.
- Windows one-click packaging must persist local Zhuque defaults in both `windows-oneclick/.env.template` and `runtime/start.ps1`: `ZHUQUE_DETECT_TRANSPORT=auto`, `ZHUQUE_DETECT_HEADLESS=false`, `ZHUQUE_DETECT_AUTO_SYSTEM_BROWSER=true`, `ZHUQUE_SERVER_HEADLESS_FALLBACK=false`, and a local `ZHUQUE_USER_DATA_DIR`. PyInstaller must collect the Playwright Python package/driver resources because Zhuque local open uses dynamic `playwright.async_api` imports; it still must not bundle or require the Chrome extension for one-click users.
- Pairing codes and agent tokens are secret material. Store only HMAC/hash values server-side; return the agent token only from the claim response; support revocation.
- `BrowserAgentZhuqueTransport.detect()` creates a `zhuque_agent_jobs` row, waits for completion, and normalizes the extension result through the same Zhuque result normalizer used by local detection. Extension payloads with placeholder scores (`rate < 0` or `> 100`), benchmark-table labels, empty segment labels, or example/card text must be rejected before the reduce pipeline consumes them.
- Extension/manual states are progress states, not immediate failures. `manual_required` should keep the job alive until the user solves Zhuque login/CAPTCHA locally or the configured timeout expires.
- A visible login entry is not itself a blocker. Extension `0.1.8+` must allow the logged-out/guest detector when a real editor and Detect control are present, while still returning `zhuque_not_logged_in` when those controls are unavailable.
- One claimed `job_id` may submit the Zhuque Detect control at most once. Before the click, record the current network-snapshot/DOM result fingerprints; after CAPTCHA/manual recovery, resume waiting with the same per-job baseline instead of filling text and clicking again. Accept a result only when it arrives as a post-click live network event, its fingerprint differs from the baseline, the old visible DOM result was cleared before submission and then reappeared, or the page completes a full busy-to-idle cycle. Merely resuming or observing the busy state start does not make an unchanged pre-click result current. Clear-page evidence applies only to the visible DOM candidate; do not use it to accept a Vue/network snapshot that may still contain cached old state.
- Extension `0.1.9+` must accept both Zhuque summary layouts: three percentages in `human, suspicious, AI` order, or two percentages in `human, AI` order when Zhuque omits the zero-valued suspicious class. The two-value form maps suspicious to zero; a single unlabeled percentage remains ambiguous and must not be fabricated into a complete result.
- Extension `0.1.10+` must use Chrome MV3-supported repeating alarms of at least 30 seconds (`periodInMinutes >= 0.5`) for heartbeat and job claim. Install/reload, service-worker initialization, and browser startup must also run one immediate heartbeat and claim so a paired extension does not appear online while waiting for or missing its first alarm.
- Clear per-job extension state on completion, failure, timeout, or background cleanup so a finished job cannot contaminate a later claim.
- The extension may open/reuse `https://matrix.tencent.com/ai-detect/` in the user's local Chrome, but backend code must not require public CDP, remote desktop, or `--remote-debugging-port` for VPS browser-agent mode.
- Full paper text can live in `zhuque_agent_jobs.payload_text` for MVP handoff, but application logs, traces, and progress JSON must avoid logging the full payload.
- `POST /api/optimization/sessions/{session_id}/stop` must cancel every non-terminal `zhuque_agent_jobs` row linked to that optimization session. While waiting, `BrowserAgentZhuqueTransport` must also observe the durable session status and exit promptly when it becomes `stopped`; the task queue must preserve that user terminal state instead of overwriting it with `failed` when the unblocked transport raises. This is required to release the serial Docker worker for queued polish/enhance/emotional-polish tasks.
- Browser-agent quota sync must not depend on the first fixed-size slice of
  `document.body.innerText`. The result view can move or hide the quota after a
  detection. Extension version `0.1.8+` reads the shared quota contract from
  terminal detection payloads (`availableUses` / `remainingUses`), targeted DOM
  text, and Vue runtime fields such as `aiGenTxtRemainingCount`, then heartbeats
  the numeric `remaining_uses` to the backend. `remainingRequests` is not a
  Zhuque quota field and must be ignored.

### 4. Validation & Error Matrix

- No fresh online agent and transport is `browser_agent` -> preflight/start returns an actionable error before spending Zhuque quota or LLM credits.
- Pairing expired/claimed/invalid -> HTTP 400/404 style error; no token is issued.
- Revoked agent token -> heartbeat and job claim fail; status reports offline/revoked.
- Concurrent extension claims -> one job can be claimed once; row lock/atomic update prevents double execution.
- Job remains `pending/claimed/running/manual_required` beyond timeout -> backend marks it `expired` and returns a timeout message that tells the user to keep Chrome/plugin online and finish Zhuque manual verification.
- Extension completes with invalid result -> backend normalization rejects it and the session fails with a Zhuque result error rather than saving fake `-100`, `Benchmark`, or `检测中` payloads.
- VPS browser-agent mode logs show server-side Playwright Zhuque detection -> deployment/config regression.
- Plugin sync returns a logged-in status but no numeric quota -> workspace may
  confirm login only; it must not claim that remaining uses were synchronized.
- Logged-out page exposes an editor and Detect control -> heartbeat preserves `button_enabled=true`, transport remains ready, and UI reports guest mode rather than requiring login.
- Resume receives the same result fingerprint captured before the original click and no busy-to-idle transition -> keep waiting; do not complete the job from stale state and do not click again.
- Result DOM reports `0%` human and `100%` AI with no suspicious percentage -> complete with AI rate `100`, human ratio `0`, suspicious ratio `0`, and return the result to the waiting backend job.
- User stops a processing session whose plugin job is pending/claimed/running/manual-required -> the job becomes `cancelled`, transport exits within one polling interval, the session remains `stopped`, and the worker can claim the next queued task.

### 5. Good/Base/Bad Cases

- Good: VPS worker creates one persistent browser-agent job, the user's Chrome extension claims it, reuses the Zhuque tab, returns normalized `rate/labels_ratio/segment_labels`, and the reduce pipeline continues.
- Good: Workspace shows browser-agent `required=true`, generates a pairing code, then flips from offline to online after heartbeat.
- Good: User sees a visible Zhuque CAPTCHA in local Chrome; extension sends `manual_required`, the task waits, and completion resumes after the user solves it.
- Good: A logged-out Zhuque page with usable guest controls reports anonymous readiness and runs the same browser-agent job without forcing account login.
- Good: CAPTCHA appears after Detect was submitted; the background marks `detection_started=true`, retries only the wait phase, and one backend job consumes one Zhuque submission.
- Good: A completed detection leaves the Zhuque tab on its result view; the
  extension extracts the updated quota from the terminal payload or Vue state
  and the workspace updates without closing/reopening the tab.
- Good: A binary Zhuque result card omits its zero suspicious slice; the extension parses the remaining human/AI pair and completes the claimed job instead of waiting until timeout.
- Good: Chrome starts with an already-paired `0.1.10` extension; the service worker creates valid 30-second alarms and immediately claims an existing pending job without waiting for the first alarm.
- Good: A user stops a Zhuque task waiting on the plugin; the linked handoff row is cancelled and the single Docker worker proceeds to the next queued polish task instead of remaining blocked for the full browser-agent timeout.
- Base: Local `python main.py` or Windows one-click with `ZHUQUE_DETECT_TRANSPORT=auto` uses the local visible-browser path, `POST /api/optimization/zhuque/local/open` can open/focus a local page without relying on `package/backend/app/tools/zhuque_capture_window.py` inside the frozen exe, and `GET /api/browser-agent/status` returns `required=false`.
- Bad: VPS uses `server_headless` or hidden fallback by default, requires public CDP, or asks users to start Chrome with `--remote-debugging-port`.
- Bad: Extension host permissions use `<all_urls>` or backend logs include full paper text from `payload_text`.
- Bad: Treating any visible `登录` link as a hard blocker, clicking Detect again after `manual_required`, or accepting an unchanged result snapshot merely because the button just became disabled.

### 6. Tests Required

- Backend tests must cover pairing creation/claim expiry/reuse, token auth, heartbeat freshness, status online/offline, revoke, job claim/progress/complete/fail/expire, ownership checks, and browser-agent transport selection.
- Zhuque integration tests must keep local-window, built-in local opener before legacy capture, local `/zhuque/local/open|sync|focus`, remote QR, and browser-agent behavior passing when transport code exists. Release/package tests must assert one-click env template/start script/local README and PyInstaller Playwright collection remain aligned.
- Frontend/static tests must assert `browserAgentAPI`, pairing/status/revoke UI strings, `required/offline/online` copy, local-mode copy, and offline preflight blocking.
- Extension tests must cover numeric/unknown quota text, nested terminal
  payloads, Vue ref values, and rejection of unrelated `remainingRequests`.
- Extension tests must also cover anonymous editor readiness, resume-without-reclick state, rejection of pre-click fingerprints on resume/busy start, and acceptance after a live event, changed fingerprint, or completed busy cycle. Backend tests must prove `button_enabled` survives heartbeat sanitization and guest readiness does not imply `logged_in`/`has_token`.
- Extension tests must cover both three-class and two-class result text, including the `0% human / 100% AI` boundary, and reject an ambiguous single-percentage card.
- Extension tests must assert every repeating alarm uses at least `0.5` minutes and startup calls both heartbeat and job claim immediately. Backend regressions must prove stop cancels linked jobs, releases the transport promptly, and preserves the durable `stopped` session state.
- Billing regressions must cover both batch-enabled and legacy Zhuque reduce paths under BYOK and assert no balance change or `CreditTransaction`; preflight tests must assert BYOK platform-credit estimates are zero.
- Manual VPS validation must prove no server-headless Zhuque detection starts in `browser_agent` mode and the user's local Chrome performs the Zhuque interaction.

### 7. Wrong vs Correct

#### Wrong

```env
# VPS default that tends to trigger Zhuque CAPTCHA/fraud controls.
ZHUQUE_DETECT_TRANSPORT=server_headless
ZHUQUE_SERVER_HEADLESS_FALLBACK=true
```

#### Correct

```env
# VPS recommended path: dispatch to a paired user-local Chrome extension.
ZHUQUE_DETECT_TRANSPORT=browser_agent
ZHUQUE_SERVER_HEADLESS_FALLBACK=false
```
