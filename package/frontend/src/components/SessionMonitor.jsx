import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  Activity,
  RefreshCw,
  History,
  Square,
  Search,
  Calendar,
  MessageSquare,
  Timer,
  Server,
  CheckCircle2,
  AlertCircle,
  User,
  Eye,
} from 'lucide-react';
import { formatChinaDateTime, parseBackendDate } from '../utils/dateTime';

const getSessionUserLabel = (session) => (
  session.user_display_name || session.nickname || session.username || (session.user_id ? `用户 #${session.user_id}` : '未知用户')
);

const sessionModeLabels = {
  paper_polish: '论文润色',
  paper_enhance: '论文增强',
  paper_polish_enhance: '论文润色+增强',
  emotion_polish: '感情文章润色',
  ai_detect_reduce: 'AI检测+降重',
};

const statisticsRangeOptions = [
  { value: 'today', label: '今日' },
  { value: '7d', label: '最近 7 天' },
  { value: '30d', label: '近 30 天' },
];

const getStatisticsRangeLabel = (range) => (
  statisticsRangeOptions.find((option) => option.value === range)?.label || '所选范围'
);

const getProcessingModeLabel = (mode) => sessionModeLabels[mode] || mode || '-';

const getNumericValue = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const formatMetricNumber = (value) => {
  const number = getNumericValue(value);
  return number == null ? '--' : number.toLocaleString('zh-CN');
};

const formatPercentMetric = (value) => {
  const number = getNumericValue(value);
  return number == null ? '--' : `${number.toFixed(2)}%`;
};

const formatDurationMetric = (seconds) => {
  const number = getNumericValue(seconds);
  if (number == null) {
    return '--';
  }
  if (number >= 3600) {
    return `${(number / 3600).toFixed(1)}h`;
  }
  if (number >= 60) {
    return `${(number / 60).toFixed(number >= 600 ? 0 : 1)}m`;
  }
  return `${number.toFixed(number >= 10 ? 1 : 2)}s`;
};

const formatTrendPercent = (value) => {
  const number = getNumericValue(value);
  if (number == null) {
    return '暂无对比数据';
  }
  if (number === 0) {
    return '较上一周期 持平';
  }
  const sign = number > 0 ? '+' : '';
  const arrow = number > 0 ? '↑' : '↓';
  return `较上一周期 ${sign}${number.toFixed(2)}% ${arrow}`;
};

const getTrendClassName = (value, { lowerIsBetter = false } = {}) => {
  const number = getNumericValue(value);
  if (number == null || number === 0) {
    return 'is-neutral';
  }
  if (lowerIsBetter) {
    return number > 0 ? 'is-warning' : 'is-down';
  }
  return number < 0 ? 'is-down' : '';
};

const formatChartTick = (value) => {
  const number = getNumericValue(value) ?? 0;
  if (number >= 10000) {
    return `${(number / 10000).toFixed(1)}W`;
  }
  if (number >= 1000) {
    return `${(number / 1000).toFixed(1)}K`;
  }
  return String(Math.round(number));
};

const buildThroughputChart = (series = []) => {
  const width = 640;
  const height = 220;
  const points = series.map((item, index) => ({
    index,
    label: item.label || '',
    value: getNumericValue(item.value) ?? 0,
  }));
  const maxValue = Math.max(...points.map((point) => point.value), 0);
  const scaleMax = Math.max(Math.ceil(maxValue), 4);
  const renderedPoints = points.map((point) => {
    const x = points.length <= 1 ? width / 2 : (width / (points.length - 1)) * point.index;
    const y = height - (point.value / scaleMax) * height;
    return { ...point, x, y };
  });
  const path = renderedPoints.length > 1
    ? renderedPoints.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ')
    : renderedPoints.length === 1
      ? `M0 ${renderedPoints[0].y.toFixed(2)} L${width} ${renderedPoints[0].y.toFixed(2)}`
      : '';
  const highlightPoint = [...renderedPoints].reverse().find((point) => point.value > 0)
    || renderedPoints[renderedPoints.length - 1]
    || null;
  const ticks = [1, 0.75, 0.5, 0.25, 0].map((ratio) => formatChartTick(scaleMax * ratio));

  return {
    path,
    points: renderedPoints,
    highlightPoint,
    ticks,
    hasData: renderedPoints.length > 0,
    hasNonZeroData: maxValue > 0,
  };
};

const getSessionDurationLabel = (session) => {
  if (session.duration_seconds != null) {
    const seconds = Number(session.duration_seconds) || 0;
    return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }
  const createdAt = parseBackendDate(session.created_at)?.getTime() || Date.now();
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - createdAt) / 1000));
  return `${String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')}:${String(elapsedSeconds % 60).padStart(2, '0')}`;
};

const SessionMonitor = ({ adminToken }) => {
  const [activeSessions, setActiveSessions] = useState([]);
  const [historySessions, setHistorySessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userSessions, setUserSessions] = useState([]);
  const [viewMode, setViewMode] = useState('active');
  const [modeFilter, setModeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sessionSearchTerm, setSessionSearchTerm] = useState('');
  const [queueExpanded, setQueueExpanded] = useState(false);
  const [statistics, setStatistics] = useState(null);
  const [statsRange, setStatsRange] = useState('today');
  const [loadingStats, setLoadingStats] = useState(false);

  useEffect(() => {
    const refreshActiveView = () => {
      fetchActiveSessions();
      fetchSessionStatistics({ silent: true });
    };

    if (viewMode === 'active') {
      refreshActiveView();
      if (autoRefresh) {
        const interval = setInterval(() => {
          if (document.visibilityState !== 'visible') {
            return;
          }
          refreshActiveView();
        }, 5000);
        return () => clearInterval(interval);
      }
    } else if (viewMode === 'history') {
      fetchHistorySessions();
      fetchSessionStatistics({ silent: true });
    }
    return undefined;
  }, [autoRefresh, viewMode, statsRange]);

  const handleStopSession = async (sessionId) => {
    if (!window.confirm('确定要强制停止该会话吗？')) {
      return;
    }

    try {
      await axios.post(`/api/admin/sessions/${sessionId}/stop`, null, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success('会话已停止');
      fetchActiveSessions();
      fetchSessionStatistics({ silent: true });
    } catch (error) {
      toast.error('停止失败: ' + (error.response?.data?.detail || '未知错误'));
    }
  };

  const handleRefreshSessions = () => {
    if (viewMode === 'active') {
      fetchActiveSessions();
    } else {
      fetchHistorySessions();
    }
    fetchSessionStatistics();
  };

  const fetchActiveSessions = async () => {
    try {
      const response = await axios.get('/api/admin/sessions/active', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setActiveSessions(response.data);
    } catch (error) {
      if (error.response?.status !== 401) {
        console.error('获取活跃会话失败:', error);
      }
    }
  };

  const fetchHistorySessions = async () => {
    if (historySessions.length === 0) {
      setLoading(true);
    }
    try {
      const response = await axios.get('/api/admin/sessions', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { limit: 100 }
      });
      setHistorySessions(response.data);
    } catch (error) {
      if (error.response?.status !== 401) {
        toast.error('获取历史会话失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionStatistics = async ({ silent = false } = {}) => {
    if (!silent) {
      setLoadingStats(true);
    }
    try {
      const response = await axios.get('/api/admin/statistics', {
        headers: { Authorization: `Bearer ${adminToken}` },
        params: { range: statsRange },
      });
      setStatistics(response.data);
    } catch (error) {
      if (error.response?.status !== 401) {
        console.error('获取会话统计失败:', error);
        if (!silent) {
          toast.error('获取会话统计失败');
        }
      }
    } finally {
      if (!silent) {
        setLoadingStats(false);
      }
    }
  };

  const fetchUserSessions = async (userId, userLabel) => {
    setLoading(true);
    try {
      const response = await axios.get(`/api/admin/users/${userId}/sessions`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUserSessions(response.data);
      setSelectedUser({ id: userId, label: userLabel || `用户 #${userId}` });
    } catch (error) {
      toast.error('获取用户会话历史失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'processing': return '处理中';
      case 'completed': return '已完成';
      case 'failed': return '失败';
      case 'queued': return '排队中';
      case 'waiting_browser_agent': return '等待本机朱雀插件';
      case 'stopped': return '已停止';
      default: return status;
    }
  };

  const rawSessionsToRender = viewMode === 'active' ? activeSessions : historySessions;
  const normalizedSessionSearch = sessionSearchTerm.trim().toLowerCase();
  const sessionsToRender = rawSessionsToRender.filter((session) => {
    const matchesMode = modeFilter === 'all' || session.processing_mode === modeFilter;
    const matchesStatus = statusFilter === 'all' || session.status === statusFilter;
    const matchesSearch = !normalizedSessionSearch || [
      session.session_id,
      session.id,
      session.username,
      session.nickname,
      session.user_display_name,
      session.user_id,
    ].some((value) => String(value ?? '').toLowerCase().includes(normalizedSessionSearch));
    return matchesMode && matchesStatus && matchesSearch;
  });
  const allQueueSessions = activeSessions.filter((session) => session.status === 'queued');
  const queueSessions = allQueueSessions.slice(0, queueExpanded ? 20 : 6);
  const timelineSessions = sessionsToRender.slice(0, 4);
  const rangeLabel = statistics?.range?.label || getStatisticsRangeLabel(statsRange);
  const rangeRequests = statistics?.requests?.in_range;
  const successRate = statistics?.sessions?.success_rate;
  const averageProcessingTime = statistics?.processing?.avg_processing_time_in_range;
  const processingModeRows = statistics?.processing?.mode_rows || [];
  const activeModelCount = new Set(sessionsToRender.map(s => s.processing_mode).filter(Boolean)).size
    || processingModeRows.filter((mode) => (getNumericValue(mode.count) ?? 0) > 0).length;
  const totalTrackedModelCount = Object.keys(sessionModeLabels).length;
  const throughputSeries = statistics?.processing?.series?.sessions || [];
  const throughputChart = buildThroughputChart(statistics?.processing?.series?.sessions || []);
  const throughputHighlight = throughputChart.highlightPoint;

  return (
    <div className="aurora-admin-section space-y-6 aurora-session-console">
      <div className="aurora-admin-section-head">
        <div>
          <h2>会话监控</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="aurora-admin-card flex rounded-lg p-1 aurora-session-view-toggle">
            <button
              onClick={() => setViewMode('active')}
              className={`aurora-admin-tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors ${viewMode === 'active' ? 'aurora-admin-tab-button-active bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              <Activity className="w-4 h-4 inline mr-1" />
              实时会话
            </button>
            <button
              onClick={() => setViewMode('history')}
              className={`aurora-admin-tab-button px-4 py-2 rounded-md text-sm font-medium transition-colors ${viewMode === 'history' ? 'aurora-admin-tab-button-active bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              <History className="w-4 h-4 inline mr-1" />
              历史会话
            </button>
          </div>
          <button
            onClick={handleRefreshSessions}
            className="aurora-admin-secondary-action"
          >
            <RefreshCw className={`w-4 h-4 ${loadingStats ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      <div className="aurora-session-filter-row">
        <select
          value={modeFilter}
          onChange={(event) => setModeFilter(event.target.value)}
          className="aurora-admin-input aurora-session-filter-select"
          aria-label="筛选模型"
        >
          <option value="all">全部模型</option>
          {Object.entries(sessionModeLabels).map(([mode, label]) => (
            <option key={mode} value={mode}>{label}</option>
          ))}
        </select>
        <label className="aurora-session-range-select">
          <Calendar className="h-4 w-4 text-slate-500" />
          <span className="sr-only">统计范围</span>
          <select
            value={statsRange}
            onChange={(event) => setStatsRange(event.target.value)}
            className="aurora-admin-input aurora-session-filter-select"
            aria-label="统计范围"
          >
            {statisticsRangeOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="aurora-admin-input aurora-session-filter-select"
          aria-label="筛选状态"
        >
          <option value="all">全部状态</option>
          <option value="processing">处理中</option>
          <option value="queued">排队中</option>
          <option value="waiting_browser_agent">等待本机朱雀插件</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="stopped">已停止</option>
        </select>
        <label className="aurora-session-search">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            type="search"
            value={sessionSearchTerm}
            onChange={(event) => setSessionSearchTerm(event.target.value)}
            placeholder="搜索会话ID / 用户名"
            aria-label="搜索会话"
          />
        </label>
        {viewMode === 'active' && (
          <button
            type="button"
            onClick={() => setAutoRefresh((value) => !value)}
            className="aurora-admin-subtle-button aurora-session-interval-button"
            aria-pressed={autoRefresh}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? '5秒自动刷新' : '手动刷新'}
          </button>
        )}
      </div>

      <div className="aurora-session-kpi-grid">
        <div className="aurora-admin-stat-card compact">
          <div className="aurora-admin-metric-icon aurora-admin-metric-icon-blue"><User className="h-6 w-6" /></div>
          <p className="aurora-admin-stat-label">在线会话</p>
          <p className="aurora-admin-stat-value">{viewMode === 'active' ? activeSessions.length : sessionsToRender.length}</p>
          <span className={getTrendClassName(statistics?.sessions?.trend_percent)}>
            {formatTrendPercent(statistics?.sessions?.trend_percent)}
          </span>
        </div>
        <div className="aurora-admin-stat-card compact">
          <div className="aurora-admin-metric-icon aurora-admin-metric-icon-cyan"><Activity className="h-6 w-6" /></div>
          <p className="aurora-admin-stat-label">{rangeLabel}请求</p>
          <p className="aurora-admin-stat-value">{formatMetricNumber(rangeRequests)}</p>
          <span className={getTrendClassName(statistics?.requests?.trend_percent)}>
            {formatTrendPercent(statistics?.requests?.trend_percent)}
          </span>
        </div>
        <div className="aurora-admin-stat-card compact">
          <div className="aurora-admin-metric-icon aurora-admin-metric-icon-violet"><Timer className="h-6 w-6" /></div>
          <p className="aurora-admin-stat-label">平均处理时间</p>
          <p className="aurora-admin-stat-value">{formatDurationMetric(averageProcessingTime)}</p>
          <span className={getTrendClassName(statistics?.processing?.avg_processing_time_trend_percent, { lowerIsBetter: true })}>
            {formatTrendPercent(statistics?.processing?.avg_processing_time_trend_percent)}
          </span>
        </div>
        <div className="aurora-admin-stat-card compact">
          <div className="aurora-admin-metric-icon aurora-admin-metric-icon-amber"><CheckCircle2 className="h-6 w-6" /></div>
          <p className="aurora-admin-stat-label">成功率</p>
          <p className="aurora-admin-stat-value">{formatPercentMetric(successRate)}</p>
          <span className={getTrendClassName(statistics?.sessions?.success_rate_trend_percent)}>
            {formatTrendPercent(statistics?.sessions?.success_rate_trend_percent)}
          </span>
        </div>
        <div className="aurora-admin-stat-card compact">
          <div className="aurora-admin-metric-icon aurora-admin-metric-icon-blue"><Server className="h-6 w-6" /></div>
          <p className="aurora-admin-stat-label">活跃模型</p>
          <p className="aurora-admin-stat-value">{activeModelCount}</p>
          <span className="is-neutral">已配置 {totalTrackedModelCount} 个处理模式</span>
        </div>
      </div>

      <div className="aurora-session-main-grid">
        <div className="aurora-admin-card overflow-hidden">
          <div className="aurora-admin-list-head">
            <div><h3>{viewMode === 'active' ? '实时会话列表' : '历史会话列表'}</h3><p>共 {sessionsToRender.length} 条</p></div>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-12"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
          ) : sessionsToRender.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-4"><Activity className="w-8 h-8 text-gray-300" /></div>
              <p className="text-gray-500 font-medium">{viewMode === 'active' ? '当前没有活跃会话' : '暂无历史会话'}</p>
            </div>
          ) : (
            <div className="overflow-auto max-h-[28rem]">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="aurora-admin-table-head sticky top-0 z-10">
                  <tr>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">会话ID</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">用户名</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">模型</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">状态</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">创建时间</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">持续时长</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">令牌(输入/输出)</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold text-slate-500">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {sessionsToRender.map((session) => (
                    <tr key={session.id || session.session_id}>
                      <td className="px-5 py-3 whitespace-nowrap text-sm font-semibold text-blue-700">
                        <span className={`mr-2 inline-block h-2 w-2 rounded-full ${session.status === 'failed' ? 'bg-red-500' : ['queued', 'waiting_browser_agent'].includes(session.status) ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                        {(session.session_id || session.id || '').toString().slice(0, 12)}
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        <button onClick={() => fetchUserSessions(session.user_id, getSessionUserLabel(session))} className="text-sm font-semibold text-slate-700 hover:text-blue-700">
                          {getSessionUserLabel(session)}
                        </button>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap text-sm text-slate-600">{getProcessingModeLabel(session.processing_mode)}</td>
                      <td className="px-5 py-3 whitespace-nowrap">
                        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${session.status === 'processing' ? 'bg-green-100 text-green-800' : session.status === 'queued' ? 'bg-blue-100 text-blue-800' : session.status === 'waiting_browser_agent' ? 'bg-amber-100 text-amber-800' : session.status === 'completed' ? 'bg-green-100 text-green-800' : session.status === 'failed' ? 'bg-red-100 text-red-800' : session.status === 'stopped' ? 'bg-orange-100 text-orange-800' : 'bg-gray-100 text-gray-800'}`}>
                          {getStatusText(session.status)}
                        </span>
                      </td>
                      <td className="px-5 py-3 whitespace-nowrap text-sm text-slate-500">{formatChinaDateTime(session.created_at)}</td>
                      <td className="px-5 py-3 whitespace-nowrap text-sm text-slate-600">{getSessionDurationLabel(session)}</td>
                      <td className="px-5 py-3 whitespace-nowrap text-sm text-slate-600">
                        {session.original_char_count != null ? session.original_char_count.toLocaleString() : '0'} / {session.polished_char_count != null ? session.polished_char_count.toLocaleString() : '0'}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {(['processing', 'queued', 'waiting_browser_agent'].includes(session.status)) ? (
                          <button onClick={() => handleStopSession(session.session_id || session.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="强制停止"><Square className="w-4 h-4 fill-current" /></button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => fetchUserSessions(session.user_id, getSessionUserLabel(session))}
                            className="rounded-lg p-2 text-blue-600 hover:bg-blue-50"
                            title="查看该用户会话"
                          >
                            <MessageSquare className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="aurora-session-table-footer">
                <span>已加载 {rawSessionsToRender.length} 条</span>
                <span>当前显示 {sessionsToRender.length} 条</span>
                <span>{viewMode === 'history' ? '历史模式加载最近 100 条' : '实时模式显示当前活跃队列'}</span>
              </div>
            </div>
          )}
        </div>

        <aside className="aurora-admin-card aurora-session-queue-card">
          <div className="aurora-admin-list-head compact">
            <div className="aurora-session-queue-title">
              <h3>活动队列</h3>
              <span>排队中 {allQueueSessions.length}</span>
            </div>
          </div>
          {queueSessions.length === 0 ? (
            <div className="aurora-session-empty-state">
              <Activity className="h-5 w-5" />
              <p>当前没有排队中的会话</p>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {queueSessions.map((session, index) => (
                  <div key={session.id || session.session_id || index} className="aurora-session-queue-row">
                    <span>{index + 1}</span>
                    <strong>{(session.session_id || session.id || '').toString().slice(0, 12)}</strong>
                    <small>{getProcessingModeLabel(session.processing_mode)}</small>
                    <small>{getSessionUserLabel(session)}</small>
                    <small>等待中</small>
                    <button
                      type="button"
                      onClick={() => fetchUserSessions(session.user_id, getSessionUserLabel(session))}
                      className="aurora-session-row-icon-button"
                      aria-label="查看队列会话用户历史"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
              {allQueueSessions.length > 6 && (
                <button type="button" onClick={() => setQueueExpanded((value) => !value)} className="aurora-session-card-link" aria-expanded={queueExpanded}>
                  {queueExpanded ? '收起队列' : '查看全部队列'} <span>→</span>
                </button>
              )}
            </>
          )}
        </aside>
      </div>

      <div className="aurora-session-bottom-grid">
        <div className="aurora-admin-card aurora-session-throughput">
          <div className="aurora-admin-list-head compact">
            <div>
              <h3>吞吐量（请求数 / 时段）</h3>
              <p>{rangeLabel} · {throughputSeries.length} 个统计桶</p>
            </div>
          </div>
          <div className="aurora-session-chart-frame">
            {throughputChart.ticks.map((tick, index) => (
              <span key={`${tick}-${index}`}>{tick}</span>
            ))}
            {throughputChart.hasData ? (
              <>
                <svg viewBox="0 0 640 220" preserveAspectRatio="none" aria-label={`${rangeLabel}请求趋势`}>
                  {throughputChart.path && <path d={throughputChart.path} />}
                  {throughputHighlight && (
                    <circle cx={throughputHighlight.x} cy={throughputHighlight.y} r="5" />
                  )}
                </svg>
                {throughputHighlight && (
                  <strong
                    style={{
                      left: `${Math.min(82, Math.max(18, (throughputHighlight.x / 640) * 100))}%`,
                      right: 'auto',
                      top: `${Math.min(210, Math.max(24, throughputHighlight.y + 10))}px`,
                    }}
                  >
                    {throughputHighlight.label || rangeLabel}<br />请求数 {formatMetricNumber(throughputHighlight.value)}
                  </strong>
                )}
                {!throughputChart.hasNonZeroData && (
                  <em className="aurora-session-chart-empty">所选范围暂无请求</em>
                )}
              </>
            ) : (
              <em className="aurora-session-chart-empty">暂无统计序列</em>
            )}
          </div>
        </div>
        <div className="aurora-admin-card aurora-session-timeline-card">
          <div className="aurora-admin-list-head compact"><div><h3>最近任务时间线</h3><p>最新任务动态</p></div></div>
          <div className="aurora-session-timeline">
            {timelineSessions.length === 0 ? (
              <div className="aurora-session-empty-state">
                <MessageSquare className="h-5 w-5" />
                <p>暂无最近任务</p>
              </div>
            ) : (
              timelineSessions.map((session, index) => (
                <div key={session.id || session.session_id || index}>
                  <span className={session.status === 'failed' ? 'is-error' : ['processing', 'queued', 'waiting_browser_agent'].includes(session.status) ? 'is-info' : 'is-ok'}>
                    {session.status === 'failed' ? <AlertCircle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  </span>
                  <p>会话 <strong>{(session.session_id || session.id || '').toString().slice(0, 12)}</strong> {getStatusText(session.status)}</p>
                  <small>模型：{getProcessingModeLabel(session.processing_mode)} · 用户：{getSessionUserLabel(session)}</small>
                  <time>{formatChinaDateTime(session.created_at)}</time>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {selectedUser && (
        <div className="aurora-session-history-drawer fixed inset-0 bg-black bg-opacity-50 z-50 p-4">
          <div className="aurora-admin-card shadow-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <User className="w-6 h-6 text-blue-600" />
                <h3 className="text-xl font-bold text-gray-800">用户会话历史: {selectedUser.label}</h3>
              </div>
              <button onClick={() => setSelectedUser(null)} className="text-gray-400 hover:text-gray-600"><span className="text-2xl">&times;</span></button>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-12"><div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>
            ) : userSessions.length === 0 ? (
              <div className="text-center py-12 text-gray-500">该用户暂无会话记录</div>
            ) : (
              <div className="space-y-4">
                {userSessions.map((session) => (
                  <div key={session.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${session.status === 'completed' ? 'bg-green-100 text-green-800' : session.status === 'processing' ? 'bg-blue-100 text-blue-800' : session.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'}`}>{getStatusText(session.status)}</span>
                        {session.processing_mode && <span className="px-2 py-1 text-xs font-medium rounded bg-blue-100 text-blue-800">{getProcessingModeLabel(session.processing_mode)}</span>}
                        <span className="text-xs text-gray-500">ID: {session.session_id || session.id}</span>
                      </div>
                      <div className="text-xs text-gray-500">{formatChinaDateTime(session.created_at)}</div>
                    </div>
                    {session.total_segments > 0 && (
                      <div>
                        <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                          <span>完成进度</span>
                          <span>{session.completed_segments || 0}/{session.total_segments} 段 ({session.progress || 0}%)</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className={`h-2 rounded-full transition-all ${session.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${session.progress || 0}%` }} />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionMonitor;
