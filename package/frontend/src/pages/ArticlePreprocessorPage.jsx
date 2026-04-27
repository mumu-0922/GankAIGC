import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft, ArrowRight, FileText, Upload, Play, Download,
  CheckCircle, AlertCircle, Loader2, Settings, Eye, Edit3,
  Save, Trash2, RefreshCw, FileUp, X, ChevronDown, ChevronUp,
  Hash, Type, List, BookOpen, Quote, Table, Image, Code
} from 'lucide-react';
import { wordFormatterAPI } from '../api';
import BrandLogo from '../components/BrandLogo';

// Paragraph type configuration with icons and colors
const PARAGRAPH_TYPES = {
  title: { label: '标题', icon: Type, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  heading1: { label: '一级标题', icon: Hash, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  heading2: { label: '二级标题', icon: Hash, color: 'bg-cyan-100 text-cyan-700 border-cyan-300' },
  heading3: { label: '三级标题', icon: Hash, color: 'bg-teal-100 text-teal-700 border-teal-300' },
  abstract: { label: '摘要', icon: BookOpen, color: 'bg-amber-100 text-amber-700 border-amber-300' },
  keywords: { label: '关键词', icon: List, color: 'bg-orange-100 text-orange-700 border-orange-300' },
  body: { label: '正文', icon: FileText, color: 'bg-gray-100 text-gray-700 border-gray-300' },
  quote: { label: '引用', icon: Quote, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  list_item: { label: '列表项', icon: List, color: 'bg-green-100 text-green-700 border-green-300' },
  table: { label: '表格', icon: Table, color: 'bg-pink-100 text-pink-700 border-pink-300' },
  figure: { label: '图片', icon: Image, color: 'bg-rose-100 text-rose-700 border-rose-300' },
  code: { label: '代码', icon: Code, color: 'bg-slate-100 text-slate-700 border-slate-300' },
  reference: { label: '参考文献', icon: BookOpen, color: 'bg-teal-100 text-teal-700 border-teal-300' },
};

const ArticlePreprocessorPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Input mode and content
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'text'
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Configuration
  const [showConfig, setShowConfig] = useState(false);
  const [chunkParagraphs, setChunkParagraphs] = useState(40);
  const [chunkChars, setChunkChars] = useState(8000);

  // Job state
  const [currentJobId, setCurrentJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // 'pending', 'running', 'completed', 'failed'
  const [progress, setProgress] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Result state
  const [paragraphs, setParagraphs] = useState([]);
  const [markedText, setMarkedText] = useState('');
  const [integrityStatus, setIntegrityStatus] = useState(null);
  const [editingIndex, setEditingIndex] = useState(null);

  // View mode
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'raw'
  const [usage, setUsage] = useState(null);
  const [billingMode, setBillingMode] = useState('platform');

  // Check if coming from spec generator with a spec
  const selectedSpec = location.state?.specJson || null;
  const specName = location.state?.specName || null;

  useEffect(() => {
    loadUsage();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (
      usage &&
      !usage.is_unlimited &&
      (usage.credit_balance || 0) <= 0 &&
      usage.has_provider_config
    ) {
      setBillingMode('byok');
    }
  }, [usage]);

  const loadUsage = async () => {
    try {
      const response = await wordFormatterAPI.getUsage();
      setUsage(response.data);
    } catch (error) {
      console.error('Load usage failed:', error);
    }
  };

  // File handling
  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    const allowedTypes = [
      'text/plain',
      'text/markdown',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    const allowedExtensions = ['.txt', '.md', '.docx'];
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();

    if (!allowedTypes.includes(selectedFile.type) && !allowedExtensions.includes(ext)) {
      toast.error('仅支持 .txt, .md, .docx 文件');
      return;
    }

    if (selectedFile.size > 10 * 1024 * 1024) {
      toast.error('文件大小不能超过 10MB');
      return;
    }

    setFile(selectedFile);
    toast.success(`已选择文件: ${selectedFile.name}`);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  // Start preprocessing
  const handleStartPreprocess = async () => {
    if (inputMode === 'file' && !file) {
      toast.error('请选择文件');
      return;
    }
    if (inputMode === 'text' && !text.trim()) {
      toast.error('请输入文本内容');
      return;
    }
    if (billingMode === 'platform' && usage && !usage.is_unlimited && (usage.credit_balance || 0) <= 0) {
      toast.error('平台剩余额度不足，请先兑换额度或切换自带 API 模式');
      return;
    }
    if (billingMode === 'byok' && usage && !usage.has_provider_config) {
      toast.error('请先保存自带 API 配置');
      return;
    }

    try {
      setIsSubmitting(true);
      setJobStatus('pending');
      setParagraphs([]);
      setMarkedText('');
      setIntegrityStatus(null);

      let response;
      if (inputMode === 'file') {
        response = await wordFormatterAPI.preprocessFile(file, {
          chunkParagraphs,
          chunkChars,
          billingMode,
        });
      } else {
        response = await wordFormatterAPI.preprocessText(text, {
          chunkParagraphs,
          chunkChars,
          billingMode,
        });
      }

      const jobId = response.data.job_id;
      setCurrentJobId(jobId);
      startSSE(jobId);
      toast.success('预处理任务已开始');
    } catch (error) {
      console.error('Start preprocess failed:', error);
      toast.error(error.response?.data?.detail || '启动预处理失败');
      setJobStatus(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  // SSE connection
  const startSSE = (jobId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = wordFormatterAPI.getPreprocessStreamUrl(jobId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleSSEData(data);
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    es.addEventListener('progress', (event) => {
      try {
        const data = JSON.parse(event.data);
        setJobStatus('running');
        setProgress(data);
      } catch (e) {
        console.error('SSE progress error:', e);
      }
    });

    es.addEventListener('completed', (event) => {
      try {
        const data = JSON.parse(event.data);
        setJobStatus('completed');
        fetchResult(jobId);
        toast.success('文章预处理完成！');
        loadUsage();
      } catch (e) {
        console.error('SSE completed error:', e);
      }
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data);
        setJobStatus('failed');
        toast.error(`预处理失败: ${data.message}`);
      } catch (e) {
        console.error('SSE error event:', e);
      }
      es.close();
    });

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        return;
      }
      console.log('SSE connection error, will retry fetching result...');
      es.close();
      // 延迟后尝试获取结果，如果任务仍在运行会自动忽略
      setTimeout(() => fetchResult(jobId), 2000);
    };
  };

  const handleSSEData = (data) => {
    if (data.status) {
      setJobStatus(data.status);
    }
    if (data.progress) {
      setProgress(data);
    }
  };

  // Fetch preprocessing result
  const fetchResult = async (jobId) => {
    try {
      const response = await wordFormatterAPI.getPreprocessResult(jobId);
      if (response.data.success) {
        // 后端直接返回 response.data，无需 .result
        // 字段映射：后端 text/paragraph_type -> 前端 content/type
        const paragraphsData = (response.data.paragraphs || []).map((p) => ({
          index: p.index,
          content: p.text,
          type: p.paragraph_type || 'body',
        }));
        setParagraphs(paragraphsData);
        setMarkedText(response.data.marked_text || '');
        setIntegrityStatus({
          verified: response.data.integrity_check_passed,
          originalHash: response.data.original_hash,
          processedHash: response.data.processed_hash,
        });
        setJobStatus('completed');
      } else {
        // 任务失败
        setJobStatus('failed');
        toast.error(response.data.error || '预处理失败');
      }
    } catch (error) {
      console.error('Fetch result failed:', error);
      const status = error.response?.status;
      if (status === 404) {
        toast.error('任务不存在或已过期');
        setJobStatus(null);
      } else if (status === 400) {
        // 任务尚未完成，保持当前状态
        console.log('任务尚未完成，稍后重试');
      } else {
        // 其他错误
        console.error('获取结果失败:', error.response?.data?.detail || error.message);
      }
    }
  };

  // Edit paragraph type
  const handleTypeChange = (index, newType) => {
    const updated = [...paragraphs];
    updated[index] = { ...updated[index], type: newType };
    setParagraphs(updated);
    setEditingIndex(null);

    // Regenerate marked text
    regenerateMarkedText(updated);
  };

  const regenerateMarkedText = (updatedParagraphs) => {
    const lines = updatedParagraphs.map((p) => {
      return `<!-- wf:type=${p.type} -->\n${p.content}`;
    });
    setMarkedText(lines.join('\n\n'));
  };

  // Export marked text
  const handleExportMarkdown = () => {
    if (!markedText) {
      toast.error('没有可导出的内容');
      return;
    }

    const blob = new Blob([markedText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file?.name?.replace(/\.[^.]+$/, '_marked.md') || 'article_marked.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('已导出 Markdown 文件');
  };

  // Navigate to format page
  const handleGoToFormat = () => {
    if (!markedText) {
      toast.error('请先完成预处理');
      return;
    }

    navigate('/word-formatter', {
      state: {
        preprocessedText: markedText,
        specJson: selectedSpec,
        specName: specName,
      },
    });
  };

  // Reset form
  const handleReset = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setFile(null);
    setText('');
    setCurrentJobId(null);
    setJobStatus(null);
    setProgress(null);
    setParagraphs([]);
    setMarkedText('');
    setIntegrityStatus(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Delete current job
  const handleDeleteJob = async () => {
    if (!currentJobId) return;

    try {
      await wordFormatterAPI.deletePreprocessJob(currentJobId);
      handleReset();
      toast.success('任务已删除');
    } catch (error) {
      console.error('Delete job failed:', error);
      toast.error('删除任务失败');
    }
  };

  // Render paragraph type badge
  const renderTypeBadge = (type, index) => {
    const config = PARAGRAPH_TYPES[type] || PARAGRAPH_TYPES.body;
    const IconComponent = config.icon;
    const isEditing = editingIndex === index;

    if (isEditing) {
      return (
        <div className="absolute top-0 left-0 z-10 bg-white border rounded-lg shadow-lg p-2 min-w-48">
          <div className="text-xs text-gray-500 mb-1">选择段落类型</div>
          <div className="grid grid-cols-2 gap-1">
            {Object.entries(PARAGRAPH_TYPES).map(([key, cfg]) => {
              const Icon = cfg.icon;
              return (
                <button
                  key={key}
                  onClick={() => handleTypeChange(index, key)}
                  className={`flex items-center gap-1 px-2 py-1 text-xs rounded ${cfg.color} hover:opacity-80 transition-opacity`}
                >
                  <Icon className="w-3 h-3" />
                  {cfg.label}
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setEditingIndex(null)}
            className="mt-2 text-xs text-gray-500 hover:text-gray-700"
          >
            取消
          </button>
        </div>
      );
    }

    return (
      <button
        onClick={() => setEditingIndex(index)}
        className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded border ${config.color} hover:opacity-80 transition-opacity`}
        title="点击修改类型"
      >
        <IconComponent className="w-3 h-3" />
        {config.label}
        <Edit3 className="w-2.5 h-2.5 ml-1 opacity-50" />
      </button>
    );
  };

  // Render progress bar
  const renderProgress = () => {
    // 后端发送: { phase, progress (0-1), message, detail }
    // detail 格式: "分块 x/y" 或 null

    // 没有进度数据时显示加载中状态
    if (!progress) {
      return (
        <div className="bg-white rounded-lg border p-4 mb-4">
          <div className="flex items-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="text-sm font-medium text-gray-700">正在初始化预处理任务...</span>
          </div>
        </div>
      );
    }

    const percentage = Math.round((progress.progress || 0) * 100);

    // 解析 detail 获取分块信息
    let chunkInfo = '';
    if (progress.detail) {
      chunkInfo = progress.detail;
    }

    // 根据后端 phase 值显示消息
    const phaseMessages = {
      splitting: '正在分割文章...',
      marking: `正在识别段落类型${chunkInfo ? ` (${chunkInfo})` : ''}`,
      validating: '正在验证完整性...',
      completed: '处理完成',
      error: '处理出错',
    };

    const displayMessage = progress.message || phaseMessages[progress.phase] || '处理中...';

    return (
      <div className="bg-white rounded-lg border p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            {displayMessage}
          </span>
          <span className="text-sm text-gray-500">{percentage}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="gank-app-page">
      {/* Header */}
      <header className="gank-glass-toolbar sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <BrandLogo size="sm" />
            <Link
              to="/spec-generator"
              className="hidden sm:flex items-center gap-1 text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">返回规范生成</span>
            </Link>
            <div className="hidden sm:block h-6 w-px bg-gray-300" />
            <h1 className="text-lg font-semibold text-gray-900">文章预处理</h1>
          </div>

          <div className="flex items-center gap-4">
            {usage && (
              <div className="hidden md:block gank-topbar-pill rounded-xl px-3 py-1.5 text-sm text-gray-600">
                平台额度: {usage.is_unlimited ? '无限' : `${usage.credit_balance ?? 0} 额度`}
              </div>
            )}
            {selectedSpec && (
              <div className="flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-sm">
                <CheckCircle className="w-4 h-4" />
                已选规范: {specName || '自定义'}
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Workflow indicator */}
        <div className="mb-6 flex items-center justify-center gap-2 text-sm text-gray-500">
          <span className="px-3 py-1 bg-gray-100 rounded-full">1. 生成规范</span>
          <ArrowRight className="w-4 h-4" />
          <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
            2. 文章预处理
          </span>
          <ArrowRight className="w-4 h-4" />
          <span className="px-3 py-1 bg-gray-100 rounded-full">3. 生成 Word</span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel - Input */}
          <div className="space-y-4">
            {/* Input Mode Toggle */}
            <div className="bg-white rounded-lg border p-4">
              <div className="flex items-center gap-4 mb-4">
                <button
                  onClick={() => setInputMode('file')}
                  className={`flex-1 py-2 px-4 rounded-lg border transition-colors ${
                    inputMode === 'file'
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Upload className="w-4 h-4 inline mr-2" />
                  上传文件
                </button>
                <button
                  onClick={() => setInputMode('text')}
                  className={`flex-1 py-2 px-4 rounded-lg border transition-colors ${
                    inputMode === 'text'
                      ? 'bg-blue-50 border-blue-300 text-blue-700'
                      : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <FileText className="w-4 h-4 inline mr-2" />
                  粘贴文本
                </button>
              </div>

              {inputMode === 'file' ? (
                <div
                  onDragEnter={handleDrag}
                  onDragOver={handleDrag}
                  onDragLeave={handleDrag}
                  onDrop={handleDrop}
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.md,.docx"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  {file ? (
                    <div className="flex items-center justify-center gap-3">
                      <FileUp className="w-8 h-8 text-blue-500" />
                      <div className="text-left">
                        <div className="font-medium text-gray-900">{file.name}</div>
                        <div className="text-sm text-gray-500">
                          {(file.size / 1024).toFixed(1)} KB
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setFile(null);
                          if (fileInputRef.current) fileInputRef.current.value = '';
                        }}
                        className="p-1 text-gray-400 hover:text-red-500"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                      <p className="text-gray-600 mb-2">拖拽文件到这里，或点击选择</p>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                      >
                        选择文件
                      </button>
                      <p className="text-sm text-gray-400 mt-2">支持 .txt, .md, .docx (最大 10MB)</p>
                    </>
                  )}
                </div>
              ) : (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="在此粘贴您的文章内容..."
                  className="w-full h-64 p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              )}
            </div>

            {/* Billing Mode */}
            <div className="bg-white rounded-lg border p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setBillingMode('platform')}
                  className={`text-left rounded-xl border px-4 py-3 transition-all ${
                    billingMode === 'platform'
                      ? 'border-blue-300 bg-blue-50 text-blue-700'
                      : 'border-gray-100 bg-gray-50 text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    <CheckCircle className="w-4 h-4" />
                    平台额度
                  </div>
                  <p className="mt-1 text-[12px] text-gray-500">
                    剩余 {usage?.is_unlimited ? '无限' : `${usage?.credit_balance ?? '-'} 额度`}
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setBillingMode('byok')}
                  className={`text-left rounded-xl border px-4 py-3 transition-all ${
                    billingMode === 'byok'
                      ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                      : 'border-gray-100 bg-gray-50 text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    <Settings className="w-4 h-4" />
                    自带 API
                  </div>
                  <p className="mt-1 text-[12px] text-gray-500">
                    {usage?.has_provider_config ? '已保存配置，不消耗平台额度' : '需要先保存 API 配置'}
                  </p>
                </button>
              </div>
            </div>

            {/* Configuration */}
            <div className="bg-white rounded-lg border">
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="w-full px-4 py-3 flex items-center justify-between text-gray-700 hover:bg-gray-50"
              >
                <span className="flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  高级配置
                </span>
                {showConfig ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showConfig && (
                <div className="px-4 pb-4 space-y-3 border-t">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      每块最大段落数
                    </label>
                    <input
                      type="number"
                      value={chunkParagraphs}
                      onChange={(e) => setChunkParagraphs(parseInt(e.target.value) || 40)}
                      min={10}
                      max={100}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">建议 30-50，过大可能导致 AI 识别不准</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      每块最大字符数
                    </label>
                    <input
                      type="number"
                      value={chunkChars}
                      onChange={(e) => setChunkChars(parseInt(e.target.value) || 8000)}
                      min={2000}
                      max={20000}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">建议 6000-10000，防止 AI 上下文溢出</p>
                  </div>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleStartPreprocess}
                disabled={isSubmitting || jobStatus === 'running'}
                className="flex-1 flex items-center justify-center gap-2 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting || jobStatus === 'running' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    处理中...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    开始预处理
                  </>
                )}
              </button>
              <button
                onClick={handleReset}
                disabled={jobStatus === 'running'}
                className="px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Right Panel - Result */}
          <div className="space-y-4">
            {/* Progress */}
            {(jobStatus === 'running' || jobStatus === 'pending') && renderProgress()}

            {/* Result Header */}
            {jobStatus === 'completed' && paragraphs.length > 0 && (
              <div className="bg-white rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium text-gray-900">预处理结果</h3>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-2 rounded ${
                        viewMode === 'list' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
                      }`}
                      title="列表视图"
                    >
                      <List className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setViewMode('raw')}
                      className={`p-2 rounded ${
                        viewMode === 'raw' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
                      }`}
                      title="原始文本"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Integrity Status */}
                {integrityStatus && (
                  <div
                    className={`flex items-center gap-2 p-2 rounded text-sm mb-4 ${
                      integrityStatus.verified
                        ? 'bg-green-50 text-green-700'
                        : 'bg-yellow-50 text-yellow-700'
                    }`}
                  >
                    {integrityStatus.verified ? (
                      <>
                        <CheckCircle className="w-4 h-4" />
                        内容完整性验证通过 - 原文未被修改
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-4 h-4" />
                        警告：内容可能已被修改，请仔细检查
                      </>
                    )}
                  </div>
                )}

                {/* Statistics */}
                <div className="grid grid-cols-3 gap-4 text-center text-sm mb-4">
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-blue-600">{paragraphs.length}</div>
                    <div className="text-gray-500">总段落</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-blue-600">
                      {paragraphs.filter((p) => p.type.startsWith('heading')).length}
                    </div>
                    <div className="text-gray-500">标题</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-green-600">
                      {paragraphs.filter((p) => p.type === 'body').length}
                    </div>
                    <div className="text-gray-500">正文</div>
                  </div>
                </div>

                {/* Content View */}
                <div className="max-h-96 overflow-y-auto border rounded-lg">
                  {viewMode === 'list' ? (
                    <div className="divide-y">
                      {paragraphs.map((para, index) => (
                        <div key={index} className="p-3 hover:bg-gray-50 relative">
                          <div className="flex items-start gap-3">
                            <span className="text-xs text-gray-400 mt-1 w-6">{index + 1}</span>
                            <div className="flex-1">
                              <div className="mb-1">{renderTypeBadge(para.type, index)}</div>
                              <p className="text-sm text-gray-700 line-clamp-2">{para.content}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <pre className="p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono">
                      {markedText}
                    </pre>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={handleExportMarkdown}
                    className="flex-1 flex items-center justify-center gap-2 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                  >
                    <Download className="w-4 h-4" />
                    导出 Markdown
                  </button>
                  <button
                    onClick={handleGoToFormat}
                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    下一步: 生成 Word
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!jobStatus && (
              <div className="bg-white rounded-lg border p-8 text-center">
                <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">等待预处理</h3>
                <p className="text-gray-500 text-sm">
                  上传文件或粘贴文本后，点击"开始预处理"按钮
                  <br />
                  AI 将自动识别并标记段落类型
                </p>
              </div>
            )}

            {/* Failed state */}
            {jobStatus === 'failed' && (
              <div className="bg-white rounded-lg border p-8 text-center">
                <AlertCircle className="w-16 h-16 mx-auto text-red-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">预处理失败</h3>
                <p className="text-gray-500 text-sm mb-4">请检查文件格式或网络连接后重试</p>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  重新开始
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ArticlePreprocessorPage;
