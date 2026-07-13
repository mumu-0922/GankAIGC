import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  Github,
  LogIn,
} from 'lucide-react';
import BrandLogo from '../components/BrandLogo';
import './WelcomePage.css';

const GITHUB_PROJECT_URL = 'https://github.com/mumu-0922/GankAIGC';

const capabilityCards = [
  {
    number: '01',
    title: '定位风险段落',
    desc: '连接朱雀检测结果，先找到需要处理的表达，不盲目重写全文。',
  },
  {
    number: '02',
    title: '保留原意改写',
    desc: '按段处理并保留术语、观点与论证关系，减少不必要的语义漂移。',
  },
  {
    number: '03',
    title: '对照结果复核',
    desc: '原文、风险片段和优化结果放在同一条处理记录里，随时回看。',
  },
];

const workflowSteps = [
  {
    step: '01',
    title: '智能检测',
    desc: '读取检测结果，标出高风险表达。',
  },
  {
    step: '02',
    title: '语义改写',
    desc: '逐段优化措辞，保持论文原意。',
  },
  {
    step: '03',
    title: '结果复核',
    desc: '对照前后内容，再决定是否采用。',
  },
];

const WelcomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="gank-app-page home-page text-[var(--apple-ink)]">
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
            <a href="#features">产品能力</a>
            <a href="#workflow">工作流程</a>
            <a href="#security">使用方式</a>
            <a href={GITHUB_PROJECT_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>

          <div className="flex items-center gap-1 sm:gap-2">
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
        <section className="home-hero px-5 sm:px-8">
          <div className="home-hero-copy mx-auto text-center">
            <p className="home-eyebrow">GankAIGC · 论文降 AI</p>
            <h1 className="home-title">
              论文表达更自然，
              <span>原意依然清晰。</span>
            </h1>
            <p className="home-hero-description mx-auto">
              从朱雀检测到逐段改写，在一个工作台完成。原文和结果始终可以对照。
            </p>

            <div className="home-hero-actions flex flex-wrap items-center justify-center">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="home-primary-button inline-flex min-h-[46px] items-center justify-center gap-2 px-6 text-sm font-medium"
              >
                开始使用
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
              <a href="#workflow" className="home-text-link inline-flex items-center gap-1.5 text-sm font-medium">
                了解工作流程
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </div>

          <div className="home-product-stage mx-auto" data-home-preview="workbench">
            <div className="home-stage-halo" aria-hidden="true" />
            <div className="home-preview home-glass">
              <div className="home-preview-toolbar">
                <div className="home-preview-dots" aria-hidden="true"><i /><i /><i /></div>
                <span>论文优化工作台</span>
                <span className="home-preview-status"><i aria-hidden="true" /> 检测完成</span>
              </div>

              <div className="home-preview-body">
                <article className="home-document-card">
                  <div className="home-preview-card-head">
                    <div>
                      <small>原始文本</small>
                      <strong>研究方法与实验设计</strong>
                    </div>
                    <span>1,842 字</span>
                  </div>

                  <div className="home-document-copy" aria-label="论文风险片段示意">
                    <p>本研究围绕生成式内容检测场景展开，通过对不同表达方式进行对照，分析文本特征变化。</p>
                    <p className="is-risk">研究结果表明，该方法能够在一定程度上提升文本表达的自然度。</p>
                    <p>实验过程保留原始观点和关键术语，并对处理前后的内容进行逐段核验。</p>
                    <p className="is-risk is-short">因此，本文进一步讨论了语义保持与表达调整之间的关系。</p>
                  </div>

                  <div className="home-document-footer">
                    <span><i aria-hidden="true" /> 识别到 6 个风险片段</span>
                    <strong>查看检测详情 <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" /></strong>
                  </div>
                </article>

                <aside className="home-preview-side">
                  <div className="home-score-card">
                    <div className="home-score-label"><span>AI 风险率</span><small>朱雀</small></div>
                    <strong>26<small>%</small></strong>
                    <div className="home-score-track" aria-hidden="true"><i /></div>
                    <p><span>处理前 78%</span><b>下降 52%</b></p>
                  </div>

                  <div className="home-preview-steps">
                    {workflowSteps.map(({ step, title }, index) => (
                      <div key={step} className={`home-preview-step ${index < 2 ? 'is-complete' : 'is-current'}`}>
                        <span>{index < 2 ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : step}</span>
                        <strong>{title}</strong>
                      </div>
                    ))}
                  </div>
                </aside>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="home-feature-band scroll-mt-20" aria-labelledby="features-title">
          <div className="home-content mx-auto px-5 sm:px-8">
            <div className="home-section-heading mx-auto text-center">
              <p className="home-section-kicker">产品能力</p>
              <h2 id="features-title">先看清问题，再处理表达。</h2>
              <p>不追求一次生成整篇新文章，只处理真正需要调整的部分。</p>
            </div>

            <div className="home-capability-grid">
              {capabilityCards.map(({ number, title, desc }) => (
                <article key={number} className="home-capability-item">
                  <span>{number}</span>
                  <h3>{title}</h3>
                  <p>{desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" data-home-scenarios="workflow" className="home-workflow-section scroll-mt-20 px-5 sm:px-8" aria-labelledby="workflow-title">
          <div className="home-workflow-stage mx-auto">
            <div className="home-workflow-heading">
              <p className="home-section-kicker">论文处理链路</p>
              <h2 id="workflow-title">从检测到复核，只保留三步。</h2>
              <p>每一步都有明确输入和结果，不用在多个页面之间来回切换。</p>
            </div>

            <div className="home-workflow-list">
              {workflowSteps.map(({ step, title, desc }) => (
                <article key={step} className="home-workflow-row">
                  <span>{step}</span>
                  <h3>{title}</h3>
                  <p>{desc}</p>
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="home-use-section scroll-mt-20 px-5 sm:px-8" aria-labelledby="security-title">
          <div className="home-use-layout mx-auto">
            <div>
              <p className="home-section-kicker">使用方式</p>
              <h2 id="security-title">平台次数，或自带 API。</h2>
            </div>
            <div className="home-use-copy">
              <p>登录后按啤酒使用平台能力，同时支持自带 API，兼容 OpenAI-compatible 接口。项目、任务和处理记录按账号隔离保存。</p>
              <button type="button" onClick={() => navigate('/login')} className="home-text-link inline-flex items-center gap-1.5 text-sm font-medium">
                进入工作台
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        </section>

        <section data-home-github-star="footer" className="home-github-section px-5 sm:px-8">
          <div className="home-github-row mx-auto">
            <div>
              <p className="home-section-kicker">GitHub 项目</p>
              <h2>开放迭代，欢迎留下具体反馈。</h2>
            </div>
            <a
              href={GITHUB_PROJECT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="home-github-link inline-flex items-center gap-2 text-sm font-medium"
              aria-label="打开项目仓库并求 Star"
            >
              <Github className="h-4 w-4" aria-hidden="true" />
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
