const test = require('node:test');
const assert = require('node:assert/strict');

const {
  loginBlocksDetection,
  mergeDetectionStarted,
  resultFingerprint,
  shouldAcceptObservedResult,
  shouldResumeExistingDetection,
  withResumeState,
} = require('../zhuque-job.js');

test('allows anonymous Zhuque detection when editor controls exist', () => {
  assert.equal(loginBlocksDetection({
    loginVisible: true,
    hasInput: true,
    hasDetectButton: true,
    detectButtonDisabled: true,
  }), false);
  assert.equal(loginBlocksDetection({
    loginVisible: true,
    hasInput: false,
    hasDetectButton: false,
    detectButtonDisabled: false,
  }), true);
});

test('manual verification resumes an already submitted job without another click', () => {
  const job = { job_id: 'job-1', text: 'paper' };
  const started = mergeDetectionStarted(false, { detection_started: true });
  assert.equal(started, true);
  assert.deepEqual(withResumeState(job, started), {
    job_id: 'job-1',
    text: 'paper',
    resume_existing_detection: true,
  });
  assert.equal(job.resume_existing_detection, undefined);
  assert.equal(shouldResumeExistingDetection(job, { detectionStarted: true }), true);
  assert.equal(shouldResumeExistingDetection(job, { detectionStarted: false }), false);
  assert.equal(shouldResumeExistingDetection({ ...job, resume_existing_detection: true }, null), true);
});

test('rejects stale pre-click snapshots until a live event, change, or full busy cycle', () => {
  const stale = { rate: 42, labels_ratio: { 0: 0.42, 1: 0.58, 2: 0 }, segment_labels: [] };
  const staleAfterQuotaRefresh = { ...stale, remaining_uses: 2, raw_payload: { remainingUses: 2 } };
  const current = { rate: 18, labels_ratio: { 0: 0.18, 1: 0.82, 2: 0 }, segment_labels: [] };
  const baselineFingerprints = [resultFingerprint(stale)];

  assert.equal(shouldAcceptObservedResult({ candidate: stale, baselineFingerprints }), false);
  assert.equal(resultFingerprint(staleAfterQuotaRefresh), resultFingerprint(stale));
  assert.equal(shouldAcceptObservedResult({ candidate: staleAfterQuotaRefresh, baselineFingerprints }), false);
  assert.equal(shouldAcceptObservedResult({ candidate: current, baselineFingerprints }), true);
  assert.equal(shouldAcceptObservedResult({
    candidate: stale,
    baselineFingerprints,
    fromLiveEvent: true,
  }), true);
  assert.equal(shouldAcceptObservedResult({
    candidate: stale,
    baselineFingerprints,
    resuming: true,
  }), false);
  assert.equal(shouldAcceptObservedResult({
    candidate: stale,
    baselineFingerprints,
    sawBusy: true,
    completedBusyCycle: false,
  }), false);
  assert.equal(shouldAcceptObservedResult({
    candidate: stale,
    baselineFingerprints,
    completedBusyCycle: true,
  }), true);
});
