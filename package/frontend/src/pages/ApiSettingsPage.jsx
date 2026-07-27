import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, CheckCircle2, KeyRound, Loader2, PlugZap, RefreshCw, Save, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { userAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import EditableModelCombobox from '../components/EditableModelCombobox';

const API_FORMAT_OPTIONS = [
  { value: 'openai_chat', label: 'OpenAI Compatible' },
  { value: 'anthropic', label: 'Anthropic Messages（原生）' },
];

const FIELD_CONFIG = [
  { field: 'base_url', label: 'Base URL', placeholder: '例如 https://api.openai.com/v1', type: 'text', required: true },
  { field: 'api_key', label: 'API Key', placeholder: '留空则使用已保存 Key', type: 'password', required: false },
  { field: 'api_format', label: 'API 格式', type: 'select', required: true },
  { field: 'polish_model', label: '润色模型', placeholder: '例如 gpt-5.4', type: 'text', required: true },
  { field: 'enhance_model', label: '增强模型', placeholder: '例如 gpt-5.4', type: 'text', required: true },
  { field: 'emotion_model', label: '感情润色模型', placeholder: '可选', type: 'text', required: false },
];

const ApiSettingsPage = () => {
  const [form, setForm] = useState({
    base_url: '',
    api_format: 'openai_chat',
    api_key: '',
    polish_model: 'gpt-5.4',
    enhance_model: 'gpt-5.4',
    emotion_model: '',
  });
  const [maskedKey, setMaskedKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await userAPI.getProviderConfig();
        if (response.data) {
          setForm({
            base_url: response.data.base_url,
            api_format: response.data.api_format || 'openai_chat',
            api_key: '',
            polish_model: response.data.polish_model,
            enhance_model: response.data.enhance_model,
            emotion_model: response.data.emotion_model || '',
          });
          setMaskedKey(response.data.api_key_last4);
        }
      } catch (error) {
        console.error('加载 API 配置失败:', error);
      }
    };
    loadConfig();
  }, []);

  const updateField = (field, value) => {
    if (['base_url', 'api_key', 'api_format'].includes(field)) {
      setAvailableModels([]);
    }
    setForm((current) => ({ ...current, [field]: value }));
  };

  const getErrorMessage = (error, fallback) => {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (detail?.message) {
      return detail.message;
    }
    return fallback;
  };

  const handleSave = async (event) => {
    event.preventDefault();
    if (!form.api_key.trim() && !maskedKey) {
      toast.error('首次保存需要输入 API Key');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        ...form,
        emotion_model: form.emotion_model || null,
      };
      const response = await userAPI.saveProviderConfig(payload);
      setMaskedKey(response.data.api_key_last4);
      setForm((current) => ({ ...current, api_key: '' }));
      toast.success('API 配置已保存');
    } catch (error) {
      toast.error(getErrorMessage(error, '保存失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (testing) return;

    setTesting(true);
    try {
      const response = await userAPI.testProviderModelConfig({
        model: form.polish_model,
        base_url: form.base_url,
        api_key: form.api_key,
        api_format: form.api_format,
      });
      toast.success(response.data?.message || 'API 连接测试通过；如需正式生效请点击保存');
    } catch (error) {
      toast.error(getErrorMessage(error, '请先保存完整 API 配置'));
    } finally {
      setTesting(false);
    }
  };

  const handleFetchModels = async () => {
    if (fetchingModels) return;

    setFetchingModels(true);
    try {
      const response = await userAPI.listProviderModels({
        base_url: form.base_url,
        api_key: form.api_key,
        api_format: form.api_format,
      });
      const models = Array.isArray(response.data?.models) ? response.data.models : [];
      setAvailableModels(models);
      if (models[0]) {
        setForm((current) => ({
          ...current,
          polish_model: current.polish_model || models[0],
          enhance_model: current.enhance_model || models[0],
        }));
      }
      toast.success(response.data?.message || `已拉取 ${models.length} 个模型`);
    } catch (error) {
      toast.error(getErrorMessage(error, '模型探测失败'));
    } finally {
      setFetchingModels(false);
    }
  };

  const renderModelField = ({ field, label, placeholder, required }) => {
    return (
      <div key={field}>
        <label className="aurora-field-label" htmlFor={`api-${field}`}>{label}</label>
        <EditableModelCombobox
          id={`api-${field}`}
          value={form[field]}
          options={availableModels}
          onChange={(value) => updateField(field, value)}
          placeholder={placeholder}
          inputClassName="aurora-input"
          required={required}
          label={label}
          autoOpenOnOptions={field === 'polish_model'}
        />
      </div>
    );
  };

  const renderFetchModelsButton = () => (
    <button
      type="button"
      onClick={handleFetchModels}
      disabled={fetchingModels}
      className="aurora-secondary-action min-h-[48px] px-6 disabled:cursor-not-allowed disabled:opacity-60"
      title="从当前账号配置的中转站拉取真实模型列表"
    >
      <RefreshCw className={`h-4 w-4 ${fetchingModels ? 'animate-spin' : ''}`} />
      探测模型
    </button>
  );

  const renderTestConnectionButton = () => (
    <button
      type="button"
      onClick={handleTest}
      disabled={testing}
      className="aurora-secondary-action min-h-[48px] px-6 disabled:cursor-not-allowed disabled:opacity-60"
      title="测试当前页面填写的模型配置；成功后仍需点击保存才会正式生效"
    >
      {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}
      测试连接
    </button>
  );

  return (
    <div className="gank-app-page aurora-app-page aurora-account-page">
      <div className="gank-ambient-orb orb-one" />
      <div className="gank-ambient-orb orb-two" />
      <div className="gank-ambient-orb orb-three" />

      <header className="sticky top-0 z-50">
        <nav className="apple-global-nav aurora-topbar">
          <div className="mx-auto flex min-h-[68px] max-w-[1180px] items-center justify-between gap-4 px-5 sm:px-8 lg:px-10">
            <BrandLogo size="md" showText className="aurora-brand-logo" />
            <Link to="/workspace" className="aurora-account-back-link">
              <ArrowLeft className="h-4 w-4" />
              <span>返回工作台</span>
            </Link>
          </div>
        </nav>
      </header>

      <main className="aurora-page-shell aurora-account-shell relative z-[1] mx-auto max-w-[1180px] px-5 pb-12 pt-8 sm:px-8 lg:px-10">
        <h1 className="sr-only">自带 API 配置</h1>
        <div className="grid gap-5 lg:grid-cols-[0.78fr_1.22fr]">
          <aside className="apple-utility-card aurora-account-card aurora-api-summary">
            <div className="aurora-profile-avatar" aria-hidden="true">
              <KeyRound className="h-10 w-10" />
            </div>
            <h2>模型服务接入</h2>
            <p>自带 API 模式会优先使用你保存的供应商配置，适合已有额度或私有模型网关。</p>

            <div className="aurora-api-checklist">
              <div>
                <ShieldCheck className="h-4 w-4" />
                <span>仅当前账号使用，不影响平台后台模型配置</span>
              </div>
              <div>
                <SlidersHorizontal className="h-4 w-4" />
                <span>支持探测真实模型列表并下拉选择</span>
              </div>
              <div>
                <CheckCircle2 className="h-4 w-4" />
                <span>测试当前填写内容，成功后仍需保存才会生效</span>
              </div>
            </div>
          </aside>

          <section className="apple-utility-card aurora-account-card aurora-api-form-card">
            <div className="aurora-account-form-head">
              <div>
                <h2>供应商配置</h2>
              </div>
            </div>

            {maskedKey && (
              <div className="aurora-saved-key-notice" role="status">
                <CheckCircle2 className="h-4 w-4" />
                <span>已保存 API Key：****{maskedKey}。如需修改，请重新输入完整 Key 后保存。</span>
              </div>
            )}

            <form onSubmit={handleSave} className="aurora-api-form">
              {FIELD_CONFIG.map(({ field, label, placeholder, type, required }) => {
                if (field.endsWith('_model')) {
                  if (field === 'emotion_model') {
                    return (
                      <React.Fragment key={field}>
                        {renderModelField({ field, label, placeholder, required })}
                        <div className="aurora-api-probe-slot">
                          {renderFetchModelsButton()}
                          {renderTestConnectionButton()}
                        </div>
                      </React.Fragment>
                    );
                  }
                  return renderModelField({ field, label, placeholder, required });
                }
                if (field === 'api_format') {
                  return (
                    <div key={field} className="md:col-span-2">
                      <label className="aurora-field-label" htmlFor="api-format">{label}</label>
                      <select
                        id="api-format"
                        value={form.api_format}
                        onChange={(event) => updateField('api_format', event.target.value)}
                        className="aurora-input"
                        required={required}
                      >
                        {API_FORMAT_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                  );
                }
                return (
                  <div key={field} className={field === 'base_url' || field === 'api_key' ? 'md:col-span-2' : ''}>
                    <label className="aurora-field-label" htmlFor={`api-${field}`}>{label}</label>
                    <input
                      id={`api-${field}`}
                      type={type}
                      value={form[field]}
                      onChange={(event) => updateField(field, event.target.value)}
                      placeholder={placeholder}
                      className="aurora-input"
                      required={required}
                      autoComplete={field === 'api_key' ? 'off' : undefined}
                    />
                  </div>
                );
              })}

              <div className="aurora-api-actions aurora-api-save-actions md:col-span-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="aurora-account-primary apple-action-pill disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {loading ? '保存中...' : '保存配置'}
                </button>
              </div>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
};

export default ApiSettingsPage;
