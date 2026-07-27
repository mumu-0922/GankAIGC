(function exposeZhuqueJobControl(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.GankAIGCZhuqueJobControl = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, () => {
  function loginBlocksDetection({ loginVisible, hasInput, hasDetectButton, detectButtonDisabled }) {
    if (!loginVisible) return false;
    // Zhuque disables the detect button while the editor is empty. Presence of
    // the real editor + detect control is enough to prove anonymous mode exists;
    // button state is checked again after the job text is inserted.
    void detectButtonDisabled;
    return !(hasInput && hasDetectButton);
  }

  function withResumeState(job, detectionStarted) {
    return {
      ...(job || {}),
      resume_existing_detection: Boolean(detectionStarted),
    };
  }

  function mergeDetectionStarted(current, response) {
    return Boolean(current || response?.detection_started);
  }

  function shouldResumeExistingDetection(job, detectionState) {
    return Boolean(job?.resume_existing_detection || detectionState?.detectionStarted);
  }

  function stableValue(value, depth = 0, seen = new Set()) {
    if (value === null || value === undefined || typeof value !== 'object') {
      return value;
    }
    if (depth > 6 || seen.has(value)) {
      return undefined;
    }
    seen.add(value);
    if (Array.isArray(value)) {
      return value.map((item) => stableValue(item, depth + 1, seen));
    }
    const normalized = {};
    Object.keys(value).sort().forEach((key) => {
      if (['source', 'success', 'message', 'rate_label'].includes(key)) return;
      const nested = stableValue(value[key], depth + 1, seen);
      if (nested !== undefined) normalized[key] = nested;
    });
    return normalized;
  }

  function resultFingerprint(result) {
    if (!result || typeof result !== 'object') return '';
    return JSON.stringify(stableValue({
      rate: result.rate,
      risk_rate: result.risk_rate,
      labels_ratio: result.labels_ratio,
      segment_labels: result.segment_labels,
    }));
  }

  function resultPercentagesFromText(resultText) {
    const percentages = [...String(resultText || '').matchAll(/(\d+(?:\.\d+)?)\s*%/g)]
      .map((match) => Number(match[1]))
      .filter((value) => Number.isFinite(value) && value >= 0 && value <= 100);
    if (percentages.length >= 3) {
      return {
        human: percentages[0],
        suspicious: percentages[1],
        ai: percentages[2],
      };
    }
    if (percentages.length === 2) {
      // Zhuque omits the zero-valued suspicious class on some result pages and
      // renders only human + AI percentages, in that order.
      return {
        human: percentages[0],
        suspicious: 0,
        ai: percentages[1],
      };
    }
    return null;
  }

  function shouldAcceptObservedResult({
    candidate,
    baselineFingerprints = [],
    fromLiveEvent = false,
    completedBusyCycle = false,
    resultClearedAfterBaseline = false,
  }) {
    if (!candidate) return false;
    if (fromLiveEvent || completedBusyCycle || resultClearedAfterBaseline) return true;
    const fingerprint = resultFingerprint(candidate);
    if (!fingerprint) return false;
    const baselines = new Set((baselineFingerprints || []).filter(Boolean));
    return baselines.size === 0 || !baselines.has(fingerprint);
  }

  return {
    loginBlocksDetection,
    mergeDetectionStarted,
    resultFingerprint,
    resultPercentagesFromText,
    shouldAcceptObservedResult,
    shouldResumeExistingDetection,
    withResumeState,
  };
});
