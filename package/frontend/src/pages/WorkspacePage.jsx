import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  FileText, History, Play,
  Users, Clock, AlertCircle, CheckCircle, Trash2, Info, Pencil
} from 'lucide-react';
import { optimizationAPI, projectAPI, userAPI } from '../api';
import UserMenu from '../components/UserMenu';
import BrandLogo from '../components/BrandLogo';
import { formatChinaDate } from '../utils/dateTime';

const CREDIT_UNIT_CHARACTERS = 1000;
const PROCESSING_MODE_STAGE_MULTIPLIERS = {
  paper_polish: 1,
  paper_enhance: 1,
  paper_polish_enhance: 2,
  emotion_polish: 1,
};

const countBillableCharacters = (value) => (value.match(/\S/g) || []).length;

const calculateEstimatedCredits = (value, mode) => {
  const billableCharacters = countBillableCharacters(value);
  const baseCredits = Math.max(1, Math.ceil(billableCharacters / CREDIT_UNIT_CHARACTERS));
  return baseCredits * (PROCESSING_MODE_STAGE_MULTIPLIERS[mode] || 1);
};

// 会话列表项组件 - 使用 memo 避免不必要重渲染
const SessionItem = memo(({ session, activeSession, onView, onDelete, onRetry }) => {
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

  const handleView = useCallback(() => {
    onView(session.session_id);
  }, [session.session_id, onView]);

  return (
    <div
      onClick={handleView}
      className="group p-3 rounded-xl hover:bg-gray-50 transition-all cursor-pointer border border-transparent hover:border-gray-100 relative"
    >
      <div className="flex items-start justify-between mb-1.5 gap-2">
        <div className="flex items-center gap-1.5">
          {session.status === 'completed' && (
            <CheckCircle className="w-4 h-4 text-ios-green" />
          )}
          {session.status === 'processing' && (
            <div className="w-4 h-4 border-2 border-ios-blue border-t-transparent rounded-full animate-spin" />
          )}
          {session.status === 'failed' && (
            <AlertCircle className="w-4 h-4 text-ios-red" />
          )}
          {session.status === 'stopped' && (
            <AlertCircle className="w-4 h-4 text-orange-500" />
          )}
          <span className={`text-[13px] font-medium ${
            session.status === 'completed' ? 'text-black' :
            session.status === 'processing' ? 'text-ios-blue' :
            session.status === 'failed' ? 'text-ios-red' :
            session.status === 'stopped' ? 'text-orange-600' : 'text-ios-gray'
          }`}>
            {session.status === 'completed' && '已完成'}
            {session.status === 'processing' && '处理中'}
            {session.status === 'queued' && '排队中'}
            {session.status === 'failed' && '失败'}
            {session.status === 'stopped' && '已停止'}
          </span>
        </div>

        <span className="text-[11px] text-ios-gray/70 font-medium">
          {formatChinaDate(session.created_at)}
        </span>
      </div>

      {session.task_title && (
        <p className="text-[13px] font-semibold text-black line-clamp-1 mb-1 pr-6">
          {session.task_title}
        </p>
      )}

      <p className="text-[13px] text-ios-gray leading-snug line-clamp-2 mb-2 pr-6">
        {session.preview_text || session.project_title || '暂无预览'}
      </p>

      {session.status === 'processing' && (
        <div className="w-full bg-gray-100 rounded-full h-1 mb-1">
          <div
            className="bg-ios-blue h-1 rounded-full"
            style={{ width: `${session.progress}%` }}
          />
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center justify-between mt-1">
        {session.status === 'failed' && (
          <button
            onClick={handleRetry}
            className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200"
          >
            继续处理
          </button>
        )}
        <button
          onClick={handleDelete}
          className="p-1.5 text-gray-300 hover:text-ios-red hover:bg-red-50 rounded-lg transition-colors ml-auto"
          title="删除会话"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {session.status === 'failed' && session.current_position < session.total_segments && (
        <div className="text-[11px] text-ios-red bg-red-50 px-2 py-1 rounded mt-1">
          {session.error_message ? '发生错误' : '网络超时'}
        </div>
      )}
    </div>
  );
});

SessionItem.displayName = 'SessionItem';

const WorkspacePage = () => {
  const [text, setText] = useState('');
  const [processingMode, setProcessingMode] = useState('paper_polish_enhance');
  const [sessions, setSessions] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [credits, setCredits] = useState(null);
  const [hasProviderConfig, setHasProviderConfig] = useState(false);
  const [billingMode, setBillingMode] = useState('platform');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectTitle, setProjectTitle] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editProjectTitle, setEditProjectTitle] = useState('');
  const [editProjectDescription, setEditProjectDescription] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const navigate = useNavigate();

  const activeProject = projects.find((project) => project.id === activeProjectId);
  const billableCharacterCount = useMemo(() => countBillableCharacters(text), [text]);
  const estimatedCredits = useMemo(
    () => calculateEstimatedCredits(text, processingMode),
    [processingMode, text]
  );

  // 使用显式项目 ID 避免切换项目时读取到旧闭包中的 activeProjectId
  const loadSessions = useCallback(async (projectId = activeProjectId) => {
    if (projectId === null) {
      return;
    }

    try {
      setIsLoadingSessions(true);
      const response = await optimizationAPI.listSessions(projectId);
      setSessions(response.data);

      // 查找正在处理的会话
      const processing = response.data.find(
        s => s.status === 'processing' || s.status === 'queued'
      );
      setActiveSession(processing ? processing.session_id : null);
    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [activeProjectId]);

  // loadQueueStatus 不依赖 activeSession，避免 useEffect 重复触发
  const loadQueueStatus = useCallback(async () => {
    try {
      const response = await optimizationAPI.getQueueStatus();
      setQueueStatus(response.data);
    } catch (error) {
      console.error('加载队列状态失败:', error);
    }
  }, [activeProjectId]);

  const loadProjects = useCallback(async () => {
    try {
      const response = await projectAPI.list();
      setProjects(response.data);
      setActiveProjectId((current) => {
        if (current !== null) {
          return current;
        }
        return response.data.length > 0 ? response.data[0].id : 0;
      });
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

  const updateSessionProgress = useCallback(async (sessionId) => {
    try {
      const response = await optimizationAPI.getSessionProgress(sessionId);
      const progress = response.data;

      // 更新会话列表中的进度 - 只在数据有变化时更新
      setSessions(prev => {
        const target = prev.find(s => s.session_id === sessionId);
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

        if (progress.status === 'completed') {
          toast.success('优化完成!');
        } else {
          toast.error(`优化失败: ${progress.error_message}`);
        }
      }
    } catch (error) {
      console.error('更新进度失败:', error);
    }
  }, [loadSessions]);

  // 初始加载 - 只在组件挂载时执行一次
  useEffect(() => {
    loadProjects();
    loadQueueStatus();
    loadAccountState();
  }, [loadProjects, loadQueueStatus, loadAccountState]);

  useEffect(() => {
    if (activeProjectId !== null) {
      setSessions([]);
      loadSessions(activeProjectId);
    }
  }, [activeProjectId, loadSessions]);

  // 队列状态轮询 - 独立的 useEffect，避免与初始加载混淆
  useEffect(() => {
    const interval = setInterval(loadQueueStatus, 15000);
    return () => clearInterval(interval);
  }, [loadQueueStatus]);

  useEffect(() => {
    // 如果有活跃会话,每4秒更新进度（进一步降低频率）
    if (activeSession) {
      const interval = setInterval(() => {
        updateSessionProgress(activeSession);
      }, 4000);
      return () => clearInterval(interval);
    }
  }, [activeSession, updateSessionProgress]);

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
        const nextProjectId = remaining.length > 0 ? remaining[0].id : 0;
        setActiveProjectId(nextProjectId);
        setSessions([]);
        await loadSessions(nextProjectId);
      }
      toast.success('论文项目已归档');
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

  const handleStartOptimization = useCallback(async () => {
    if (!text.trim()) {
      toast.error('请输入要优化的文本');
      return;
    }

    if (isSubmitting) {
      return;
    }

    if (billingMode === 'platform' && credits && !credits.is_unlimited && credits.credit_balance < estimatedCredits) {
      toast.error(`平台剩余额度不足，本次需要 ${estimatedCredits} 额度，当前剩余 ${credits.credit_balance ?? 0} 额度`);
      return;
    }

    if (billingMode === 'byok' && !hasProviderConfig) {
      toast.error('请先保存自带 API 配置');
      navigate('/api-settings');
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await optimizationAPI.startOptimization({
        original_text: text,
        processing_mode: processingMode,
        billing_mode: billingMode,
        project_id: activeProjectId && activeProjectId !== 0 ? activeProjectId : null,
        task_title: taskTitle.trim() || null,
      });

      setActiveSession(response.data.session_id);
      toast.success('优化任务已启动');
      setText('');
      setTaskTitle('');
      loadAccountState();
      loadSessions(activeProjectId);
    } catch (error) {
      toast.error('启动优化失败: ' + error.response?.data?.detail);
    } finally {
      setIsSubmitting(false);
    }
  }, [activeProjectId, taskTitle, text, processingMode, billingMode, credits, estimatedCredits, hasProviderConfig, isSubmitting, loadSessions, loadAccountState, navigate]);

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

  const handleRetrySegment = useCallback(async (session) => {
    if (session.status !== 'failed') {
      return;
    }

    const confirmRetry = window.confirm('检测到会话执行失败。是否继续处理未完成的段落?');
    if (!confirmRetry) {
      return;
    }

    try {
      const response = await optimizationAPI.retryFailedSegments(session.session_id);
      setActiveSession(session.session_id);
      toast.success(response.data?.message || '已重新继续处理未完成段落');
      await loadSessions();
    } catch (error) {
      console.error('重试失败:', error);
      toast.error(error.response?.data?.detail || '重试失败，请稍后再试');
    }
  }, [loadSessions]);

  // 使用 useMemo 缓存当前活跃会话的数据
  const currentActiveSessionData = useMemo(() => {
    return sessions.find(s => s.session_id === activeSession);
  }, [sessions, activeSession]);


  return (
    <div className="gank-app-page">
      {/* 顶部导航栏 */}
      <nav className="gank-glass-toolbar sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center min-h-[64px] gap-4">
            <BrandLogo size="sm" />
            
            <div className="flex items-center gap-3 overflow-x-auto">
              {/* 队列状态 */}
              {queueStatus && (
                <div className="hidden md:flex items-center gap-2 text-[13px]">
                  <div className="flex items-center gap-1.5 gank-topbar-pill px-2.5 py-1.5 rounded-xl">
                    <Users className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-slate-600 font-medium">
                      {queueStatus.current_users}/{queueStatus.max_users}
                    </span>
                  </div>
                  {queueStatus.queue_length > 0 && (
                    <div className="flex items-center gap-1.5 bg-orange-50 px-2.5 py-1.5 rounded-xl border border-orange-100">
                      <Clock className="w-3.5 h-3.5 text-ios-orange" />
                      <span className="text-ios-orange font-medium">
                        {queueStatus.queue_length} 排队
                      </span>
                    </div>
                  )}
                </div>
              )}
              
              <UserMenu credits={credits} />
            </div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧 - 输入区域 */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* 说明卡片 */}
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden">
              <div className="p-4 flex items-start gap-3 bg-blue-50/50">
                <Info className="w-5 h-5 text-ios-blue flex-shrink-0 mt-0.5" />
                <div className="text-[15px] text-black">
                  <p className="font-semibold mb-1 text-ios-blue">当前模式说明</p>
                  <p className="text-gray-700 leading-relaxed">
                    {processingMode === 'paper_polish' && '仅进行论文润色，提升文本的学术性和表达质量。'}
                    {processingMode === 'paper_enhance' && '直接进行原创性增强，跳过润色阶段，适合已经润色过的文本。'}
                    {processingMode === 'paper_polish_enhance' && '先进行论文润色，然后自动进行原创性增强，两阶段处理。'}
                    {processingMode === 'emotion_polish' && '专为感情文章设计，生成更自然、更具人性化的表达。'}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-ios p-5">
              <div className="h-[40px] flex items-center mb-2">
                <div>
                  <h2 className="text-[20px] font-bold text-black tracking-tight pl-1">
                    新建任务
                  </h2>
                  <p className="text-xs text-ios-gray pl-1">
                    当前论文：{activeProject ? activeProject.title : activeProjectId === 0 ? '未归档历史' : '加载中'}
                  </p>
                </div>
              </div>
              
              {/* 处理模式选择 - iOS Segmented Control Style */}
              <div className="mb-5">
                <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                  选择模式
                </label>
                <div className="space-y-3">
                  {[
                    { id: 'paper_polish', title: '论文润色', desc: '提升学术表达质量' },
                    { id: 'paper_enhance', title: '论文增强', desc: '直接提升原创性' },
                    { id: 'paper_polish_enhance', title: '润色 + 增强', desc: '两阶段完整处理' },
                    { id: 'emotion_polish', title: '感情文章润色', desc: '自然、人性化表达' }
                  ].map((mode) => (
                    <label
                      key={mode.id}
                      className={`flex items-center p-3.5 rounded-xl cursor-pointer transition-all border ${
                        processingMode === mode.id
                          ? 'bg-blue-50 border-ios-blue ring-1 ring-ios-blue/20'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name="processingMode"
                        value={mode.id}
                        checked={processingMode === mode.id}
                        onChange={(e) => setProcessingMode(e.target.value)}
                        className="mr-3 w-5 h-5 text-ios-blue focus:ring-ios-blue border-gray-300"
                      />
                      <div>
                        <div className={`font-semibold text-[15px] ${processingMode === mode.id ? 'text-ios-blue' : 'text-black'}`}>
                          {mode.title}
                        </div>
                        <div className="text-[13px] text-ios-gray mt-0.5">
                          {mode.desc}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="mb-5">
                <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                  计费方式
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label
                    className={`p-3.5 rounded-xl cursor-pointer transition-all border ${
                      billingMode === 'platform'
                        ? 'bg-amber-50 border-amber-500 ring-1 ring-amber-500/20'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="billingMode"
                      value="platform"
                      checked={billingMode === 'platform'}
                      onChange={(event) => setBillingMode(event.target.value)}
                      className="mr-2 text-amber-500"
                    />
                    <span className="font-semibold text-black">平台模式</span>
                    <p className="text-xs text-gray-500 mt-1">
                      剩余 {credits?.is_unlimited ? '无限' : `${credits?.credit_balance ?? '-'} 额度`}
                      {text.trim() && (
                        <span className="block mt-0.5 text-amber-600">
                          预计消耗 {estimatedCredits} 额度
                        </span>
                      )}
                    </p>
                  </label>
                  <label
                    className={`p-3.5 rounded-xl cursor-pointer transition-all border ${
                      billingMode === 'byok'
                        ? 'bg-blue-50 border-ios-blue ring-1 ring-ios-blue/20'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="billingMode"
                      value="byok"
                      checked={billingMode === 'byok'}
                      onChange={(event) => setBillingMode(event.target.value)}
                      className="mr-2 text-ios-blue"
                    />
                    <span className="font-semibold text-black">自带 API 模式</span>
                    <p className="text-xs text-gray-500 mt-1">
                      {hasProviderConfig ? '已保存配置，不消耗平台额度' : '需要先保存 API 配置'}
                    </p>
                  </label>
                </div>
              </div>
              
              <div className="mb-4">
                <label className="block text-[13px] font-medium text-ios-gray mb-2 ml-1 uppercase tracking-wide">
                  本次处理标题
                </label>
                <input
                  type="text"
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  placeholder="例如：摘要降 AI、二稿润色、投稿前终版"
                  className="w-full px-4 py-3 bg-gray-50 rounded-xl focus:bg-white focus:ring-2 focus:ring-ios-blue/20 transition-all text-[15px] text-black placeholder-gray-400 border-none outline-none"
                />
              </div>

              <div className="relative">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="在此粘贴您的内容..."
                  className="w-full h-64 px-4 py-3 bg-gray-50 rounded-xl focus:bg-white focus:ring-2 focus:ring-ios-blue/20 transition-all text-[16px] leading-relaxed text-black placeholder-gray-400 border-none outline-none resize-none"
                />
                <div className="absolute bottom-3 right-3 text-[12px] text-ios-gray bg-white/80 px-2 py-1 rounded-md backdrop-blur-sm">
                  有效 {billableCharacterCount} 字符
                </div>
              </div>
              
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleStartOptimization}
                  disabled={!text.trim() || activeSession || isSubmitting}
                  className="flex items-center gap-2 bg-ios-blue hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 px-8 rounded-xl transition-all active:scale-[0.98] shadow-sm text-[17px]"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      提交中...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      开始优化
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 活跃会话进度 */}
            {activeSession && currentActiveSessionData && (
              <div className="bg-white rounded-2xl shadow-ios p-5 border border-blue-100">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-[17px] font-bold text-black flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-ios-blue animate-pulse" />
                    正在处理
                  </h2>
                  <span className="text-[13px] font-medium px-2 py-1 bg-blue-50 text-ios-blue rounded-md">
                    进行中
                  </span>
                </div>

                {(() => {
                  const session = currentActiveSessionData;
                  const getStageName = (stage) => {
                    if (stage === 'polish') return '论文润色';
                    if (stage === 'emotion_polish') return '感情文章润色';
                    if (stage === 'enhance') return '原创性增强';
                    return stage;
                  };
                  return (
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-[13px] mb-2 font-medium">
                          <span className="text-ios-gray">
                            当前阶段: <span className="text-black">{getStageName(session.current_stage)}</span>
                          </span>
                          <span className="text-ios-blue">
                            {session.progress.toFixed(1)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-ios-blue h-2 rounded-full transition-all duration-500 ease-out shadow-[0_0_10px_rgba(0,122,255,0.3)]"
                            style={{ width: `${session.progress}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[13px]">
                        <span className="text-ios-gray">
                          进度: <span className="font-medium text-black">{session.current_position + 1}</span> / {session.total_segments} 段
                        </span>

                        {session.status === 'queued' && queueStatus?.your_position && (
                          <div className="flex items-center gap-1.5 text-ios-orange">
                            <Clock className="w-3.5 h-3.5" />
                            <span>
                              排队第 {queueStatus.your_position} 位
                              (~{Math.ceil(queueStatus.estimated_wait_time / 60)}分)
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* 右侧 - 历史会话 */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-ios overflow-hidden flex flex-col h-[calc(100vh-140px)] sticky top-24">
              <div className="p-5 border-b border-gray-100 bg-white/50 backdrop-blur-sm z-10">
                <div className="flex items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-ios-blue" />
                    <h2 className="text-[20px] font-bold text-black tracking-tight">
                      论文项目
                    </h2>
                  </div>
                  <button
                    onClick={() => setShowProjectForm((value) => !value)}
                    className="px-3 py-1.5 text-xs font-semibold text-ios-blue bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
                  >
                    {showProjectForm ? '取消' : '新建论文'}
                  </button>
                </div>

                {showProjectForm && (
                  <form onSubmit={handleCreateProject} className="space-y-2 mb-4">
                    <input
                      type="text"
                      value={projectTitle}
                      onChange={(e) => setProjectTitle(e.target.value)}
                      placeholder="论文题目"
                      className="w-full px-3 py-2 bg-gray-50 rounded-lg text-sm border-none outline-none focus:ring-2 focus:ring-ios-blue/20"
                    />
                    <input
                      type="text"
                      value={projectDescription}
                      onChange={(e) => setProjectDescription(e.target.value)}
                      placeholder="备注，可选"
                      className="w-full px-3 py-2 bg-gray-50 rounded-lg text-sm border-none outline-none focus:ring-2 focus:ring-ios-blue/20"
                    />
                    <button
                      type="submit"
                      className="w-full py-2 bg-ios-blue text-white rounded-lg text-sm font-semibold hover:bg-blue-600"
                    >
                      创建项目
                    </button>
                  </form>
                )}

                <div className="space-y-2 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                  <button
                    onClick={() => setActiveProjectId(0)}
                    className={`w-full text-left p-3 rounded-xl transition-all border ${
                      activeProjectId === 0
                        ? 'bg-gray-100 border-gray-300'
                        : 'bg-white border-gray-100 hover:bg-gray-50'
                    }`}
                  >
                    <div className="text-sm font-semibold text-black">未归档历史</div>
                    <div className="text-xs text-ios-gray mt-0.5">旧任务或未选择论文的任务</div>
                  </button>

                  {projects.map((project) => (
                    <div
                      key={project.id}
                      className={`group rounded-xl border transition-all ${
                        activeProjectId === project.id
                          ? 'bg-blue-50 border-ios-blue'
                          : 'bg-white border-gray-100 hover:bg-gray-50'
                      }`}
                    >
                      {editingProjectId === project.id ? (
                        <form onSubmit={handleUpdateProject} className="p-3 space-y-2">
                          <input
                            type="text"
                            value={editProjectTitle}
                            onChange={(e) => setEditProjectTitle(e.target.value)}
                            placeholder="论文题目"
                            className="w-full px-3 py-2 bg-white rounded-lg text-sm border border-blue-100 outline-none focus:ring-2 focus:ring-ios-blue/20"
                            autoFocus
                          />
                          <input
                            type="text"
                            value={editProjectDescription}
                            onChange={(e) => setEditProjectDescription(e.target.value)}
                            placeholder="备注，可选"
                            className="w-full px-3 py-2 bg-white rounded-lg text-sm border border-blue-100 outline-none focus:ring-2 focus:ring-ios-blue/20"
                          />
                          <div className="flex gap-2">
                            <button
                              type="submit"
                              className="flex-1 py-2 bg-ios-blue text-white rounded-lg text-xs font-semibold hover:bg-blue-600"
                            >
                              保存
                            </button>
                            <button
                              type="button"
                              onClick={handleCancelEditProject}
                              className="flex-1 py-2 bg-gray-100 text-ios-gray rounded-lg text-xs font-semibold hover:bg-gray-200"
                            >
                              取消
                            </button>
                          </div>
                        </form>
                      ) : (
                        <>
                          <button
                            onClick={() => setActiveProjectId(project.id)}
                            className="w-full text-left p-3"
                          >
                            <div className="text-sm font-semibold text-black line-clamp-1">{project.title}</div>
                            {project.description && (
                              <div className="text-xs text-ios-gray mt-0.5 line-clamp-1">{project.description}</div>
                            )}
                          </button>
                          <div className="hidden group-hover:flex mx-3 mb-2 gap-3">
                            <button
                              onClick={() => handleStartEditProject(project)}
                              className="inline-flex items-center gap-1 text-xs text-ios-blue hover:underline"
                            >
                              <Pencil className="w-3 h-3" />
                              编辑
                            </button>
                            <button
                              onClick={() => handleArchiveProject(project)}
                              className="text-xs text-ios-red hover:underline"
                            >
                              归档
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              
              <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                <History className="w-4 h-4 text-ios-gray" />
                <h3 className="text-[15px] font-bold text-black">
                  {activeProject ? activeProject.title : '未归档历史'} · 处理记录
                </h3>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar h-full">
                {isLoadingSessions ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-6 h-6 border-2 border-ios-gray/30 border-t-ios-gray rounded-full animate-spin" />
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="text-center py-12 space-y-2">
                    <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mx-auto text-gray-300">
                      <History className="w-6 h-6" />
                    </div>
                    <p className="text-ios-gray text-sm">
                      暂无会话记录
                    </p>
                  </div>
                ) : (
                  sessions.map((session) => (
                    <SessionItem
                      key={session.id}
                      session={session}
                      activeSession={activeSession}
                      onView={handleViewSession}
                      onDelete={handleDeleteSession}
                      onRetry={handleRetrySegment}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkspacePage;
