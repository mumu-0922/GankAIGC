import React, { useState } from 'react';
import { ArrowRight, Check, Github, LogIn } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import BrandLogo from '../components/BrandLogo';
import './WelcomePage.css';

const GITHUB_PROJECT_URL = 'https://github.com/mumu-0922/GankAIGC';

const paperParagraphs = [
  {
    original: '随着生成式人工智能的快速发展，其在文本创作领域的应用日益广泛。',
    revised: '生成式人工智能正逐渐进入文本创作流程，并改变内容的生产方式。',
    risk: true,
  },
  {
    original: '本文以论文表达为研究对象，分析不同处理方式对语义结构的影响。',
    revised: '本文以论文表达为研究对象，分析不同处理方式对语义结构的影响。',
    risk: false,
  },
  {
    original: '研究结果表明，该方法能够有效提高文本质量，具有重要的现实意义。',
    revised: '实验结果显示，该方法改善了部分表达；其适用范围仍需结合具体文本判断。',
    risk: true,
  },
  {
    original: '处理过程保留原有术语、观点和论证关系，并提供前后版本用于复核。',
    revised: '处理过程保留原有术语、观点和论证关系，并提供前后版本用于复核。',
    risk: false,
  },
];

const capabilityRows = [
  {
    title: '只动需要处理的段落',
    desc: '检测结果直接落到正文，高风险表达逐段处理，不把整篇论文重新生成一遍。',
  },
  {
    title: '原文永远在旁边',
    desc: '每次修改都能前后对照。术语有没有变化、论点有没有偏移，一眼就能核对。',
  },
  {
    title: '过程不会在刷新后消失',
    desc: '项目、任务和处理记录按账号保存，回来时仍能接着上一次的结果继续。',
  },
];

const workflowSteps = [
  {
    step: '01',
    title: '智能检测',
    desc: '读取朱雀结果，定位需要复核的表达。',
  },
  {
    step: '02',
    title: '语义改写',
    desc: '逐段调整措辞，保留术语和论证关系。',
  },
  {
    step: '03',
    title: '结果复核',
    desc: '对照原文确认修改，再决定是否采用。',
  },
];

const WelcomePage = () => {
  const navigate = useNavigate();
  const [previewMode, setPreviewMode] = useState('detect');

  return (
    <div className="gank-app-page home-page">
      <a
        href="#home-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-full focus:bg-black focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        跳到主要内容
      </a>

      <header className="home-header home-glass fixed inset-x-0 top-0 z-50">
        <nav className="home-nav mx-auto flex items-center justify-between px-5 sm:px-8" aria-label="首页导航">
          <BrandLogo size="sm" />

          <div className="home-nav-links hidden items-center md:flex">
            <a href="#features">为什么这样处理</a>
            <a href="#workflow">处理流程</a>
            <a href="#security">使用方式</a>
            <a href={GITHUB_PROJECT_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => navigate('/login')}
              aria-label="登录"
              className="home-nav-login inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium"
            >
              <LogIn className="h-4 w-4 sm:hidden" aria-hidden="true" />
              <span className="hidden sm:inline">登录</span>
            </button>
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="home-nav-register rounded-full px-4 py-2 text-sm font-medium"
            >
              邀请码注册
            </button>
          </div>
        </nav>
      </header>

      <main id="home-main">
        <section className="home-hero mx-auto grid items-center px-5 sm:px-8">
          <div className="home-hero-copy">
            <p className="home-overline">GankAIGC · 论文表达工作台</p>
            <h1 className="home-title">
              保留你的论点。
              <span>只调整机器味。</span>
            </h1>
            <p className="home-hero-description">
              从朱雀检测结果出发，逐段处理高风险表达。术语、观点和论证结构，始终由你掌控。
            </p>

            <div className="home-hero-actions flex flex-wrap items-center">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="home-primary-button inline-flex min-h-[48px] items-center justify-center gap-2 px-6 text-sm font-medium"
              >
                打开工作台
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
              <a href="#workflow" className="home-text-link inline-flex items-center gap-1.5 text-sm font-medium">
                先看处理流程
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>

            <p className="home-hero-footnote">朱雀检测 · 分段改写 · 原文对照</p>
          </div>

          <div className="home-demo" data-home-preview="workbench">
            <div className="home-demo-mat" aria-hidden="true" />

            <article className="home-paper" data-view={previewMode} aria-label="论文检测与改写预览">
              <div className="home-paper-meta">
                <span>论文正文</span>
                <span>第 3 页 / 共 12 页</span>
              </div>
              <h2>生成式内容检测与论文表达研究</h2>
              <p className="home-paper-author">研究方法与实验设计</p>

              <div className="home-paper-copy">
                {paperParagraphs.map(({ original, revised, risk }, index) => (
                  <div key={original} className={`home-paper-paragraph ${risk ? 'is-risk' : ''}`}>
                    <span className="home-paragraph-index">{String(index + 1).padStart(2, '0')}</span>
                    <p>
                      <span className="home-copy-original">{original}</span>
                      <span className="home-copy-revised">{revised}</span>
                    </p>
                    {risk && <span className="home-margin-mark">需复核</span>}
                  </div>
                ))}
              </div>

              <div className="home-paper-footer">
                <span>原文始终保留</span>
                <span>自动保存</span>
              </div>
            </article>

            <aside className="home-review-panel home-glass" aria-label="稿件审阅控制">
              <div className="home-review-head">
                <div>
                  <span>校阅台</span>
                  <strong>{previewMode === 'detect' ? '发现 2 处高风险表达' : '2 处建议等待确认'}</strong>
                </div>
                <i aria-hidden="true" />
              </div>

              <div className="home-preview-switch" role="group" aria-label="预览模式">
                <button
                  type="button"
                  aria-pressed={previewMode === 'detect'}
                  onClick={() => setPreviewMode('detect')}
                >
                  检测视图
                </button>
                <button
                  type="button"
                  aria-pressed={previewMode === 'rewrite'}
                  onClick={() => setPreviewMode('rewrite')}
                >
                  改写视图
                </button>
              </div>

              <div className="home-review-score">
                <span>{previewMode === 'detect' ? 'AI 风险率' : '语义保持'}</span>
                <strong>{previewMode === 'detect' ? '78%' : '待复核'}</strong>
                <div aria-hidden="true"><i /></div>
              </div>

              <div className="home-review-list">
                {workflowSteps.map(({ step, title }, index) => (
                  <div key={step} className={previewMode === 'rewrite' || index === 0 ? 'is-done' : ''}>
                    <span>{previewMode === 'rewrite' || index === 0 ? <Check className="h-3 w-3" aria-hidden="true" /> : step}</span>
                    <strong>{title}</strong>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </section>

        <section id="features" className="home-feature-section scroll-mt-20 px-5 sm:px-8" aria-labelledby="features-title">
          <div className="home-section-layout mx-auto">
            <div className="home-section-intro">
              <p className="home-overline">不是整篇重写</p>
              <h2 id="features-title">先指出问题，再给出修改。</h2>
              <p>论文不是一段 Prompt。处理从具体段落开始，也应该回到具体段落结束。</p>
            </div>

            <div className="home-capability-list">
              {capabilityRows.map(({ title, desc }) => (
                <article key={title} className="home-capability-row">
                  <div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" data-home-scenarios="workflow" className="home-workflow-section scroll-mt-20 px-5 sm:px-8" aria-labelledby="workflow-title">
          <div className="home-workflow-shell mx-auto">
            <div className="home-workflow-heading">
              <p className="home-overline">一条处理链路</p>
              <h2 id="workflow-title">从检测到采用，每一步都看得见。</h2>
              <p>没有黑箱式的一键重写。你可以停在任何一步，检查后再继续。</p>
            </div>

            <div className="home-workflow-track">
              {workflowSteps.map(({ step, title, desc }) => (
                <article key={step} className="home-workflow-step">
                  <div className="home-step-marker"><span>{step}</span><i aria-hidden="true" /></div>
                  <h3>{title}</h3>
                  <p>{desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="home-access-section scroll-mt-20 px-5 sm:px-8" aria-labelledby="security-title">
          <div className="home-access-layout mx-auto">
            <div className="home-access-heading">
              <p className="home-overline">使用方式</p>
              <h2 id="security-title">用平台次数，或者连接你的 API。</h2>
            </div>

            <div className="home-access-options">
              <div>
                <strong>平台模式</strong>
                <p>按啤酒使用，登录后查看余量、项目和全部处理记录。</p>
              </div>
              <div>
                <strong>自带 API</strong>
                <p>支持自带 API，兼容 OpenAI-compatible 接口，配置由账号独立保存。</p>
              </div>
              <button type="button" onClick={() => navigate('/login')} className="home-text-link inline-flex items-center gap-1.5 text-sm font-medium">
                进入工作台
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        </section>

        <footer data-home-github-star="footer" className="home-footer px-5 sm:px-8">
          <div className="home-footer-row mx-auto">
            <div>
              <BrandLogo size="sm" />
              <p>把问题讲清楚，比一句“再优化一下”更有用。</p>
            </div>
            <a
              href={GITHUB_PROJECT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="home-github-link inline-flex items-center gap-2 text-sm font-medium"
              aria-label="打开项目仓库并求 Star"
            >
              <Github className="h-4 w-4" aria-hidden="true" />
              GitHub 项目 · 求 Star
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
        </footer>
      </main>
    </div>
  );
};

export default WelcomePage;
