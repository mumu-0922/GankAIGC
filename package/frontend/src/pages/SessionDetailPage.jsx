import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  Download, FileText, GitCompare, ArrowLeft,
  CheckCircle, AlertCircle, Shield, Square, Activity,
  Search, RefreshCw, Database, ChevronDown, ChevronUp, Clock
} from 'lucide-react';
import { optimizationAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import { formatChinaDate } from '../utils/dateTime';

const STREAM_FLUSH_INTERVAL_MS = 100;
const STREAM_RECONNECT_DELAY_MS = 2000;
const ACTIVE_DETAIL_POLL_INTERVAL_MS = 5000;
const ZHUQUE_MANUAL_VERIFICATION_TEXT_MARKERS = [
  'zhuque_captcha_required',
  'manual_verification_required',
  '腾讯验证码',
  '验证码',
  'captcha',
  'tcaptcha',
  'Verification Code',
  'Choose all similar',
  '朱雀真实页面检测失败',
  '朱雀真实页面检测超时',
  '找不到文本输入框',
  '找不到检测按钮',
];

const messageNeedsZhuqueManualVerification = (message) => {
  const text = String(message || '');
  if (!text) {
    return false;
  }
  const lowerText = text.toLowerCase();
  return ZHUQUE_MANUAL_VERIFICATION_TEXT_MARKERS.some((marker) => lowerText.includes(marker.toLowerCase()));
};

const SessionDetailPage = () => {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [segments, setSegments] = useState([]);
  const [changes, setChanges] = useState([]);
  const [activeTab, setActiveTab] = useState('result');
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportFormat, setExportFormat] = useState('docx');
  const [resultViewMode, setResultViewMode] = useState('enhanced');
  const [zhuqueLiveEvents, setZhuqueLiveEvents] = useState([]);
  const [zhuqueStatus, setZhuqueStatus] = useState(null);
  const [collapsedZhuqueEventKeys, setCollapsedZhuqueEventKeys] = useState(() => new Set());
  const [isOpeningZhuqueVerification, setIsOpeningZhuqueVerification] = useState(false);
  const [isRetryingZhuqueAfterVerification, setIsRetryingZhuqueAfterVerification] = useState(false);
  const pendingContentUpdatesRef = useRef([]);
  const pendingZhuqueEventsRef = useRef([]);
  const streamFlushTimerRef = useRef(null);
  const lastStreamEventIdRef = useRef(0);
  const sessionStatusRef = useRef(null);

  useEffect(() => {
    setCollapsedZhuqueEventKeys(new Set());
    lastStreamEventIdRef.current = 0;
  }, [sessionId]);

  useEffect(() => {
    let eventSource = null;
    let reconnectTimer = null;
    let progressPollTimer = null;
    let disposed = false;

    const scheduleReconnect = () => {
      if (disposed || reconnectTimer) return;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectStream();
      }, STREAM_RECONNECT_DELAY_MS);
    };

    const connectStream = async () => {
      try {
        const tokenResponse = await optimizationAPI.createStreamToken(sessionId);
        if (disposed) return;
        const streamUrl = optimizationAPI.getStreamUrl(
          sessionId,
          tokenResponse.data.stream_token,
          lastStreamEventIdRef.current,
        );
        eventSource = new EventSource(streamUrl);

        eventSource.onmessage = (event) => {
          if (event.lastEventId) {
            const parsedEventId = Number(event.lastEventId);
            if (Number.isFinite(parsedEventId)) {
              lastStreamEventIdRef.current = Math.max(lastStreamEventIdRef.current, parsedEventId);
            }
          }
          try {
            if (!event.data || event.data.startsWith(':')) {
              return;
            }
            const data = JSON.parse(event.data);
            if (data.type === 'content') {
              enqueueStreamUpdate({ kind: 'content', data });
            } else if (
              data.type === 'zhuque_agent_event'
              || data.agent_event
              || data.type === 'zhuque_detect'
              || data.type === 'zhuque_reduce'
            ) {
              const liveEvent = normalizeZhuqueLiveEvent(data);
              if (liveEvent) {
                enqueueStreamUpdate({ kind: 'zhuque', data: liveEvent });
              }
            } else if (data.type === 'history_compressed') {
              toast.info(data.message);
            } else if (data.type === 'status') {
              loadSessionDetail();
            }
          } catch (error) {
            console.error('Error parsing SSE data:', error);
          }
        };

        eventSource.onerror = (error) => {
          console.error('SSE Error:', error);
          eventSource.close();
          eventSource = null;
          scheduleReconnect();
        };
      } catch (error) {
        console.error('SSE connection failed:', error);
        scheduleReconnect();
      }
    };

    const initializeSession = async () => {
      await loadSessionDetail();
      await loadChanges();
      if (disposed) return;
      await connectStream();
      progressPollTimer = window.setInterval(() => {
        if (
          document.visibilityState === 'visible'
          && ['queued', 'processing', 'waiting_browser_agent'].includes(sessionStatusRef.current)
        ) {
          loadSessionDetail();
        }
      }, ACTIVE_DETAIL_POLL_INTERVAL_MS);
    };

    initializeSession();

    return () => {
      disposed = true;
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (progressPollTimer) window.clearInterval(progressPollTimer);
      if (streamFlushTimerRef.current) {
        window.clearTimeout(streamFlushTimerRef.current);
        streamFlushTimerRef.current = null;
      }
      pendingContentUpdatesRef.current = [];
      pendingZhuqueEventsRef.current = [];
    };
  }, [sessionId]);

  const enqueueStreamUpdate = (update) => {
    if (update.kind === 'content') {
      pendingContentUpdatesRef.current.push(update.data);
    } else if (update.kind === 'zhuque') {
      pendingZhuqueEventsRef.current.push(update.data);
    }

    if (streamFlushTimerRef.current) {
      return;
    }

    streamFlushTimerRef.current = window.setTimeout(() => {
      flushStreamUpdates();
    }, STREAM_FLUSH_INTERVAL_MS);
  };

  const flushStreamUpdates = () => {
    const contentUpdates = pendingContentUpdatesRef.current;
    const zhuqueEvents = pendingZhuqueEventsRef.current;

    pendingContentUpdatesRef.current = [];
    pendingZhuqueEventsRef.current = [];
    streamFlushTimerRef.current = null;

    if (contentUpdates.length > 0) {
      handleStreamUpdates(contentUpdates);
    }

    if (zhuqueEvents.length > 0) {
      setZhuqueLiveEvents((current) => (
        mergeZhuqueEvents([], [...current, ...zhuqueEvents]).slice(-20)
      ));
      const latestRemaining = [...zhuqueEvents]
        .reverse()
        .map(event => event?.remaining_uses)
        .find(value => Number.isFinite(Number(value)) && Number(value) >= 0);
      if (latestRemaining !== undefined) {
        setZhuqueStatus((current) => ({ ...(current || {}), remaining_uses: Number(latestRemaining) }));
      }
    }
  };

  const handleStreamUpdates = (updates) => {
    setSegments(prevSegments => {
      const newSegments = [...prevSegments];

      for (const data of updates) {
        const segmentIndex = data.segment_index;

        // 确保段落存在
        if (!newSegments[segmentIndex]) {
          // 如果段落不存在（这不应该发生，除非初始化延迟），可以尝试重新加载或创建一个占位符
          // 这里简单地忽略或记录错误
          console.warn(`Segment ${segmentIndex} not found for update`);
          continue;
        }

        const segment = { ...newSegments[segmentIndex] };

        // 更新内容
        if (data.stage === 'polish' || data.stage === 'emotion_polish') {
          segment.polished_text = typeof data.full_text === 'string'
            ? data.full_text
            : (segment.polished_text || "") + data.content;
        } else if (data.stage === 'enhance') {
          segment.enhanced_text = typeof data.full_text === 'string'
            ? data.full_text
            : (segment.enhanced_text || "") + data.content;
        }

        // 标记为处理中（如果尚未标记）
        if (segment.status !== 'processing') {
            segment.status = 'processing';
        }

        newSegments[segmentIndex] = segment;
      }

      return newSegments;
    });

    // 同时更新会话状态为 processing
    setSession(prev => {
        if (prev && prev.status !== 'processing') {
            return { ...prev, status: 'processing' };
        }
        return prev;
    });
  };

  const loadSessionDetail = async () => {
    try {
      const [sessionResponse, zhuqueStatusResponse] = await Promise.all([
        optimizationAPI.getSessionDetail(sessionId),
        optimizationAPI.getZhuqueAuthStatus().catch((error) => {
          console.warn('加载朱雀状态失败:', error);
          return null;
        }),
      ]);
      sessionStatusRef.current = sessionResponse.data.status;
      setSession(sessionResponse.data);
      setSegments(sessionResponse.data.segments || []);
      if (zhuqueStatusResponse?.data) {
        setZhuqueStatus(zhuqueStatusResponse.data);
      }
    } catch (error) {
      toast.error('加载会话详情失败');
      navigate('/workspace');
    }
  };

  const loadChanges = async () => {
    try {
      const response = await optimizationAPI.getSessionChanges(sessionId);
      setChanges(response.data);
    } catch (error) {
      console.error('加载变更记录失败:', error);
    }
  };

  const handleExport = async (acknowledged) => {
    if (!acknowledged) {
      toast.error('请确认学术诚信承诺');
      return;
    }

    try {
      const response = await optimizationAPI.exportSession(sessionId, {
        session_id: sessionId,
        acknowledge_academic_integrity: true,
        export_format: exportFormat,
      });

      const mimeType = response.data.mime_type || 'application/octet-stream';
      let blob;
      if (response.data.content_base64) {
        const binary = window.atob(response.data.content_base64);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
          bytes[index] = binary.charCodeAt(index);
        }
        blob = new Blob([bytes], { type: mimeType });
      } else {
        blob = new Blob([response.data.content || ''], { type: mimeType });
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.data.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast.success('导出成功');
      setShowExportModal(false);
    } catch (error) {
      toast.error('导出失败: ' + error.response?.data?.detail);
    }
  };

  const handleStop = async () => {
    if (!window.confirm('确定要停止当前的优化任务吗？已完成的段落将保留。')) {
      return;
    }

    try {
      await optimizationAPI.stopSession(sessionId);
      toast.success('任务已停止');
      loadSessionDetail(); // 刷新状态
    } catch (error) {
      toast.error('停止任务失败: ' + (error.response?.data?.detail || '未知错误'));
    }
  };

  const handleOpenZhuqueVerificationWindow = async () => {
    if (isOpeningZhuqueVerification) {
      return;
    }

    try {
      setIsOpeningZhuqueVerification(true);
      const response = await optimizationAPI.startZhuqueLogin({ syncSession: true, mode: 'local_window' });
      const payload = response.data || {};
      const message = payload.message || '已请求打开朱雀验证窗口，请在真实浏览器完成腾讯验证码。';
      if (payload.command) {
        console.info('Zhuque verification command:', payload.command);
      }
      if (payload.status === 'manual_required' || payload.status === 'missing_script' || payload.status === 'error') {
        toast.error(message);
      } else {
        toast.success(message);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '打开朱雀验证窗口失败，请稍后再试');
    } finally {
      setIsOpeningZhuqueVerification(false);
    }
  };

  const handleRetryZhuqueAfterManualVerification = async () => {
    if (isRetryingZhuqueAfterVerification) {
      return;
    }
    if (!['failed', 'stopped'].includes(session?.status)) {
      toast.error('当前任务状态不可继续处理');
      return;
    }

    try {
      setIsRetryingZhuqueAfterVerification(true);
      const response = await optimizationAPI.retryFailedSegments(sessionId, {
        billing_mode: session?.billing_mode || 'keep',
      });
      toast.success(response.data?.message || '已重新排队继续朱雀检测降重');
      await loadSessionDetail();
    } catch (error) {
      toast.error(error.response?.data?.detail || '继续处理失败，请确认验证码已完成后再试');
    } finally {
      setIsRetryingZhuqueAfterVerification(false);
    }
  };

  const sortedSegments = useMemo(() => [...segments].sort((a, b) => a.segment_index - b.segment_index), [segments]);

  const getFinalText = useCallback(() => {
    return sortedSegments
      .map(seg => seg.zhuque_reduced_text || seg.enhanced_text || seg.polished_text || seg.original_text)
      .join('\n\n');
  }, [sortedSegments]);

  const parseZhuqueResult = (rawResult) => {
    if (!rawResult) {
      return null;
    }
    if (typeof rawResult === 'object') {
      return rawResult;
    }
    try {
      return JSON.parse(rawResult);
    } catch (error) {
      return { raw: rawResult };
    }
  };

  const parseZhuqueAgentTrace = (rawTrace) => {
    if (!rawTrace) {
      return null;
    }
    if (typeof rawTrace === 'object') {
      return rawTrace;
    }
    try {
      return JSON.parse(rawTrace);
    } catch (error) {
      return { version: 1, events: [], final: { diagnosis: String(rawTrace) } };
    }
  };

  const getZhuqueReport = () => {
    if (session?.processing_mode !== 'ai_detect_reduce') {
      return null;
    }

    const trace = parseZhuqueAgentTrace(session?.zhuque_agent_trace);
    const traceEvents = Array.isArray(trace?.events) ? trace.events : [];
    const detectEvents = traceEvents.filter(event => event?.type === 'detect');
    const successfulDetectEvents = detectEvents.filter(event => (
      event?.status !== 'error'
      && event?.rate !== null
      && event?.rate !== undefined
      && !Number.isNaN(Number(event.rate))
    ));
    const latestSuccessfulDetect = [...successfulDetectEvents].reverse()[0] || null;
    const latestKnownRemaining = [
      zhuqueStatus?.remaining_uses,
      ...[...detectEvents].reverse().map(event => event?.remaining_uses),
    ].find(value => Number.isFinite(Number(value)) && Number(value) >= 0);

    const detectedSegments = sortedSegments.filter(
      seg => seg.zhuque_detect_count > 0 || seg.zhuque_detect_rate !== null || seg.zhuque_detect_result
    );
    if (detectedSegments.length === 0 && successfulDetectEvents.length === 0) {
      return {
        finalRate: null,
        isInvalid: false,
        detectCount: 0,
        reduceRounds: 0,
        segmentCount: sortedSegments.length,
        result: latestKnownRemaining !== undefined ? { remaining_uses: Number(latestKnownRemaining) } : null,
      };
    }

    // sortedSegments is already sorted by segment_index, no need to re-sort
    const reportSegment = [...detectedSegments]
      .reverse()
      .find(seg => seg.zhuque_detect_result || seg.zhuque_detect_rate !== null) || detectedSegments[0] || {};
    const parsedResult = parseZhuqueResult(reportSegment.zhuque_detect_result);
    const result = {
      ...(parsedResult || {}),
      ...(latestSuccessfulDetect?.rate !== undefined ? { rate: latestSuccessfulDetect.rate } : {}),
      ...(latestKnownRemaining !== undefined ? { remaining_uses: Number(latestKnownRemaining) } : {}),
    };
    const finalRate = getZhuqueRiskRate(result, reportSegment.zhuque_detect_rate ?? latestSuccessfulDetect?.rate ?? null);
    const isInvalid = result?.success === false || finalRate === null;
    const traceReduceRounds = Math.max(
      ...traceEvents
        .filter(event => Number.isFinite(Number(event?.round)))
        .map(event => Number(event.round)),
      0,
    );

    return {
      finalRate,
      isInvalid,
      detectCount: successfulDetectEvents.length || Math.max(...detectedSegments.map(seg => seg.zhuque_detect_count || 0), 0),
      reduceRounds: Math.max(...segments.map(seg => seg.zhuque_reduce_attempt || 0), traceReduceRounds, 0),
      segmentCount: segments.length,
      result,
    };
  };

  const formatRate = (rate) => {
    if (rate === null || rate === undefined || Number.isNaN(Number(rate))) {
      return '--';
    }
    const number = Number(rate);
    return `${Number.isInteger(number) ? number : number.toFixed(1)}%`;
  };

  const formatRemainingUses = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) {
      return '--';
    }
    return String(Math.trunc(number));
  };

  const normalizeZhuqueLiveEvent = (data) => {
    if (!data || typeof data !== 'object') {
      return null;
    }
    if (data.agent_event && typeof data.agent_event === 'object') {
      return data.agent_event;
    }
    if (data.type === 'zhuque_detect') {
      return {
        ...data,
        live_type: data.type,
        type: 'detect',
        phase: 'zhuque_detect',
        status: data.success === false ? 'error' : 'success',
        round: data.round ?? 0,
        title: '全文检测',
        summary: data.message || `朱雀检测：${formatRate(data.rate)}`,
        selected_segment_indices: data.segment_indices || [],
      };
    }
    if (data.type === 'zhuque_reduce') {
      return {
        ...data,
        live_type: data.type,
        type: 'reduce',
        phase: 'zhuque_reduce',
        status: data.rollback_applied ? 'warning' : 'success',
        title: data.title || `第 ${data.round ?? '--'} 轮降 AI`,
        summary: data.message || `朱雀降重：${formatRate(data.old_rate)} → ${formatRate(data.new_rate)}`,
        selected_segment_indices: data.selected_segment_indices || data.segment_indices || [],
      };
    }
    return data;
  };

  const getZhuqueEventSignature = (event) => ([
    event?.type || '',
    event?.phase || '',
    event?.round ?? '',
    event?.rate ?? '',
    event?.old_rate ?? '',
    event?.new_rate ?? '',
    event?.strategy || '',
    event?.rewrite_mode || '',
    event?.stage || '',
    event?.batch_id || '',
  ].join('|'));

  const getZhuqueEventKey = (event, index) => (
    event?.id
      || (event?.seq !== undefined ? `seq-${event.seq}` : null)
      || `${getZhuqueEventSignature(event)}-${index}`
  );

  const getZhuqueEventDetailId = (eventKey, index) => {
    const safeKey = String(eventKey || index).replace(/[^a-zA-Z0-9_-]/g, '-');
    return `zhuque-agent-detail-${index}-${safeKey}`;
  };

  const toggleZhuqueEvent = useCallback((eventKey) => {
    setCollapsedZhuqueEventKeys((current) => {
      const next = new Set(current);
      if (next.has(eventKey)) {
        next.delete(eventKey);
      } else {
        next.add(eventKey);
      }
      return next;
    });
  }, []);

  const mergeZhuqueEvents = (traceEvents = [], liveEvents = []) => {
    const merged = [];
    const primaryIndex = new Map();
    const signatureIndex = new Map();
    const sourceEvents = [...(traceEvents || []), ...(liveEvents || [])]
      .map(normalizeZhuqueLiveEvent)
      .filter(event => event && typeof event === 'object');

    sourceEvents.forEach((event) => {
      const primaryKey = event.id
        ? `id:${event.id}`
        : (event.seq !== undefined ? `seq:${event.seq}` : null);
      const signature = getZhuqueEventSignature(event);
      let existingIndex = primaryKey && primaryIndex.has(primaryKey)
        ? primaryIndex.get(primaryKey)
        : undefined;

      if (existingIndex === undefined && signatureIndex.has(signature)) {
        existingIndex = signatureIndex.get(signature);
      }

      if (existingIndex !== undefined) {
        const previous = merged[existingIndex];
        merged[existingIndex] = {
          ...previous,
          ...event,
          id: event.id || previous.id,
          seq: event.seq ?? previous.seq,
          created_at: event.created_at || previous.created_at,
          title: event.title || previous.title,
          summary: event.summary || previous.summary,
        };
      } else {
        existingIndex = merged.length;
        merged.push(event);
      }

      const mergedEvent = merged[existingIndex];
      const mergedPrimaryKey = mergedEvent.id
        ? `id:${mergedEvent.id}`
        : (mergedEvent.seq !== undefined ? `seq:${mergedEvent.seq}` : null);
      if (mergedPrimaryKey) {
        primaryIndex.set(mergedPrimaryKey, existingIndex);
      }
      signatureIndex.set(getZhuqueEventSignature(mergedEvent), existingIndex);
    });

    return merged;
  };

  const getZhuqueManualVerificationState = (report, events = [], errorMessage = '') => {
    const candidates = [
      report?.result,
      ...(events || []),
    ].filter(item => item && typeof item === 'object');
    const matched = candidates.find(item => (
      item.manual_verification_required === true
      || item.error_code === 'zhuque_captcha_required'
      || messageNeedsZhuqueManualVerification(item.message)
      || messageNeedsZhuqueManualVerification(item.summary)
    ));
    if (matched) {
      return {
        label: matched.manual_verification_label || '打开朱雀验证窗口',
        message: matched.message || matched.summary || '朱雀触发腾讯验证码，需要在真实浏览器完成验证。',
        mode: matched.manual_verification_mode || 'local_window',
        action: matched.manual_verification_action || 'open_zhuque_local_window',
      };
    }
    if (messageNeedsZhuqueManualVerification(errorMessage)) {
      return {
        label: '打开朱雀验证窗口',
        message: errorMessage,
        mode: 'local_window',
        action: 'open_zhuque_local_window',
      };
    }
    return null;
  };

  const getAgentEventTitle = (event) => {
    if (event?.title) {
      return event.title;
    }
    if (event?.type === 'detect') {
      return '全文检测';
    }
    if (event?.type === 'segment_classification') {
      return 'fallback 段落识别';
    }
    if (event?.type === 'batch_plan') {
      return `第 ${event.round ?? '--'} 轮批量规划`;
    }
    if (event?.type === 'batch_validation') {
      return `批次校验：${event.batch_id || '--'}`;
    }
    if (event?.type === 'batch_stage') {
      return `批次完成：${event.batch_id || '--'}`;
    }
    if (event?.type === 'batch_fallback') {
      return `批次降级：${event.batch_id || '--'}`;
    }
    if (event?.type === 'reflection') {
      return `第 ${event.round} 轮收敛反思`;
    }
    if (event?.type === 'plateau_exit') {
      return `第 ${event.round} 轮卡点退出`;
    }
    if (event?.type === 'plateau_recovery') {
      return `第 ${event.round} 轮卡点自动探索`;
    }
    if (event?.type === 'plateau_deep_reconstruction') {
      return `第 ${event.round} 轮深度重构`;
    }
    if (event?.type === 'detector_floor') {
      return '检测地板校准';
    }
    if (event?.type === 'prompt_evolution') {
      return `第 ${event.round} 轮 Agent 学习结果`;
    }
    return `第 ${event?.round ?? '--'} 轮降 AI`;
  };

  const getAgentEventStatusLabel = (status) => {
    const labels = {
      running: '执行中',
      success: '已完成',
      accepted: '已采纳',
      failed: '未采纳',
      partial: '部分成功',
      invalid_json: 'JSON异常',
      invalid_structure: '结构异常',
      warning: '需关注',
      error: '失败',
    };
    return labels[status] || status;
  };

  const formatAgentList = (value) => Array.isArray(value) && value.length > 0
    ? value.join('、')
    : '无';

  const formatAgentCounts = (value) => {
    if (!value || typeof value !== 'object') {
      return null;
    }
    return Object.entries(value)
      .map(([key, count]) => `${key}: ${count}`)
      .join(' / ');
  };

  const getZhuqueRiskRate = (result, fallbackRate = null) => {
    if (result?.success === false) {
      return null;
    }
    const labelsRatio = result?.labels_ratio;
    if (labelsRatio && typeof labelsRatio === 'object' && Object.keys(labelsRatio).length > 0) {
      const aiRate = Number(labelsRatio[0] ?? labelsRatio['0'] ?? 0) * 100;
      const suspiciousRate = Number(labelsRatio[2] ?? labelsRatio['2'] ?? 0) * 100;
      const riskRate = Math.max(
        Number.isNaN(aiRate) ? 0 : aiRate,
        Number.isNaN(suspiciousRate) ? 0 : suspiciousRate,
      );
      return Number(riskRate.toFixed(2));
    }
    const fallback = result?.risk_rate ?? fallbackRate ?? result?.rate ?? null;
    if (fallback === null || fallback === undefined || Number.isNaN(Number(fallback))) {
      return null;
    }
    return Number(fallback);
  };

  const formatLabelsRatio = (labelsRatio) => {
    if (!labelsRatio || typeof labelsRatio !== 'object' || Object.keys(labelsRatio).length === 0) {
      return null;
    }
    const labelNames = {
      0: 'AI特征',
      1: '人工特征',
      2: '疑似AI',
    };
    return Object.entries(labelsRatio)
      .map(([label, value]) => {
        const ratio = Number(value);
        const displayValue = Number.isNaN(ratio)
          ? String(value)
          : `${(ratio * 100).toFixed(1)}%`;
        return `${labelNames[label] || label}: ${displayValue}`;
      })
      .join(' / ');
  };

  const getOriginalText = useCallback(() => {
    return sortedSegments
      .map(seg => seg.original_text)
      .join('\n\n');
  }, [sortedSegments]);

  const getPolishedText = useCallback(() => {
    return sortedSegments
      .map(seg => seg.polished_text || seg.original_text)
      .join('\n\n');
  }, [sortedSegments]);

  const getDisplayText = useCallback(() => {
    if (resultViewMode === 'polished') {
      return getPolishedText();
    }
    return getFinalText();
  }, [resultViewMode, getPolishedText, getFinalText]);

  const shouldShowResultSwitch = useMemo(() => {
    return session?.processing_mode === 'paper_polish_enhance'
      && segments.some(seg => seg.polished_text && seg.enhanced_text);
  }, [session?.processing_mode, segments]);

  const zhuqueReport = useMemo(() => getZhuqueReport(), [session, sortedSegments, zhuqueStatus]);
  const zhuqueAgentTrace = useMemo(() => parseZhuqueAgentTrace(session?.zhuque_agent_trace), [session?.zhuque_agent_trace]);
  const zhuqueTraceEvents = useMemo(() => zhuqueAgentTrace?.events || [], [zhuqueAgentTrace]);
  const zhuqueTimelineEvents = useMemo(() => mergeZhuqueEvents(zhuqueTraceEvents, zhuqueLiveEvents), [zhuqueTraceEvents, zhuqueLiveEvents]);
  const zhuqueManualVerification = useMemo(
    () => getZhuqueManualVerificationState(zhuqueReport, zhuqueTimelineEvents, session?.error_message),
    [session?.error_message, zhuqueReport, zhuqueTimelineEvents],
  );
  const canRetryZhuqueAfterManualVerification = ['failed', 'stopped'].includes(session?.status);
  const reflectionDrawerIndex = useMemo(() => zhuqueTimelineEvents.findIndex((event) => event.type === 'reflection'), [zhuqueTimelineEvents]);
  const reflectionRollbackEvent = useMemo(() => reflectionDrawerIndex >= 0
    ? [...zhuqueTimelineEvents.slice(0, reflectionDrawerIndex + 1)].reverse().find((event) => event.rollback_applied)
    : null, [zhuqueTimelineEvents, reflectionDrawerIndex]);
  const reflectionLearningEvent = useMemo(() => reflectionDrawerIndex >= 0
    ? zhuqueTimelineEvents.slice(reflectionDrawerIndex + 1).find((event) => Array.isArray(event.root_causes) && event.root_causes.length > 0)
    : null, [zhuqueTimelineEvents, reflectionDrawerIndex]);
  const hasReflectionDrawer = useMemo(() => reflectionDrawerIndex >= 0 && (reflectionRollbackEvent || reflectionLearningEvent), [reflectionDrawerIndex, reflectionRollbackEvent, reflectionLearningEvent]);
  const zhuqueThreshold = 20;
  const zhuquePassed = useMemo(() => !zhuqueReport?.isInvalid && zhuqueReport?.finalRate !== null && zhuqueReport?.finalRate <= zhuqueThreshold, [zhuqueReport]);
  const zhuqueLabelsRatio = useMemo(() => formatLabelsRatio(zhuqueReport?.result?.labels_ratio), [zhuqueReport]);
  const labelsRatio = zhuqueReport?.result?.labels_ratio;
  const ratioChipData = useMemo(() => !zhuqueReport?.isInvalid && labelsRatio && typeof labelsRatio === 'object' && Object.keys(labelsRatio).length > 0
    ? [
        ['AI生成', labelsRatio[0] ?? labelsRatio['0'], 'blue'],
        ['人类写作', labelsRatio[1] ?? labelsRatio['1'], 'green'],
        ['疑似AI', labelsRatio[2] ?? labelsRatio['2'], 'slate'],
      ].filter(([, value]) => value !== undefined && value !== null)
    : [], [zhuqueReport?.isInvalid, labelsRatio]);
  const formatRatioChipValue = useCallback((value) => {
    const ratio = Number(value);
    return Number.isNaN(ratio) ? String(value) : `${Math.round(ratio * 100)}%`;
  }, []);

  if (!session) {
    return (
      <div className="gank-app-page flex items-center justify-center">
        <div className="gank-card rounded-2xl p-10 text-center">
          <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="gank-app-page aurora-session-page">
      <div className="gank-ambient-orb orb-one" />
      <div className="gank-ambient-orb orb-two" />
      <div className="gank-ambient-orb orb-three" />

      {/* 顶部导航 */}
      <header className="sticky top-0 z-50">
        <nav className="apple-global-nav aurora-session-topbar">
          <div className="mx-auto flex min-h-[68px] max-w-[1840px] items-center justify-between gap-4 px-5 sm:px-8 lg:px-12">
            <div className="flex min-w-0 items-center gap-4">
              <BrandLogo size="md" showText className="aurora-session-brand" />
              <span className="hidden text-[16px] font-light leading-none text-slate-400 sm:block">›</span>
              <span className="hidden text-[12px] font-medium text-slate-500 sm:inline">会话详情</span>
            </div>

            <div className="flex min-w-0 items-center gap-3">
              <button
                onClick={() => navigate('/workspace')}
                className="aurora-detail-back-link"
              >
                <ArrowLeft className="h-4 w-4" />
                <span className="hidden sm:inline">返回工作台</span>
              </button>

              {session.status === 'completed' && (
                <>
                  <div className="aurora-status-pill aurora-status-pill-success">
                    <CheckCircle className="h-4 w-4" />
                    <span>已完成</span>
                  </div>

                  <button
                    onClick={() => setShowExportModal(true)}
                    className="aurora-export-button apple-action-pill gank-primary-button"
                  >
                    <Download className="h-4 w-4" />
                    导出
                  </button>
                </>
              )}

              {session.status === 'failed' && (
                <div className="aurora-status-pill aurora-status-pill-danger">
                  <AlertCircle className="h-4 w-4" />
                  <span>处理失败</span>
                </div>
              )}

              {session.status === 'stopped' && (
                <div className="aurora-status-pill aurora-status-pill-muted">
                  <AlertCircle className="h-4 w-4" />
                  <span>已停止</span>
                </div>
              )}

              {session.status === 'waiting_browser_agent' && (
                <div className="aurora-status-pill aurora-status-pill-muted">
                  <Clock className="h-4 w-4" />
                  <span>等待本机朱雀插件</span>
                </div>
              )}

              {(['processing', 'queued', 'waiting_browser_agent'].includes(session.status)) && (
                <button
                  onClick={handleStop}
                  className="aurora-stop-button"
                >
                  <Square className="h-4 w-4 fill-current" />
                  停止
                </button>
              )}
            </div>
          </div>
        </nav>
      </header>

      {/* 主内容 */}
      <div className="aurora-session-shell relative z-[1] mx-auto max-w-[1480px] px-5 pb-8 pt-4 sm:px-8 lg:px-0">
        <div className="aurora-session-title-row mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.04em] text-slate-950 sm:text-[27px]">
              会话详情
            </h1>
            <span className="text-[12px] font-medium text-slate-500">
              {formatChinaDate(session.created_at)}
            </span>
          </div>

          <div className="flex justify-center lg:absolute lg:left-1/2 lg:-translate-x-1/2">
            <div className="aurora-detail-tabs gank-segmented-control inline-flex w-full max-w-xl p-1">
              <button
                onClick={() => setActiveTab('result')}
                className={`aurora-detail-tab ${activeTab === 'result' ? 'aurora-detail-tab-active' : ''}`}
              >
                优化结果
              </button>
              <button
                onClick={() => setActiveTab('compare')}
                className={`aurora-detail-tab ${activeTab === 'compare' ? 'aurora-detail-tab-active' : ''}`}
              >
                变更对照
              </button>
            </div>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="aurora-session-stack space-y-5">
          {session.status === 'failed' && (
            <div className="gank-liquid-section px-5 py-4 text-red-800">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">处理失败原因</p>
                  <p className="mt-1 text-sm leading-6">
                    {session.error_message || '任务处理失败，请检查 API 配置或稍后继续处理。'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {zhuqueManualVerification && (
            <div className="gank-liquid-section px-5 py-4 text-slate-800">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-3">
                  <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                  <div>
                    <p className="text-sm font-semibold text-slate-950">朱雀需要人工验证码</p>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      {zhuqueManualVerification.message}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      完成验证后回到本页点击“验证完成，继续处理”，系统会沿用当前会话继续排队。
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="apple-action-pill"
                    onClick={handleOpenZhuqueVerificationWindow}
                    disabled={isOpeningZhuqueVerification || zhuqueManualVerification.mode !== 'local_window'}
                  >
                    {isOpeningZhuqueVerification ? '正在打开…' : zhuqueManualVerification.label}
                  </button>
                  <button
                    type="button"
                    className="apple-ghost-pill"
                    onClick={handleRetryZhuqueAfterManualVerification}
                    disabled={!canRetryZhuqueAfterManualVerification || isRetryingZhuqueAfterVerification}
                  >
                    {isRetryingZhuqueAfterVerification ? '正在继续…' : '验证完成，继续处理'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'result' && (
            <>
              {zhuqueReport && (
                <section className="aurora-detail-report apple-report-stage gank-liquid-panel gank-report-shell overflow-hidden">
                  <div className="aurora-detail-report-head">
                    <div className="flex items-center gap-4">
                      <div className="aurora-detail-icon aurora-detail-icon-blue">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-[17px] font-semibold leading-tight tracking-[-0.025em] text-slate-950">检测报告预览</h3>
                        <p className="mt-1 text-[11px] leading-5 text-slate-500">
                          朱雀 AI 报告，全文合并检测，阈值 {zhuqueThreshold}%，检测不消耗啤酒
                        </p>
                      </div>
                    </div>
                    <div className={`aurora-report-status ${zhuquePassed ? 'aurora-report-status-success' : 'aurora-report-status-danger'}`}>
                      {zhuquePassed ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                      {zhuqueReport.finalRate === null ? (zhuqueReport.isInvalid ? '检测无效' : '暂无报告') : (zhuquePassed ? '已达标' : '未达标')}
                    </div>
                  </div>

                  <div className="aurora-detail-report-body">
                    <div className="aurora-report-metrics gank-glass-status-grid">
                      <div className="aurora-report-metric apple-utility-card apple-metric-card">
                        <div className="aurora-metric-icon aurora-metric-icon-blue">
                          <Shield className="h-5 w-5" />
                        </div>
                        <div>
                          <p>最终风险率</p>
                          <strong className="aurora-metric-value-blue">{formatRate(zhuqueReport.finalRate)}</strong>
                        </div>
                      </div>
                      <div className="aurora-report-metric apple-utility-card apple-metric-card">
                        <div className="aurora-metric-icon aurora-metric-icon-sky">
                          <Search className="h-5 w-5" />
                        </div>
                        <div>
                          <p>朱雀检测</p>
                          <strong className="aurora-metric-value-blue">{zhuqueReport.detectCount}<span>次</span></strong>
                        </div>
                      </div>
                      <div className="aurora-report-metric apple-utility-card apple-metric-card">
                        <div className="aurora-metric-icon aurora-metric-icon-green">
                          <RefreshCw className="h-5 w-5" />
                        </div>
                        <div>
                          <p>降重轮次</p>
                          <strong className="aurora-metric-value-green">{zhuqueReport.reduceRounds}<span>轮</span></strong>
                        </div>
                      </div>
                      <div className="aurora-report-metric apple-utility-card apple-metric-card">
                        <div className="aurora-metric-icon aurora-metric-icon-purple">
                          <Database className="h-5 w-5" />
                        </div>
                        <div>
                          <p>朱雀剩余</p>
                          <strong className="aurora-metric-value-purple">{formatRemainingUses(zhuqueReport.result?.remaining_uses)}<span>次</span></strong>
                        </div>
                      </div>
                    </div>

                    {(ratioChipData.length > 0 || zhuqueLabelsRatio || zhuqueReport.result?.message || zhuqueReport.result?.text_length) && (
                      <div className="aurora-report-meta gank-liquid-section">
                        <div className="aurora-report-meta-item aurora-report-meta-ratios">
                          <span className="aurora-report-meta-label">分类占比：</span>
                          {zhuqueReport.isInvalid || !zhuqueLabelsRatio ? (
                            <span>暂无有效占比</span>
                          ) : ratioChipData.length > 0 ? ratioChipData.map(([label, value, tone]) => (
                            <span key={label} className={`aurora-report-chip aurora-report-chip-${tone}`}>
                              {label} {formatRatioChipValue(value)}
                            </span>
                          )) : <span>{zhuqueLabelsRatio}</span>}
                        </div>
                        {zhuqueReport.result?.text_length != null && (
                          <div className="aurora-report-meta-item">
                            <span className="aurora-report-meta-label">检测字数：</span>
                            <span>{Number(zhuqueReport.result.text_length).toLocaleString()} 字</span>
                          </div>
                        )}
                        {zhuqueReport.result?.message && (
                          <div className="aurora-report-meta-item aurora-report-meta-message">
                            <span className="aurora-report-meta-label">朱雀提示：</span>
                            <span>{zhuqueReport.result.message}</span>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="aurora-process-wrap">
                      <div className="aurora-process-rail" aria-label="处理过程">
                        <span className="sr-only">处理过程</span>
                        <div className="aurora-process-step">
                          <span>1</span>
                          <p>全文检测</p>
                          <span>合并 {zhuqueReport.segmentCount} 段调用朱雀</span>
                        </div>
                        <div className="aurora-process-step">
                          <span>2</span>
                          <p>论文润色</p>
                          <span>{zhuqueReport.reduceRounds > 0 ? `已执行 ${zhuqueReport.reduceRounds} 轮` : '风险率未超阈值，未调用'}</span>
                        </div>
                        <div className="aurora-process-step">
                          <span>3</span>
                          <p>论文增强</p>
                          <span>{zhuqueReport.reduceRounds > 0 ? '使用增强结果作为最终文本' : '保留原文'}</span>
                        </div>
                        <div className="aurora-process-step">
                          <span>4</span>
                          <p>全文复检</p>
                          <span>{zhuqueReport.detectCount > 1 ? `已复检 ${zhuqueReport.detectCount - 1} 次` : '无需复检'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {session?.processing_mode === 'ai_detect_reduce' && (zhuqueAgentTrace || zhuqueTimelineEvents.length > 0) && (
                <section className="aurora-agent-panel apple-utility-card gank-liquid-panel overflow-hidden">
                  <div className="aurora-agent-head">
                    <div className="flex items-center gap-4">
                      <div className="aurora-detail-icon aurora-detail-icon-pulse">
                        <Activity className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="text-[15px] font-semibold leading-tight tracking-[-0.02em] text-slate-950">Agent 决策轨迹</h3>
                        <p className="mt-0.5 text-[11px] leading-5 text-slate-500">
                          记录朱雀检测、策略选择、命中段落和风险率变化
                        </p>
                      </div>
                    </div>
                    {zhuqueAgentTrace?.final?.diagnosis && (
                      <div className="aurora-diagnosis-pill">
                        诊断建议：{zhuqueAgentTrace.final.diagnosis}
                      </div>
                    )}
                  </div>

                  <div className="gank-agent-scroll aurora-agent-scroll custom-scrollbar max-h-[560px]">
                    {zhuqueTimelineEvents.map((event, index) => {
                      const eventTitle = getAgentEventTitle(event);
                      const rewriteModeLabel = event.rewrite_mode === 'breakthrough'
                        ? '逃逸改写'
                        : event.rewrite_mode === 'paper_reconstruction'
                          ? '论文重构'
                          : `rewrite_mode: ${event.rewrite_mode}`;
                      const isReflectionDrawer = index === reflectionDrawerIndex && hasReflectionDrawer;
                      const showStandaloneRollback = event.rollback_applied && event !== reflectionRollbackEvent;
                      const showStandaloneRootCause = event.root_causes && event.root_causes.length > 0 && event !== reflectionLearningEvent;
                      const hasPaperAiPatterns = Array.isArray(event.paper_ai_patterns) && event.paper_ai_patterns.length > 0;
                      const hasLengthAdjustments = Array.isArray(event.length_adjustments) && event.length_adjustments.length > 0;
                      const hasExpandableDetails = Boolean(
                        isReflectionDrawer
                        || showStandaloneRollback
                        || event.type === 'plateau_exit'
                        || hasPaperAiPatterns
                        || showStandaloneRootCause
                        || event.prompt_patch
                        || hasLengthAdjustments
                        || event.type === 'segment_classification'
                        || event.type === 'batch_validation'
                        || event.type === 'batch_fallback'
                        || Array.isArray(event.skipped_summary)
                        || event.type_counts
                        || event.action_counts
                        || event.summary
                        || event.message
                      );
                      const eventKey = getZhuqueEventKey(event, index);
                      const eventDetailId = getZhuqueEventDetailId(eventKey, index);
                      const isEventCollapsed = hasExpandableDetails && collapsedZhuqueEventKeys.has(eventKey);

                      return (
                        <article key={eventKey} className="aurora-agent-event">
                          <div className="aurora-agent-node" aria-hidden="true">{index + 1}</div>
                          <div className="aurora-agent-card gank-liquid-section">
                            <div className="aurora-agent-row-main">
                              <h4>{eventTitle}</h4>
                              <div className="aurora-agent-chip-row">
                                {event.strategy && (
                                  <span className="aurora-agent-chip aurora-agent-chip-blue">{event.strategy}</span>
                                )}
                                {event.status && (
                                  <span className={`aurora-agent-chip ${
                                    ['failed', 'error', 'warning'].includes(event.status)
                                      ? 'aurora-agent-chip-red'
                                      : event.status === 'accepted'
                                        ? 'aurora-agent-chip-green'
                                        : 'aurora-agent-chip-muted'
                                  }`}>
                                    {getAgentEventStatusLabel(event.status)}
                                  </span>
                                )}
                                {event.current_strategy && (
                                  <span className="aurora-agent-chip aurora-agent-chip-muted">当前：{event.current_strategy}</span>
                                )}
                                {event.next_strategy && (
                                  <span className="aurora-agent-chip aurora-agent-chip-blue">下一轮：{event.next_strategy}</span>
                                )}
                                {event.rewrite_mode && (
                                  <span className={`aurora-agent-chip ${
                                    event.rewrite_mode === 'breakthrough'
                                      ? 'aurora-agent-chip-red'
                                      : event.rewrite_mode === 'paper_reconstruction'
                                        ? 'aurora-agent-chip-green'
                                        : 'aurora-agent-chip-muted'
                                  }`}>
                                    {rewriteModeLabel}
                                  </span>
                                )}
                              </div>

                              <div className="aurora-agent-meta-grid">
                                {event.rate !== undefined && <p>风险率：{formatRate(event.rate)}</p>}
                                {(event.old_rate !== undefined || event.new_rate !== undefined) && (
                                  <p>风险率变化：{formatRate(event.old_rate)} → {formatRate(event.new_rate)}</p>
                                )}
                                {event.selected_segment_indices && (
                                  <p>命中段落：{formatAgentList(event.selected_segment_indices)}</p>
                                )}
                                {event.segment_indices && (
                                  <p>批次段落：{formatAgentList(event.segment_indices)}</p>
                                )}
                                {event.fallback_segment_indices && (
                                  <p>降级段落：{formatAgentList(event.fallback_segment_indices)}</p>
                                )}
                                {event.stubborn_segment_indices && (
                                  <p>顽固段落：{formatAgentList(event.stubborn_segment_indices)}</p>
                                )}
                                {event.selected_count !== undefined && <p>选中段数：{event.selected_count}</p>}
                                {event.skipped_count !== undefined && <p>跳过段数：{event.skipped_count}</p>}
                                {event.batch_count !== undefined && <p>批次数：{event.batch_count}</p>}
                                {event.saved_llm_calls !== undefined && <p>节省调用：{event.saved_llm_calls} 次</p>}
                                {event.duration_ms !== undefined && <p>耗时：{event.duration_ms} ms</p>}
                                {event.fallback_count !== undefined && <p>降级数量：{event.fallback_count}</p>}
                                {event.stage && <p>阶段：{event.stage}</p>}
                                {event.stagnation_count !== undefined && (
                                  <p>连续停滞：{event.stagnation_count} 轮</p>
                                )}
                                {event.decision && <p>决策：{event.decision}</p>}
                                {event.action && <p>动作：{event.action}</p>}
                                {event.source && <p>来源：{event.source === 'memory' ? '历史记忆' : event.source}</p>}
                                {event.safety_status && <p>安全校验：{event.safety_status}</p>}
                                {event.paper_language && <p>论文语言：{event.paper_language === 'zh' ? '中文' : 'English'}</p>}
                                {event.paper_section && <p>论文章节：{event.paper_section}</p>}
                                {event.candidate_count !== undefined && <p>候选数量：{event.candidate_count}</p>}
                                {event.fact_card_count !== undefined && <p>事实卡片：{event.fact_card_count} 项</p>}
                                {Array.isArray(event.candidate_rates) && <p>候选复检：{event.candidate_rates.length} 次</p>}
                                {event.recommended_threshold !== undefined && <p>建议阈值：{formatRate(event.recommended_threshold)}</p>}
                                {formatAgentCounts(event.type_counts) && <p>类型统计：{formatAgentCounts(event.type_counts)}</p>}
                              </div>

                              {hasExpandableDetails ? (
                                <button
                                  type="button"
                                  className="aurora-agent-chevron"
                                  onClick={() => toggleZhuqueEvent(eventKey)}
                                  aria-expanded={!isEventCollapsed}
                                  aria-controls={eventDetailId}
                                  aria-label={`${isEventCollapsed ? '展开' : '收起'}${eventTitle}详情`}
                                >
                                  {isEventCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                                </button>
                              ) : (
                                <span className="aurora-agent-chevron aurora-agent-chevron-placeholder" aria-hidden="true" />
                              )}
                            </div>

                            {(!isEventCollapsed || !hasExpandableDetails) && (
                              <div id={hasExpandableDetails ? eventDetailId : undefined}>
                            <div className="aurora-agent-meta-grid aurora-agent-meta-grid-mobile">
                              {event.rate !== undefined && <p>风险率：{formatRate(event.rate)}</p>}
                              {(event.old_rate !== undefined || event.new_rate !== undefined) && (
                                <p>风险率变化：{formatRate(event.old_rate)} → {formatRate(event.new_rate)}</p>
                              )}
                              {event.selected_segment_indices && (
                                <p>命中段落：{formatAgentList(event.selected_segment_indices)}</p>
                              )}
                              {event.segment_indices && (
                                <p>批次段落：{formatAgentList(event.segment_indices)}</p>
                              )}
                              {event.fallback_segment_indices && (
                                <p>降级段落：{formatAgentList(event.fallback_segment_indices)}</p>
                              )}
                              {event.stubborn_segment_indices && (
                                <p>顽固段落：{formatAgentList(event.stubborn_segment_indices)}</p>
                              )}
                              {event.selected_count !== undefined && <p>选中段数：{event.selected_count}</p>}
                              {event.skipped_count !== undefined && <p>跳过段数：{event.skipped_count}</p>}
                              {event.batch_count !== undefined && <p>批次数：{event.batch_count}</p>}
                              {event.saved_llm_calls !== undefined && <p>节省调用：{event.saved_llm_calls} 次</p>}
                              {event.duration_ms !== undefined && <p>耗时：{event.duration_ms} ms</p>}
                              {event.fallback_count !== undefined && <p>降级数量：{event.fallback_count}</p>}
                              {event.stage && <p>阶段：{event.stage}</p>}
                              {event.stagnation_count !== undefined && (
                                <p>连续停滞：{event.stagnation_count} 轮</p>
                              )}
                              {event.decision && <p>决策：{event.decision}</p>}
                              {event.action && <p>动作：{event.action}</p>}
                              {event.source && <p>来源：{event.source === 'memory' ? '历史记忆' : event.source}</p>}
                              {event.safety_status && <p>安全校验：{event.safety_status}</p>}
                              {event.paper_language && <p>论文语言：{event.paper_language === 'zh' ? '中文' : 'English'}</p>}
                              {event.paper_section && <p>论文章节：{event.paper_section}</p>}
                              {event.candidate_count !== undefined && <p>候选数量：{event.candidate_count}</p>}
                              {event.fact_card_count !== undefined && <p>事实卡片：{event.fact_card_count} 项</p>}
                              {Array.isArray(event.candidate_rates) && <p>候选复检：{event.candidate_rates.length} 次</p>}
                              {event.recommended_threshold !== undefined && <p>建议阈值：{formatRate(event.recommended_threshold)}</p>}
                              {formatAgentCounts(event.type_counts) && <p>类型统计：{formatAgentCounts(event.type_counts)}</p>}
                            </div>

                            {(formatAgentCounts(event.action_counts) || Array.isArray(event.skipped_summary)) && (
                              <div className="aurora-agent-note aurora-agent-note-blue">
                                <p className="font-semibold">fallback 识别日志</p>
                                {formatAgentCounts(event.action_counts) && (
                                  <p>动作统计：{formatAgentCounts(event.action_counts)}</p>
                                )}
                                {Array.isArray(event.skipped_summary) && event.skipped_summary.length > 0 && (
                                  <p>
                                    跳过样例：{event.skipped_summary.slice(0, 6).map((item) => (
                                      `#${item.segment_index} ${item.type_code || '--'}(${item.reason || '--'})`
                                    )).join('；')}
                                  </p>
                                )}
                              </div>
                            )}

                            {(event.missing_ids || event.duplicate_ids || event.unknown_ids || event.empty_ids) && (
                              <div className="aurora-agent-note aurora-agent-note-muted">
                                <p className="font-semibold">批量输出校验</p>
                                {event.missing_ids && <p>缺失 ID：{formatAgentList(event.missing_ids)}</p>}
                                {event.duplicate_ids && <p>重复 ID：{formatAgentList(event.duplicate_ids)}</p>}
                                {event.unknown_ids && <p>未知 ID：{formatAgentList(event.unknown_ids)}</p>}
                                {event.empty_ids && <p>空文本 ID：{formatAgentList(event.empty_ids)}</p>}
                              </div>
                            )}

                            {isReflectionDrawer && (
                              <div className="aurora-agent-drawer">
                                {reflectionRollbackEvent && (
                                  <div className="aurora-agent-note aurora-agent-note-red">
                                    <p className="font-semibold">回滚保护</p>
                                    <p>
                                      本轮改写未取得更低风险率，已恢复上一版文本，避免风险率反弹。
                                      {Array.isArray(reflectionRollbackEvent.restored_segment_indices) && reflectionRollbackEvent.restored_segment_indices.length > 0
                                        ? ` 恢复段落：${reflectionRollbackEvent.restored_segment_indices.join('、')}`
                                        : ''}
                                    </p>
                                  </div>
                                )}
                                {reflectionLearningEvent && (
                                  <div className="aurora-agent-note aurora-agent-note-blue">
                                    <p className="font-semibold">失败原因</p>
                                    <p>{reflectionLearningEvent.root_causes.join('；')}</p>
                                  </div>
                                )}
                              </div>
                            )}

                            {showStandaloneRollback && (
                              <div className="aurora-agent-note aurora-agent-note-red">
                                <p className="font-semibold">回滚保护</p>
                                <p>
                                  本轮改写未取得更低风险率，已恢复上一版文本。
                                  {Array.isArray(event.restored_segment_indices) && event.restored_segment_indices.length > 0
                                    ? ` 恢复段落：${event.restored_segment_indices.join('、')}`
                                    : ''}
                                </p>
                              </div>
                            )}
                            {event.type === 'plateau_exit' && (
                              <div className="aurora-agent-note aurora-agent-note-muted">
                                <p className="font-semibold">卡点退出</p>
                                <p>已保留上一版最低风险文本，建议人工微调顽固段落或调整阈值后复检。</p>
                              </div>
                            )}
                            {hasPaperAiPatterns && (
                              <div className="aurora-agent-note aurora-agent-note-green">
                                <p className="font-semibold">论文 AI 痕迹</p>
                                <p>{event.paper_ai_patterns.join('；')}</p>
                                {event.candidate_selector && <p>候选选择：{event.candidate_selector}</p>}
                              </div>
                            )}
                            {showStandaloneRootCause && (
                              <div className="aurora-agent-note aurora-agent-note-blue">
                                <p className="font-semibold">失败原因</p>
                                <p>{event.root_causes.join('；')}</p>
                              </div>
                            )}
                            {event.prompt_patch && (
                              <details className="aurora-agent-note aurora-agent-note-purple">
                                <summary className="cursor-pointer font-semibold text-purple-700">查看 prompt_patch</summary>
                                <pre className="mt-2 whitespace-pre-wrap font-sans leading-6">{event.prompt_patch}</pre>
                              </details>
                            )}
                            {hasLengthAdjustments && (
                              <div className="aurora-agent-note aurora-agent-note-blue">
                                <p className="font-semibold">长度校正</p>
                                {event.length_adjustments.map((item, adjustIndex) => (
                                  <p key={`length-adjustment-${adjustIndex}`}>
                                    段落 {item.segment_index}：
                                    原文 {item.original_length} 字，
                                    校正前 {item.before_length} 字，
                                    校正后 {item.after_length} 字
                                    {item.lower_bound !== undefined && item.upper_bound !== undefined
                                      ? `（目标 ${item.lower_bound}-${item.upper_bound} 字）`
                                      : ''}
                                  </p>
                                ))}
                              </div>
                            )}
                            {(event.summary || event.message) && (
                              <p className="mt-2 text-[11px] leading-5 text-slate-500">{event.summary || event.message}</p>
                            )}
                              </div>
                            )}
                          </div>
                        </article>
                      );
                    })}

                    {zhuqueLiveEvents.length > 0 && (
                      <div className="aurora-agent-live gank-liquid-section">
                        <p className="mb-2 text-[11px] font-semibold text-slate-950">实时 Agent 状态</p>
                        <div className="space-y-1 text-[11px] leading-5 text-slate-700">
                          {zhuqueLiveEvents.map((event, index) => (
                            <p key={getZhuqueEventKey(event, index)}>
                              {event.type === 'detect'
                                ? `朱雀检测：${formatRate(event.rate)}`
                                : event.type === 'segment_classification'
                                  ? `段落识别：选中 ${event.selected_count ?? 0} 段，跳过 ${event.skipped_count ?? 0} 段`
                                  : event.type?.startsWith?.('batch_')
                                    ? `批量处理：${event.batch_id || '--'}，${event.stage || '--'}，${event.status || '--'}`
                                    : `朱雀降重：第 ${event.round ?? '--'} 轮，策略 ${event.strategy || '--'}，${formatRate(event.old_rate)} → ${formatRate(event.new_rate)}${event.length_adjustments?.length ? `，长度校正 ${event.length_adjustments.length} 段` : ''}`}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              )}

              <div className="aurora-reading-grid grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="aurora-reading-card apple-reading-panel gank-text-panel overflow-hidden">
                  <div className="aurora-reading-head">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="aurora-reading-icon aurora-reading-icon-blue">
                        <FileText className="h-3.5 w-3.5" />
                      </div>
                      <h3>
                        {shouldShowResultSwitch
                          ? (resultViewMode === 'enhanced' ? '增强后的文本' : '润色后的文本')
                          : '优化后的文本'}
                      </h3>

                      {shouldShowResultSwitch && (
                        <div className="aurora-mini-tabs gank-segmented-control inline-flex p-0.5">
                          <button
                            onClick={() => setResultViewMode('polished')}
                            className={resultViewMode === 'polished' ? 'aurora-mini-tab-active' : ''}
                          >
                            润色
                          </button>
                          <button
                            onClick={() => setResultViewMode('enhanced')}
                            className={resultViewMode === 'enhanced' ? 'aurora-mini-tab-active' : ''}
                          >
                            增强
                          </button>
                        </div>
                      )}
                    </div>

                    <button
                      className="aurora-copy-button apple-action-pill"
                      onClick={() => {
                        navigator.clipboard.writeText(getDisplayText());
                        toast.success('已复制到剪贴板');
                      }}
                    >
                      复制全文
                    </button>
                  </div>
                  <div className="aurora-reading-body custom-scrollbar">
                    <pre className="whitespace-pre-wrap font-sans">
                      {getDisplayText()}
                    </pre>
                  </div>
                </div>

                <div className="aurora-reading-card aurora-reading-card-muted apple-reading-panel gank-text-panel overflow-hidden">
                  <div className="aurora-reading-head">
                    <div className="flex items-center gap-3">
                      <div className="aurora-reading-icon aurora-reading-icon-muted">
                        <FileText className="h-3.5 w-3.5" />
                      </div>
                      <h3>原始文本</h3>
                    </div>
                  </div>
                  <div className="aurora-reading-body custom-scrollbar">
                    <pre className="whitespace-pre-wrap font-sans">
                      {getOriginalText()}
                    </pre>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'compare' && (
            <div className="apple-utility-card gank-liquid-panel p-6 min-h-[calc(100vh-180px)]">
              <h3 className="text-[20px] font-bold text-black mb-6 tracking-tight">
                变更对照记录
              </h3>
              
              {changes.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4 text-gray-300">
                    <GitCompare className="w-8 h-8" />
                  </div>
                  <p className="text-ios-gray">
                    暂无变更记录
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {changes.map((change, index) => (
                    <div key={change.id} className="border border-gray-100 rounded-xl p-5 hover:shadow-md transition-shadow">
                      <div className="flex items-center gap-2 mb-4">
                        <span className="bg-blue-50 text-ios-blue text-[11px] font-bold px-2 py-1 rounded-md uppercase tracking-wide">
                          段落 {change.segment_index + 1}
                        </span>
                        <span className="bg-blue-50 text-ios-blue text-[11px] font-bold px-2 py-1 rounded-md uppercase tracking-wide">
                          {change.stage === 'polish' ? '润色' :
                           change.stage === 'emotion_polish' ? '感情润色' :
                           '增强'}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <h4 className="text-[13px] font-semibold text-ios-gray mb-2 uppercase tracking-wide">
                            修改前
                          </h4>
                          <div className="bg-red-50/50 border border-red-100 rounded-lg p-4 text-[15px] text-gray-800 leading-relaxed">
                            {change.before_text}
                          </div>
                        </div>
                        
                        <div>
                          <h4 className="text-[13px] font-semibold text-ios-gray mb-2 uppercase tracking-wide">
                            修改后
                          </h4>
                          <div className="bg-green-50/50 border border-green-100 rounded-lg p-4 text-[15px] text-black leading-relaxed font-medium">
                            {change.after_text}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 导出确认模态框 - iOS Alert Style */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-[100]">
          <div className="gank-liquid-panel max-w-sm w-full overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 text-center">
              <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-6 h-6 text-ios-orange" />
              </div>
              <h2 className="text-[17px] font-semibold text-black mb-2">
                学术诚信确认
              </h2>
              <p className="text-[13px] text-black mb-4">
                请确认您已审核所有内容，并对最终论文负责。
              </p>

              <div className="gank-liquid-section rounded-lg p-3 text-left mb-4">
                <ul className="space-y-1.5 text-[12px] text-gray-600">
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 符合学术规范
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 核心观点原创
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-ios-green font-bold">✓</span> 承担全部责任
                  </li>
                </ul>
              </div>

              <div className="mb-4">
                <label className="block text-[12px] font-medium text-ios-gray mb-1.5 text-left">
                  导出格式
                </label>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value)}
                  className="gank-input rounded-lg px-3 py-2 text-[15px]"
                >
                  <option value="docx">Word文档 (.docx)</option>
                  <option value="md">Markdown文件 (.md)</option>
                  {session?.processing_mode === 'ai_detect_reduce' && (
                    <>
                      <option value="aigc_report_docx">AIGC检测报告 (.docx)</option>
                      <option value="aigc_report_md">AIGC检测报告 (.md)</option>
                    </>
                  )}
                </select>
                {session?.processing_mode === 'ai_detect_reduce' && (
                  <p className="mt-2 text-left text-[12px] leading-5 text-gray-500">
                    AIGC检测报告会像知网报告一样列出每一段的 AI 率、AI特征、疑似AI和人工特征占比。
                  </p>
                )}
              </div>
            </div>

            <div className="flex border-t border-gray-200 divide-x divide-gray-200">
              <button
                onClick={() => setShowExportModal(false)}
                className="flex-1 py-3.5 text-[17px] font-normal text-ios-blue hover:bg-white/50 active:bg-white/70 transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => handleExport(true)}
                className="flex-1 py-3.5 text-[17px] font-semibold text-ios-blue hover:bg-white/50 active:bg-white/70 transition-colors"
              >
                确认导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionDetailPage;
