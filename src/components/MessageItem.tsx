import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Bot, 
  Copy, 
  Check, 
  RotateCcw, 
  ThumbsUp, 
  ThumbsDown, 
  Sparkles,
  Paperclip
} from 'lucide-react';
import { Message } from '../types';
import { CodeBlock } from './CodeBlock';
import { SourcesList } from './SourcesList';
import { FollowUps } from './FollowUps';
import { GenUIDispatcher } from './genui/GenUIDispatcher';

interface MessageItemProps {
  message: Message;
  isLastAI: boolean;
  onRegenerate?: () => void;
  onFollowUpClick?: (prompt: string) => void;
  isStreaming?: boolean;
}
function cleanContent(content: string): string {
  if (!content) return '';
  const parts = content.split(/(```[\s\S]*?```)/g);
  return parts.map((part) => {
    if (part.startsWith('```')) return part;
    return part
      .replace(/\\Delta\s*T/g, 'ΔT')
      .replace(/\\\$/g, '$')
      .replace(/\^\\circ(?:\\text\{C\}|C)?/g, '°C')
      .replace(/\\circ/g, '°')
      .replace(/\\ge\b/g, '≥')
      .replace(/\\le\b/g, '≤')
      .replace(/\\pm\b/g, '±')
      .replace(/\\approx\b/g, '≈')
      .replace(/\\times\b/g, '×')
      .replace(/\$([^\$\n]+)\$/g, '$1');
  }).join('');
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isLastAI,
  onRegenerate,
  onFollowUpClick,
  isStreaming = false,
}) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleCopyText = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  // ==========================================
  // USER MESSAGE: Compact Right-Aligned Bubble
  // ==========================================
  if (isUser) {
    return (
      <div className="w-full flex justify-end my-4 animate-fade-slide-up">
        <div className="max-w-[85%] sm:max-w-[75%] flex flex-col items-end">
          {message.attachments && message.attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-1.5 justify-end">
              {message.attachments.map((att, i) => (
                <div 
                  key={i} 
                  className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs bg-white/[0.04] dark:bg-white/[0.04] light:bg-black/[0.05] border border-white/[0.08] text-neutral-400"
                >
                  <Paperclip className="w-3 h-3 text-accent" />
                  <span className="truncate max-w-[150px]">{att.name}</span>
                </div>
              ))}
            </div>
          )}
          <div className="px-4 py-3 rounded-2xl rounded-br-sm bg-[#16171D] dark:bg-[#16171D] light:bg-neutral-100 border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] text-neutral-100 dark:text-neutral-100 light:text-neutral-900 text-[15px] leading-relaxed shadow-sm break-words whitespace-pre-wrap">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  // ==========================================
  // AI MESSAGE: Plain Text, Full Column Width
  // ==========================================
  return (
    <div className="w-full my-6 animate-fade-slide-up">
      <div className="flex items-start space-x-3.5">
        {/* Cinematic AI Avatar Mark */}
        <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-gradient-to-tr from-accent/20 via-accent/10 to-transparent border border-accent/30 flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.15)] mt-0.5">
          <Bot className="w-4 h-4 text-accent" />
        </div>

        {/* AI Content Column */}
        <div className="flex-1 min-w-0">
          {/* Header Metadata */}
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-xs font-semibold tracking-wide text-neutral-300 dark:text-neutral-200 light:text-neutral-800">
              Asset Copilot
            </span>
            <span className="text-[11px] text-neutral-500 font-mono">
              {typeof message.timestamp === 'string'
                ? message.timestamp
                : new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* Perplexity-style Source Citations */}
          {message.sources && message.sources.length > 0 && (
            <SourcesList sources={message.sources} />
          )}

          {/* Thinking State */}
          {message.isThinking && (
            <div className="space-y-2.5 my-3 py-1">
              <div className="flex items-center space-x-2 text-xs font-medium text-accent">
                <Sparkles className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: '3s' }} />
                <span>Thinking & synthesizing response...</span>
              </div>
              <div className="h-4 w-4/5 rounded-md bg-white/[0.06] dark:bg-white/[0.06] light:bg-black/[0.06] skeleton-shimmer" />
              <div className="h-4 w-3/5 rounded-md bg-white/[0.06] dark:bg-white/[0.06] light:bg-black/[0.06] skeleton-shimmer" />
            </div>
          )}

          {/* Markdown Body */}
          {message.content ? (
            <div className="markdown-body text-neutral-200 dark:text-neutral-200 light:text-neutral-800 break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Render Code Blocks or Generative UI Widgets
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');

                    if (!inline && match && (match[1] === 'genui' || match[1] === 'a2ui' || match[1] === 'json')) {
                      try {
                        const parsed = JSON.parse(codeString);
                        if (parsed && (parsed.component || parsed.root || parsed.type)) {
                          return <GenUIDispatcher payload={parsed} />;
                        }
                      } catch {
                        // fallback to standard code block
                      }
                    }

                    if (!inline && match) {
                      return <CodeBlock language={match[1]} code={codeString} />;
                    }
                    if (!inline && codeString.includes('\n')) {
                      return <CodeBlock language="code" code={codeString} />;
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  // Styled Links
                  a({ href, children }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent underline underline-offset-4 hover:brightness-125 transition-all"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {cleanContent(message.content)}
              </ReactMarkdown>

              {/* Streaming Cursor */}
              {message.isStreaming && <span className="streaming-cursor" />}
            </div>
          ) : null}

          {/* Action Row - Visible on Hover or Mobile */}
          {!message.isThinking && message.content && (
            <div className="flex items-center space-x-1.5 mt-3 pt-1 text-neutral-400 opacity-90 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-200">
              <button
                onClick={handleCopyText}
                aria-label="Copy entire message"
                className="p-1.5 rounded-lg hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] hover:text-white dark:hover:text-white light:hover:text-black transition-colors"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

              {isLastAI && onRegenerate && !isStreaming && (
                <button
                  onClick={onRegenerate}
                  aria-label="Regenerate response"
                  className="p-1.5 rounded-lg hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] hover:text-white dark:hover:text-white light:hover:text-black transition-colors"
                  title="Regenerate"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}

              <button
                onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
                aria-label="Helpful"
                className={`p-1.5 rounded-lg hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors ${
                  feedback === 'up' ? 'text-accent' : 'hover:text-white dark:hover:text-white light:hover:text-black'
                }`}
                title="Helpful"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
                aria-label="Not helpful"
                className={`p-1.5 rounded-lg hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-colors ${
                  feedback === 'down' ? 'text-rose-400' : 'hover:text-white dark:hover:text-white light:hover:text-black'
                }`}
                title="Not helpful"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Follow-up Suggestion Pills */}
          {message.followUps && message.followUps.length > 0 && !message.isStreaming && (
            <FollowUps
              followUps={message.followUps}
              onSelect={(prompt) => onFollowUpClick && onFollowUpClick(prompt)}
              disabled={isStreaming}
            />
          )}
        </div>
      </div>
    </div>
  );
};
