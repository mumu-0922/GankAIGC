import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  LogIn,
  LogOut,
  Users,
  Key,
  CheckCircle,
  XCircle,
  Shield,
  Plus,
  TrendingUp,
  Activity,
  RefreshCw,
  Settings,
  BarChart3,
  Database,
  Clock,
  FileText,
  Loader2
} from 'lucide-react';
import ConfigManager from '../components/ConfigManager';
import SessionMonitor from '../components/SessionMonitor';
import DatabaseManager from '../components/DatabaseManager';
import BrandLogo from '../components/BrandLogo';

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [adminToken, setAdminToken] = useState(localStorage.getItem('adminToken'));
  
  // Tab state
  const [activeTab, setActiveTab] = useState('dashboard');

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
  const [providerConfigs, setProviderConfigs] = useState([]);
  const [loadingAccountData, setLoadingAccountData] = useState(false);
  const [newInviteCode, setNewInviteCode] = useState('');
  const [newCreditCode, setNewCreditCode] = useState('');
  const [newCreditAmount, setNewCreditAmount] = useState(10);
  const [creditTopUps, setCreditTopUps] = useState({});

  useEffect(() => {
    if (adminToken) {
      verifyToken();
    }
  }, [adminToken]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchStatistics();
      // 每30秒自动刷新统计数据
      const interval = setInterval(fetchStatistics, 30000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated && activeTab === 'accounts') {
      fetchAccountData();
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

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setAdminToken(null);
    setIsAuthenticated(false);
    setUsername('');
    setPassword('');
    toast.success('已退出登录');
  };

  const fetchStatistics = async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('/api/admin/statistics', {
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

  const fetchAccountData = async () => {
    setLoadingAccountData(true);
    try {
      const headers = { Authorization: `Bearer ${adminToken}` };
      const [usersResponse, invitesResponse, creditCodesResponse, providerConfigsResponse] = await Promise.all([
        axios.get('/api/admin/users', { headers }),
        axios.get('/api/admin/invites', { headers }),
        axios.get('/api/admin/credit-codes', { headers }),
        axios.get('/api/admin/provider-configs', { headers })
      ]);

      setUsers(usersResponse.data);
      setInvites(invitesResponse.data);
      setCreditCodes(creditCodesResponse.data);
      setProviderConfigs(providerConfigsResponse.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || '获取账号管理数据失败');
      console.error('Error fetching account data:', error);
    } finally {
      setLoadingAccountData(false);
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

  const handleCreateCreditCode = async (e) => {
    e.preventDefault();
    const amount = parseInt(newCreditAmount, 10);
    if (!amount || amount < 1) {
      toast.error('兑换次数必须大于 0');
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

  const handleAddCredits = async (userId) => {
    const amount = parseInt(creditTopUps[userId], 10);
    if (!amount || amount < 1) {
      toast.error('充值次数必须大于 0');
      return;
    }

    try {
      await axios.post(`/api/admin/users/${userId}/credits`,
        { amount, reason: 'admin_recharge' },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setCreditTopUps((current) => ({ ...current, [userId]: '' }));
      toast.success('次数已充值');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '充值失败');
    }
  };

  const handleToggleUnlimited = async (user) => {
    try {
      await axios.patch(`/api/admin/users/${user.id}/unlimited`,
        { is_unlimited: !user.is_unlimited },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(user.is_unlimited ? '已取消无限调用' : '已设为无限调用');
      fetchAccountData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新无限调用状态失败');
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
      icon: BarChart3,
      activeClass: 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/30',
      inactiveClass: 'text-gray-600 hover:text-blue-600 hover:bg-blue-50',
    },
    {
      id: 'sessions',
      label: '会话监控',
      icon: Activity,
      activeClass: 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-lg shadow-blue-500/30',
      inactiveClass: 'text-gray-600 hover:text-blue-600 hover:bg-blue-50',
    },
    {
      id: 'accounts',
      label: '账号次数',
      icon: Users,
      activeClass: 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-500/30',
      inactiveClass: 'text-gray-600 hover:text-indigo-600 hover:bg-indigo-50',
    },
    {
      id: 'database',
      label: '数据库管理',
      icon: Database,
      activeClass: 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white shadow-lg shadow-emerald-500/30',
      inactiveClass: 'text-gray-600 hover:text-emerald-600 hover:bg-emerald-50',
    },
    {
      id: 'config',
      label: '系统配置',
      icon: Settings,
      activeClass: 'bg-gradient-to-r from-amber-600 to-amber-500 text-white shadow-lg shadow-amber-500/30',
      inactiveClass: 'text-gray-600 hover:text-amber-600 hover:bg-amber-50',
    },
  ];

  // Admin Dashboard
  return (
    <div className="gank-app-page">
      {/* Header */}
      <div className="gank-glass-toolbar sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BrandLogo size="sm" />
              <span className="hidden sm:inline text-sm font-semibold text-slate-500">管理后台</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-xl transition-colors font-semibold"
            >
              <LogOut className="w-5 h-5" />
              退出登录
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
        <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)] gap-6 items-start">
          <aside
            data-admin-nav="sidebar"
            className="gank-glass-card rounded-2xl p-3 lg:sticky lg:top-24"
          >
            <nav className="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible">
              {adminNavItems.map(({ id, label, icon: Icon, activeClass, inactiveClass }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`group flex min-w-max lg:min-w-0 items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-all duration-200 ${
                    activeTab === id
                      ? activeClass
                      : `bg-white/70 border border-white/70 shadow-sm ${inactiveClass}`
                  }`}
                >
                  <Icon className={`w-5 h-5 transition-transform duration-200 ${
                    activeTab === id ? 'scale-110' : 'group-hover:scale-110'
                  }`} />
                  <span className="whitespace-nowrap">{label}</span>
                </button>
              ))}
            </nav>
          </aside>

          <main className="min-w-0">
        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <>
            {/* Statistics Cards */}
            {statistics && (
              <>
                {/* 第一行：用户和会话统计 */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
                  {/* Total Users */}
                  <div className="bg-white rounded-2xl shadow-ios p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-500 mb-1">总用户数</p>
                        <p className="text-3xl font-bold text-gray-900 tracking-tight">{statistics.users.total}</p>
                        <div className="flex items-center gap-1 mt-2">
                          <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                            +{statistics.users.today_new} 今日
                          </span>
                        </div>
                      </div>
                      <div className="w-12 h-12 bg-gray-50 rounded-xl flex items-center justify-center">
                        <Users className="w-6 h-6 text-gray-600" />
                      </div>
                    </div>
                  </div>

                  {/* Active Users */}
                  <div className="bg-white rounded-2xl shadow-ios p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-500 mb-1">启用用户</p>
                        <p className="text-3xl font-bold text-gray-900 tracking-tight">{statistics.users.active}</p>
                        <div className="flex items-center gap-1 mt-2">
                          <span className="text-xs font-medium text-gray-500 bg-gray-50 px-2 py-0.5 rounded-full">
                            {statistics.users.inactive} 禁用
                          </span>
                        </div>
                      </div>
                      <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center">
                        <CheckCircle className="w-6 h-6 text-green-600" />
                      </div>
                    </div>
                  </div>

                  {/* Today Active */}
                  <div className="bg-white rounded-2xl shadow-ios p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-500 mb-1">今日活跃</p>
                        <p className="text-3xl font-bold text-gray-900 tracking-tight">{statistics.users.today_active}</p>
                        <div className="flex items-center gap-1 mt-2">
                          <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                            {statistics.users.recent_active_7days} (7日)
                          </span>
                        </div>
                      </div>
                      <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                        <Activity className="w-6 h-6 text-blue-600" />
                      </div>
                    </div>
                  </div>

                  {/* Total Sessions */}
                  <div className="bg-white rounded-2xl shadow-ios p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-500 mb-1">总会话数</p>
                        <p className="text-3xl font-bold text-gray-900 tracking-tight">{statistics.sessions.total}</p>
                        <div className="flex items-center gap-1 mt-2">
                          <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                            {statistics.sessions.today} 今日
                          </span>
                        </div>
                      </div>
                      <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                        <Database className="w-6 h-6 text-blue-600" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* 第二行：处理统计 - 统一使用白色背景，更专业 */}
                {statistics.processing && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    {/* Total Characters Processed */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                          <BarChart3 className="w-5 h-5 text-blue-600" />
                        </div>
                        <span className="text-xs font-medium text-gray-400">累计</span>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">处理字符数</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.processing.total_chars_processed.toLocaleString()}
                      </p>
                    </div>

                    {/* Average Processing Time */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-orange-50 rounded-lg flex items-center justify-center">
                          <Clock className="w-5 h-5 text-orange-600" />
                        </div>
                        <span className="text-xs font-medium text-gray-400">平均</span>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">处理耗时</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {Math.round(statistics.processing.avg_processing_time)}
                        <span className="text-sm font-normal text-gray-500 ml-1">秒</span>
                      </p>
                    </div>

                    {/* Paper Polish Count */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-teal-50 rounded-lg flex items-center justify-center">
                          <FileText className="w-5 h-5 text-teal-600" />
                        </div>
                        <span className="text-xs font-medium text-gray-400">计数</span>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">论文润色</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.processing.paper_polish_count}
                      </p>
                    </div>

                    {/* Paper Polish Enhance Count */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-rose-50 rounded-lg flex items-center justify-center">
                          <TrendingUp className="w-5 h-5 text-rose-600" />
                        </div>
                        <span className="text-xs font-medium text-gray-400">计数</span>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">润色 + 增强</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.processing.paper_polish_enhance_count}
                      </p>
                    </div>
                  </div>
                )}

                {/* 第三行：Word Formatter 统计 */}
                {statistics.word_formatter && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
                    {/* Total Word Formatter Jobs */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                          <FileText className="w-5 h-5 text-blue-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">排版任务</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.word_formatter.total}
                      </p>
                    </div>

                    {/* Completed */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-green-50 rounded-xl flex items-center justify-center">
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">已完成</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.word_formatter.completed}
                      </p>
                    </div>

                    {/* Running */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                          <Loader2 className="w-5 h-5 text-blue-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">运行中</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.word_formatter.running}
                      </p>
                    </div>

                    {/* Pending */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-yellow-50 rounded-xl flex items-center justify-center">
                          <Clock className="w-5 h-5 text-yellow-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">等待中</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.word_formatter.pending}
                      </p>
                    </div>

                    {/* Failed */}
                    <div className="bg-white rounded-2xl shadow-ios p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="w-10 h-10 bg-red-50 rounded-xl flex items-center justify-center">
                          <XCircle className="w-5 h-5 text-red-600" />
                        </div>
                      </div>
                      <p className="text-sm font-medium text-gray-500 mb-1">失败</p>
                      <p className="text-2xl font-bold text-gray-900 tracking-tight">
                        {statistics.word_formatter.failed}
                      </p>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* Account and Credits Tab */}
        {activeTab === 'accounts' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">账号与次数管理</h2>
                <p className="text-sm text-gray-500 mt-1">管理注册邀请码、兑换码、用户次数和自带 API 配置摘要</p>
              </div>
              <button
                onClick={fetchAccountData}
                disabled={loadingAccountData}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white rounded-lg transition-colors"
              >
                <RefreshCw className={`w-4 h-4 ${loadingAccountData ? 'animate-spin' : ''}`} />
                刷新
              </button>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl shadow-ios p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                    <Key className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">注册邀请码</h3>
                    <p className="text-xs text-gray-500">留空会自动生成随机邀请码</p>
                  </div>
                </div>

                <form onSubmit={handleCreateInvite} className="flex flex-col sm:flex-row gap-3 mb-5">
                  <input
                    type="text"
                    value={newInviteCode}
                    onChange={(e) => setNewInviteCode(e.target.value)}
                    placeholder="邀请码，可留空自动生成"
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    创建
                  </button>
                </form>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead>
                      <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <th className="py-3 pr-4">邀请码</th>
                        <th className="py-3 pr-4">状态</th>
                        <th className="py-3 pr-4">使用者</th>
                        <th className="py-3 pr-4">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {invites.length === 0 ? (
                        <tr>
                          <td colSpan="4" className="py-8 text-center text-sm text-gray-500">暂无邀请码</td>
                        </tr>
                      ) : invites.map((invite) => (
                        <tr key={invite.id}>
                          <td className="py-3 pr-4">
                            <button
                              onClick={() => copyToClipboard(invite.code)}
                              className="font-mono text-sm text-blue-700 hover:text-blue-900"
                              title="点击复制"
                            >
                              {invite.code}
                            </button>
                          </td>
                          <td className="py-3 pr-4">
                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                              invite.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'
                            }`}>
                              {invite.is_active ? '启用' : '停用'}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-sm text-gray-600">{invite.used_by_user_id || '-'}</td>
                          <td className="py-3 pr-4">
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

              <div className="bg-white rounded-2xl shadow-ios p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-emerald-50 rounded-xl flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">次数兑换码</h3>
                    <p className="text-xs text-gray-500">用户兑换后增加平台调用次数</p>
                  </div>
                </div>

                <form onSubmit={handleCreateCreditCode} className="grid grid-cols-1 sm:grid-cols-[1fr_120px_auto] gap-3 mb-5">
                  <input
                    type="text"
                    value={newCreditCode}
                    onChange={(e) => setNewCreditCode(e.target.value)}
                    placeholder="兑换码，可留空自动生成"
                    className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  />
                  <input
                    type="number"
                    min="1"
                    value={newCreditAmount}
                    onChange={(e) => setNewCreditAmount(e.target.value)}
                    className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    创建
                  </button>
                </form>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead>
                      <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        <th className="py-3 pr-4">兑换码</th>
                        <th className="py-3 pr-4">次数</th>
                        <th className="py-3 pr-4">状态</th>
                        <th className="py-3 pr-4">兑换者</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {creditCodes.length === 0 ? (
                        <tr>
                          <td colSpan="4" className="py-8 text-center text-sm text-gray-500">暂无兑换码</td>
                        </tr>
                      ) : creditCodes.map((code) => (
                        <tr key={code.id}>
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
            </div>

            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-6 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">用户次数余额</h3>
                  <p className="text-xs text-gray-500 mt-1">管理员可给平台模式充值次数，或给账号开启无限调用</p>
                </div>
                {loadingAccountData && <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />}
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">次数余额</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">权限</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">登录/使用</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">充值</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">{user.username || '未绑定账号'}</div>
                          <div className="text-xs text-gray-500">ID #{user.id}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-lg font-bold text-gray-900">{user.credit_balance ?? 0}</span>
                          <span className="ml-1 text-xs text-gray-500">次</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <button
                            onClick={() => handleToggleUnlimited(user)}
                            className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                              user.is_unlimited
                                ? 'bg-purple-100 hover:bg-purple-200 text-purple-800'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                            }`}
                          >
                            {user.is_unlimited ? '无限调用' : '按次数'}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <div>登录：{user.last_login_at ? new Date(user.last_login_at).toLocaleString('zh-CN') : '从未登录'}</div>
                          <div>使用：{user.last_used ? new Date(user.last_used).toLocaleString('zh-CN') : '从未使用'}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <input
                              type="number"
                              min="1"
                              value={creditTopUps[user.id] || ''}
                              onChange={(e) => setCreditTopUps((current) => ({ ...current, [user.id]: e.target.value }))}
                              placeholder="次数"
                              className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                            />
                            <button
                              onClick={() => handleAddCredits(user.id)}
                              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm transition-colors"
                            >
                              充值
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900">用户自带 API 配置摘要</h3>
                <p className="text-xs text-gray-500 mt-1">仅显示 base_url、模型名和 API Key 后四位，不展示完整密钥</p>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
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
                          {config.updated_at ? new Date(config.updated_at).toLocaleString('zh-CN') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
        
        {/* Session Monitor Tab */}
        {activeTab === 'sessions' && (
          <SessionMonitor adminToken={adminToken} />
        )}
        
        {/* Database Manager Tab */}
        {activeTab === 'database' && (
          <DatabaseManager adminToken={adminToken} />
        )}
        
        {/* Config Manager Tab */}
        {activeTab === 'config' && (
          <ConfigManager adminToken={adminToken} />
        )}
          </main>
        </div>
      </div>

    </div>
  );
};

export default AdminDashboard;
