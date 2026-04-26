import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle,
  FileText,
  KeyRound,
  LogIn,
  Shield,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from 'lucide-react';
import BrandLogo from '../components/BrandLogo';

const featureCards = [
  {
    title: '智能降 AI',
    desc: '面向论文文本的润色与原创性增强流程',
    icon: Sparkles,
    accent: 'text-blue-600 bg-blue-50',
  },
  {
    title: '语义保持',
    desc: '保留论文原意，减少机械化表达',
    icon: FileText,
    accent: 'text-teal-600 bg-teal-50',
  },
  {
    title: '账号体系',
    desc: '注册登录后按次数使用，也可配置自带 API',
    icon: KeyRound,
    accent: 'text-violet-600 bg-violet-50',
  },
];

const scenarioCards = [
  { label: '初稿降 AI', value: '润色 + 增强' },
  { label: '二稿优化', value: '语义更自然' },
  { label: '投稿前检查', value: '保留处理记录' },
  { label: '自带 API', value: '不消耗平台次数' },
];

const WelcomePage = () => {
  const navigate = useNavigate();

  const goTo = (path) => {
    navigate(path);
  };

  return (
    <div className="gank-auth-page overflow-hidden">
      <header className="sticky top-0 z-30 border-b border-white/70 bg-white/70 backdrop-blur-2xl">
        <div className="mx-auto flex min-h-[76px] max-w-7xl items-center justify-between px-5 sm:px-8">
          <BrandLogo size="sm" />

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => goTo('/admin')}
              className="hidden items-center gap-2 rounded-xl border border-white/80 bg-white/75 px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:text-slate-950 sm:flex"
            >
              <Shield className="h-4 w-4 text-blue-600" />
              管理后台
            </button>
            <button
              type="button"
              onClick={() => goTo('/login')}
              className="gank-primary-button inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition active:scale-[0.98]"
            >
              <LogIn className="h-4 w-4" />
              登录 / 注册
            </button>
          </div>
        </div>
      </header>

      <main id="home" className="relative mx-auto max-w-7xl px-5 pb-10 pt-12 sm:px-8 lg:pt-20">
        <section className="grid items-center gap-12 lg:grid-cols-[1.02fr_0.98fr]">
          <div>
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white/75 px-4 py-2 text-sm font-semibold text-blue-700 shadow-sm backdrop-blur-xl">
              <Sparkles className="h-4 w-4" />
              新一代 AI 降重引擎
            </div>

            <h1 className="max-w-3xl text-[42px] font-black leading-[1.08] text-slate-950 sm:text-[64px]">
              让论文原创更简单
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
              GankAIGC 聚焦论文降 AI、学术润色与原创性增强，支持账号登录、邀请码注册、兑换码充值次数和自带 API 使用。
            </p>

            <div className="mt-7 flex flex-wrap gap-5 text-sm font-semibold text-slate-600">
              {['智能降重', '语义保持', '安全可靠'].map((item) => (
                <span key={item} className="inline-flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-teal-500" />
                  {item}
                </span>
              ))}
            </div>

            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <button
                type="button"
                onClick={() => goTo('/login')}
                className="gank-primary-button inline-flex min-h-[52px] items-center justify-center gap-2 rounded-xl px-8 text-base font-bold transition active:scale-[0.98]"
              >
                开始使用
                <ArrowRight className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={() => goTo('/register')}
                className="gank-secondary-button inline-flex min-h-[52px] items-center justify-center gap-2 rounded-xl px-8 text-base font-bold transition hover:-translate-y-0.5 active:scale-[0.98]"
              >
                <UserPlus className="h-5 w-5 text-blue-600" />
                邀请码注册
              </button>
            </div>

            <div id="security" className="mt-8 flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-blue-600" />
                账号隔离
              </span>
              <span>隐私严格保护</span>
              <span>平台次数与自带 API 双模式</span>
            </div>
          </div>

          <div className="relative min-h-[430px]">
            <div className="absolute inset-x-4 top-4 h-[360px] rounded-[2rem] border border-white/70 bg-white/45 shadow-[0_30px_90px_rgba(37,99,235,0.16)] backdrop-blur-2xl" />

            <div className="relative mx-auto max-w-[520px] rounded-[2rem] border border-white/80 bg-white/72 p-5 shadow-[0_34px_90px_rgba(15,23,42,0.14)] backdrop-blur-2xl">
              <div className="mb-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-blue-600 text-xl font-black text-white shadow-lg">
                    AI
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-950">论文原创性工作台</p>
                    <p className="text-xs text-slate-500">润色与增强处理中</p>
                  </div>
                </div>
                <div className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                  运行中
                </div>
              </div>

              <div className="space-y-3 rounded-[1.35rem] bg-white/80 p-5">
                <div className="h-4 w-2/3 rounded-full bg-slate-200" />
                <div className="h-3 w-full rounded-full bg-blue-100" />
                <div className="h-3 w-11/12 rounded-full bg-blue-100" />
                <div className="h-3 w-4/5 rounded-full bg-blue-100" />
                <div className="my-4 h-px bg-slate-100" />
                <div className="h-3 w-full rounded-full bg-teal-100" />
                <div className="h-3 w-10/12 rounded-full bg-teal-100" />
                <div className="h-3 w-8/12 rounded-full bg-teal-100" />
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-blue-100 bg-white/80 p-4 shadow-sm">
                  <p className="text-xs font-semibold text-slate-500">示例降幅</p>
                  <p className="mt-2 text-3xl font-black text-slate-950">68%</p>
                </div>
                <div className="rounded-2xl border border-emerald-100 bg-white/80 p-4 shadow-sm">
                  <p className="text-xs font-semibold text-slate-500">表达自然度</p>
                  <p className="mt-2 text-3xl font-black text-slate-950">提升</p>
                </div>
              </div>
            </div>

            <div className="absolute -left-2 top-24 hidden rounded-2xl border border-white/80 bg-white/75 px-5 py-4 shadow-xl backdrop-blur-xl sm:block">
              <p className="text-xs font-semibold text-slate-500">示例降幅</p>
              <p className="mt-1 text-2xl font-black text-slate-950">68%</p>
            </div>

            <div className="absolute -right-1 bottom-20 hidden rounded-2xl border border-white/80 bg-white/75 px-5 py-4 shadow-xl backdrop-blur-xl sm:block">
              <p className="text-xs font-semibold text-slate-500">安全准确</p>
              <p className="mt-1 text-2xl font-black text-slate-950">可控</p>
            </div>
          </div>
        </section>

        <section id="features" className="mt-14 grid gap-4 md:grid-cols-3">
          {featureCards.map(({ title, desc, icon: Icon, accent }) => (
            <div key={title} className="gank-glass-card rounded-2xl p-5">
              <div className={`mb-4 grid h-12 w-12 place-items-center rounded-2xl ${accent}`}>
                <Icon className="h-6 w-6" />
              </div>
              <h2 className="text-lg font-black text-slate-950">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{desc}</p>
            </div>
          ))}
        </section>

        <section id="scenarios" className="mt-6 grid gap-4 rounded-[1.75rem] border border-white/80 bg-white/70 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-2xl sm:grid-cols-2 lg:grid-cols-4">
          {scenarioCards.map(({ label, value }) => (
            <div key={label} className="rounded-2xl bg-white/70 p-5">
              <p className="text-sm font-semibold text-slate-500">{label}</p>
              <p className="mt-2 text-xl font-black text-slate-950">{value}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
};

export default WelcomePage;
