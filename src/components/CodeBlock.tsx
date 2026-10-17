import React, { useState, useEffect } from 'react';
import { Check, Copy } from 'lucide-react';
import Prism from 'prismjs';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-markdown';

interface CodeBlockProps {
  language?: string;
  code: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ language = 'typescript', code }) => {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    Prism.highlightAll();
  }, [code, language]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  // Normalize language name
  const langDisplay = language.replace(/^(language-|lang-)/, '').toLowerCase() || 'code';

  return (
    <div className="my-4 rounded-xl overflow-hidden border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] bg-[#0E1015] shadow-lg group">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#14161C] border-b border-white/[0.06] text-xs font-mono text-neutral-400">
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-green-500/80 inline-block" />
          </div>
          <span className="ml-2 font-medium uppercase tracking-wider text-[11px] text-neutral-300">
            {langDisplay}
          </span>
        </div>

        <button
          onClick={handleCopy}
          aria-label="Copy code to clipboard"
          className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-sans text-neutral-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.1] border border-white/[0.06] transition-all duration-150 active:scale-95"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Container */}
      <div className="p-4 overflow-x-auto text-[13.5px] leading-relaxed font-mono">
        <pre className="!bg-transparent !p-0 !m-0">
          <code className={`language-${langDisplay} text-neutral-200`}>
            {code}
          </code>
        </pre>
      </div>
    </div>
  );
};
