import React from 'react';
import { AlertCircle, User, Database, ArrowRight } from 'lucide-react';

interface ConflictAlertProps {
  data: {
    claimant: string;
    claim: string;
    contradictingSource: string;
    contradictingEvidence: string;
    resolutionStatus?: string;
  };
}

export const ConflictAlert: React.FC<ConflictAlertProps> = ({ data }) => {
  return (
    <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-amber-950/25 border border-amber-500/30 text-neutral-100 font-sans shadow-lg">
      <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs uppercase tracking-wider pb-2 border-b border-amber-500/20">
        <AlertCircle className="w-4 h-4 text-amber-400" />
        <span>Operational Data Conflict Detected</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-3">
        {/* User Assertion */}
        <div className="p-3 rounded-xl bg-black/30 border border-amber-500/15">
          <div className="flex items-center space-x-1.5 text-[11px] text-amber-300 font-semibold mb-1">
            <User className="w-3 h-3" />
            <span>Operator Statement ({data.claimant}):</span>
          </div>
          <div className="text-xs text-neutral-200 italic">
            "{data.claim}"
          </div>
        </div>

        {/* System of Record Evidence */}
        <div className="p-3 rounded-xl bg-black/30 border border-amber-500/15">
          <div className="flex items-center space-x-1.5 text-[11px] text-amber-300 font-semibold mb-1">
            <Database className="w-3 h-3" />
            <span>Verified Telemetry ({data.contradictingSource}):</span>
          </div>
          <div className="text-xs text-neutral-200">
            {data.contradictingEvidence}
          </div>
        </div>
      </div>

      <div className="text-xs text-amber-200/90 bg-amber-500/10 p-2.5 rounded-xl border border-amber-500/20 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <ArrowRight className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
          <span>
            {data.resolutionStatus || "Claim marked as UNCONFIRMED pending physical operator verification."}
          </span>
        </div>
      </div>
    </div>
  );
};
