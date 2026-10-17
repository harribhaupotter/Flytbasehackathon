import React, { useState, useEffect, useRef } from 'react';
import { TopNav } from './components/TopNav';
import { Sidebar } from './components/Sidebar';
import { EmptyState } from './components/EmptyState';
import { MessageList } from './components/MessageList';
import { Composer } from './components/Composer';
import { AVAILABLE_MODELS, ACCENT_THEMES } from './config/themeConfig';
import { sendMessage } from './services/aiService';
import { Conversation, Message, Theme, AccentColor, AIModel, OperatorUser, OPERATOR_USERS } from './types';

export const App: React.FC = () => {
  // Operator Identity State (FlytBase Copilot Multi-Tiered Memory)
  const [currentUser, setCurrentUser] = useState<OperatorUser>(() => {
    try {
      const saved = localStorage.getItem('flytbase_current_user');
      return saved ? JSON.parse(saved) : OPERATOR_USERS[0];
    } catch {
      return OPERATOR_USERS[0];
    }
  });

  useEffect(() => {
    localStorage.setItem('flytbase_current_user', JSON.stringify(currentUser));
  }, [currentUser]);

  // Theme & Accent State
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem('aether_theme') as Theme) || 'dark';
  });
  const [accent, setAccent] = useState<AccentColor>(() => {
    return (localStorage.getItem('aether_accent') as AccentColor) || 'violet';
  });

  // Navigation & Model State
  const [selectedModel, setSelectedModel] = useState<AIModel>(AVAILABLE_MODELS[0]);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Conversations & Chat State
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    try {
      const saved = localStorage.getItem('aether_conversations');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [activeConversationId, setActiveConversationId] = useState<string>('');
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync Theme with HTML Document Class
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
    localStorage.setItem('aether_theme', theme);
  }, [theme]);

  // Apply Accent CSS Variables to root
  useEffect(() => {
    const root = document.documentElement;
    const themeConfig = ACCENT_THEMES[accent];
    if (themeConfig) {
      Object.entries(themeConfig.cssVars).forEach(([key, val]) => {
        root.style.setProperty(key, val);
      });
    }
    localStorage.setItem('aether_accent', accent);
  }, [accent]);

  // Persist Conversations
  useEffect(() => {
    try {
      localStorage.setItem('aether_conversations', JSON.stringify(conversations));
    } catch (err) {
      console.error('Failed to persist conversations:', err);
    }
  }, [conversations]);

  // Get Active Conversation
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConversation?.messages || [];

  // Toggle Theme
  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Start New Chat
  const handleNewChat = () => {
    if (isStreaming) {
      handleStopStreaming();
    }
    setActiveConversationId('');
    setInput('');
  };

  // Switch Conversation
  const handleSelectConversation = (id: string) => {
    if (isStreaming) {
      handleStopStreaming();
    }
    setActiveConversationId(id);
  };

  // Delete Conversation
  const handleDeleteConversation = (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId('');
    }
  };

  // Stop Streaming
  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);

    // Finalize last message state
    setConversations((prev) =>
      prev.map((conv) => {
        if (conv.id !== activeConversationId) return conv;
        const updatedMessages = conv.messages.map((m, idx) => {
          if (idx === conv.messages.length - 1 && m.role === 'assistant') {
            return { ...m, isStreaming: false, isThinking: false };
          }
          return m;
        });
        return { ...conv, messages: updatedMessages };
      })
    );
  };

  // Core Send Message Pipeline
  const handleSendMessage = async (
    customPrompt?: string,
    attachments?: Array<{ name: string; size: string; type: string }>
  ) => {
    const promptToSend = (customPrompt !== undefined ? customPrompt : input).trim();
    if (!promptToSend && (!attachments || attachments.length === 0)) return;
    if (isStreaming) return;

    setInput('');

    // Ensure conversation exists
    let convId = activeConversationId;
    let currentMessages = messages;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: promptToSend,
      timestamp: new Date().toISOString(),
      attachments,
    };

    if (!convId || !activeConversation) {
      convId = `conv-${Date.now()}`;
      const title = promptToSend.slice(0, 32) + (promptToSend.length > 32 ? '...' : '');
      const newConv: Conversation = {
        id: convId,
        title: title || 'New Conversation',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messages: [userMessage],
        modelId: selectedModel.id,
        userId: currentUser.id,
      };
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversationId(convId);
      currentMessages = [userMessage];
    } else {
      currentMessages = [...currentMessages, userMessage];
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                messages: currentMessages,
                updatedAt: new Date().toISOString(),
              }
            : c
        )
      );
    }

    // Append Initial AI Thinking Message
    const aiMessageId = `ai-${Date.now()}`;
    const initialAIMessage: Message = {
      id: aiMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isThinking: true,
      isStreaming: true,
    };

    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? {
              ...c,
              messages: [...currentMessages, initialAIMessage],
            }
          : c
      )
    );

    setIsStreaming(true);
    abortControllerRef.current = new AbortController();

    try {
      await sendMessage({
        prompt: promptToSend,
        modelId: selectedModel.id,
        conversationHistory: currentMessages,
        userId: currentUser.id,
        conversationId: convId,
        signal: abortControllerRef.current.signal,
        onThinking: () => {
          // Thinking indicator active
        },
        onSources: (sources) => {
          setConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              const updated = c.messages.map((m) =>
                m.id === aiMessageId ? { ...m, sources } : m
              );
              return { ...c, messages: updated };
            })
          );
        },
        onToken: (_token, fullText) => {
          setConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              const updated = c.messages.map((m) =>
                m.id === aiMessageId
                  ? {
                      ...m,
                      content: fullText,
                      isThinking: false,
                      isStreaming: true,
                    }
                  : m
              );
              return { ...c, messages: updated };
            })
          );
        },
        onFollowUps: (followUps) => {
          setConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              const updated = c.messages.map((m) =>
                m.id === aiMessageId ? { ...m, followUps } : m
              );
              return { ...c, messages: updated };
            })
          );
        },
      });
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Streaming error:', err);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          const updated = c.messages.map((m) =>
            m.id === aiMessageId
              ? { ...m, isStreaming: false, isThinking: false }
              : m
          );
          return { ...c, messages: updated };
        })
      );
    }
  };

  // Regenerate Last AI Message
  const handleRegenerate = () => {
    if (messages.length < 2 || isStreaming) return;
    const lastUserIndex = [...messages].reverse().findIndex((m) => m.role === 'user');
    if (lastUserIndex === -1) return;

    const actualIndex = messages.length - 1 - lastUserIndex;
    const lastUserPrompt = messages[actualIndex].content;

    // Remove the last AI message
    const prunedMessages = messages.slice(0, actualIndex + 1);
    setConversations((prev) =>
      prev.map((c) =>
        c.id === activeConversationId
          ? { ...c, messages: prunedMessages }
          : c
      )
    );

    // Re-trigger
    handleSendMessage(lastUserPrompt);
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-dark-bg dark:bg-dark-bg light:bg-light-bg text-dark-text dark:text-dark-text light:text-light-text font-sans">
      {/* Slim Collapsible Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations.filter((c) => !c.userId || c.userId === currentUser.id)}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onNewChat={handleNewChat}
      />

      {/* Main Content Area */}
      <div className="relative flex flex-col flex-1 h-full min-w-0 overflow-hidden">
        {/* Top Minimal Navigation */}
        <TopNav
          selectedModel={selectedModel}
          onSelectModel={setSelectedModel}
          currentUser={currentUser}
          onSelectUser={(user) => {
            setCurrentUser(user);
            // Switch to a new or existing chat for this user
            const userConvs = conversations.filter((c) => c.userId === user.id);
            if (userConvs.length > 0) {
              setActiveConversationId(userConvs[0].id);
            } else {
              handleNewChat();
            }
          }}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          onNewChat={handleNewChat}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          sidebarOpen={sidebarOpen}
        />

        {/* Conversation Stream OR Empty State Hero */}
        <main className="relative flex-1 flex flex-col min-h-0 overflow-hidden">
          {!hasMessages ? (
            <div className="flex-1 flex flex-col overflow-y-auto px-2">
              <EmptyState
                selectedModelName={selectedModel.name}
                onSelectSuggestion={(prompt) => handleSendMessage(prompt)}
              >
                <Composer
                  input={input}
                  setInput={setInput}
                  onSend={(attachments) => handleSendMessage(undefined, attachments)}
                  onStop={handleStopStreaming}
                  isStreaming={isStreaming}
                />
              </EmptyState>
            </div>
          ) : (
            <div className="relative flex-1 flex flex-col h-full min-h-0">
              {/* Message List */}
              <MessageList
                messages={messages}
                isStreaming={isStreaming}
                onRegenerate={handleRegenerate}
                onFollowUpClick={(prompt) => handleSendMessage(prompt)}
              />

              {/* Pinned Bottom Composer with Graceful Fade Mask */}
              <div className="absolute bottom-0 left-0 right-0 z-20 pointer-events-none pb-5 pt-10 bg-gradient-to-t from-dark-bg via-dark-bg/95 to-transparent dark:from-dark-bg dark:via-dark-bg/95 dark:to-transparent light:from-light-bg light:via-light-bg/95 light:to-transparent">
                <div className="pointer-events-auto">
                  <Composer
                    input={input}
                    setInput={setInput}
                    onSend={(attachments) => handleSendMessage(undefined, attachments)}
                    onStop={handleStopStreaming}
                    isStreaming={isStreaming}
                  />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
