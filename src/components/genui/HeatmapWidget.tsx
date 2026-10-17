import React from 'react';
import { Grid, FileText } from 'lucide-react';

interface HeatmapWidgetProps {
  data: {
    title: string;
    subtitle?: string;
    months?: string[];
    rows: Array<{
      area: string;
      values: number[];
      total?: number;
    }>;
    citations?: Array<{ id: string; title: string }>;
  };
}

const DEFAULT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'];

export const HeatmapWidget: React.FC<HeatmapWidgetProps> = ({ data }) => {
  const months = data.months || DEFAULT_MONTHS;
  const rows = data.rows || [];

  // Determine max value for dynamic color scaling
  const allVals = rows.flatMap((r) => r.values);
  const maxVal = Math.max(...(allVals.length ? allVals : [1]), 1);

  const getCellColor = (val: number) => {
    if (val === 0) return 'bg-white/[0.02] text-neutral-500';
    const intensity = val / maxVal;
    if (intensity < 0.3) return 'bg-rose-500/20 text-rose-300 font-semibold';
    if (intensity < 0.6) return 'bg-rose-500/40 text-rose-200 font-bold';
    return 'bg-rose-600/70 text-white font-extrabold shadow-sm';
  };

  return (
    <div className="w-full max-w-3xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      <div className="flex items-start justify-between pb-3 border-b border-white/[0.08] mb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
            <Grid className="w-4 h-4 text-rose-400" />
            <span>{data.title}</span>
          </h3>
          {data.subtitle && (
            <p className="text-xs text-neutral-400 mt-0.5">{data.subtitle}</p>
          )}
        </div>
      </div>

      {/* Heatmap Grid Table */}
      <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
        <table className="w-full text-center text-xs">
          <thead className="bg-white/[0.04] text-[10px] text-neutral-400 uppercase tracking-wider border-b border-white/[0.06]">
            <tr>
              <th className="py-2.5 px-3 text-left">Area</th>
              {months.map((m, i) => (
                <th key={i} className="py-2 px-1.5 min-w-[32px] sm:min-w-[40px]">
                  {m}
                </th>
              ))}
              <th className="py-2.5 px-3 font-bold text-white">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {rows.map((row, rIdx) => {
              const rowTotal = row.total ?? row.values.reduce((a, b) => a + b, 0);
              return (
                <tr key={rIdx} className="hover:bg-white/[0.01]">
                  <td className="py-2 px-3 text-left font-medium text-neutral-200 whitespace-nowrap text-xs">
                    {row.area}
                  </td>
                  {row.values.map((val, cIdx) => (
                    <td key={cIdx} className="p-1">
                      <div className={`h-8 w-full rounded-lg flex items-center justify-center font-mono text-[11px] ${getCellColor(val)}`}>
                        {val}
                      </div>
                    </td>
                  ))}
                  <td className="py-2 px-3 font-mono font-bold text-rose-300">
                    {rowTotal}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Citations Footer */}
      {data.citations && data.citations.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex flex-wrap gap-1.5">
          {data.citations.map((c, i) => (
            <span key={i} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 text-[10px] font-mono border border-blue-500/20">
              <FileText className="w-2.5 h-2.5" />
              <span>{c.id}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
