const GANKAIGC_RESULT_EVENT = 'GANKAIGC_ZHUQUE_RESULT';
const GANKAIGC_STATUS_SNAPSHOT_REQUEST = 'GANKAIGC_ZHUQUE_STATUS_SNAPSHOT_REQUEST';
const GANKAIGC_STATUS_SNAPSHOT_RESPONSE = 'GANKAIGC_ZHUQUE_STATUS_SNAPSHOT_RESPONSE';
const ZHUQUE_QUOTA = globalThis.GankAIGCZhuqueQuota;
const ZHUQUE_JOB_CONTROL = globalThis.GankAIGCZhuqueJobControl;
let lastObservedRemainingUses;
let lastObservedUserName = '';
const activeDetectionJobs = new Map();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function visible(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
}

function visibleInViewport(el) {
  if (!visible(el)) return false;
  const rect = el.getBoundingClientRect();
  const vw = window.innerWidth || document.documentElement.clientWidth;
  const vh = window.innerHeight || document.documentElement.clientHeight;
  return rect.width >= 20 && rect.height >= 20 && rect.bottom > 0 && rect.right > 0 && rect.top < vh && rect.left < vw;
}

function safeJsonParse(value) {
  try {
    return JSON.parse(value);
  } catch (error) {
    return null;
  }
}

function findStringInObject(value, depth = 0) {
  if (!value || depth > 4) return '';
  if (typeof value === 'string') {
    const text = value.trim();
    return text.length >= 1 && text.length <= 40 ? text : '';
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findStringInObject(item, depth + 1);
      if (found) return found;
    }
    return '';
  }
  if (typeof value === 'object') {
    const preferredKeys = ['nickName', 'nickname', 'userName', 'username', 'name', 'displayName'];
    for (const key of preferredKeys) {
      const found = findStringInObject(value[key], depth + 1);
      if (found) return found;
    }
    for (const item of Object.values(value)) {
      const found = findStringInObject(item, depth + 1);
      if (found) return found;
    }
  }
  return '';
}

function normalizeAccountName(text) {
  const value = String(text || '').trim().replace(/\s+/g, ' ');
  if (!value || value.length > 40) return '';
  if (/登录|扫码|注册|退出|检测|上传|清空|示例|人工|疑似|AI特征|Benchmark|产品|腾讯朱雀/i.test(value)) return '';
  if (/^https?:\/\//i.test(value) || /^[A-Za-z0-9_-]{24,}$/.test(value)) return '';
  return value;
}

function extractRemainingUsesFromPage() {
  const candidateTexts = [];
  const selectors = [
    '.submit-btn',
    '.detect-btn',
    '.quota',
    '.quota-text',
    '[class*="quota"]',
    '[class*="remain"]',
    '[class*="usage"]',
    'button'
  ];
  selectors.forEach((selector) => {
    document.querySelectorAll(selector).forEach((node) => {
      const text = String(node.textContent || '').replace(/\s+/g, ' ').trim();
      if (text) candidateTexts.push(text);
    });
  });
  const pageLines = String(document.body?.innerText || document.body?.textContent || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line && line.length <= 120);
  const remaining = ZHUQUE_QUOTA?.extractRemainingUses([...candidateTexts, ...pageLines]);
  return remaining === undefined ? -1 : remaining;
}

function rememberRemainingUses(value) {
  const remaining = ZHUQUE_QUOTA?.extractRemainingUses(value);
  if (remaining !== undefined) {
    lastObservedRemainingUses = remaining;
  }
  return remaining;
}

function extractZhuqueAccountName() {
  const storageKeys = [...Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index))]
    .filter(Boolean)
    .filter((key) => /user|account|profile|login|auth|wechat|wx|matrix/i.test(key));
  for (const key of storageKeys) {
    const parsed = safeJsonParse(localStorage.getItem(key));
    const found = normalizeAccountName(findStringInObject(parsed));
    if (found) return found;
  }
  const selectors = [
    '[class*="user"]',
    '[class*="avatar"]',
    '[class*="account"]',
    '[class*="profile"]',
    '[class*="nickname"]',
    '[aria-label*="用户"]',
    '[title*="用户"]'
  ];
  for (const selector of selectors) {
    const found = [...document.querySelectorAll(selector)]
      .filter(visible)
      .map((el) => normalizeAccountName(el.getAttribute('title') || el.getAttribute('aria-label') || el.textContent || ''))
      .find(Boolean);
    if (found) return found;
  }
  return '';
}

function detectZhuqueSessionStatus(injectedStatus = null) {
  const manual = detectCaptchaOrLogin();
  if (manual?.error_code === 'zhuque_not_logged_in') {
    lastObservedRemainingUses = undefined;
    lastObservedUserName = '';
    return {
      page_found: true,
      logged_in: false,
      connected: false,
      has_token: false,
      status: 'not_logged_in',
      user_name: '',
      message: '朱雀页面未登录'
    };
  }
  const userName = extractZhuqueAccountName();
  if (lastObservedUserName && userName && lastObservedUserName !== userName) {
    lastObservedRemainingUses = undefined;
  }
  if (userName) {
    lastObservedUserName = userName;
  }
  const injectedRemaining = rememberRemainingUses(injectedStatus);
  const pageRemaining = extractRemainingUsesFromPage();
  if (injectedRemaining === undefined && pageRemaining >= 0) {
    rememberRemainingUses(pageRemaining);
  }
  const remainingUses = lastObservedRemainingUses ?? -1;
  if (userName) {
    return {
      page_found: true,
      logged_in: true,
      connected: true,
      has_token: true,
      status: 'logged_in',
      user_name: userName,
      remaining_uses: remainingUses,
      message: `朱雀已登录：${userName}`
    };
  }
  const input = findInput();
  const detectButton = findDetectButton();
  const buttonEnabled = Boolean(
    detectButton
    && remainingUses !== 0
    && (!detectionControlDisabled(detectButton) || input)
  );
  return {
    page_found: Boolean(input || detectButton || document.body),
    logged_in: false,
    connected: false,
    has_token: false,
    status: input || detectButton ? 'page_ready' : 'unknown',
    user_name: '',
    remaining_uses: remainingUses,
    button_enabled: buttonEnabled,
    message: input && buttonEnabled ? '朱雀游客检测可用；也可登录朱雀账号使用账号次数' : '暂未识别朱雀页面状态'
  };
}

function detectionControlDisabled(control) {
  return Boolean(
    control && (
      control.disabled
      || control.classList?.contains('is-disabled')
      || control.getAttribute?.('aria-disabled') === 'true'
    )
  );
}

function detectCaptchaOrLogin() {
  const captchaFrames = [...document.querySelectorAll('iframe[src*="captcha"], iframe[src*="tcaptcha"], iframe[src*="gtimg"]')]
    .filter(visibleInViewport);
  const visibleCaptchaText = [...document.querySelectorAll('button, a, span, div, p')]
    .filter(visibleInViewport)
    .map((el) => (el.textContent || '').trim())
    .filter(Boolean)
    .some((text) => /请完成安全验证|拖动.*滑块|滑块验证|选择.*相似|Choose all similar|Verification Code/i.test(text));
  const hasCaptcha = captchaFrames.length > 0 || visibleCaptchaText;
  if (hasCaptcha) {
    return { manual_required: true, error_code: 'zhuque_captcha_required', message: '请在本机朱雀页面完成验证码' };
  }
  const loginVisible = [...document.querySelectorAll('button, a, span, div')]
    .filter(visible)
    .some((el) => /^(登录|扫码登录|微信登录|Login|Sign in)$/i.test((el.textContent || '').trim()));
  const input = findInput();
  const detectButton = findDetectButton();
  if (ZHUQUE_JOB_CONTROL.loginBlocksDetection({
    loginVisible,
    hasInput: Boolean(input),
    hasDetectButton: Boolean(detectButton),
    detectButtonDisabled: detectionControlDisabled(detectButton),
  })) {
    return { manual_required: true, error_code: 'zhuque_not_logged_in', message: '请先在本机朱雀页面登录朱雀' };
  }
  return null;
}

function findInput() {
  const selectors = [
    'textarea',
    '[contenteditable="true"]',
    '.el-textarea__inner',
    '.input textarea',
    '.detect-input textarea'
  ];
  for (const selector of selectors) {
    const el = [...document.querySelectorAll(selector)].find(visible);
    if (el) return el;
  }
  return null;
}

function setInputText(el, text) {
  el.focus();
  if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
    el.value = text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return;
  }
  el.textContent = text;
  el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
}

function findClearButton() {
  return [...document.querySelectorAll('button, a')]
    .filter(visible)
    .find((el) => /清空|Clear/i.test(el.textContent || ''));
}

function findDetectButton() {
  return [...document.querySelectorAll('button, a')]
    .filter(visible)
    .find((el) => /立即检测|开始检测|重新检测|Detect|Check/i.test(el.textContent || ''));
}

function parsePercent(text) {
  const match = String(text || '').match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? Number(match[1]) : null;
}

function domResultFallback() {
  const resultNode = [...document.querySelectorAll('.card-right, .rst')]
    .filter(visible)
    .find((el) => {
      const text = el.innerText || el.textContent || '';
      if (/检测中|立即检测|上传|清空|示例一|示例二|示例三|示例四/.test(text)) return false;
      return /人工特征|AI特征|疑似AI|人工创作|AI生成|疑似/.test(text);
    });
  if (!resultNode) return null;
  const resultText = resultNode.innerText || resultNode.textContent || '';
  const percentages = ZHUQUE_JOB_CONTROL.resultPercentagesFromText(resultText);
  if (percentages) {
    const { human, suspicious, ai } = percentages;
    return {
      success: true,
      source: 'browser_agent_dom',
      // 朱雀右侧图例顺序：人工特征、疑似AI、AI特征；GankAIGC：AI、人工、疑似。
      rate: ai,
      risk_rate: Math.max(ai, suspicious),
      rate_label: resultText.split(/\n/).find((line) => /人工创作|AI生成|疑似|人工特征|AI特征/.test(line)) || '朱雀页面检测结果',
      labels_ratio: { '0': ai / 100, '1': human / 100, '2': suspicious / 100 },
      segment_labels: [],
      raw_payload: { rate: ai, labelsRatio: { '0': human / 100, '1': ai / 100, '2': suspicious / 100 }, result_text: resultText.slice(0, 500) }
    };
  }
  return null;
}

function detectionBusy() {
  const pageText = String(document.body?.innerText || document.body?.textContent || '');
  if (/检测中|正在检测|分析中|Detecting|Analyzing/i.test(pageText)) return true;
  return detectionControlDisabled(findDetectButton());
}

function normalizeScore(value) {
  const score = Number(value);
  if (!Number.isFinite(score)) return null;
  const percent = score <= 1 ? score * 100 : score;
  if (percent < 0 || percent > 100) return null;
  return percent;
}

function validSegmentLabels(segmentLabels) {
  if (!Array.isArray(segmentLabels)) return [];
  return segmentLabels.filter((item) => {
    const label = Number(item?.label);
    const span = Array.isArray(item?.position) ? Number(item.position[1]) : 0;
    return [0, 1, 2].includes(label) && Number.isFinite(span) && span > 0 && typeof item?.text === 'string' && item.text.trim().length > 0;
  });
}

function ratioFromSegmentLabels(segmentLabels) {
  const validLabels = validSegmentLabels(segmentLabels);
  if (!validLabels.length) return null;
  const raw = { 0: 0, 1: 0, 2: 0 };
  for (const item of validLabels) {
    const label = Number(item.label);
    const span = Number(item.position[1]);
    raw[label] += span;
  }
  const total = raw[0] + raw[1] + raw[2];
  if (!total) return null;
  return {
    // 朱雀当前页面：0=人工, 1=AI, 2=疑似；GankAIGC：0=AI, 1=人工, 2=疑似。
    '0': raw[1] / total,
    '1': raw[0] / total,
    '2': raw[2] / total
  };
}

function terminalPayloadFromInjected(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const data = payload.data || payload.result || payload.value || payload;
  if (!data || typeof data !== 'object') return null;
  const segmentLabels = validSegmentLabels(data.segment_labels || data.segmentLabels || []);
  const segmentRatio = ratioFromSegmentLabels(segmentLabels);
  const rawLabels = data.labels_ratio || data.labelsRatio || null;
  const aiRate = normalizeScore(data.rate ?? data.confidence ?? data.ai_generated);
  const remainingUses = rememberRemainingUses([data, payload]);
  const labelsRatio = segmentRatio || rawLabels || (aiRate !== null ? { '0': aiRate / 100, '1': Math.max(0, 1 - aiRate / 100), '2': 0 } : {});
  const hasRate = aiRate !== null || Object.keys(labelsRatio).length > 0 || segmentLabels.length > 0;
  if (!hasRate) return null;
  const normalizedRate = aiRate !== null ? aiRate : (labelsRatio['0'] || 0) * 100;
  const normalized = {
    success: true,
    source: 'browser_agent_page',
    raw_payload: data,
    rate: Number(normalizedRate.toFixed(2)),
    risk_rate: Number(Math.max(labelsRatio['0'] || 0, labelsRatio['2'] || 0) * 100).toFixed ? Number((Math.max(labelsRatio['0'] || 0, labelsRatio['2'] || 0) * 100).toFixed(2)) : normalizedRate,
    rate_label: data.rateLabel || data.rate_label || '朱雀页面检测结果',
    labels_ratio: labelsRatio,
    segment_labels: segmentLabels
  };
  if (remainingUses !== undefined) {
    normalized.remaining_uses = remainingUses;
  }
  return normalized;
}

function requestInjectedStatusSnapshot() {
  return new Promise((resolve) => {
    const requestId = `status-${Date.now()}-${Math.random()}`;
    const timer = setTimeout(() => {
      window.removeEventListener('message', listener);
      resolve(null);
    }, 1200);
    function listener(event) {
      if (event.source !== window || event.data?.type !== GANKAIGC_STATUS_SNAPSHOT_RESPONSE) return;
      if (event.data.requestId !== requestId) return;
      clearTimeout(timer);
      window.removeEventListener('message', listener);
      resolve(event.data.status || null);
    }
    window.addEventListener('message', listener);
    window.postMessage({ type: GANKAIGC_STATUS_SNAPSHOT_REQUEST, requestId }, '*');
  });
}

function requestInjectedSnapshot() {
  return new Promise((resolve) => {
    const requestId = `${Date.now()}-${Math.random()}`;
    const timer = setTimeout(() => {
      window.removeEventListener('message', listener);
      resolve(null);
    }, 1000);
    function listener(event) {
      if (event.source !== window || event.data?.type !== 'GANKAIGC_ZHUQUE_SNAPSHOT_RESPONSE') return;
      if (event.data.requestId !== requestId) return;
      clearTimeout(timer);
      window.removeEventListener('message', listener);
      const payload = (event.data.payloads || [])
        .map((item) => terminalPayloadFromInjected(item.value || item))
        .find(Boolean);
      resolve(payload || null);
    }
    window.addEventListener('message', listener);
    window.postMessage({ type: 'GANKAIGC_ZHUQUE_SNAPSHOT_REQUEST', requestId }, '*');
  });
}

window.addEventListener('message', (event) => {
  if (event.source !== window || event.data?.type !== GANKAIGC_RESULT_EVENT) return;
  rememberRemainingUses(event.data.payload);
});

async function collectResultBaseline() {
  const fingerprints = new Set();
  const snapshotResult = await requestInjectedSnapshot();
  const domResult = domResultFallback();
  [snapshotResult, domResult].filter(Boolean).forEach((result) => {
    const fingerprint = ZHUQUE_JOB_CONTROL.resultFingerprint(result);
    if (fingerprint) fingerprints.add(fingerprint);
  });
  return [...fingerprints];
}

async function waitForResult(timeoutMs, detectionState) {
  let networkResult = null;
  const listener = (event) => {
    if (event.source !== window || event.data?.type !== GANKAIGC_RESULT_EVENT) return;
    networkResult = terminalPayloadFromInjected(event.data.payload);
  };
  window.addEventListener('message', listener);
  try {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (networkResult && ZHUQUE_JOB_CONTROL.shouldAcceptObservedResult({
        candidate: networkResult,
        baselineFingerprints: detectionState.baselineFingerprints,
        fromLiveEvent: true,
      })) return networkResult;
      const busyNow = detectionBusy();
      if (detectionState.sawBusy && !busyNow) {
        detectionState.completedBusyCycle = true;
      }
      if (busyNow) {
        detectionState.sawBusy = true;
      }
      const snapshotResult = await requestInjectedSnapshot();
      if (ZHUQUE_JOB_CONTROL.shouldAcceptObservedResult({
        candidate: snapshotResult,
        baselineFingerprints: detectionState.baselineFingerprints,
        completedBusyCycle: detectionState.completedBusyCycle,
      })) return snapshotResult;
      const domResult = domResultFallback();
      if (ZHUQUE_JOB_CONTROL.shouldAcceptObservedResult({
        candidate: domResult,
        baselineFingerprints: detectionState.baselineFingerprints,
        completedBusyCycle: detectionState.completedBusyCycle,
        resultClearedAfterBaseline: detectionState.resultClearedAfterBaseline,
      })) return domResult;
      const manual = detectCaptchaOrLogin();
      if (manual) return manual;
      await sleep(1000);
    }
    return { success: false, error_code: 'zhuque_browser_agent_timeout', message: '等待朱雀检测结果超时', retryable: true };
  } finally {
    window.removeEventListener('message', listener);
  }
}

async function runZhuqueDetect(job) {
  await sleep(1000);
  const jobId = String(job.job_id || '').trim();
  let detectionState = jobId ? activeDetectionJobs.get(jobId) : null;
  const resuming = ZHUQUE_JOB_CONTROL.shouldResumeExistingDetection(job, detectionState);
  const manualBefore = detectCaptchaOrLogin();
  if (manualBefore) return { ...manualBefore, detection_started: resuming };

  const timeoutMs = Math.max(30000, Number(job.timeout_seconds || 180) * 1000);
  if (resuming) {
    if (!detectionState) {
      detectionState = {
        baselineFingerprints: await collectResultBaseline(),
        detectionStarted: true,
        sawBusy: false,
        completedBusyCycle: false,
        resultClearedAfterBaseline: false,
      };
      if (jobId) activeDetectionJobs.set(jobId, detectionState);
    }
    const resumedResult = await waitForResult(timeoutMs, detectionState);
    if (!resumedResult?.manual_required && jobId) activeDetectionJobs.delete(jobId);
    return { ...resumedResult, detection_started: true };
  }

  const baselineFingerprints = await collectResultBaseline();
  detectionState = {
    baselineFingerprints,
    detectionStarted: false,
    sawBusy: false,
    completedBusyCycle: false,
    resultClearedAfterBaseline: false,
  };
  if (jobId) activeDetectionJobs.set(jobId, detectionState);

  const clearButton = findClearButton();
  if (clearButton) {
    clearButton.click();
    await sleep(300);
    detectionState.resultClearedAfterBaseline = Boolean(
      baselineFingerprints.length > 0 && !domResultFallback()
    );
  }

  const input = findInput();
  if (!input) {
    if (jobId) activeDetectionJobs.delete(jobId);
    return { success: false, error_code: 'zhuque_input_not_found', message: '未找到朱雀检测输入框', retryable: true };
  }
  setInputText(input, job.text || '');
  await sleep(500);

  const detectButton = findDetectButton();
  if (!detectButton) {
    if (jobId) activeDetectionJobs.delete(jobId);
    return { success: false, error_code: 'zhuque_detect_button_not_found', message: '未找到朱雀立即检测按钮', retryable: true };
  }
  if (detectionControlDisabled(detectButton)) {
    if (jobId) activeDetectionJobs.delete(jobId);
    return {
      success: false,
      error_code: 'zhuque_detect_button_disabled',
      message: '朱雀检测按钮当前不可用，请确认游客/账号剩余次数或完成页面提示',
      retryable: true,
      detection_started: false,
    };
  }
  detectButton.click();
  detectionState.detectionStarted = true;

  const result = await waitForResult(timeoutMs, detectionState);
  if (!result?.manual_required && jobId) activeDetectionJobs.delete(jobId);
  return { ...result, detection_started: true };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'GANKAIGC_ZHUQUE_STATUS') {
    requestInjectedStatusSnapshot()
      .then((status) => sendResponse({ success: true, status: detectZhuqueSessionStatus(status) }))
      .catch(() => sendResponse({ success: true, status: detectZhuqueSessionStatus() }));
    return true;
  }
  if (message?.type === 'GANKAIGC_ZHUQUE_JOB_CLEANUP') {
    const jobId = String(message.job_id || '').trim();
    if (jobId) activeDetectionJobs.delete(jobId);
    sendResponse({ success: true });
    return false;
  }
  if (message?.type !== 'GANKAIGC_ZHUQUE_DETECT') return false;
  runZhuqueDetect(message.job || {})
    .then((result) => {
      if (result?.manual_required) {
        sendResponse({
          success: false,
          manual_required: true,
          detection_started: Boolean(result.detection_started),
          error_code: result.error_code,
          message: result.message,
          metadata: result,
        });
        return;
      }
      if (!result?.success) {
        sendResponse(result || { success: false, message: '朱雀检测失败' });
        return;
      }
      sendResponse({ success: true, result });
    })
    .catch((error) => sendResponse({ success: false, error_code: 'zhuque_browser_agent_exception', message: String(error.message || error), retryable: true }));
  return true;
});
