import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ArrowLeft, Coins } from 'lucide-react';
import { userAPI } from '../api';
import BrandLogo from '../components/BrandLogo';
import { formatChinaDateTime } from '../utils/dateTime';

const CreditsPage = () => {
  const [credits, setCredits] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [code, setCode] = useState('');

  const loadData = async () => {
    const [creditResponse, transactionResponse] = await Promise.all([
      userAPI.getCredits(),
      userAPI.listCreditTransactions(),
    ]);
    setCredits(creditResponse.data);
    setTransactions(transactionResponse.data);
  };

  useEffect(() => {
    loadData().catch((error) => {
      console.error('加载额度数据失败:', error);
      toast.error('加载额度数据失败');
    });
  }, []);

  const handleRedeem = async (event) => {
    event.preventDefault();
    if (!code.trim()) return;

    try {
      await userAPI.redeemCode(code.trim());
      setCode('');
      toast.success('兑换成功');
      await loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || '兑换失败');
    }
  };

  return (
    <div className="gank-app-page">
      <header className="gank-glass-toolbar sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <BrandLogo size="sm" />
          <Link to="/workspace" className="inline-flex items-center gap-2 text-slate-500 hover:text-slate-900 text-sm font-semibold">
            <ArrowLeft className="w-4 h-4" />
            返回工作台
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="mb-6">
          <p className="text-sm font-semibold text-teal-600">兑换额度</p>
          <h1 className="text-3xl font-bold text-slate-950 mt-1">平台处理额度</h1>
        </div>
        <div className="grid lg:grid-cols-[0.85fr_1.15fr] gap-6">
          <section className="gank-glass-card rounded-[2rem] p-6">
            <div className="gank-icon-tile w-12 h-12 rounded-2xl flex items-center justify-center mb-4">
              <Coins className="w-6 h-6" />
            </div>
            <p className="text-slate-500 text-sm">当前剩余额度</p>
            <h1 className="text-5xl font-black text-slate-950 mt-2">
              {credits?.is_unlimited ? '无限' : credits?.credit_balance ?? '-'}
            </h1>

            <form onSubmit={handleRedeem} className="mt-6 space-y-3">
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="输入兑换码"
                className="gank-input px-4 py-3 rounded-2xl"
              />
              <button className="gank-primary-button w-full py-3 rounded-2xl text-white font-semibold">
                兑换额度
              </button>
            </form>
          </section>

          <section className="gank-card rounded-[2rem] p-6">
            <h2 className="text-xl font-bold text-slate-950 mb-4">额度流水</h2>
            <div className="space-y-3">
              {transactions.length === 0 && (
                <p className="text-slate-500 text-sm">暂无流水记录</p>
              )}
              {transactions.map((transaction) => (
                <div key={transaction.id} className="flex items-center justify-between rounded-2xl bg-slate-50 px-4 py-3">
                  <div>
                    <p className="font-semibold text-slate-900">{transaction.reason}</p>
                    <p className="text-xs text-slate-500">{formatChinaDateTime(transaction.created_at)}</p>
                  </div>
                  <div className={transaction.delta >= 0 ? 'text-emerald-600 font-bold' : 'text-red-600 font-bold'}>
                    {transaction.delta > 0 ? '+' : ''}{transaction.delta}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default CreditsPage;
