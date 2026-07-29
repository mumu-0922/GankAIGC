import React, { useRef, useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  LogIn,
  LogOut,
  Users,
  Key,
  Search,
  Calendar,
  CheckCircle,
  Shield,
  Plus,
  TrendingUp,
  RefreshCw,
  BarChart3,
  Clock,
  FileText,
  MessageSquare,
  Filter,
  Eye,
  Ban,
  Edit2,
  PanelLeftClose,
  Send,
  LayoutGrid,
  CircleDollarSign,
  Sparkles,
  Loader2,
  Github,
  ExternalLink,
  Copy,
  Download,
  Megaphone,
  Save,
  Trash2,
  X,
  DownloadCloud,
  Upload,
  UserCheck
} from 'lucide-react';
import ConfigManager from '../components/ConfigManager';
import SessionMonitor from '../components/SessionMonitor';
import AdminOperationsPanel from '../components/AdminOperationsPanel';
import BrandLogo from '../components/BrandLogo';
import BeerIcon from '../components/BeerIcon';
import MarkdownPreview, { DEFAULT_ANNOUNCEMENT_MARKDOWN } from '../components/MarkdownPreview';
import { formatChinaDate, formatChinaDateTime, parseBackendDate } from '../utils/dateTime';

const DEFAULT_ADMIN_TAB = 'dashboard';
const ADMIN_TAB_IDS = ['dashboard', 'operations', 'sessions', 'accounts', 'announcements', 'config', 'audit', 'adminProfile'];
const ADMIN_ACCOUNT_FORM_CLASS = 'grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_5rem_7rem] gap-3 mb-5';
const ADMIN_ACCOUNT_INPUT_CLASS = 'aurora-admin-input w-full min-w-0 h-12 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent';
const ADMIN_ACCOUNT_WIDE_INPUT_CLASS = `${ADMIN_ACCOUNT_INPUT_CLASS} sm:col-span-2`;
const ADMIN_ACCOUNT_ACTION_BUTTON_CLASS = 'aurora-admin-action min-w-[7rem] h-12 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2 font-semibold';
const ADMIN_COMPACT_TABLE_SCROLL_CLASS = 'overflow-auto max-h-[20rem]';
const ADMIN_TABLE_SCROLL_CLASS = 'overflow-auto max-h-[37rem]';
const ADMIN_COMPACT_TABLE_HEAD_CLASS = 'sticky top-0 z-10 bg-white aurora-admin-table-head';
const ADMIN_TABLE_HEAD_CLASS = 'sticky top-0 z-10 bg-gray-50 aurora-admin-table-head';
const ACCOUNT_PANEL_TABS = [
  { id: 'users', label: '用户列表' },
  { id: 'invites', label: '邀请码管理' },
  { id: 'creditCodes', label: '兑换码' },
  { id: 'creditTransactions', label: '啤酒流水' },
  { id: 'apiConfigs', label: 'API 配置' },
];
const CURRENT_APP_VERSION = window.__GANKAIGC_RUNTIME__?.appVersion || import.meta.env.VITE_APP_VERSION || 'v2.1.0';
const ANNOUNCEMENT_MARKDOWN_TOOLS = [
  { id: 'heading', label: 'H', title: '标题', syntax: 'line-prefix', prefix: '## ' },
  { id: 'bold', label: 'B', title: '加粗', syntax: 'wrap', prefix: '**', suffix: '**', sample: '加粗文字' },
  { id: 'italic', label: 'I', title: '斜体', syntax: 'wrap', prefix: '*', suffix: '*', sample: '斜体文字' },
  { id: 'strike', label: 'S', title: '删除线', syntax: 'wrap', prefix: '~~', suffix: '~~', sample: '删除线文字' },
  { id: 'bullet', label: '•', title: '无序列表', syntax: 'line-prefix', prefix: '- ' },
  { id: 'ordered', label: '1.', title: '有序列表', syntax: 'line-prefix', prefix: '1. ' },
  { id: 'task', label: '☑', title: '任务列表', syntax: 'line-prefix', prefix: '- [ ] ' },
  { id: 'code', label: '</>', title: '代码块', syntax: 'block', before: '```\n', after: '\n```', sample: '代码内容' },
  { id: 'link', label: '🔗', title: '链接', syntax: 'wrap', prefix: '[', suffix: '](https://example.com)', sample: '链接文字' },
  { id: 'table', label: '▦', title: '表格', syntax: 'insert', text: '\n| 项目 | 说明 |\n| --- | --- |\n| 功能 | 内容 |\n' },
  { id: 'quote', label: '“', title: '引用', syntax: 'line-prefix', prefix: '> ' },
  { id: 'divider', label: '—', title: '分割线', syntax: 'insert', text: '\n---\n' },
];


const formatAdminNumber = (value) => Number(value || 0).toLocaleString();

const formatBeerDelta = (delta) => {
  const value = Number(delta || 0);
  return `${value > 0 ? '+' : ''}${value} 啤酒`;
};

const getCreditTransactionClass = (transaction) => {
  if (transaction.transaction_type === 'credit' || transaction.delta > 0) {
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  }
  if (transaction.transaction_type === 'debit' || transaction.delta < 0) {
    return 'bg-red-50 text-red-700 border-red-100';
  }
  return 'bg-slate-50 text-slate-700 border-slate-100';
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

const formatAuditDetail = (detail) => {
  if (!detail) {
    return '-';
  }
  if (typeof detail === 'string') {
    return detail;
  }
  return Object.entries(detail)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
    .join('；') || '-';
};

const getAuditSeverity = (action = '') => {
  if (action.includes('delete') || action.includes('ban') || action.includes('删除') || action.includes('封禁')) {
    return { label: 'warning', className: 'bg-amber-50 text-amber-700 border-amber-100' };
  }
  return { label: 'info', className: 'bg-blue-50 text-blue-700 border-blue-100' };
};

const getAuditIp = (log, index = 0) => (
  log?.detail?.ip
  || log?.detail?.ip_address
  || log?.ip_address
  || '未知'
);

const getAdminUserRole = (user, providerConfig) => {
  if (user?.is_unlimited || providerConfig) {
    return { label: 'VIP用户', className: 'bg-amber-50 text-amber-700 border-amber-200' };
  }
  return { label: '普通用户', className: 'bg-blue-50 text-blue-700 border-blue-100' };
};


const getAdminTabFromSearchParams = (searchParams) => {
  const requestedTab = searchParams.get('tab');
  return ADMIN_TAB_IDS.includes(requestedTab) ? requestedTab : DEFAULT_ADMIN_TAB;
};

const createTextDownload = (content, filename, type = 'text/plain;charset=utf-8') => {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

const escapeCsvCell = (value) => {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const modeLabels = {
  paper_polish: '论文润色',
  paper_enhance: '论文增强',
  paper_polish_enhance: '润色 + 增强',
  emotion_polish: '感情文章润色',
  ai_detect_reduce: 'AI检测+降重',
};

const getModeLabel = (mode) => modeLabels[mode] || mode || '-';

const modeTones = {
  paper_polish: 'blue',
  paper_enhance: 'cyan',
  paper_polish_enhance: 'violet',
  emotion_polish: 'amber',
  ai_detect_reduce: 'slate',
};

const chartTones = ['blue', 'cyan', 'violet', 'amber', 'slate'];

const getSeriesValues = (series, fallbackValue = 0) => {
  const values = Array.isArray(series)
    ? series
      .map((point) => Number(typeof point === 'number' ? point : point?.value))
      .filter((value) => Number.isFinite(value))
    : [];

  if (values.length === 0) {
    return [fallbackValue, fallbackValue];
  }

  if (values.length === 1) {
    return [values[0], values[0]];
  }

  return values;
};

const formatTrendPercent = (trendPercent) => {
  if (trendPercent === null || trendPercent === undefined || Number.isNaN(Number(trendPercent))) {
    return '上一周期无数据';
  }
  const value = Number(trendPercent);
  if (value === 0) {
    return '较上一周期 0.00%';
  }
  return `较上一周期 ${value > 0 ? '▲' : '▼'} ${Math.abs(value).toFixed(2)}%`;
};

const isTrendDown = (trendPercent, trendText = '') => (
  trendText.includes('▼') || Number(trendPercent) < 0
);

const buildLineCoordinates = (values, width = 520, height = 170) => {
  const safeValues = getSeriesValues(values);
  const max = Math.max(...safeValues);
  const min = Math.min(...safeValues);
  const range = max - min || 1;
  const topPadding = 28;
  const bottomPadding = 24;

  return safeValues.map((value, index) => {
    const x = safeValues.length === 1 ? 0 : (index / (safeValues.length - 1)) * width;
    const y = height - bottomPadding - ((value - min) / range) * (height - topPadding - bottomPadding);
    return { x, y };
  });
};

const MiniSparkline = ({ tone = 'blue', points = [0, 0] }) => {
  const safePoints = getSeriesValues(points);
  const max = Math.max(...safePoints);
  const min = Math.min(...safePoints);
  const range = max - min || 1;
  const path = safePoints
    .map((value, index) => {
      const x = (index / (safePoints.length - 1)) * 100;
      const y = 34 - ((value - min) / range) * 24;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg className={`aurora-admin-sparkline aurora-admin-sparkline-${tone}`} viewBox="0 0 100 40" preserveAspectRatio="none">
      <polyline points={path} />
    </svg>
  );
};

const AdminMetricCard = ({ icon: Icon, title, value, suffix, note, trendPercent, trendLabel, tone = 'blue', points = [0, 0] }) => {
  const trendText = note || trendLabel || formatTrendPercent(trendPercent);
  return (
    <div className="aurora-admin-stat-card">
      <div className="flex items-start justify-between gap-3">
        <div className={`aurora-admin-metric-icon aurora-admin-metric-icon-${tone}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
      <div className="mt-3">
        <p className="aurora-admin-stat-label">{title}</p>
        <p className="aurora-admin-stat-value">
          {value}
          {suffix && <span>{suffix}</span>}
        </p>
        <p className={`aurora-admin-stat-trend ${isTrendDown(trendPercent, trendText) ? 'is-down' : ''}`}>
          {trendText}
        </p>
      </div>
      <MiniSparkline tone={tone} points={points} />
    </div>
  );
};

const AdminChartCard = ({ title, value, suffix, tone = 'blue', icon: Icon, trendPercent, trendLabel, children }) => {
  const trendText = trendLabel || formatTrendPercent(trendPercent);
  return (
    <div className="aurora-admin-chart-card">
      <div className="aurora-admin-chart-head">
        <div>
          <h3>{title}</h3>
          {value !== undefined && value !== null && (
            <p className={`aurora-admin-chart-value aurora-admin-chart-value-${tone}`}>
              {value}
              {suffix && <span>{suffix}</span>}
            </p>
          )}
          <p className={`aurora-admin-stat-trend ${isTrendDown(trendPercent, trendText) ? 'is-down' : ''}`}>
            {trendText}
          </p>
        </div>
        {Icon && (
          <div className={`aurora-admin-metric-icon aurora-admin-metric-icon-${tone}`}>
            <Icon className="h-7 w-7" />
          </div>
        )}
      </div>
      {children}
    </div>
  );
};

const AdminBarChart = ({ tone = 'blue', values = [0, 0] }) => {
  const bars = getSeriesValues(values);
  const max = Math.max(...bars, 1);
  return (
    <div className="aurora-admin-bar-chart">
      {bars.map((value, index) => (
        <span
          key={index}
          style={{ height: `${Math.max(0, (value / max) * 100)}%` }}
          className={`aurora-admin-bar aurora-admin-bar-${tone}`}
          title={`${value}`}
        />
      ))}
    </div>
  );
};

const AdminLineChart = ({ tone = 'cyan', area = false, values = [0, 0] }) => {
  const points = buildLineCoordinates(values);
  const pointString = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
  const areaPath = points.length > 0
    ? `M${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)} ${points.slice(1).map((point) => `L${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ')} L520 170 L0 170 Z`
    : '';

  return (
    <div className={`aurora-admin-line-chart ${area ? 'is-area' : ''}`}>
      <svg viewBox="0 0 520 170" preserveAspectRatio="none">
        {area && areaPath && (
          <path
            d={areaPath}
            className={`aurora-admin-area aurora-admin-area-${tone}`}
          />
        )}
        <polyline
          points={pointString}
          className={`aurora-admin-chart-line aurora-admin-chart-line-${tone}`}
        />
        {points.map((point, index) => (
          <circle
            key={`${point.x}-${index}`}
            cx={point.x}
            cy={point.y}
            r="4"
            className={`aurora-admin-chart-dot aurora-admin-chart-dot-${tone}`}
          />
        ))}
      </svg>
    </div>
  );
};

const AdminNavGlyph = ({ type, className = 'w-5 h-5' }) => {
  const commonProps = {
    className: `aurora-admin-nav-glyph ${className}`,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '1.9',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
  };

  switch (type) {
    case 'dashboard':
      return (
        <svg {...commonProps}>
          <path d="M5 19V9.8" />
          <path d="M10 19V5.6" />
          <path d="M15 19v-7.2" />
          <path d="M20 19V7.4" />
          <path d="M3.7 19.4h17.1" opacity=".62" />
        </svg>
      );
    case 'sessions':
      return (
        <svg {...commonProps}>
          <path d="M5.3 5.4h13.4a2.2 2.2 0 0 1 2.2 2.2v6.3a2.2 2.2 0 0 1-2.2 2.2h-6.5l-4.4 3v-3H5.3a2.2 2.2 0 0 1-2.2-2.2V7.6a2.2 2.2 0 0 1 2.2-2.2Z" />
          <path d="M7.6 9.4h8.7M7.6 12.3h5.7" />
        </svg>
      );
    case 'operations':
      return (
        <svg {...commonProps}>
          <path d="M3.2 12h3.4l2.1-5.7 4.2 11.2 2.2-6h5.7" />
          <path d="M18.4 5.8a8.7 8.7 0 0 1 2.3 6.2 8.7 8.7 0 0 1-2.4 6.1" opacity=".55" />
        </svg>
      );
    case 'accounts':
      return (
        <svg {...commonProps}>
          <circle cx="9" cy="8.2" r="3" />
          <path d="M3.7 19.1c.8-3.1 2.6-4.7 5.3-4.7s4.5 1.6 5.3 4.7" />
          <path d="M15 10.5a2.5 2.5 0 1 0-1.2-4.7M15.6 14.1c2.4.3 3.9 1.9 4.7 4.8" opacity=".7" />
        </svg>
      );
    case 'announcements':
      return (
        <svg {...commonProps}>
          <path d="M4.3 13.8h3.2l8.9 3.8V6.4l-8.9 3.8H4.3a1.7 1.7 0 0 0-1.7 1.7v.2a1.7 1.7 0 0 0 1.7 1.7Z" />
          <path d="M7.4 13.9 8.8 19h2.5l-1.1-4.1M18.7 9.2c1 .7 1.5 1.6 1.5 2.8s-.5 2.1-1.5 2.8" />
        </svg>
      );
    case 'config':
      return (
        <svg {...commonProps}>
          <path d="M12 3.6 19 7.7v8.6L12 20.4l-7-4.1V7.7L12 3.6Z" />
          <circle cx="12" cy="12" r="2.5" />
          <circle cx="12" cy="12" r=".8" fill="currentColor" stroke="none" />
          <path d="M12 6.8v1.5M12 15.7v1.5M7.7 9.5l1.3.8M15 13.7l1.3.8M16.3 9.5l-1.3.8M9 13.7l-1.3.8" opacity=".62" />
        </svg>
      );
    case 'audit':
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="7.6" />
          <path d="M12 7.5v4.8l3.1 1.8" />
          <path d="M6.9 5.9 5.4 4.4M17.1 5.9l1.5-1.5" opacity=".62" />
        </svg>
      );
    case 'adminProfile':
      return (
        <svg {...commonProps}>
          <rect x="4" y="4.6" width="16" height="14.8" rx="3.1" />
          <circle cx="10" cy="10" r="2.25" />
          <path d="M6.8 16.4c.55-2.05 1.62-3.1 3.2-3.1s2.65 1.05 3.2 3.1" />
          <path d="M15.4 9.2h2.1M15.4 12h2.1M15.4 14.8h2.1" opacity=".68" />
        </svg>
      );
    default:
      return <LayoutGrid className={className} />;
  }
};

const AdminALinesGlyph = ({ className = 'h-7 w-7' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4.6 18.5 9.2 5.8h1.5l4.7 12.7" />
    <path d="M7 14.2h6" />
    <path d="M17.2 8.1h2.6M17.2 12h3.7M17.2 15.9h2.6" />
  </svg>
);

const AdminKeyboardGlyph = ({ className = 'h-7 w-7' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3.7" y="6.8" width="16.6" height="10.4" rx="2.1" />
    <path d="M7.1 10h.1M10.2 10h.1M13.3 10h.1M16.4 10h.1M7.1 13.4h.1M10.2 13.4h3.2M16.4 13.4h.1" />
  </svg>
);

const AdminStarGrowthGlyph = ({ className = 'h-6 w-6' }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="m12 3.9 2.35 4.76 5.25.76-3.8 3.7.9 5.23L12 15.88l-4.7 2.47.9-5.23-3.8-3.7 5.25-.76L12 3.9Z" />
  </svg>
);

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [adminToken, setAdminToken] = useState(localStorage.getItem('adminToken'));
  
  // Tab state
  const [activeTab, setActiveTab] = useState(() => getAdminTabFromSearchParams(searchParams));

  // Login form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Users state
  const [users, setUsers] = useState([]);

  // Statistics state
  const [statistics, setStatistics] = useState(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Account and credit management state
  const [invites, setInvites] = useState([]);
  const [creditCodes, setCreditCodes] = useState([]);
  const [creditTransactions, setCreditTransactions] = useState([]);
  const [providerConfigs, setProviderConfigs] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAccountData, setLoadingAccountData] = useState(false);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState(false);
  const [loadingAuditLogs, setLoadingAuditLogs] = useState(false);
  const [newInviteCode, setNewInviteCode] = useState('');
  const [newCreditCode, setNewCreditCode] = useState('');
  const [newCreditAmount, setNewCreditAmount] = useState(10);
  const [inviteBatchQuantity, setInviteBatchQuantity] = useState(10);
  const [creditBatchQuantity, setCreditBatchQuantity] = useState(10);
  const [creatingInviteBatch, setCreatingInviteBatch] = useState(false);
  const [creatingCreditBatch, setCreatingCreditBatch] = useState(false);
  const [selectedInviteIds, setSelectedInviteIds] = useState([]);
  const [selectedCreditCodeIds, setSelectedCreditCodeIds] = useState([]);
  const [accountPanelTab, setAccountPanelTab] = useState('users');
  const [userSearchTerm, setUserSearchTerm] = useState('');
  const [userStatusFilter, setUserStatusFilter] = useState('all');
  const [userApiFilter, setUserApiFilter] = useState('all');
  const [announcementTitle, setAnnouncementTitle] = useState('');
  const [announcementContent, setAnnouncementContent] = useState('');
  const [announcementCategory, setAnnouncementCategory] = useState('notice');
  const [announcementContentHistory, setAnnouncementContentHistory] = useState(['']);
  const [announcementContentHistoryIndex, setAnnouncementContentHistoryIndex] = useState(0);
  const [isAnnouncementEditorExpanded, setIsAnnouncementEditorExpanded] = useState(false);
  const announcementTextareaRef = useRef(null);
  const [creditTopUps, setCreditTopUps] = useState({});
  const [showUpdateModal, setShowUpdateModal] = useState(false);
  const [updateStatus, setUpdateStatus] = useState(null);
  const [loadingUpdateStatus, setLoadingUpdateStatus] = useState(false);
  const [selectedAuditLogId, setSelectedAuditLogId] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [dashboardDateRange, setDashboardDateRange] = useState('7d');
  const [auditRoleFilter, setAuditRoleFilter] = useState('all');
  const [auditActionFilter, setAuditActionFilter] = useState('all');
  const [auditResourceFilter, setAuditResourceFilter] = useState('all');
  const [auditSeverityFilter, setAuditSeverityFilter] = useState('all');
  const [auditDateRange, setAuditDateRange] = useState('all');
  const adminAvatarInputRef = useRef(null);
  const [adminProfile, setAdminProfile] = useState(null);
  const [loadingAdminProfile, setLoadingAdminProfile] = useState(false);
  const [savingAdminProfile, setSavingAdminProfile] = useState(false);
  const [uploadingAdminAvatar, setUploadingAdminAvatar] = useState(false);
  const [adminAvatarLoadFailed, setAdminAvatarLoadFailed] = useState(false);
  const [savingAdminPassword, setSavingAdminPassword] = useState(false);
  const [adminDisplayName, setAdminDisplayName] = useState('');
  const [adminPasswordForm, setAdminPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  useEffect(() => {
    if (adminToken) {
      verifyToken();
    }
  }, [adminToken]);

  useEffect(() => {
    const nextTab = getAdminTabFromSearchParams(searchParams);
    setActiveTab((currentTab) => currentTab === nextTab ? currentTab : nextTab);
  }, [searchParams]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchStatistics();
      // 每30秒自动刷新统计数据
      const interval = setInterval(fetchStatistics, 30000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, dashboardDateRange]);

  useEffect(() => {
    if (isAuthenticated && !updateStatus) {
      fetchUpdateStatus({ silent: true });
    }
  }, [isAuthenticated, updateStatus]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'accounts') {
      fetchAccountData();
    }
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'audit') {
      fetchAuditLogs();
    }
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'announcements') {
      fetchAnnouncements();
    }
  }, [isAuthenticated, activeTab]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'adminProfile') {
      fetchAdminProfile();
    }
  }, [isAuthenticated, activeTab]);

  const verifyToken = async () => {
    try {
      await axios.post('/api/admin/verify-token', {}, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setIsAuthenticated(true);
    } catch (error) {
      localStorage.removeItem('adminToken');
      setAdminToken(null);
      setIsAuthenticated(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post('/api/admin/login', {
        username,
        password
      });

      const { access_token } = response.data;
      localStorage.setItem('adminToken', access_token);
      setAdminToken(access_token);
      setIsAuthenticated(true);
      toast.success('登录成功！');
    } catch (error) {
      toast.error(error.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = (options = {}) => {
    const silent = Boolean(options?.silent);
    localStorage.removeItem('adminToken');
    setAdminToken(null);
    setIsAuthenticated(false);
    setUsername('');
    setPassword('');
    setAdminProfile(null);
    setAdminDisplayName('');
    setAdminAvatarLoadFailed(false);
    setAdminPasswordForm({
      current_password: '',
      new_password: '',
      confirm_password: '',
    });
    if (!silent) {
      toast.success('已退出登录');
    }
  };

  const handleAdminTabChange = (tabId) => {
    if (!ADMIN_TAB_IDS.includes(tabId)) {
      return;
    }

    setActiveTab(tabId);
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      if (tabId === DEFAULT_ADMIN_TAB) {
        nextParams.delete('tab');
      } else {
        nextParams.set('tab', tabId);
      }
      return nextParams;
    }, { replace: true });
  };

  const fetchStatistics = async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('/api/admin/statistics', {
        params: { range: dashboardDateRange },
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setStatistics(response.data);
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      setLoadingStats(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('已复制到剪贴板');
  };

  const fetchUpdateStatus = async ({ silent = false } = {}) => {
    setLoadingUpdateStatus(true);
    try {
      const response = await axios.get('/api/admin/update/status', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUpdateStatus(response.data);
    } catch (error) {
      if (!silent) {
        toast.error(error.response?.data?.detail || '检查更新失败');
      }
    } finally {
      setLoadingUpdateStatus(false);
    }
  };

  const openUpdateModal = () => {
    setShowUpdateModal(true);
    fetchUpdateStatus();
  };

  const openGithubIssues = () => {
    window.open('https://github.com/mumu-0922/GankAIGC/issues', '_blank', 'noopener,noreferrer');
  };

  const toggleSidebarCollapsed = () => {
    setSidebarCollapsed((value) => !value);
  };

  const fetchAccountData = async () => {
    setLoadingAccountData(true);
    try {
      const headers = { Authorization: `Bearer ${adminToken}` };
      const [usersResponse, invitesResponse, creditCodesResponse] = await Promise.all([
        axios.get('/api/admin/users', { headers }),
        axios.get('/api/admin/invites', { headers }),
        axios.get('/api/admin/credit-codes', { headers }),
      ]);

      setUsers(usersResponse.data);
      setInvites(invitesResponse.data);
      setCreditCodes(creditCodesResponse.data);
      setSelectedInviteIds((current) => current.filter((id) => invitesResponse.data.some((invite) => invite.id === id)));
      setSelectedCreditCodeIds((current) => current.filter((id) => creditCodesResponse.data.some((code) => code.id === id)));

      const [creditTransactionsResult, providerConfigsResult] = await Promise.allSettled([
        axios.get('/api/admin/credit-transactions', { headers, params: { limit: 30 } }),
        axios.get('/api/admin/provider-configs', { headers })
      ]);

      if (creditTransactionsResult.status === 'fulfilled') {
        setCreditTransactions(creditTransactionsResult.value.data);
      } else {
        setCreditTransactions([]);
        console.warn('Beer transaction history is unavailable:', creditTransactionsResult.reason);
      }

      if (providerConfigsResult.status === 'fulfilled') {
        setProviderConfigs(providerConfigsResult.value.data);
      } else {
        setProviderConfigs([]);
        console.warn('Provider config summaries are unavailable:', providerConfigsResult.reason);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '获取账号管理数据失败');
      console.error('Error fetching account data:', error);
    } finally {
      setLoadingAccountData(false);
    }
  };

  const fetchAuditLogs = async () => {
    setLoadingAuditLogs(true);
    try {
      const response = await axios.get('/api/admin/audit-logs', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { limit: 50 }
      });
      setAuditLogs(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || '获取操作日志失败');
      console.error('Error fetching audit logs:', error);
    } finally {
      setLoadingAuditLogs(false);
    }
  };

  const fetchAnnouncements = async () => {
    setLoadingAnnouncements(true);
    try {
      const response = await axios.get('/api/admin/announcements', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setAnnouncements(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || '获取公告失败');
      console.error('Error fetching announcements:', error);
    } finally {
      setLoadingAnnouncements(false);
    }
  };

  const fetchAdminProfile = async () => {
    setLoadingAdminProfile(true);
    try {
      const response = await axios.get('/api/admin/profile', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setAdminProfile(response.data);
      setAdminDisplayName(response.data.display_name || response.data.username || '');
      setAdminAvatarLoadFailed(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || '获取管理员资料失败');
    } finally {
      setLoadingAdminProfile(false);
    }
  };

  const handleSaveAdminProfile = async (event) => {
    event.preventDefault();
    const displayName = adminDisplayName.trim();
    if (!displayName) {
      toast.error('管理员昵称不能为空');
      return;
    }

    setSavingAdminProfile(true);
    try {
      const response = await axios.patch('/api/admin/profile',
        { display_name: displayName },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setAdminProfile(response.data);
      setAdminDisplayName(response.data.display_name || '');
      setAdminAvatarLoadFailed(false);
      toast.success('管理员资料已更新');
    } catch (error) {
      toast.error(error.response?.data?.detail || '保存管理员资料失败');
    } finally {
      setSavingAdminProfile(false);
    }
  };

  const handleAdminAvatarUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    const formData = new FormData();
    formData.append('avatar', file);
    setUploadingAdminAvatar(true);
    try {
      const response = await axios.post('/api/admin/profile/avatar', formData, {
        headers: { Authorization: `Bearer ${adminToken}` },
        timeout: 20000,
      });
      setAdminProfile(response.data);
      setAdminAvatarLoadFailed(false);
      toast.success('管理员头像已更新');
    } catch (error) {
      toast.error(error.response?.data?.detail || '上传管理员头像失败');
    } finally {
      setUploadingAdminAvatar(false);
    }
  };

  const handleAdminPasswordInput = (field, value) => {
    setAdminPasswordForm((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handleSaveAdminPassword = async (event) => {
    event.preventDefault();
    if (!adminPasswordForm.current_password) {
      toast.error('请输入当前密码');
      return;
    }
    if (adminPasswordForm.new_password.length < 8) {
      toast.error('新密码至少 8 位');
      return;
    }
    if (adminPasswordForm.new_password !== adminPasswordForm.confirm_password) {
      toast.error('两次输入的新密码不一致');
      return;
    }

    setSavingAdminPassword(true);
    try {
      await axios.post('/api/admin/profile/password',
        {
          current_password: adminPasswordForm.current_password,
          new_password: adminPasswordForm.new_password,
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setAdminPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
      toast.success('管理员密码已更新，请用新密码重新登录');
      handleLogout({ silent: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新管理员密码失败');
    } finally {
      setSavingAdminPassword(false);
    }
  };

  const handleCreateInvite = async (e) => {
    e.preventDefault();
    try {
      await axios.post('/api/admin/invites',
        { code: newInviteCode.trim() || null },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setNewInviteCode('');
      toast.success('邀请码已创建');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '创建邀请码失败');
    }
  };

  const handleToggleInvite = async (inviteId) => {
    try {
      await axios.patch(`/api/admin/invites/${inviteId}/toggle`, {}, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success('邀请码状态已更新');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新邀请码失败');
    }
  };

  const handleBatchCreateInvites = async () => {
    setCreatingInviteBatch(true);
    try {
      const response = await axios.post('/api/admin/invites/batch',
        { quantity: inviteBatchQuantity },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(`已批量生成 ${response.data.length} 个邀请码`);
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '批量生成邀请码失败');
    } finally {
      setCreatingInviteBatch(false);
    }
  };

  const handleCreateCreditCode = async (e) => {
    e.preventDefault();
    const amount = parseInt(newCreditAmount, 10);
    if (!amount || amount < 1) {
      toast.error('兑换啤酒必须大于 0');
      return;
    }

    try {
      await axios.post('/api/admin/credit-codes',
        { code: newCreditCode.trim() || null, credit_amount: amount },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setNewCreditCode('');
      setNewCreditAmount(10);
      toast.success('兑换码已创建');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '创建兑换码失败');
    }
  };

  const handleBatchCreateCreditCodes = async () => {
    const amount = parseInt(newCreditAmount, 10);
    if (!amount || amount < 1) {
      toast.error('兑换啤酒必须大于 0');
      return;
    }

    setCreatingCreditBatch(true);
    try {
      const response = await axios.post('/api/admin/credit-codes/batch',
        { credit_amount: amount, quantity: creditBatchQuantity },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(`已批量生成 ${response.data.length} 个兑换码`);
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '批量生成兑换码失败');
    } finally {
      setCreatingCreditBatch(false);
    }
  };

  const selectedInvites = invites.filter((invite) => selectedInviteIds.includes(invite.id));
  const selectedCreditCodes = creditCodes.filter((code) => selectedCreditCodeIds.includes(code.id));
  const providerConfigByUserId = new Map(providerConfigs.map((config) => [config.user_id, config]));
  const normalizedUserSearchTerm = userSearchTerm.trim().toLowerCase();
  const filteredUsers = users.filter((user) => {
    const providerConfig = providerConfigByUserId.get(user.id);
    const matchesSearch = !normalizedUserSearchTerm || [
      user.id,
      user.username,
      user.nickname,
    ].some((value) => String(value ?? '').toLowerCase().includes(normalizedUserSearchTerm));
    const matchesStatus = userStatusFilter === 'all'
      || (userStatusFilter === 'active' && user.is_active)
      || (userStatusFilter === 'blocked' && !user.is_active);
    const matchesApi = userApiFilter === 'all'
      || (userApiFilter === 'configured' && providerConfig)
      || (userApiFilter === 'empty' && !providerConfig);

    return matchesSearch && matchesStatus && matchesApi;
  });

  const toggleInviteSelection = (inviteId) => {
    setSelectedInviteIds((current) => (
      current.includes(inviteId)
        ? current.filter((id) => id !== inviteId)
        : [...current, inviteId]
    ));
  };

  const toggleCreditCodeSelection = (codeId) => {
    setSelectedCreditCodeIds((current) => (
      current.includes(codeId)
        ? current.filter((id) => id !== codeId)
        : [...current, codeId]
    ));
  };

  const toggleAllInviteSelection = () => {
    setSelectedInviteIds((current) => (
      invites.length > 0 && current.length === invites.length ? [] : invites.map((invite) => invite.id)
    ));
  };

  const toggleAllCreditCodeSelection = () => {
    setSelectedCreditCodeIds((current) => (
      creditCodes.length > 0 && current.length === creditCodes.length ? [] : creditCodes.map((code) => code.id)
    ));
  };

  const copyInviteCodes = (onlySelected = false) => {
    const rows = onlySelected ? selectedInvites : invites;
    if (rows.length === 0) {
      toast.error(onlySelected ? '请先选择邀请码' : '暂无可复制的邀请码');
      return;
    }
    copyToClipboard(rows.map((invite) => invite.code).join('\n'));
  };

  const copyCreditCodes = (onlySelected = false) => {
    const rows = onlySelected ? selectedCreditCodes : creditCodes;
    if (rows.length === 0) {
      toast.error(onlySelected ? '请先选择兑换码' : '暂无可复制的兑换码');
      return;
    }
    copyToClipboard(rows.map((code) => code.code).join('\n'));
  };

  const downloadRows = (rows, format, filenameBase, headers, toRow) => {
    if (rows.length === 0) {
      toast.error('请先选择要导出的记录');
      return;
    }
    if (format === 'txt') {
      createTextDownload(`${rows.map((row) => row.code).join('\n')}\n`, `${filenameBase}.txt`);
      return;
    }
    const content = [
      headers.join(','),
      ...rows.map((row) => toRow(row).map(escapeCsvCell).join(',')),
    ].join('\n') + '\n';
    createTextDownload(content, `${filenameBase}.csv`, 'text/csv;charset=utf-8');
  };

  const downloadInvites = async (format, onlySelected = false) => {
    if (onlySelected) {
      downloadRows(
        selectedInvites,
        format,
        'gankaigc-selected-invites',
        ['code', 'is_active', 'created_by_type', 'used_by_user_id', 'created_at'],
        (invite) => [
          invite.code,
          invite.is_active,
          invite.created_by_type || 'admin',
          invite.used_by_user_id || '',
          invite.created_at || '',
        ],
      );
      return;
    }

    try {
      const response = await axios.get('/api/admin/invites/export', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { format },
        responseType: 'blob',
      });
      createTextDownload(response.data, `gankaigc-registration-invites.${format}`, format === 'csv' ? 'text/csv;charset=utf-8' : 'text/plain;charset=utf-8');
    } catch (error) {
      toast.error(error.response?.data?.detail || '导出邀请码失败');
    }
  };

  const downloadCreditCodes = async (format, onlySelected = false) => {
    if (onlySelected) {
      downloadRows(
        selectedCreditCodes,
        format,
        'gankaigc-selected-credit-codes',
        ['code', 'credit_amount', 'is_active', 'redeemed_by_user_id', 'created_at'],
        (code) => [
          code.code,
          code.credit_amount,
          code.is_active,
          code.redeemed_by_user_id || '',
          code.created_at || '',
        ],
      );
      return;
    }

    try {
      const response = await axios.get('/api/admin/credit-codes/export', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { format },
        responseType: 'blob',
      });
      createTextDownload(response.data, `gankaigc-credit-codes.${format}`, format === 'csv' ? 'text/csv;charset=utf-8' : 'text/plain;charset=utf-8');
    } catch (error) {
      toast.error(error.response?.data?.detail || '导出兑换码失败');
    }
  };

  const downloadUsers = () => {
    const rows = filteredUsers.length > 0 ? filteredUsers : users;
    if (rows.length === 0) {
      toast.error('暂无可导出的用户');
      return;
    }
    const content = [
      ['id', 'username', 'nickname', 'is_active', 'is_unlimited', 'credit_balance', 'zhuque_free_uses_remaining', 'zhuque_total_uses', 'created_at', 'last_login_at'].join(','),
      ...rows.map((user) => [
        user.id,
        user.username || '',
        user.nickname || '',
        user.is_active,
        user.is_unlimited,
        user.credit_balance ?? 0,
        user.zhuque_free_uses_remaining ?? '',
        user.zhuque_total_uses ?? 0,
        user.created_at || '',
        user.last_login_at || '',
      ].map(escapeCsvCell).join(',')),
    ].join('\n') + '\n';
    createTextDownload(content, 'gankaigc-admin-users.csv', 'text/csv;charset=utf-8');
  };

  const downloadAuditLogs = () => {
    const rows = filteredAuditLogs.length > 0 ? filteredAuditLogs : auditLogs;
    if (rows.length === 0) {
      toast.error('暂无可导出的操作日志');
      return;
    }
    const content = [
      ['id', 'action', 'target_type', 'target_id', 'detail', 'created_at'].join(','),
      ...rows.map((log) => [
        log.id || '',
        log.action || '',
        log.target_type || '',
        log.target_id || '',
        formatAuditDetail(log.detail),
        log.created_at || '',
      ].map(escapeCsvCell).join(',')),
    ].join('\n') + '\n';
    createTextDownload(content, 'gankaigc-admin-audit-logs.csv', 'text/csv;charset=utf-8');
  };

  const resetAuditFilters = () => {
    setAuditRoleFilter('all');
    setAuditActionFilter('all');
    setAuditResourceFilter('all');
    setAuditSeverityFilter('all');
    setAuditDateRange('all');
    fetchAuditLogs();
    setSelectedAuditLogId(null);
    toast.success('操作日志筛选已重置');
  };

  const updateAnnouncementContent = (nextContent, { selectionStart = null, selectionEnd = null, pushHistory = true } = {}) => {
    if (nextContent.length > 1000) {
      toast.error('公告内容最多 1000 字');
      return;
    }

    setAnnouncementContent(nextContent);
    if (pushHistory && nextContent !== announcementContent) {
      setAnnouncementContentHistory((current) => {
        const baseHistory = current.slice(0, announcementContentHistoryIndex + 1);
        return [...baseHistory, nextContent].slice(-50);
      });
      setAnnouncementContentHistoryIndex((current) => Math.min(current + 1, 49));
    }

    if (Number.isInteger(selectionStart) && Number.isInteger(selectionEnd)) {
      window.requestAnimationFrame(() => {
        announcementTextareaRef.current?.focus();
        announcementTextareaRef.current?.setSelectionRange(selectionStart, selectionEnd);
      });
    }
  };

  const resetAnnouncementContentHistory = (nextContent = '') => {
    setAnnouncementContentHistory([nextContent]);
    setAnnouncementContentHistoryIndex(0);
  };

  const undoAnnouncementContent = () => {
    if (announcementContentHistoryIndex <= 0) {
      toast('没有可撤销的 Markdown 编辑');
      return;
    }
    const nextIndex = announcementContentHistoryIndex - 1;
    const nextContent = announcementContentHistory[nextIndex] || '';
    setAnnouncementContentHistoryIndex(nextIndex);
    setAnnouncementContent(nextContent);
  };

  const redoAnnouncementContent = () => {
    if (announcementContentHistoryIndex >= announcementContentHistory.length - 1) {
      toast('没有可重做的 Markdown 编辑');
      return;
    }
    const nextIndex = announcementContentHistoryIndex + 1;
    const nextContent = announcementContentHistory[nextIndex] || '';
    setAnnouncementContentHistoryIndex(nextIndex);
    setAnnouncementContent(nextContent);
  };

  const applyAnnouncementMarkdownTool = (tool) => {
    if (tool.id === 'undo') {
      undoAnnouncementContent();
      return;
    }
    if (tool.id === 'redo') {
      redoAnnouncementContent();
      return;
    }
    if (tool.id === 'fullscreen') {
      setIsAnnouncementEditorExpanded((current) => !current);
      return;
    }

    const textarea = announcementTextareaRef.current;
    const content = announcementContent;
    const start = textarea?.selectionStart ?? content.length;
    const end = textarea?.selectionEnd ?? start;
    const selectedText = content.slice(start, end);
    let nextContent = content;
    let nextSelectionStart = start;
    let nextSelectionEnd = end;

    if (tool.syntax === 'line-prefix') {
      const lineStart = content.lastIndexOf('\n', Math.max(0, start - 1)) + 1;
      const nextLineBreak = content.indexOf('\n', end);
      const lineEnd = nextLineBreak === -1 ? content.length : nextLineBreak;
      const block = content.slice(lineStart, lineEnd) || '';
      const replacement = block
        .split('\n')
        .map((line) => `${tool.prefix}${line.replace(/^\s*/, '') || '内容'}`)
        .join('\n');
      nextContent = `${content.slice(0, lineStart)}${replacement}${content.slice(lineEnd)}`;
      nextSelectionStart = lineStart + tool.prefix.length;
      nextSelectionEnd = lineStart + replacement.length;
    } else if (tool.syntax === 'wrap') {
      const body = selectedText || tool.sample || '内容';
      const replacement = `${tool.prefix}${body}${tool.suffix}`;
      nextContent = `${content.slice(0, start)}${replacement}${content.slice(end)}`;
      nextSelectionStart = start + tool.prefix.length;
      nextSelectionEnd = nextSelectionStart + body.length;
    } else if (tool.syntax === 'block') {
      const body = selectedText || tool.sample || '内容';
      const replacement = `${tool.before}${body}${tool.after}`;
      nextContent = `${content.slice(0, start)}${replacement}${content.slice(end)}`;
      nextSelectionStart = start + tool.before.length;
      nextSelectionEnd = nextSelectionStart + body.length;
    } else if (tool.syntax === 'insert') {
      nextContent = `${content.slice(0, start)}${tool.text}${content.slice(end)}`;
      nextSelectionStart = start + tool.text.length;
      nextSelectionEnd = nextSelectionStart;
    }

    updateAnnouncementContent(nextContent, {
      selectionStart: nextSelectionStart,
      selectionEnd: nextSelectionEnd,
    });
  };

  const editAnnouncementDraft = (announcement) => {
    setAnnouncementTitle(announcement.title || '');
    setAnnouncementContent(announcement.content || '');
    resetAnnouncementContentHistory(announcement.content || '');
    setAnnouncementCategory(announcement.category || 'notice');
    toast.success('已载入公告到编辑区');
  };

  const submitAnnouncement = async (isActive) => {
    if (!announcementTitle.trim() || !announcementContent.trim()) {
      toast.error('请填写公告标题和内容');
      return;
    }

    try {
      await axios.post('/api/admin/announcements',
        {
          title: announcementTitle.trim(),
          content: announcementContent.trim(),
          category: announcementCategory,
          is_active: isActive,
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setAnnouncementTitle('');
      setAnnouncementContent('');
      resetAnnouncementContentHistory('');
      setAnnouncementCategory('notice');
      toast.success(isActive ? '公告已发布' : '草稿已保存');
      fetchAnnouncements();
    } catch (error) {
      toast.error(error.response?.data?.detail || (isActive ? '发布公告失败' : '保存草稿失败'));
    }
  };

  const saveAnnouncementDraft = () => {
    submitAnnouncement(false);
  };

  const handleCreateAnnouncement = (e) => {
    e.preventDefault();
    submitAnnouncement(true);
  };

  const handleToggleAnnouncement = async (announcement) => {
    try {
      await axios.patch(`/api/admin/announcements/${announcement.id}`,
        { is_active: !announcement.is_active },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(announcement.is_active ? '公告已隐藏' : '公告已启用');
      fetchAnnouncements();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新公告失败');
    }
  };

  const handleDeleteAnnouncement = async (announcement) => {
    const confirmed = window.confirm(`确认删除公告「${announcement.title}」吗？删除后用户工作台不会再显示。`);
    if (!confirmed) {
      return;
    }

    try {
      await axios.delete(`/api/admin/announcements/${announcement.id}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success('公告已删除');
      fetchAnnouncements();
    } catch (error) {
      toast.error(error.response?.data?.detail || '删除公告失败');
    }
  };

  const handleAddCredits = async (userId, explicitAmount = null) => {
    const amount = parseInt(explicitAmount ?? creditTopUps[userId], 10);
    if (!amount || amount < 1) {
      toast.error('充值啤酒必须大于 0');
      return;
    }

    try {
      await axios.post(`/api/admin/users/${userId}/credits`,
        { amount, reason: 'admin_recharge' },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setCreditTopUps((current) => ({ ...current, [userId]: '' }));
      toast.success('啤酒已充值');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '充值失败');
    }
  };

  const promptAddCredits = (user) => {
    const rawAmount = window.prompt(`给用户 ${user.username || user.id} 充值多少啤酒？`, creditTopUps[user.id] || '100');
    if (rawAmount === null) {
      return;
    }
    handleAddCredits(user.id, rawAmount);
  };

  const cycleAuditDateRange = () => {
    setAuditDateRange((current) => {
      if (current === '7d') return 'today';
      if (current === 'today') return 'all';
      return '7d';
    });
  };

  const handleToggleUnlimited = async (user) => {
    try {
      await axios.patch(`/api/admin/users/${user.id}/unlimited`,
        { is_unlimited: !user.is_unlimited },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(user.is_unlimited ? '已取消无限啤酒' : '已设为无限啤酒');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新无限啤酒状态失败');
    }
  };

  const handleToggleUserStatus = async (user) => {
    if (user.is_active) {
      const username = user.username || '未绑定账号';
      const confirmed = window.confirm(`确认封禁用户 ${username}（ID #${user.id}）？封禁后该用户将无法登录。`);
      if (!confirmed) {
        return;
      }
    }

    try {
      await axios.patch(`/api/admin/users/${user.id}/toggle`, {}, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success(user.is_active ? '用户已封禁' : '用户已解封');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新用户状态失败');
    }
  };

  // Login Page
  if (!isAuthenticated) {
    return (
      <div className="gank-auth-page flex items-center justify-center p-4">
        <div className="gank-auth-card rounded-[2rem] w-full max-w-md p-8 animate-fade-in-up">
          <div className="flex items-center justify-between mb-8">
            <BrandLogo size="sm" />
            <div className="gank-icon-tile w-12 h-12 rounded-2xl flex items-center justify-center">
              <Shield className="w-7 h-7" />
            </div>
          </div>
          <h1 className="text-3xl font-bold mb-2 text-gray-900">
            管理后台
          </h1>
          <p className="text-gray-600 mb-8">
            请使用管理员账号登录
          </p>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="gank-input px-4 py-3 rounded-xl"
                placeholder="请输入用户名"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="gank-input px-4 py-3 rounded-xl"
                placeholder="请输入密码"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="gank-primary-button w-full disabled:bg-gray-400 text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  登录中...
                </>
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  登录
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => navigate('/')}
              className="text-blue-600 hover:text-blue-700 text-sm"
            >
              返回首页
            </button>
          </div>
        </div>
      </div>
    );
  }

  const adminNavItems = [
    {
      id: 'dashboard',
      label: '数据面板',
      glyph: 'dashboard',
      hint: '总览',
    },
    {
      id: 'sessions',
      label: '会话监控',
      glyph: 'sessions',
      hint: '实时',
    },
    {
      id: 'operations',
      label: '运维状态',
      glyph: 'operations',
      hint: '健康',
    },
    {
      id: 'accounts',
      label: '用户管理',
      glyph: 'accounts',
      hint: '资产',
    },
    {
      id: 'announcements',
      label: '公告',
      glyph: 'announcements',
      hint: '发布',
    },
    {
      id: 'config',
      label: '系统配置',
      glyph: 'config',
      hint: '参数',
    },
    {
      id: 'audit',
      label: '操作日志',
      glyph: 'audit',
      hint: '审计',
    },
    {
      id: 'adminProfile',
      label: '个人资料',
      glyph: 'adminProfile',
      hint: '账户',
    },
  ];

  const processingStats = statistics?.processing || {};
  const processingSeries = processingStats.series || {};
  const completedTaskCount = Number(statistics?.sessions?.completed_in_range ?? statistics?.sessions?.completed ?? 0);
  const totalCharsProcessed = Number(processingStats.total_chars_processed_in_range ?? processingStats.total_chars_processed ?? 0);
  const avgCharsPerTask = Number(processingStats.avg_input_chars ?? (
    completedTaskCount > 0
      ? Math.round(totalCharsProcessed / completedTaskCount)
      : 0
  ));
  const updateAvailable = Boolean(
    updateStatus?.release_update_available || updateStatus?.source_update_available
  );
  const updateStatusLabel = updateAvailable ? '可手动升级' : '已是最新版本';
  const manualUpdateCommand = updateStatus?.setup_command
    || 'git fetch --tags origin main\ngit pull --ff-only origin main\ndocker compose --env-file .env.docker up -d --build';
  const successRateValue = Number(statistics?.sessions?.success_rate ?? (
    statistics?.sessions?.in_range > 0
      ? (Number(statistics.sessions.completed_in_range || 0) / Number(statistics.sessions.in_range || 1)) * 100
      : 0
  ));
  const successRate = `${successRateValue.toFixed(2)}%`;
  const legacyModeRows = [
    { id: 'paper_polish', label: '论文润色', count: Number(processingStats.paper_polish_count || 0) },
    { id: 'paper_enhance', label: '论文增强', count: Number(processingStats.paper_enhance_count || 0) },
    { id: 'paper_polish_enhance', label: '润色 + 增强', count: Number(processingStats.paper_polish_enhance_count || 0) },
    { id: 'emotion_polish', label: '感情文章润色', count: Number(processingStats.emotion_polish_count || 0) },
    { id: 'ai_detect_reduce', label: 'AI检测+降重', count: Number(processingStats.ai_detect_reduce_count || 0) },
  ];
  const sourceModeRows = Array.isArray(processingStats.mode_rows) && processingStats.mode_rows.length > 0
    ? processingStats.mode_rows
    : legacyModeRows;
  const modeRows = sourceModeRows.map((mode, index) => ({
    id: mode.id,
    label: mode.label || getModeLabel(mode.id),
    count: Number(mode.count || 0),
    percent: Number(mode.percent || 0),
    trendPercent: mode.trend_percent,
    trend: formatTrendPercent(mode.trend_percent),
    spark: getSeriesValues(mode.series, Number(mode.count || 0)),
    tone: modeTones[mode.id] || chartTones[index % chartTones.length],
  }));
  const modeTotal = modeRows.reduce((sum, mode) => sum + mode.count, 0);
  const mostPopularMode = modeRows.reduce((best, mode) => (mode.count > best.count ? mode : best), modeRows[0] || { label: '-', count: 0 });
  const donutStops = modeRows.slice(0, 4).reduce((acc, mode, index) => {
    const previous = index === 0 ? 0 : acc[index - 1];
    const percent = modeTotal > 0 ? (mode.count / modeTotal) * 100 : 0;
    acc.push(Math.min(100, previous + percent));
    return acc;
  }, []);
  const donutStyle = {
    '--p1': `${(donutStops[0] || 0).toFixed(2)}%`,
    '--p2': `${(donutStops[1] || donutStops[0] || 0).toFixed(2)}%`,
    '--p3': `${(donutStops[2] || donutStops[1] || donutStops[0] || 0).toFixed(2)}%`,
  };
  const auditRoleOptions = Array.from(new Set(auditLogs.map((log) => log.admin_username).filter(Boolean)));
  const auditActionOptions = Array.from(new Set(auditLogs.map((log) => log.action).filter(Boolean)));
  const auditResourceOptions = Array.from(new Set(auditLogs.map((log) => log.target_type || '系统').filter(Boolean)));
  const isAuditLogInsideDateRange = (log) => {
    if (auditDateRange === 'all') {
      return true;
    }
    const createdAt = parseBackendDate(log?.created_at);
    if (!createdAt) {
      return false;
    }
    if (auditDateRange === 'today') {
      return formatChinaDate(createdAt) === formatChinaDate(new Date());
    }
    return Date.now() - createdAt.getTime() <= 7 * 24 * 60 * 60 * 1000;
  };
  const filteredAuditLogs = auditLogs.filter((log) => {
    const severity = getAuditSeverity(log.action).label;
    return (auditRoleFilter === 'all' || log.admin_username === auditRoleFilter)
      && (auditActionFilter === 'all' || log.action === auditActionFilter)
      && (auditResourceFilter === 'all' || (log.target_type || '系统') === auditResourceFilter)
      && (auditSeverityFilter === 'all' || severity === auditSeverityFilter)
      && isAuditLogInsideDateRange(log);
  });
  const selectedAuditLog = filteredAuditLogs.find((log) => log.id === selectedAuditLogId) || filteredAuditLogs[0] || null;
  const topbarVersionLabel = updateStatus?.current_version || CURRENT_APP_VERSION;
  const adminTopbarStatusTime = formatChinaDateTime(new Date()).replace(/\//g, '-');
  const sidebarVariantClass = [
    'aurora-admin-sidebar--plain',
    sidebarCollapsed ? 'aurora-admin-sidebar--collapsed' : '',
  ].filter(Boolean).join(' ');

  // Admin Dashboard
  return (
    <div className="gank-app-page aurora-app-page aurora-admin-page" data-admin-tab={activeTab}>
      {/* Header */}
      <div className="apple-global-nav aurora-topbar aurora-admin-topbar sticky top-0 z-50">
        <div className="w-full px-4 sm:px-6 lg:px-8 py-3">
          <div className="aurora-admin-topbar-row flex items-center justify-between">
            <div className="aurora-admin-brand-stack">
              <BrandLogo size="sm" showText={false} className="aurora-brand-logo aurora-admin-brand-mark-only" />
              <div className="aurora-admin-brand-copy">
                <span className="aurora-admin-brand-title">GankAIGC</span>
                <button
                  type="button"
                  onClick={openUpdateModal}
                  className="aurora-admin-version-badge"
                  title="查看版本和 SSH 升级命令"
                  aria-label={`当前版本 ${topbarVersionLabel}，点击查看版本和 SSH 升级命令`}
                >
                  {topbarVersionLabel}
                </button>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <button
                type="button"
                onClick={openGithubIssues}
                className="aurora-admin-icon-button"
                aria-label="打开 GitHub Issues"
                title="前往 GitHub Issues"
              >
                <Github className="h-5 w-5" />
              </button>
              <button
                onClick={handleLogout}
                className="aurora-admin-profile-button"
                title="退出登录"
                aria-label="退出管理员登录"
              >
                <span className="hidden sm:inline">退出</span>
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="aurora-page-shell aurora-admin-shell" data-sidebar-collapsed={sidebarCollapsed ? 'true' : 'false'}>
        <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)] gap-0 items-start">
          <aside
            data-admin-nav="sidebar"
            className={`aurora-admin-sidebar ${sidebarVariantClass} p-3 lg:sticky lg:top-[76px] lg:min-h-[calc(100vh-8rem)] lg:flex lg:flex-col`}
          >
            <nav className="flex lg:flex-col lg:flex-1 gap-2 overflow-x-auto lg:overflow-visible" aria-label="后台管理导航">
              {adminNavItems.map(({ id, label, glyph }) => (
                <button
                  key={id}
                  onClick={() => handleAdminTabChange(id)}
                  className={`aurora-admin-nav-item group flex min-w-max lg:min-w-0 items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-all duration-200 ${
                    activeTab === id ? 'aurora-admin-nav-item-active' : ''
                  }`}
                >
                  <span className="aurora-admin-nav-icon">
                    <AdminNavGlyph type={glyph} className="w-5 h-5 transition-transform duration-200 group-hover:scale-105" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col items-start">
                    <span className="whitespace-nowrap">{label}</span>
                  </span>
                </button>
              ))}
            </nav>
            <button
              type="button"
              onClick={toggleSidebarCollapsed}
              className="aurora-admin-collapse-button mt-3 hidden lg:flex"
              aria-pressed={sidebarCollapsed}
            >
              <PanelLeftClose className={`h-4 w-4 ${sidebarCollapsed ? 'rotate-180' : ''}`} />
              <span>{sidebarCollapsed ? '展开菜单' : '收起菜单'}</span>
            </button>
          </aside>

          <main className="aurora-admin-main min-w-0 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <div className="aurora-admin-section space-y-6">
            <div className="aurora-admin-section-head aurora-admin-dashboard-head">
                      <div>
                        <span className="sr-only">平均输入规模</span>
                        <h1>数据面板</h1>
                      </div>
              <div className="aurora-admin-dashboard-toolbar aurora-admin-dashboard-toolbar-inline">
                <select
                  value={dashboardDateRange}
                  onChange={(event) => setDashboardDateRange(event.target.value)}
                  className="aurora-admin-date-range"
                  aria-label="选择统计时间范围"
                >
                  <option value="7d">最近 7 天</option>
                  <option value="today">今日数据</option>
                  <option value="30d">近 30 天</option>
                </select>
                <button
                  onClick={fetchStatistics}
                  disabled={loadingStats}
                  className="aurora-admin-icon-button"
                  aria-label="刷新数据"
                >
                  <RefreshCw className={`h-4 w-4 ${loadingStats ? 'animate-spin' : ''}`} />
                </button>
                <button
                  type="button"
                  onClick={() => createTextDownload(
                    JSON.stringify(statistics, null, 2),
                    `gankaigc-admin-statistics-${dashboardDateRange}.json`,
                    'application/json;charset=utf-8'
                  )}
                  className="aurora-admin-icon-button"
                  aria-label="下载统计数据"
                  disabled={!statistics}
                >
                  <Download className="h-4 w-4" />
                </button>
              </div>
            </div>

            {loadingStats && !statistics && (
              <div className="aurora-admin-card aurora-loading-card">
                <Loader2 className="h-5 w-5 animate-spin" />
                正在加载后台统计
              </div>
            )}

            {/* Statistics Cards */}
            {statistics && (
              <div className="aurora-admin-dashboard-grid">

                <div className="aurora-admin-kpi-grid">
                  <AdminMetricCard
                    icon={MessageSquare}
                    title="范围会话数"
                    value={formatAdminNumber(statistics.sessions.in_range ?? statistics.sessions.total)}
                    tone="blue"
                    trendPercent={statistics.sessions.trend_percent}
                    points={getSeriesValues(processingSeries.sessions, Number(statistics.sessions.in_range || 0))}
                  />
                  <AdminMetricCard
                    icon={Users}
                    title="活跃用户数"
                    value={formatAdminNumber(statistics.users.active_in_range ?? statistics.users.active)}
                    tone="cyan"
                    trendPercent={statistics.users.trend_percent}
                    points={getSeriesValues(processingSeries.active_users, Number(statistics.users.active_in_range || 0))}
                  />
                  <AdminMetricCard
                    icon={FileText}
                    title="范围请求数"
                    value={formatAdminNumber(statistics.requests?.in_range ?? statistics.sessions.in_range ?? statistics.sessions.total)}
                    tone="violet"
                    trendPercent={statistics.requests?.trend_percent ?? statistics.sessions.trend_percent}
                    points={getSeriesValues(processingSeries.sessions, Number(statistics.requests?.in_range || statistics.sessions.in_range || 0))}
                  />
                  <AdminMetricCard
                    icon={Sparkles}
                    title="范围生成数"
                    value={formatAdminNumber(statistics.sessions.completed_in_range ?? statistics.sessions.completed)}
                    tone="amber"
                    trendPercent={statistics.sessions.completed_trend_percent}
                    points={getSeriesValues(processingSeries.completed_sessions, Number(statistics.sessions.completed_in_range || 0))}
                  />
                  <AdminMetricCard
                    icon={CheckCircle}
                    title="成功率"
                    value={successRate}
                    tone="slate"
                    trendPercent={statistics.sessions.success_rate_trend_percent}
                    points={getSeriesValues(processingSeries.success_rate, successRateValue)}
                  />
                </div>

                {statistics.processing && (
                  <>
                    <div className="aurora-admin-analytics-grid">
                      <AdminChartCard
                        title="处理字符总数"
                        value={formatAdminNumber(totalCharsProcessed)}
                        suffix="字符"
                        tone="blue"
                        icon={AdminALinesGlyph}
                        trendPercent={processingStats.chars_trend_percent}
                      >
                        <AdminBarChart tone="blue" values={processingSeries.chars_processed} />
                      </AdminChartCard>

                      <AdminChartCard
                        title="平均处理时间"
                        value={Math.round(processingStats.avg_processing_time_in_range ?? processingStats.avg_processing_time ?? 0)}
                        suffix="s"
                        tone="cyan"
                        icon={Clock}
                        trendPercent={processingStats.avg_processing_time_trend_percent}
                      >
                        <AdminLineChart tone="cyan" values={processingSeries.avg_processing_time} />
                      </AdminChartCard>

                      <AdminChartCard
                        title="平均输入大小"
                        value={formatAdminNumber(avgCharsPerTask)}
                        suffix="字符"
                        tone="violet"
                        icon={AdminKeyboardGlyph}
                        trendPercent={processingStats.avg_input_chars_trend_percent}
                      >
                        <AdminLineChart tone="violet" area values={processingSeries.avg_input_chars} />
                      </AdminChartCard>
                    </div>

                    <div className="aurora-admin-card aurora-admin-mode-card" data-admin-processing-modes>
                      <div className="aurora-admin-mode-head">
                        <div>
                          <h3>AI 模式统计</h3>
                          <p>{modeRows.length} 种降 AI 模式统计 · {statistics.range?.label || '当前范围'}</p>
                        </div>
                      </div>

                      <div className="aurora-admin-mode-layout">
                        <div className="aurora-admin-donut-wrap">
                          <div className="aurora-admin-donut" style={donutStyle}>
                            <div>
                              <span>总生成数</span>
                              <strong>{formatAdminNumber(modeTotal)}</strong>
                            </div>
                          </div>
                        </div>

                        <div className="aurora-admin-mode-table">
                          <div className="aurora-admin-mode-row aurora-admin-mode-row-head">
                            <span>模式</span>
                            <span>生成数</span>
                            <span>占比</span>
                            <span>上一周期</span>
                            <span>趋势</span>
                          </div>
                          {modeRows.map((mode) => {
                            const percent = modeTotal > 0 ? ((mode.count / modeTotal) * 100).toFixed(2) : Number(mode.percent || 0).toFixed(2);
                            return (
                              <div key={mode.id} className="aurora-admin-mode-row">
                                <span className="aurora-admin-mode-name">
                                  <i className={`aurora-admin-mode-dot aurora-admin-mode-dot-${mode.tone}`} />
                                  {mode.label}
                                </span>
                                <span>{formatAdminNumber(mode.count)}</span>
                                <span>{percent}%</span>
                                <span className={isTrendDown(mode.trendPercent, mode.trend) ? 'text-emerald-600' : 'text-emerald-600'}>{mode.trend}</span>
                                <span><MiniSparkline tone={mode.tone} points={mode.spark} /></span>
                              </div>
                            );
                          })}
                        </div>

                        <div className="aurora-admin-mode-summary" data-admin-processing-summary>
                          <div className="aurora-admin-summary-tile">
                            <BarChart3 className="h-7 w-7" />
                            <span>最受欢迎模式</span>
                            <strong>{mostPopularMode.label}</strong>
                            <p>{modeTotal > 0 ? ((mostPopularMode.count / modeTotal) * 100).toFixed(2) : '0.00'}% 的生成占比</p>
                          </div>
                          <div className="aurora-admin-summary-tile is-muted">
                            <AdminStarGrowthGlyph className="h-6 w-6" />
                            <span>上一周期变化</span>
                            <strong>{formatTrendPercent(mostPopularMode.trendPercent).replace('较上一周期 ', '')}</strong>
                            <p>基于当前筛选范围与上一周期真实对比</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Account and Beer Tab */}
        {activeTab === 'accounts' && (
          <div className="aurora-admin-section aurora-admin-accounts-page space-y-6">
            <div className="aurora-admin-card aurora-admin-account-utility-tabs p-1">
              <div className="aurora-admin-account-tabs-row">
                <div className="aurora-admin-account-tab-list">
                  {ACCOUNT_PANEL_TABS.map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setAccountPanelTab(tab.id)}
                      className={`aurora-admin-tab-button rounded-xl px-4 py-2 text-sm font-semibold transition-colors ${
                        accountPanelTab === tab.id
                          ? 'aurora-admin-tab-button-active'
                          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                <div className="aurora-admin-user-head-actions">
                  {accountPanelTab === 'users' && (
                    <button
                      type="button"
                      onClick={() => {
                        setUserStatusFilter('all');
                        setUserApiFilter('all');
                        setUserSearchTerm('');
                      }}
                      className="aurora-admin-subtle-button"
                    >
                      <Filter className="h-4 w-4" />
                      清除筛选
                    </button>
                  )}
                  <button
                    onClick={fetchAccountData}
                    disabled={loadingAccountData}
                    className="aurora-admin-icon-button"
                    aria-label="刷新用户数据"
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingAccountData ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              {accountPanelTab === 'invites' && (
              <div className="aurora-admin-card p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                    <Key className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">注册邀请码</h3>
                    <p className="text-xs text-gray-500">留空会自动生成随机邀请码</p>
                  </div>
                </div>

                <form onSubmit={handleCreateInvite} className={ADMIN_ACCOUNT_FORM_CLASS}>
                  <input
                    type="text"
                    value={newInviteCode}
                    onChange={(e) => setNewInviteCode(e.target.value)}
                    placeholder="邀请码，可留空自动生成"
                    className={ADMIN_ACCOUNT_WIDE_INPUT_CLASS}
                  />
                  <button
                    type="submit"
                    className={ADMIN_ACCOUNT_ACTION_BUTTON_CLASS}
                  >
                    <Plus className="w-4 h-4" />
                    创建
                  </button>
                </form>

                <div className="mb-5 flex flex-col gap-3 rounded-xl border border-blue-100 bg-blue-50/50 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-gray-800">批量生成</span>
                    {[10, 50, 100].map((quantity) => (
                      <button
                        key={quantity}
                        type="button"
                        onClick={() => setInviteBatchQuantity(quantity)}
                        className={`h-9 rounded-lg px-3 text-sm font-semibold transition-colors ${
                          inviteBatchQuantity === quantity
                            ? 'bg-blue-600 text-white'
                            : 'bg-white text-blue-700 hover:bg-blue-100'
                        }`}
                      >
                        {quantity}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={handleBatchCreateInvites}
                      disabled={creatingInviteBatch}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-gray-300"
                    >
                      {creatingInviteBatch ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      生成
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => copyInviteCodes(selectedInviteIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Copy className="h-4 w-4" />
                      {selectedInviteIds.length > 0 ? `复制选中 ${selectedInviteIds.length}` : '复制全部'}
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadInvites('csv', selectedInviteIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4" />
                      CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadInvites('txt', selectedInviteIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4" />
                      TXT
                    </button>
                  </div>
                </div>

                <div className={ADMIN_COMPACT_TABLE_SCROLL_CLASS}>
                  <table className="w-full table-auto divide-y divide-gray-200">
                    <thead className={ADMIN_COMPACT_TABLE_HEAD_CLASS}>
                      <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <th className="w-10 py-3 pr-4 whitespace-nowrap">
                          <input
                            type="checkbox"
                            checked={invites.length > 0 && selectedInviteIds.length === invites.length}
                            onChange={toggleAllInviteSelection}
                            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            title="全选邀请码"
                          />
                        </th>
                        <th className="w-[26%] py-3 pr-4 whitespace-nowrap">邀请码</th>
                        <th className="w-[9%] py-3 pr-4 whitespace-nowrap">状态</th>
                        <th className="w-[20%] py-3 pr-4 whitespace-nowrap">来源</th>
                        <th className="w-[20%] py-3 pr-4 whitespace-nowrap">注册用户</th>
                        <th className="w-[7rem] py-3 pr-4 whitespace-nowrap">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {invites.length === 0 ? (
                        <tr>
                          <td colSpan="6" className="py-8 text-center text-sm text-gray-500">暂无邀请码</td>
                        </tr>
                      ) : invites.map((invite) => (
                        <tr key={invite.id}>
                          <td className="w-10 py-3 pr-4 whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={selectedInviteIds.includes(invite.id)}
                              onChange={() => toggleInviteSelection(invite.id)}
                              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                              title="选择邀请码"
                            />
                          </td>
                          <td className="w-[26%] py-3 pr-4 whitespace-nowrap">
                            <button
                              onClick={() => copyToClipboard(invite.code)}
                              className="max-w-full truncate font-mono text-sm text-blue-700 hover:text-blue-900"
                              title="点击复制"
                            >
                              {invite.code}
                            </button>
                          </td>
                          <td className="w-[9%] py-3 pr-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              invite.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'
                            }`}>
                              {invite.is_active ? '启用' : '停用'}
                            </span>
                          </td>
                          <td className="w-[20%] py-3 pr-4 text-sm text-gray-700 whitespace-nowrap">
                            {invite.created_by_type === 'user' ? (
                              <div className="min-w-0">
                                <div className="truncate font-medium text-gray-900">
                                  {invite.created_by_display_name || `用户 #${invite.created_by_user_id}`}
                                </div>
                                <div className="truncate text-xs text-gray-500">用户邀请 · ID #{invite.created_by_user_id}</div>
                              </div>
                            ) : (
                              <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
                                管理员创建
                              </span>
                            )}
                          </td>
                          <td className="w-[20%] py-3 pr-4 text-sm text-gray-700 whitespace-nowrap">
                            {invite.used_by_user_id ? (
                              <div className="min-w-0">
                                <div className="truncate font-medium text-gray-900">
                                  {invite.used_by_display_name || `用户 #${invite.used_by_user_id}`}
                                </div>
                                <div className="text-xs text-gray-500">ID #{invite.used_by_user_id}</div>
                              </div>
                            ) : '-'}
                          </td>
                          <td className="w-[7rem] py-3 pr-4 whitespace-nowrap">
                            <button
                              onClick={() => handleToggleInvite(invite.id)}
                              className="text-sm px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded transition-colors"
                            >
                              {invite.is_active ? '停用' : '启用'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              )}

              {accountPanelTab === 'creditCodes' && (
              <div className="aurora-admin-card p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-emerald-50 rounded-xl flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">啤酒兑换码</h3>
                    <p className="text-xs text-gray-500">用户兑换后增加平台啤酒</p>
                  </div>
                </div>

                <form onSubmit={handleCreateCreditCode} className={ADMIN_ACCOUNT_FORM_CLASS}>
                  <input
                    type="text"
                    value={newCreditCode}
                    onChange={(e) => setNewCreditCode(e.target.value)}
                    placeholder="兑换码，可留空生成"
                    className={ADMIN_ACCOUNT_INPUT_CLASS}
                  />
                  <input
                    type="number"
                    min="1"
                    value={newCreditAmount}
                    onChange={(e) => setNewCreditAmount(e.target.value)}
                    className={ADMIN_ACCOUNT_INPUT_CLASS}
                  />
                  <button
                    type="submit"
                    className={ADMIN_ACCOUNT_ACTION_BUTTON_CLASS}
                  >
                    <Plus className="w-4 h-4" />
                    创建
                  </button>
                </form>

                <div className="mb-5 flex flex-col gap-3 rounded-xl border border-emerald-100 bg-emerald-50/50 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-gray-800">批量生成</span>
                    {[10, 50, 100].map((quantity) => (
                      <button
                        key={quantity}
                        type="button"
                        onClick={() => setCreditBatchQuantity(quantity)}
                        className={`h-9 rounded-lg px-3 text-sm font-semibold transition-colors ${
                          creditBatchQuantity === quantity
                            ? 'bg-emerald-600 text-white'
                            : 'bg-white text-emerald-700 hover:bg-emerald-100'
                        }`}
                      >
                        {quantity}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={handleBatchCreateCreditCodes}
                      disabled={creatingCreditBatch}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:bg-gray-300"
                    >
                      {creatingCreditBatch ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      生成
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => copyCreditCodes(selectedCreditCodeIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Copy className="h-4 w-4" />
                      {selectedCreditCodeIds.length > 0 ? `复制选中 ${selectedCreditCodeIds.length}` : '复制全部'}
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadCreditCodes('csv', selectedCreditCodeIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4" />
                      CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadCreditCodes('txt', selectedCreditCodeIds.length > 0)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-white px-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      <Download className="h-4 w-4" />
                      TXT
                    </button>
                  </div>
                </div>

                <div className={ADMIN_COMPACT_TABLE_SCROLL_CLASS}>
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className={ADMIN_COMPACT_TABLE_HEAD_CLASS}>
                      <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <th className="py-3 pr-4">
                          <input
                            type="checkbox"
                            checked={creditCodes.length > 0 && selectedCreditCodeIds.length === creditCodes.length}
                            onChange={toggleAllCreditCodeSelection}
                            className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                            title="全选兑换码"
                          />
                        </th>
                        <th className="py-3 pr-4">兑换码</th>
                        <th className="py-3 pr-4">啤酒</th>
                        <th className="py-3 pr-4">状态</th>
                        <th className="py-3 pr-4">兑换者</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {creditCodes.length === 0 ? (
                        <tr>
                          <td colSpan="5" className="py-8 text-center text-sm text-gray-500">暂无兑换码</td>
                        </tr>
                      ) : creditCodes.map((code) => (
                        <tr key={code.id}>
                          <td className="py-3 pr-4">
                            <input
                              type="checkbox"
                              checked={selectedCreditCodeIds.includes(code.id)}
                              onChange={() => toggleCreditCodeSelection(code.id)}
                              className="h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                              title="选择兑换码"
                            />
                          </td>
                          <td className="py-3 pr-4">
                            <button
                              onClick={() => copyToClipboard(code.code)}
                              className="font-mono text-sm text-emerald-700 hover:text-emerald-900"
                              title="点击复制"
                            >
                              {code.code}
                            </button>
                          </td>
                          <td className="py-3 pr-4 text-sm font-semibold text-gray-900">{code.credit_amount}</td>
                          <td className="py-3 pr-4">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              code.redeemed_by_user_id
                                ? 'bg-blue-100 text-blue-800'
                                : code.is_active
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-gray-100 text-gray-700'
                            }`}>
                              {code.redeemed_by_user_id ? '已兑换' : code.is_active ? '可用' : '停用'}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-sm text-gray-600">{code.redeemed_by_user_id || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              )}
            </div>

            {accountPanelTab === 'users' && (
              <div className="aurora-admin-users-layout">
                <div className="aurora-admin-card overflow-hidden">
                  <div className="aurora-admin-users-toolbar">
                    <div className="aurora-admin-user-filter-strip">
                      <span>角色：</span>
                      <button type="button" className={userApiFilter === 'all' ? 'is-active' : ''} onClick={() => setUserApiFilter('all')}>全部</button>
                      <button type="button" className={userApiFilter === 'empty' ? 'is-active' : ''} onClick={() => setUserApiFilter('empty')}>普通用户</button>
                      <button type="button" className={userApiFilter === 'configured' ? 'is-active' : ''} onClick={() => setUserApiFilter('configured')}>VIP用户</button>
                      <i />
                      <span>状态：</span>
                      <button type="button" className={userStatusFilter === 'all' ? 'is-active' : ''} onClick={() => setUserStatusFilter('all')}>全部</button>
                      <button type="button" className={userStatusFilter === 'active' ? 'is-active' : ''} onClick={() => setUserStatusFilter('active')}>正常</button>
                      <button type="button" className={userStatusFilter === 'blocked' ? 'is-active' : ''} onClick={() => setUserStatusFilter('blocked')}>封禁</button>
                      <label className="aurora-admin-user-filter-search relative">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                        <input
                          type="search"
                          value={userSearchTerm}
                          onChange={(e) => setUserSearchTerm(e.target.value)}
                          placeholder="搜索用户名 / 邮箱 / UID"
                          className="aurora-admin-input h-11 w-full pl-9 pr-3 text-sm"
                        />
                      </label>
                      <button type="button" onClick={downloadUsers} className="aurora-admin-user-filter-export"><Download className="h-4 w-4" /> 导出</button>
                    </div>
                    <div className="aurora-admin-users-table-actions">
                      <span>共 {filteredUsers.length || users.length} 条</span>
                    </div>
                  </div>

                  <div className={ADMIN_TABLE_SCROLL_CLASS}>
                    <table className="w-full min-w-[1260px] divide-y divide-gray-200 aurora-admin-user-table">
                      <thead className={ADMIN_TABLE_HEAD_CLASS}>
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户名</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">角色</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">啤酒余额</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">朱雀剩余次数</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最近活跃</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {filteredUsers.length === 0 ? (
                          <tr>
                            <td colSpan="7" className="px-6 py-10 text-center text-sm text-gray-500">没有符合筛选条件的用户</td>
                          </tr>
                        ) : filteredUsers.map((user) => {
                          const providerConfig = providerConfigByUserId.get(user.id);
                          const role = getAdminUserRole(user, providerConfig);
                          const userAvatarFallback = (user.nickname || user.username || 'U').slice(0, 1).toUpperCase();
                          return (
                          <tr
                            key={user.id}
                            className={user.is_active ? 'hover:bg-gray-50' : 'bg-red-50/40 hover:bg-red-50'}
                          >
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="flex items-center gap-3">
                                <span className="aurora-admin-user-avatar">
                                  {user.avatar_url ? (
                                    <>
                                      <img src={user.avatar_url} alt=""
                                        onError={(event) => {
                                          event.currentTarget.hidden = true;
                                          event.currentTarget.nextElementSibling?.removeAttribute('hidden');
                                        }}
                                      />
                                      <span hidden>{userAvatarFallback}</span>
                                    </>
                                  ) : (
                                    userAvatarFallback
                                  )}
                                </span>
                                <div>
                                  <div className="text-sm font-medium text-gray-900">{user.username || '未绑定账号'}</div>
                                  <div className="text-xs text-gray-500">UID: {user.id}</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span className={`aurora-admin-user-role-badge ${role.className}`}>
                                {role.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                                user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-700'
                              }`}>
                                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                                {user.is_active ? '正常' : '已封禁'}
                              </span>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700">
                                {user.is_unlimited ? '∞' : formatAdminNumber(user.credit_balance ?? 0)}
                                <BeerIcon className="h-4 w-4" />
                              </div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              <div className="inline-flex items-center gap-1 text-sm font-semibold text-slate-700">
                                {(user.zhuque_free_uses_remaining ?? -1) >= 0 ? (
                                  formatAdminNumber(user.zhuque_free_uses_remaining)
                                ) : (
                                  <span className="text-sm font-semibold text-slate-500">--</span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                              {user.last_login_at ? formatChinaDateTime(user.last_login_at) : '-'}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-right">
                              <div className="aurora-admin-user-row-actions">
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleToggleUserStatus(user);
                                  }}
                                  className={`aurora-admin-icon-mini aurora-admin-status-toggle ${user.is_active ? 'is-danger' : 'is-restore'}`}
                                  title={user.is_active ? '封禁' : '启用'}
                                  aria-label={user.is_active ? '封禁用户' : '启用用户'}
                                >
                                  {user.is_active ? <Ban className="h-4 w-4" /> : <UserCheck className="h-4 w-4" />}
                                </button>
                                <input
                                  type="number"
                                  min="1"
                                  value={creditTopUps[user.id] || ''}
                                  onClick={(event) => event.stopPropagation()}
                                  onChange={(e) => setCreditTopUps((current) => ({ ...current, [user.id]: e.target.value }))}
                                  placeholder="啤酒"
                                  className="aurora-admin-row-credit-input"
                                />
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleAddCredits(user.id);
                                  }}
                                  className="aurora-admin-icon-mini is-blue"
                                  title="充值"
                                >
                                  <Plus className="h-4 w-4" />
                                </button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleToggleUnlimited(user);
                                  }}
                                  className={`aurora-admin-icon-mini aurora-admin-unlimited-toggle ${user.is_unlimited ? 'is-active' : ''}`}
                                  title={user.is_unlimited ? '取消无限' : '设为无限'}
                                  aria-label={user.is_unlimited ? '取消无限啤酒' : '设为无限啤酒'}
                                >
                                  <CircleDollarSign className="h-4 w-4" />
                                  <span>{user.is_unlimited ? '取消无限' : '设为无限'}</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>
            )}

            {accountPanelTab === 'creditTransactions' && (
            <div className="aurora-admin-card overflow-hidden">
              <div className="p-6 border-b border-gray-200 flex items-center gap-3">
                <div className="w-10 h-10 bg-amber-50 rounded-xl flex items-center justify-center">
                  <BeerIcon className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">最近啤酒流水</h3>
                  <p className="text-xs text-gray-500 mt-1">展示充值、兑换、降 AI 消耗和失败退款，方便排查用户余额变化</p>
                </div>
              </div>
              <div className={ADMIN_TABLE_SCROLL_CLASS}>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className={ADMIN_TABLE_HEAD_CLASS}>
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">类型</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">变动</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">关联</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {creditTransactions.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="px-6 py-10 text-center text-sm text-gray-500">暂无啤酒流水</td>
                      </tr>
                    ) : creditTransactions.map((transaction) => (
                      <tr key={transaction.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{transaction.user_display_name || transaction.username || `用户 #${transaction.user_id}`}</div>
                          <div className="text-xs text-gray-500">ID #{transaction.user_id}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-sm font-semibold text-gray-900">{transaction.reason_label || transaction.reason}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-bold ${getCreditTransactionClass(transaction)}`}>
                            {formatBeerDelta(transaction.delta)}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">余额 {transaction.balance_after} 啤酒</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {transaction.related_session_title
                            ? `任务：${transaction.related_session_title}`
                            : transaction.related_session_public_id
                              ? `会话：${transaction.related_session_public_id.slice(0, 8)}…`
                              : transaction.related_code_id
                                ? `兑换码 #${transaction.related_code_id}`
                                : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatChinaDateTime(transaction.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}

            {accountPanelTab === 'apiConfigs' && (
            <div className="aurora-admin-card overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">用户自带 API 配置摘要</h3>
                <p className="text-xs text-gray-500 mt-1">仅显示 base_url、模型名和 API Key 后四位，不展示完整密钥</p>
              </div>
              <div className={ADMIN_TABLE_SCROLL_CLASS}>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className={ADMIN_TABLE_HEAD_CLASS}>
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Base URL</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Key</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">模型</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">更新时间</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {providerConfigs.length === 0 ? (
                      <tr>
                        <td colSpan="5" className="px-6 py-10 text-center text-sm text-gray-500">暂无用户配置自带 API</td>
                      </tr>
                    ) : providerConfigs.map((config) => (
                      <tr key={config.user_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{config.username}</div>
                          <div className="text-xs text-gray-500">ID #{config.user_id}</div>
                        </td>
                        <td className="px-6 py-4 max-w-xs truncate text-sm text-gray-700">{config.base_url}</td>
                        <td className="px-6 py-4 whitespace-nowrap font-mono text-sm text-gray-700">****{config.api_key_last4}</td>
                        <td className="px-6 py-4 text-sm text-gray-700">
                          <div>润色：{config.polish_model}</div>
                          <div>降重：{config.enhance_model}</div>
                          <div>情感：{config.emotion_model || '-'}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatChinaDateTime(config.updated_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}
          </div>
        )}
        
        {/* Session Monitor Tab */}
        {activeTab === 'sessions' && (
          <SessionMonitor adminToken={adminToken} />
        )}

        {activeTab === 'operations' && (
          <AdminOperationsPanel adminToken={adminToken} />
        )}

        {activeTab === 'announcements' && (
          <div className="aurora-admin-section space-y-6">
            <div className={`aurora-admin-announcement-composer ${isAnnouncementEditorExpanded ? 'is-expanded' : ''}`}>
              <div className="aurora-admin-card aurora-admin-editor-card">
                <div className="aurora-admin-editor-head">
                  <div>
                    <strong>公告内容</strong>
                  </div>
                </div>

                <form onSubmit={handleCreateAnnouncement} className="space-y-4">
                  <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-700">公告标题</label>
                    <input
                      type="text"
                      value={announcementTitle}
                      onChange={(e) => setAnnouncementTitle(e.target.value)}
                      placeholder="GankAIGC 平台功能更新说明"
                      className={ADMIN_ACCOUNT_INPUT_CLASS}
                      maxLength={120}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-700">类型</label>
                    <select
                      value={announcementCategory}
                      onChange={(e) => setAnnouncementCategory(e.target.value)}
                      className={ADMIN_ACCOUNT_INPUT_CLASS}
                    >
                      <option value="notice">通知</option>
                      <option value="maintenance">维护</option>
                      <option value="model">模型</option>
                      <option value="guide">说明</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-700">内容</label>
                    <div className="aurora-admin-editor-toolbar">
                      {ANNOUNCEMENT_MARKDOWN_TOOLS.map((tool) => (
                        <button
                          key={tool.id}
                          type="button"
                          onClick={() => applyAnnouncementMarkdownTool(tool)}
                          title={tool.title}
                          aria-label={`插入 Markdown ${tool.title}`}
                        >
                          {tool.label}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={undoAnnouncementContent}
                        disabled={announcementContentHistoryIndex <= 0}
                        title="撤销"
                        aria-label="撤销 Markdown 编辑"
                      >
                        ↶
                      </button>
                      <button
                        type="button"
                        onClick={redoAnnouncementContent}
                        disabled={announcementContentHistoryIndex >= announcementContentHistory.length - 1}
                        title="重做"
                        aria-label="重做 Markdown 编辑"
                      >
                        ↷
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsAnnouncementEditorExpanded((current) => !current)}
                        title={isAnnouncementEditorExpanded ? '退出大编辑区' : '展开编辑区'}
                        aria-label={isAnnouncementEditorExpanded ? '退出 Markdown 大编辑区' : '展开 Markdown 编辑区'}
                      >
                        ⛶
                      </button>
                    </div>
                    <textarea
                      ref={announcementTextareaRef}
                      value={announcementContent}
                      onChange={(e) => updateAnnouncementContent(e.target.value)}
                      placeholder={'## 功能更新\n- 新增会话监控实时分析能力\n- 优化知识库检索相关体验\n\n> 感谢您一直以来的支持与信任！'}
                      className={`aurora-admin-input w-full resize-none rounded-lg border border-gray-300 px-4 py-3 font-mono text-sm outline-none transition focus:border-transparent focus:ring-2 focus:ring-blue-500 ${isAnnouncementEditorExpanded ? 'h-[30rem]' : 'h-44'}`}
                      maxLength={1000}
                    />
                  </div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                    <button type="button" onClick={saveAnnouncementDraft} className="aurora-admin-subtle-button">
                      <Save className="h-4 w-4" />
                      保存草稿
                    </button>
                    <button
                      type="submit"
                      className="aurora-admin-action inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2 font-semibold text-white transition-colors hover:bg-blue-700"
                    >
                      <Send className="h-4 w-4" />
                      发布公告
                    </button>
                  </div>
                </form>
              </div>

              <div className="aurora-admin-card aurora-admin-preview-card">
                <article className="aurora-admin-announcement-preview">
                  <span className={`inline-flex w-max rounded-full border px-2.5 py-1 text-xs font-semibold ${getAnnouncementCategoryClass(announcementCategory)}`}>
                    预览
                  </span>
                  <h3>{announcementTitle || 'GankAIGC 平台功能更新说明'}</h3>
                  <p className="text-xs text-slate-400">发布于 {formatChinaDateTime(new Date().toISOString())}</p>
                  <div className="aurora-admin-preview-body">
                    <MarkdownPreview content={announcementContent} fallback={DEFAULT_ANNOUNCEMENT_MARKDOWN} />
                  </div>
                </article>
              </div>
            </div>

            <div className="aurora-admin-card overflow-hidden">
              <div className="aurora-admin-list-head">
                <div>
                  <h3>公告列表</h3>
                </div>
                <div className="aurora-admin-list-actions">
                  <button
                    type="button"
                    onClick={fetchAnnouncements}
                    disabled={loadingAnnouncements}
                    className="aurora-admin-icon-button"
                    aria-label="刷新公告"
                    title="刷新公告列表"
                  >
                    <RefreshCw className={`h-4 w-4 ${loadingAnnouncements ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>
              <div className="max-h-[37rem] overflow-auto">
                {announcements.length === 0 ? (
                  <div className="px-6 py-12 text-center text-sm text-gray-500">
                    {loadingAnnouncements ? '正在加载公告' : '暂无公告'}
                  </div>
                ) : (
                  <table className="min-w-full divide-y divide-gray-200 aurora-admin-announcement-table">
                    <thead className="aurora-admin-table-head sticky top-0 z-10">
                      <tr>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">公告标题</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">状态</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">类型</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">发布时间</th>
                        <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">创建人</th>
                        <th className="px-5 py-3 text-right text-xs font-semibold text-slate-500">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 bg-white">
                      {announcements.map((announcement) => (
                        <tr key={announcement.id}>
                          <td className="px-5 py-4">
                            <strong className="block text-sm text-slate-900">{announcement.title}</strong>
                            <small className="mt-1 block max-w-xl truncate text-xs text-slate-500">{announcement.content}</small>
                          </td>
                          <td className="px-5 py-4">
                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                              announcement.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'
                            }`}>
                              {announcement.is_active ? '发布中' : '已隐藏'}
                            </span>
                          </td>
                          <td className="px-5 py-4">
                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getAnnouncementCategoryClass(announcement.category)}`}>
                              {getAnnouncementCategoryLabel(announcement.category)}
                            </span>
                          </td>
                          <td className="px-5 py-4 whitespace-nowrap text-sm text-slate-500">{formatChinaDateTime(announcement.created_at)}</td>
                          <td className="px-5 py-4 whitespace-nowrap text-sm text-slate-600">管理员</td>
                          <td className="px-5 py-4">
                            <div className="flex justify-end gap-2">
                              <button onClick={() => handleToggleAnnouncement(announcement)} className="aurora-admin-subtle-button"><Eye className="h-4 w-4" />{announcement.is_active ? '隐藏' : '启用'}</button>
                              <button type="button" onClick={() => editAnnouncementDraft(announcement)} className="aurora-admin-subtle-button"><Edit2 className="h-4 w-4" />编辑</button>
                              <button onClick={() => handleDeleteAnnouncement(announcement)} className="aurora-admin-danger-button"><Trash2 className="h-4 w-4" />删除</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              {announcements.length > 0 && (
                <div className="aurora-admin-list-footer">
                  <span>共 {announcements.length} 条</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Audit Logs Tab */}
        {activeTab === 'audit' && (
          <div className="aurora-admin-section space-y-6">
            <div className="aurora-admin-audit-filters">
              <select value={auditRoleFilter} onChange={(event) => setAuditRoleFilter(event.target.value)} className="aurora-admin-input" aria-label="筛选管理员角色">
                <option value="all">全部角色</option>
                {auditRoleOptions.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
              <select value={auditActionFilter} onChange={(event) => setAuditActionFilter(event.target.value)} className="aurora-admin-input" aria-label="筛选审计动作">
                <option value="all">全部动作</option>
                {auditActionOptions.map((action) => <option key={action} value={action}>{action}</option>)}
              </select>
              <select value={auditResourceFilter} onChange={(event) => setAuditResourceFilter(event.target.value)} className="aurora-admin-input" aria-label="筛选资源类型">
                <option value="all">全部资源</option>
                {auditResourceOptions.map((resource) => <option key={resource} value={resource}>{resource}</option>)}
              </select>
              <select value={auditSeverityFilter} onChange={(event) => setAuditSeverityFilter(event.target.value)} className="aurora-admin-input" aria-label="筛选严重级别">
                <option value="all">全部级别</option>
                <option value="info">info</option>
                <option value="warning">warning</option>
              </select>
              <button type="button" onClick={cycleAuditDateRange} className="aurora-admin-subtle-button aurora-admin-audit-date-range" aria-label="切换审计时间范围">
                {auditDateRange === 'today' ? '今日' : auditDateRange === 'all' ? '全部时间' : '近 7 天'}
                <Calendar className="h-4 w-4" />
              </button>
              <button type="button" onClick={resetAuditFilters} className="aurora-admin-subtle-button">重置</button>
              <button type="button" onClick={fetchAuditLogs} className="aurora-admin-action bg-blue-600">查询</button>
              <button
                type="button"
                onClick={fetchAuditLogs}
                disabled={loadingAuditLogs}
                className="aurora-admin-secondary-action"
                aria-label="刷新操作日志"
              >
                <RefreshCw className={`w-4 h-4 ${loadingAuditLogs ? 'animate-spin' : ''}`} />
                刷新
              </button>
            </div>

            <div className="aurora-admin-audit-layout">
              <aside className="aurora-admin-card aurora-admin-audit-timeline">
                <div className="aurora-admin-list-head compact">
                  <div>
                    <h3>操作时间线</h3>
                    <p>最近关键事件</p>
                  </div>
                  <Calendar className="h-4 w-4 text-slate-400" />
                </div>
                <div className="aurora-admin-timeline-list">
                  {filteredAuditLogs.slice(0, 5).map((log, index) => (
                    <div key={log.id || index} className="aurora-admin-timeline-item">
                      <span className={index === 1 ? 'is-warn' : index === 2 ? 'is-good' : ''} />
                      <strong>{log.action}</strong>
                      <p>{log.target_type || '系统'}{log.target_id ? ` #${log.target_id}` : ''}</p>
                      <small>{formatChinaDateTime(log.created_at)}</small>
                    </div>
                  ))}
                  {filteredAuditLogs.length === 0 && <p className="p-5 text-sm text-slate-500">暂无符合筛选的操作日志</p>}
                </div>
              </aside>

              <div className="aurora-admin-card aurora-admin-audit-list-card overflow-hidden">
                <div className="aurora-admin-list-head">
                  <div>
                    <h3>操作日志列表</h3>
                    <p>最近 50 条管理员关键操作审计记录，当前显示 {filteredAuditLogs.length} 条</p>
                  </div>
                  <button type="button" onClick={downloadAuditLogs} className="aurora-admin-subtle-button"><Download className="h-4 w-4" /> 导出</button>
                </div>
                <div className="aurora-admin-audit-table-scroll max-h-[41rem] overflow-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="sticky top-0 z-10 bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">管理员</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">动作</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">资源</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">结果</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">严重级别</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredAuditLogs.length === 0 ? (
                        <tr>
                          <td colSpan="7" className="px-6 py-10 text-center text-sm text-gray-500">暂无符合筛选的操作日志</td>
                        </tr>
                      ) : filteredAuditLogs.map((log, index) => {
                        const severity = getAuditSeverity(log.action);
                        return (
                          <tr
                            key={log.id}
                            onClick={() => setSelectedAuditLogId(log.id)}
                            className={log === selectedAuditLog ? 'aurora-admin-audit-row-selected bg-blue-50/80 hover:bg-blue-50' : 'hover:bg-gray-50'}
                          >
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {formatChinaDateTime(log.created_at)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                              {log.admin_username}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                                {log.action}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                              {log.target_type || '-'}{log.target_id ? ` #${log.target_id}` : ''}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                              <span className="inline-flex items-center gap-1.5 text-emerald-700">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                成功
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${severity.className}`}>
                                {severity.label}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap font-mono text-sm text-gray-600">
                              {getAuditIp(log, index)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <aside className="aurora-admin-card aurora-admin-audit-detail">
                <div className="flex items-center justify-between">
                  <h3>事件详情</h3>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">info</span>
                    <button type="button" onClick={() => setSelectedAuditLogId(null)} className="aurora-admin-icon-button" aria-label="关闭事件详情">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                {selectedAuditLog ? (
                  <>
                    <div className="aurora-admin-user-info-list mt-4">
                      <div><span>事件 ID</span><strong>{selectedAuditLog.id}</strong></div>
                      <div><span>时间</span><strong>{formatChinaDateTime(selectedAuditLog.created_at)}</strong></div>
                      <div><span>操作人</span><strong>{selectedAuditLog.admin_username}</strong></div>
                      <div><span>IP 地址</span><strong>{getAuditIp(selectedAuditLog)}</strong></div>
                      <div><span>用户代理</span><strong>Mozilla/5.0 AppleWebKit/537.36...</strong></div>
                      <div><span>资源</span><strong>{selectedAuditLog.target_type || '-'}</strong></div>
                      <div><span>资源路径</span><strong>/{selectedAuditLog.target_type || 'system'}/{selectedAuditLog.target_id || selectedAuditLog.action}</strong></div>
                      <div><span>结果</span><strong className="text-emerald-600">● 成功</strong></div>
                    </div>
                    <div className="aurora-admin-audit-code">
                      <button type="button" onClick={() => copyToClipboard(formatAuditDetail(selectedAuditLog.detail))}>复制</button>
                      <pre>{formatAuditDetail(selectedAuditLog.detail)}</pre>
                    </div>
                    <div className="aurora-admin-trace-steps">
                      {['接收请求', '权限校验', selectedAuditLog.action, '操作完成'].map((step, index) => (
                        <div key={step}>
                          <span className={index === 3 ? 'is-done' : ''} />
                          <p>{step}</p>
                          <small>{index === 3 ? '耗时 23ms' : '请求参数校验通过'}</small>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="py-12 text-center text-sm text-slate-500">暂无事件详情</div>
                )}
              </aside>
            </div>
          </div>
        )}

        {activeTab === 'adminProfile' && (
          <div className="aurora-admin-section aurora-admin-profile-page">
            <div className="aurora-admin-profile-page-title">
              <div>
                <h2>个人设置</h2>
                <p>管理后台账户信息和安全设置</p>
              </div>
            </div>

            <div className="aurora-admin-card aurora-admin-profile-hero">
              <div className="aurora-admin-profile-hero-main">
                <div className="aurora-admin-profile-avatar-stack">
                  <div className="aurora-admin-profile-avatar">
                    {adminProfile?.avatar_url && !adminAvatarLoadFailed ? (
                      <img src={adminProfile.avatar_url} alt="" onError={() => setAdminAvatarLoadFailed(true)} />
                    ) : (
                      (adminProfile?.display_name || adminProfile?.username || username || 'A').slice(0, 1).toUpperCase()
                    )}
                  </div>
                </div>
                <div className="aurora-admin-profile-identity">
                  <div className="aurora-admin-profile-name-row">
                    <h1>{adminProfile?.display_name || adminDisplayName || '管理员'}</h1>
                    <span><Shield className="h-4 w-4" />{adminProfile?.role || '管理员'}</span>
                    <span className="is-green"><CheckCircle className="h-4 w-4" />启用</span>
                  </div>
                  <p>{adminProfile?.username || 'admin'}</p>
                </div>
              </div>
              <div className="aurora-admin-profile-meta-grid">
                <div>
                  <span>认证方式</span>
                  <strong>{adminProfile?.auth_method === 'password' ? '密码登录' : adminProfile?.auth_method || '--'}</strong>
                </div>
                <div>
                  <span>令牌有效期</span>
                  <strong>{adminProfile?.token_expire_minutes ? `${adminProfile.token_expire_minutes} 分钟` : '--'}</strong>
                </div>
                <div>
                  <span>资料更新</span>
                  <strong>{adminProfile?.updated_at ? formatChinaDateTime(adminProfile.updated_at) : '未修改'}</strong>
                </div>
              </div>
            </div>

            {loadingAdminProfile && !adminProfile ? (
              <div className="aurora-admin-card aurora-loading-card">
                <Loader2 className="h-5 w-5 animate-spin" />
                正在加载管理员资料
              </div>
            ) : (
              <div className="aurora-admin-profile-stack">
                <section className="aurora-admin-card aurora-admin-profile-panel aurora-admin-profile-info-card">
                  <div className="aurora-admin-profile-card-head">
                    <h3>资料与头像</h3>
                    <p>维护后台显示信息，并保持头像与昵称风格一致。</p>
                  </div>
                  <div className="aurora-admin-profile-editor-grid">
                    <div className="aurora-admin-profile-avatar-panel">
                      <div className="aurora-admin-profile-avatar is-panel">
                        {adminProfile?.avatar_url && !adminAvatarLoadFailed ? (
                          <img src={adminProfile.avatar_url} alt="" onError={() => setAdminAvatarLoadFailed(true)} />
                        ) : (
                          (adminProfile?.display_name || adminProfile?.username || username || 'A').slice(0, 1).toUpperCase()
                        )}
                      </div>
                      <h4>资料头像</h4>
                      <p>上传 PNG、JPG 或 WebP 图片，保存后顶部头像与用户列表会同步显示。</p>
                      <button
                        type="button"
                        className="aurora-admin-avatar-upload"
                        onClick={() => adminAvatarInputRef.current?.click()}
                        disabled={uploadingAdminAvatar}
                      >
                        {uploadingAdminAvatar ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                        上传头像
                      </button>
                      <input
                        ref={adminAvatarInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        className="sr-only"
                        onChange={handleAdminAvatarUpload}
                      />
                    </div>

                    <form onSubmit={handleSaveAdminProfile} className="aurora-admin-profile-edit-panel">
                      <h4>编辑个人资料</h4>
                      <label className="aurora-admin-profile-field">
                        <span>显示昵称</span>
                        <input
                          type="text"
                          value={adminDisplayName}
                          onChange={(event) => setAdminDisplayName(event.target.value)}
                          className="aurora-admin-input"
                          maxLength={32}
                          placeholder="例如：魔尊后台"
                        />
                      </label>
                      <label className="aurora-admin-profile-field">
                        <span>登录用户名</span>
                        <input
                          type="text"
                          value={adminProfile?.username || ''}
                          className="aurora-admin-input"
                          disabled
                          readOnly
                        />
                      </label>
                      <button
                        type="submit"
                        disabled={savingAdminProfile}
                        className="aurora-admin-action aurora-admin-profile-submit aurora-admin-profile-submit-inline"
                      >
                        {savingAdminProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        更新资料
                      </button>
                    </form>
                  </div>
                </section>

                <section className="aurora-admin-card aurora-admin-profile-panel aurora-admin-profile-login-card">
                  <div className="aurora-admin-profile-card-head">
                    <h3>登录方式绑定</h3>
                    <p>查看当前登录方式，并管理后台账号密码。</p>
                  </div>
                  <details className="aurora-admin-profile-password-details">
                    <summary className="aurora-admin-profile-login-row">
                      <div className="aurora-admin-profile-login-icon"><Key className="h-5 w-5" /></div>
                      <div className="aurora-admin-profile-login-copy">
                        <strong>后台密码</strong>
                        <span>{adminProfile?.auth_method === 'password' ? '当前后台账号使用系统密码登录' : adminProfile?.auth_method || '密码登录'}</span>
                      </div>
                      <span className="aurora-admin-profile-bound-badge">已绑定</span>
                      <span className="aurora-admin-profile-password-manage">修改密码</span>
                    </summary>

                    <form onSubmit={handleSaveAdminPassword} className="aurora-admin-profile-password-grid">
                      <label className="aurora-admin-profile-field">
                        <span>当前密码</span>
                        <input
                          type="password"
                          value={adminPasswordForm.current_password}
                          onChange={(event) => handleAdminPasswordInput('current_password', event.target.value)}
                          className="aurora-admin-input"
                          autoComplete="current-password"
                          placeholder="请输入当前管理员密码"
                        />
                      </label>
                      <label className="aurora-admin-profile-field">
                        <span>新密码</span>
                        <input
                          type="password"
                          value={adminPasswordForm.new_password}
                          onChange={(event) => handleAdminPasswordInput('new_password', event.target.value)}
                          className="aurora-admin-input"
                          autoComplete="new-password"
                          placeholder="至少 8 位"
                        />
                      </label>
                      <label className="aurora-admin-profile-field">
                        <span>确认新密码</span>
                        <input
                          type="password"
                          value={adminPasswordForm.confirm_password}
                          onChange={(event) => handleAdminPasswordInput('confirm_password', event.target.value)}
                          className="aurora-admin-input"
                          autoComplete="new-password"
                          placeholder="再次输入新密码"
                        />
                      </label>
                      <button
                        type="submit"
                        disabled={savingAdminPassword}
                        className="aurora-admin-action aurora-admin-profile-submit aurora-admin-profile-submit-inline"
                      >
                        {savingAdminPassword ? <Loader2 className="h-4 w-4 animate-spin" /> : <Key className="h-4 w-4" />}
                        保存密码
                      </button>
                    </form>
                  </details>
                </section>
              </div>
            )}
          </div>
        )}
        
        {/* Config Manager Tab */}
        {activeTab === 'config' && (
          <ConfigManager adminToken={adminToken} />
        )}
          </main>
        </div>
      </div>

      {showUpdateModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/40 px-4 py-6 backdrop-blur-sm">
          <div className="w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50">
                  <DownloadCloud className="h-5 w-5 text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">版本更新</h3>
                  <p className="text-xs text-slate-500">检测版本后，复制命令到 VPS SSH 执行</p>
                </div>
              </div>
              <button
                onClick={() => setShowUpdateModal(false)}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                title="关闭"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-5 px-6 py-6">
              {loadingUpdateStatus && !updateStatus ? (
                <div className="flex items-center justify-center gap-3 py-10 text-slate-500">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  正在检查 GitHub 最新版本
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                      <p className="text-xs font-medium text-slate-500">当前版本</p>
                      <p className="mt-2 text-2xl font-bold text-slate-900">
                        {updateStatus?.current_version || CURRENT_APP_VERSION}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                      <p className="text-xs font-medium text-slate-500">最新版本</p>
                      <div className="mt-2 flex items-center gap-2">
                        <p className="text-2xl font-bold text-slate-900">
                          {updateStatus?.latest_version || '-'}
                        </p>
                        {updateStatus?.release_update_available ? (
                          <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">可更新</span>
                        ) : updateStatus && (
                          <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">最新</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {updateStatus?.release_error && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                      GitHub Release 检查失败：{updateStatus.release_error}
                    </div>
                  )}

                  <div className="rounded-xl border border-slate-100 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">升级方式</p>
                        <p className="mt-1 text-xs text-slate-500">SSH 到 VPS 项目目录执行复制的命令</p>
                      </div>
                      <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                        updateAvailable
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}>
                        {updateStatusLabel}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <button
                      onClick={fetchUpdateStatus}
                      disabled={loadingUpdateStatus}
                      className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                    >
                      <RefreshCw className={`h-4 w-4 ${loadingUpdateStatus ? 'animate-spin' : ''}`} />
                      检查更新
                    </button>
                    <a
                      href={updateStatus?.release_url || 'https://github.com/mumu-0922/GankAIGC/releases'}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      <Github className="h-4 w-4" />
                      查看发布
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <button
                      onClick={() => copyToClipboard(manualUpdateCommand)}
                      className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      <Copy className="h-4 w-4" />
                      复制 SSH 升级命令
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminDashboard;
