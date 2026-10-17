import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Message } from '../types';
import { MessageItem } from './MessageItem';
import { ScrollToBottomBtn } from './ScrollToBottomBtn';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  onRegenerate: () => void;
  onFollowUpClick: (prompt: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isStreaming,
  onRegenerate,
  onFollowUpClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const userHasScrolledUpRef = useRef(false);

  // Check scroll position to determine if user manually scrolled away from bottom
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);

    // If more than 100px away from bottom, consider user as having scrolled up
    if (distanceFromBottom > 100) {
      userHasScrolledUpRef.current = true;
      setShowScrollBottom(true);
    } else {
      userHasScrolledUpRef.current = false;
      setShowScrollBottom(false);
    }
  }, []);

  // Smoothly scroll to bottom
  const scrollToBottom = useCallback((smooth = true) => {
    userHasScrolledUpRef.current = false;
    setShowScrollBottom(false);
    bottomAnchorRef.current?.scrollIntoView({
      behavior: smooth ? 'smooth' : 'auto',
      block: 'end',
    });
  }, []);

  // Auto-scroll when messages update OR while streaming, UNLESS user explicitly scrolled up
  useEffect(() => {
    if (!userHasScrolledUpRef.current) {
      scrollToBottom(false);
    }
  }, [messages, isStreaming, scrollToBottom]);

  // Find index of last AI message for regenerate button
  let lastAIIndex = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') {
      lastAIIndex = i;
      break;
    }
  }

  return (
    <div className="relative flex-1 w-full h-full overflow-hidden">
      {/* Scrollable Container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="w-full h-full overflow-y-auto px-4 sm:px-6 pt-4 pb-36 overscroll-contain"
      >
        {/* Constrained Column: 720-760px Centered */}
        <div className="max-w-[740px] mx-auto group">
          {messages.map((message, idx) => (
            <MessageItem
              key={message.id || idx}
              message={message}
              isLastAI={idx === lastAIIndex}
              onRegenerate={onRegenerate}
              onFollowUpClick={onFollowUpClick}
              isStreaming={isStreaming && idx === lastAIIndex}
            />
          ))}
          <div ref={bottomAnchorRef} className="h-4" />
        </div>
      </div>

      {/* Floating Scroll to Bottom Indicator */}
      <ScrollToBottomBtn visible={showScrollBottom} onClick={() => scrollToBottom(true)} />
    </div>
  );
};
