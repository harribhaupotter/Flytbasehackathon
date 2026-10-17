import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine
} from 'recharts';
import { Activity, FileText } from 'lucide-react';

interface LineChartWidgetProps {
  data: {
    title: string;
    subtitle?: string;
    data: Array<{
      date: string;
      wellhead_temp_c: number;
      ambient_temp_c: number;
      delta_temp_c?: number;
      is_producing?: boolean;
      annotation?: string;
    }>;
    statusBands?: Array<{
      startDate: string;
      endDate: string;
      label: string;
      fillColor?: string;
    }>;
    thresholdLine?: {
      value: number;
      label: string;
    };
    citations?: Array<{ id: string; title: string }>;
  };
}

export const LineChartWidget: React.FC<LineChartWidgetProps> = ({ data: rawData }) => {
  const raw: any = rawData || {};
  // Safely extract props without spreading arrays into numeric keys
  const nestedProps = (raw.props && typeof raw.props === 'object' && !Array.isArray(raw.props)) ? raw.props : {};
  const nestedData = (raw.data && typeof raw.data === 'object' && !Array.isArray(raw.data)) ? raw.data : {};

  const merged: any = {
    ...raw,
    ...nestedProps,
    ...nestedData,
  };

  const title = merged.title || 'Telemetry Line Chart';
  const subtitle = merged.subtitle;
  const citations = merged.citations || [];
  const statusBands = merged.statusBands || [];
  const thresholdLine = merged.thresholdLine;

  // Extract raw points array from any possible field
  let rawPoints: any[] = [];
  if (Array.isArray(raw.data)) {
    rawPoints = raw.data;
  } else if (Array.isArray(merged.data)) {
    rawPoints = merged.data;
  } else if (Array.isArray(merged.points)) {
    rawPoints = merged.points;
  } else if (Array.isArray(merged.series)) {
    rawPoints = merged.series;
  } else if (Array.isArray(merged.rows)) {
    rawPoints = merged.rows;
  }

  if (!rawPoints || rawPoints.length === 0) {
    return (
      <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
        <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
          <Activity className="w-4 h-4 text-blue-400" />
          <span>{title}</span>
        </h3>
        {subtitle && <p className="text-xs text-neutral-400 mt-0.5">{subtitle}</p>}
        <div className="h-32 flex items-center justify-center text-xs text-neutral-500">
          No telemetry points available
        </div>
      </div>
    );
  }

  const firstPoint = rawPoints[0] || {};

  // Auto-detect Date/Time X-Axis Key
  const explicitXKey = merged.xAxisKey || merged.xKey;
  const knownDateKeys = ['date', 'inspected_at', 'timestamp', 'time', 'day', 'datetime', 'x'];
  const detectedXKey = explicitXKey ||
    knownDateKeys.find((k) => k in firstPoint) ||
    Object.keys(firstPoint).find((k) => typeof firstPoint[k] === 'string') ||
    'date';

  // Normalize points: guarantee valid date string and numeric series
  const chartPoints = rawPoints.map((pt: any) => {
    const rawDate = pt[detectedXKey] || pt.date || pt.inspected_at || pt.timestamp || '';
    const dateStr = typeof rawDate === 'string' ? rawDate.split('T')[0] : String(rawDate);
    const normalized: Record<string, any> = {
      ...pt,
      [detectedXKey]: dateStr,
      date: dateStr,
    };

    // Ensure all numeric fields are numbers
    Object.keys(pt).forEach((k) => {
      if (k !== detectedXKey && k !== 'date' && !isNaN(Number(pt[k])) && pt[k] !== '' && pt[k] !== null) {
        normalized[k] = Number(pt[k]);
      }
    });

    return normalized;
  });

  // Determine which lines to draw
  const hasWellhead = 'wellhead_temp_c' in firstPoint || chartPoints.some(p => p.wellhead_temp_c !== undefined);
  const hasAmbient = 'ambient_temp_c' in firstPoint || chartPoints.some(p => p.ambient_temp_c !== undefined);
  const hasDelta = 'delta_temp_c' in firstPoint || chartPoints.some(p => p.delta_temp_c !== undefined);

  // If no known temperature fields, find any other numeric keys
  const customNumericKeys = (!hasWellhead && !hasAmbient)
    ? Object.keys(firstPoint).filter(k => k !== detectedXKey && k !== 'date' && !isNaN(Number(firstPoint[k])))
    : [];

  const SERIES_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];

  return (
    <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      <div className="flex items-start justify-between pb-3 border-b border-white/[0.08] mb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <span>{title}</span>
          </h3>
          {subtitle && (
            <p className="text-xs text-neutral-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="w-full h-64 sm:h-72 min-h-[256px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartPoints} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis 
              dataKey="date" 
              stroke="#737373" 
              fontSize={11} 
              tickLine={false}
              tick={{ fill: '#a3a3a3' }}
              tickFormatter={(d) => {
                try {
                  const parts = String(d).split('-');
                  if (parts.length >= 3) return `${parts[1]}/${parts[2]}`;
                  return String(d);
                } catch {
                  return String(d);
                }
              }}
            />
            <YAxis 
              stroke="#737373" 
              fontSize={11} 
              unit={hasWellhead || hasAmbient ? "°C" : ""} 
              tickLine={false} 
              tick={{ fill: '#a3a3a3' }}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#181820', 
                borderColor: 'rgba(255,255,255,0.12)', 
                borderRadius: '0.75rem', 
                fontSize: '12px',
                color: '#fff' 
              }} 
            />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />

            {/* Red Reference Bands for Downtime */}
            {statusBands?.map((band: any, idx: number) => (
              <ReferenceArea
                key={idx}
                x1={band.startDate}
                x2={band.endDate}
                fill={band.fillColor || "rgba(239, 68, 68, 0.18)"}
                stroke="rgba(239, 68, 68, 0.4)"
                strokeDasharray="3 3"
              />
            ))}

            {/* Threshold line if provided */}
            {thresholdLine && (
              <ReferenceLine
                y={thresholdLine.value}
                stroke="#f59e0b"
                strokeDasharray="3 3"
                label={{ value: thresholdLine.label, fill: '#f59e0b', fontSize: 10 }}
              />
            )}

            {hasWellhead && (
              <Line 
                type="monotone" 
                dataKey="wellhead_temp_c" 
                name="Wellhead Temp (°C)" 
                stroke="#3b82f6" 
                strokeWidth={2.5} 
                dot={{ r: 3, fill: '#3b82f6' }}
                activeDot={{ r: 5 }}
                isAnimationActive={false}
              />
            )}
            {hasAmbient && (
              <Line 
                type="monotone" 
                dataKey="ambient_temp_c" 
                name="Ambient Air (°C)" 
                stroke="#94a3b8" 
                strokeWidth={1.8} 
                strokeDasharray="4 4"
                dot={{ r: 2, fill: '#94a3b8' }}
                isAnimationActive={false}
              />
            )}
            {hasDelta && !hasAmbient && (
              <Line 
                type="monotone" 
                dataKey="delta_temp_c" 
                name="ΔT Temp Delta (°C)" 
                stroke="#10b981" 
                strokeWidth={2} 
                dot={{ r: 3, fill: '#10b981' }}
                isAnimationActive={false}
              />
            )}
            {customNumericKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={key.replace(/_/g, ' ')}
                stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Citations Footer */}
      {citations && citations.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex flex-wrap gap-1.5">
          {citations.map((c: any, i: number) => (
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
