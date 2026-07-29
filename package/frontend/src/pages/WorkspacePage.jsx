import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  FileText, History,
  ListChecks, Clock, AlertCircle, CheckCircle, Trash2, Pencil, ExternalLink,
  Sparkles, TrendingUp, ShieldCheck, Heart, Layers, Link as LinkIcon, Folder,
  Filter, ChevronDown, Wand2, Plus, Archive, CircleDollarSign, X, FolderInput, QrCode, RefreshCw,
  UploadCloud, Loader2
} from 'lucide-react';
import { browserAgentAPI, optimizationAPI, projectAPI, userAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import UserMenu from '../components/UserMenu';
import MarkdownPreview from '../components/MarkdownPreview';
import { formatChinaDate, parseBackendDate } from '../utils/dateTime';

const CREDIT_UNIT_CHARACTERS = 1000;
const PROCESSING_MODE_STAGE_MULTIPLIERS = {
  paper_polish: 1,
  paper_enhance: 1,
  paper_polish_enhance: 2,
};

const PROCESSING_MODE_OPTIONS = [
  { id: 'paper_polish', title: '论文润色', desc: '优化语言表达，提升论文可读性', icon: Sparkles, tone: 'cyan' },
  { id: 'paper_enhance', title: '论文增强', desc: '增强逻辑结构，提升论证深度', icon: TrendingUp, tone: 'navy' },
  { id: 'paper_polish_enhance', title: '润色 + 增强', desc: '语言优化与内容增强双重提升', icon: Layers, tone: 'violet' },
  { id: 'ai_detect_reduce', title: 'AI检测 + 降重', desc: '降低AI疑似率，减少重复率', icon: ShieldCheck, tone: 'blue' },
  { id: 'emotion_polish', title: '感情文章润色', desc: '优化情感表达，提升文章温度', icon: Heart, tone: 'pink' },
];

const DEFAULT_PROCESSING_MODE = 'paper_polish';
const DEFAULT_BILLING_MODE = 'platform';
const WORKSPACE_PROCESSING_MODE_STORAGE_KEY = 'gankaigc.workspace.processingMode';
const WORKSPACE_BILLING_MODE_STORAGE_KEY = 'gankaigc.workspace.billingMode';
const PROCESSING_MODE_IDS = new Set(PROCESSING_MODE_OPTIONS.map((option) => option.id));
const BILLING_MODE_IDS = new Set(['platform', 'byok']);

const getInitialProcessingMode = () => {
  if (typeof window === 'undefined') {
    return DEFAULT_PROCESSING_MODE;
  }

  try {
    const savedMode = window.localStorage.getItem(WORKSPACE_PROCESSING_MODE_STORAGE_KEY);
    return PROCESSING_MODE_IDS.has(savedMode) ? savedMode : DEFAULT_PROCESSING_MODE;
  } catch {
    return DEFAULT_PROCESSING_MODE;
  }
};

const getInitialBillingMode = () => {
  if (typeof window === 'undefined') {
    return DEFAULT_BILLING_MODE;
  }

  try {
    const savedMode = window.localStorage.getItem(WORKSPACE_BILLING_MODE_STORAGE_KEY);
    return BILLING_MODE_IDS.has(savedMode) ? savedMode : DEFAULT_BILLING_MODE;
  } catch {
    return DEFAULT_BILLING_MODE;
  }
};

const PROCESSING_MODE_DESCRIPTIONS = {
  paper_polish: '仅进行论文润色，提升文本的学术性和表达质量。',
  paper_enhance: '直接进行原创性增强，跳过润色阶段，适合已经润色过的文本。',
  paper_polish_enhance: '先进行论文润色，然后自动进行原创性增强，两阶段处理。',
  ai_detect_reduce: '先执行 1 次朱雀全文初检；仅当 AI 浓度超过 20% 并发生改写时，才会在每轮改写后复检。检测不消耗啤酒，实际降重改写按次数扣啤酒。',
  emotion_polish: '专为感情文章设计，生成更自然、更具人性化的表达。',
};

const ZHUQUE_PROCESS_STEPS = ['朱雀检测', '论文重构', '全文复检'];
const ZHUQUE_DETECT_PAGE_URL = 'https://matrix.tencent.com/ai-detect/';
const ZHUQUE_STATUS_POLL_INTERVAL_MS = 5000;
const ZHUQUE_STATUS_FAST_POLL_INTERVAL_MS = 1500;
const ZHUQUE_STATUS_FAST_POLL_DURATION_MS = 8000;
const ZHUQUE_LOGIN_POLL_INTERVAL_MS = 700;
const ZHUQUE_READINESS_SOFT_TIMEOUT_MS = 2500;
const WORKSPACE_QUEUE_POLL_INTERVAL_MS = 15000;
const ACTIVE_SESSION_POLL_INTERVAL_MS = 6000;
const BROWSER_AGENT_SYNC_REQUEST_TYPE = 'GANKAIGC_SYNC_ZHUQUE_STATUS';
const BROWSER_AGENT_SYNC_RESULT_TYPE = 'GANKAIGC_SYNC_ZHUQUE_STATUS_RESULT';
const BROWSER_AGENT_PAGE_SOURCE = 'GANKAIGC_PAGE';
const BROWSER_AGENT_EXTENSION_SOURCE = 'GANKAIGC_EXTENSION';

const requestBrowserAgentZhuqueRefresh = ({ focus = false, timeoutMs = 4000 } = {}) => {
  if (typeof window === 'undefined') {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    const requestId = `zhuque-sync-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      window.removeEventListener('message', handleMessage);
      clearTimeout(timer);
      resolve(value);
    };
    const handleMessage = (event) => {
      if (event.source !== window) return;
      const data = event.data || {};
      if (data.source !== BROWSER_AGENT_EXTENSION_SOURCE || data.type !== BROWSER_AGENT_SYNC_RESULT_TYPE || data.requestId !== requestId) {
        return;
      }
      finish(data.response || null);
    };
    const timer = setTimeout(() => finish(null), timeoutMs);
    window.addEventListener('message', handleMessage);
    window.postMessage({
      source: BROWSER_AGENT_PAGE_SOURCE,
      type: BROWSER_AGENT_SYNC_REQUEST_TYPE,
      requestId,
      focus,
    }, window.location.origin);
  });
};

const countBillableCharacters = (value) => (value.match(/\S/g) || []).length;

const getDocumentTitleFromFilename = (filename = '') => filename
  .replace(/\.[^.]+$/, '')
  .replace(/[_-]+/g, ' ')
  .trim();

const calculateEstimatedCredits = (value, mode) => {
  if (mode === 'ai_detect_reduce') {
    return 0;
  }
  const billableCharacters = countBillableCharacters(value);
  const baseCredits = Math.max(1, Math.ceil(billableCharacters / CREDIT_UNIT_CHARACTERS));
  return baseCredits * (PROCESSING_MODE_STAGE_MULTIPLIERS[mode] || 1);
};

const getAnnouncementCategoryLabel = (category) => {
  const labels = {
    notice: '通知',
    maintenance: '维护',
    model: '模型',
    guide: '说明',
  };
  return labels[category] || '通知';
};

const getAnnouncementCategoryClass = (category) => {
  const classes = {
    notice: 'bg-blue-50 text-blue-700 border-blue-100',
    maintenance: 'bg-amber-50 text-amber-700 border-amber-100',
    model: 'bg-violet-50 text-violet-700 border-violet-100',
    guide: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  };
  return classes[category] || classes.notice;
};

const formatZhuqueRemainingUses = (value) => {
  if (value === null || value === undefined) {
    return '检测后同步';
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return '检测后同步';
  }
  return `${numeric} 次`;
};

const parseZhuqueRemainingUses = (value) => {
  if (value === null || value === undefined || typeof value === 'boolean') {
    return undefined;
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) && value >= 0 ? Math.trunc(value) : undefined;
  }
  const text = String(value).trim();
  if (!text) {
    return undefined;
  }
  const numeric = Number(text);
  if (Number.isFinite(numeric)) {
    return numeric >= 0 ? Math.trunc(numeric) : undefined;
  }
  if (/(^|\D)-1(\D|$)|unknown|unavailable|检测后同步|未知|不可用/i.test(text)) {
    return undefined;
  }
  const patterns = [
    /(?:今日)?剩余\s*(\d+)\s*次/i,
    /可用\s*(\d+)\s*次/i,
    /(\d+)\s*(?:left|uses?|次)/i,
    /(?:left|uses?|remaining|available|quota)[^\d]{0,12}(\d+)/i,
    /(?:Detect now|立即检测)[^\d]{0,16}(\d+)/i,
  ];
  const match = patterns.map((pattern) => text.match(pattern)).find(Boolean);
  return match ? Number(match[1]) : undefined;
};

const extractZhuqueRemainingUses = (...sources) => {
  for (const source of sources) {
    if (source === null || source === undefined) {
      continue;
    }
    if (typeof source === 'object') {
      const remaining = extractZhuqueRemainingUses(
        source.remaining_uses,
        source.remainingUses,
        source.availableUses,
        source.quota_text,
        source.quotaText,
        source.submitButtonText
      );
      if (remaining !== undefined) {
        return remaining;
      }
      continue;
    }
    const remaining = parseZhuqueRemainingUses(source);
    if (remaining !== undefined) {
      return remaining;
    }
  }
  return undefined;
};

const mergeBrowserAgentZhuqueStatuses = (reportedStatus = {}, freshStatus = {}) => {
  const reported = reportedStatus && typeof reportedStatus === 'object' ? reportedStatus : {};
  const fresh = freshStatus && typeof freshStatus === 'object' ? freshStatus : {};
  const reportedRemaining = extractZhuqueRemainingUses(reported);
  const freshRemaining = extractZhuqueRemainingUses(fresh);
  const remaining = freshRemaining ?? reportedRemaining;
  return {
    ...reported,
    ...fresh,
    ...(remaining !== undefined ? { remaining_uses: remaining } : {}),
  };
};

const withSoftTimeout = (promise, timeoutMs) => Promise.race([
  promise,
  new Promise((resolve) => {
    window.setTimeout(resolve, timeoutMs);
  }),
]);

const PROCESSING_MODE_LABELS = PROCESSING_MODE_OPTIONS.reduce((acc, option) => {
  acc[option.id] = option.title;
  return acc;
}, {});

const getProcessingModeLabel = (mode) => PROCESSING_MODE_LABELS[mode] || '论文处理';

const getSessionStatusLabel = (status) => {
  const labels = {
    completed: '已完成',
    processing: '处理中',
    queued: '排队中',
    waiting_browser_agent: '等待本机朱雀插件',
    failed: '失败',
    stopped: '已停止',
  };
  return labels[status] || '处理中';
};

const getSessionStatusClass = (status) => {
  if (status === 'completed') return 'text-emerald-600';
  if (status === 'processing' || status === 'queued' || status === 'waiting_browser_agent') return 'text-[#2563eb]';
  if (status === 'failed') return 'text-rose-600';
  if (status === 'stopped') return 'text-orange-600';
  return 'text-slate-500';
};

const HISTORY_STATUS_FILTERS = [
  { id: 'all', label: '全部状态' },
  { id: 'completed', label: '已完成' },
  { id: 'processing', label: '处理中' },
  { id: 'queued', label: '排队中' },
  { id: 'waiting_browser_agent', label: '等待本机朱雀插件' },
  { id: 'failed', label: '失败' },
  { id: 'stopped', label: '已停止' },
];

const getModeToneClass = (tone) => {
  const tones = {
    cyan: 'aurora-icon-cyan',
    navy: 'aurora-icon-navy',
    violet: 'aurora-icon-violet',
    blue: 'aurora-icon-blue',
    pink: 'aurora-icon-pink',
  };
  return tones[tone] || tones.blue;
};

const formatSessionWordCount = (count) => {
  const numeric = Number(count);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return '字数 --';
  }
  return `字数 ${numeric.toLocaleString('zh-CN')}`;
};

const formatSessionDuration = (session) => {
  const startDate = parseBackendDate(session.started_at || session.created_at);
  const endDate = parseBackendDate(session.finished_at || session.completed_at || session.updated_at);
  if (!startDate || !endDate || endDate < startDate) {
    return '耗时 --';
  }

  const totalSeconds = Math.max(0, Math.round((endDate.getTime() - startDate.getTime()) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `耗时 ${hours}小时${minutes}分`;
  }
  if (minutes > 0) {
    return `耗时 ${minutes}分${seconds}秒`;
  }
  return `耗时 ${seconds}秒`;
};

const ZHUQUE_MANUAL_CHECK_MESSAGE_MARKERS = [
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

const messageNeedsZhuqueManualCheck = (message) => {
  const text = String(message || '');
  if (!text) {
    return false;
  }
  const lowerText = text.toLowerCase();
  return ZHUQUE_MANUAL_CHECK_MESSAGE_MARKERS.some((marker) => lowerText.includes(marker.toLowerCase()));
};

const parseZhuqueTraceForManualCheck = (rawTrace) => {
  if (!rawTrace) {
    return null;
  }
  let trace = rawTrace;
  if (typeof rawTrace === 'string') {
    try {
      trace = JSON.parse(rawTrace);
    } catch {
      return messageNeedsZhuqueManualCheck(rawTrace)
        ? { message: rawTrace, label: '打开朱雀窗口' }
        : null;
    }
  }
  if (!trace || typeof trace !== 'object') {
    return null;
  }
  const events = Array.isArray(trace.events) ? trace.events : [];
  const matchedEvent = events.find((event) => (
    event
    && typeof event === 'object'
    && (
      event.manual_verification_required === true
      || event.error_code === 'zhuque_captcha_required'
      || messageNeedsZhuqueManualCheck(event.message)
      || messageNeedsZhuqueManualCheck(event.summary)
    )
  ));
  if (matchedEvent) {
    return {
      message: matchedEvent.message || matchedEvent.summary || '朱雀检测需要在真实浏览器确认页面状态。',
      label: matchedEvent.manual_verification_label || '打开朱雀窗口',
    };
  }
  const finalDiagnosis = trace.final?.diagnosis;
  return messageNeedsZhuqueManualCheck(finalDiagnosis)
    ? { message: finalDiagnosis, label: '打开朱雀窗口' }
    : null;
};

const getZhuqueManualCheckInfo = (session) => {
  if (!session || session.processing_mode !== 'ai_detect_reduce') {
    return null;
  }
  const traceInfo = parseZhuqueTraceForManualCheck(session.zhuque_agent_trace);
  if (traceInfo) {
    return traceInfo;
  }
  if (messageNeedsZhuqueManualCheck(session.error_message)) {
    return {
      message: session.error_message,
      label: '打开朱雀窗口',
    };
  }
  return null;
};

// 会话列表项组件 - 使用 memo 避免不必要重渲染
const SessionItem = memo(({ session, activeSession, projects, openProjectMenuSessionId, onToggleProjectMenu, onView, onDelete, onRetry, onMoveToProject, onOpenZhuqueVerification }) => {
  const handleDelete = useCallback((e) => {
    e.stopPropagation();
    onDelete(session);
  }, [session, onDelete]);

  const handleRetry = useCallback((e) => {
    e.stopPropagation();
    if (session.status === 'failed') {
      onRetry(session);
    }
  }, [session, onRetry]);

  const handleOpenZhuqueVerification = useCallback((e) => {
    e.stopPropagation();
    onOpenZhuqueVerification(session);
  }, [session, onOpenZhuqueVerification]);

  const handleView = useCallback(() => {
    onView(session.session_id);
  }, [session.session_id, onView]);

  const handleProjectMenuToggle = useCallback((event) => {
    event.stopPropagation();
    onToggleProjectMenu(openProjectMenuSessionId === session.session_id ? null : session.session_id);
  }, [onToggleProjectMenu, openProjectMenuSessionId, session.session_id]);

  const handleMoveToProject = useCallback((event, projectId) => {
    event.stopPropagation();
    onMoveToProject(session, projectId);
  }, [onMoveToProject, session]);

  const statusLabel = getSessionStatusLabel(session.status);
  const statusClass = getSessionStatusClass(session.status);
  const modeLabel = getProcessingModeLabel(session.processing_mode);
  const isActive = activeSession === session.session_id;
  const isProjectMenuOpen = openProjectMenuSessionId === session.session_id;
  const projectActionLabel = session.project_id ? '移动项目' : '归入项目';
  const targetProjects = projects.filter((project) => project.id !== session.project_id);
  const hasMoveTargets = targetProjects.length > 0 || Boolean(session.project_id);
  const zhuqueManualCheckInfo = getZhuqueManualCheckInfo(session);

  return (
    <article
      onClick={handleView}
      className={`aurora-history-item group ${isActive ? 'aurora-history-item-active' : ''} ${isProjectMenuOpen ? 'aurora-history-item-menu-open' : ''}`}
    >
      <div className="aurora-history-icon">
        {session.status === 'completed' && <FileText className="h-5 w-5" />}
        {session.status === 'processing' && <div className="h-5 w-5 rounded-full border-2 border-[#3b82f6]/25 border-t-[#3b82f6] animate-spin" />}
        {session.status === 'queued' && <Clock className="h-5 w-5" />}
        {session.status === 'waiting_browser_agent' && <Clock className="h-5 w-5" />}
        {session.status === 'failed' && <AlertCircle className="h-5 w-5" />}
        {session.status === 'stopped' && <AlertCircle className="h-5 w-5" />}
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-start justify-between gap-2">
          <h3 className="line-clamp-1 text-[14px] font-semibold tracking-[-0.01em] text-slate-900">
            {session.task_title || session.project_title || session.preview_text || '未命名任务'}
          </h3>
          <span className="aurora-mode-badge shrink-0">
            {modeLabel}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] leading-5 text-slate-500">
          <span>{formatChinaDate(session.created_at)}</span>
          <span>{formatSessionWordCount(session.original_char_count)}</span>
          <span>{formatSessionDuration(session)}</span>
          <span className={`font-semibold ${statusClass}`}>{statusLabel} ●</span>
        </div>

        {hasMoveTargets && (
          <div className="aurora-session-project-move" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              onClick={handleProjectMenuToggle}
              className={`aurora-session-project-trigger ${isProjectMenuOpen ? 'aurora-session-project-trigger-active' : ''}`}
              aria-label={`${projectActionLabel}：${session.task_title || session.preview_text || '未命名任务'}`}
              aria-haspopup="menu"
              aria-expanded={isProjectMenuOpen}
            >
              <FolderInput className="h-3.5 w-3.5" />
              <span>{projectActionLabel}</span>
              <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isProjectMenuOpen ? 'rotate-180' : ''}`} />
            </button>
            {isProjectMenuOpen && (
              <div className="aurora-session-project-menu" role="menu">
                <div className="aurora-session-project-menu-title">选择目标项目</div>
                {session.project_id && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={(event) => handleMoveToProject(event, null)}
                    className="aurora-session-project-option"
                  >
                    <span className="aurora-session-project-option-icon">
                      <Archive className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold">移回未归档</span>
                      <span className="block text-[11px] font-medium text-slate-500">从当前项目移出</span>
                    </span>
                  </button>
                )}
                {targetProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    role="menuitem"
                    onClick={(event) => handleMoveToProject(event, project.id)}
                    className="aurora-session-project-option"
                  >
                    <span className="aurora-session-project-option-icon">
                      <Folder className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{project.title}</span>
                      <span className="block text-[11px] font-medium text-slate-500">归入此项目</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {(session.status === 'processing' || session.status === 'waiting_browser_agent') && (
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500 transition-all duration-500 ease-out"
              style={{ width: `${session.progress}%` }}
            />
          </div>
        )}

        {session.status === 'failed' && (
          <div className="mt-2 flex items-start justify-between gap-2 rounded-xl bg-rose-50 px-2.5 py-2 text-[12px] text-rose-700">
            <span className="line-clamp-2">{session.error_message || '网络超时，请稍后继续处理'}</span>
            <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
              {zhuqueManualCheckInfo && (
                <button
                  type="button"
                  onClick={handleOpenZhuqueVerification}
                  className="rounded-full bg-amber-50 px-2 py-1 font-semibold text-amber-700 shadow-sm hover:bg-amber-100"
                >
                  打开验证
                </button>
              )}
              <button
                type="button"
                onClick={handleRetry}
                className="rounded-full bg-white px-2 py-1 font-semibold text-rose-600 shadow-sm hover:bg-rose-100"
              >
                继续
              </button>
            </div>
          </div>
        )}
      </div>

      <button
        onClick={handleDelete}
        className="aurora-delete-button"
        title="删除会话"
        aria-label="删除会话"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </article>
  );
});

SessionItem.displayName = 'SessionItem';


const WorkspacePage = () => {
  const [text, setText] = useState('');
  const [processingMode, setProcessingMode] = useState(getInitialProcessingMode);
  const [sessions, setSessions] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [credits, setCredits] = useState(null);
  const [hasProviderConfig, setHasProviderConfig] = useState(false);
  const [billingMode, setBillingMode] = useState(getInitialBillingMode);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isParsingDocument, setIsParsingDocument] = useState(false);
  const [retryDialogSession, setRetryDialogSession] = useState(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectTitle, setProjectTitle] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editProjectTitle, setEditProjectTitle] = useState('');
  const [editProjectDescription, setEditProjectDescription] = useState('');
  const [historyStatusFilter, setHistoryStatusFilter] = useState('all');
  const [showHistoryFilters, setShowHistoryFilters] = useState(false);
  const [movingSessionId, setMovingSessionId] = useState(null);
  const [openProjectMenuSessionId, setOpenProjectMenuSessionId] = useState(null);
  const [taskTitle, setTaskTitle] = useState('');
  const [documentParse, setDocumentParse] = useState(null);
  const [announcements, setAnnouncements] = useState([]);
  const [isStartingZhuqueLogin, setIsStartingZhuqueLogin] = useState(false);
  const [isRefreshingZhuqueQuota, setIsRefreshingZhuqueQuota] = useState(false);
  const [isSyncingBrowserAgentZhuque, setIsSyncingBrowserAgentZhuque] = useState(false);
  const [zhuqueAuthStatus, setZhuqueAuthStatus] = useState(null);
  const [zhuqueReadiness, setZhuqueReadiness] = useState(null);
  const [zhuqueLoginSession, setZhuqueLoginSession] = useState(null);
  const [browserAgentStatus, setBrowserAgentStatus] = useState(null);
  const [browserAgentPairing, setBrowserAgentPairing] = useState(null);
  const [isCreatingBrowserAgentPairing, setIsCreatingBrowserAgentPairing] = useState(false);
  const [isRevokingBrowserAgent, setIsRevokingBrowserAgent] = useState(false);
  const [showZhuqueLoginModal, setShowZhuqueLoginModal] = useState(false);
  const [zhuqueLastKnownLoggedOutRemaining, setZhuqueLastKnownLoggedOutRemaining] = useState(undefined);
  const [zhuqueFastPollUntil, setZhuqueFastPollUntil] = useState(0);
  const activeProjectIdRef = useRef(null);
  const isLoadingZhuqueStatusRef = useRef(false);
  const isRefreshingZhuqueQuotaRef = useRef(false);
  const hasAutoRefreshedZhuqueQuotaRef = useRef(false);
  const zhuqueLastKnownLoggedOutRemainingRef = useRef(undefined);
  const zhuqueLoginSessionIdRef = useRef('');
  const sessionsRef = useRef([]);
  const zhuqueManualVerificationOpenedSessionRef = useRef(new Set());
  const documentFileInputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  const rememberZhuqueLoggedOutRemaining = useCallback((value) => {
    const remaining = parseZhuqueRemainingUses(value);
    if (remaining === undefined) {
      return undefined;
    }
    zhuqueLastKnownLoggedOutRemainingRef.current = remaining;
    setZhuqueLastKnownLoggedOutRemaining((current) => (current === remaining ? current : remaining));
    return remaining;
  }, []);

  const clearZhuqueLoggedOutRemaining = useCallback(() => {
    zhuqueLastKnownLoggedOutRemainingRef.current = undefined;
    setZhuqueLastKnownLoggedOutRemaining(undefined);
  }, []);

  const activeProject = useMemo(() => (
    typeof activeProjectId === 'number' && activeProjectId > 0
      ? projects.find((project) => project.id === activeProjectId) || null
      : null
  ), [activeProjectId, projects]);
  const projectSelectValue = activeProjectId === null ? 'all' : String(activeProjectId ?? 0);
  const historyScopeTitle = activeProject
    ? activeProject.title
    : activeProjectId === 0 ? '未归档历史' : '全部历史';
  const historyScopeDescription = activeProject
    ? '当前论文项目'
    : activeProjectId === 0 ? '未归档任务' : '所有项目与未归档任务';
  const activeHistoryStatusFilter = HISTORY_STATUS_FILTERS.find((filter) => filter.id === historyStatusFilter) || HISTORY_STATUS_FILTERS[0];
  const filteredSessions = useMemo(() => {
    if (historyStatusFilter === 'all') {
      return sessions;
    }
    return sessions.filter((session) => session.status === historyStatusFilter);
  }, [historyStatusFilter, sessions]);
  const billableCharacterCount = useMemo(() => countBillableCharacters(text), [text]);
  const estimatedCredits = useMemo(
    () => calculateEstimatedCredits(text, processingMode),
    [processingMode, text]
  );
  const zhuqueAuthConnected = Boolean(zhuqueAuthStatus?.connected || zhuqueAuthStatus?.has_token);
  const zhuqueReadinessConnected = Boolean(zhuqueReadiness?.connected || zhuqueReadiness?.has_token);
  const zhuqueConnected = Boolean(zhuqueAuthConnected || zhuqueReadinessConnected);
  const zhuqueAuthRemainingValue = extractZhuqueRemainingUses(zhuqueAuthStatus);
  const zhuqueReadinessRemainingValue = extractZhuqueRemainingUses(zhuqueReadiness);
  const zhuqueLiveRemainingValue = (
    zhuqueConnected
      ? [
          zhuqueReadinessConnected ? zhuqueReadinessRemainingValue : undefined,
          zhuqueAuthConnected ? zhuqueAuthRemainingValue : undefined,
        ]
      : [
          !zhuqueReadinessConnected ? zhuqueReadinessRemainingValue : undefined,
          !zhuqueAuthConnected ? zhuqueAuthRemainingValue : undefined,
        ]
  ).find((value) => value !== undefined);
  useEffect(() => {
    if (!zhuqueConnected) {
      rememberZhuqueLoggedOutRemaining(zhuqueLiveRemainingValue);
    }
  }, [rememberZhuqueLoggedOutRemaining, zhuqueConnected, zhuqueLiveRemainingValue]);
  const zhuqueRemainingValue = zhuqueLiveRemainingValue ?? (!zhuqueConnected ? zhuqueLastKnownLoggedOutRemaining : undefined);
  const zhuqueHasKnownRemaining = zhuqueRemainingValue !== undefined;
  const zhuqueRemainingLabel = zhuqueHasKnownRemaining
    ? formatZhuqueRemainingUses(zhuqueRemainingValue)
    : '检测后同步';
  const zhuqueAccountName = [
    zhuqueReadiness?.user_name,
    zhuqueAuthStatus?.user_name,
    zhuqueReadiness?.userName,
    zhuqueAuthStatus?.userName,
  ].find((value) => typeof value === 'string' && value.trim())?.trim() || '';
  const zhuqueAccountLabel = zhuqueConnected ? (zhuqueAccountName || '已登录') : '未登录';
  const browserAgentRequired = Boolean(browserAgentStatus?.required || browserAgentStatus?.transport === 'browser_agent');
  const browserAgentStatusLoaded = browserAgentStatus !== null;
  const browserAgentOnline = Boolean(browserAgentStatus?.online);
  const browserAgentTransport = browserAgentStatus?.transport || 'auto';
  const browserAgentPrimary = Array.isArray(browserAgentStatus?.agents) && browserAgentStatus.agents.length > 0
    ? browserAgentStatus.agents[0]
    : null;
  const browserAgentZhuqueStatus = browserAgentStatus?.zhuque || browserAgentPrimary?.zhuque_status || {};
  const browserAgentZhuqueConnected = Boolean(
    browserAgentZhuqueStatus?.logged_in
    || browserAgentZhuqueStatus?.connected
    || browserAgentZhuqueStatus?.has_token
  );
  const browserAgentZhuqueAnonymousReady = Boolean(
    browserAgentZhuqueStatus?.page_found
    && browserAgentZhuqueStatus?.button_enabled
    && !browserAgentZhuqueConnected
  );
  const browserAgentZhuqueAccountName = [
    browserAgentZhuqueStatus?.user_name,
    browserAgentZhuqueStatus?.userName,
  ].find((value) => typeof value === 'string' && value.trim())?.trim() || '';
  const browserAgentZhuqueRemaining = extractZhuqueRemainingUses(browserAgentZhuqueStatus);
  const browserAgentStatusLabel = browserAgentRequired
    ? (browserAgentOnline ? '插件在线' : '插件未连接')
    : '本地浏览器模式';
  const browserAgentStatusMessage = browserAgentRequired
    ? (browserAgentStatus?.message || (browserAgentOnline ? '本机 Chrome 插件在线，朱雀检测将在用户浏览器执行。' : 'VPS 模式需要连接本机 Chrome 插件。'))
    : '本地部署继续使用内置/本机浏览器检测链路，无需安装插件。';
  const zhuqueDisplayConnected = browserAgentRequired ? browserAgentZhuqueConnected : zhuqueConnected;
  const zhuqueDisplayAccountLabel = browserAgentRequired
    ? (browserAgentZhuqueConnected ? `登录用户：${browserAgentZhuqueAccountName || '朱雀账号'}` : '朱雀未登录')
    : zhuqueAccountLabel;
  const zhuquePrimaryActionLabel = browserAgentRequired
    ? (browserAgentOnline ? '打开朱雀页面' : '生成配对码')
    : '打开朱雀页面';
  const zhuquePrimaryActionTitle = browserAgentRequired
    ? (browserAgentOnline ? '打开本机 Chrome 的朱雀检测页；游客次数可直接检测，页面要求时再完成登录或验证码' : '生成 Chrome 插件配对码')
    : '打开或聚焦本机托管的朱雀页面，完成登录/验证码后回到工作台同步状态';
  const zhuqueRemainingDisplayLabel = browserAgentRequired
    ? (browserAgentZhuqueRemaining !== undefined ? formatZhuqueRemainingUses(browserAgentZhuqueRemaining) : '检测后同步')
    : zhuqueRemainingLabel;

  const handleProcessingModeChange = useCallback((event) => {
    const nextMode = event.target.value;
    if (PROCESSING_MODE_IDS.has(nextMode)) {
      setProcessingMode(nextMode);
    }
  }, []);

  // 使用显式项目 ID 避免切换项目时读取到旧闭包中的 activeProjectId
  const loadSessions = useCallback(async (projectId = activeProjectIdRef.current) => {
    const resolvedProjectId = projectId === undefined ? activeProjectIdRef.current : projectId;

    try {
      setIsLoadingSessions(true);
      const response = await optimizationAPI.listSessions(resolvedProjectId);
      setSessions(response.data);

      // 查找正在处理的会话
      const processing = response.data.find(
        s => ['processing', 'queued', 'waiting_browser_agent'].includes(s.status)
      );
      setActiveSession(processing ? processing.session_id : null);
    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  // loadQueueStatus 不依赖 activeSession，避免 useEffect 重复触发
  const loadQueueStatus = useCallback(async () => {
    try {
      const response = await optimizationAPI.getQueueStatus();
      setQueueStatus(response.data);
    } catch (error) {
      console.error('加载队列状态失败:', error);
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      const response = await projectAPI.list();
      setProjects(response.data);
    } catch (error) {
      console.error('加载论文项目失败:', error);
    }
  }, []);

  const loadAccountState = useCallback(async () => {
    try {
      const [creditResponse, providerResponse] = await Promise.all([
        userAPI.getCredits(),
        userAPI.getProviderConfig(),
      ]);
      setCredits(creditResponse.data);
      setHasProviderConfig(Boolean(providerResponse.data));
    } catch (error) {
      console.error('加载账户状态失败:', error);
    }
  }, []);

  const loadAnnouncements = useCallback(async () => {
    try {
      const response = await userAPI.listAnnouncements();
      setAnnouncements(response.data);
    } catch (error) {
      console.error('加载公告失败:', error);
    }
  }, []);

  useEffect(() => {
    activeProjectIdRef.current = activeProjectId;
  }, [activeProjectId]);

  const syncZhuqueLoggedOutSnapshot = useCallback((statusPayload = null) => {
    const payload = statusPayload || {
      connected: false,
      ready: false,
      page_found: false,
      has_token: false,
      remaining_uses: -1,
      button_enabled: true,
      user_name: '',
      quota_text: '',
      message: '朱雀网页显示未登录',
    };
    const rawRemaining = payload.remaining_uses;
    const liveRemaining = rememberZhuqueLoggedOutRemaining(extractZhuqueRemainingUses(payload, rawRemaining));
    const fallbackRemaining = liveRemaining ?? zhuqueLastKnownLoggedOutRemainingRef.current;
    const hasKnownQuota = fallbackRemaining !== undefined;
    setZhuqueAuthStatus((current) => ({
      ...current,
      ...payload,
      status: payload.status || 'missing_credentials',
      connected: false,
      ready: false,
      has_token: false,
      remaining_uses: hasKnownQuota ? fallbackRemaining : -1,
      user_name: '',
      quota_text: payload.quota_text || '',
    }));
    setZhuqueReadiness((current) => ({
      ...current,
      ...payload,
      ready: Boolean(current?.text_length_ok ?? true),
      connected: false,
      page_found: false,
      has_token: false,
      remaining_uses: hasKnownQuota ? fallbackRemaining : -1,
      button_enabled: payload.button_enabled ?? true,
      user_name: '',
      quota_text: payload.quota_text || '',
      actions: payload.actions || current?.actions || [],
      message: payload.message || '朱雀未登录，可使用免费次数或扫码登录',
    }));
  }, [rememberZhuqueLoggedOutRemaining]);

  const mergeZhuqueAuthStatus = useCallback((payload) => {
    const parsedRemaining = extractZhuqueRemainingUses(payload);
    const isLoggedOutPayload = payload && payload.connected === false && payload.has_token === false;
    const liveRemaining = isLoggedOutPayload ? rememberZhuqueLoggedOutRemaining(parsedRemaining) : parsedRemaining;
    const nextPayload = liveRemaining !== undefined ? { ...payload, remaining_uses: liveRemaining } : payload;
    if (nextPayload && nextPayload.connected === false && nextPayload.has_token === false) {
      syncZhuqueLoggedOutSnapshot(nextPayload);
      return;
    }
    setZhuqueAuthStatus(nextPayload);
  }, [rememberZhuqueLoggedOutRemaining, syncZhuqueLoggedOutSnapshot]);

  const mergeZhuqueReadiness = useCallback((payload) => {
    const parsedRemaining = extractZhuqueRemainingUses(payload);
    const isLoggedOutPayload = payload && payload.connected === false && payload.has_token === false;
    const liveRemaining = isLoggedOutPayload ? rememberZhuqueLoggedOutRemaining(parsedRemaining) : parsedRemaining;
    const nextPayload = liveRemaining !== undefined ? { ...payload, remaining_uses: liveRemaining } : payload;
    if (nextPayload && nextPayload.connected === false && nextPayload.has_token === false) {
      const fallbackRemaining = liveRemaining ?? zhuqueLastKnownLoggedOutRemainingRef.current;
      const hasKnownQuota = fallbackRemaining !== undefined;
      setZhuqueReadiness((current) => ({
        ...current,
        ...nextPayload,
        connected: false,
        page_found: false,
        has_token: false,
        remaining_uses: hasKnownQuota ? fallbackRemaining : -1,
        user_name: '',
        quota_text: nextPayload.quota_text || '',
      }));
      setZhuqueAuthStatus((current) => ({
        ...current,
        connected: false,
        ready: false,
        has_token: false,
        remaining_uses: hasKnownQuota ? fallbackRemaining : -1,
        user_name: '',
        quota_text: nextPayload.quota_text || '',
      }));
      return;
    }
    setZhuqueReadiness(nextPayload);
  }, [rememberZhuqueLoggedOutRemaining]);

  const loadZhuqueAuthStatus = useCallback(async () => {
    try {
      const response = await optimizationAPI.getZhuqueAuthStatus();
      mergeZhuqueAuthStatus(response.data);
    } catch (error) {
      mergeZhuqueAuthStatus({
        status: 'disconnected',
        connected: false,
        message: '无法检测朱雀凭证状态',
      });
    }
  }, [mergeZhuqueAuthStatus]);

  const loadZhuqueReadiness = useCallback(async () => {
    try {
      const response = await optimizationAPI.getZhuqueReadiness();
      mergeZhuqueReadiness(response.data);
    } catch (error) {
      mergeZhuqueReadiness({
        ready: false,
        connected: false,
        page_found: false,
        has_token: false,
        remaining_uses: -1,
        button_enabled: false,
        text_length_ok: true,
        message: '无法检测朱雀就绪状态',
        actions: ['微信扫码登录朱雀'],
      });
    }
  }, [mergeZhuqueReadiness]);

  const loadBrowserAgentStatus = useCallback(async () => {
    try {
      const response = await browserAgentAPI.getStatus();
      setBrowserAgentStatus(response.data);
      return response.data;
    } catch (error) {
      const fallbackStatus = {
        required: false,
        transport: 'auto',
        online: false,
        agents: [],
        message: '无法检测浏览器插件状态',
      };
      setBrowserAgentStatus(fallbackStatus);
      return fallbackStatus;
    }
  }, []);

  const loadZhuqueStatusPanel = useCallback(async () => {
    if (isLoadingZhuqueStatusRef.current) {
      return;
    }

    isLoadingZhuqueStatusRef.current = true;
    try {
      if (browserAgentRequired) {
        await loadBrowserAgentStatus();
        return;
      }
      await Promise.all([
        loadZhuqueAuthStatus(),
        withSoftTimeout(loadZhuqueReadiness(), ZHUQUE_READINESS_SOFT_TIMEOUT_MS),
        loadBrowserAgentStatus(),
      ]);
    } finally {
      isLoadingZhuqueStatusRef.current = false;
    }
  }, [browserAgentRequired, loadBrowserAgentStatus, loadZhuqueAuthStatus, loadZhuqueReadiness]);

  const refreshZhuqueFreeQuota = useCallback(async ({ silent = false } = {}) => {
    if (isRefreshingZhuqueQuotaRef.current || isStartingZhuqueLogin) {
      return;
    }

    isRefreshingZhuqueQuotaRef.current = true;
    try {
      setIsRefreshingZhuqueQuota(true);
      const response = browserAgentRequired
        ? await optimizationAPI.refreshZhuqueFreeQuota()
        : await optimizationAPI.syncZhuqueLocalBrowser();
      const remaining = extractZhuqueRemainingUses(response.data);
      if (remaining === undefined && response.data?.connected === false && response.data?.has_token === false) {
        clearZhuqueLoggedOutRemaining();
      }
      mergeZhuqueAuthStatus(response.data);
      mergeZhuqueReadiness(response.data);
      if (!silent) {
        if (remaining !== undefined) {
          toast.success(`${response.data?.has_token ? '朱雀剩余次数' : '朱雀免费次数'}：${remaining} 次`);
        } else if (response.data?.button_enabled || response.data?.ready) {
          toast.success(response.data?.message || '朱雀检测入口可用，剩余次数将在检测后同步');
        } else {
          toast.error(response.data?.message || '暂未探测到朱雀次数，请打开朱雀页面登录或稍后再刷新');
        }
      }
      setZhuqueFastPollUntil(Date.now() + ZHUQUE_STATUS_FAST_POLL_DURATION_MS);
    } catch (error) {
      if (!silent) {
        toast.error(error.response?.data?.detail || '刷新朱雀次数失败');
      }
    } finally {
      isRefreshingZhuqueQuotaRef.current = false;
      setIsRefreshingZhuqueQuota(false);
    }
  }, [browserAgentRequired, clearZhuqueLoggedOutRemaining, isStartingZhuqueLogin, mergeZhuqueAuthStatus, mergeZhuqueReadiness]);

  const handleCreateBrowserAgentPairing = useCallback(async () => {
    if (isCreatingBrowserAgentPairing) {
      return;
    }
    setIsCreatingBrowserAgentPairing(true);
    try {
      const response = await browserAgentAPI.createPairing();
      setBrowserAgentPairing(response.data);
      toast.success('浏览器插件配对码已生成，请在 Chrome 插件中输入');
      await loadBrowserAgentStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || '生成浏览器插件配对码失败');
    } finally {
      setIsCreatingBrowserAgentPairing(false);
    }
  }, [isCreatingBrowserAgentPairing, loadBrowserAgentStatus]);

  const handleRevokeBrowserAgent = useCallback(async (agentId) => {
    if (!agentId || isRevokingBrowserAgent) {
      return;
    }
    setIsRevokingBrowserAgent(true);
    try {
      await browserAgentAPI.revoke(agentId);
      setBrowserAgentPairing(null);
      await loadBrowserAgentStatus();
      toast.success('已撤销浏览器插件连接');
    } catch (error) {
      toast.error(error.response?.data?.detail || '撤销浏览器插件失败');
    } finally {
      setIsRevokingBrowserAgent(false);
    }
  }, [isRevokingBrowserAgent, loadBrowserAgentStatus]);

  const handleBrowserAgentPrimaryAction = useCallback(async () => {
    if (!browserAgentOnline) {
      await handleCreateBrowserAgentPairing();
      return;
    }
    window.open(ZHUQUE_DETECT_PAGE_URL, '_blank', 'noopener,noreferrer');
    toast('已打开本机朱雀页面；游客次数可直接检测，页面要求时再完成登录/验证码。');
  }, [browserAgentOnline, handleCreateBrowserAgentPairing]);

  const handleSyncBrowserAgentZhuqueStatus = useCallback(async () => {
    if (isSyncingBrowserAgentZhuque) {
      return;
    }
    setIsSyncingBrowserAgentZhuque(true);
    try {
      const syncResult = await requestBrowserAgentZhuqueRefresh({ focus: false, timeoutMs: 5000 });
      const latestStatus = await loadBrowserAgentStatus();
      if (!syncResult) {
        toast.error('本机插件未响应同步请求，请重新加载 0.1.10 或更高版本插件');
        return;
      }
      if (syncResult.ok === false) {
        toast.error(syncResult.message || '插件未能同步朱雀状态，请确认已安装最新版插件并刷新页面');
        return;
      }
      const zhuqueStatus = mergeBrowserAgentZhuqueStatuses(latestStatus?.zhuque, syncResult.zhuque);
      setBrowserAgentStatus((current) => ({ ...(current || latestStatus || {}), zhuque: zhuqueStatus }));
      if (zhuqueStatus?.logged_in || zhuqueStatus?.user_name) {
        const remaining = extractZhuqueRemainingUses(zhuqueStatus);
        if (remaining !== undefined) {
          toast.success(`已同步本机朱雀登录状态，剩余 ${remaining} 次`);
        } else {
          toast('朱雀登录状态已同步，但当前页面暂未返回剩余次数');
        }
        return;
      }
      if (zhuqueStatus?.page_found && zhuqueStatus?.button_enabled) {
        const remaining = extractZhuqueRemainingUses(zhuqueStatus);
        toast.success(remaining !== undefined ? `朱雀游客检测可用，剩余 ${remaining} 次` : '朱雀游客检测可用，剩余次数将在检测后同步');
        return;
      }
      toast('已请求同步；如果刚登录朱雀，请确认朱雀页面已打开并等待插件识别。');
    } finally {
      setIsSyncingBrowserAgentZhuque(false);
    }
  }, [isSyncingBrowserAgentZhuque, loadBrowserAgentStatus]);

  const handleOpenZhuqueVerificationWindow = useCallback(async (session, { auto = false } = {}) => {
    if (isStartingZhuqueLogin) {
      return;
    }

    try {
      setIsStartingZhuqueLogin(true);
      setShowZhuqueLoginModal(false);
      if (auto) {
        toast('朱雀检测失败，需要人工确认，正在打开真实浏览器窗口…');
      }
      const response = await optimizationAPI.startZhuqueLogin({ syncSession: true, mode: 'local_window' });
      const payload = response.data || {};
      const message = payload.message || '已请求打开朱雀验证窗口，请在真实浏览器完成页面验证。';
      if (payload.command) {
        console.info('Zhuque verification command:', payload.command);
      }
      setZhuqueFastPollUntil(Date.now() + ZHUQUE_STATUS_FAST_POLL_DURATION_MS);
      await loadZhuqueStatusPanel();
      if (payload.status === 'manual_required' || payload.status === 'missing_script' || payload.status === 'error') {
        toast.error(message);
      } else {
        toast.success(message);
      }
    } catch (error) {
      const manualInfo = getZhuqueManualCheckInfo(session);
      toast.error(error.response?.data?.detail || manualInfo?.message || '打开朱雀验证窗口失败，请稍后再试');
    } finally {
      setIsStartingZhuqueLogin(false);
    }
  }, [isStartingZhuqueLogin, loadZhuqueStatusPanel]);

  const updateSessionProgress = useCallback(async (sessionId) => {
    try {
      const response = await optimizationAPI.getSessionProgress(sessionId);
      const progress = response.data;
      let mergedSessionForManualCheck = null;

      // 更新会话列表中的进度 - 只在数据有变化时更新
      setSessions(prev => {
        const target = prev.find(s => s.session_id === sessionId);
        if (target) {
          mergedSessionForManualCheck = { ...target, ...progress };
        }
        if (target && target.progress === progress.progress && target.status === progress.status) {
          return prev; // 无变化，不触发重渲染
        }
        return prev.map(s =>
          s.session_id === sessionId ? { ...s, ...progress } : s
        );
      });

      // 如果会话完成,刷新列表
      if (progress.status === 'completed' || progress.status === 'failed') {
        setActiveSession(null);
        loadSessions();

        if (browserAgentRequired) {
          requestBrowserAgentZhuqueRefresh({ timeoutMs: 5000 })
            .then(() => loadBrowserAgentStatus())
            .catch(() => loadBrowserAgentStatus());
        }
        if (progress.status === 'completed') {
          toast.success('优化完成!');
        } else {
          const latestSession = mergedSessionForManualCheck
            || sessionsRef.current.find(s => s.session_id === sessionId)
            || progress;
          const zhuqueManualCheckInfo = getZhuqueManualCheckInfo(latestSession);
          const failureMessage = progress.error_message || zhuqueManualCheckInfo?.message || '网络超时，请稍后继续处理';
          toast.error(`优化失败: ${failureMessage}`);
          if (
            zhuqueManualCheckInfo
            && !zhuqueManualVerificationOpenedSessionRef.current.has(sessionId)
          ) {
            zhuqueManualVerificationOpenedSessionRef.current.add(sessionId);
            await handleOpenZhuqueVerificationWindow(latestSession, { auto: true });
          }
        }
      } else {
        zhuqueManualVerificationOpenedSessionRef.current.delete(sessionId);
      }
    } catch (error) {
      console.error('更新进度失败:', error);
    }
  }, [browserAgentRequired, handleOpenZhuqueVerificationWindow, loadBrowserAgentStatus, loadSessions]);

  // 初始加载 - 只在组件挂载时执行一次
  useEffect(() => {
    loadProjects();
    loadQueueStatus();
    loadAccountState();
    loadAnnouncements();
    loadBrowserAgentStatus();
  }, [loadProjects, loadQueueStatus, loadAccountState, loadAnnouncements, loadBrowserAgentStatus]);

  useEffect(() => {
    setSessions([]);
    loadSessions(activeProjectId);
  }, [activeProjectId, loadSessions]);

  // 队列状态轮询 - 独立的 useEffect，避免与初始加载混淆
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      loadQueueStatus();
    }, WORKSPACE_QUEUE_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadQueueStatus]);

  useEffect(() => {
    // 如果有活跃会话,每4秒更新进度（进一步降低频率）
    if (activeSession) {
      const interval = setInterval(() => {
        updateSessionProgress(activeSession);
      }, ACTIVE_SESSION_POLL_INTERVAL_MS);
      return () => clearInterval(interval);
    }
  }, [activeSession, updateSessionProgress]);

  useEffect(() => {
    try {
      window.localStorage.setItem(WORKSPACE_PROCESSING_MODE_STORAGE_KEY, processingMode);
    } catch {
      // localStorage 可能被浏览器隐私策略禁用；此时保留本次页面内选择即可。
    }
  }, [processingMode]);

  useEffect(() => {
    try {
      window.localStorage.setItem(WORKSPACE_BILLING_MODE_STORAGE_KEY, billingMode);
    } catch {
      // localStorage 可能被浏览器隐私策略禁用；此时保留本次页面内选择即可。
    }
  }, [billingMode]);

  useEffect(() => {
    if (processingMode !== 'ai_detect_reduce') {
      hasAutoRefreshedZhuqueQuotaRef.current = false;
      return;
    }
    if (!browserAgentStatusLoaded) {
      return;
    }

    let isCancelled = false;
    const loadInitialZhuqueStatus = async () => {
      if (browserAgentRequired) {
        if (browserAgentOnline) {
          await requestBrowserAgentZhuqueRefresh({ timeoutMs: 3000 });
        }
        await loadZhuqueStatusPanel();
        if (!isCancelled) {
          hasAutoRefreshedZhuqueQuotaRef.current = true;
        }
        return;
      }
      await loadZhuqueStatusPanel();
      if (isCancelled || hasAutoRefreshedZhuqueQuotaRef.current) {
        return;
      }
      hasAutoRefreshedZhuqueQuotaRef.current = true;
      await refreshZhuqueFreeQuota({ silent: true });
    };
    loadInitialZhuqueStatus();

    const pollInterval = Date.now() < zhuqueFastPollUntil
      ? ZHUQUE_STATUS_FAST_POLL_INTERVAL_MS
      : ZHUQUE_STATUS_POLL_INTERVAL_MS;
    const interval = setInterval(() => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      loadZhuqueStatusPanel();
    }, pollInterval);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [browserAgentOnline, browserAgentRequired, browserAgentStatusLoaded, loadZhuqueStatusPanel, processingMode, refreshZhuqueFreeQuota, zhuqueFastPollUntil]);

  const mergeZhuqueLoginSession = useCallback((payload) => {
    if (!payload) {
      return;
    }
    setZhuqueLoginSession((current) => ({ ...(current || {}), ...payload }));
    if (payload.session_id) {
      zhuqueLoginSessionIdRef.current = payload.session_id;
    }
    if (payload.connected || payload.has_token || payload.status === 'logged_in') {
      mergeZhuqueAuthStatus({
        ...payload,
        status: 'connected',
        connected: true,
        ready: true,
        has_token: payload.has_token ?? true,
        button_enabled: true,
      });
      mergeZhuqueReadiness({
        ...payload,
        ready: true,
        connected: true,
        page_found: true,
        has_token: payload.has_token ?? true,
        button_enabled: true,
        text_length_ok: true,
      });
    }
  }, [mergeZhuqueAuthStatus, mergeZhuqueReadiness]);

  useEffect(() => {
    if (!showZhuqueLoginModal || !zhuqueLoginSession?.session_id) {
      return;
    }
    const terminalStatuses = new Set(['logged_in', 'expired', 'error', 'cancelled', 'manual_required', 'not_found']);
    if (terminalStatuses.has(zhuqueLoginSession.status)) {
      return;
    }

    const pollLoginStatus = async () => {
      try {
        const response = await optimizationAPI.getZhuqueLoginStatus(zhuqueLoginSession.session_id);
        mergeZhuqueLoginSession(response.data);
        if (response.data?.status === 'logged_in') {
          setZhuqueFastPollUntil(Date.now() + ZHUQUE_STATUS_FAST_POLL_DURATION_MS);
          await loadZhuqueStatusPanel();
          toast.success('朱雀扫码登录成功');
        }
      } catch (error) {
        mergeZhuqueLoginSession({
          session_id: zhuqueLoginSession.session_id,
          status: 'error',
          message: error.response?.data?.detail || '朱雀扫码状态同步失败',
        });
      }
    };

    pollLoginStatus();
    const interval = setInterval(pollLoginStatus, ZHUQUE_LOGIN_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [loadZhuqueStatusPanel, mergeZhuqueLoginSession, showZhuqueLoginModal, zhuqueLoginSession?.session_id, zhuqueLoginSession?.status]);

  const handleCreateProject = useCallback(async (e) => {
    e.preventDefault();
    if (!projectTitle.trim()) {
      toast.error('请输入论文题目');
      return;
    }

    try {
      const response = await projectAPI.create({
        title: projectTitle.trim(),
        description: projectDescription.trim() || null,
      });
      setProjects((current) => [response.data, ...current]);
      setActiveProjectId(response.data.id);
      setSessions([]);
      await loadSessions(response.data.id);
      setProjectTitle('');
      setProjectDescription('');
      setShowProjectForm(false);
      toast.success('论文项目已创建');
    } catch (error) {
      toast.error(error.response?.data?.detail || '创建论文项目失败');
    }
  }, [loadSessions, projectDescription, projectTitle]);

  const handleArchiveProject = useCallback(async (project) => {
    const confirmArchive = window.confirm(`确认归档论文项目「${project.title}」吗？项目下的历史记录不会被删除。`);
    if (!confirmArchive) {
      return;
    }

    try {
      await projectAPI.archive(project.id);
      const remaining = projects.filter((item) => item.id !== project.id);
      setProjects(remaining);
      if (activeProjectId === project.id) {
        activeProjectIdRef.current = null;
        setActiveProjectId(null);
        await loadSessions(null);
      }
      toast.success('论文项目已归档，历史记录仍可在全部历史查看');
    } catch (error) {
      toast.error(error.response?.data?.detail || '归档失败');
    }
  }, [activeProjectId, loadSessions, projects]);

  const handleStartEditProject = useCallback((project) => {
    setEditingProjectId(project.id);
    setEditProjectTitle(project.title);
    setEditProjectDescription(project.description || '');
  }, []);

  const handleCancelEditProject = useCallback(() => {
    setEditingProjectId(null);
    setEditProjectTitle('');
    setEditProjectDescription('');
  }, []);

  const handleUpdateProject = useCallback(async (e) => {
    e.preventDefault();
    if (!editingProjectId) {
      return;
    }
    if (!editProjectTitle.trim()) {
      toast.error('请输入论文题目');
      return;
    }

    try {
      const response = await projectAPI.update(editingProjectId, {
        title: editProjectTitle.trim(),
        description: editProjectDescription.trim() || null,
      });
      setProjects((current) => current.map((project) => (
        project.id === editingProjectId ? response.data : project
      )));
      handleCancelEditProject();
      toast.success('论文项目已更新');
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新论文项目失败');
    }
  }, [editProjectDescription, editProjectTitle, editingProjectId, handleCancelEditProject]);

  const handleProjectScopeChange = useCallback((event) => {
    const value = event.target.value;
    const nextProjectId = value === 'all' ? null : Number(value);
    setEditingProjectId(null);
    setEditProjectTitle('');
    setEditProjectDescription('');
    setShowHistoryFilters(false);
    setOpenProjectMenuSessionId(null);
    setActiveProjectId(nextProjectId);
  }, []);

  const handleHistoryStatusFilterChange = useCallback((statusId) => {
    setHistoryStatusFilter(statusId);
    setShowHistoryFilters(false);
  }, []);

  const handleToggleProjectMenu = useCallback((sessionId) => {
    setShowHistoryFilters(false);
    setOpenProjectMenuSessionId(sessionId);
  }, []);

  const handleMoveSessionToProject = useCallback(async (session, projectId) => {
    if (movingSessionId) {
      return;
    }

    const targetProject = projectId === null
      ? null
      : projects.find((project) => project.id === projectId);
    const targetLabel = targetProject?.title || '未归档历史';

    try {
      setMovingSessionId(session.session_id);
      setOpenProjectMenuSessionId(null);
      const response = await optimizationAPI.updateSessionProject(session.session_id, {
        project_id: projectId,
      });
      const updatedSession = response.data;
      setSessions((current) => {
        const shouldRemoveFromCurrentScope = (
          activeProjectId === 0 && updatedSession.project_id !== null
        ) || (
          typeof activeProjectId === 'number'
          && activeProjectId > 0
          && updatedSession.project_id !== activeProjectId
        );

        if (shouldRemoveFromCurrentScope) {
          return current.filter((item) => item.session_id !== session.session_id);
        }

        return current.map((item) => (
          item.session_id === session.session_id ? { ...item, ...updatedSession } : item
        ));
      });
      toast.success(`已归入「${targetLabel}」`);
    } catch (error) {
      toast.error(error.response?.data?.detail || '归入项目失败');
    } finally {
      setMovingSessionId(null);
    }
  }, [activeProjectId, movingSessionId, projects]);

  const handleChooseDocumentFile = useCallback(() => {
    if (isParsingDocument) {
      return;
    }
    documentFileInputRef.current?.click();
  }, [isParsingDocument]);

  const handleDocumentUpload = useCallback(async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || isParsingDocument) {
      return;
    }

    const filename = file.name || '';
    if (!/\.(docx|pdf|md|markdown|txt)$/i.test(filename)) {
      toast.error('仅支持上传 PDF(.pdf)、Word(.docx)、Markdown(.md/.markdown) 和 TXT(.txt)');
      return;
    }

    if (text.trim()) {
      const shouldReplace = window.confirm('上传解析会替换当前论文内容，是否继续？');
      if (!shouldReplace) {
        return;
      }
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setIsParsingDocument(true);
      const response = await optimizationAPI.parseDocument(formData);
      const parsed = response.data || {};
      setText(parsed.text || '');
      setDocumentParse({
        document_format: parsed.document_format || null,
        parse_engine: parsed.parse_engine || parsed.parser || null,
        parse_fallback_used: Boolean(parsed.parse_fallback_used),
        parse_trace: parsed.parse_trace || null,
        parser: parsed.parser || null,
        segments: Array.isArray(parsed.segments) ? parsed.segments : [],
      });
      if (!taskTitle.trim()) {
        setTaskTitle(getDocumentTitleFromFilename(parsed.filename || filename));
      }
      const warningText = Array.isArray(parsed.warnings) && parsed.warnings.length
        ? `；${parsed.warnings.join('；')}`
        : '';
      if (parsed.parse_fallback_used) {
        toast.success(`文件解析完成，但 MinerU 失败，已回退 MarkItDown，结构识别精度会降低；已导入 ${parsed.char_count ?? 0} 字符${warningText}`);
      } else if ((parsed.parse_engine || parsed.parser) === 'mineru') {
        toast.success(`文件解析完成，已使用 MinerU 高精度解析；已导入 ${parsed.char_count ?? 0} 字符${warningText}`);
      } else {
        toast.success(`文件解析完成，已导入 ${parsed.char_count ?? 0} 字符${warningText}`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '文件解析失败');
    } finally {
      setIsParsingDocument(false);
    }
  }, [isParsingDocument, taskTitle, text]);

  const handleStartOptimization = useCallback(async () => {
    if (!text.trim()) {
      toast.error('请输入要优化的文本');
      return;
    }

    if (isSubmitting) {
      return;
    }

    if (processingMode !== 'ai_detect_reduce' && billingMode === 'platform' && credits && !credits.is_unlimited && credits.credit_balance < estimatedCredits) {
      toast.error(`平台啤酒不足，本次需要 ${estimatedCredits} 啤酒，当前剩余 ${credits.credit_balance ?? 0} 啤酒`);
      return;
    }

    if (billingMode === 'byok' && !hasProviderConfig) {
      toast.error('请先保存自带 API 配置');
      navigate('/api-settings');
      return;
    }

    try {
      setIsSubmitting(true);
      if (processingMode === 'ai_detect_reduce' && browserAgentRequired && !browserAgentOnline) {
        const latestAgentStatus = await loadBrowserAgentStatus();
        if (!latestAgentStatus?.online) {
          toast.error('VPS 朱雀检测需要先连接本机 Chrome 插件');
          return;
        }
      }
      if (processingMode === 'ai_detect_reduce') {
        const preflightResponse = await optimizationAPI.preflightZhuqueTask({
          original_text: text,
          processing_mode: processingMode,
          billing_mode: billingMode,
        });
        const preflight = preflightResponse.data;
        mergeZhuqueReadiness(preflight);
        if (!preflight.ready) {
          toast.error(preflight.message || '朱雀尚未就绪');
          return;
        }
        if (preflight.estimated_max_round_credits > 0) {
          const zhuqueReadyLabel = preflight.has_token ? '朱雀账号检测链路已就绪' : '朱雀免费检测次数可用';
          toast(`${zhuqueReadyLabel}，预计最多消耗 ${preflight.estimated_max_round_credits} 啤酒（仅实际降重时扣）`);
        } else {
          toast.success(preflight.has_token ? '朱雀账号检测链路已就绪' : '朱雀免费检测次数可用');
        }
      }

      const response = await optimizationAPI.startOptimization({
        original_text: text,
        processing_mode: processingMode,
        billing_mode: billingMode,
        project_id: activeProjectId && activeProjectId !== 0 ? activeProjectId : null,
        task_title: taskTitle.trim() || null,
        document_parse: documentParse,
      });

      setActiveSession(response.data.session_id);
      toast.success('优化任务已启动');
      setText('');
      setTaskTitle('');
      setDocumentParse(null);
      loadAccountState();
      loadSessions(activeProjectId);
    } catch (error) {
      const responseDetail = error.response?.data?.detail;
      const validationDetail = Array.isArray(responseDetail)
        ? responseDetail.map((item) => item?.msg).filter(Boolean).join('；')
        : '';
      const failureDetail = typeof responseDetail === 'string' && responseDetail.trim()
        ? responseDetail
        : validationDetail
          || (error.code === 'ECONNABORTED' ? '请求超时，请检查后台与数据库状态' : '')
          || (error.response?.status ? `服务返回 HTTP ${error.response.status}，请检查后台日志` : '')
          || error.message
          || '无法连接后台服务';
      toast.error(`启动优化失败: ${failureDetail}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [activeProjectId, taskTitle, text, processingMode, billingMode, credits, estimatedCredits, hasProviderConfig, isSubmitting, loadSessions, loadAccountState, mergeZhuqueReadiness, navigate, documentParse, browserAgentOnline, browserAgentRequired, loadBrowserAgentStatus]);

  const handleStartZhuqueLogin = useCallback(async () => {
    if (isStartingZhuqueLogin) {
      return;
    }
    if (browserAgentRequired) {
      toast('VPS 插件模式不使用服务器扫码登录；请保持本机 Chrome 插件在线，游客检测不可用或页面要求时再登录/验证。');
      return;
    }

    try {
      setIsStartingZhuqueLogin(true);
      setShowZhuqueLoginModal(false);
      const response = await optimizationAPI.openZhuqueLocalBrowser({ syncSession: true });
      mergeZhuqueAuthStatus(response.data);
      mergeZhuqueReadiness(response.data);
      setZhuqueFastPollUntil(Date.now() + ZHUQUE_STATUS_FAST_POLL_DURATION_MS);
      await loadZhuqueStatusPanel();
      const launchMessage = response.data?.message || '已打开本机朱雀页面，请在该窗口完成登录/验证码后回到工作台同步状态';
      if (response.data?.status === 'manual_required' || response.data?.status === 'error' || response.data?.status === 'missing_script') {
        toast.error(launchMessage);
      } else {
        toast.success(launchMessage);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '打开本机朱雀页面失败');
    } finally {
      setIsStartingZhuqueLogin(false);
    }
  }, [browserAgentRequired, isStartingZhuqueLogin, loadZhuqueStatusPanel, mergeZhuqueAuthStatus, mergeZhuqueReadiness]);

  const handleLogoutZhuque = useCallback(async () => {
    if (isStartingZhuqueLogin) {
      return;
    }
    const shouldLogout = window.confirm('确认退出当前朱雀登录？退出后会回到未登录免费次数路径。');
    if (!shouldLogout) {
      return;
    }
    try {
      setIsStartingZhuqueLogin(true);
      const response = await optimizationAPI.logoutZhuque();
      mergeZhuqueAuthStatus({
        ...response.data,
        connected: false,
        ready: false,
        has_token: false,
        user_name: '',
        remaining_uses: response.data?.remaining_uses ?? -1,
      });
      mergeZhuqueReadiness({
        ...response.data,
        connected: false,
        ready: false,
        has_token: false,
        page_found: false,
        user_name: '',
        remaining_uses: response.data?.remaining_uses ?? -1,
      });
      setZhuqueLoginSession(null);
      zhuqueLoginSessionIdRef.current = '';
      setZhuqueFastPollUntil(Date.now() + ZHUQUE_STATUS_FAST_POLL_DURATION_MS);
      toast.success(response.data?.message || '已退出朱雀登录');
      await loadZhuqueStatusPanel();
    } catch (error) {
      toast.error(error.response?.data?.detail || '退出朱雀登录失败');
    } finally {
      setIsStartingZhuqueLogin(false);
    }
  }, [isStartingZhuqueLogin, loadZhuqueStatusPanel, mergeZhuqueAuthStatus, mergeZhuqueReadiness]);

  const handleRefreshZhuqueFreeQuota = useCallback(() => {
    refreshZhuqueFreeQuota({ silent: false });
  }, [refreshZhuqueFreeQuota]);

  const handleCloseZhuqueLoginModal = useCallback(async () => {
    const sessionId = zhuqueLoginSessionIdRef.current;
    setShowZhuqueLoginModal(false);
    if (sessionId && zhuqueLoginSession?.status && !['logged_in', 'expired', 'error', 'cancelled', 'manual_required'].includes(zhuqueLoginSession.status)) {
      try {
        await optimizationAPI.cancelZhuqueLogin(sessionId);
      } catch {
        // 关闭弹窗失败不影响主流程，服务端会按超时清理。
      }
    }
  }, [zhuqueLoginSession?.status]);

  const handleDeleteSession = useCallback(async (session) => {
    const confirmDelete = window.confirm('确认删除该会话及其结果吗?');
    if (!confirmDelete) {
      return;
    }

    try {
      await optimizationAPI.deleteSession(session.session_id);
      if (activeSession === session.session_id) {
        setActiveSession(null);
      }
      toast.success('会话已删除');
      await loadSessions();
    } catch (error) {
      console.error('删除会话失败:', error);
      toast.error(error.response?.data?.detail || '删除会话失败');
    }
  }, [activeSession, loadSessions]);

  const handleViewSession = useCallback((sessionId) => {
    navigate(`/session/${sessionId}`);
  }, [navigate]);

  const handleRetrySegment = useCallback((session) => {
    if (session.status !== 'failed') {
      return;
    }

    setRetryDialogSession(session);
  }, []);

  const confirmRetrySegment = useCallback(async () => {
    if (!retryDialogSession || isRetrying) {
      return;
    }

    if (billingMode === 'byok' && !hasProviderConfig) {
      setRetryDialogSession(null);
      toast.error('请先保存自带 API 配置');
      navigate('/api-settings');
      return;
    }

    try {
      setIsRetrying(true);
      const response = await optimizationAPI.retryFailedSegments(retryDialogSession.session_id, {
        billing_mode: billingMode,
      });
      setActiveSession(retryDialogSession.session_id);
      toast.success(response.data?.message || '已重新继续处理未完成段落');
      await loadSessions();
      await loadAccountState();
      setRetryDialogSession(null);
    } catch (error) {
      console.error('重试失败:', error);
      toast.error(error.response?.data?.detail || '重试失败，请稍后再试');
    } finally {
      setIsRetrying(false);
    }
  }, [billingMode, hasProviderConfig, isRetrying, loadAccountState, loadSessions, navigate, retryDialogSession]);

  // 使用 useMemo 缓存当前活跃会话的数据
  const currentActiveSessionData = useMemo(() => {
    return sessions.find(s => s.session_id === activeSession);
  }, [sessions, activeSession]);


  return (
    <div className="gank-app-page aurora-app-page">
      <div className="gank-ambient-orb orb-one" />
      <div className="gank-ambient-orb orb-two" />
      <div className="gank-ambient-orb orb-three" />

      {/* 顶部导航栏 */}
      <header className="sticky top-0 z-50">
        <nav className="apple-global-nav aurora-topbar">
          <div className="mx-auto flex min-h-[68px] max-w-[1760px] items-center justify-between gap-4 px-5 sm:px-8 lg:px-12">
            <div className="flex items-center gap-3">
              <BrandLogo size="md" showText className="aurora-brand-logo" />
              <span className="sr-only">AI PAPER RECONSTRUCTION</span>
            </div>

            <div className="flex min-w-0 items-center gap-3 overflow-x-auto pb-1 sm:pb-0">
              {queueStatus && (
                <div className="hidden items-center gap-3 text-[14px] md:flex">
                  <div className="aurora-nav-pill">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.13)]" />
                    <span className="font-semibold">在线 {queueStatus.online_users ?? 0}</span>
                  </div>
                  <div className="aurora-nav-pill aurora-nav-pill-blue">
                    <ListChecks className="h-4 w-4" />
                    <span className="font-semibold">处理中 {queueStatus.current_users}/{queueStatus.max_users}</span>
                  </div>
                  {queueStatus.queue_length > 0 && (
                    <div className="aurora-nav-pill">
                      <Clock className="h-4 w-4 text-slate-500" />
                      <span className="font-semibold">{queueStatus.queue_length} 排队</span>
                    </div>
                  )}
                </div>
              )}

              <UserMenu credits={credits} />
            </div>
          </div>
        </nav>
        <div className="apple-subnav aurora-contract-strip" aria-hidden="true">
          <span>朱雀检测</span>
          <span>论文重构</span>
          <span>全文复检</span>
        </div>
      </header>

      <main className="aurora-page-shell relative z-[1] mx-auto max-w-[1760px] px-5 pb-10 pt-8 sm:px-8 lg:px-12">
        {announcements.length > 0 && (
          <div className="mb-6 space-y-3">
            {announcements.slice(0, 3).map((announcement) => (
              <div key={announcement.id} className="aurora-announcement">
                <span className={`inline-flex w-fit shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${getAnnouncementCategoryClass(announcement.category)}`}>
                  {getAnnouncementCategoryLabel(announcement.category)}
                </span>
                <div className="min-w-0">
                  <div className="break-words text-sm font-semibold text-slate-950">{announcement.title}</div>
                  <MarkdownPreview content={announcement.content} className="mt-1" compact />
                </div>
              </div>
            ))}
          </div>
        )}

        <section className="mb-7 flex flex-col gap-2 pl-1">
          <div className="flex items-center gap-5">
            <span className="h-11 w-1.5 rounded-full bg-gradient-to-b from-cyan-400 to-sky-500 shadow-[0_0_20px_rgba(34,211,238,0.42)]" />
            <div>
              <h1 className="text-[34px] font-semibold leading-tight tracking-[-0.045em] text-slate-950 sm:text-[38px]">论文重构</h1>
              <p className="mt-2 text-[16px] leading-6 text-slate-500">
                选择合适的模式，输入论文内容，AI 将帮助您重构与优化论文质量
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,2.6fr)_minmax(360px,1fr)]">
          <section id="new-task" className="aurora-workbench-card apple-product-tile apple-paper-stage gank-tabbit-hero gank-liquid-panel scroll-mt-24">
            <div className="grid min-h-[690px] gap-0 lg:grid-cols-[390px_minmax(0,1fr)]">
              <aside className="aurora-control-column">
                <div>
                  <div className="aurora-section-heading">
                    <ListChecks className="h-4 w-4 text-[#6680bf]" />
                    <span>选择模式</span>
                  </div>
                  <div className="gank-segmented-control aurora-mode-list">
                    {PROCESSING_MODE_OPTIONS.map((mode) => {
                      const Icon = mode.icon;
                      const selected = processingMode === mode.id;
                      return (
                        <label
                          key={mode.id}
                          className={`aurora-mode-card ${selected ? 'aurora-mode-card-active gank-glass-choice-active' : 'gank-glass-choice'}`}
                        >
                          <input
                            type="radio"
                            name="processingMode"
                            value={mode.id}
                            checked={selected}
                            onChange={handleProcessingModeChange}
                            className="hidden"
                          />
                          <span className={`aurora-mode-icon ${getModeToneClass(mode.tone)}`}>
                            <Icon className="h-6 w-6" />
                          </span>
                          <span className="min-w-0">
                            <span className="block text-[16px] font-semibold tracking-[-0.01em] text-slate-950">{mode.title}</span>
                            <span className="mt-1 block text-[13px] leading-5 text-slate-500">{mode.desc}</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <div className="aurora-control-divider" />

                <div>
                  <div className="aurora-section-heading">
                    <CircleDollarSign className="h-4 w-4 text-[#6680bf]" />
                    <span>计费方式</span>
                  </div>
                  <div className="gank-segmented-control aurora-mode-list aurora-billing-list">
                    <label className={`aurora-mode-card aurora-billing-card ${billingMode === 'platform' ? 'aurora-mode-card-active aurora-billing-card-active gank-glass-choice-active' : 'gank-glass-choice'}`}>
                      <input
                        type="radio"
                        name="billingMode"
                        value="platform"
                        checked={billingMode === 'platform'}
                        onChange={(event) => setBillingMode(event.target.value)}
                        className="hidden"
                      />
                      <span className="aurora-mode-icon aurora-icon-blue">
                        <Layers className="h-6 w-6" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[16px] font-semibold tracking-[-0.01em] text-slate-950">平台模式</span>
                        <span className="mt-1 block text-[13px] leading-5 text-slate-500">
                          使用平台模型，1 啤酒 = 1000 非空白字符
                        </span>
                        <span className="mt-1 block text-[12px] text-slate-400">
                          剩余 {credits?.is_unlimited ? '无限啤酒' : `${credits?.credit_balance ?? '-'} 啤酒`}
                          {text.trim() && processingMode !== 'ai_detect_reduce' ? <> · 预计消耗 {estimatedCredits} 啤酒</> : ''}
                          {processingMode === 'ai_detect_reduce' ? ' · 检测不扣啤酒' : ''}
                        </span>
                      </span>
                    </label>

                    <label className={`aurora-mode-card aurora-billing-card ${billingMode === 'byok' ? 'aurora-mode-card-active aurora-billing-card-active gank-glass-choice-active' : 'gank-glass-choice'}`}>
                      <input
                        type="radio"
                        name="billingMode"
                        value="byok"
                        checked={billingMode === 'byok'}
                        onChange={(event) => setBillingMode(event.target.value)}
                        className="hidden"
                      />
                      <span className="aurora-mode-icon aurora-icon-navy">
                        <LinkIcon className="h-6 w-6" />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[16px] font-semibold tracking-[-0.01em] text-slate-950">自带API模式</span>
                        <span className="mt-1 block text-[13px] leading-5 text-slate-500">
                          接入自有API Key，按实际用量
                        </span>
                        <span className="mt-1 block text-[12px] text-slate-400">
                          {hasProviderConfig ? '已保存配置，不消耗啤酒' : '需要先保存 API 配置'}
                        </span>
                      </span>
                    </label>
                  </div>
                </div>
              </aside>

              <section className="aurora-editor-column">
                {processingMode === 'ai_detect_reduce' && (
                  <div className="aurora-zhuque-panel mb-6">
                    <div className="aurora-zhuque-status-card">
                      <div className="aurora-zhuque-title">
                        {/* source aliases kept for static contracts: startZhuqueBrowser loadZhuqueBrowserStatus zhuqueBrowserStatus?.connected */}
                        <div className="aurora-zhuque-title-copy">
                          <p>朱雀 AI 检测</p>
                          {!browserAgentRequired && (
                            <span
                              className={`aurora-zhuque-account ${zhuqueDisplayConnected ? 'is-connected' : ''}`}
                              title={zhuqueConnected ? `朱雀登录用户：${zhuqueAccountLabel}` : '朱雀未登录'}
                            >
                              {zhuqueDisplayAccountLabel}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="aurora-zhuque-actions">
                        <button
                          type="button"
                          onClick={browserAgentRequired ? handleBrowserAgentPrimaryAction : handleStartZhuqueLogin}
                          disabled={browserAgentRequired ? isCreatingBrowserAgentPairing : isStartingZhuqueLogin}
                          className={`aurora-zhuque-login-button ${zhuqueDisplayConnected ? 'is-ready' : ''}`}
                          aria-label={zhuquePrimaryActionLabel}
                          title={zhuquePrimaryActionTitle}
                        >
                          {(isStartingZhuqueLogin || isCreatingBrowserAgentPairing) ? (
                            <>
                              <div className="h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                              处理中
                            </>
                          ) : browserAgentRequired && browserAgentOnline ? (
                            <>
                              <ExternalLink className="h-5 w-5" />
                              {zhuquePrimaryActionLabel}
                            </>
                          ) : zhuqueDisplayConnected ? (
                            <>
                              <CheckCircle className="h-6 w-6" />
                              {zhuquePrimaryActionLabel}
                            </>
                          ) : (
                            <>
                              <ExternalLink className="h-5 w-5" />
                              {zhuquePrimaryActionLabel}
                            </>
                          )}
                        </button>
                        {!browserAgentRequired && zhuqueConnected && (
                          <button
                            type="button"
                            onClick={handleLogoutZhuque}
                            disabled={isStartingZhuqueLogin}
                            className="aurora-zhuque-logout-button"
                            aria-label="退出朱雀登录"
                            title="清除当前用户保存的朱雀凭证，回到未登录免费次数"
                          >
                            退出
                          </button>
                        )}
                      </div>
                      <div className="aurora-zhuque-metrics gank-glass-status-grid">
                        <div className="aurora-zhuque-metric">
                          <span>朱雀账号</span>
                          <strong className={zhuqueDisplayConnected ? 'is-connected' : 'is-disconnected'}>
                            <i />
                            {browserAgentRequired ? (zhuqueDisplayConnected ? (browserAgentZhuqueAccountName || '已登录') : (browserAgentZhuqueAnonymousReady ? '游客模式' : '未登录')) : (zhuqueDisplayConnected ? (zhuqueAccountName || '已登录') : '未登录')}
                          </strong>
                        </div>
                        <div className="aurora-zhuque-metric">
                          <span>剩余次数</span>
                          <div className="aurora-zhuque-quota-inline">
                            <strong>{zhuqueRemainingDisplayLabel}</strong>
                            <button
                              type="button"
                              onClick={browserAgentRequired ? handleSyncBrowserAgentZhuqueStatus : handleRefreshZhuqueFreeQuota}
                              disabled={browserAgentRequired ? isSyncingBrowserAgentZhuque : (isRefreshingZhuqueQuota || isStartingZhuqueLogin)}
                              className="aurora-zhuque-quota-refresh"
                              aria-label={browserAgentRequired ? '同步朱雀登录和剩余次数' : '刷新朱雀剩余次数'}
                              title={browserAgentRequired ? '同步本机插件上报的朱雀登录状态和剩余次数' : (zhuqueConnected ? '刷新朱雀账号剩余次数' : '检测朱雀未登录免费次数')}
                            >
                              <RefreshCw className={(browserAgentRequired ? isSyncingBrowserAgentZhuque : isRefreshingZhuqueQuota) ? 'animate-spin' : ''} />
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className={`aurora-browser-agent-card mt-1 rounded-[14px] border px-3 py-2 ${browserAgentRequired ? 'border-blue-100 bg-blue-50/70' : 'border-slate-200 bg-white/70'}`}>
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-[13px] font-semibold text-slate-500">检测传输</span>
                              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${browserAgentRequired ? (browserAgentOnline ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700') : 'bg-slate-100 text-slate-600'}`}>
                                {browserAgentStatusLabel}
                              </span>
                              <span className="rounded-full bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-500">{browserAgentTransport}</span>
                              {browserAgentPrimary && (
                                <span className="truncate text-[12px] text-slate-400">
                                  当前设备：{browserAgentPrimary.name || browserAgentPrimary.agent_id}
                                  {browserAgentPrimary.extension_version ? ` · v${browserAgentPrimary.extension_version}` : ''}
                                </span>
                              )}
                            </div>
                            {(!browserAgentOnline || !browserAgentZhuqueConnected) && (
                              <p className="mt-1 text-[12px] leading-5 text-slate-500">{browserAgentStatusMessage}</p>
                            )}
                          </div>
                          {browserAgentRequired && browserAgentPrimary && (
                            <div className="flex shrink-0 flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleRevokeBrowserAgent(browserAgentPrimary.agent_id)}
                                disabled={isRevokingBrowserAgent}
                                className="rounded-full border border-slate-200 bg-white/80 px-3 py-2 text-[13px] font-semibold text-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                撤销插件
                              </button>
                            </div>
                          )}
                        </div>
                        {browserAgentRequired && browserAgentPairing?.pairing_code && (
                          <div className="mt-3 rounded-2xl border border-blue-100 bg-white px-4 py-3 text-[13px] leading-6 text-slate-600">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-slate-900">配对码</span>
                              <code className="rounded-xl bg-slate-950 px-3 py-1.5 text-sm font-bold tracking-[0.12em] text-white">{browserAgentPairing.pairing_code}</code>
                              <span>在 Chrome 插件中填写当前站点地址和此配对码。</span>
                            </div>
                            <p className="mt-1 text-xs text-slate-400">有效期至 {browserAgentPairing.expires_at ? formatChinaDate(browserAgentPairing.expires_at) : '10 分钟后'}；插件连上后工作区会显示在线。</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="space-y-6">
                  <div>
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <label htmlFor="task-title" className="text-[16px] font-semibold text-slate-950">任务标题</label>
                      <span className="text-[14px] text-slate-400">{taskTitle.length}/100</span>
                    </div>
                    <input
                      id="task-title"
                      type="text"
                      maxLength={100}
                      value={taskTitle}
                      onChange={(e) => setTaskTitle(e.target.value)}
                      placeholder="请输入任务标题（选填）"
                      className="aurora-input"
                    />
                  </div>

                  <div>
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <label htmlFor="paper-content" className="text-[16px] font-semibold text-slate-950">论文内容</label>
                      <div className="flex items-center gap-2">
                        <input
                          ref={documentFileInputRef}
                          type="file"
                          accept=".pdf,.docx,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain"
                          onChange={handleDocumentUpload}
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={handleChooseDocumentFile}
                          disabled={isParsingDocument || Boolean(activeSession)}
                          className="inline-flex h-10 items-center gap-2 rounded-2xl border border-blue-100 bg-white/90 px-4 text-[13px] font-semibold text-[#2563eb] shadow-[0_10px_25px_rgba(37,99,235,0.08)] transition hover:border-blue-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
                          title="上传 PDF、Word(.docx)、Markdown(.md/.markdown) 或 TXT 论文并自动解析到输入框"
                        >
                          {isParsingDocument ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                          {isParsingDocument ? '解析中' : '上传文件'}
                        </button>
                      </div>
                    </div>
                    <textarea
                      id="paper-content"
                      value={text}
                      onChange={(e) => {
                        setText(e.target.value);
                        setDocumentParse(null);
                      }}
                      placeholder="请输入或粘贴论文内容，支持中英文..."
                      className="aurora-textarea"
                    />
                    {documentParse?.parse_fallback_used ? (
                      <p className="mt-3 rounded-2xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-[13px] leading-6 text-amber-800">
                        MinerU 解析失败，当前文件已回退 MarkItDown；标题、表格、公式等结构识别精度会降低。
                      </p>
                    ) : documentParse?.parse_engine === 'mineru' ? (
                      <p className="mt-3 rounded-2xl border border-blue-100 bg-blue-50/80 px-4 py-3 text-[13px] leading-6 text-blue-700">
                        已使用 MinerU 高精度解析，标题、表格、公式等结构已参与保护。
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <span className="text-[14px] text-slate-500">{billableCharacterCount} 字符</span>
                  <button
                    onClick={handleStartOptimization}
                    disabled={!text.trim() || activeSession || isSubmitting}
                    className="aurora-primary-action apple-action-pill gank-pill-button disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSubmitting ? (
                      <>
                        <div className="h-5 w-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                        提交中...
                      </>
                    ) : (
                      <>
                        <Wand2 className="h-5 w-5" />
                        开始优化
                      </>
                    )}
                  </button>
                </div>
              </section>
            </div>
          </section>

          <aside className="aurora-side-card apple-utility-card gank-liquid-panel">
            <div className="aurora-side-top">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="aurora-section-heading mb-0">
                  <Folder className="h-5 w-5 text-[#2563eb]" />
                  <span>论文项目</span>
                </div>
                <button
                  onClick={() => setShowProjectForm((value) => !value)}
                  className="aurora-icon-button"
                  aria-label={showProjectForm ? '取消新建论文' : '新建论文'}
                  title={showProjectForm ? '取消新建论文' : '新建论文'}
                >
                  {showProjectForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                </button>
              </div>

              {showProjectForm && (
                <form onSubmit={handleCreateProject} className="mb-4 space-y-2 rounded-2xl border border-slate-200/70 bg-white/70 p-3">
                  <input
                    type="text"
                    value={projectTitle}
                    onChange={(e) => setProjectTitle(e.target.value)}
                    placeholder="论文题目"
                    className="aurora-input min-h-[42px] text-sm"
                  />
                  <input
                    type="text"
                    value={projectDescription}
                    onChange={(e) => setProjectDescription(e.target.value)}
                    placeholder="备注，可选"
                    className="aurora-input min-h-[42px] text-sm"
                  />
                  <button type="submit" className="aurora-secondary-action w-full justify-center">
                    创建项目
                  </button>
                </form>
              )}

              <div className="relative">
                <select
                  value={projectSelectValue}
                  onChange={handleProjectScopeChange}
                  className="aurora-select"
                >
                  <option value="all">全部历史</option>
                  <option value="0">未归档历史</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>{project.title}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              </div>

              {activeProject && (
                <div className="mt-3 flex items-center gap-3 text-[12px]">
                  {editingProjectId === activeProject.id ? (
                    <form onSubmit={handleUpdateProject} className="grid w-full gap-2">
                      <input
                        type="text"
                        value={editProjectTitle}
                        onChange={(e) => setEditProjectTitle(e.target.value)}
                        placeholder="论文题目"
                        className="aurora-input min-h-[38px] text-xs"
                        autoFocus
                      />
                      <input
                        type="text"
                        value={editProjectDescription}
                        onChange={(e) => setEditProjectDescription(e.target.value)}
                        placeholder="备注，可选"
                        className="aurora-input min-h-[38px] text-xs"
                      />
                      <div className="flex gap-2">
                        <button type="submit" className="aurora-secondary-action min-h-[34px] flex-1 justify-center text-xs">保存</button>
                        <button type="button" onClick={handleCancelEditProject} className="aurora-plain-button flex-1 justify-center">取消</button>
                      </div>
                    </form>
                  ) : (
                    <div className="aurora-project-actions">
                      <button
                        type="button"
                        onClick={() => handleStartEditProject(activeProject)}
                        className="aurora-project-action-button"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        编辑当前项目
                      </button>
                      <button
                        type="button"
                        onClick={() => handleArchiveProject(activeProject)}
                        className="aurora-project-action-button aurora-project-action-danger"
                      >
                        <Archive className="h-3.5 w-3.5" />
                        归档当前项目
                      </button>
                    </div>
                  )}
                </div>
              )}
              {!activeProject && (
                <div className="aurora-project-hint">
                  <Archive className="h-3.5 w-3.5" />
                  <span>选择具体项目后可编辑或隐藏项目；未归档记录可在卡片上点“归入项目”放进对应项目。</span>
                </div>
              )}
            </div>

            <div className="aurora-history-head">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-[#3b82f6]" />
                <div className="min-w-0">
                  <h2 className="line-clamp-1 text-[19px] font-semibold tracking-[-0.02em] text-slate-950">
                    {historyScopeTitle} · 处理记录
                  </h2>
                  <p className="mt-1 text-[12px] leading-5 text-slate-500">
                    {historyScopeDescription}
                    {historyStatusFilter !== 'all' ? ` · ${activeHistoryStatusFilter.label}` : ''}
                  </p>
                </div>
              </div>
              <div className="relative shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    setOpenProjectMenuSessionId(null);
                    setShowHistoryFilters((value) => !value);
                  }}
                  className={`aurora-history-filter-button ${showHistoryFilters || historyStatusFilter !== 'all' ? 'aurora-history-filter-button-active' : ''}`}
                  aria-label="筛选历史状态"
                  aria-expanded={showHistoryFilters}
                >
                  <Filter className="h-4 w-4" />
                </button>
                {showHistoryFilters && (
                  <div className="aurora-history-filter-menu">
                    {HISTORY_STATUS_FILTERS.map((filter) => (
                      <button
                        key={filter.id}
                        type="button"
                        onClick={() => handleHistoryStatusFilterChange(filter.id)}
                        className={`aurora-history-filter-option ${historyStatusFilter === filter.id ? 'aurora-history-filter-option-active' : ''}`}
                      >
                        <span>{filter.label}</span>
                        {historyStatusFilter === filter.id && <CheckCircle className="h-3.5 w-3.5" />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="aurora-history-list custom-scrollbar">
              {isLoadingSessions ? (
                <div className="flex items-center justify-center py-12">
                  <div className="h-6 w-6 rounded-full border-2 border-slate-200 border-t-[#3b82f6] animate-spin" />
                </div>
              ) : sessions.length === 0 ? (
                <div className="py-12 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-50 text-slate-300">
                    <History className="h-7 w-7" />
                  </div>
                  <p className="mt-3 text-sm text-slate-500">暂无会话记录</p>
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="py-12 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-[#2563eb]">
                    <Filter className="h-7 w-7" />
                  </div>
                  <p className="mt-3 text-sm font-semibold text-slate-700">当前筛选暂无记录</p>
                  <button
                    type="button"
                    onClick={() => handleHistoryStatusFilterChange('all')}
                    className="aurora-plain-button mt-3"
                  >
                    清除筛选
                  </button>
                </div>
              ) : (
                filteredSessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    activeSession={activeSession}
                    projects={projects}
                    openProjectMenuSessionId={openProjectMenuSessionId}
                    onToggleProjectMenu={handleToggleProjectMenu}
                    onView={handleViewSession}
                    onDelete={handleDeleteSession}
                    onRetry={handleRetrySegment}
                    onMoveToProject={handleMoveSessionToProject}
                    onOpenZhuqueVerification={handleOpenZhuqueVerificationWindow}
                  />
                ))
              )}
            </div>
          </aside>
        </div>

        {activeSession && currentActiveSessionData && (
          <section className="aurora-progress-card mt-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-[17px] font-semibold text-slate-950">
                <span className="h-2.5 w-2.5 rounded-full bg-[#3b82f6] animate-pulse" />
                正在处理
              </h2>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-[13px] font-semibold text-[#2563eb]">进行中</span>
            </div>
            {(() => {
              const session = currentActiveSessionData;
              const getStageName = (stage) => {
                if (stage === 'polish') return '论文润色';
                if (stage === 'emotion_polish') return '感情文章润色';
                if (stage === 'ai_detect_reduce') return 'AI检测 + 降重';
                if (stage === 'enhance') return '原创性增强';
                return stage;
              };
              return (
                <div>
                  <div className="mb-2 flex justify-between text-[13px] font-medium">
                    <span className="text-slate-500">当前阶段：<span className="text-slate-950">{getStageName(session.current_stage)}</span></span>
                    <span className="text-[#2563eb]">{session.progress.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500 transition-all duration-500 ease-out shadow-[0_0_14px_rgba(59,130,246,0.28)]"
                      style={{ width: `${session.progress}%` }}
                    />
                  </div>
                  <div className="mt-3 flex justify-between text-[13px] text-slate-500">
                    <span>进度：<span className="font-semibold text-slate-950">{session.current_position + 1}</span> / {session.total_segments} 段</span>
                    {session.status === 'queued' && queueStatus?.your_position && (
                      <span className="text-orange-500">排队第 {queueStatus.your_position} 位 (~{Math.ceil(queueStatus.estimated_wait_time / 60)}分)</span>
                    )}
                    {session.status === 'waiting_browser_agent' && (
                      <span className="text-amber-600">等待本机朱雀插件检测，期间不占全站处理名额</span>
                    )}
                  </div>
                </div>
              );
            })()}
          </section>
        )}
      </main>

      {showZhuqueLoginModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center px-4 py-8">
          <div
            className="absolute inset-0 bg-slate-950/35 backdrop-blur-md"
            onClick={handleCloseZhuqueLoginModal}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="zhuque-login-dialog-title"
            className="aurora-zhuque-login-modal relative w-full max-w-[440px] overflow-hidden"
          >
            <button
              type="button"
              onClick={handleCloseZhuqueLoginModal}
              className="aurora-zhuque-login-close"
              aria-label="关闭朱雀扫码登录"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="aurora-zhuque-login-glow aurora-zhuque-login-glow-one" />
            <div className="aurora-zhuque-login-glow aurora-zhuque-login-glow-two" />
            <div className="relative p-6">
              <div className="mb-5 flex items-center gap-3">
                <div className="aurora-zhuque-login-icon">
                  <QrCode className="h-6 w-6" />
                </div>
                <div>
                  <h3 id="zhuque-login-dialog-title" className="text-[20px] font-semibold tracking-[-0.03em] text-slate-950">
                    朱雀扫码登录
                  </h3>
                  <p className="mt-1 text-[13px] text-slate-500">每个 GankAIGC 用户独立保存朱雀凭证</p>
                </div>
              </div>

              <div className="aurora-zhuque-qr-frame">
                {zhuqueLoginSession?.qr_image_data ? (
                  <img
                    src={zhuqueLoginSession.qr_image_data}
                    alt="朱雀微信扫码登录二维码"
                    className="aurora-zhuque-qr-image"
                  />
                ) : zhuqueLoginSession?.status === 'logged_in' ? (
                  <div className="aurora-zhuque-qr-success">
                    <CheckCircle className="h-12 w-12" />
                    <span>登录成功</span>
                  </div>
                ) : (
                  <div className="aurora-zhuque-qr-loading">
                    <RefreshCw className="h-9 w-9 animate-spin" />
                    <span>{isStartingZhuqueLogin ? '正在启动二维码' : '等待二维码加载'}</span>
                  </div>
                )}
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="aurora-zhuque-login-stat">
                  <span>状态</span>
                  <strong>{zhuqueLoginSession?.status === 'logged_in' ? '已登录' : zhuqueLoginSession?.status === 'expired' ? '已超时' : zhuqueLoginSession?.status === 'error' ? '异常' : '待扫码'}</strong>
                </div>
                <div className="aurora-zhuque-login-stat">
                  <span>用户</span>
                  <strong>{zhuqueLoginSession?.user_name || zhuqueAccountName || '--'}</strong>
                </div>
                <div className="aurora-zhuque-login-stat">
                  <span>剩余</span>
                  <strong>{formatZhuqueRemainingUses(zhuqueLoginSession?.remaining_uses ?? zhuqueRemainingValue)}</strong>
                </div>
              </div>

              <p className={`aurora-zhuque-login-message ${zhuqueLoginSession?.status === 'error' || zhuqueLoginSession?.status === 'expired' ? 'is-danger' : ''}`}>
                {zhuqueLoginSession?.message || '请使用微信扫描二维码，登录成功后会自动同步状态'}
              </p>

              <div className="mt-5 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={handleCloseZhuqueLoginModal}
                  className="aurora-zhuque-login-secondary"
                >
                  {zhuqueLoginSession?.status === 'logged_in' ? '完成' : '关闭'}
                </button>
                {(zhuqueLoginSession?.status === 'expired' || zhuqueLoginSession?.status === 'error' || zhuqueLoginSession?.status === 'manual_required') && (
                  <button
                    type="button"
                    onClick={handleStartZhuqueLogin}
                    disabled={isStartingZhuqueLogin}
                    className="aurora-zhuque-login-primary"
                  >
                    重新生成
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {retryDialogSession && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center px-4 py-8">
          <div
            className="absolute inset-0 bg-slate-900/30 backdrop-blur-md"
            onClick={() => !isRetrying && setRetryDialogSession(null)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="retry-dialog-title"
            className="gank-liquid-panel relative w-full max-w-md overflow-hidden"
          >
            <div className="absolute -top-20 -right-16 h-40 w-40 rounded-full bg-blue-200/50 blur-3xl" />
            <div className="absolute -bottom-24 -left-16 h-44 w-44 rounded-full bg-amber-200/50 blur-3xl" />
            <div className="relative p-6">
              <div className="mb-4 flex items-start gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 shadow-inner">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <div>
                  <h3 id="retry-dialog-title" className="text-xl font-bold tracking-tight text-slate-950">
                    继续处理失败任务？
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    将从未完成段落继续执行，并使用你当前选择的
                    <span className="mx-1 font-semibold text-slate-950">
                      {billingMode === 'byok' ? '自带 API 模式' : '平台模式'}
                    </span>
                    重新连接模型。
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-white/70 bg-white/60 p-4 text-sm text-slate-600">
                <div className="font-semibold text-slate-900">
                  {retryDialogSession.task_title || retryDialogSession.project_title || '未命名任务'}
                </div>
                <div className="mt-1 line-clamp-2">
                  {retryDialogSession.preview_text || '暂无预览'}
                </div>
                {billingMode === 'byok' && (
                  <div className="mt-3 rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-700">
                    会切换为你保存的自带 API 配置，不再沿用上次失败的平台 API。
                  </div>
                )}
              </div>

              <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setRetryDialogSession(null)}
                  disabled={isRetrying}
                  className="gank-secondary-button rounded-xl px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={confirmRetrySegment}
                  disabled={isRetrying}
                  className="gank-primary-button inline-flex items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
                >
                  {isRetrying && (
                    <span className="h-4 w-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                  )}
                  继续处理
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkspacePage;
