importScripts('zhuque-quota.js', 'zhuque-job.js');

const ZHUQUE_QUOTA = globalThis.GankAIGCZhuqueQuota;
const ZHUQUE_JOB_CONTROL = globalThis.GankAIGCZhuqueJobControl;
const STORAGE_KEYS = {
  serverUrl: 'gankaigc.serverUrl',
  agentToken: 'gankaigc.agentToken',
  agentId: 'gankaigc.agentId',
  agentName: 'gankaigc.agentName',
  pairingCodeDraft: 'gankaigc.pairingCodeDraft'
};

const DEFAULT_SERVER_URL = 'https://ga.mumubuku.top';
const DEFAULT_AGENT_NAME = 'Chrome on Windows';
const MATRIX_URL = 'https://matrix.tencent.com/ai-detect/';
const EXTENSION_VERSION = chrome.runtime.getManifest().version;
// Chrome 120+ clamps repeating MV3 alarms to a minimum of 30 seconds. Values
// below 0.5 minutes can reject alarm creation entirely, leaving a paired
// extension able to heartbeat on demand but unable to claim detection jobs.
const CHROME_MIN_ALARM_PERIOD_MINUTES = 0.5;
let polling = false;

function normalizeServerUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '');
}

function generateAgentId() {
  return 'agent_' + crypto.randomUUID().replace(/-/g, '');
}

async function getState() {
  return await chrome.storage.local.get(Object.values(STORAGE_KEYS));
}

async function setState(values) {
  await chrome.storage.local.set(values);
}

async function apiFetch(path, { method = 'GET', body, token } = {}) {
  const state = await getState();
  const serverUrl = normalizeServerUrl(state[STORAGE_KEYS.serverUrl] || DEFAULT_SERVER_URL);
  if (!serverUrl) {
    throw new Error('请先配置 GankAIGC 服务地址');
  }
  const headers = { 'Content-Type': 'application/json' };
  const activeToken = token || state[STORAGE_KEYS.agentToken];
  if (activeToken) {
    headers.Authorization = `Bearer ${activeToken}`;
  }
  const response = await fetch(`${serverUrl}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `请求失败: ${response.status}`);
  }
  return payload;
}

async function claimPairing({ serverUrl, pairingCode, agentName }) {
  const normalizedUrl = normalizeServerUrl(serverUrl || DEFAULT_SERVER_URL);
  if (!normalizedUrl) {
    throw new Error('GankAIGC 服务地址不能为空');
  }
  let state = await getState();
  let agentId = state[STORAGE_KEYS.agentId] || generateAgentId();
  await setState({
    [STORAGE_KEYS.serverUrl]: normalizedUrl,
    [STORAGE_KEYS.agentId]: agentId,
    [STORAGE_KEYS.agentName]: agentName || DEFAULT_AGENT_NAME,
    [STORAGE_KEYS.pairingCodeDraft]: pairingCode || ''
  });
  const payload = await apiFetch('/api/browser-agent/claim', {
    method: 'POST',
    body: {
      pairing_code: pairingCode,
      agent_id: agentId,
      name: agentName || DEFAULT_AGENT_NAME,
      extension_version: EXTENSION_VERSION,
      capabilities: { zhuque_detect: true, manual_verification: true },
      user_agent: navigator.userAgent
    }
  });
  await setState({
    [STORAGE_KEYS.agentToken]: payload.agent_token,
    [STORAGE_KEYS.agentId]: payload.agent_id
  });
  await ensureAlarms();
  await heartbeat();
  return { ok: true, agentId: payload.agent_id };
}

async function getZhuqueSessionStatus({ focus = false } = {}) {
  const tabs = await chrome.tabs.query({ url: 'https://matrix.tencent.com/*' });
  const tab = tabs.find((item) => item.url && item.url.includes('/ai-detect')) || tabs[0];
  if (!tab?.id) {
    return { page_found: false, logged_in: false, status: 'not_open', message: '未打开本机朱雀页面' };
  }
  if (focus) {
    await chrome.tabs.update(tab.id, { active: true }).catch(() => undefined);
    if (tab.windowId !== undefined) {
      await chrome.windows.update(tab.windowId, { focused: true }).catch(() => undefined);
    }
  }
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ['zhuque-quota.js', 'injected-zhuque.js'],
    world: 'MAIN'
  }).catch(() => undefined);
  let response = await chrome.tabs.sendMessage(tab.id, { type: 'GANKAIGC_ZHUQUE_STATUS' }).catch(() => null);
  if (!response) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['zhuque-quota.js', 'zhuque-job.js', 'content-zhuque.js']
    }).catch(() => undefined);
    response = await chrome.tabs.sendMessage(tab.id, { type: 'GANKAIGC_ZHUQUE_STATUS' }).catch(() => null);
  }
  return response?.status || { page_found: true, logged_in: false, status: 'unknown', message: '朱雀页面已打开，暂未识别登录状态' };
}

async function heartbeat(activeJobId = null, zhuqueStatusOverride = null) {
  const state = await getState();
  const token = state[STORAGE_KEYS.agentToken];
  const agentId = state[STORAGE_KEYS.agentId];
  if (!token || !agentId) {
    return { ok: false, message: '未配对' };
  }
  const zhuqueStatus = zhuqueStatusOverride || await getZhuqueSessionStatus().catch((error) => ({
    page_found: false,
    logged_in: false,
    status: 'unknown',
    message: String(error?.message || error || '无法检测朱雀登录状态')
  }));
  return await apiFetch('/api/browser-agent/heartbeat', {
    method: 'POST',
    token,
    body: { agent_id: agentId, status: 'online', active_job_id: activeJobId, metadata: { zhuque: zhuqueStatus } }
  });
}

async function syncZhuqueStatus({ focus = false, remainingUses } = {}) {
  let zhuqueStatus = await getZhuqueSessionStatus({ focus });
  const resultRemaining = ZHUQUE_QUOTA.parseRemainingUses(remainingUses);
  const pageRemaining = ZHUQUE_QUOTA.extractRemainingUses(zhuqueStatus);
  if (resultRemaining !== undefined && pageRemaining === undefined) {
    zhuqueStatus = { ...zhuqueStatus, remaining_uses: resultRemaining };
  }
  await heartbeat(null, zhuqueStatus);
  return { ok: true, zhuque: zhuqueStatus };
}

async function findOrCreateZhuqueTab() {
  const tabs = await chrome.tabs.query({ url: 'https://matrix.tencent.com/*' });
  const existing = tabs.find((tab) => tab.url && tab.url.includes('/ai-detect')) || tabs[0];
  if (existing?.id) {
    const alreadyOnDetectPage = Boolean(existing.url && existing.url.includes('/ai-detect'));
    await chrome.tabs.update(existing.id, alreadyOnDetectPage ? { active: true } : { active: true, url: MATRIX_URL });
    if (existing.windowId !== undefined) {
      await chrome.windows.update(existing.windowId, { focused: true }).catch(() => undefined);
    }
    return existing.id;
  }
  const tab = await chrome.tabs.create({ url: MATRIX_URL, active: true });
  return tab.id;
}

async function waitForTabReady(tabId, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const tab = await chrome.tabs.get(tabId).catch(() => null);
    if (tab?.status === 'complete') {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

async function executeZhuqueJob(job) {
  let tabId = null;
  try {
    await heartbeat(job.job_id);
    await apiFetch(`/api/browser-agent/jobs/${job.job_id}/progress`, {
      method: 'POST',
      body: {
        status: 'running',
        message: '正在打开本机朱雀页面',
        progress: 0.05,
        metadata: { url: MATRIX_URL }
      }
    });
    tabId = await findOrCreateZhuqueTab();
    await waitForTabReady(tabId);
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['zhuque-quota.js', 'injected-zhuque.js'],
      world: 'MAIN'
    }).catch(() => undefined);
    let response = null;
    let detectionStarted = false;
    const deadline = Date.now() + Math.max(30000, Number(job.timeout_seconds || 180) * 1000);
    while (Date.now() < deadline) {
      response = await chrome.tabs.sendMessage(tabId, {
        type: 'GANKAIGC_ZHUQUE_DETECT',
        job: ZHUQUE_JOB_CONTROL.withResumeState(job, detectionStarted)
      });
      if (response?.manual_required) {
        detectionStarted = ZHUQUE_JOB_CONTROL.mergeDetectionStarted(detectionStarted, response);
        await apiFetch(`/api/browser-agent/jobs/${job.job_id}/progress`, {
          method: 'POST',
          body: {
            status: 'manual_required',
            message: response.message || '请在本机朱雀页面完成验证码/登录验证',
            progress: 0.5,
            metadata: {
              ...(response.metadata || {}),
              detection_started: detectionStarted
            }
          }
        });
        await new Promise((resolve) => setTimeout(resolve, 5000));
        continue;
      }
      break;
    }
    if (!response?.success) {
      await apiFetch(`/api/browser-agent/jobs/${job.job_id}/fail`, {
        method: 'POST',
        body: {
          error_code: response?.error_code || 'zhuque_browser_agent_failed',
          message: response?.message || '本机浏览器朱雀检测失败',
          retryable: response?.retryable !== false
        }
      });
      return;
    }
    await apiFetch(`/api/browser-agent/jobs/${job.job_id}/complete`, {
      method: 'POST',
      body: { result: response.result }
    });
    await syncZhuqueStatus({
      remainingUses: ZHUQUE_QUOTA.extractRemainingUses(response.result)
    }).catch((error) => console.warn('[GankAIGC Browser Agent] sync Zhuque status after job failed:', error));
  } finally {
    if (tabId !== null) {
      await chrome.tabs.sendMessage(tabId, {
        type: 'GANKAIGC_ZHUQUE_JOB_CLEANUP',
        job_id: job.job_id
      }).catch(() => undefined);
    }
  }
}

async function pollJobsOnce() {
  if (polling) return;
  polling = true;
  try {
    const state = await getState();
    const token = state[STORAGE_KEYS.agentToken];
    const agentId = state[STORAGE_KEYS.agentId];
    if (!token || !agentId) return;
    const payload = await apiFetch('/api/browser-agent/jobs/claim', {
      method: 'POST',
      token,
      body: { agent_id: agentId, wait_seconds: 20 }
    });
    if (payload.job) {
      await executeZhuqueJob(payload.job);
    }
  } catch (error) {
    console.warn('[GankAIGC Browser Agent] poll failed:', error);
  } finally {
    polling = false;
  }
}

async function ensureAlarms() {
  await chrome.alarms.create('gankaigc-heartbeat', {
    periodInMinutes: CHROME_MIN_ALARM_PERIOD_MINUTES
  });
  await chrome.alarms.create('gankaigc-poll-jobs', {
    periodInMinutes: CHROME_MIN_ALARM_PERIOD_MINUTES
  });
}

async function startBackgroundLoops() {
  await ensureAlarms();
  // Do not wait up to 30 seconds for the first alarm after install, reload, or
  // Chrome startup. A direct first claim also makes alarm failures visible in
  // the service-worker console instead of silently presenting as "online".
  await Promise.allSettled([heartbeat(), pollJobsOnce()]);
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'gankaigc-heartbeat') {
    heartbeat().catch((error) => console.warn('[GankAIGC Browser Agent] heartbeat failed:', error));
  }
  if (alarm.name === 'gankaigc-poll-jobs') {
    pollJobsOnce();
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message?.type === 'CLAIM_PAIRING') {
      return await claimPairing(message.payload || {});
    }
    if (message?.type === 'GET_STATUS') {
      const state = await getState();
      return {
        serverUrl: state[STORAGE_KEYS.serverUrl] || DEFAULT_SERVER_URL,
        pairingCode: state[STORAGE_KEYS.pairingCodeDraft] || '',
        agentName: state[STORAGE_KEYS.agentName] || DEFAULT_AGENT_NAME,
        agentId: state[STORAGE_KEYS.agentId] || '',
        paired: Boolean(state[STORAGE_KEYS.agentToken]),
        extensionVersion: EXTENSION_VERSION,
        zhuque: await getZhuqueSessionStatus().catch(() => null)
      };
    }
    if (message?.type === 'SAVE_POPUP_DRAFT') {
      const payload = message.payload || {};
      await setState({
        [STORAGE_KEYS.serverUrl]: normalizeServerUrl(payload.serverUrl || DEFAULT_SERVER_URL),
        [STORAGE_KEYS.pairingCodeDraft]: payload.pairingCode || '',
        [STORAGE_KEYS.agentName]: payload.agentName || DEFAULT_AGENT_NAME
      });
      return { ok: true };
    }
    if (message?.type === 'OPEN_ZHUQUE_PAGE') {
      const tabId = await findOrCreateZhuqueTab();
      await waitForTabReady(tabId);
      return { ok: true, tabId };
    }
    if (message?.type === 'SYNC_ZHUQUE_STATUS') {
      return await syncZhuqueStatus(message.payload || {});
    }
    if (message?.type === 'FORGET_AGENT') {
      await chrome.storage.local.remove(Object.values(STORAGE_KEYS));
      return { ok: true };
    }
    return { ok: false, message: 'unknown message' };
  })().then(sendResponse).catch((error) => sendResponse({ ok: false, message: String(error.message || error) }));
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  startBackgroundLoops().catch((error) => {
    console.warn('[GankAIGC Browser Agent] background startup failed:', error);
  });
});

chrome.runtime.onStartup.addListener(() => {
  startBackgroundLoops().catch((error) => {
    console.warn('[GankAIGC Browser Agent] background startup failed:', error);
  });
});

startBackgroundLoops().catch((error) => {
  console.warn('[GankAIGC Browser Agent] background startup failed:', error);
});
