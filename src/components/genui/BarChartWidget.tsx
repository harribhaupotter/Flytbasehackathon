import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { BarChart3, FileText } from 'lucide-react';

interface BarChartWidgetProps {
  data: {
    title: string;
    subtitle?: string;
    xAxisKey?: string;
    dataKey?: string;
    unit?: string;
    data?: Array<Record<string, any>>;
    points?: Array<Record<string, any>>;
    series?: Array<Record<string, any>>;
    rows?: Array<Record<string, any>>;
    citations?: Array<{ id: string; title: string }>;
  };
}

const BAR_COLORS = ['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe'];

export const BarChartWidget: React.FC<BarChartWidgetProps> = ({ data: rawData }) => {
  const raw: any = rawData || {};
  // Safely extract props without spreading arrays into numeric keys
  const nestedProps = (raw.props && typeof raw.props === 'object' && !Array.isArray(raw.props)) ? raw.props : {};
  const nestedData = (raw.data && typeof raw.data === 'object' && !Array.isArray(raw.data)) ? raw.data : {};

  const merged: any = {
    ...raw,
    ...nestedProps,
    ...nestedData,
  };

  const title = merged.title || 'Bar Chart';
  const subtitle = merged.subtitle;
  const unit = merged.unit || '';
  const citations = merged.citations || [];

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
  } else if (Array.isArray(merged.items)) {
    rawPoints = merged.items;
  }

  if (!rawPoints || rawPoints.length === 0) {
    return (
      <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
        <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
          <BarChart3 className="w-4 h-4 text-blue-400" />
          <span>{title}</span>
        </h3>
        {subtitle && <p className="text-xs text-neutral-400 mt-0.5">{subtitle}</p>}
        <div className="h-32 flex items-center justify-center text-xs text-neutral-500">
          No chart data available
        </div>
      </div>
    );
  }

  const firstPoint = rawPoints[0] || {};

  // Auto-detect category key for X-Axis
  const explicitXKey = merged.xAxisKey || merged.xKey;
  const knownXKeys = ['name', 'well_name', 'well', 'asset_id', 'label', 'category', 'area', 'area_name', 'id', 'date', 'month', 'x'];
  const detectedXKey = explicitXKey ||
    knownXKeys.find((k) => k in firstPoint && typeof firstPoint[k] === 'string') ||
    knownXKeys.find((k) => k in firstPoint) ||
    Object.keys(firstPoint).find((k) => typeof firstPoint[k] === 'string') ||
    Object.keys(firstPoint)[0] ||
    'name';

  // Auto-detect metric key for Bar values
  const explicitValKey = merged.dataKey || merged.valKey || merged.yKey || merged.valueKey;
  const knownValKeys = [
    'value', 'downtime_days', 'downtime_hours', 'downtime', 'days', 'hours', 
    'spill_est_volume_bbl', 'spill_bbl', 'volume', 'count', 'total', 'delta_temp_c', 'y'
  ];
  const detectedValKey = explicitValKey ||
    knownValKeys.find((k) => k in firstPoint && !isNaN(Number(firstPoint[k]))) ||
    Object.keys(firstPoint).find((k) => k !== detectedXKey && !isNaN(Number(firstPoint[k]))) ||
    'value';

  // Normalize data points: guarantee 'name' (X axis) and 'value' (Bar height) exist and are properly typed
  const chartPoints = rawPoints.map((pt: any) => {
    const rawVal = pt[detectedValKey] !== undefined ? pt[detectedValKey] : (pt.value ?? pt.downtime_days ?? pt.days ?? 0);
    const numVal = typeof rawVal === 'number' ? rawVal : (Number(rawVal) || 0);
    const rawX = pt[detectedXKey] !== undefined ? pt[detectedXKey] : (pt.name ?? pt.well_name ?? pt.well ?? pt.label ?? '');
    const strX = String(rawX);

    return {
      ...pt,
      [detectedXKey]: strX,
      [detectedValKey]: numVal,
      name: strX,
      value: numVal,
    };
  });

  return (
    <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      <div className="flex items-start justify-between pb-3 border-b border-white/[0.08] mb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            <span>{title}</span>
          </h3>
          {subtitle && (
            <p className="text-xs text-neutral-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="w-full h-60 sm:h-64 min-h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartPoints} margin={{ top: 10, right: 20, left: -10, bottom: 25 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis 
              dataKey="name" 
              stroke="#737373" 
              fontSize={11} 
              tickLine={false}
              interval={0}
              tick={{ fill: '#a3a3a3' }}
            />
            <YAxis 
              stroke="#737373" 
              fontSize={11} 
              unit={unit ? ` ${unit}` : ''} 
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
              formatter={(val: any) => [`${val}${unit ? ` ${unit}` : ''}`, detectedValKey.replace(/_/g, ' ')]}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} isAnimationActive={false}>
              {chartPoints.map((_: any, index: number) => (
                <Cell key={`cell-${index}`} fill={BAR_COLORS[index % BAR_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
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
