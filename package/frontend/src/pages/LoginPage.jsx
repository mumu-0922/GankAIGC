import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, Shield } from 'lucide-react';
import { authAPI } from '../api';
import BrandLogo from '../components/BrandLogo';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);

    try {
      const response = await authAPI.login({ username, password });
      localStorage.setItem('userToken', response.data.access_token);
      toast.success('登录成功');
      navigate('/workspace');
    } catch (error) {
      toast.error(error.response?.data?.detail || '登录失败，请检查账号密码');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="gank-auth-page flex items-center justify-center px-5 py-10">
      <div className="w-full max-w-md gank-auth-card rounded-[2rem] p-7 sm:p-8">
        <div className="mb-8 flex items-center justify-between">
          <BrandLogo size="sm" showText={false} />
          <div>
            <p className="text-sm text-teal-600 font-semibold text-right">用户登录</p>
            <h1 className="text-3xl font-bold text-slate-950 mt-1">进入工作台</h1>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="用户名"
            className="gank-input px-4 py-3 rounded-2xl"
            required
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码"
            className="gank-input px-4 py-3 rounded-2xl"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="gank-primary-button w-full py-3.5 rounded-2xl disabled:opacity-60 text-white font-semibold transition-all active:scale-[0.98]"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/register" className="text-blue-600 hover:text-blue-700 font-medium">
            邀请码注册
          </Link>
          <Link to="/admin" className="text-slate-500 hover:text-slate-900 flex items-center gap-1">
            <Shield className="w-4 h-4" />
            管理后台
          </Link>
        </div>

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

export default LoginPage;
