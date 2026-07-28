# Component Guidelines

> How components are built in this project.

---

## Overview

<!--
Document your project's component conventions here.

Questions to answer:
- What component patterns do you use?
- How are props defined?
- How do you handle composition?
- What accessibility standards apply?
-->

(To be filled by the team)

---

## Component Structure

<!-- Standard structure of a component file -->

(To be filled by the team)

---

## Props Conventions

<!-- How props should be defined and typed -->

(To be filled by the team)

---

## Styling Patterns

<!-- How styles are applied (CSS modules, styled-components, Tailwind, etc.) -->

(To be filled by the team)

---

## Accessibility

<!-- A11y requirements and patterns -->

(To be filled by the team)

---

## Common Mistakes

<!-- Component-related mistakes your team has made -->

(To be filled by the team)

---

## Scenario: Public Homepage Editorial Review-Desk Contract

### 1. Scope / Trigger

- Trigger: changes to `package/frontend/src/pages/WelcomePage.jsx`,
  `WelcomePage.css`, public entry-point copy, navigation, or served homepage
  assets.
- The homepage is an Apple-inspired editorial tool page, not a generic AI SaaS
  landing page. Its single visual signature is a paper manuscript paired with a
  compact interactive review panel.

### 2. Signatures

- Source component: `src/pages/WelcomePage.jsx`.
- Route-scoped stylesheet: `src/pages/WelcomePage.css`.
- Local interaction state: `previewMode` is either `detect` or `rewrite`.
- Stable test anchors:
  - `data-home-preview="workbench"`.
  - `data-home-scenarios="workflow"`.
  - `data-home-github-star="footer"`.
- Navigation destinations: `#features`, `#workflow`, `#security`, GitHub,
  `/login`, and `/register`.

### 3. Contracts

- The hero states the product action in the user's language: `保留你的论点。只调整机器味。`
  and sends the primary action to `/login` using `打开工作台`.
- The preview uses real product concepts only: Zhuque-backed detection, risky
  passages, semantic rewriting, result review, and saved history. Sample risk
  values belong to the visibly illustrative manuscript; they must never be
  presented as platform-wide accuracy or customer statistics.
- `检测视图` and `改写视图` are real buttons with `aria-pressed`; switching
  modes changes the manuscript text treatment, score label, and review state.
- Use the subject's visual materials: a Songti manuscript face, editorial
  margin rule, paragraph marks, change highlights, and a floating review panel.
  Do not replace the manuscript with a generic dashboard skeleton.
- Live blur is limited to the thin global header and the review panel
  (`home-glass` occurs exactly twice). The manuscript and content sections are
  opaque for reading quality.
- Public navigation must not expose `管理后台`. Use `登录` and `邀请码注册`.
- Capability content uses ruled editorial rows rather than repeated rounded
  cards. Numbering is reserved for the actual ordered three-step workflow, not
  decorative feature labels.
- Motion is one orchestrated entrance plus meaningful mode-change feedback.
  Avoid ambient light orbs, sweep effects, parallax, and scattered animation.
- `prefers-reduced-motion`, `prefers-reduced-transparency`,
  `prefers-contrast: more`, and missing-backdrop support require explicit
  fallbacks.

### 4. Validation & Error Matrix

- Browser lacks `backdrop-filter` -> the header and review panel use an opaque
  near-white surface.
- Reduced transparency/contrast requested -> glass becomes solid without
  hiding controls or manuscript content.
- Reduced motion requested -> paper/review entrance and copy-change animations
  stop; both preview modes remain usable.
- Mobile width -> paper and review panel leave absolute positioning, stack in a
  pale-blue reading mat, and keep all actions keyboard/touch accessible.
- `previewMode=detect` -> original text and risk highlights are visible.
- `previewMode=rewrite` -> revised copy, blue change marks, `语义保持`, and
  `待复核` are visible.
- A new claim is unsupported by source behavior -> reject it even if it makes
  the marketing page sound stronger.

### 5. Good/Base/Bad Cases

- Good: thin frosted navigation, restrained split hero, real manuscript copy,
  interactive review modes, ruled information sections, and one blue/white
  visual language.
- Base: blur and animation are unavailable; the manuscript, controls, and page
  hierarchy remain readable and operable.
- Bad: generic dashboard skeletons, gradient mesh/orbs, floating capsule nav,
  repeated icon cards, decorative feature numbering, giant marketing copy,
  dark corporate information walls, fake adoption metrics, or an admin CTA.

### 6. Tests Required

- E2E: headline, login, invitation registration, manuscript preview, GitHub
  footer, and detect-to-rewrite interaction are visible and operable.
- Static source: current hero copy, both preview modes, real workflow labels,
  stable data anchors, and exactly two `home-glass` uses are present;
  `管理后台`, Word-formatting claims, and a fourth stage are absent.
- CSS/static bundle: `backdrop-filter: blur(24px)`, manuscript/rewrite
  animations, accessibility fallbacks, and the route-scoped
  `WelcomePage-*.css` asset are present.
- Run `npm run build`, sync `dist/` to `package/static/`, then run the homepage
  E2E and `test_frontend_redeem_entry.py`.

### 7. Wrong vs Correct

#### Wrong

```jsx
<div className="gradient-orb" />
<section>{features.map((item) => <GenericRoundedCard {...item} />)}</section>
```

#### Correct

```jsx
<button aria-pressed={previewMode === 'rewrite'} onClick={() => setPreviewMode('rewrite')}>
  改写视图
</button>
<article className="home-paper" data-view={previewMode}>...</article>
```

---

## Scenario: Apple Product Tile Workspace Theme

### 1. Scope / Trigger

- Trigger: any production UI theme or layout change in `package/frontend/src/pages/WorkspacePage.jsx`, `SessionDetailPage.jsx`, or shared app shell styling in `package/frontend/src/index.css`.
- Current visual direction: Apple website product tile language for a paper AI-reduction workspace. Use content-first white/light-gray sections, SF Pro/system typography, low chrome, and one interaction accent: Action Blue `#0066cc`; reserve dark tiles for local product moments rather than the global app chrome.
- This is a CSS/product-language approximation only. Do not copy Apple assets, screenshots, icons, product claims, or private design-system code.

### 2. Signatures

- Shared CSS tokens/classes in `src/index.css`:
  - Compatibility glass tokens that must remain for existing tests and fallbacks: `--glass-bg`, `--glass-bg-strong`, `--glass-bg-solid`, `--glass-border`, `--glass-edge`, `--glass-refraction`, `--glass-shadow`, `--glass-blur`, `--glass-radius-xl`, `--app-accent`.
  - Apple product tokens: `--apple-blue`, `--apple-blue-focus`, `--apple-blue-on-dark`, `--apple-ink`, `--apple-body-muted`, `--apple-canvas`, `--apple-parchment`, `--apple-pearl`, `--apple-hairline`, `--apple-dark-tile`.
  - Apple layout/component classes: `.apple-global-nav`, `.apple-subnav`, `.apple-product-tile`, `.apple-product-tile-dark`, `.apple-action-pill`, `.apple-ghost-pill`, `.apple-utility-card`, `.apple-paper-stage`, `.apple-paper-stage-preview`, `.apple-report-stage`, `.apple-reading-panel`, `.apple-metric-card`, `.apple-config-chip`.
  - Legacy compatibility classes still used by tests/pages: `.gank-app-page`, `.gank-ambient-orb`, `.gank-liquid-panel`, `.gank-liquid-section`, `.gank-text-panel`, `.gank-segmented-control`, `.gank-glass-status-grid`, `.gank-glass-choice-active`, `.gank-glass-choice-warm`, `.gank-agent-scroll`.
- Primary pages using the contract:
  - `src/pages/WorkspacePage.jsx`.
  - `src/pages/SessionDetailPage.jsx`.
- Production static bundle location:
  - Build output: `package/frontend/dist`.
  - Served bundle: `package/static`.

### 3. Contracts

- Use Action Blue `#0066cc` as the only interactive accent for primary CTAs, active choices, links, and product-stage highlights. Do not reintroduce warm orange/black pill CTA as the main theme.
- Workspace must include a light frosted `.apple-global-nav` plus frosted light `.apple-subnav`, followed by a full-width `.apple-product-tile.apple-paper-stage` hero containing `AI PAPER RECONSTRUCTION` and the paper flow chips: `Zhuque detection`, `paper reconstruction`, `full-text recheck`. Do not use a full-width black top bar for the workspace chrome.
- Workspace processing mode and billing mode selections must both persist through refresh via localStorage keys (`gankaigc.workspace.processingMode`, `gankaigc.workspace.billingMode`). Billing cards should reuse the same `.aurora-mode-list` / `.aurora-mode-card` visual structure as processing-mode cards rather than a separate radio-dot layout.
- Use product-tile contrast intentionally: light/parchment paper stage for the main workspace, optional local dark tile (`.apple-product-tile-dark`) only inside hero/report content, and white utility cards for forms/report metrics.
- Primary actions should use `.apple-action-pill` and active press `scale(0.95)`. Secondary actions should use `.apple-ghost-pill` or a low-chrome text/link treatment.
- Utility/report cards should be low chrome: `18px` radius, hairline borders, minimal/no shadow. Heavy generic shadows and decorative gradients are not part of this direction except the single product-preview resting shadow.
- Keep legacy `.gank-*` class strings where tests or existing pages depend on them, but the visual source of truth for new theme work is the `.apple-*` class set above.
- Keep the Apple/glass visual language mostly through opaque gradients, borders, and light shadows at runtime. Heavy `.glass`, `.gank-liquid-panel`, `.apple-*`, and `.aurora-*` surfaces must be covered by a runtime performance guardrail that sets `backdrop-filter: none !important`; blurred ambient orbs should not use live `filter: blur(...)`.
- Long reading surfaces, especially original/final paper text panels, must use `.gank-text-panel` plus `.apple-reading-panel` or an equally opaque background. Do not make paper body text translucent.
- Long Agent histories must remain inside `.gank-agent-scroll` plus `custom-scrollbar` and `max-h-[560px]` so the result/original text panels stay reachable.
- The app remains light-mode-first for readability; do not add automatic dark-mode overrides that make Tailwind `text-black`, `bg-white`, or `text-gray-*` content unreadable unless the pages are audited end-to-end.
- All translucent surfaces must have solid fallbacks through both:
  - `@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))`.
  - `@media (prefers-reduced-transparency: reduce)`.
- After any production frontend change, run `npm.cmd run build`, sync `package/frontend/dist` into `package/static`, force-stage new ignored static assets, and stage old hashed assets as deletions.

### 4. Validation & Error Matrix

- Missing Apple tokens/classes in source -> `test_frontend_uses_apple_glass_theme_tokens` fails.
- Static bundle not synced after build -> the same test fails because it reads the CSS bundle referenced by `package/static/index.html`.
- Browser lacks `backdrop-filter` -> UI must fall back to solid readable surfaces, not transparent unreadable panels.
- User has reduced transparency enabled -> ambient orbs are hidden and surfaces become solid.
- Workspace feels sluggish while typing or polling -> first check for large `backdrop-filter` surfaces, blurred ambient orbs, overlapping pollers, and effect dependencies that restart initial loaders after `activeProjectId` changes.
- Static bundle grows or first route feels slow -> pages should be route-level lazy loaded with `React.lazy` + `Suspense`; static tests that inspect served JS must scan all lazy chunks, not only the entry `index-*.js`.
- SSE streams feel jumpy or CPU-heavy -> batch content/zhuque live events before setting state; do not call `setState` for every single SSE token/event.
- Warm Tabbit/orange remnants become primary visual language -> visual review fails even if static string tests pass.
- Long Agent trace -> keep a bounded scroll container so final/original paper text remains reachable.

### 5. Good/Base/Bad Cases

- Good: Workspace uses `.apple-global-nav`, `.apple-subnav`, `.apple-product-tile.apple-paper-stage`, `.apple-action-pill`, `.apple-config-chip`, and keeps the existing task form, project list, billing copy, and Zhuque readiness flow.
- Good: Session detail shows a distinct `.apple-report-stage` "Detection report preview" shell, `.apple-utility-card` metric tiles, `.apple-reading-panel` text panes, and keeps Agent trace rows inside `.gank-agent-scroll`.
- Good: New CSS bundle in `package/static/index.html` references current hashed `assets/index-*.css` and contains the Apple + fallback tokens.
- Base: A small legacy `.gank-liquid-panel` wrapper can remain for compatibility if the visible card is governed by the Apple low-chrome tokens/classes.
- Bad: Editing only `frontend/dist` or only `package/static` without source changes.
- Bad: Copying Apple screenshots, icons, marketing claims, reference-site logos, or fake product imagery into GankAIGC.
- Bad: Reintroducing multiple accent colors, warm orange primary states, black primary pill buttons, full-width black workspace chrome, or decorative mesh gradients.
- Bad: Shipping only token changes that still look like the previous white-card workspace in screenshots.

### 6. Tests Required

- Static frontend test must assert source tokens/classes and page class usage.
- Static frontend test must also read the CSS bundle referenced by `package/static/index.html` to prove static sync happened.
- Run:
  - `cd package/frontend; npm.cmd run build`
  - `cd package/backend; python -m pytest tests/test_frontend_redeem_entry.py -q --basetemp D:\AI\TOOL\GankAIGC\package\backend\tmp-pytest`

### 7. Wrong vs Correct

#### Wrong

```jsx
<section className="gank-tabbit-hero rounded-[38px] bg-orange-50">
  <button className="gank-pill-button bg-black text-white">Start optimization</button>
</section>
```

#### Correct

```jsx
<section className="apple-product-tile apple-paper-stage gank-tabbit-hero">
  <p className="gank-eyebrow">AI PAPER RECONSTRUCTION</p>
  <a href="#new-task" className="apple-action-pill">Start optimization</a>
</section>
```

## Scenario: Workspace Project Archive and History Scope Controls

### 1. Scope / Trigger

- Trigger: any change to `package/frontend/src/pages/WorkspacePage.jsx` project selector, project archive/edit controls, per-session project assignment controls, or right-side processing history list.
- The workspace history API already has a three-way scope contract; do not collapse it into a vague "全部项目" label.

### 2. Signatures

- `optimizationAPI.listSessions(projectId = null)`:
  - `projectId === null` -> call `/optimization/sessions` with no `project_id` param, returning all sessions.
  - `projectId === 0` -> call `/optimization/sessions?project_id=0`, returning only unfiled/no-project sessions.
  - `projectId > 0` -> call `/optimization/sessions?project_id=<id>`, returning that paper project's sessions.
- `optimizationAPI.updateSessionProject(sessionId, { project_id })` -> `PATCH /optimization/sessions/{session_id}/project`; assigns a single session to an active paper project, or moves it back to unfiled when `project_id=null`.
- `projectAPI.archive(projectId)` -> `DELETE /user/projects/{project_id}`; archives the project but does not delete its session history.

### 3. Contracts

- `activeProjectId` must preserve these sentinel values:
  - `null` = "全部历史".
  - `0` = "未归档历史".
  - positive number = selected paper project.
- The project selector must expose both `全部历史` and `未归档历史`; avoid old `全部项目` wording because it hid the unfiled/all distinction.
- Archive/edit controls are project-management actions and should only appear after selecting a concrete paper project. In all-history or unfiled scope, show a hint explaining that unfiled records are assigned from each session card via `归入项目`.
- Moving an unfiled session into a project is not project archiving. Use a per-session themed action (`归入项目` / `移动项目`) that calls `updateSessionProject`; do not overload the project archive button for this and do not use the browser's native `<select>` menu for this action.
- History filter icons must be actual controls with `button`, `aria-label`, and `aria-expanded`; static icons are forbidden.
- `全部历史` must be selected from the project scope selector. Do not add a second bottom "查看/刷新全部历史" button that duplicates the same scope and confuses users.
- History filter menus must render above history cards. If the side card or scroll list clips the menu, raise the menu/head z-index and keep the card overflow visible rather than letting options appear behind records.
- Per-session move menus must use the same light Apple-style custom menu as the history filter: pill trigger, white rounded menu, blue hover states, `aria-haspopup="menu"`, `aria-expanded`, and `role="menu"/"menuitem"`.

### 4. Validation & Error Matrix

- `activeProjectId === null` -> no `project_id` query param; title renders "全部历史".
- `activeProjectId === 0` -> query param `project_id=0`; title renders "未归档历史".
- selected project archived -> remove it from the selector, switch to all history, and keep archived sessions reachable through all-history results.
- session moved from unfiled to project -> remove it from the `project_id=0` current list immediately; project/all-history scopes should update the row in place or show it after refresh.
- status filter yields no rows -> show an empty-filter state with a clear-filter action, not a blank list.

### 5. Good/Base/Bad Cases

- Good: selecting a concrete project shows pill-style `编辑当前项目` and `归档当前项目` buttons with icons.
- Good: an unfiled session card exposes a themed `归入项目` menu, lets the user choose `test1` (or any active project), then removes that card from the unfiled list after the API confirms.
- Good: the filter button opens a status menu (`全部状态`, `已完成`, `失败`, `处理中`, `排队中`, `已停止`) and filters client-side rows from the loaded scope.
- Good: the project selector is the single source of truth for switching between `全部历史`, `未归档历史`, and concrete projects.
- Base: no projects exist; selector still offers `全部历史` and `未归档历史`, and archive hint remains visible.
- Bad: treating "归档到 test1" as project archive/hide; it should be session project assignment.
- Bad: `loadSessions` returns early for `null`, because that breaks all-history loading.
- Bad: a bare `<Filter />` icon or a down chevron implying a dropdown without behavior.
- Bad: a filter dropdown with lower z-index than history cards, causing menu options to appear behind records.
- Bad: native project-move `<select>` options with OS blue highlight and square borders; it visually breaks the workspace theme.

### 6. Tests Required

- Static frontend tests should assert `HISTORY_STATUS_FILTERS`, `historyStatusFilter`, `filteredSessions`, filter button ARIA, and clear-filter behavior.
- Static frontend tests should assert selector options `value="all"` / `value="0"`, `handleProjectScopeChange`, `loadSessions(null)`, the absence of `全部项目`, and the absence of duplicate bottom `查看/刷新全部历史` buttons in `WorkspacePage.jsx`.
- Static frontend tests should assert archive/edit visible strings, `projectAPI.archive(project.id)`, `updateSessionProject`, `handleMoveSessionToProject`, `归入项目`, custom menu roles/classes (`aurora-session-project-trigger`, `aurora-session-project-menu`, `role="menu"`), absence of `aurora-session-project-select`, and filter menu z-index/overflow CSS.
- Backend/API tests should assert `PATCH /api/optimization/sessions/{session_id}/project` can move an unfiled session into an active project, removes it from `project_id=0`, and can move it back with `project_id=null`.
- Build with `cd package/frontend; npm run build` and sync `package/frontend/dist` into `package/static`.

### 7. Wrong vs Correct

#### Wrong

```jsx
if (projectId === null || projectId === undefined) return;
<option value={0}>全部项目</option>
<Filter className="h-4 w-4" />
<button onClick={() => loadSessions(activeProjectId)}>查看全部历史</button>
```

#### Correct

```jsx
const resolvedProjectId = projectId === undefined ? activeProjectIdRef.current : projectId;
await optimizationAPI.listSessions(resolvedProjectId);

<option value="all">全部历史</option>
<option value="0">未归档历史</option>
<button aria-label="筛选历史状态" aria-expanded={showHistoryFilters}>...</button>
<button aria-haspopup="menu" aria-expanded={isProjectMenuOpen}>归入项目</button>
<div role="menu">...</div>
```

## Scenario: Zhuque AI Detect-Reduce UI Contract

### 1. Scope / Trigger

- Trigger: any frontend change to `ai_detect_reduce` mode selection, Zhuque WeChat credential guidance, session progress labels, result detail, or export/copy text display.
- This UI mirrors backend contracts; do not invent different risk-rate or billing semantics in components.

### 2. Signatures

- API client functions in `src/api/index.js`:
  - `optimizationAPI.startZhuqueLogin()`.
  - `optimizationAPI.getZhuqueAuthStatus()`.
  - `optimizationAPI.getZhuqueReadiness()`.
  - `optimizationAPI.preflightZhuqueTask(payload)`.
- Session segment fields consumed by detail UI:
  - `zhuque_detect_rate`, `zhuque_detect_result`, `zhuque_detect_count`, `zhuque_reduce_attempt`, `zhuque_reduced_text`.
- Session-level fields consumed by detail UI:
  - `zhuque_agent_trace`.
- Processing mode id:
  - `ai_detect_reduce`.

### 3. Contracts

- Workspace mode list must include `AI检测 + 降重`.
- Platform billing copy for `ai_detect_reduce` must say detection does not consume beer and actual high-AI LLM rewrite is charged by reduce call. Estimated start cost should display as zero/skip.
- When `processingMode === "ai_detect_reduce"`, show the Zhuque credential panel, call `getZhuqueAuthStatus()` immediately, then poll every 5 seconds while the mode remains selected.
- The same panel must call `getZhuqueReadiness()` immediately and on the same polling cadence, but the workspace visible card is intentionally compact: render `朱雀 AI 检测`, Zhuque login user name under the title, the scan-login/logged-in button, connection status, and remaining uses. Do not render page status, text-length readiness, auth method, credential filename, readiness message, action suggestions, or estimated credit details inside the workspace card.
- Zhuque status polling must be lightweight: do not overlap in-flight status/readiness requests and pause polling when `document.visibilityState !== "visible"`. The backend may refresh quota through a throttled no-text WebSocket auth peek because `creds_latest.json` quota is stale after detections; frontend must not add extra client-side probes or tighten the polling cadence to force refresh.
- If `remaining_uses` is negative or missing, render it as an unknown/sync-pending state (`检测后同步`) and never show raw `-1` or a vague `免费次数` placeholder in the compact card. If the backend status/readiness payload carries a logged-out live anonymous quota (for example from `Detect now(16 left)`), render the numeric count (`16 次`) immediately even when `connected=false` / `has_token=false`. If the backend returns `remaining_uses=-1` together with `button_enabled=true`/`ready=true`, treat it as a valid Zhuque entry point whose remaining count will sync after detection; show success feedback for refresh/preflight instead of blocking start. The workspace may cache the last known logged-out numeric quota only for smoothing a logout-page rerender gap; do not use a logged-in account quota as the logged-out fallback unless the backend has already persisted it into logged-out `session_status.json`. When the user explicitly clicks `刷新次数` and the backend still returns unknown logged-out quota, clear the cached logged-out number before merging readiness so the UI does not keep showing stale `16 次`.
- In VPS browser-agent mode, manual sync must prefer the fresh extension payload
  over an older backend status object when only the extension payload has a
  numeric quota. A missing plugin response is an error; a logged-in response
  without a numeric quota may confirm login but must say the current page did
  not return remaining uses instead of showing a successful quota-sync toast.
- Before starting an `ai_detect_reduce` task, call `preflightZhuqueTask({original_text, processing_mode, billing_mode})`; if `ready=false`, show the backend message and do not call `startOptimization`.
- If preflight returns `estimated_max_round_credits`, it may be shown in a toast or start-flow feedback only. Do not put it back into the compact workspace credential card, and do not present it as a pre-held or guaranteed charge.
- The login button calls `startZhuqueLogin({syncSession: true, mode: "remote_qr"})` by default. It opens an in-app modal that polls `getZhuqueLoginStatus(session_id)` and shows `qr_image_data` until login succeeds; `cancelZhuqueLogin(session_id)` closes active remote sessions. The compact card keeps status based on the status/readiness endpoint's connected/token fields, not on the launch response alone. Its visible label is `扫码登录` before credentials are ready and `已登录` after credentials are ready. It must not be disabled merely because credentials are already connected; logged-in users can click the same button to generate a fresh QR for the current user. Only the in-flight launch state may disable it.
- Clicking the logged-in Zhuque button must not pre-delete `creds_latest.json` or pass a destructive switch-account flow. The default backend path should open a remote QR session scoped to the current GankAIGC user; replacing credentials only happens after a successful scan writes that user's isolated credential file. The old `zhuque_capture_window.py --sync-session` behavior belongs only to explicit `mode="local_window"` tooling.
- The compact Zhuque card must not show a decorative icon to the left of `朱雀 AI 检测`; the card is narrow inside the editor column, so title, action button, connection-status metric, and remaining-uses metric must use a wrapping/flexible layout rather than fixed three-column sizing that can overlap. Desktop/tablet order must be exactly `朱雀 AI 检测` -> `扫码登录/已登录` -> `连接状态` -> `剩余次数`, staying on one row when the editor column has enough width. Metric labels, metric values, and button text should use the same 14px visual scale.
- Do not let `.aurora-zhuque-metrics` behave as one large flex/grid item on desktop, because that makes `连接状态` and `剩余次数` drop together to the second row. Use `display: contents` or equivalent so both metric tiles participate directly in the parent row after the login button.
- The title item must not use a growable `flex: 1` value on desktop, because it pushes the login button too far right. Use content-sized title width and a single shared gap token so `朱雀 AI 检测`, `已登录`, `连接状态`, and `剩余次数` have visually even spacing.
- UI copy must not tell users to "start Zhuque browser" or imply detection depends on a local browser/debug port; after credentials are ready, detection is direct headless WebSocket API using the current user's isolated credential file. The workspace card itself should stay terse, while the modal may state that each GankAIGC user stores independent Zhuque credentials.
- Session detail final text must prefer `zhuque_reduced_text`, then `enhanced_text`, then `polished_text`, then `original_text`.
- Zhuque report risk rate in UI must use `max(labels_ratio[0], labels_ratio[2]) * 100` when `labels_ratio` is present, matching backend threshold semantics. Zhuque payload normalization maps `0=AI`, `1=human`, `2=suspicious/mixed`.
- Session detail must parse `zhuque_agent_trace` defensively and render the "Agent 决策轨迹" panel when trace or live Zhuque SSE events exist. The trace list must live in a bounded-height scroll container so long multi-round histories do not push the final/original text panels off the page.
- When trace contains `type="reflection"` events, render them as "收敛反思" rows and show `stubborn_segment_indices`, `stagnation_count`, `current_strategy`, `next_strategy`, and `action` when present.
- When trace contains `type="prompt_evolution"` events, render them as "Agent 学习结果" rows and show root causes, source, safety status, and a collapsible `prompt_patch`.
- When trace or live `zhuque_reduce` events contain `length_adjustments`, render a "长度校正" summary with segment index, original length, before/after lengths, and bounds. This is metadata only; UI must not expect full text in the trace payload.
- When trace or live `zhuque_reduce` events contain `rewrite_mode`, render the mode. `rewrite_mode="breakthrough"` should be shown as "逃逸改写" so users can tell the agent has stopped using the default academic-polish base prompt after stagnation.
- When trace or live `zhuque_reduce` events contain `rewrite_mode="paper_reconstruction"`, render it as "论文重构" and show compact paper metadata when present: `paper_language`, `paper_section`, `paper_ai_patterns`, `candidate_count`, `candidate_selector`, and `fact_card_count`.
- When trace or live `zhuque_reduce` events contain `rollback_applied=true`, render a "回滚保护" summary with `rollback_reason`, `rolled_back_from_rate`, `rolled_back_to_rate`, and `restored_segment_indices` so users can see that an equal-or-worse rewrite did not overwrite a better previous version.
- When trace contains `type="plateau_exit"`, render it as "卡点退出" and explain that the best reduced text was preserved and the user should manually adjust stubborn paragraphs or change the threshold before retrying.
- When Zhuque result, trace, or live detect metadata carries `manual_verification_required=true` or `error_code="zhuque_captcha_required"`, Session detail must show an actionable CAPTCHA panel. The primary action calls `startZhuqueLogin({ syncSession: true, mode: "local_window" })` to open the explicit real-browser verification window; the secondary action retries the failed/stopped session via `retryFailedSegments` after the user completes verification.
- Session detail SSE must consume `zhuque_detect` and `zhuque_reduce` in addition to `content`; live state is supplemental and refresh must still recover from stored trace.
- Session detail SSE must throttle/batch live updates (current contract: 100ms flush window) so long content streams do not force a full component tree render for every token.

### 4. Validation & Error Matrix

- Credential status endpoint fails -> show disconnected guidance, not a blocking crash.
- Logged-out payload has a numeric quota -> update both auth/readiness state to logged out and render the number immediately; do not wait for a second readiness poll and do not flash `免费次数`.
- Browser-agent result page hides the quota in normal DOM text -> consume the
  extension's terminal-payload/Vue quota and update the card without requiring
  the user to close and reopen the Zhuque tab.
- Start login returns `manual_required` -> show backend message and command, making clear the missing dependency is for the QR authorization page only.
- Readiness endpoint fails -> show a not-ready panel with action guidance, not a blocking crash.
- Preflight returns `ready=false` -> do not start the task; toast/display `message` and `actions`.
- Launch endpoint fails -> toast backend `detail` if present.
- `zhuque_detect_result` is missing or invalid JSON -> render a lightweight empty/raw report instead of crashing.
- `zhuque_agent_trace` is missing or invalid JSON -> hide trace or show lightweight diagnosis instead of crashing.
- Final report absent -> show "暂无报告" and keep result text panels usable.
- Exporting `ai_detect_reduce` sessions must offer the normal final-paper formats plus separate AIGC report formats; non-Zhuque sessions should not show report-only options.

### 5. Good/Base/Bad Cases

- Good: selecting `ai_detect_reduce` shows credential guidance, connected state updates from polling, and detail page shows final risk rate, detect count, reduce rounds, remaining uses, labels ratio, text length, and process timeline.
- Good: the workspace can remember `ai_detect_reduce` across refresh without making the page sluggish; idle status refresh uses the backend's throttled readiness/status state, only one status/readiness pair can be in flight, and hidden tabs stop polling.
- Good: route chunks show Workspace/SessionDetail/AdminDashboard split from the initial entry bundle, and SessionDetail batches SSE content/zhuque events before state updates.
- Good: the workspace Zhuque card uses `.aurora-zhuque-status-card`, `.aurora-zhuque-metric`, `.aurora-zhuque-account`, and `.aurora-zhuque-login-button`, showing `朱雀 AI 检测`, `登录用户`, `扫码登录`/`已登录`, `连接状态`, and `剩余次数` in that order. The modal uses `.aurora-zhuque-login-modal`, `.aurora-zhuque-qr-frame`, and `.aurora-zhuque-login-stat` and never navigates away from the workspace.
- Good: when the backend cannot know live quota yet, readiness shows `检测后同步` instead of `-1` or `免费次数`, and switches to a numeric count once the live probe, session-status sync, or a detection result returns `remaining_uses`; logged-out anonymous quota may show as `16 次` without implying `已登录`.
- Good: manual browser-agent sync overlays a fresh numeric extension status on
  the latest backend status before rendering and reports the exact count.
- Good: detail page shows Agent trace rows with initial detect, round strategy, selected segments, risk-rate change, and final diagnosis.
- Good: detail page shows Convergence Reflection rows with stubborn segments and strategy-upgrade rationale after repeated minor/no drops.
- Good: detail page shows Prompt Evolution learning rows explaining why the previous prompt failed and which safe patch was used next.
- Good: detail page shows length-correction metadata when Zhuque reduce output was repaired to stay within ±10% of the original segment length.
- Good: detail page shows "逃逸改写" when a repeated-stagnation round uses `rewrite_mode="breakthrough"`.
- Good: detail page shows "论文重构" with Chinese/English language, section, AI pattern, candidate count, and fact-card metadata when a stubborn paper paragraph uses `rewrite_mode="paper_reconstruction"`.
- Good: detail page shows "回滚保护" when a round regresses, including the restored segment indices and risk-rate rollback.
- Good: a long Agent trace is scrollable inside the trace card, and `plateau_exit` appears as "卡点退出" with manual-review guidance.
- Good: the export modal for completed `ai_detect_reduce` sessions offers `AIGC检测报告 (.docx)` and `AIGC检测报告 (.md)` in addition to final paper `Word文档` and `Markdown文件`, and copy explains the report lists every segment's AI rate.
- Base: no report yet; result page still shows original/optimized text and a non-crashing empty report.
- Bad: UI treats `labels_ratio[1]` as AI, shows a fixed "20%" threshold unrelated to backend config without matching tests, marks credentials connected just because launch was attempted, deletes credentials when the user merely clicks `已登录`, disables the logged-in QR/login button so it looks clickable but cannot reopen the Zhuque sync page, uses old browser-launch wording, or reintroduces workspace card fields such as `页面状态`, `文本长度`, `认证方式`, credential filename, long API explanations, or action-suggestion rows.
- Bad: UI hides the normal final-paper export after adding AIGC report export, offers AIGC report options for non-Zhuque sessions, or labels the report export as if it were the final paper text.
- Bad: UI displays `剩余次数：-1`, causing users to read an unknown quota as negative usage.
- Bad: UI calls `startOptimization` after preflight returns `ready=false`, or displays estimated max credits as already charged beer.
- Bad: Frontend tries to force quota freshness by adding an unthrottled client-side probe or shorter polling interval, restarts initial loaders because a callback depends on `activeProjectId`, or uses large live `backdrop-filter` surfaces that repaint on every status tick.
- Bad: Synchronous page imports in `App.jsx` pull every route into the first bundle, or SessionDetail appends SSE events with one `setState` per event.

### 6. Tests Required

- Static/frontend tests should assert mode option text, launcher/status endpoint strings, browser status polling state usage, report field rendering, and `zhuque_reduced_text` final-text priority.
- Static/frontend tests should assert AIGC report export option strings (`aigc_report_docx`, `aigc_report_md`) are gated to `ai_detect_reduce` sessions and that the modal explains per-segment AI-rate reporting.
- Static/frontend tests should assert readiness/preflight endpoint strings, compact workspace readiness rendering (`朱雀 AI 检测`, `连接状态`, `剩余次数`, `登录用户`, `扫码登录`/`已登录`, `.aurora-zhuque-status-card`, `.aurora-zhuque-account`, `.aurora-zhuque-login-button`), remote QR modal rendering (`zhuqueLoginSession`, `qr_image_data`, `getZhuqueLoginStatus`, `cancelZhuqueLogin`, `.aurora-zhuque-login-modal`, `.aurora-zhuque-qr-frame`), absence of the old complex workspace fields (`页面状态`, `文本长度`, `认证方式`, estimate/action rows), preflight usage before start, Agent trace/reflection/prompt-evolution/length-correction/rewrite-mode panel strings, and `zhuque_detect` / `zhuque_reduce` SSE handling.
- Static/frontend tests should assert negative/missing `remaining_uses` renders as an unknown/sync-pending label, not raw `-1`, and that unknown text such as `remaining_uses: -1` is not parsed as `1`.
- Browser-agent frontend tests should assert missing extension responses are not
  reported as successful quota synchronization and fresh numeric extension
  status is merged before rendering.
- Static/frontend tests should assert the compact Zhuque card has no `: '免费次数'` fallback and uses a logged-out remaining-use normalizer/cache so logout can render a numeric quota from status/readiness immediately.
- Static/frontend tests should assert `handleRefreshZhuqueFreeQuota` clears the logged-out quota cache when the backend returns unknown logged-out quota, and that unknown-but-ready (`button_enabled=true`) refresh responses show sync-pending success instead of an error toast.
- Static/frontend tests should assert Zhuque status polling has an in-flight guard, pauses when the document is hidden, and that workspace queue polling uses a named interval constant rather than an aggressive inline interval.
- Static/frontend tests should assert route-level lazy loading, SSE batching refs/timer, and runtime CSS guardrails in both source CSS and the served static CSS bundle.
- Static/frontend tests should assert Paper Reconstruction trace strings: `paper_reconstruction`, "论文重构", `paper_language`, `paper_section`, `paper_ai_patterns`, `candidate_count`, and `fact_card_count`.
- Static/frontend tests should assert rollback protection strings: `rollback_applied` and "回滚保护".
- Build must pass with `npm.cmd run build` on Windows PowerShell environments where `npm.ps1` may be blocked by execution policy.
- After any production frontend change, sync `package/frontend/dist` into `package/static` before committing. Because `package/static` is ignored, new hashed assets must be staged with `git add -f package/static/...`; old hashed assets must be staged as deletions so `package/static/index.html` never points at missing files.

### 7. Wrong vs Correct

#### Wrong

```jsx
const finalText = segments.map(seg => seg.enhanced_text || seg.polished_text || seg.original_text);
const aiRate = Number(result.labels_ratio?.[1] || 0) * 100;
```

#### Correct

```jsx
const finalText = segments.map(
  seg => seg.zhuque_reduced_text || seg.enhanced_text || seg.polished_text || seg.original_text
);
const aiRate = Number(result.labels_ratio?.[0] ?? result.labels_ratio?.["0"] ?? 0) * 100;
const suspiciousRate = Number(result.labels_ratio?.[2] ?? result.labels_ratio?.["2"] ?? 0) * 100;
const riskRate = Math.max(aiRate, suspiciousRate);
```

## Scenario: Aurora Account Utility Pages Theme

### 1. Scope / Trigger

- Trigger: any visual/layout change in `package/frontend/src/pages/ProfilePage.jsx`, `CreditsPage.jsx`, `ApiSettingsPage.jsx`, or their shared account-page styling in `package/frontend/src/index.css`.
- Current direction: these secondary/account pages must visually belong to the same Apple/light workspace theme as `WorkspacePage.jsx`, not the old centered glass-card island layout.

### 2. Signatures

- Shared source classes:
  - Page shell: `gank-app-page aurora-app-page aurora-account-page`.
  - Top navigation: `apple-global-nav aurora-topbar`, `aurora-brand-logo`, `aurora-account-back-link`.
  - Main shell: `aurora-page-shell aurora-account-shell`.
  - Hero/metadata: `aurora-account-hero` only when it contains useful content. Do not render an empty decorative account hero; keep the page title in an `sr-only` heading when the visible hero is removed.
  - Cards/forms: `apple-utility-card aurora-account-card`, `apple-metric-card`, `aurora-input`, `aurora-account-primary apple-action-pill`, `aurora-secondary-action`.
- Static bundle location remains `package/static`; after build, `package/static/index.html` must reference the current hashed CSS/JS assets.

### 3. Contracts

- Profile, Credits, and API Settings pages must keep the same light Apple/Aurora chrome as the workspace: translucent-looking but runtime-opaque topbar, soft blue/cyan accents, low-shadow utility cards, rounded product surfaces, and Action Blue primary buttons.
- `返回工作台` must be a visible themed control with an icon and button frame, not a plain text link.
- Do not reintroduce `gank-glass-toolbar`, `gank-glass-card`, or a single narrow `gank-card rounded-[2rem]` island as the dominant layout for these pages.
- Decorative English eyebrow labels above Chinese headings are intentionally removed on account/admin utility pages. Do not render text such as `ACCOUNT CONTROL`, `DISPLAY NAME`, `BEER BALANCE`, `MODEL PROVIDER`, or `CONFIGURATION`; keep the Chinese title and, if needed, an `sr-only` page heading instead.
- Use `aurora-input` for form fields so focus rings and spacing match the workspace controls.
- Long ledgers/history-style lists, such as credit transactions, must be bounded and scrollable (`custom-scrollbar`) instead of pushing the page indefinitely.
- Keep business behavior unchanged: profile nickname/password/invite actions, credit redeem/load transactions, API save/test flows must keep existing API calls and validation messages.

### 4. Validation & Error Matrix

- Page misses `aurora-account-page` or `apple-global-nav aurora-topbar` -> static theme test fails.
- Page keeps old `gank-glass-toolbar`/dominant old `gank-glass-card` -> visual regression; static tests should assert absence where practical.
- Build succeeds but `package/static` is not synced -> static bundle assertions for `aurora-account-page`, absence of `aurora-account-hero-blank`, and absence of decorative English labels fail.
- Importing a Lucide icon not exported by the pinned `lucide-react` version -> `npm run build` fails; check local `node_modules/lucide-react/dist/esm/lucide-react.js` before choosing new icons.

### 5. Good/Base/Bad Cases

- Good: `ProfilePage.jsx` uses an account hero, profile card, two metric cards, themed forms, and keeps nickname/password/invite flows intact.
- Good: `CreditsPage.jsx` uses a balance card plus bounded ledger card, keeps `formatChinaDateTime(transaction.created_at)`, and uses a smaller `aurora-credit-balance-unlimited` style for the `无限啤酒` label so text does not dominate the card.
- Good: `ApiSettingsPage.jsx` uses a provider summary card plus two-column config form and keeps encrypted-key copy.
- Base: no transactions or no saved API key; page still shows a composed empty/notice state.
- Bad: a plain max-width centered white card with default toolbar, old teal/orange primary accents, native-looking inputs, or unsynced static bundle.

### 6. Tests Required

- Static frontend tests should assert each page uses `gank-app-page aurora-app-page aurora-account-page`, `apple-global-nav aurora-topbar`, `aurora-account-back-link`, `apple-utility-card aurora-account-card`, and `aurora-input`, while rejecting empty `aurora-account-hero-blank` placeholders and decorative English labels above Chinese headings.
- Static frontend tests should assert source CSS includes `.aurora-account-page`, `.aurora-account-hero`, `.aurora-account-card.apple-utility-card`, `.aurora-account-primary.apple-action-pill`, `.aurora-ledger-item`, and `.aurora-api-form`.
- Static frontend tests should read all served JS chunks in `package/static/assets` because route-level lazy pages may not be in the entry chunk.
- Run `cd package/frontend && npm run build`, sync `dist` into `../static`, remove stale hashed assets, and verify `package/static/index.html` asset references exist.

### 7. Wrong vs Correct

#### Wrong

```jsx
<div className="gank-app-page">
  <header className="gank-glass-toolbar">
    <Link to="/workspace">返回工作台</Link>
  </header>
  <main className="max-w-3xl mx-auto">
    <div className="gank-card rounded-[2rem] p-6">...</div>
  </main>
</div>
```

#### Correct

```jsx
<div className="gank-app-page aurora-app-page aurora-account-page">
  <nav className="apple-global-nav aurora-topbar">
    <BrandLogo size="md" showText className="aurora-brand-logo" />
    <Link to="/workspace" className="aurora-account-back-link">返回工作台</Link>
  </nav>
  <main className="aurora-page-shell aurora-account-shell">
    <h1 className="sr-only">账号资料</h1>
    <section className="apple-utility-card aurora-account-card">...</section>
  </main>
</div>
```

## Scenario: Aurora Admin Dashboard Theme

### 1. Scope / Trigger

- Trigger: any visual/layout change in `package/frontend/src/pages/AdminDashboard.jsx`, `SessionMonitor.jsx`, `AdminOperationsPanel.jsx`, `ConfigManager.jsx`, or shared admin styling in `package/frontend/src/index.css`.
- Current direction: admin management must use the same Apple-light Aurora product language as the workspace and account utility pages, with the first admin reference image as the sidebar/navigation baseline.

### 2. Signatures

- Admin page shell classes:
  - Root: `gank-app-page aurora-app-page aurora-admin-page`.
  - Topbar: `apple-global-nav aurora-topbar aurora-admin-topbar`.
  - Topbar actions: keep one GitHub Issues icon button (`openGithubIssues` + `<Github />`) and one direct logout button whose visible label is only `退出`.
  - Main shell: `aurora-page-shell aurora-admin-shell`.
  - Sidebar: `data-admin-nav="sidebar"`, `aurora-admin-sidebar`, `aurora-admin-nav-item`, `aurora-admin-nav-item-active`. The old duplicate service-node card is intentionally removed.
  - Content: `aurora-admin-main`, `aurora-admin-section`, `aurora-admin-section-head`, `aurora-admin-card`.
- Shared admin controls:
  - Inputs: `aurora-admin-input`.
  - Primary action: `aurora-admin-action` using Action Blue `#0066cc`.
  - Secondary action: `aurora-admin-secondary-action`.
  - Segmented tab: `aurora-admin-tab-button`, `aurora-admin-tab-button-active`.
- System config guide:
  - `ConfigManager.jsx` must render `<ApiConfigGuide />` inside `.aurora-config-guide-shell`.
  - `ApiConfigGuide.jsx` must keep `data-api-guide-multi-expand="true"` because tests and static bundle checks use it as the interaction anchor.
- System config model/detector separation:
  - The model configuration card represents the LLM gateway only: Sub API or any OpenAI-compatible proxy used by polish/enhance/emotion/compression.
  - Zhuque is Tencent AI-rate detection, not a model provider. It must be rendered as a separate detector credential/readiness card and must not appear as a provider option, model name, or model API base URL.
  - Admin and BYOK model fields use the shared `EditableModelCombobox`: the input remains freely editable, while an explicit chevron opens the discovered `/v1/models` suggestions and shows the discovered count. A successful probe may fill an empty field, but it must never replace a non-empty custom/local model just because that name is absent from the probed list.
- Operations status panel:
  - `AdminOperationsPanel.jsx` consumes `/api/admin/operations/status`.
  - System health cards must read `status.system.cpu.percent`, `status.system.memory.percent`, `status.system.disk.percent`, `status.system.network.*_rate_label`, and `status.system.load.load1/load5`.
  - Database latency must read `status.database.average_latency_ms`, `latency_samples_ms`, and `slow_query_count`.
  - Model rows must render `status.models.items`; events must render `status.events`.
  - The operations board may follow the Sub2API realtime monitoring composition (header status, refresh controls, score ring, metric tiles, trend card), but labels must match metrics GankAIGC actually collects. Do not add SLA, QPS, TPS, TTFT, or request counts unless the backend reports them.
  - Auto refresh must use a bounded interval, avoid overlapping requests with an in-flight guard, and skip polling while `document.visibilityState !== 'visible'`.
  - Latency window tabs (`1min`, `5min`, `30min`, `1h`) must stay actionable through `aria-pressed` and active styling, but must not render an extra “当前窗口 … 样本” chip or toast on every switch.
- Session monitor metrics:
  - `SessionMonitor.jsx` must call `GET /api/admin/statistics` with `params: { range: statsRange }` for `today`, `7d`, and `30d`.
  - KPI cards must read real backend fields such as `statistics.requests.in_range`, `statistics.requests.trend_percent`, `statistics.sessions.success_rate`, `statistics.sessions.success_rate_trend_percent`, `statistics.processing.avg_processing_time_in_range`, `statistics.processing.avg_processing_time_trend_percent`, and `statistics.processing.mode_rows`.
  - The throughput chart must render from `statistics.processing.series.sessions`; empty or all-zero series must show an empty/zero state instead of a decorative spike.
  - Activity queue rows must come only from real queued sessions returned by `/api/admin/sessions/active`; show an empty state when there are no queued sessions.
  - The task timeline must render real loaded sessions or a clear empty state.
- Static bundle remains `package/static`; production frontend changes must sync `package/frontend/dist` into `package/static` and remove stale hashed assets.

### 3. Contracts

- The admin left sidebar is the primary navigation. Do not reintroduce top-tab admin navigation or remove `data-admin-nav="sidebar"`.
- The seven first-level tabs must stay available by id: `dashboard`, `sessions`, `operations`, `accounts`, `announcements`, `config`, `audit`. `ADMIN_TAB_IDS` still drives URL persistence; do not break `?tab=` handling.
- All seven first-level sidebar items must share the same nav item height, icon box, padding, and active-state treatment. Do not enlarge `audit` with a separate boxed sidebar variant.
- Do not render a separate “服务节点” card/link that jumps to the operations tab; the operations tab itself is the single entry point for runtime status.
- Do not render a topbar notification/audit icon (`BellDot`, `openAdminNotifications`, notification count/dot CSS). The left sidebar `操作日志` item is the single audit entry point.
- The topbar profile/logout control should not show role prefixes such as `Admin · 退出`, `admin · 退出`, or `管理员 · 退出`; use only `退出` next to the avatar and log-out icon.
- Use Action Blue `#0066cc` as the only strong interactive color. Semantic green/amber/red chips are allowed for status, warning, and danger only.
- Do not use multicolor active gradients (`activeClass`/`inactiveClass` style maps) for admin navigation. Active state is blue text/icon, pale-blue pill, and a left blue indicator.
- Runtime-heavy glass must stay disabled. Admin surfaces may look translucent but CSS must rely on opaque/near-opaque white, hairline borders, and low shadows rather than stacked `backdrop-filter`.
- The system configuration API tutorial is a functional onboarding component, not decorative chrome. Do not hide `.aurora-config-guide-shell` with `display: none`; restyle the existing `ApiConfigGuide` with Aurora-compatible CSS instead.
- In `ConfigManager.jsx`, keep “模型中转站配置” and “腾讯朱雀 AI 率检测” conceptually separate. Do not label the provider as `ZhuQue（朱雀）`, use `zhuque-70b-chat` as a default model, or show `https://api.zhuque-ai.com/v1` as the LLM API URL. Use the admin Zhuque readiness endpoint for detection status instead of fake model-health rows.
- Do not switch `ConfigManager.jsx` or `ApiSettingsPage.jsx` to a closed model `<select>` after discovery. Provider model lists are suggestions, not an allowlist; local gateways frequently support manually named models that `/v1/models` omits.
- Operations health values must not be invented in React. Do not hardcode CPU/memory/disk/network/load/database-latency/model/provider rows such as `18%`, `3.6 GB / 7.8 GB`, `↑ 1.2 MB/s ↓ 2.4 MB/s`, `2.42 ms`, `OpenAI (gpt-4o)`, or fake recovery events. If a metric is unavailable, render the backend's `不可用`/false status instead.
- Session monitor values must not be invented in React. Do not hardcode fake trends, response times, request rates, queue counts, model counts, chart paths, date ranges, or pagination copy such as `较昨日 +18%`, `1.28s`, `* 37`, `queuedCount || 6`, `共 12 个模型`, `请求数 2,431`, `今日 00:00 ~ 23:59`, or `每页 10 条`. If a metric is unavailable, render `--`, `暂无对比数据`, or an empty state.
- Preserve business behavior and source anchors: update modal, account management handlers/API calls, `ADMIN_ACCOUNT_*` constants, `data-admin-processing-modes`, `data-admin-processing-summary`, `data-admin-operations-panel="true"`, audit formatting, and existing Chinese labels used by tests/E2E.

- The old data-diagnostics/database manager page has been removed from the admin UI. Do not import `DatabaseManager`, do not include a `database` sidebar item, do not render `activeTab === 'database'`, and do not keep `.aurora-database-*` CSS. Backend `/api/admin/database/*` endpoints may remain for compatibility/testing, but they must not be exposed as a visible admin page unless a future task explicitly restores the feature with tests.

### 4. Validation & Error Matrix

- Page misses `aurora-admin-page` or `aurora-admin-topbar` -> static theme test fails.
- Sidebar misses `aurora-admin-nav-item-active`, reintroduces duplicate service-node card, or gives `audit` a larger nav item than other tabs -> visual regression against reference image.
- Source contains old admin nav `activeClass`/`inactiveClass` gradient mapping -> static test fails.
- A tab component drops `aurora-admin-section-head` -> inconsistent functional page chrome.
- `.aurora-config-guide-shell` is present but `display: none` in source or served CSS -> system config tutorial disappears even though the component remains mounted.
- Config page treats Zhuque as a model provider or shows fake Zhuque model counts/rate-limit status -> semantic bug; Zhuque is detector-only and should read `zhuque_service.readiness()`.
- Native `<datalist>` reports models but Chrome shows no visible dropdown affordance -> use `EditableModelCombobox`; a successful probe auto-opens the primary model list, and the chevron must reopen it later.
- Operations panel contains hardcoded monitoring numbers/provider rows/events instead of backend `status.system`, `status.database`, `status.models`, `status.jobs`, and `status.events` fields -> user sees fake health data.
- Operations panel borrows Sub2API-only metrics such as SLA/QPS/TTFT without backend fields -> UI fabricates monitoring data.
- Session monitor contains hardcoded fake KPI/chart/queue strings or does not call `/api/admin/statistics` with the selected range -> user sees fake session data.
- Operations latency tabs show redundant current-window chips or switch toast spam -> visual noise returns; static tests should reject `activeLatencyWindow`, `latencySampleCount`, `当前窗口`, and latency-window switch toast copy.
- Topbar reintroduces notification/audit bell -> duplicates the `操作日志` sidebar entry and should fail static review.
- Source or served bundle reintroduces `DatabaseManager`, `数据诊断`, `id: 'database'`, or `.aurora-database-*` -> the removed diagnostics page has leaked back into the UI.
- Build succeeds but `package/static` is not synced -> static bundle assertions and served app UI drift.
- New Lucide icon import not exported by pinned `lucide-react` -> `npm run build` fails; check local `node_modules/lucide-react/dist/esm/lucide-react.js` first.

### 5. Good/Base/Bad Cases

- Good: `AdminDashboard.jsx` has a white Aurora topbar, left sidebar with 7 uniform pill nav items, no duplicate service-node card, dashboard stat cards, and URL tab persistence.
- Good: topbar actions are compact and non-duplicative: optional search/config actions, GitHub Issues icon, and direct `退出`.
- Good: `SessionMonitor`, `AdminOperationsPanel`, and `ConfigManager` each start with `aurora-admin-section-head` and keep their original API calls and operations.
- Good: `AdminOperationsPanel` displays real backend-collected CPU, memory, disk, network, load, database latency samples, model configuration status, worker capacity, job counts, and recent events in a Sub2API-inspired realtime layout with manual refresh and guarded auto refresh.
- Good: `SessionMonitor` displays selected-range requests, success rate, average processing time, trends, mode counts, queue rows, throughput series, and timeline rows from real backend statistics/session APIs, with empty states instead of fabricated fallbacks.
- Good: latency window buttons visibly switch active state without adding explanatory chips or toasts.
- Good: `ConfigManager` renders `ApiConfigGuide`, `.aurora-config-guide-shell` is `display: block`, and the guide card is restyled with Aurora borders/radius/shadows rather than removed.
- Good: `ConfigManager` shows Sub/OpenAI-compatible gateway fields for LLM calls and a separate Tencent Zhuque AI-rate detector card sourced from `/api/admin/zhuque/readiness`.
- Good: model discovery auto-opens an editable combobox, visibly reports the discovered count, and preserves a manually entered local/custom model in admin and per-user BYOK settings.
- Good: account secondary tabs use a themed segmented control, while invite/credit forms still use `ADMIN_ACCOUNT_FORM_CLASS`, `ADMIN_ACCOUNT_INPUT_CLASS`, and `ADMIN_ACCOUNT_ACTION_BUTTON_CLASS`.
- Base: a subcomponent retains some Tailwind utility classes internally, but lives inside `aurora-admin-section` and `aurora-admin-card`, and functions/tests still pass.
- Bad: old `gank-glass-toolbar`/`gank-glass-card` dominates the admin layout, nav active state uses teal/indigo/violet/amber gradients, or a visual refactor changes API endpoints/handlers.
- Bad: keeping `ApiConfigGuide` in JSX but hiding `.aurora-config-guide-shell`; static source tests can pass while users lose the tutorial.
- Bad: using `ZhuQue（朱雀）` in the provider select, `zhuque-70b-chat` as a model, `api.zhuque-ai.com` as an LLM API URL, or hardcoded “可用模型数 8 个” for Zhuque.
- Bad: replacing a custom model with `models[0]` or rendering a closed `<select>` whenever a probe returns one or more models.
- Bad: relying on native `<datalist>` as the only discovery UI; Chrome may omit the arrow and make a successfully fetched model list invisible.
- Bad: operations page keeps a pretty UI by fabricating fixed health values when the backend did not provide them.
- Bad: session monitor keeps a pretty UI by fabricating request rate, queue rows, chart spikes, model totals, date range text, or pagination copy when backend/session data is empty.
- Bad: a notification bell opens `操作日志`, because that duplicates the sidebar item and crowds the topbar.
- Bad: logout text includes role labels (`Admin · 退出`), because the button title/aria already carries context and the UI should stay concise.

### 6. Tests Required

- Static frontend tests should assert admin root/topbar/sidebar/content classes, Action Blue CSS token, active nav class, no duplicate service-node card, uniform sidebar nav sizing, section head classes in all admin subcomponents, and absence of old `activeClass`/`inactiveClass` gradient nav mapping.
- Static frontend tests should assert `ConfigManager.jsx` still renders `ApiConfigGuide`, `ApiConfigGuide.jsx` still has `data-api-guide-multi-expand="true"`, source CSS has `.aurora-config-guide-shell { display: block; }`, and served CSS does not contain `.aurora-config-guide-shell{display:none}`.
- Static frontend tests should assert `ConfigManager.jsx` separates `模型中转站配置` from `腾讯朱雀 AI 率检测`, contains `/api/admin/zhuque/readiness`, and rejects `ZhuQue（朱雀）</option>`, `zhuque-70b-chat`, `api.zhuque-ai.com`, and fake Zhuque model-count/rate-limit labels.
- Static frontend tests should assert admin/BYOK model controls use `EditableModelCombobox`, retain `role="combobox"`/`listbox`/`option`, expose a visible toggle and discovered count, auto-open the primary field after probing, merge the current value with discovered suggestions, preserve non-empty custom models, and reject `models.includes(currentModel) ? currentModel : models[0]` replacement logic.
- Static frontend tests should assert operations panel reads `status.system.*`, `status.database.average_latency_ms`, `status.database.latency_samples_ms`, `status.models.items`, and `status.events`; tests should also assert fake values/provider rows/events are absent, auto-refresh has a visibility/in-flight guard, and Sub2API-only SLA/QPS/TTFT labels are absent unless backed by API fields.
- Static frontend tests should assert `SessionMonitor.jsx` calls `/api/admin/statistics`, passes `params: { range: statsRange }`, consumes `statistics.processing.series.sessions`, renders range options for `today`/`7d`/`30d`, and rejects fake placeholders such as `较昨日`, `1.28`, `* 37`, `queuedCount || 6`, `共 12 个模型`, `请求数 2,431`, `今日 00:00 ~ 23:59`, and `每页 10 条`.
- Static frontend tests should assert latency tabs keep `handleLatencyWindowChange`, `fetchStatus({ silent: true, force: true })`, and `aria-pressed`, while rejecting `activeLatencyWindow`, `latencySampleCount`, `当前窗口`, and latency-window switch toast copy.
- Static frontend tests should assert the admin topbar rejects `BellDot`, `openAdminNotifications`, `auditNotificationLabel`, `aurora-admin-notification-*`, and `{topbarAdminLabel} · 退出`, while keeping the GitHub Issues button and direct `退出` label.
- Existing static tests must continue to assert account management strings, processing mode statistics anchors, left sidebar navigation, operations panel anchors, removal of the old data-diagnostics page, and admin tab URL persistence.
- Run `cd package/frontend && npm run build`, sync `dist` into `../static`, remove stale hashed assets, and verify `package/static/index.html` asset references exist.

### 7. Wrong vs Correct

#### Wrong

```jsx
<div className="gank-app-page">
  <div className="gank-glass-toolbar">...</div>
  <aside className="gank-glass-card">
    <button className={activeTab === id ? activeClass : inactiveClass}>...</button>
  </aside>
</div>
```

#### Correct

```jsx
<div className="gank-app-page aurora-app-page aurora-admin-page">
  <div className="apple-global-nav aurora-topbar aurora-admin-topbar">...</div>
  <aside data-admin-nav="sidebar" className="aurora-admin-sidebar">
    <button className={`aurora-admin-nav-item ${activeTab === id ? 'aurora-admin-nav-item-active' : ''}`}>...</button>
  </aside>
</div>
```

#### Wrong

```css
.aurora-config-guide-shell {
  display: none;
}
```

#### Correct

```css
.aurora-config-guide-shell {
  display: block;
}

.aurora-config-guide-shell > [data-api-guide-multi-expand="true"] {
  border: 1px solid rgba(191, 219, 254, 0.78);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
}
```

---

## Scenario: Workspace Browser-Agent Zhuque UX

### 1. Scope / Trigger

- Trigger: any frontend change to `WorkspacePage.jsx`, `src/api/index.js`, or static bundle behavior for VPS/browser-agent Zhuque detection.
- This UI is a cross-layer status surface for `GET /api/browser-agent/status`, pairing, revocation, Zhuque account/quota refresh, and Zhuque task start/preflight blocking.

### 2. Signatures

- API client functions in `src/api/index.js`:
  - `browserAgentAPI.createPairing()` -> `POST /browser-agent/pairings`.
  - `browserAgentAPI.getStatus()` -> `GET /browser-agent/status`.
  - `browserAgentAPI.revoke(agentId)` -> `POST /browser-agent/revoke` with `{agent_id}`.
- Workspace state:
  - `browserAgentStatus`, `browserAgentPairing`, `browserAgentRequired`, `browserAgentOnline`, `browserAgentPrimary`.
  - `requestBrowserAgentZhuqueRefresh()` posts `GANKAIGC_SYNC_ZHUQUE_STATUS` to the extension page bridge and then reloads backend browser-agent status.
- Backend status payload consumed by the UI:
  - `{required, transport, online, agents, message, zhuque}`.
  - `zhuque` may report guest readiness as `{page_found: true, logged_in: false, button_enabled: true, remaining_uses}`.
  - agent rows may include `{agent_id, name, status, last_seen_at, extension_version, zhuque_status}`.
- Extension bridge:
  - `browser-extension/content-gankaigc.js` is matched only to allowed GankAIGC origins, not `<all_urls>`.
  - It relays page `postMessage` requests to background `SYNC_ZHUQUE_STATUS`, which reads the live Zhuque tab and sends an immediate heartbeat containing `metadata.zhuque`.

### 3. Contracts

- The compact Zhuque card remains ordered as `朱雀 AI 检测` -> primary action -> `朱雀账号` -> `剩余次数`; browser-agent transport information is a secondary block below those core metrics. Older `连接状态` copy must not be reintroduced as the main local metric because local/browser-agent modes both need to show Zhuque account separately from transport state.
- When `required=true` or `transport="browser_agent"`, show VPS/plugin copy: `插件在线` or `插件未连接`, pairing-code generation, and optional revoke action for the connected device.
- When browser-agent is not required, show local copy such as `本地浏览器模式` and explicitly say local deployment continues using the built-in/local browser path without mandatory plugin installation. The primary action should open/focus the managed local Zhuque page via `openZhuqueLocalBrowser`, not remote QR login.
- Starting `AI检测 + 降重` while browser-agent is required but offline must fail fast in the workspace with actionable copy before the normal Zhuque preflight/start chain.
- Pairing codes are short-lived secrets. Render them only after explicit user action, not in passive page load. Do not store them in localStorage.
- In browser-agent mode, page load, manual quota refresh, and task completion should request an immediate extension-side Zhuque status sync instead of waiting for the next 30-second MV3 heartbeat. The UI must still fall back to backend status if the bridge is unavailable or the extension is stale.
- The browser-agent status payload is the aggregate polling source in browser-agent mode. The periodic panel refresh should call only `GET /api/browser-agent/status`; do not also poll the headless-only `/optimization/zhuque/browser/status` and `/optimization/zhuque/readiness` endpoints in parallel.
- Polling effects must depend on stable scalar transitions such as `browserAgentStatusLoaded`, `browserAgentRequired`, and `browserAgentOnline`, not the full `browserAgentStatus` response object. Every fetch creates a new object identity; using that object as an effect dependency restarts the effect, triggers another extension sync/heartbeat, and creates an unbounded request loop.
- Browser-agent login is optional when the extension reports a usable guest detector. Render `游客模式`, keep the primary action as `打开朱雀页面`, and describe login/CAPTCHA as conditional rather than a prerequisite.
- Explain automatic detection honestly: one initial whole-text detection, then one recheck only after each real LLM rewrite round. Do not describe stale/repeated extension clicks as normal pipeline retries.
- User-facing upgrade guidance must require extension `0.1.10+` when diagnosing an online-but-not-claiming plugin. Chrome MV3 repeating alarms must be at least 30 seconds, and extension install/reload/browser startup must perform one immediate claim; do not restore sub-30-second alarm periods.
- Keep the Apple workspace visual language: low-chrome rounded card, Action Blue for pairing action, no new heavy gradients, and static bundle sync after build.

### 4. Validation & Error Matrix

- `required=true`, `online=false` -> show `插件未连接` and generation guidance; start button flow toasts `VPS 朱雀检测需要先连接本机 Chrome 插件`.
- `required=true`, `online=true` -> show `插件在线`, device name/version when available, and allow task start to continue into Zhuque preflight. Manual refresh should spin the refresh icon, ask the extension to sync, then update `朱雀账号` / `剩余次数` from backend status.
- `required=true`, `online=true`, `zhuque.logged_in=false`, `zhuque.button_enabled=true` -> show `游客模式`; do not show a login-required blocker.
- Stable `required=true`, `online=true` payloads -> one immediate extension sync on effect entry, then one aggregate status request per configured poll interval; response-object identity changes must not retrigger the initial sync.
- `required=false`, `transport=auto/local_browser` -> show `本地浏览器模式`; do not imply plugin is mandatory.
- Pairing creation fails -> toast backend detail or `生成浏览器插件配对码失败`.
- Revocation fails -> toast backend detail or `撤销浏览器插件失败`.

### 5. Good/Base/Bad Cases

- Good: VPS user selects `AI检测 + 降重`, sees plugin offline, generates a code, enters it in the extension, status flips online, then starts the task.
- Good: user logs into Zhuque in the local Chrome tab, clicks the workspace refresh icon, and sees `朱雀账号` plus real remaining uses without waiting for the next heartbeat. After a detection job completes, the extension syncs status again so consumed quota is reflected.
- Good: a logged-out user with guest quota sees `游客模式`, opens the Zhuque page, and starts detection without being forced through account login.
- Good: an idle browser-agent workspace emits the expected bounded status poll plus the extension's independent heartbeat instead of continuously cycling through three status GETs and a forced heartbeat.
- Good: Local user still sees the normal Zhuque login/quota card plus `本地浏览器模式`, with no blocker demanding extension installation.
- Base: Browser-agent API is temporarily unreachable; the workspace falls back to non-required `auto` copy and the existing Zhuque readiness error handling remains visible.
- Bad: Rendering a pairing code automatically on page load, hiding Zhuque quota metrics behind plugin UI, adding a second unrelated朱雀 card that duplicates state, or relying solely on the delayed heartbeat for a user-clicked refresh action.
- Bad: Labeling guest-ready status as `未登录` plus `打开朱雀登录`, or promising repeated automatic detections when no rewritten text was produced.

### 6. Tests Required

- Static tests must assert `browserAgentAPI`, `/browser-agent/pairings`, `/browser-agent/status`, `/browser-agent/revoke`, local Zhuque API functions (`openZhuqueLocalBrowser`, `syncZhuqueLocalBrowser`), `browserAgentRequired`, `browserAgentOnline`, `requestBrowserAgentZhuqueRefresh`, `GANKAIGC_SYNC_ZHUQUE_STATUS`, `检测传输`, `插件在线`, `插件未连接`, `生成配对码`, `撤销插件`, `配对码`, local-mode copy, offline start-blocking copy, and manifest absence of `<all_urls>`.
- Static tests must also assert guest-mode copy, extension `0.1.10+`, Chrome-supported 30-second alarms plus immediate startup claim, two-/three-class result parsing, single-click/baseline job controls, and the initial-detect/real-rewrite-only recheck explanation.
- Polling regression tests must assert the scalar `browserAgentStatusLoaded` dependency, the browser-agent-only aggregate status branch, absence of the full response object from the effect dependency list, and exactly one immediate `requestBrowserAgentZhuqueRefresh` call in the initial loader.
- Existing static tests for the compact Zhuque card order and CSS tokens must continue to pass.
- Run `cd package/frontend && npm run build`, sync `package/frontend/dist` into `package/static`, and force-stage new ignored static assets.

### 7. Wrong vs Correct

#### Wrong

```jsx
// Blocks every local user until an extension is installed.
if (!browserAgentStatus?.online) {
  toast.error('请先安装 Chrome 插件');
  return;
}
```

#### Correct

```jsx
// Only VPS/browser-agent mode requires the plugin.
if (processingMode === 'ai_detect_reduce' && browserAgentRequired && !browserAgentOnline) {
  toast.error('VPS 朱雀检测需要先连接本机 Chrome 插件');
  return;
}
```

#### Wrong

```jsx
// Each response replaces browserAgentStatus and immediately restarts this effect.
useEffect(loadInitialZhuqueStatus, [browserAgentStatus]);
```

#### Correct

```jsx
const browserAgentStatusLoaded = browserAgentStatus !== null;
useEffect(loadInitialZhuqueStatus, [browserAgentStatusLoaded, browserAgentRequired, browserAgentOnline]);
```
