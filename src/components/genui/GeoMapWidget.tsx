import React, { useState } from 'react';
import { MapPin, Navigation, FileText, Droplets } from 'lucide-react';

interface MapPoint {
  asset_id: string;
  name?: string;
  lat: number;
  lon: number;
  spill_bbl?: number;
  date?: string;
  status?: string;
}

interface GeoMapWidgetProps {
  data: {
    title: string;
    subtitle?: string;
    area_name?: string;
    points: MapPoint[];
    citations?: Array<{ id: string; title: string }>;
  };
}

export const GeoMapWidget: React.FC<GeoMapWidgetProps> = ({ data }) => {
  const points = data.points || [];
  const [hoveredPoint, setHoveredPoint] = useState<MapPoint | null>(null);

  // Compute bounding box for projection
  const lats = points.map((p) => p.lat);
  const lons = points.map((p) => p.lon);

  const minLat = Math.min(...(lats.length ? lats : [32.1])) - 0.015;
  const maxLat = Math.max(...(lats.length ? lats : [32.2])) + 0.015;
  const minLon = Math.min(...(lons.length ? lons : [-102.2])) - 0.015;
  const maxLon = Math.max(...(lons.length ? lons : [-102.1])) + 0.015;

  const latSpan = maxLat - minLat || 0.01;
  const lonSpan = maxLon - minLon || 0.01;

  // Project lat/lon to SVG 0..100 coordinate space
  const project = (lat: number, lon: number) => {
    const x = ((lon - minLon) / lonSpan) * 100;
    const y = (1 - (lat - minLat) / latSpan) * 100;
    return { x: Math.max(10, Math.min(90, x)), y: Math.max(10, Math.min(90, y)) };
  };

  return (
    <div className="w-full max-w-2xl my-3 p-4 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl text-neutral-100 font-sans">
      <div className="flex items-start justify-between pb-3 border-b border-white/[0.08] mb-3">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white flex items-center space-x-2">
            <Navigation className="w-4 h-4 text-emerald-400" />
            <span>{data.title}</span>
          </h3>
          {data.subtitle && (
            <p className="text-xs text-neutral-400 mt-0.5">{data.subtitle}</p>
          )}
        </div>
        {data.area_name && (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            {data.area_name}
          </span>
        )}
      </div>

      {/* Map Surface */}
      <div className="relative w-full h-72 rounded-xl bg-[#09090D] border border-white/[0.08] overflow-hidden p-2">
        {/* Subtle Map Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:24px_24px]" />

        {/* Compass indicator */}
        <div className="absolute top-3 right-3 text-[10px] font-mono text-neutral-500 flex flex-col items-center">
          <span className="text-neutral-400 font-bold">N</span>
          <span>▲</span>
        </div>

        {/* Map Pins */}
        <div className="relative w-full h-full">
          {points.map((pt, i) => {
            const { x, y } = project(pt.lat, pt.lon);
            const isHovered = hoveredPoint?.asset_id === pt.asset_id;

            return (
              <div
                key={i}
                style={{ left: `${x}%`, top: `${y}%` }}
                onMouseEnter={() => setHoveredPoint(pt)}
                onMouseLeave={() => setHoveredPoint(null)}
                className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-transform duration-150 z-20 group hover:scale-110"
              >
                <div className="relative flex items-center justify-center">
                  <div className="w-8 h-8 rounded-full bg-rose-500/20 animate-ping absolute" />
                  <div className="w-7 h-7 rounded-full bg-rose-600 border-2 border-white shadow-lg flex items-center justify-center text-white">
                    <Droplets className="w-3.5 h-3.5" />
                  </div>
                </div>

                <div className="absolute left-1/2 -translate-x-1/2 mt-1 whitespace-nowrap px-1.5 py-0.5 rounded bg-black/80 border border-white/10 text-[10px] font-mono font-semibold text-white pointer-events-none">
                  {pt.asset_id}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Point Info Drawer */}
        {hoveredPoint && (
          <div className="absolute bottom-2 left-2 right-2 p-2.5 rounded-xl bg-[#181822]/95 border border-white/15 backdrop-blur-md shadow-2xl z-30 flex items-center justify-between text-xs animate-in fade-in slide-in-from-bottom-2">
            <div>
              <div className="font-bold text-white flex items-center space-x-1.5">
                <MapPin className="w-3.5 h-3.5 text-rose-400" />
                <span>{hoveredPoint.asset_id}</span>
                {hoveredPoint.spill_bbl !== undefined && (
                  <span className="text-rose-400 font-mono">({hoveredPoint.spill_bbl} bbl crude)</span>
                )}
              </div>
              <div className="text-[10px] text-neutral-400 font-mono mt-0.5">
                Lat: {hoveredPoint.lat.toFixed(5)}, Lon: {hoveredPoint.lon.toFixed(5)}
                {hoveredPoint.date && ` · ${hoveredPoint.date}`}
              </div>
            </div>
          </div>
        )}
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
