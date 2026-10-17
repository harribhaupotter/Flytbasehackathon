import React, { useState } from 'react';
import { Table, Search, FileText } from 'lucide-react';

interface Column {
  key: string;
  label: string;
  type?: 'text' | 'number' | 'badge' | 'date';
}

interface DataTableProps {
  data: {
    title: string;
    subtitle?: string;
    columns: Column[];
    rows: Array<Record<string, any>>;
    citations?: Array<{ id: string; title: string }>;
  };
}

export const DataTable: React.FC<DataTableProps> = ({ data: rawData }) => {
  const raw: any = rawData;
  const data: any = {
    ...raw,
    ...(raw?.props || {}),
    ...(raw?.data || {}),
  };

  const [search, setSearch] = useState('');

  // Normalize columns: accept columns or headers
  let columns: Column[] = data.columns || [];
  if (!columns.length && data.headers && Array.isArray(data.headers)) {
    columns = data.headers.map((h: string, idx: number) => ({
      key: `col_${idx}`,
      label: h,
    }));
  }

  // Normalize rows: convert array of arrays to key-value objects
  const rawRows = data.rows || [];
  const rows = rawRows.map((r: any) => {
    if (Array.isArray(r)) {
      const rowObj: Record<string, any> = {};
      r.forEach((val, idx) => {
        const key = columns[idx]?.key || `col_${idx}`;
        rowObj[key] = val;
      });
      return rowObj;
    }
    return r;
  });

  const filteredRows = rows.filter((row: any) => {
    if (!search.trim()) return true;
    return Object.values(row).some(
      (val) => val && String(val).toLowerCase().includes(search.toLowerCase())
    );
  });

  return (
    <div className="w-full max-w-3xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      {/* Table Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-white/[0.08] gap-2 mb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
            <Table className="w-4 h-4 text-blue-400" />
            <span>{data.title}</span>
          </h3>
          {data.subtitle && (
            <p className="text-xs text-neutral-400 mt-0.5">{data.subtitle}</p>
          )}
        </div>

        {rows.length > 5 && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-neutral-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter records..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1 text-xs rounded-xl bg-white/[0.04] border border-white/[0.08] text-white focus:outline-none focus:border-blue-500/50 w-full sm:w-44"
            />
          </div>
        )}
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
        <table className="w-full text-left text-xs text-neutral-300">
          <thead className="bg-white/[0.04] text-[11px] font-semibold text-neutral-400 uppercase tracking-wider border-b border-white/[0.06]">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="py-2.5 px-3">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {filteredRows.length > 0 ? (
              filteredRows.map((row: any, i: number) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                  {columns.map((col) => {
                    const val = row[col.key];
                    return (
                      <td key={col.key} className="py-2 px-3 whitespace-nowrap">
                        {col.key === 'well' || col.key === 'asset_id' ? (
                          <span className="font-mono font-semibold text-blue-400">{val}</span>
                        ) : col.key === 'status' || col.key === 'dynamic_status' ? (
                          <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                            val === 'producing' || val === 'active' 
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' 
                              : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                          }`}>
                            {val}
                          </span>
                        ) : typeof val === 'number' ? (
                          <span className="font-mono">{val}</span>
                        ) : (
                          <span>{val ?? '—'}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="py-4 text-center text-neutral-500">
                  No matching records found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Citations Footer */}
      {data.citations && data.citations.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex flex-wrap gap-1.5">
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
