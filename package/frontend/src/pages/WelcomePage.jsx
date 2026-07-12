import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle,
  FileText,
  Github,
  KeyRound,
  LogIn,
  ShieldCheck,
  Sparkles,
  Star,
  UserPlus,
} from 'lucide-react';
import BrandLogo from '../components/BrandLogo';
import './WelcomePage.css';

const GITHUB_PROJECT_URL = 'https://github.com/mumu-0922/GankAIGC';

const capabilityCards = [
  {
    title: '检测与改写同屏',
    desc: '从朱雀检测到分段降重，少一次跳转，多一份上下文。',
    icon: Sparkles,
  },
  {
    title: '原文结果可对照',
    desc: '原文、风险片段和优化结果并排查看，改动清晰可复核。',
    icon: FileText,
  },
  {
    title: '处理记录可追溯',
    desc: '每轮结果自动保存，随时回看历史版本和任务进度。',
    icon: ShieldCheck,
  },
];

const workflowSteps = [
  {
    step: '01',
    title: '智能检测',
    desc: '先定位高风险表达，不对整篇论文盲目重写。',
  },
  {
    step: '02',
    title: '语义改写',
    desc: '保留术语、观点与论证结构，逐段降低机器感。',
  },
  {
    step: '03',
    title: '结果复核',
    desc: '对照原文与优化结果，再决定是否继续处理。',
  },
];

const trustItems = ['语义优先', '账号隔离', '按啤酒使用', '支持自带 API'];

const WelcomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="gank-app-page home-page text-[var(--apple-ink)]">
      <div className="home-ambient home-ambient-left" aria-hidden="true" />
      <div className="home-ambient home-ambient-right" aria-hidden="true" />
      <div className="home-ambient home-ambient-bottom" aria-hidden="true" />

      <a
        href="#home-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-full focus:bg-slate-950 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        跳到主要内容
      </a>

      <header className="home-header fixed inset-x-0 top-0 z-50 px-4 pt-4 sm:px-6">
        <nav className="home-nav home-glass mx-auto flex max-w-7xl items-center justify-between" aria-label="首页导航">
          <BrandLogo size="sm" />

          <div className="home-nav-links hidden items-center lg:flex">
            <a href="#features">产品能力</a>
            <a href="#workflow">工作流程</a>
            <a href="#security">安全与隐私</a>
            <a href={GITHUB_PROJECT_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/login')}
              aria-label="登录"
              className="home-nav-login inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold sm:px-4"
            >
              <LogIn className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">登录</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="home-primary-button inline-flex min-h-[42px] items-center justify-center gap-2 px-4 text-sm font-semibold sm:px-5"
            >
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              邀请码注册
            </button>
          </div>
        </nav>
      </header>

      <main id="home-main" className="relative z-[1]">
        <section className="home-hero mx-auto grid max-w-7xl items-center gap-12 px-5 sm:px-8 lg:grid-cols-[0.86fr_1.14fr] lg:gap-16">
          <div className="home-hero-copy">
            <div className="home-eyebrow inline-flex items-center gap-2">
              <span className="home-eyebrow-icon"><Sparkles className="h-4 w-4" aria-hidden="true" /></span>
              论文降 AI · 语义保持
            </div>

            <h1 className="home-title mt-7">
              论文表达更自然，
              <span>原意依然清晰。</span>
            </h1>

            <p className="home-hero-description mt-6">
              检测高风险表达，逐段优化机器感，并保留术语、观点与论证结构。每一步都能回看。
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="home-primary-button inline-flex min-h-[50px] items-center justify-center gap-2 px-7 text-sm font-semibold"
              >
                开始使用
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
              <a
                href="#workflow"
                className="home-secondary-button inline-flex min-h-[50px] items-center justify-center gap-2 px-7 text-sm font-semibold"
              >
                查看工作流
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>

            <div className="home-trust-list mt-7 flex flex-wrap gap-x-5 gap-y-3">
              {trustItems.map((item) => (
                <span key={item} className="inline-flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4" aria-hidden="true" />
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="home-preview-wrap" data-home-preview="workbench">
            <div className="home-preview-glow" aria-hidden="true" />
            <div className="home-preview home-glass">
              <div className="home-preview-toolbar">
                <div className="home-preview-dots" aria-hidden="true"><i /><i /><i /></div>
                <span>论文优化工作台</span>
                <span className="home-preview-status">AI检测 + 降重</span>
              </div>

              <div className="home-preview-body">
                <article className="home-document-card">
                  <div className="home-preview-card-head">
                    <span>原始文本</span>
                    <small>1,842 字</small>
                  </div>
                  <div className="home-document-lines" aria-hidden="true">
                    <i /><i /><i className="is-risk" /><i /><i className="is-risk is-short" /><i /><i className="is-shorter" />
                  </div>
                  <div className="home-document-footer">
                    <span>已识别 6 个高风险片段</span>
                    <strong>查看详情</strong>
                  </div>
                </article>

                <aside className="home-preview-side">
                  <div className="home-score-card">
                    <span>AI 风险率</span>
                    <strong>26<small>%</small></strong>
                    <div className="home-score-track" aria-hidden="true"><i /></div>
                    <p><span>优化前 78%</span><b>预计降低 52%</b></p>
                  </div>

                  <div className="home-preview-steps">
                    {workflowSteps.map(({ step, title }, index) => (
                      <React.Fragment key={step}>
                        <div className={`home-preview-step ${index < 2 ? 'is-active' : ''}`}>
                          <span>{step}</span>
                          <strong>{title}</strong>
                        </div>
                        {index < workflowSteps.length - 1 && <i className="home-preview-connector" aria-hidden="true" />}
                      </React.Fragment>
                    ))}
                  </div>
                </aside>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="home-section mx-auto max-w-7xl scroll-mt-28 px-5 sm:px-8" aria-labelledby="features-title">
          <div className="home-section-heading">
            <p className="home-section-kicker">产品能力</p>
            <h2 id="features-title">少一点包装，多一点可用。</h2>
            <p>核心能力围绕检测、改写与复核展开，不让首页变成功能目录。</p>
          </div>

          <div className="home-capability-grid mt-10">
            {capabilityCards.map(({ title, desc, icon: Icon }) => (
              <article key={title} className="home-capability-card">
                <span className="home-capability-icon"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                <h3>{title}</h3>
                <p>{desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="workflow" data-home-scenarios="workflow" className="home-section mx-auto max-w-7xl scroll-mt-28 px-5 sm:px-8" aria-labelledby="workflow-title">
          <div className="home-workflow-shell">
            <div className="home-section-heading max-w-xl">
              <p className="home-section-kicker">论文处理链路</p>
              <h2 id="workflow-title">从检测到复核，只保留三步。</h2>
              <p>先看清问题，再稳定改写，最后由你决定是否采用。</p>
            </div>

            <div className="home-workflow-grid">
              {workflowSteps.map(({ step, title, desc }, index) => (
                <article key={step} className="home-workflow-card">
                  <div className="home-workflow-number">{step}</div>
                  <div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                  </div>
                  {index < workflowSteps.length - 1 && <ArrowRight className="home-workflow-arrow" aria-hidden="true" />}
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="home-section mx-auto max-w-7xl scroll-mt-28 px-5 sm:px-8" aria-labelledby="security-title">
          <div className="home-security-shell">
            <div className="home-security-icon"><KeyRound className="h-6 w-6" aria-hidden="true" /></div>
            <div>
              <p className="home-section-kicker">使用边界</p>
              <h2 id="security-title">平台啤酒与自带 API，按你的方式使用。</h2>
              <p>登录后查看个人项目和处理记录；平台模式按啤酒使用，也可以配置自己的 OpenAI-compatible API。</p>
            </div>
            <button type="button" onClick={() => navigate('/login')} className="home-secondary-button inline-flex min-h-[46px] items-center justify-center gap-2 px-6 text-sm font-semibold">
              进入工作台
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </section>

        <section data-home-github-star="footer" className="home-section mx-auto max-w-7xl px-5 pb-20 sm:px-8">
          <div className="home-github-card">
            <div className="flex items-start gap-4">
              <span className="home-capability-icon"><Github className="h-5 w-5" aria-hidden="true" /></span>
              <div>
                <p className="home-section-kicker">GitHub 项目</p>
                <h2>持续迭代，欢迎留下具体反馈。</h2>
                <p>觉得项目有用，可以点个 Star；问题描述越具体，下一次改进越准确。</p>
              </div>
            </div>
            <a
              href={GITHUB_PROJECT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="home-secondary-button inline-flex min-h-[46px] items-center justify-center gap-2 px-6 text-sm font-semibold"
              aria-label="打开项目仓库并求 Star"
            >
              <Star className="h-4 w-4 fill-[#f5b700] text-[#f5b700]" aria-hidden="true" />
              求 Star
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
        </section>
      </main>
    </div>
  );
};

export default WelcomePage;
