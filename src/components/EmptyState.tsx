import React from 'react';
import { Layers, Bug, Atom, Sparkles, ArrowUpRight } from 'lucide-react';
import { STARTER_SUGGESTIONS, StarterSuggestion } from '../config/themeConfig';

interface EmptyStateProps {
  onSelectSuggestion: (prompt: string) => void;
  selectedModelName: string;
  children?: React.ReactNode;
}

const ICON_MAP: Record<string, React.ReactNode> = {
  Layers: <Layers className="w-4 h-4 text-accent" />,
  Bug: <Bug className="w-4 h-4 text-accent" />,
  Atom: <Atom className="w-4 h-4 text-accent" />,
  Sparkles: <Sparkles className="w-4 h-4 text-accent" />,
};

export const EmptyState: React.FC<EmptyStateProps> = ({
  onSelectSuggestion,
  selectedModelName,
  children,
}) => {
  return (
    <div className="relative flex-1 flex flex-col items-center justify-center px-4 sm:px-6 w-full max-w-[760px] mx-auto text-center z-10 py-8 my-auto">
      {/* Soft Cinematic Ambient Radial Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[380px] pointer-events-none -z-10">
        <div className="w-full h-full rounded-full bg-gradient-to-tr from-accent/15 via-purple-600/10 to-cyan-500/10 blur-[110px] animate-ambient-pulse" />
      </div>

      {/* Hero Badge */}
      <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-white/[0.04] dark:bg-white/[0.04] light:bg-black/[0.04] border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] text-xs font-medium text-neutral-400 mb-5 backdrop-blur-sm">
        <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
        <span>Powered by {selectedModelName}</span>
      </div>

      {/* Confident Headline with Gradient Accent */}
      <h1 className="text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight text-neutral-100 dark:text-neutral-100 light:text-neutral-900 max-w-xl leading-[1.18] mb-3">
        Asset{' '}
        <span className="bg-gradient-to-r from-accent via-purple-400 to-cyan-400 bg-clip-text text-transparent">
          Intelligence
        </span>{' '}
        Copilot
      </h1>

      {/* Short Subline */}
      <p className="text-neutral-400 dark:text-neutral-400 light:text-neutral-600 text-sm sm:text-base max-w-md mb-8 leading-relaxed">
        Real-time wellhead health, downtime accounting, and environmental compliance intelligence across your field.
      </p>

      {/* Prompt Composer Directly Beneath Subline */}
      {children && (
        <div className="w-full mb-8">
          {children}
        </div>
      )}

      {/* 3-4 Suggestion Chips Below Composer */}
      <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        {STARTER_SUGGESTIONS.map((item: StarterSuggestion, idx: number) => (
          <button
            key={idx}
            onClick={() => onSelectSuggestion(item.prompt)}
            className="group relative flex flex-col justify-between p-3.5 sm:p-4 rounded-2xl bg-white/[0.02] dark:bg-white/[0.02] light:bg-black/[0.02] hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.05] border border-white/[0.07] dark:border-white/[0.07] light:border-black/[0.07] hover:border-accent/40 dark:hover:border-accent/40 light:hover:border-accent/40 transition-all duration-200 text-left active:scale-[0.98] shadow-sm backdrop-blur-xs"
          >
            <div className="flex items-center justify-between w-full mb-2">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 rounded-lg bg-white/[0.04] dark:bg-white/[0.04] light:bg-black/[0.04] border border-white/[0.06]">
                  {ICON_MAP[item.icon] || <Sparkles className="w-4 h-4 text-accent" />}
                </div>
                <span className="text-[11px] font-mono tracking-wider uppercase text-neutral-500">
                  {item.tag}
                </span>
              </div>
              <ArrowUpRight className="w-4 h-4 text-neutral-500 group-hover:text-accent group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all duration-150" />
            </div>

            <div>
              <h3 className="text-sm font-medium text-neutral-200 dark:text-neutral-200 light:text-neutral-800 group-hover:text-white dark:group-hover:text-white light:group-hover:text-black mb-1">
                {item.title}
              </h3>
              <p className="text-xs text-neutral-500 dark:text-neutral-500 light:text-neutral-600 line-clamp-1">
                {item.subtitle}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};
