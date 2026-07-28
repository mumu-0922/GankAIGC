(() => {
  const INJECTED_VERSION = '0.1.10';
  const previousVersion = window.__GANKAIGC_ZHUQUE_INJECTED__;
  if (previousVersion === INJECTED_VERSION) return;
  window.__GANKAIGC_ZHUQUE_INJECTED__ = INJECTED_VERSION;
  const shouldInstrumentNetwork = !previousVersion;
  const ZHUQUE_QUOTA = globalThis.GankAIGCZhuqueQuota;
  const RESULT_EVENT = 'GANKAIGC_ZHUQUE_RESULT';
  const SNAPSHOT_REQUEST = 'GANKAIGC_ZHUQUE_SNAPSHOT_REQUEST';
  const SNAPSHOT_RESPONSE = 'GANKAIGC_ZHUQUE_SNAPSHOT_RESPONSE';
  const STATUS_REQUEST = 'GANKAIGC_ZHUQUE_STATUS_SNAPSHOT_REQUEST';
  const STATUS_RESPONSE = 'GANKAIGC_ZHUQUE_STATUS_SNAPSHOT_RESPONSE';

  function postPayload(payload, source) {
    try {
      window.postMessage({ type: RESULT_EVENT, source, payload }, '*');
    } catch (_) {}
  }

  function maybeParseJson(value) {
    if (!value) return null;
    if (typeof value === 'object') return value;
    try { return JSON.parse(value); } catch (_) { return null; }
  }

  function looksLikeTerminal(payload) {
    const data = payload?.data || payload?.result || payload;
    if (!data || typeof data !== 'object') return false;
    if (data.rate !== undefined || data.confidence !== undefined || data.labels_ratio || data.labelsRatio) return true;
    if (Array.isArray(data.segment_labels) && data.segment_labels.length > 0) return true;
    if (Array.isArray(data.segmentLabels) && data.segmentLabels.length > 0) return true;
    return false;
  }

  function isValidSegmentLabel(item) {
    if (!item || typeof item !== 'object') return false;
    const label = Number(item.label);
    const position = item.position;
    const span = Array.isArray(position) && position.length >= 2 ? Number(position[1]) : 0;
    return [0, 1, 2].includes(label) && Number.isFinite(span) && span > 0 && typeof item.text === 'string' && item.text.trim().length > 0;
  }

  function cleanSegmentLabels(items) {
    if (!Array.isArray(items)) return undefined;
    const cleaned = items
      .filter(isValidSegmentLabel)
      .map((item) => ({
        text: item.text,
        label: Number(item.label),
        conf: item.conf,
        order: item.order,
        position: Array.isArray(item.position) ? item.position.slice(0, 2).map(Number) : item.position
      }));
    return cleaned.length > 0 ? cleaned : undefined;
  }

  function isSegmentLabelArray(value) {
    return Array.isArray(value) && value.some(isValidSegmentLabel);
  }

  function normalizeScore(value) {
    const score = Number(value);
    if (!Number.isFinite(score)) return undefined;
    const percent = score <= 1 ? score * 100 : score;
    if (percent < 0 || percent > 100) return undefined;
    return percent;
  }

  function cleanPayload(value) {
    if (!value || typeof value !== 'object') return null;
    const segmentLabels = cleanSegmentLabels(value.segment_labels || value.segmentLabels || value.segmentLabel);
    const remainingUses = ZHUQUE_QUOTA?.extractRemainingUses(value);
    const cleanValue = {
      confidence: normalizeScore(value.confidence),
      rate: normalizeScore(value.rate),
      ai_generated: normalizeScore(value.ai_generated),
      rateLabel: value.rateLabel,
      rate_label: value.rate_label,
      labels_ratio: value.labels_ratio,
      labelsRatio: value.labelsRatio,
      msg: value.msg,
      message: value.message,
      remaining_uses: remainingUses,
      segment_labels: segmentLabels
    };
    Object.keys(cleanValue).forEach((key) => cleanValue[key] === undefined && delete cleanValue[key]);
    const hasScore = cleanValue.confidence !== undefined || cleanValue.rate !== undefined || cleanValue.ai_generated !== undefined;
    const hasLabels = cleanValue.labels_ratio !== undefined || cleanValue.labelsRatio !== undefined;
    const hasSegments = Array.isArray(cleanValue.segment_labels) && cleanValue.segment_labels.length > 0;
    const hasQuota = cleanValue.remaining_uses !== undefined;
    return hasScore || hasLabels || hasSegments || hasQuota ? cleanValue : null;
  }

  function collectVuePayloads() {
    const payloads = [];
    const seenValues = new Set();
    const pushPayload = (value, source) => {
      const cleanValue = cleanPayload(value);
      if (!cleanValue) return;
      const fingerprint = JSON.stringify({
        rate: cleanValue.rate ?? cleanValue.confidence ?? cleanValue.ai_generated,
        labelsRatio: cleanValue.labels_ratio || cleanValue.labelsRatio,
        remainingUses: cleanValue.remaining_uses,
        segmentLen: cleanValue.segment_labels?.length || 0,
        first: cleanValue.segment_labels?.[0]?.position || null
      });
      if (seenValues.has(fingerprint)) return;
      seenValues.add(fingerprint);
      payloads.push({ source, value: cleanValue });
    };
    const walk = (obj, source, depth = 0, seen = new Set()) => {
      if (!obj || typeof obj !== 'object' || depth > 5 || seen.has(obj)) return;
      seen.add(obj);
      pushPayload(obj, source);
      for (const key of [
        'data', 'segmentLabel', 'segmentLabels', 'segment_labels', 'props', 'setupState',
        'ctx', '$props', '$data', '$parent', '$children'
      ]) {
        let value;
        try { value = obj[key]; } catch (_) { continue; }
        if (Array.isArray(value) && key !== 'segment_labels') {
          if (isSegmentLabelArray(value)) {
            pushPayload({ segment_labels: value }, `${source}.${key}`);
          } else {
            value.slice(0, 5).forEach((child, index) => walk(child, `${source}.${key}:${index}`, depth + 1, seen));
          }
        } else if (value && typeof value === 'object') {
          walk(value, `${source}.${key}`, depth + 1, seen);
        }
      }
    };
    document.querySelectorAll('*').forEach((node, index) => {
      if (node.__vue__) walk(node.__vue__, `vue:${index}`);
      if (node.__vueParentComponent) {
        walk(node.__vueParentComponent.props, `vue3:${index}.props`);
        walk(node.__vueParentComponent.setupState, `vue3:${index}.setupState`);
        walk(node.__vueParentComponent.ctx, `vue3:${index}.ctx`);
      }
    });
    return payloads.sort((left, right) => {
      const leftSegments = left.value.segment_labels?.length || 0;
      const rightSegments = right.value.segment_labels?.length || 0;
      const leftHasRatio = left.value.labels_ratio !== undefined || left.value.labelsRatio !== undefined;
      const rightHasRatio = right.value.labels_ratio !== undefined || right.value.labelsRatio !== undefined;
      const leftHasScore = left.value.rate !== undefined || left.value.confidence !== undefined || left.value.ai_generated !== undefined;
      const rightHasScore = right.value.rate !== undefined || right.value.confidence !== undefined || right.value.ai_generated !== undefined;
      return rightSegments - leftSegments || Number(rightHasRatio) - Number(leftHasRatio) || Number(rightHasScore) - Number(leftHasScore);
    });
  }

  function collectQuotaStatus() {
    const candidates = [];
    const pushCandidate = (value, source) => {
      const remainingUses = ZHUQUE_QUOTA?.extractRemainingUses(value);
      if (remainingUses === undefined) return;
      const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : '';
      if (!candidates.some((item) => item.remaining_uses === remainingUses && item.source === source)) {
        candidates.push({ remaining_uses: remainingUses, source, text });
      }
    };

    const allNodes = [...document.querySelectorAll('*')];
    allNodes.forEach((node, index) => {
      if (node.__vue__) pushCandidate(node.__vue__, `vue:${index}`);
      if (node.__vueParentComponent) {
        pushCandidate(node.__vueParentComponent.props, `vue3:${index}.props`);
        pushCandidate(node.__vueParentComponent.setupState, `vue3:${index}.setupState`);
        pushCandidate(node.__vueParentComponent.ctx, `vue3:${index}.ctx`);
      }
    });

    const quotaSelectors = [
      '.submit-btn',
      '.detect-btn',
      '.quota',
      '.quota-text',
      '[class*="quota"]',
      '[class*="remain"]',
      '[class*="usage"]'
    ];
    quotaSelectors.forEach((selector) => {
      document.querySelectorAll(selector).forEach((node) => {
        pushCandidate(node.textContent || '', selector);
      });
    });
    allNodes.forEach((node, index) => {
      const text = String(node.textContent || '').replace(/\s+/g, ' ').trim();
      if (text.length <= 120) pushCandidate(text, `node:${index}`);
    });

    const submitButton = document.querySelector('.submit-btn')
      || [...document.querySelectorAll('button')].find((button) => /Detect|检测/i.test(button.textContent || ''));
    const submitButtonText = String(submitButton?.textContent || '').replace(/\s+/g, ' ').trim();
    pushCandidate(submitButtonText, 'submitButtonText');
    const submitButtonVisible = Boolean(
      submitButton && (submitButton.offsetWidth || submitButton.offsetHeight || submitButton.getClientRects().length)
    );
    const submitButtonDisabled = Boolean(
      submitButton && (
        submitButton.disabled
        || submitButton.classList.contains('is-disabled')
        || submitButton.getAttribute('aria-disabled') === 'true'
      )
    );
    const selected = candidates[0];
    return {
      remaining_uses: selected?.remaining_uses ?? -1,
      quota_text: selected?.text || submitButtonText,
      quota_source: selected?.source || '',
      button_enabled: Boolean(submitButton && submitButtonVisible && !submitButtonDisabled),
      page_found: Boolean(document.body)
    };
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    const data = event.data || {};
    const requestId = data.requestId;
    if (data.type === SNAPSHOT_REQUEST) {
      const payloads = collectVuePayloads().slice(0, 8);
      window.postMessage({ type: SNAPSHOT_RESPONSE, requestId, payloads }, '*');
      return;
    }
    if (data.type === STATUS_REQUEST) {
      window.postMessage({ type: STATUS_RESPONSE, requestId, status: collectQuotaStatus() }, '*');
    }
  });

  const originalFetch = window.fetch;
  if (shouldInstrumentNetwork && typeof originalFetch === 'function') {
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      try {
        const url = String(args[0]?.url || args[0] || '');
        if (/\/user\/detect\/result|\/ai-detect|detect/i.test(url)) {
          response.clone().text().then((text) => {
            const payload = maybeParseJson(text);
            if (looksLikeTerminal(payload)) postPayload(payload, 'fetch');
          }).catch(() => undefined);
        }
      } catch (_) {}
      return response;
    };
  }

  const OriginalWebSocket = window.WebSocket;
  if (shouldInstrumentNetwork && typeof OriginalWebSocket === 'function') {
    window.WebSocket = function GankAigcObservedWebSocket(...args) {
      const ws = new OriginalWebSocket(...args);
      ws.addEventListener('message', (event) => {
        const payload = maybeParseJson(event.data);
        if (looksLikeTerminal(payload)) postPayload(payload, 'websocket');
      });
      return ws;
    };
    window.WebSocket.prototype = OriginalWebSocket.prototype;
    Object.assign(window.WebSocket, OriginalWebSocket);
  }
})();
