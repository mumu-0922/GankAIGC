import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  Settings,
  Save,
  RefreshCw,
  Cpu,
  Brain,
  PlugZap,
  Route,
  Fingerprint,
  Gauge,
  SlidersHorizontal,
  FileText,
} from 'lucide-react';
import ApiConfigGuide from './ApiConfigGuide';
import EditableModelCombobox from './EditableModelCombobox';

const API_FORMAT_OPTIONS = [
  { value: 'openai_chat', label: 'OpenAI Compatible' },
  { value: 'anthropic', label: 'Anthropic Messages（原生）' },
];

const ConfigManager = ({ adminToken }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testingStage, setTestingStage] = useState('');
  const [fetchingModels, setFetchingModels] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);
  const [keyStatus, setKeyStatus] = useState({
    polish: { set: false, last4: '' },
    enhance: { set: false, last4: '' },
    emotion: { set: false, last4: '' },
    compression: { set: false, last4: '' },
    mineru: { set: false, last4: '' }
  });

  const [formData, setFormData] = useState({
    MODEL_PROVIDER_NAME: '',
    MODEL_API_FORMAT: 'openai_chat',
    POLISH_MODEL: '',
    POLISH_API_KEY: '',
    POLISH_BASE_URL: '',
    ENHANCE_MODEL: '',
    ENHANCE_API_KEY: '',
    ENHANCE_BASE_URL: '',
    EMOTION_MODEL: '',
    EMOTION_API_KEY: '',
    EMOTION_BASE_URL: '',
    MAX_CONCURRENT_USERS: '',
    API_KEY_CONCURRENCY: '',
    HISTORY_COMPRESSION_THRESHOLD: '',
    COMPRESSION_MODEL: '',
    COMPRESSION_API_KEY: '',
    COMPRESSION_BASE_URL: '',
    SEGMENT_SKIP_THRESHOLD: '',
    API_REQUEST_INTERVAL: '',
    REGISTRATION_ENABLED: true,
    SERVER_HOST: '',
    ALLOW_LOCAL_MODEL_PROXY: false,
    ACCESS_TOKEN_EXPIRE_MINUTES: '',
    USER_ACCESS_TOKEN_EXPIRE_MINUTES: '',
    AUTH_RATE_LIMIT_PER_MINUTE: '',
    REDEEM_RATE_LIMIT_PER_MINUTE: '',
    THINKING_MODE_ENABLED: true,
    THINKING_MODE_EFFORT: 'high',
    PDF_STRUCTURE_ENGINE: 'mineru',
    MINERU_BASE_URL: 'https://mineru.net',
    MINERU_API_TOKEN: '',
    MINERU_MODEL_VERSION: 'vlm',
    MINERU_ENABLE_FORMULA: true,
    MINERU_ENABLE_TABLE: true,
    MINERU_IS_OCR: false,
    MINERU_LANGUAGE: 'ch',
    MINERU_TIMEOUT_SECONDS: '300',
    MINERU_POLL_INTERVAL_SECONDS: '2.0'
  });

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/admin/config', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });

      setKeyStatus({
        polish: {
          set: Boolean(response.data.polish.api_key_set),
          last4: response.data.polish.api_key_last4 || ''
        },
        enhance: {
          set: Boolean(response.data.enhance.api_key_set),
          last4: response.data.enhance.api_key_last4 || ''
        },
        emotion: {
          set: Boolean(response.data.emotion?.api_key_set),
          last4: response.data.emotion?.api_key_last4 || ''
        },
        compression: {
          set: Boolean(response.data.compression?.api_key_set),
          last4: response.data.compression?.api_key_last4 || ''
        },
        mineru: {
          set: Boolean(response.data.document_parse?.mineru_api_token_set),
          last4: response.data.document_parse?.mineru_api_token_last4 || ''
        }
      });

      setFormData({
        MODEL_PROVIDER_NAME: response.data.system.model_provider_name ?? '',
        MODEL_API_FORMAT: response.data.system.model_api_format || 'openai_chat',
        POLISH_MODEL: response.data.polish.model || '',
        POLISH_API_KEY: '',
        POLISH_BASE_URL: response.data.polish.base_url || '',
        ENHANCE_MODEL: response.data.enhance.model || '',
        ENHANCE_API_KEY: '',
        ENHANCE_BASE_URL: response.data.enhance.base_url || '',
        EMOTION_MODEL: response.data.emotion?.model || '',
        EMOTION_API_KEY: '',
        EMOTION_BASE_URL: response.data.emotion?.base_url || '',
        MAX_CONCURRENT_USERS: [5, 8, 10].includes(Number(response.data.system.max_concurrent_users))
          ? response.data.system.max_concurrent_users.toString()
          : '5',
        API_KEY_CONCURRENCY: response.data.system.api_key_concurrency?.toString() || '2',
        HISTORY_COMPRESSION_THRESHOLD: response.data.system.history_compression_threshold?.toString() || '',
        COMPRESSION_MODEL: response.data.compression?.model || '',
        COMPRESSION_API_KEY: '',
        COMPRESSION_BASE_URL: response.data.compression?.base_url || '',
        SEGMENT_SKIP_THRESHOLD: response.data.system.segment_skip_threshold?.toString() || '',
        API_REQUEST_INTERVAL: response.data.system.api_request_interval?.toString() || '6',
        REGISTRATION_ENABLED: response.data.system.registration_enabled ?? true,
        SERVER_HOST: response.data.system.server_host || '0.0.0.0',
        ALLOW_LOCAL_MODEL_PROXY: response.data.system.allow_local_model_proxy ?? false,
        ACCESS_TOKEN_EXPIRE_MINUTES: response.data.security?.admin_token_expire_minutes?.toString() || '',
        USER_ACCESS_TOKEN_EXPIRE_MINUTES: response.data.security?.user_token_expire_minutes?.toString() || '',
        AUTH_RATE_LIMIT_PER_MINUTE: response.data.security?.auth_rate_limit_per_minute?.toString() || '',
        REDEEM_RATE_LIMIT_PER_MINUTE: response.data.security?.redeem_rate_limit_per_minute?.toString() || '',
        THINKING_MODE_ENABLED: response.data.thinking?.enabled ?? true,
        THINKING_MODE_EFFORT: response.data.thinking?.effort || 'high',
        PDF_STRUCTURE_ENGINE: response.data.document_parse?.pdf_structure_engine || 'mineru',
        MINERU_BASE_URL: response.data.document_parse?.mineru_base_url || 'https://mineru.net',
        MINERU_API_TOKEN: '',
        MINERU_MODEL_VERSION: response.data.document_parse?.mineru_model_version || 'vlm',
        MINERU_ENABLE_FORMULA: response.data.document_parse?.mineru_enable_formula ?? true,
        MINERU_ENABLE_TABLE: response.data.document_parse?.mineru_enable_table ?? true,
        MINERU_IS_OCR: response.data.document_parse?.mineru_is_ocr ?? false,
        MINERU_LANGUAGE: response.data.document_parse?.mineru_language || 'ch',
        MINERU_TIMEOUT_SECONDS: response.data.document_parse?.mineru_timeout_seconds?.toString() || '300',
        MINERU_POLL_INTERVAL_SECONDS: response.data.document_parse?.mineru_poll_interval_seconds?.toString() || '2.0'
      });
    } catch (error) {
      toast.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // 只发送已修改的非空值
      const updates = {};
      Object.keys(formData).forEach(key => {
        const value = formData[key];
        // 布尔值需要转换为字符串；供应商名称允许保存为空，避免前端自动兜底。
        if (typeof value === 'boolean') {
          updates[key] = value.toString();
        } else if (key === 'MODEL_PROVIDER_NAME') {
          updates[key] = String(value || '').trim();
        } else if (typeof value === 'string' && value.trim()) {
          updates[key] = value.trim();
        }
      });

      const response = await axios.post('/api/admin/config', updates, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });

      toast.success(response.data.message);
      fetchConfig();
    } catch (error) {
      toast.error(error.response?.data?.detail || '配置保存失败');
    } finally {
      setSaving(false);
    }
  };

  const getStageFormConfig = (stage) => {
    const stageKeyMap = {
      polish: ['POLISH_MODEL', 'POLISH_BASE_URL', 'POLISH_API_KEY'],
      enhance: ['ENHANCE_MODEL', 'ENHANCE_BASE_URL', 'ENHANCE_API_KEY'],
      emotion: ['EMOTION_MODEL', 'EMOTION_BASE_URL', 'EMOTION_API_KEY'],
      compression: ['COMPRESSION_MODEL', 'COMPRESSION_BASE_URL', 'COMPRESSION_API_KEY'],
    };
    const [modelKey, baseUrlKey, apiKeyKey] = stageKeyMap[stage] || stageKeyMap.polish;
    return {
      model: formData[modelKey],
      base_url: formData[baseUrlKey],
      api_key: formData[apiKeyKey],
      api_format: formData.MODEL_API_FORMAT,
    };
  };

  const handleTestModel = async (stage) => {
    const stageConfig = getStageFormConfig(stage);
    setTestingStage(stage);
    try {
      const response = await axios.post('/api/admin/operations/model-test', {
        stage,
        ...stageConfig,
      }, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success(response.data?.message || 'API 连接测试通过；如需正式生效请点击保存');
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail?.message || detail || 'API 连接测试失败');
    } finally {
      setTestingStage('');
    }
  };

  const handleFetchModels = async () => {
    setFetchingModels(true);
    try {
      const response = await axios.post('/api/admin/operations/model-list', {
        stage: 'polish',
        base_url: formData.POLISH_BASE_URL,
        api_key: formData.POLISH_API_KEY,
        api_format: formData.MODEL_API_FORMAT,
      }, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      const models = Array.isArray(response.data?.models) ? response.data.models : [];
      setAvailableModels(models);
      if (models[0] && !String(formData.POLISH_MODEL || '').trim()) {
        applyUnifiedModel(models[0]);
      }
      toast.success(response.data?.message || `已拉取 ${models.length} 个模型`);
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(detail?.message || detail || '模型探测失败');
    } finally {
      setFetchingModels(false);
    }
  };

  const getMineruTokenPlaceholder = () => {
    const status = keyStatus.mineru;
    if (status?.set) {
      return status.last4 ? `已配置，后四位 ${status.last4}；留空则不修改` : '已配置；留空则不修改';
    }
    return 'mineru API token';
  };

  const getApiKeyPlaceholder = (stage) => {
    const status = keyStatus[stage];
    if (status?.set) {
      return status.last4 ? `已配置，后四位 ${status.last4}；留空则不修改` : '已配置；留空则不修改';
    }
    return 'sk-... 或 Google API Key';
  };

  const primaryModel = formData.POLISH_MODEL || formData.ENHANCE_MODEL || 'gpt-5.5';
  const primaryBaseUrl = formData.POLISH_BASE_URL || formData.ENHANCE_BASE_URL || '';
  const applyUnifiedModel = (modelName) => {
    setFormData((previous) => ({
      ...previous,
      POLISH_MODEL: modelName,
      ENHANCE_MODEL: modelName,
      EMOTION_MODEL: modelName,
      COMPRESSION_MODEL: modelName,
    }));
  };
  const applyUnifiedBaseUrl = (baseUrl) => {
    setAvailableModels([]);
    setFormData((previous) => ({
      ...previous,
      POLISH_BASE_URL: baseUrl,
      ENHANCE_BASE_URL: baseUrl,
      EMOTION_BASE_URL: baseUrl,
      COMPRESSION_BASE_URL: baseUrl,
    }));
  };
  const applyUnifiedApiKey = (apiKey) => {
    setAvailableModels([]);
    setFormData((previous) => ({
      ...previous,
      POLISH_API_KEY: apiKey,
      ENHANCE_API_KEY: apiKey,
      EMOTION_API_KEY: apiKey,
      COMPRESSION_API_KEY: apiKey,
    }));
  };
  const applyApiFormat = (apiFormat) => {
    setAvailableModels([]);
    setFormData((previous) => ({
      ...previous,
      MODEL_API_FORMAT: apiFormat,
    }));
  };

  const renderTestButton = (stage) => (
    <button
      type="button"
      onClick={() => handleTestModel(stage)}
      disabled={testingStage === stage}
      className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-60"
      title="测试当前页面填写的模型配置；成功后仍需点击保存才会正式生效"
    >
      {testingStage === stage ? (
        <RefreshCw className="h-4 w-4 animate-spin" />
      ) : (
        <PlugZap className="h-4 w-4" />
      )}
      测试连接
    </button>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="aurora-admin-section space-y-6 aurora-config-console">
      <div className="aurora-config-guide-shell">
        <ApiConfigGuide />
      </div>

      <div className="aurora-config-reference-grid">
        <div className="aurora-admin-card aurora-config-card aurora-config-provider-card p-6">
          <div className="aurora-config-card-title">
            <span className="aurora-config-title-icon aurora-config-title-icon-gateway">
              <Route className="h-5 w-5" />
            </span>
            <div>
              <h3>模型中转站配置</h3>
            </div>
          </div>

          <div className="aurora-config-provider-stack">
            <label>
              <span>供应商名称</span>
              <input
                type="text"
                value={formData.MODEL_PROVIDER_NAME}
                onChange={(e) => setFormData({ ...formData, MODEL_PROVIDER_NAME: e.target.value })}
                placeholder="手动输入供应商名称"
                className="aurora-admin-input"
                aria-label="供应商名称"
              />
            </label>
            <label>
              <span>API 地址</span>
              <input
                type="text"
                value={formData.POLISH_BASE_URL}
                onChange={(e) => applyUnifiedBaseUrl(e.target.value)}
                placeholder="https://your-sub-domain/v1"
                className="aurora-admin-input"
              />
            </label>
            <label>
              <span>API Key</span>
              <input
                type="password"
                value={formData.POLISH_API_KEY}
                onChange={(e) => applyUnifiedApiKey(e.target.value)}
                placeholder={getApiKeyPlaceholder('polish')}
                className="aurora-admin-input font-mono"
              />
            </label>
            <label>
              <span>API 格式</span>
              <select
                value={formData.MODEL_API_FORMAT}
                onChange={(e) => applyApiFormat(e.target.value)}
                className="aurora-admin-input"
                aria-label="API 格式"
              >
                {API_FORMAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>模型</span>
              <div className="aurora-config-model-picker">
                <EditableModelCombobox
                  id="admin-model"
                  value={primaryModel}
                  options={availableModels}
                  onChange={applyUnifiedModel}
                  inputClassName="aurora-admin-input"
                  label="模型"
                  placeholder="输入模型名，或探测后选择"
                  autoOpenOnOptions
                />
                <button
                  type="button"
                  onClick={handleFetchModels}
                  disabled={fetchingModels}
                  className="aurora-config-model-probe-button"
                  title="从中转站拉取 /v1/models 模型列表"
                >
                  <RefreshCw className={`h-4 w-4 ${fetchingModels ? 'animate-spin' : ''}`} />
                  探测模型
                </button>
              </div>
            </label>
            <label className="aurora-config-timeout-field">
              <span>超时时间</span>
              <div className="aurora-config-unit-input aurora-config-unit-input-compact">
                <input
                  type="number"
                  value={formData.API_REQUEST_INTERVAL || '60'}
                  onChange={(e) => setFormData({ ...formData, API_REQUEST_INTERVAL: e.target.value })}
                  className="aurora-admin-input"
                />
                <strong>秒</strong>
              </div>
            </label>
            <div className="aurora-config-connection-row">
              <span className="text-emerald-600">● 连接状态</span>
              <strong>{primaryBaseUrl ? '已配置' : '待配置'}</strong>
              <code className="aurora-config-mono-value">{primaryBaseUrl || '请填写 Sub/OpenAI Compatible Base URL'}</code>
              {renderTestButton('polish')}
            </div>

            <div className="aurora-config-quota-card aurora-config-embedded-quota">
              <div className="aurora-config-card-title no-margin">
                <span className="aurora-config-title-icon aurora-config-title-icon-quota">
                  <Gauge className="h-5 w-5" />
                </span>
                <div>
                  <h3>配额与限制</h3>
                </div>
              </div>
              <div className="aurora-config-quota-grid">
                <label>
                  <span>全站任务并发</span>
                  <select className="aurora-admin-input" value={formData.MAX_CONCURRENT_USERS} onChange={(e) => setFormData({ ...formData, MAX_CONCURRENT_USERS: e.target.value })}>
                    <option value="5">5（稳妥起步）</option>
                    <option value="8">8（观察后放量）</option>
                    <option value="10">10（峰值档）</option>
                  </select>
                </label>
                <label>
                  <span>相同 API Key 并发</span>
                  <select className="aurora-admin-input" value={formData.API_KEY_CONCURRENCY} onChange={(e) => setFormData({ ...formData, API_KEY_CONCURRENCY: e.target.value })}>
                    <option value="1">1（最保守）</option>
                    <option value="2">2（推荐）</option>
                    <option value="4">4（高额度 Key）</option>
                  </select>
                </label>
                <label>
                  <span>单会话最大消息数</span>
                  <input type="number" className="aurora-admin-input" value={formData.HISTORY_COMPRESSION_THRESHOLD} onChange={(e) => setFormData({ ...formData, HISTORY_COMPRESSION_THRESHOLD: e.target.value })} />
                </label>
                <label>
                  <span>单条消息最大长度</span>
                  <input type="number" className="aurora-admin-input" value={formData.SEGMENT_SKIP_THRESHOLD} onChange={(e) => setFormData({ ...formData, SEGMENT_SKIP_THRESHOLD: e.target.value })} />
                </label>
                <label>
                  <span>每日请求上限</span>
                  <input type="number" className="aurora-admin-input" value="10000" readOnly />
                </label>
              </div>
            </div>
          </div>
        </div>

        <div className="aurora-admin-card aurora-config-card aurora-config-security-card p-6">
          <div className="aurora-config-card-title">
            <span className="aurora-config-title-icon aurora-config-title-icon-security">
              <Fingerprint className="h-5 w-5" />
            </span>
            <div>
              <h3>安全配置</h3>
            </div>
          </div>
          <div className="aurora-config-security-list">
            <div className="aurora-config-switch-line">
              <div><strong>访问令牌认证</strong></div>
              <span className="aurora-config-state-chip is-on" role="status">已启用</span>
            </div>
            <label>
              <span>后台令牌有效期</span>
              <div className="aurora-config-unit-input">
                <input
                  type="number"
                  min="5"
                  className="aurora-admin-input"
                  value={formData.ACCESS_TOKEN_EXPIRE_MINUTES}
                  onChange={(e) => setFormData({ ...formData, ACCESS_TOKEN_EXPIRE_MINUTES: e.target.value })}
                />
                <strong>分钟</strong>
              </div>
            </label>
            <label>
              <span>用户令牌有效期</span>
              <div className="aurora-config-unit-input">
                <input
                  type="number"
                  min="30"
                  className="aurora-admin-input"
                  value={formData.USER_ACCESS_TOKEN_EXPIRE_MINUTES}
                  onChange={(e) => setFormData({ ...formData, USER_ACCESS_TOKEN_EXPIRE_MINUTES: e.target.value })}
                />
                <strong>分钟</strong>
              </div>
            </label>
            <label>
              <span>登录限流</span>
              <div className="aurora-config-unit-input">
                <input
                  type="number"
                  min="1"
                  className="aurora-admin-input"
                  value={formData.AUTH_RATE_LIMIT_PER_MINUTE}
                  onChange={(e) => setFormData({ ...formData, AUTH_RATE_LIMIT_PER_MINUTE: e.target.value })}
                />
                <strong>次/分钟</strong>
              </div>
            </label>
            <label>
              <span>兑换限流</span>
              <div className="aurora-config-unit-input">
                <input
                  type="number"
                  min="1"
                  className="aurora-admin-input"
                  value={formData.REDEEM_RATE_LIMIT_PER_MINUTE}
                  onChange={(e) => setFormData({ ...formData, REDEEM_RATE_LIMIT_PER_MINUTE: e.target.value })}
                />
                <strong>次/分钟</strong>
              </div>
            </label>
            <div className="aurora-config-switch-line">
              <div><strong>模型 Base URL 安全校验</strong></div>
              <span className="aurora-config-state-chip is-on" role="status">已启用</span>
            </div>
            <div className="aurora-config-switch-line aurora-config-local-proxy-line">
              <div>
                <strong>本地模型代理</strong>
              </div>
              <button
                type="button"
                className={formData.ALLOW_LOCAL_MODEL_PROXY ? 'is-on' : ''}
                aria-pressed={Boolean(formData.ALLOW_LOCAL_MODEL_PROXY)}
                onClick={() => setFormData({ ...formData, ALLOW_LOCAL_MODEL_PROXY: !formData.ALLOW_LOCAL_MODEL_PROXY })}
              >
                <span />
              </button>
            </div>
            <label className="aurora-config-server-host-field">
              <span>运行绑定地址</span>
              <input
                type="text"
                value={formData.SERVER_HOST}
                onChange={(e) => setFormData({ ...formData, SERVER_HOST: e.target.value })}
                placeholder="127.0.0.1"
                className="aurora-admin-input font-mono"
              />
            </label>
          </div>
        </div>
      </div>

      <div className="aurora-admin-card aurora-config-card aurora-config-document-card p-6">
        <div className="aurora-config-card-title">
          <span className="aurora-config-title-icon aurora-config-title-icon-feature">
            <FileText className="h-5 w-5" />
          </span>
          <div>
            <h3>文档解析设置</h3>
            <p className="mt-1 text-xs text-slate-500">支持 PDF、Word(.docx)、Markdown(.md/.markdown)、TXT；MinerU 当前主要用于 PDF 高精度结构解析。</p>
          </div>
        </div>
        <div className="aurora-config-document-grid">
          <label className="aurora-config-field">
            <span>PDF 解析引擎</span>
            <select
              value={formData.PDF_STRUCTURE_ENGINE}
              onChange={(e) => setFormData({ ...formData, PDF_STRUCTURE_ENGINE: e.target.value })}
              className="aurora-admin-input"
              aria-label="PDF 解析引擎"
            >
              <option value="mineru">MinerU 高精度解析</option>
              <option value="markitdown">MarkItDown 本地解析</option>
            </select>
          </label>
          <label className="aurora-config-field">
            <span>MinerU Base URL</span>
            <input
              type="text"
              value={formData.MINERU_BASE_URL}
              onChange={(e) => setFormData({ ...formData, MINERU_BASE_URL: e.target.value })}
              placeholder="https://mineru.net"
              className="aurora-admin-input font-mono"
            />
          </label>
          <label className="aurora-config-field">
            <span>MinerU API Token</span>
            <input
              type="password"
              value={formData.MINERU_API_TOKEN}
              onChange={(e) => setFormData({ ...formData, MINERU_API_TOKEN: e.target.value })}
              placeholder={getMineruTokenPlaceholder()}
              className="aurora-admin-input font-mono"
            />
          </label>
          <label className="aurora-config-field">
            <span>MinerU 模型版本</span>
            <input
              type="text"
              value={formData.MINERU_MODEL_VERSION}
              onChange={(e) => setFormData({ ...formData, MINERU_MODEL_VERSION: e.target.value })}
              placeholder="vlm"
              className="aurora-admin-input font-mono"
            />
          </label>
          <label className="aurora-config-field aurora-config-field-compact">
            <span>语言</span>
            <input
              type="text"
              value={formData.MINERU_LANGUAGE}
              onChange={(e) => setFormData({ ...formData, MINERU_LANGUAGE: e.target.value })}
              placeholder="ch"
              className="aurora-admin-input font-mono"
            />
          </label>
          <label className="aurora-config-field">
            <span>解析超时</span>
            <div className="aurora-config-unit-input">
              <input
                type="number"
                min="1"
                value={formData.MINERU_TIMEOUT_SECONDS}
                onChange={(e) => setFormData({ ...formData, MINERU_TIMEOUT_SECONDS: e.target.value })}
                className="aurora-admin-input"
              />
              <strong>秒</strong>
            </div>
          </label>
          <label className="aurora-config-field">
            <span>轮询间隔</span>
            <div className="aurora-config-unit-input">
              <input
                type="number"
                min="0.5"
                step="0.5"
                value={formData.MINERU_POLL_INTERVAL_SECONDS}
                onChange={(e) => setFormData({ ...formData, MINERU_POLL_INTERVAL_SECONDS: e.target.value })}
                className="aurora-admin-input"
              />
              <strong>秒</strong>
            </div>
          </label>
        </div>
        <div className="aurora-config-document-switches">
          {[
            ['启用公式解析', 'MINERU_ENABLE_FORMULA'],
            ['启用表格解析', 'MINERU_ENABLE_TABLE'],
            ['OCR 识别', 'MINERU_IS_OCR'],
          ].map(([title, key]) => {
            const enabled = Boolean(formData[key]);
            return (
              <div key={key} className="aurora-config-feature-switch aurora-config-document-switch">
                <div><strong>{title}</strong></div>
                <button
                  type="button"
                  className={enabled ? 'is-on' : ''}
                  aria-pressed={enabled}
                  onClick={() => setFormData({ ...formData, [key]: !formData[key] })}
                >
                  <span />
                </button>
              </div>
            );
          })}
        </div>
        <p className="aurora-config-document-note">
          MinerU 官方支持 PDF、DOCX、PPTX、XLSX、图片和网页；当前 GankAIGC 默认仅将 MinerU 用于 PDF，Word(.docx)、Markdown、TXT 使用本地解析链路，速度更快且不消耗 MinerU 额度。
        </p>
      </div>

      <div className="aurora-admin-card aurora-config-feature-card p-6">
        <div className="aurora-config-card-title">
          <span className="aurora-config-title-icon aurora-config-title-icon-feature">
            <SlidersHorizontal className="h-5 w-5" />
          </span>
          <div>
            <h3>系统功能开关</h3>
          </div>
        </div>
        <div className="aurora-config-feature-switches">
          {[
            ['账号注册控制', 'REGISTRATION_ENABLED'],
            ['思考模式', 'THINKING_MODE_ENABLED'],
          ].map(([title, key]) => {
            const enabled = Boolean(formData[key]);
            return (
              <div key={title} className="aurora-config-feature-switch">
                <div><strong>{title}</strong></div>
                <button
                  type="button"
                  className={enabled ? 'is-on' : ''}
                  aria-pressed={enabled}
                  onClick={() => setFormData({ ...formData, [key]: !formData[key] })}
                >
                  <span />
                </button>
              </div>
            );
          })}
          {[
            ['邮件通知', false],
            ['内容审核', true],
            ['插件功能', false],
          ].map(([title, enabled]) => (
            <div key={title} className="aurora-config-feature-switch">
              <div><strong>{title}</strong></div>
              <span className={`aurora-config-readonly-switch ${enabled ? 'is-on' : ''}`} role="status" aria-label={enabled ? '已启用' : '未开放'}>
                <span />
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="aurora-config-advanced-drawer">
        <details>
          <summary>高级模型分阶段配置</summary>
          <div className="aurora-config-grid mt-4">
            <div className="aurora-admin-card aurora-config-card p-6">
              <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-teal-50 rounded-xl flex items-center justify-center"><Cpu className="w-5 h-5 text-teal-600" /></div>
                  <div><h3 className="text-lg font-bold text-gray-900">润色模型配置</h3></div>
                </div>
                {renderTestButton('polish')}
              </div>
              <div className="space-y-5">
                <label><span className="block text-sm font-medium text-gray-500 mb-2">模型名称</span><input type="text" value={formData.POLISH_MODEL} onChange={(e) => setFormData({ ...formData, POLISH_MODEL: e.target.value })} placeholder="gpt-5.5" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">API Key</span><input type="password" value={formData.POLISH_API_KEY} onChange={(e) => setFormData({ ...formData, POLISH_API_KEY: e.target.value })} placeholder={getApiKeyPlaceholder('polish')} className="aurora-admin-input w-full px-4 py-2.5 text-sm font-mono" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">Base URL</span><input type="text" value={formData.POLISH_BASE_URL} onChange={(e) => setFormData({ ...formData, POLISH_BASE_URL: e.target.value })} placeholder="https://api.openai.com/v1" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
              </div>
            </div>

            <div className="aurora-admin-card aurora-config-card p-6">
              <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-cyan-50 rounded-xl flex items-center justify-center"><Cpu className="w-5 h-5 text-cyan-600" /></div>
                  <div><h3 className="text-lg font-bold text-gray-900">论文增强模型配置</h3></div>
                </div>
                {renderTestButton('enhance')}
              </div>
              <div className="space-y-5">
                <label><span className="block text-sm font-medium text-gray-500 mb-2">模型名称</span><input type="text" value={formData.ENHANCE_MODEL} onChange={(e) => setFormData({ ...formData, ENHANCE_MODEL: e.target.value })} placeholder="gpt-5.5" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">API Key</span><input type="password" value={formData.ENHANCE_API_KEY} onChange={(e) => setFormData({ ...formData, ENHANCE_API_KEY: e.target.value })} placeholder={getApiKeyPlaceholder('enhance')} className="aurora-admin-input w-full px-4 py-2.5 text-sm font-mono" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">Base URL</span><input type="text" value={formData.ENHANCE_BASE_URL} onChange={(e) => setFormData({ ...formData, ENHANCE_BASE_URL: e.target.value })} placeholder="https://api.openai.com/v1" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
              </div>
            </div>

            <div className="aurora-admin-card aurora-config-card p-6">
              <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center"><Brain className="w-5 h-5 text-purple-600" /></div>
                  <div><h3 className="text-lg font-bold text-gray-900">情感润色模型配置</h3></div>
                </div>
                {renderTestButton('emotion')}
              </div>
              <div className="space-y-5">
                <label><span className="block text-sm font-medium text-gray-500 mb-2">模型名称</span><input type="text" value={formData.EMOTION_MODEL} onChange={(e) => setFormData({ ...formData, EMOTION_MODEL: e.target.value })} placeholder="gpt-5.5" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">API Key</span><input type="password" value={formData.EMOTION_API_KEY} onChange={(e) => setFormData({ ...formData, EMOTION_API_KEY: e.target.value })} placeholder={getApiKeyPlaceholder('emotion')} className="aurora-admin-input w-full px-4 py-2.5 text-sm font-mono" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">Base URL</span><input type="text" value={formData.EMOTION_BASE_URL} onChange={(e) => setFormData({ ...formData, EMOTION_BASE_URL: e.target.value })} placeholder="https://api.openai.com/v1" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
              </div>
            </div>

            <div className="aurora-admin-card aurora-config-card p-6">
              <div className="flex items-center gap-3 mb-6"><div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center"><Brain className="w-5 h-5 text-blue-600" /></div><h3 className="text-lg font-bold text-gray-900">思考模式配置</h3></div>
              <div className="space-y-5">
                <div className="flex items-center justify-between"><div><label className="block text-sm font-medium text-gray-700">启用思考模式</label></div><button type="button" onClick={() => setFormData({ ...formData, THINKING_MODE_ENABLED: !formData.THINKING_MODE_ENABLED })} className={`relative w-12 h-7 rounded-full transition-colors duration-200 ${formData.THINKING_MODE_ENABLED ? 'bg-blue-600' : 'bg-gray-200'}`}><span className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow transition-transform ${formData.THINKING_MODE_ENABLED ? 'translate-x-5' : 'translate-x-0'}`} /></button></div>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">思考强度</span><select value={formData.THINKING_MODE_EFFORT} onChange={(e) => setFormData({ ...formData, THINKING_MODE_EFFORT: e.target.value })} disabled={!formData.THINKING_MODE_ENABLED} className="aurora-admin-input w-full px-4 py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed"><option value="none">无推理 (最低延迟)</option><option value="low">轻度推理</option><option value="medium">中度推理</option><option value="high">深度推理 (推荐)</option><option value="xhigh">极深推理 (仅部分模型支持)</option></select></label>
              </div>
            </div>

            <div className="aurora-admin-card aurora-config-card p-6">
              <div className="flex flex-col gap-4 mb-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3"><div className="w-10 h-10 bg-orange-50 rounded-xl flex items-center justify-center"><Settings className="w-5 h-5 text-orange-600" /></div><div><h3 className="text-lg font-bold text-gray-900">压缩模型与运行参数</h3></div></div>
                {renderTestButton('compression')}
              </div>
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <label><span className="block text-sm font-medium text-gray-500 mb-2">压缩模型</span><input type="text" value={formData.COMPRESSION_MODEL} onChange={(e) => setFormData({ ...formData, COMPRESSION_MODEL: e.target.value })} placeholder="gpt-5.5" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">压缩 API Key</span><input type="password" value={formData.COMPRESSION_API_KEY} onChange={(e) => setFormData({ ...formData, COMPRESSION_API_KEY: e.target.value })} placeholder={getApiKeyPlaceholder('compression')} className="aurora-admin-input w-full px-4 py-2.5 text-sm font-mono" /></label>
                <label><span className="block text-sm font-medium text-gray-500 mb-2">压缩 Base URL</span><input type="text" value={formData.COMPRESSION_BASE_URL} onChange={(e) => setFormData({ ...formData, COMPRESSION_BASE_URL: e.target.value })} placeholder="https://api.openai.com/v1" className="aurora-admin-input w-full px-4 py-2.5 text-sm" /></label>
              </div>
            </div>
          </div>
        </details>
      </div>

      <div className="aurora-config-bottom-bar">
        <div className="aurora-config-bottom-actions">
          <button onClick={fetchConfig} disabled={loading} className="aurora-admin-secondary-action">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button onClick={handleSave} disabled={saving} className="aurora-admin-action">
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存配置'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfigManager;
