import React from 'react';

const sizeMap = {
  sm: 'w-9 h-9',
  md: 'w-11 h-11',
  lg: 'w-14 h-14',
};

const BrandLogo = ({ size = 'md', showText = true, className = '' }) => {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <img
        src="/gankaigc-logo.svg"
        alt="GankAIGC 标志"
        className={`${sizeMap[size] || sizeMap.md} object-contain rounded-xl`}
      />
      {showText && (
        <span className="text-[19px] font-bold text-slate-950 leading-none">
          GankAIGC
        </span>
      )}
    </div>
  );
};

export default BrandLogo;
