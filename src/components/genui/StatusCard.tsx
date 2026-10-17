import React from 'react';
import { Activity, Thermometer, User, Calendar, AlertTriangle, CheckCircle2, FileText } from 'lucide-react';

interface StatusCardProps {
  data: {
    asset_id: string;
    name?: string;
    well_type?: string;
    area?: string;
    dynamic_status: 'producing' | 'non_producing';
    is_producing_dynamically?: boolean;
    wellhead_temp_c: number;
    ambient_temp_c: number;
    delta_temp_c: number;
    threshold_delta_c: number;
    inspected_at?: string;
    inspector_name?: string;
    method?: string;
    recorded_status?: string;
    is_recorded_status_stale?: boolean;
    reason_for_stop?: string;
    citations?: Array<{ id: string; title: string }>;
  };
}

export const StatusCard: React.FC<StatusCardProps> = ({ data: rawData }) => {
  const raw: any = rawData;
  const data: any = {
    ...raw,
    ...(raw?.props || {}),
    ...(raw?.data || {}),
    ...(raw?.latest_inspection || {}),
  };

  const assetId = data.asset_id || data.asset || data.id || 'WELL-0001';
  const wellType = data.well_type || (data.threshold_delta_c === 20 ? 'T350' : 'T200');

  // Dynamic status evaluation
  const isProducing = 
    data.dynamic_status === 'producing' || 
    data.status === 'producing' || 
    data.is_producing_dynamically === true || 
    data.is_producing_dynamically === 1;

  // Temperature values with multi-key fallbacks
  const wellheadTempRaw = data.wellhead_temp_c ?? data.wellhead_temp ?? data.current_wellhead_temp_c;
  const ambientTempRaw = data.ambient_temp_c ?? data.ambient_temp;
  
  const wellheadTemp = wellheadTempRaw !== undefined && wellheadTempRaw !== null && !isNaN(Number(wellheadTempRaw))
    ? Number(wellheadTempRaw)
    : undefined;

  const ambientTemp = ambientTempRaw !== undefined && ambientTempRaw !== null && !isNaN(Number(ambientTempRaw))
    ? Number(ambientTempRaw)
    : undefined;

  let deltaTempRaw = data.delta_temp_c ?? data.delta_temp ?? data.temperature_delta_c ?? data.temp_delta;
  if (deltaTempRaw === undefined && wellheadTemp !== undefined && ambientTemp !== undefined) {
    deltaTempRaw = wellheadTemp - ambientTemp;
  }
  const deltaTemp = deltaTempRaw !== undefined && deltaTempRaw !== null && !isNaN(Number(deltaTempRaw))
    ? Number(deltaTempRaw)
    : undefined;

  const thresholdDelta = data.threshold_delta_c ?? data.threshold ?? data.threshold_c ?? (wellType === 'T350' ? 20.0 : 15.0);

  // Inspector and Inspection Date
  const inspectedAt = data.inspected_at || data.inspection_date || data.inspected_date || data.date;
  const formattedDate = inspectedAt 
    ? (isNaN(Date.parse(inspectedAt)) ? inspectedAt : new Date(inspectedAt).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }))
    : '15 Oct 2026';

  const inspectorName = data.inspector_name || data.inspector || data.inspector_user_id || 'Drone Telemetry';
  const reasonForStop = data.reason_for_stop || data.notes || data.reason;
  const recordedStatus = data.recorded_status || 'active';
  const isStale = data.is_recorded_status_stale ?? (!isProducing && recordedStatus.toLowerCase() === 'active');

  return (
    <div className="w-full max-w-xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-white tracking-wide">{assetId}</h3>
            {wellType && (
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {wellType}
              </span>
            )}
            {data.area && (
              <span className="text-xs text-neutral-400">· {data.area}</span>
            )}
          </div>
          {data.name && <div className="text-xs text-neutral-400 mt-0.5">{data.name}</div>}
        </div>

        {/* Dynamic Status Badge */}
        <div className={`flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
          isProducing 
            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
            : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
        }`}>
          {isProducing ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
          <span>{isProducing ? 'PRODUCING OIL' : 'NOT PRODUCING'}</span>
        </div>
      </div>

      {/* Temperature Telemetry Grid */}
      <div className="grid grid-cols-3 gap-2 my-3.5">
        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center text-[10px] text-neutral-400 space-x-1">
            <Thermometer className="w-3 h-3 text-red-400" />
            <span>Wellhead Temp</span>
          </div>
          <div className="text-sm sm:text-base font-mono font-semibold text-white mt-1">
            {wellheadTemp !== undefined ? `${wellheadTemp.toFixed(1)} °C` : '--'}
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center text-[10px] text-neutral-400 space-x-1">
            <Thermometer className="w-3 h-3 text-cyan-400" />
            <span>Ambient Air</span>
          </div>
          <div className="text-sm sm:text-base font-mono font-semibold text-white mt-1">
            {ambientTemp !== undefined ? `${ambientTemp.toFixed(1)} °C` : '--'}
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
          <div className="flex items-center text-[10px] text-neutral-400 space-x-1">
            <Activity className="w-3 h-3 text-amber-400" />
            <span>ΔT (Delta)</span>
          </div>
          <div className={`text-sm sm:text-base font-mono font-bold mt-1 ${isProducing ? 'text-emerald-400' : 'text-rose-400'}`}>
            {deltaTemp !== undefined ? `${deltaTemp >= 0 ? `+${deltaTemp.toFixed(1)}` : deltaTemp.toFixed(1)} °C` : '--'}
          </div>
          <div className="text-[9px] text-neutral-500 mt-0.5">
            Req: ≥ {thresholdDelta} °C ({wellType})
          </div>
        </div>
      </div>

      {/* Stop Reason / Notes */}
      {reasonForStop && (
        <div className="p-3 mb-3 rounded-xl bg-rose-950/20 border border-rose-500/20 text-xs">
          <div className="font-semibold text-rose-300 flex items-center space-x-1 mb-1">
            <AlertTriangle className="w-3 h-3" />
            <span>Reason for Shutdown:</span>
          </div>
          <div className="text-neutral-300 leading-relaxed">{reasonForStop}</div>
        </div>
      )}

      {/* Stale Recorded Status Warning */}
      {isStale && (
        <div className="p-2.5 mb-3 rounded-xl bg-amber-950/20 border border-amber-500/20 text-xs text-amber-200/90 flex items-start space-x-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
          <span>
            <strong>System of Record Discrepancy:</strong> Static recorded status says <code className="bg-black/30 px-1 py-0.5 rounded text-amber-300">{recordedStatus}</code>, which is out of date. Current inspection thermal delta confirms the well is {isProducing ? 'active' : 'idle'}.
          </span>
        </div>
      )}

      {/* Inspection Footer */}
      <div className="pt-2.5 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-neutral-400">
        <div className="flex items-center space-x-1.5">
          <Calendar className="w-3 h-3" />
          <span>Last: {formattedDate}</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <User className="w-3 h-3" />
          <span>Inspector: {inspectorName}</span>
        </div>
      </div>

      {/* Citations Chips */}
      {data.citations && data.citations.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-white/[0.04] flex flex-wrap gap-1.5">
          {data.citations.map((c: any, i: number) => (
            <span key={i} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-mono border border-blue-500/20">
              <FileText className="w-2.5 h-2.5" />
              <span>{typeof c === 'string' ? c : c.id || c.title}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
