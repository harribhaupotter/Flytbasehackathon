import React from 'react';
import { ExternalLink, Globe } from 'lucide-react';
import { SourceCitation } from '../types';

interface SourcesListProps {
  sources: SourceCitation[];
}

export const SourcesList: React.FC<SourcesListProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mb-4">
      <div className="flex items-center space-x-1.5 text-xs font-medium text-neutral-400 mb-2">
        <Globe className="w-3.5 h-3.5 text-neutral-400" />
        <span>Sources & Citations</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {sources.map((src, idx) => (
          <a
            key={src.id || idx}
            href={src.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs bg-white/[0.04] dark:bg-white/[0.04] light:bg-black/[0.04] hover:bg-white/[0.09] dark:hover:bg-white/[0.09] light:hover:bg-black/[0.08] border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08] text-neutral-300 dark:text-neutral-300 light:text-neutral-700 transition-all duration-150 max-w-[240px] truncate"
            title={`${src.title} (${src.domain})`}
          >
            <span className="w-4 h-4 rounded-full bg-white/[0.08] flex items-center justify-center text-[10px] font-mono text-neutral-400 group-hover:text-white">
              {idx + 1}
            </span>
            <span className="truncate font-medium">{src.domain}</span>
            <ExternalLink className="w-3 h-3 opacity-40 group-hover:opacity-100 transition-opacity flex-shrink-0" />
          </a>
        ))}
      </div>
    </div>
  );
};
