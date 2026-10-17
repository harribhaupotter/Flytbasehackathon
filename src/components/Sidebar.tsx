import React from 'react';
import { 
  MessageSquare, 
  Trash2, 
  Plus, 
  Sparkles, 
  X
} from 'lucide-react';
import { Conversation } from '../types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: Conversation[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onNewChat: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  conversations,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewChat,
}) => {
  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden animate-fade-in"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 w-64 md:w-64 bg-[#0D0E12] dark:bg-[#0D0E12] light:bg-[#F3F4F6] border-r border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] flex flex-col transition-all duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:-ml-64'
        }`}
      >
        {/* Header: Brand & Close (mobile) */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-white/[0.06] dark:border-white/[0.06] light:border-black/[0.06] flex-shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-6 h-6 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-accent" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-white dark:text-white light:text-black">
              Asset Copilot
            </span>
          </div>

          <div className="flex items-center space-x-1">
            <button
              onClick={onNewChat}
              aria-label="New chat"
              className="p-1.5 rounded-lg text-neutral-400 hover:text-white dark:hover:text-white light:hover:text-black hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors"
              title="New Chat"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              aria-label="Close sidebar"
              className="p-1.5 rounded-lg text-neutral-400 hover:text-white dark:hover:text-white light:hover:text-black hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] md:hidden transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          <div className="px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider text-neutral-500">
            Recent Conversations
          </div>

          {conversations.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-neutral-500">
              No previous chats yet.
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              return (
                <div
                  key={conv.id}
                  className={`group relative flex items-center justify-between px-2.5 py-2 rounded-xl text-xs transition-all duration-150 cursor-pointer ${
                    isActive
                      ? 'bg-white/[0.08] dark:bg-white/[0.08] light:bg-black/[0.08] text-white dark:text-white light:text-black font-medium border border-white/[0.06]'
                      : 'text-neutral-400 hover:text-neutral-200 dark:hover:text-neutral-200 light:hover:text-black hover:bg-white/[0.03] dark:hover:bg-white/[0.03] light:hover:bg-black/[0.03]'
                  }`}
                  onClick={() => {
                    onSelectConversation(conv.id);
                    // On mobile, close sidebar upon selection
                    if (window.innerWidth < 768) {
                      onClose();
                    }
                  }}
                >
                  <div className="flex items-center space-x-2.5 truncate flex-1 mr-2">
                    <MessageSquare className={`w-3.5 h-3.5 flex-shrink-0 ${isActive ? 'text-accent' : 'text-neutral-500'}`} />
                    <span className="truncate">{conv.title || 'Untitled conversation'}</span>
                  </div>

                  {/* Delete Conversation Button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteConversation(conv.id);
                    }}
                    aria-label={`Delete conversation ${conv.title}`}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-white/[0.1] hover:text-red-400 text-neutral-500 transition-all"
                    title="Delete chat"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Footer: User profile / settings */}
        <div className="p-3 border-t border-white/[0.06] dark:border-white/[0.06] light:border-black/[0.06] flex-shrink-0">
          <div className="flex items-center justify-between px-2 py-1.5 rounded-xl bg-white/[0.02] border border-white/[0.04]">
            <div className="flex items-center space-x-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-accent to-purple-600 flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
                U
              </div>
              <div className="text-left">
                <p className="text-xs font-medium text-neutral-300 dark:text-neutral-300 light:text-neutral-700 leading-none">
                  Local Workspace
                </p>
                <p className="text-[10px] text-neutral-500 leading-none mt-1">
                  Ready to deploy
                </p>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-emerald-400/20" />
          </div>
        </div>
      </aside>
    </>
  );
};
