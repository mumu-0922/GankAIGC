import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  ArrowLeft, Sparkles, Save, Download, Trash2, Edit3,
  Loader2, CheckCircle, AlertCircle, FileText, List,
  Code, Eye, Settings, Copy
} from 'lucide-react';
import { wordFormatterAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import { formatChinaDateTime } from '../utils/dateTime';

// Preset templates for common document types
const PRESET_TEMPLATES = [
  {
    id: 'undergraduate_thesis',
    name: '本科毕业论文',
    description: '符合大多数高校本科毕业论文格式要求',
    requirements: '本科毕业论文格式：标题三号黑体居中，摘要四号宋体，正文小四号宋体1.5倍行距，一级标题三号黑体，二级标题四号黑体，三级标题小四号黑体，参考文献五号宋体，页边距上下2.54cm左右3.17cm',
  },
  {
    id: 'master_thesis',
    name: '硕士学位论文',
    description: '符合研究生院学位论文格式规范',
    requirements: '硕士学位论文格式：封面标题二号黑体，摘要小四号宋体，正文小四号宋体1.5倍行距，章标题三号黑体居中，节标题四号黑体，段落首行缩进2字符，参考文献五号宋体悬挂缩进，页边距上下2.54cm左右3cm',
  },
  {
    id: 'journal_paper',
    name: '期刊论文',
    description: '通用学术期刊论文格式',
    requirements: '期刊论文格式：标题三号黑体居中，作者信息五号宋体居中，摘要小五号宋体，关键词小五号宋体，正文五号宋体单倍行距，一级标题四号黑体，图表标题小五号宋体居中，参考文献小五号宋体',
  },
];

const SpecGeneratorPage = () => {
  const navigate = useNavigate();

  // State
  const [requirements, setRequirements] = useState('');
  const [specName, setSpecName] = useState('');
  const [specDescription, setSpecDescription] = useState('');
  const [generatedSpec, setGeneratedSpec] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [savedSpecs, setSavedSpecs] = useState([]);
  const [isLoadingSpecs, setIsLoadingSpecs] = useState(false);
  const [viewMode, setViewMode] = useState('structure'); // 'structure', 'table', 'json'
  const [isEditing, setIsEditing] = useState(false);
  const [editedSpecJson, setEditedSpecJson] = useState('');
  const [usage, setUsage] = useState(null);
  const [billingMode, setBillingMode] = useState('platform');

  useEffect(() => {
    loadSavedSpecs();
    loadUsage();
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

  const loadSavedSpecs = async () => {
    try {
      setIsLoadingSpecs(true);
      const response = await wordFormatterAPI.listSavedSpecs();
      setSavedSpecs(response.data.specs || []);
    } catch (error) {
      console.error('Load saved specs failed:', error);
      toast.error('加载已保存规范失败');
    } finally {
      setIsLoadingSpecs(false);
    }
  };

  const handleSelectTemplate = (template) => {
    setRequirements(template.requirements);
    setSpecName(template.name);
    setSpecDescription(template.description);
    toast.success(`已加载模板: ${template.name}`);
  };

  const handleGenerate = async () => {
    if (!requirements.trim()) {
      toast.error('请输入排版要求');
      return;
    }

    if (requirements.length < 20) {
      toast.error('排版要求描述太简短，请提供更详细的要求');
      return;
    }

    if (billingMode === 'platform' && usage && !usage.is_unlimited && (usage.credit_balance || 0) <= 0) {
      toast.error('平台啤酒不足，请先兑换啤酒或切换自带 API 模式');
      return;
    }

    if (billingMode === 'byok' && usage && !usage.has_provider_config) {
      toast.error('请先保存自带 API 配置');
      return;
    }

    try {
      setIsGenerating(true);
      const response = await wordFormatterAPI.generateSpec(requirements, { billingMode });

      if (response.data.success) {
        setGeneratedSpec(response.data.spec_json);
        setEditedSpecJson(response.data.spec_json);
        if (!specName) {
          setSpecName(response.data.spec_name || 'AI_Generated');
        }
        toast.success('规范生成成功');
        loadUsage(); // Refresh usage
      } else {
        toast.error('规范生成失败');
      }
    } catch (error) {
      console.error('Generate spec failed:', error);
      toast.error(error.response?.data?.detail || '生成规范失败，请稍后重试');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!specName.trim()) {
      toast.error('请输入规范名称');
      return;
    }

    const specJson = isEditing ? editedSpecJson : generatedSpec;
    if (!specJson) {
      toast.error('没有可保存的规范');
      return;
    }

    try {
      setIsSaving(true);
      await wordFormatterAPI.saveSpec(specName, specJson, specDescription);
      toast.success('规范保存成功');
      loadSavedSpecs();
    } catch (error) {
      console.error('Save spec failed:', error);
      toast.error(error.response?.data?.detail || '保存规范失败');
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadSpec = async (spec) => {
    setGeneratedSpec(spec.spec_json);
    setEditedSpecJson(spec.spec_json);
    setSpecName(spec.name);
    setSpecDescription(spec.description || '');
    setIsEditing(false);
    toast.success(`已加载规范: ${spec.name}`);
  };

  const handleDeleteSpec = async (specId) => {
    if (!window.confirm('确定要删除这个规范吗？')) {
      return;
    }

    try {
      await wordFormatterAPI.deleteSavedSpec(specId);
      toast.success('规范已删除');
      loadSavedSpecs();
    } catch (error) {
      console.error('Delete spec failed:', error);
      toast.error('删除规范失败');
    }
  };

  const handleExportJson = () => {
    const specJson = isEditing ? editedSpecJson : generatedSpec;
    if (!specJson) {
      toast.error('没有可导出的规范');
      return;
    }

    const blob = new Blob([specJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${specName || 'spec'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('规范已导出');
  };

  const handleCopyJson = () => {
    const specJson = isEditing ? editedSpecJson : generatedSpec;
    if (!specJson) {
      toast.error('没有可复制的规范');
      return;
    }

    navigator.clipboard.writeText(specJson);
    toast.success('已复制到剪贴板');
  };

  const toggleEditMode = () => {
    if (isEditing) {
      // Validate JSON before exiting edit mode
      try {
        JSON.parse(editedSpecJson);
        setGeneratedSpec(editedSpecJson);
        setIsEditing(false);
        toast.success('规范已更新');
      } catch (e) {
        toast.error('JSON 格式无效，请检查');
      }
    } else {
      setIsEditing(true);
    }
  };

  // Render spec in structured view
  const renderStructuredView = () => {
    if (!generatedSpec) return null;

    try {
      const spec = JSON.parse(generatedSpec);
      return (
        <div className="space-y-4">
          {/* Meta info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-2">基本信息</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-gray-500">名称:</span> {spec.meta?.name || '-'}</div>
              <div><span className="text-gray-500">语言:</span> {spec.meta?.lang || '-'}</div>
            </div>
          </div>

          {/* Page layout */}
          {spec.page_layout && (
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">页面布局</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-gray-500">纸张:</span> {spec.page_layout.size || '-'}</div>
                <div><span className="text-gray-500">方向:</span> {spec.page_layout.orientation || '-'}</div>
                <div><span className="text-gray-500">上边距:</span> {spec.page_layout.margin_top_cm || '-'} cm</div>
                <div><span className="text-gray-500">下边距:</span> {spec.page_layout.margin_bottom_cm || '-'} cm</div>
                <div><span className="text-gray-500">左边距:</span> {spec.page_layout.margin_left_cm || '-'} cm</div>
                <div><span className="text-gray-500">右边距:</span> {spec.page_layout.margin_right_cm || '-'} cm</div>
              </div>
            </div>
          )}

          {/* Paragraph styles */}
          {spec.paragraph_styles && (
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">段落样式</h4>
              <div className="space-y-2">
                {Object.entries(spec.paragraph_styles).map(([key, style]) => (
                  <div key={key} className="text-sm border-b border-gray-200 pb-2 last:border-0">
                    <div className="font-medium text-blue-600">{key}</div>
                    <div className="grid grid-cols-3 gap-1 text-gray-600 mt-1">
                      <span>字体: {style.font_name_cn || style.font_name_en || '-'}</span>
                      <span>字号: {style.font_size_pt || '-'}pt</span>
                      <span>对齐: {style.alignment || '-'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    } catch (e) {
      return <div className="text-red-500">JSON 解析失败</div>;
    }
  };

  // Render spec in table view
  const renderTableView = () => {
    if (!generatedSpec) return null;

    try {
      const spec = JSON.parse(generatedSpec);
      const styles = spec.paragraph_styles || {};

      return (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-3 py-2 text-left">样式名称</th>
                <th className="px-3 py-2 text-left">中文字体</th>
                <th className="px-3 py-2 text-left">英文字体</th>
                <th className="px-3 py-2 text-left">字号</th>
                <th className="px-3 py-2 text-left">对齐</th>
                <th className="px-3 py-2 text-left">行距</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {Object.entries(styles).map(([key, style]) => (
                <tr key={key} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium text-blue-600">{key}</td>
                  <td className="px-3 py-2">{style.font_name_cn || '-'}</td>
                  <td className="px-3 py-2">{style.font_name_en || '-'}</td>
                  <td className="px-3 py-2">{style.font_size_pt || '-'}pt</td>
                  <td className="px-3 py-2">{style.alignment || '-'}</td>
                  <td className="px-3 py-2">{style.line_spacing || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    } catch (e) {
      return <div className="text-red-500">JSON 解析失败</div>;
    }
  };

  return (
    <div className="gank-app-page">
      {/* Header */}
      <div className="gank-glass-toolbar sticky top-0 z-40 px-4 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/word-formatter"
              className="p-2 gank-topbar-pill rounded-xl transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <BrandLogo size="sm" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">AI 排版规范生成器</h1>
              <p className="text-sm text-gray-500">根据您的要求生成自定义排版规范</p>
            </div>
          </div>

          {usage && (
            <div className="hidden sm:block gank-topbar-pill rounded-xl px-3 py-1.5 text-sm text-gray-500">
              平台啤酒: {usage.is_unlimited ? '无限啤酒' : `${usage.credit_balance ?? 0} 啤酒`}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-4 sm:py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel - Input */}
          <div className="space-y-4">
            {/* Preset Templates */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <h3 className="font-medium text-gray-900 mb-3">常用模板</h3>
              <div className="grid grid-cols-1 gap-2">
                {PRESET_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleSelectTemplate(template)}
                    className="text-left p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
                  >
                    <div className="font-medium text-gray-900">{template.name}</div>
                    <div className="text-sm text-gray-500">{template.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Requirements Input */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <h3 className="font-medium text-gray-900 mb-3">排版要求描述</h3>
              <textarea
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                placeholder="请详细描述您的排版要求，例如：标题使用什么字体、字号，正文行距多少，页边距设置等..."
                className="w-full h-40 p-3 border border-gray-200 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <div className="flex justify-between items-center mt-3">
                <span className="text-sm text-gray-500">{requirements.length} 字符</span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setRequirements('')}
                    className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    清空
                  </button>
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating || !requirements.trim()}
                    className="px-4 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        生成中...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        生成规范
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Billing Mode */}
            <div className="bg-white rounded-xl shadow-sm p-4">
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
                    平台啤酒
                  </div>
                  <p className="mt-1 text-[12px] text-gray-500">
                    剩余 {usage?.is_unlimited ? '无限啤酒' : `${usage?.credit_balance ?? '-'} 啤酒`}
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
                    {usage?.has_provider_config ? '已保存配置，不消耗啤酒' : '需要先保存 API 配置'}
                  </p>
                </button>
              </div>
            </div>

            {/* Saved Specs List */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <h3 className="font-medium text-gray-900 mb-3">已保存的规范</h3>
              {isLoadingSpecs ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
              ) : savedSpecs.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  暂无保存的规范
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {savedSpecs.map((spec) => (
                    <div
                      key={spec.id}
                      className="flex items-center justify-between p-3 rounded-lg border border-gray-200 hover:bg-gray-50"
                    >
                      <div
                        className="flex-1 cursor-pointer"
                        onClick={() => handleLoadSpec(spec)}
                      >
                        <div className="font-medium text-gray-900">{spec.name}</div>
                        {spec.description && (
                          <div className="text-sm text-gray-500">{spec.description}</div>
                        )}
                        <div className="text-xs text-gray-400 mt-1">
                          更新于 {formatChinaDateTime(spec.updated_at)}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteSpec(spec.id)}
                        className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Preview */}
          <div className="space-y-4">
            {/* Spec Name & Description */}
            {generatedSpec && (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      规范名称
                    </label>
                    <input
                      type="text"
                      value={specName}
                      onChange={(e) => setSpecName(e.target.value)}
                      placeholder="输入规范名称"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      规范描述
                    </label>
                    <input
                      type="text"
                      value={specDescription}
                      onChange={(e) => setSpecDescription(e.target.value)}
                      placeholder="可选描述"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Spec Preview */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900">规范预览</h3>
                {generatedSpec && (
                  <div className="flex items-center gap-2">
                    {/* View Mode Switcher */}
                    <div className="flex bg-gray-100 rounded-lg p-0.5">
                      <button
                        onClick={() => setViewMode('structure')}
                        className={`px-2 py-1 text-sm rounded-md transition-colors ${
                          viewMode === 'structure'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-gray-600'
                        }`}
                      >
                        <List className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setViewMode('table')}
                        className={`px-2 py-1 text-sm rounded-md transition-colors ${
                          viewMode === 'table'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-gray-600'
                        }`}
                      >
                        <FileText className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setViewMode('json')}
                        className={`px-2 py-1 text-sm rounded-md transition-colors ${
                          viewMode === 'json'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-gray-600'
                        }`}
                      >
                        <Code className="w-4 h-4" />
                      </button>
                    </div>

                    {viewMode === 'json' && (
                      <button
                        onClick={toggleEditMode}
                        className={`px-2 py-1 text-sm rounded-lg transition-colors ${
                          isEditing
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {isEditing ? (
                          <CheckCircle className="w-4 h-4" />
                        ) : (
                          <Edit3 className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {!generatedSpec ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <Settings className="w-12 h-12 mb-3" />
                  <p>输入排版要求并点击"生成规范"</p>
                </div>
              ) : (
                <div className="border border-gray-200 rounded-lg p-4 max-h-[400px] overflow-y-auto">
                  {viewMode === 'structure' && renderStructuredView()}
                  {viewMode === 'table' && renderTableView()}
                  {viewMode === 'json' && (
                    isEditing ? (
                      <textarea
                        value={editedSpecJson}
                        onChange={(e) => setEditedSpecJson(e.target.value)}
                        className="w-full h-80 font-mono text-sm p-2 border-0 focus:ring-0 resize-none"
                      />
                    ) : (
                      <pre className="text-sm font-mono whitespace-pre-wrap">
                        {JSON.stringify(JSON.parse(generatedSpec), null, 2)}
                      </pre>
                    )
                  )}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            {generatedSpec && (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center justify-center gap-2 transition-colors"
                  >
                    {isSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    保存规范
                  </button>
                  <button
                    onClick={handleExportJson}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    导出 JSON
                  </button>
                  <button
                    onClick={handleCopyJson}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2 transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                    复制
                  </button>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => navigate('/format-checker', {
                      state: {
                        specJson: isEditing ? editedSpecJson : generatedSpec,
                        specName: specName,
                      }
                    })}
                    className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center justify-center gap-2 transition-colors"
                  >
                    下一步: 格式检测
                    <ArrowLeft className="w-4 h-4 rotate-180" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SpecGeneratorPage;
