import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Shield, UserPlus } from 'lucide-react';
import BrandLogo from '../components/BrandLogo';

const WelcomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="gank-auth-page px-5 py-5 sm:px-8 sm:py-7">
      <header className="gank-glass-toolbar rounded-[1.75rem] px-5 py-4 flex items-center justify-between max-w-7xl mx-auto">
        <BrandLogo size="sm" />
      </header>

      <main className="max-w-7xl mx-auto pt-20 pb-8">
        <section className="grid lg:grid-cols-[1.05fr_0.95fr] gap-10 items-center">
          <div>
            <h1 className="text-5xl sm:text-7xl font-black text-slate-950 leading-none">
              GankAIGC
            </h1>
            <p className="mt-6 text-xl sm:text-2xl text-slate-700 leading-relaxed max-w-3xl">
              论文降 AI、润色、格式检测与 Word 排版的一体化工作台
            </p>
          </div>

          <div className="gank-terminal rounded-[2rem] overflow-hidden">
            <div className="h-14 bg-slate-800/90 flex items-center justify-between px-6">
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded-full bg-red-400" />
                <span className="w-3.5 h-3.5 rounded-full bg-amber-300" />
                <span className="w-3.5 h-3.5 rounded-full bg-emerald-400" />
              </div>
              <span className="font-mono text-sm text-slate-400">workflow</span>
            </div>
            <div className="p-8 sm:p-10 font-mono text-base sm:text-lg leading-9">
              <p className="text-slate-400"><span className="text-teal-300">$</span> upload paper.docx</p>
              <p className="text-slate-400"><span className="text-teal-300">#</span> polish + reduce AI rate...</p>
              <p className="text-emerald-400">200 OK <span className="text-amber-300">{'{ "credits": 23 }'}</span></p>
            </div>
          </div>
        </section>

        <section className="mt-16 grid gap-5 md:grid-cols-3">
          {[
            { title: '账号登录', icon: LogIn, path: '/login' },
            { title: '邀请码注册', icon: UserPlus, path: '/register' },
            { title: '管理后台', icon: Shield, path: '/admin' },
          ].map(({ title, icon: Icon, path }) => (
            <button
              key={title}
              onClick={() => navigate(path)}
              className="gank-glass-card rounded-[1.5rem] px-6 py-5 flex items-center justify-center gap-3 font-bold text-slate-800 transition-all hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <Icon className="w-5 h-5 text-teal-600" />
              {title}
            </button>
          ))}
        </section>
      </main>
    </div>
  );
};

export default WelcomePage;
