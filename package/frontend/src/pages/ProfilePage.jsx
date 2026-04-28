import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, Copy, Loader2, Save, ShieldCheck, UserCircle, UserPlus } from 'lucide-react';
import { authAPI, userAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import BeerIcon from '../components/BeerIcon';
import { formatChinaDateTime } from '../utils/dateTime';

const ProfilePage = () => {
  const [profile, setProfile] = useState(null);
  const [nickname, setNickname] = useState('');
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generatingInvite, setGeneratingInvite] = useState(false);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const [profileResponse, inviteResponse] = await Promise.all([
        authAPI.me(),
        userAPI.getMyInvite(),
      ]);
      setProfile(profileResponse.data);
      setNickname(profileResponse.data.nickname || profileResponse.data.username || '');
      setInvite(inviteResponse.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || '加载个人信息失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const nextNickname = nickname.trim();
    if (!nextNickname) {
      toast.error('昵称不能为空');
      return;
    }

    setSaving(true);
    try {
      const response = await authAPI.updateProfile({ nickname: nextNickname });
      setProfile(response.data);
      setNickname(response.data.nickname || response.data.username || '');
      toast.success('昵称已更新');
    } catch (error) {
      toast.error(error.response?.data?.detail || '保存昵称失败');
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateInvite = async () => {
    setGeneratingInvite(true);
    try {
      const response = await userAPI.createMyInvite();
      setInvite(response.data);
      toast.success('邀请码已生成');
    } catch (error) {
      toast.error(error.response?.data?.detail || '生成邀请码失败');
    } finally {
      setGeneratingInvite(false);
    }
  };

  const handleCopyInvite = async () => {
    if (!invite?.code) return;

    try {
      await navigator.clipboard.writeText(invite.code);
      toast.success('邀请码已复制');
    } catch (error) {
      toast.error('复制失败，请手动复制');
    }
  };

  return (
    <div className="gank-app-page">
      <header className="gank-glass-toolbar sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <BrandLogo size="sm" />
          <Link to="/workspace" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 text-sm font-medium">
            <ArrowLeft className="w-4 h-4" />
            返回工作台
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6">
          <p className="text-sm font-semibold text-teal-600">个人信息</p>
          <h1 className="text-3xl font-bold text-slate-950 mt-1">账号资料</h1>
        </div>
        {loading ? (
          <div className="gank-card rounded-2xl p-10 flex items-center justify-center text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            加载中...
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-6">
            <section className="gank-glass-card rounded-[2rem] p-6">
              <div className="gank-icon-tile w-14 h-14 rounded-2xl flex items-center justify-center mb-5">
                <UserCircle className="w-8 h-8" />
              </div>
              <h1 className="text-2xl font-bold text-gray-950">{profile?.nickname || profile?.username}</h1>
              <p className="text-sm text-gray-500 mt-1">@{profile?.username}</p>

              <div className="mt-6 space-y-3 text-sm">
                <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                  <span className="text-gray-500">用户 ID</span>
                  <span className="font-mono text-gray-900">#{profile?.id}</span>
                </div>
                <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                  <span className="text-gray-500">注册时间</span>
                  <span className="text-gray-900">
                    {formatChinaDateTime(profile?.created_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between border-t border-gray-100 pt-3">
                  <span className="text-gray-500">最近登录</span>
                  <span className="text-gray-900">
                    {formatChinaDateTime(profile?.last_login_at)}
                  </span>
                </div>
              </div>
            </section>

            <section className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="gank-card rounded-2xl p-5">
                  <div className="flex items-center gap-2 text-teal-700 mb-3">
                    <BeerIcon className="w-5 h-5" />
                    <span className="font-semibold">剩余啤酒</span>
                  </div>
                  <p className="text-3xl font-bold text-gray-950">
                    {profile?.is_unlimited ? '无限啤酒' : profile?.credit_balance ?? 0}
                  </p>
                </div>
                <div className="gank-card rounded-2xl p-5">
                  <div className="flex items-center gap-2 text-emerald-700 mb-3">
                    <ShieldCheck className="w-5 h-5" />
                    <span className="font-semibold">账号状态</span>
                  </div>
                  <p className="text-3xl font-bold text-gray-950">{profile?.is_active ? '正常' : '禁用'}</p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="gank-card rounded-2xl p-6">
                <h2 className="text-lg font-bold text-gray-950 mb-4">修改昵称</h2>
                <label className="block text-sm font-medium text-gray-600 mb-2">昵称</label>
                <input
                  type="text"
                  value={nickname}
                  onChange={(event) => setNickname(event.target.value)}
                  maxLength={32}
                  className="gank-input px-4 py-3 rounded-xl"
                  placeholder="输入昵称"
                />
                <div className="mt-4 flex items-center justify-between gap-3">
                  <p className="text-xs text-gray-500">最多 32 个字符。</p>
                  <button
                    type="submit"
                    disabled={saving}
                    className="gank-primary-button inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl disabled:opacity-60 text-white font-semibold transition-colors"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    保存昵称
                  </button>
                </div>
              </form>

              <div className="gank-card rounded-2xl p-6">
                <div className="flex items-start justify-between gap-4 mb-5">
                  <div>
                    <div className="flex items-center gap-2 text-teal-700 mb-2">
                      <UserPlus className="w-5 h-5" />
                      <span className="font-semibold">我的邀请码</span>
                    </div>
                    <p className="text-sm text-gray-500">每个账号仅可生成 1 个邀请码。</p>
                  </div>
                </div>

                {invite?.code ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-gray-600">邀请码状态</span>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${invite.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                        {invite.is_active ? '可使用' : '已使用'}
                      </span>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3">
                      <div className="gank-input flex-1 rounded-xl px-4 py-3 font-mono text-sm text-gray-950 break-all">
                        {invite.code}
                      </div>
                      <button
                        type="button"
                        onClick={handleCopyInvite}
                        className="gank-secondary-button inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-semibold transition-colors"
                      >
                        <Copy className="w-4 h-4" />
                        复制邀请码
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleGenerateInvite}
                    disabled={generatingInvite}
                    className="gank-primary-button inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl disabled:opacity-60 text-white font-semibold transition-colors"
                  >
                    {generatingInvite ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                    生成邀请码
                  </button>
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
};

export default ProfilePage;
