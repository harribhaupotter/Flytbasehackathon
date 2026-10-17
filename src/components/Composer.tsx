import React, { useRef, useEffect, useState, KeyboardEvent } from 'react';
import { ArrowUp, Square, Paperclip, X } from 'lucide-react';

interface ComposerProps {
  input: string;
  setInput: (value: string) => void;
  onSend: (attachments?: Array<{ name: string; size: string; type: string }>) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  input,
  setInput,
  onSend,
  onStop,
  isStreaming,
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachments, setAttachments] = useState<Array<{ name: string; size: string; type: string }>>([]);

  // Auto-grow textarea up to ~6 lines (max ~150px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 160);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) {
        return;
      }
      if (input.trim() || attachments.length > 0) {
        handleSubmit();
      }
    }
  };

  const handleSubmit = () => {
    if (isStreaming) {
      onStop();
      return;
    }
    if ((input.trim() || attachments.length > 0) && !disabled) {
      onSend(attachments.length > 0 ? attachments : undefined);
      setAttachments([]);
      // Reset height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
      setAttachments(prev => [
        ...prev,
        {
          name: file.name,
          size: `${sizeMb} MB`,
          type: file.type || 'document',
        },
      ]);
      e.target.value = '';
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const canSubmit = (input.trim().length > 0 || attachments.length > 0) && !disabled;

  return (
    <div className="relative w-full max-w-[740px] mx-auto px-4 sm:px-6">
      {/* Composer Glass Container */}
      <div className="relative rounded-2xl sm:rounded-3xl bg-[#121318]/90 dark:bg-[#121318]/90 light:bg-white/95 border border-white/[0.1] dark:border-white/[0.1] light:border-black/[0.1] shadow-[0_12px_40px_rgba(0,0,0,0.35)] dark:shadow-[0_12px_40px_rgba(0,0,0,0.4)] light:shadow-[0_12px_40px_rgba(0,0,0,0.08)] backdrop-blur-xl transition-all duration-200 focus-within:border-accent/60 focus-within:ring-2 focus-within:ring-accent/25">
        
        {/* Attachment Pills Preview */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-4 pt-3">
            {attachments.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center space-x-2 px-2.5 py-1 rounded-lg text-xs bg-white/[0.06] dark:bg-white/[0.06] light:bg-black/[0.05] border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] text-neutral-300 dark:text-neutral-300 light:text-neutral-700 animate-fade-in"
              >
                <Paperclip className="w-3 h-3 text-accent" />
                <span className="truncate max-w-[140px] font-medium">{file.name}</span>
                <span className="text-[10px] text-neutral-500">({file.size})</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(idx)}
                  className="hover:text-red-400 p-0.5 rounded transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Input Area */}
        <div className="flex items-end px-3 py-2.5 sm:px-4 sm:py-3">
          {/* Hidden File Input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            aria-label="Upload file attachment"
          />

          {/* Attach (+) Button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="Attach file or code"
            className="p-2 sm:p-2.5 rounded-full text-neutral-400 hover:text-white dark:hover:text-white light:hover:text-black hover:bg-white/[0.06] dark:hover:bg-white/[0.06] light:hover:bg-black/[0.06] transition-all duration-150 active:scale-95 flex-shrink-0 mb-0.5"
            title="Attach file"
          >
            <Paperclip className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>

          {/* Auto-growing Textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? 'Streaming response...' : 'Ask anything, explore code, or brainstorm...'}
            disabled={disabled}
            className="flex-1 bg-transparent px-3 py-1.5 text-[15px] leading-relaxed text-neutral-100 dark:text-neutral-100 light:text-neutral-900 placeholder:text-neutral-500 dark:placeholder:text-neutral-500 light:placeholder:text-neutral-400 focus:outline-none resize-none max-h-[160px] overflow-y-auto"
            style={{ minHeight: '28px' }}
          />

          {/* Send / Stop Dynamic Button */}
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generation"
              className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-rose-500 hover:bg-rose-600 text-white flex items-center justify-center transition-all duration-150 active:scale-90 flex-shrink-0 shadow-[0_0_12px_rgba(244,63,94,0.4)] mb-0.5"
              title="Stop generating"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              aria-label="Send message"
              className={`w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center transition-all duration-200 active:scale-90 flex-shrink-0 mb-0.5 ${
                canSubmit
                  ? 'bg-accent text-accent-fg hover:brightness-110 shadow-[0_0_16px_var(--accent-glow)] cursor-pointer'
                  : 'bg-white/[0.06] dark:bg-white/[0.06] light:bg-black/[0.06] text-neutral-500 cursor-not-allowed opacity-50'
              }`}
              title="Send message (Enter)"
            >
              <ArrowUp className="w-4 h-4 sm:w-4.5 sm:h-4.5 stroke-[2.5]" />
            </button>
          )}
        </div>
      </div>

      {/* Muted Disclaimer Text */}
      <div className="text-center mt-2.5">
        <p className="text-[11px] text-neutral-500 dark:text-neutral-500 light:text-neutral-400 tracking-tight select-none">
          Aether may produce inaccurate info. Verify mission-critical facts. Shift+Enter for new line.
        </p>
      </div>
    </div>
  );
};
