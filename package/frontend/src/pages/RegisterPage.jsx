import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, KeyRound } from 'lucide-react';
import { authAPI } from '../api';
import BrandLogo from '../components/BrandLogo';

const RegisterPage = () => {
  const [inviteCode, setInviteCode] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);

    try {
      await authAPI.register({
        invite_code: inviteCode,
        username,
        password,
      });
      const loginResponse = await authAPI.login({ username, password });
      localStorage.setItem('userToken', loginResponse.data.access_token);
      toast.success('注册成功');
      navigate('/workspace');
    } catch (error) {
      toast.error(error.response?.data?.detail || '注册失败，请检查邀请码和账号信息');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="gank-auth-page flex items-center justify-center px-5 py-10">
      <div className="w-full max-w-md gank-auth-card rounded-[2rem] p-7 sm:p-8">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <BrandLogo size="sm" showText={false} className="mb-4" />
            <p className="text-sm text-teal-600 font-semibold">邀请码注册</p>
            <h1 className="text-3xl font-bold text-slate-950 mt-1">创建用户账号</h1>
            <p className="text-slate-500 text-sm mt-2">注册后可兑换次数，或后续配置自己的 API 使用。</p>
          </div>
          <div className="gank-icon-tile w-12 h-12 rounded-2xl flex items-center justify-center">
            <KeyRound className="w-6 h-6" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={inviteCode}
            onChange={(event) => setInviteCode(event.target.value)}
            placeholder="邀请码"
            className="gank-input px-4 py-3 rounded-2xl"
            required
          />
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="用户名，至少 3 位"
            className="gank-input px-4 py-3 rounded-2xl"
            required
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码，至少 8 位"
            className="gank-input px-4 py-3 rounded-2xl"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="gank-primary-button w-full py-3.5 rounded-2xl disabled:opacity-60 text-white font-semibold transition-all active:scale-[0.98]"
          >
            {loading ? '注册中...' : '注册并进入'}
          </button>
        </form>

        <p className="mt-6 text-sm text-slate-500">
          已有账号？{' '}
          <Link to="/login" className="text-emerald-600 hover:text-emerald-700 font-medium">
            去登录
          </Link>
        </p>

        <button
          type="button"
          onClick={() => navigate('/')}
          className="mt-6 inline-flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-slate-700"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          返回首页
        </button>
      </div>
    </div>
  );
};

export default RegisterPage;
