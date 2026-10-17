import React, { useState, useRef, useEffect } from 'react';
import { 
  ChevronDown, 
  Sun, 
  Moon, 
  Plus, 
  PanelLeft, 
  Check, 
  Zap, 
  Code, 
  Cpu, 
  Sparkles
} from 'lucide-react';
import { AVAILABLE_MODELS } from '../config/themeConfig';
import { AIModel, Theme, OperatorUser } from '../types';
import { UserPicker } from './UserPicker';

interface TopNavProps {
  selectedModel: AIModel;
  onSelectModel: (model: AIModel) => void;
  currentUser: OperatorUser;
  onSelectUser: (user: OperatorUser) => void;
  theme: Theme;
  onToggleTheme: () => void;
  onNewChat: () => void;
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
}

const MODEL_ICONS: Record<string, React.ReactNode> = {
  Zap: <Zap className="w-3.5 h-3.5 text-amber-400" />,
  Code: <Code className="w-3.5 h-3.5 text-accent" />,
  Cpu: <Cpu className="w-3.5 h-3.5 text-emerald-400" />,
  Sparkles: <Sparkles className="w-3.5 h-3.5 text-cyan-400" />,
};

export const TopNav: React.FC<TopNavProps> = ({
  selectedModel,
  onSelectModel,
  currentUser,
  onSelectUser,
  theme,
  onToggleTheme,
  onNewChat,
  onToggleSidebar,
  sidebarOpen,
}) => {
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
        setModelDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="h-14 w-full border-b border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] bg-[#0A0A0E]/80 dark:bg-[#0A0A0E]/80 light:bg-white/85 backdrop-blur-md px-3 sm:px-4 flex items-center justify-between z-30 flex-shrink-0 transition-colors">
      {/* Left: Sidebar Toggle & Model Selector */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          className="p-2 rounded-xl text-neutral-400 hover:text-white dark:hover:text-white light:hover:text-black hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors"
          title="Toggle history"
        >
          <PanelLeft className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
        </button>

        {/* Model Selector Dropdown */}
        <div className="relative" ref={modelMenuRef}>
          <button
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            aria-expanded={modelDropdownOpen}
            className="flex items-center space-x-2 px-2.5 py-1.5 rounded-xl hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors group text-left"
          >
            <div className="w-5 h-5 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center">
              {MODEL_ICONS[selectedModel.iconName] || <Zap className="w-3.5 h-3.5 text-accent" />}
            </div>
            <span className="text-xs sm:text-sm font-medium text-neutral-200 dark:text-neutral-200 light:text-neutral-800">
              {selectedModel.name}
            </span>
            <span className="hidden md:inline-block px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/[0.06] text-neutral-400 border border-white/[0.06]">
              {selectedModel.badge}
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-neutral-400 group-hover:text-neutral-200 transition-transform duration-200" />
          </button>

          {/* Dropdown Menu */}
          {modelDropdownOpen && (
            <div className="absolute top-full left-0 mt-1.5 w-72 rounded-2xl bg-[#14151B] dark:bg-[#14151B] light:bg-white border border-white/[0.1] dark:border-white/[0.1] light:border-black/[0.1] shadow-2xl p-1.5 z-50 animate-fade-in backdrop-blur-xl">
              <div className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider text-neutral-500">
                Select Intelligence Engine
              </div>
              {AVAILABLE_MODELS.map((model) => (
                <button
                  key={model.id}
                  onClick={() => {
                    onSelectModel(model);
                    setModelDropdownOpen(false);
                  }}
                  className={`w-full flex items-start space-x-2.5 px-3 py-2.5 rounded-xl text-left transition-colors ${
                    selectedModel.id === model.id
                      ? 'bg-accent/15 text-white'
                      : 'hover:bg-white/[0.05] text-neutral-300 dark:text-neutral-300 light:text-neutral-700'
                  }`}
                >
                  <div className="mt-0.5 p-1 rounded-md bg-white/[0.05]">
                    {MODEL_ICONS[model.iconName] || <Zap className="w-3.5 h-3.5 text-accent" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold">{model.name}</span>
                      <span className="text-[10px] font-mono opacity-60">{model.contextLength}</span>
                    </div>
                    <p className="text-[11px] text-neutral-400 truncate mt-0.5">
                      {model.tagline}
                    </p>
                  </div>
                  {selectedModel.id === model.id && (
                    <Check className="w-4 h-4 text-accent mt-1 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right: New Chat, Accent Selector & Theme Toggle */}
      <div className="flex items-center space-x-1.5 sm:space-x-2">
        {/* Operator Identity Switcher */}
        <UserPicker currentUser={currentUser} onSelectUser={onSelectUser} />

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          aria-label="Start new chat"
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-white/[0.05] dark:bg-white/[0.05] light:bg-black/[0.05] hover:bg-white/[0.1] dark:hover:bg-white/[0.1] light:hover:bg-black/[0.08] border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] text-xs font-medium text-neutral-200 dark:text-neutral-200 light:text-neutral-800 transition-all duration-150 active:scale-95"
          title="New conversation"
        >
          <Plus className="w-3.5 h-3.5 text-accent" />
          <span className="hidden sm:inline">New Chat</span>
        </button>



        {/* Theme Toggle (Dark / Light) */}
        <button
          onClick={onToggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className="p-2 rounded-xl text-neutral-400 hover:text-white dark:hover:text-white light:hover:text-black hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-300" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-600" />
          )}
        </button>
      </div>
    </header>
  );
};
