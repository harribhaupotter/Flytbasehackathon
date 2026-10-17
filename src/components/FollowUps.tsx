import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';

interface FollowUpsProps {
  followUps: string[];
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

export const FollowUps: React.FC<FollowUpsProps> = ({ followUps, onSelect, disabled = false }) => {
  if (!followUps || followUps.length === 0) return null;

  return (
    <div className="mt-5 pt-3 border-t border-white/[0.06] dark:border-white/[0.06] light:border-black/[0.06]">
      <div className="flex items-center space-x-1.5 text-xs font-medium text-neutral-400 mb-2.5">
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        <span>Related Questions</span>
      </div>
      <div className="flex flex-col space-y-2">
        {followUps.map((prompt, idx) => (
          <button
            key={idx}
            disabled={disabled}
            onClick={() => onSelect(prompt)}
            className="group flex items-center justify-between text-left px-3.5 py-2 rounded-xl text-xs sm:text-sm bg-white/[0.03] dark:bg-white/[0.03] light:bg-black/[0.03] hover:bg-white/[0.07] dark:hover:bg-white/[0.07] light:hover:bg-black/[0.06] border border-white/[0.07] dark:border-white/[0.07] light:border-black/[0.07] text-neutral-300 dark:text-neutral-300 light:text-neutral-700 hover:text-white dark:hover:text-white light:hover:text-black transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.99]"
          >
            <span className="pr-4">{prompt}</span>
            <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-accent transition-colors flex-shrink-0 group-hover:translate-x-0.5 duration-150" />
          </button>
        ))}
      </div>
    </div>
  );
};
