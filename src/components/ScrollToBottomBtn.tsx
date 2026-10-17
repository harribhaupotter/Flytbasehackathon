import React from 'react';
import { ArrowDown } from 'lucide-react';

interface ScrollToBottomBtnProps {
  visible: boolean;
  onClick: () => void;
}

export const ScrollToBottomBtn: React.FC<ScrollToBottomBtnProps> = ({ visible, onClick }) => {
  if (!visible) return null;

  return (
    <div className="absolute bottom-28 right-6 z-20 animate-fade-slide-up">
      <button
        onClick={onClick}
        aria-label="Scroll to bottom"
        className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-[#1A1C23] dark:bg-[#1A1C23] light:bg-white text-neutral-300 dark:text-neutral-300 light:text-neutral-700 hover:text-white dark:hover:text-white light:hover:text-black border border-white/[0.1] dark:border-white/[0.1] light:border-black/[0.1] shadow-[0_8px_20px_rgba(0,0,0,0.35)] hover:border-accent/50 transition-all duration-200 active:scale-95 group text-xs font-medium"
      >
        <span>Latest</span>
        <ArrowDown className="w-3.5 h-3.5 group-hover:translate-y-0.5 transition-transform" />
      </button>
    </div>
  );
};
