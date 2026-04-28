import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Coins, KeyRound, LogOut, UserCircle } from 'lucide-react';
import { authAPI } from '../api';

const UserMenu = ({ credits }) => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    let isMounted = true;

    authAPI.me()
      .then((response) => {
        if (isMounted) {
          setProfile(response.data);
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('userToken');
    navigate('/login');
  };

  return (
    <div className="flex items-center gap-2">
      {credits && (
        <div
          aria-label="剩余额度"
          className="hidden sm:flex items-center gap-1.5 gank-topbar-pill text-slate-700 px-3 py-1.5 rounded-xl text-sm font-semibold"
        >
          <Coins className="w-4 h-4 text-teal-600" />
          {credits.is_unlimited ? '无限额度' : `${credits.credit_balance} 千字额度`}
        </div>
      )}
      <Link
        to="/profile"
        className="hidden md:flex items-center gap-1.5 gank-topbar-pill text-slate-700 px-3 py-1.5 rounded-xl text-sm font-medium transition-colors hover:text-slate-950"
      >
        <UserCircle className="w-4 h-4" />
        {profile?.nickname || profile?.username || '个人信息'}
      </Link>
      <Link
        to="/credits"
        className="flex items-center gap-1.5 gank-primary-button px-3 py-1.5 rounded-xl text-sm font-semibold transition-colors"
      >
        <Coins className="w-4 h-4" />
        兑换额度
      </Link>
      <Link
        to="/api-settings"
        className="hidden sm:flex items-center gap-1.5 gank-topbar-pill text-slate-700 px-3 py-1.5 rounded-xl text-sm font-medium hover:text-slate-950"
      >
        <KeyRound className="w-4 h-4" />
        API
      </Link>
      <button
        onClick={handleLogout}
        className="flex items-center gap-1.5 text-ios-red text-sm font-medium px-2 py-1.5 hover:opacity-70 transition-opacity"
      >
        <LogOut className="w-4 h-4" />
        退出
      </button>
    </div>
  );
};

export default UserMenu;
