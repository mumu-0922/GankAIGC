import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
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
  {
    step: '阶段 01',
    label: '初稿降 AI',
    value: '润色 + 增强',
    desc: '先处理明显机器感表达，保留论文原有结构',
    icon: Sparkles,
    iconTone: 'bg-rose-500 text-white shadow-rose-500/25',
    stripe: 'from-rose-400 to-blue-500',
    panel: 'from-rose-50/90 via-white/90 to-blue-50/80',
  },
  {
    step: '阶段 02',
    label: '二稿优化',
    value: '语义更自然',
    desc: '调整句式节奏，让表达更贴近人工写作习惯',
    icon: FileText,
    iconTone: 'bg-blue-600 text-white shadow-blue-500/25',
    stripe: 'from-blue-500 to-cyan-400',
    panel: 'from-blue-50/90 via-white/90 to-cyan-50/80',
  },
  {
    step: '阶段 03',
    label: '投稿前检查',
    value: '保留处理记录',
    desc: '按论文维度归档，方便复查每次处理结果',
    icon: ShieldCheck,
    iconTone: 'bg-teal-500 text-white shadow-teal-500/25',
    stripe: 'from-teal-400 to-emerald-400',
    panel: 'from-teal-50/90 via-white/90 to-emerald-50/80',
  },
  {
    step: '阶段 04',
    label: '自带 API',
    value: '不消耗平台次数',
    desc: '有自有模型额度时，可切换为自带 API 模式',
    icon: KeyRound,
    iconTone: 'bg-violet-500 text-white shadow-violet-500/25',
    stripe: 'from-violet-500 to-blue-500',
    panel: 'from-violet-50/90 via-white/90 to-blue-50/80',
  },
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

          <div className="relative min-h-[430px] lg:min-h-[460px]">
            <div className="absolute inset-0 rounded-[2.25rem] border border-white/70 bg-[radial-gradient(circle_at_20%_18%,rgba(244,63,94,0.18),transparent_30%),radial-gradient(circle_at_84%_18%,rgba(37,99,235,0.2),transparent_32%),linear-gradient(135deg,rgba(255,255,255,0.86),rgba(239,246,255,0.78))] shadow-[0_30px_90px_rgba(37,99,235,0.14)] backdrop-blur-2xl" />

            <div className="relative mx-auto flex max-w-[660px] flex-col gap-5 rounded-[2rem] border border-white/80 bg-white/60 p-4 shadow-[0_34px_90px_rgba(15,23,42,0.12)] backdrop-blur-2xl sm:p-6">
              <div className="grid items-center gap-4 sm:grid-cols-[1fr_auto_1fr]">
                <div className="space-y-4">
                  <div className="mx-auto w-fit rounded-full bg-rose-500 px-5 py-2 text-sm font-black text-white shadow-[0_12px_24px_rgba(244,63,94,0.24)]">
                    优化前
                  </div>

                  <div className="rounded-[1.35rem] border border-rose-100 bg-white/90 p-4 shadow-[0_18px_40px_rgba(244,63,94,0.14)]">
                    <div className="mb-4 flex items-start gap-3">
                      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-rose-500 text-xl font-black text-white shadow-lg">
                        AI
                      </div>
                      <div className="flex-1 space-y-2 pt-1">
                        <div className="h-2.5 w-5/6 rounded-full bg-slate-200" />
                        <div className="h-2.5 w-2/3 rounded-full bg-slate-200" />
                      </div>
                    </div>
                    <div className="space-y-2.5">
                      <div className="h-2.5 w-full rounded-full bg-slate-200" />
                      <div className="h-2.5 w-4/5 rounded-full bg-rose-200" />
                      <div className="h-2.5 w-11/12 rounded-full bg-slate-200" />
                      <div className="h-2.5 w-3/4 rounded-full bg-rose-200" />
                      <div className="h-2.5 w-full rounded-full bg-slate-200" />
                    </div>
                    <div className="mt-4 flex items-center justify-between rounded-xl border border-rose-100 bg-white/95 p-3">
                      <div>
                        <p className="text-xs font-semibold text-slate-500">AI 率检测结果</p>
                        <p className="mt-1 text-3xl font-black text-rose-500">99%</p>
                      </div>
                      <div
                        className="h-14 w-14 rounded-full p-1"
                        style={{ background: 'conic-gradient(#fb3f61 0 80%, #fee2e2 80% 100%)' }}
                      >
                        <div className="h-full w-full rounded-full bg-white" />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-center py-1 sm:pt-10">
                  <div className="flex items-center gap-1 text-violet-400">
                    <span className="h-2 w-2 rounded-full bg-rose-200" />
                    <span className="h-3 w-3 rounded-sm bg-rose-300" />
                    <span className="h-4 w-4 rounded-sm bg-violet-300" />
                    <ArrowRight className="h-10 w-10 text-violet-500 drop-shadow-[0_8px_18px_rgba(124,58,237,0.28)] sm:h-14 sm:w-14" />
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="mx-auto w-fit rounded-full bg-blue-600 px-5 py-2 text-sm font-black text-white shadow-[0_12px_24px_rgba(37,99,235,0.24)]">
                    优化后
                  </div>

                  <div className="rounded-[1.35rem] border border-blue-100 bg-white/90 p-4 shadow-[0_18px_40px_rgba(37,99,235,0.16)]">
                    <div className="mb-4 flex items-start gap-3">
                      <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-blue-600 text-xl font-black text-white shadow-lg">
                        AI
                      </div>
                      <div className="flex-1 space-y-2 pt-1">
                        <div className="h-2.5 w-5/6 rounded-full bg-slate-200" />
                        <div className="h-2.5 w-2/3 rounded-full bg-slate-200" />
                      </div>
                    </div>
                    <div className="space-y-2.5">
                      <div className="h-2.5 w-full rounded-full bg-slate-200" />
                      <div className="h-2.5 w-4/5 rounded-full bg-blue-200" />
                      <div className="h-2.5 w-11/12 rounded-full bg-slate-200" />
                      <div className="h-2.5 w-3/4 rounded-full bg-blue-200" />
                      <div className="h-2.5 w-full rounded-full bg-slate-200" />
                    </div>
                    <div className="mt-4 flex items-center justify-between rounded-xl border border-blue-100 bg-white/95 p-3">
                      <div>
                        <p className="text-xs font-semibold text-slate-500">AI 率检测结果</p>
                        <p className="mt-1 text-3xl font-black text-blue-600">0%</p>
                      </div>
                      <div
                        className="h-14 w-14 rounded-full p-1"
                        style={{ background: 'conic-gradient(#2563eb 0 6%, #e5e7eb 6% 100%)' }}
                      >
                        <div className="h-full w-full rounded-full bg-white" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="inline-flex items-center justify-center gap-2 rounded-full bg-rose-50 px-4 py-3 text-sm font-bold text-rose-600">
                  <AlertTriangle className="h-4 w-4" />
                  内容疑似由 AI 生成，建议优化处理
                </div>
                <div className="inline-flex items-center justify-center gap-2 rounded-full bg-blue-50 px-4 py-3 text-sm font-bold text-blue-600">
                  <ShieldCheck className="h-4 w-4" />
                  原创性高，AI 痕迹低，更安全可靠
                </div>
              </div>
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

        <section id="scenarios" data-home-scenarios="workflow" className="mt-8">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-bold text-blue-600">论文处理链路</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">从初稿到投稿前的四步优化</h2>
            </div>
            <div className="w-fit rounded-full border border-white/80 bg-white/70 px-4 py-2 text-sm font-bold text-slate-600 shadow-sm backdrop-blur-xl">
              账号次数与自带 API 双模式
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {scenarioCards.map(({ step, label, value, desc, icon: Icon, iconTone, stripe, panel }) => (
              <article
                key={label}
                className={`group relative min-h-[220px] overflow-hidden rounded-[1.5rem] border border-white/80 bg-gradient-to-br ${panel} p-5 shadow-[0_18px_48px_rgba(15,23,42,0.09)] backdrop-blur-2xl transition hover:-translate-y-0.5 hover:shadow-[0_24px_60px_rgba(15,23,42,0.13)]`}
              >
                <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${stripe}`} />
                <div className="flex items-start justify-between gap-3">
                  <div className={`grid h-12 w-12 place-items-center rounded-2xl shadow-lg ${iconTone}`}>
                    <Icon className="h-6 w-6" />
                  </div>
                  <span className="rounded-full border border-white/80 bg-white/75 px-3 py-1 text-xs font-black text-slate-500 shadow-sm">
                    {step}
                  </span>
                </div>

                <p className="mt-6 text-sm font-bold text-slate-500">{label}</p>
                <h3 className="mt-2 text-2xl font-black text-slate-950">{value}</h3>
                <p className="mt-4 text-sm leading-6 text-slate-600">{desc}</p>

                <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/70">
                  <div className={`h-full w-2/3 rounded-full bg-gradient-to-r ${stripe}`} />
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};

export default WelcomePage;
