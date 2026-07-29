# Journal - mumu (Part 1)

> AI development session journal
> Started: 2026-06-01

---


## Session 1: Fix Zhuque anonymous fingerprint persistence

**Date**: 2026-06-24
**Task**: Fix Zhuque anonymous fingerprint persistence
**Branch**: `main`

### Summary

Persist anonymous Zhuque fp from quota page probes, save it even when count is hidden, add regression coverage and backend spec guardrail.

### Main Changes

- Persist anonymous Zhuque detection fp and returned/deduced `remaining_uses` into per-user logged-out `session_status.json`.
- Make anonymous page probes prefer current-user token-free state before legacy repo-level `browser_state.json`.
- Sanitize anonymous Playwright storage state to fp/language only and reject token-bearing state candidates.
- Add regression tests for post-detection quota persistence and current-user-vs-legacy fp priority.

### Git Commits

| Hash | Message |
|------|---------|
| `c801f9a` | (see git log) |

### Testing

- [OK] `package/venv/bin/python -m pytest package/backend/tests/test_zhuque_integration.py -q` -> 89 passed
- [OK] `package/venv/bin/python -m pytest package/backend/tests -q -x` -> 394 passed
- [OK] `git diff --check`
- [OK] `package/venv/bin/python -m py_compile package/backend/app/services/zhuque_api.py package/backend/app/services/zhuque_service.py`

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: Fix Zhuque anonymous free quota probe

**Date**: 2026-06-24
**Task**: Fix Zhuque anonymous free quota probe
**Branch**: `main`

### Summary

Seed Zhuque anonymous page probes with token-free browser fp, including legacy local browser state, so free quota refresh can read visible anonymous counts like 4 left; added regression tests and backend spec guardrail.

### Main Changes

- Replaced `SessionMonitor.jsx` fabricated KPI/trend values with `/api/admin/statistics?range=today|7d|30d`.
- Rendered throughput from `statistics.processing.series.sessions` with zero/empty states.
- Removed fake queue and timeline fallbacks; empty queue/timeline now show explicit empty states.
- Added static regression assertions for the session monitor fake placeholders.
- Rebuilt frontend and synced `package/static` hashed assets.

### Git Commits

| Hash | Message |
|------|---------|
| `ee5337f` | (see git log) |

### Testing

- [OK] `package/venv/bin/python -m pytest package/backend/tests/test_frontend_redeem_entry.py -q`
- [OK] `cd package/frontend && npm run build`
- [OK] placeholder scan over `package/frontend/src` and `package/static`

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: Sync Zhuque anonymous quota after detection

**Date**: 2026-06-24
**Task**: Sync Zhuque anonymous quota after detection
**Branch**: `main`

### Summary

Fixed anonymous Zhuque quota refresh identity drift by persisting the detection fp/count, prioritizing current-user token-free state before legacy browser state, sanitizing anonymous storage state, and adding regression coverage.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `4e20687` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: Real session monitor metrics

**Date**: 2026-06-25
**Task**: Real session monitor metrics
**Branch**: `main`

### Summary

Replaced fabricated admin session monitor KPIs, queue fallback, throughput chart, timeline, and footer copy with real statistics/session API data; added static regression coverage and synced production assets.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `48488ad` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: Polish admin user management UI

**Date**: 2026-06-25
**Task**: Polish admin user management UI
**Branch**: `main`

### Summary

Fixed admin user-management layout polish: removed duplicate quick filters and inert detail ellipsis, widened the user table, normalized role badges, replaced the unlimited ellipsis action with an explicit control, added static regression coverage, rebuilt and synced package/static.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `df1cadc` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: Add Anthropic Messages adapter

**Date**: 2026-06-26
**Task**: Add Anthropic Messages adapter
**Branch**: `main`

### Summary

Added native Anthropic Messages API format across admin config, BYOK provider config, model test/list, optimization routing, frontend selectors, tests, static bundle, and backend code-spec contract.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `542e6b1` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: Zhuque batch reduce trace

**Date**: 2026-06-28
**Task**: Zhuque batch reduce trace
**Branch**: `main`

### Summary

Implemented Zhuque fallback segment classification, guarded batch polish/enhance reduce, compact agent trace events, frontend trace visualization, tests, and static bundle sync.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ad41a63` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: Structure-aware Zhuque filtering

**Date**: 2026-06-29
**Task**: Structure-aware Zhuque filtering
**Branch**: `main`

### Summary

Implemented Docling-first PDF and python-docx DOCX structure parsing, semantic rewrite gating for Zhuque segment labels, compact audit trace, CPU-only Docling dependency pins, tests, frontend parse payload flow, and static bundle sync.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `4dc67b7` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 9: Ship v2.1.0 fair multi-user concurrency

**Date**: 2026-07-29
**Task**: Ship v2.1.0 fair multi-user concurrency
**Branch**: `main`

### Summary

Implemented and verified PostgreSQL fair scheduling, per-key AI request limiting, worker hot-switching, browser-agent queue recovery, restic uploads backup, plugin v0.1.10 release packaging, v2.1.0 docs and frontend assets.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `3d9d9ce` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
