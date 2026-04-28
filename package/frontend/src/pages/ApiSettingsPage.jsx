import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, KeyRound, Save } from 'lucide-react';
import { userAPI } from '../api';
import BrandLogo from '../components/BrandLogo';

const ApiSettingsPage = () => {
  const [form, setForm] = useState({
    base_url: '',
    api_key: '',
    polish_model: 'gpt-5.4',
    enhance_model: 'gpt-5.4',
    emotion_model: '',
  });
  const [maskedKey, setMaskedKey] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await userAPI.getProviderConfig();
        if (response.data) {
          setForm({
            base_url: response.data.base_url,
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
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSave = async (event) => {
    event.preventDefault();
    if (!form.api_key.trim()) {
      toast.error('保存时需要重新输入 API Key');
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
      toast.error(error.response?.data?.detail || '保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    try {
      await userAPI.testProviderConfig();
      toast.success('配置可读取，连接测试已通过基础校验');
    } catch (error) {
      toast.error(error.response?.data?.detail || '请先保存完整 API 配置');
    }
  };

  return (
    <div className="gank-app-page">
      <header className="gank-glass-toolbar sticky top-0 z-40">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <BrandLogo size="sm" />
          <Link to="/workspace" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-900 text-sm font-semibold">
            <ArrowLeft className="w-4 h-4" />
            返回工作台
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="gank-card rounded-[2rem] p-6 sm:p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="gank-icon-tile w-12 h-12 rounded-2xl flex items-center justify-center">
              <KeyRound className="w-6 h-6 text-amber-500" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-950">自带 API 配置</h1>
              <p className="text-slate-500 text-sm">API Key 会加密保存，页面只显示后 4 位。</p>
            </div>
          </div>

          {maskedKey && (
            <div className="mb-5 rounded-2xl bg-emerald-50 text-emerald-700 px-4 py-3 text-sm font-medium">
              已保存 API Key：****{maskedKey}
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-4">
            {[
              ['base_url', 'Base URL，例如 https://api.openai.com/v1'],
              ['api_key', 'API Key，保存时需重新输入'],
              ['polish_model', '润色模型'],
              ['enhance_model', '增强模型'],
              ['emotion_model', '感情润色模型，可选'],
            ].map(([field, placeholder]) => (
              <input
                key={field}
                type={field === 'api_key' ? 'password' : 'text'}
                value={form[field]}
                onChange={(event) => updateField(field, event.target.value)}
                placeholder={placeholder}
                className="gank-input px-4 py-3 rounded-2xl"
                required={field !== 'emotion_model'}
              />
            ))}
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                type="submit"
                disabled={loading}
                className="gank-primary-button flex-1 inline-flex items-center justify-center gap-2 py-3 rounded-2xl disabled:opacity-60 text-white font-semibold"
              >
                <Save className="w-4 h-4" />
                {loading ? '保存中...' : '保存配置'}
              </button>
              <button
                type="button"
                onClick={handleTest}
                className="gank-secondary-button flex-1 py-3 rounded-2xl text-slate-900 font-semibold"
              >
                测试配置
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
};

export default ApiSettingsPage;
