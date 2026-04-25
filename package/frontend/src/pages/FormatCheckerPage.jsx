import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft, ArrowRight, FileText, Upload, Play, Download,
  CheckCircle, AlertCircle, Loader2, Settings, Eye, Edit3,
  Trash2, RefreshCw, FileUp, X, ChevronDown, ChevronUp,
  Hash, Type, List, BookOpen, Quote, Table, Image, Code,
  AlertTriangle, Info, Search, Filter
} from 'lucide-react';
import { wordFormatterAPI } from '../api';
import BrandLogo from '../components/BrandLogo';

// Paragraph type configuration with icons and colors
const PARAGRAPH_TYPES = {
  title_cn: { label: '中文标题', icon: Type, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  title_en: { label: '英文标题', icon: Type, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  heading_1: { label: '一级标题', icon: Hash, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  heading_2: { label: '二级标题', icon: Hash, color: 'bg-cyan-100 text-cyan-700 border-cyan-300' },
  heading_3: { label: '三级标题', icon: Hash, color: 'bg-teal-100 text-teal-700 border-teal-300' },
  heading_4: { label: '四级标题', icon: Hash, color: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  heading_5: { label: '五级标题', icon: Hash, color: 'bg-lime-100 text-lime-700 border-lime-300' },
  heading_6: { label: '六级标题', icon: Hash, color: 'bg-green-100 text-green-700 border-green-300' },
  abstract_cn: { label: '中文摘要', icon: BookOpen, color: 'bg-amber-100 text-amber-700 border-amber-300' },
  abstract_en: { label: '英文摘要', icon: BookOpen, color: 'bg-amber-100 text-amber-700 border-amber-300' },
  keywords_cn: { label: '中文关键词', icon: List, color: 'bg-orange-100 text-orange-700 border-orange-300' },
  keywords_en: { label: '英文关键词', icon: List, color: 'bg-orange-100 text-orange-700 border-orange-300' },
  body: { label: '正文', icon: FileText, color: 'bg-gray-100 text-gray-700 border-gray-300' },
  reference: { label: '参考文献', icon: BookOpen, color: 'bg-teal-100 text-teal-700 border-teal-300' },
  acknowledgement: { label: '致谢', icon: BookOpen, color: 'bg-pink-100 text-pink-700 border-pink-300' },
  figure_caption: { label: '图题', icon: Image, color: 'bg-rose-100 text-rose-700 border-rose-300' },
  table_caption: { label: '表题', icon: Table, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  list_item: { label: '列表项', icon: List, color: 'bg-green-100 text-green-700 border-green-300' },
  toc: { label: '目录', icon: List, color: 'bg-slate-100 text-slate-700 border-slate-300' },
  code_block: { label: '代码块', icon: Code, color: 'bg-zinc-100 text-zinc-700 border-zinc-300' },
  blockquote: { label: '引用块', icon: Quote, color: 'bg-sky-100 text-sky-700 border-sky-300' },
};

// Issue severity icons and colors
const SEVERITY_CONFIG = {
  error: { icon: AlertCircle, color: 'text-red-500 bg-red-50 border-red-200', label: '错误' },
  warning: { icon: AlertTriangle, color: 'text-yellow-600 bg-yellow-50 border-yellow-200', label: '警告' },
  info: { icon: Info, color: 'text-blue-500 bg-blue-50 border-blue-200', label: '提示' },
};

const FormatCheckerPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const fileInputRef = useRef(null);
  const editingPanelRef = useRef(null);

  // Input mode and content
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'text'
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Configuration
  const [showConfig, setShowConfig] = useState(false);
  const [checkMode, setCheckMode] = useState('loose'); // 'loose' or 'strict'

  // Check state
  const [isChecking, setIsChecking] = useState(false);
  const [checkResult, setCheckResult] = useState(null);

  // Result state
  const [paragraphs, setParagraphs] = useState([]);
  const [issues, setIssues] = useState([]);
  const [markedText, setMarkedText] = useState('');
  const [editingIndex, setEditingIndex] = useState(null);

  // View mode
  const [viewMode, setViewMode] = useState('list'); // 'list', 'issues', 'raw'
  const [issueFilter, setIssueFilter] = useState('all'); // 'all', 'error', 'warning', 'info'
  const [usage, setUsage] = useState(null);

  // Check if coming from spec generator with a spec
  const selectedSpec = location.state?.specJson || null;
  const specName = location.state?.specName || null;

  // Handle click outside to close editing panel
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (editingIndex !== null && editingPanelRef.current && !editingPanelRef.current.contains(event.target)) {
        setEditingIndex(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [editingIndex]);

  useEffect(() => {
    loadUsage();
  }, []);

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

  // Start format check
  const handleStartCheck = async () => {
    if (inputMode === 'file' && !file) {
      toast.error('请选择文件');
      return;
    }
    if (inputMode === 'text' && !text.trim()) {
      toast.error('请输入文本内容');
      return;
    }

    try {
      setIsChecking(true);
      setParagraphs([]);
      setIssues([]);
      setMarkedText('');
      setCheckResult(null);

      let response;
      if (inputMode === 'file') {
        response = await wordFormatterAPI.checkFileFormat(file, checkMode);
      } else {
        response = await wordFormatterAPI.checkTextFormat(text, checkMode);
      }

      const data = response.data;
      setCheckResult(data);

      if (data.success) {
        setParagraphs(data.paragraphs || []);
        setIssues(data.issues || []);
        setMarkedText(data.marked_text || '');

        if (data.is_valid) {
          toast.success('格式检测通过！文章符合规范。');
        } else {
          const errorCount = data.issues.filter(i => i.severity === 'error').length;
          const warningCount = data.issues.filter(i => i.severity === 'warning').length;
          toast.success(
            `格式检测完成：${errorCount} 个错误，${warningCount} 个警告`,
            { duration: 4000 }
          );
        }
      } else {
        toast.error(data.error || '格式检测失败');
      }
    } catch (error) {
      console.error('Format check failed:', error);
      toast.error(error.response?.data?.detail || '格式检测失败');
    } finally {
      setIsChecking(false);
    }
  };

  // Edit paragraph type
  const handleTypeChange = (index, newType) => {
    const updated = [...paragraphs];
    updated[index] = { ...updated[index], paragraph_type: newType, is_auto_detected: false };
    setParagraphs(updated);
    setEditingIndex(null);

    // Regenerate marked text
    regenerateMarkedText(updated);
  };

  const regenerateMarkedText = (updatedParagraphs) => {
    const lines = updatedParagraphs.map((p) => {
      return `<!-- wf:type=${p.paragraph_type} -->\n${p.text}`;
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
      toast.error('请先完成格式检测');
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
    setFile(null);
    setText('');
    setCheckResult(null);
    setParagraphs([]);
    setIssues([]);
    setMarkedText('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Filter issues
  const filteredIssues = issues.filter(issue => {
    if (issueFilter === 'all') return true;
    return issue.severity === issueFilter;
  });

  // Scroll to paragraph
  const scrollToParagraph = (paragraphIndex) => {
    setViewMode('list');
    setTimeout(() => {
      const element = document.getElementById(`paragraph-${paragraphIndex}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.classList.add('ring-2', 'ring-blue-500');
        setTimeout(() => {
          element.classList.remove('ring-2', 'ring-blue-500');
        }, 2000);
      }
    }, 100);
  };

  // Render paragraph type badge
  const renderTypeBadge = (type, index) => {
    const config = PARAGRAPH_TYPES[type] || PARAGRAPH_TYPES.body;
    const IconComponent = config.icon;
    const isEditing = editingIndex === index;

    if (isEditing) {
      return (
        <div ref={editingPanelRef} className="absolute top-0 left-0 z-10 bg-white border rounded-lg shadow-lg p-2 min-w-48 max-h-60 overflow-y-auto">
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

  // Render issue item
  const renderIssue = (issue, idx) => {
    const config = SEVERITY_CONFIG[issue.severity] || SEVERITY_CONFIG.info;
    const Icon = config.icon;

    return (
      <div
        key={idx}
        className={`p-3 rounded-lg border ${config.color} cursor-pointer hover:shadow-md transition-shadow`}
        onClick={() => issue.paragraph_index >= 0 && scrollToParagraph(issue.paragraph_index)}
      >
        <div className="flex items-start gap-2">
          <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-white/50">
                行 {issue.line}
              </span>
              <span className="text-xs text-gray-500">{config.label}</span>
            </div>
            <p className="text-sm font-medium">{issue.message}</p>
            <p className="text-xs mt-1 opacity-75">{issue.suggestion}</p>
            {issue.content_preview && (
              <p className="text-xs mt-1 italic truncate opacity-60">
                "{issue.content_preview}"
              </p>
            )}
          </div>
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
            <h1 className="text-lg font-semibold text-gray-900">文章格式检测</h1>
          </div>

          <div className="flex items-center gap-4">
            {usage && (
              <div className="hidden md:block gank-topbar-pill rounded-xl px-3 py-1.5 text-sm text-gray-600">
                使用量: {usage.usage_count}/{usage.usage_limit > 0 ? usage.usage_limit : '∞'}
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
            2. 格式检测
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

            {/* Configuration */}
            <div className="bg-white rounded-lg border">
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="w-full px-4 py-3 flex items-center justify-between text-gray-700 hover:bg-gray-50"
              >
                <span className="flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  检测配置
                </span>
                {showConfig ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showConfig && (
                <div className="px-4 pb-4 space-y-3 border-t">
                  <div className="pt-3">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      检测模式
                    </label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setCheckMode('loose')}
                        className={`flex-1 py-2 px-3 rounded-lg border text-sm transition-colors ${
                          checkMode === 'loose'
                            ? 'bg-green-50 border-green-300 text-green-700'
                            : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        <CheckCircle className="w-4 h-4 inline mr-1" />
                        宽松模式
                      </button>
                      <button
                        onClick={() => setCheckMode('strict')}
                        className={`flex-1 py-2 px-3 rounded-lg border text-sm transition-colors ${
                          checkMode === 'strict'
                            ? 'bg-orange-50 border-orange-300 text-orange-700'
                            : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        <AlertTriangle className="w-4 h-4 inline mr-1" />
                        严格模式
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      {checkMode === 'loose'
                        ? '宽松模式：只检测关键格式问题（如标题层级跳跃）'
                        : '严格模式：检测所有格式问题，包括警告和提示'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleStartCheck}
                disabled={isChecking}
                className="flex-1 flex items-center justify-center gap-2 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isChecking ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    检测中...
                  </>
                ) : (
                  <>
                    <Search className="w-5 h-5" />
                    开始检测
                  </>
                )}
              </button>
              <button
                onClick={handleReset}
                disabled={isChecking}
                className="px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
            </div>

            {/* Issues Summary */}
            {checkResult && issues.length > 0 && (
              <div className="bg-white rounded-lg border p-4">
                <h3 className="font-medium text-gray-900 mb-3">检测问题</h3>

                {/* Issue filter */}
                <div className="flex gap-2 mb-3">
                  {[
                    { key: 'all', label: '全部', count: issues.length },
                    { key: 'error', label: '错误', count: issues.filter(i => i.severity === 'error').length },
                    { key: 'warning', label: '警告', count: issues.filter(i => i.severity === 'warning').length },
                    { key: 'info', label: '提示', count: issues.filter(i => i.severity === 'info').length },
                  ].map(({ key, label, count }) => (
                    <button
                      key={key}
                      onClick={() => setIssueFilter(key)}
                      className={`px-2 py-1 text-xs rounded-full transition-colors ${
                        issueFilter === key
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {label} ({count})
                    </button>
                  ))}
                </div>

                {/* Issues list */}
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {filteredIssues.map((issue, idx) => renderIssue(issue, idx))}
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Result */}
          <div className="space-y-4">
            {/* Result Header */}
            {checkResult && paragraphs.length > 0 && (
              <div className="bg-white rounded-lg border p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium text-gray-900">检测结果</h3>
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

                {/* Validity Status */}
                <div
                  className={`flex items-center gap-2 p-3 rounded-lg text-sm mb-4 ${
                    checkResult.is_valid
                      ? 'bg-green-50 text-green-700 border border-green-200'
                      : 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                  }`}
                >
                  {checkResult.is_valid ? (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      <span className="font-medium">格式检测通过！</span>
                      <span>文章结构符合规范要求</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="w-5 h-5" />
                      <span className="font-medium">发现 {issues.length} 个问题</span>
                      <span>建议修正后再继续</span>
                    </>
                  )}
                </div>

                {/* Statistics */}
                <div className="grid grid-cols-3 gap-4 text-center text-sm mb-4">
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-blue-600">{paragraphs.length}</div>
                    <div className="text-gray-500">总段落</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-blue-600">
                      {paragraphs.filter((p) => p.paragraph_type.startsWith('heading')).length}
                    </div>
                    <div className="text-gray-500">标题</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-2xl font-semibold text-green-600">
                      {paragraphs.filter((p) => p.paragraph_type === 'body').length}
                    </div>
                    <div className="text-gray-500">正文</div>
                  </div>
                </div>

                {/* Content View */}
                <div className="max-h-96 overflow-y-auto border rounded-lg">
                  {viewMode === 'list' ? (
                    <div className="divide-y">
                      {paragraphs.map((para, index) => (
                        <div
                          key={index}
                          id={`paragraph-${index}`}
                          className="p-3 hover:bg-gray-50 relative transition-all"
                        >
                          <div className="flex items-start gap-3">
                            <span className="text-xs text-gray-400 mt-1 w-6">{index + 1}</span>
                            <div className="flex-1">
                              <div className="mb-1 flex items-center gap-2">
                                {renderTypeBadge(para.paragraph_type, index)}
                                {!para.is_auto_detected && (
                                  <span className="text-xs text-green-600">已手动修改</span>
                                )}
                              </div>
                              <p className="text-sm text-gray-700 line-clamp-2">{para.text}</p>
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
            {!checkResult && (
              <div className="bg-white rounded-lg border p-8 text-center">
                <Search className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">等待格式检测</h3>
                <p className="text-gray-500 text-sm">
                  上传文件或粘贴文本后，点击"开始检测"按钮
                  <br />
                  系统将自动识别段落类型并检测格式问题
                </p>
                <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
                  <Info className="w-4 h-4 inline mr-1" />
                  无需 AI 处理，检测速度更快
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default FormatCheckerPage;
