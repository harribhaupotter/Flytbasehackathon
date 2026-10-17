import React from 'react';
import { A2UIViewer, A2UIProvider } from '@a2ui/react/v0_8';
import { GenUIComponentPayload } from '../../types';

interface GenUIDispatcherProps {
  payload: GenUIComponentPayload | any;
}

// Helper to format string values for Google A2UI v0.8 schema compatibility
function litStr(val: any): { literalString: string } | any {
  if (val && typeof val === 'object' && ('literalString' in val || 'path' in val || 'literal' in val)) {
    return val;
  }
  return { literalString: String(val ?? '') };
}

// Transform BarChart into pure Google A2UI declarative components (Card, Column, Row, Text, Divider)
function compileBarChartToA2UI(data: any) {
  const title = data.title || 'Bar Chart';
  const subtitle = data.subtitle;
  const unit = data.unit || '';
  const citations = data.citations || [];
  const rawPoints = Array.isArray(data.data) ? data.data : (data.points || data.rows || data.series || []);

  const components: any[] = [];
  const mainColChildren: string[] = ['header-title'];

  components.push({
    id: 'header-title',
    component: { Text: { text: litStr(`### 📊 ${title}`), usageHint: 'h3' } }
  });

  if (subtitle) {
    mainColChildren.push('header-subtitle');
    components.push({
      id: 'header-subtitle',
      component: { Text: { text: litStr(`*${subtitle}*`), usageHint: 'caption' } }
    });
  }

  mainColChildren.push('divider-top');
  components.push({ id: 'divider-top', component: { Divider: {} } });

  const maxVal = Math.max(
    ...rawPoints.map((p: any) => Number(p.value ?? p.downtime_days ?? p.days ?? p.downtime ?? p.hours ?? 0)),
    1
  );

  rawPoints.forEach((p: any, idx: number) => {
    const name = p.name ?? p.well_name ?? p.well ?? p.asset_id ?? p.label ?? `Item ${idx + 1}`;
    const rawNum = p.value ?? p.downtime_days ?? p.days ?? p.downtime ?? p.hours ?? 0;
    const val = typeof rawNum === 'number' ? rawNum : (Number(rawNum) || 0);

    const barLength = 20;
    const filledCount = Math.min(barLength, Math.max(1, Math.round((val / maxVal) * barLength)));
    const barVisual = '█'.repeat(filledCount) + '░'.repeat(barLength - filledCount);

    const rowId = `bar-row-${idx}`;
    const nameId = `name-${idx}`;
    const barId = `bar-${idx}`;
    const valId = `val-${idx}`;

    components.push({
      id: nameId,
      component: { Text: { text: litStr(`**${name}**`), usageHint: 'body' } }
    });
    components.push({
      id: barId,
      component: { Text: { text: litStr(`\`${barVisual}\``), usageHint: 'body' } }
    });
    components.push({
      id: valId,
      component: { Text: { text: litStr(`**${val}${unit ? ' ' + unit : ''}**`), usageHint: 'body' } }
    });

    components.push({
      id: rowId,
      component: { Row: { children: [nameId, barId, valId] } }
    });
    mainColChildren.push(rowId);
  });

  if (citations && citations.length > 0) {
    mainColChildren.push('divider-footer');
    components.push({ id: 'divider-footer', component: { Divider: {} } });

    const citationIds: string[] = [];
    citations.forEach((c: any, i: number) => {
      const citId = `cit-${i}`;
      const citLabel = typeof c === 'string' ? c : (c.id || c.title || `CIT-${i}`);
      components.push({
        id: citId,
        component: { Text: { text: litStr(`🔍 \`${citLabel}\``), usageHint: 'caption' } }
      });
      citationIds.push(citId);
    });

    mainColChildren.push('citations-row');
    components.push({
      id: 'citations-row',
      component: { Row: { children: citationIds } }
    });
  }

  components.push({
    id: 'main-col',
    component: { Column: { children: mainColChildren } }
  });

  components.push({
    id: 'root',
    component: { Card: { child: 'main-col' } }
  });

  return { root: 'root', components };
}

// Transform DataTable into pure Google A2UI declarative components
function compileDataTableToA2UI(data: any) {
  const title = data.title || 'Data Table';
  const subtitle = data.subtitle;
  const citations = data.citations || [];
  const rows: any[] = Array.isArray(data.rows) ? data.rows : (Array.isArray(data.data) ? data.data : []);

  // Determine columns
  let columns: Array<{ key: string; header: string }> = data.columns || [];
  if (!columns.length && rows.length > 0) {
    columns = Object.keys(rows[0])
      .filter((k) => k !== 'citations')
      .map((k) => ({ key: k, header: k.replace(/_/g, ' ').toUpperCase() }));
  }

  const components: any[] = [];
  const mainColChildren: string[] = ['table-title'];

  components.push({
    id: 'table-title',
    component: { Text: { text: litStr(`### 📋 ${title}`), usageHint: 'h3' } }
  });

  if (subtitle) {
    mainColChildren.push('table-subtitle');
    components.push({
      id: 'table-subtitle',
      component: { Text: { text: litStr(`*${subtitle}*`), usageHint: 'caption' } }
    });
  }

  mainColChildren.push('table-div-1');
  components.push({ id: 'table-div-1', component: { Divider: {} } });

  // Column Headers Row
  const headerColIds: string[] = [];
  columns.forEach((col, idx) => {
    const colId = `th-${idx}`;
    components.push({
      id: colId,
      component: { Text: { text: litStr(`**${col.header}**`), usageHint: 'body' } }
    });
    headerColIds.push(colId);
  });

  mainColChildren.push('table-header-row');
  components.push({
    id: 'table-header-row',
    component: { Row: { children: headerColIds } }
  });

  mainColChildren.push('table-div-2');
  components.push({ id: 'table-div-2', component: { Divider: {} } });

  // Data Rows
  rows.forEach((row: any, rIdx: number) => {
    const rowCellIds: string[] = [];
    columns.forEach((col, cIdx) => {
      const cellId = `td-${rIdx}-${cIdx}`;
      const cellVal = row[col.key] !== undefined ? String(row[col.key]) : '';
      components.push({
        id: cellId,
        component: { Text: { text: litStr(cellVal), usageHint: 'body' } }
      });
      rowCellIds.push(cellId);
    });

    const rowId = `tr-${rIdx}`;
    components.push({
      id: rowId,
      component: { Row: { children: rowCellIds } }
    });
    mainColChildren.push(rowId);
  });

  if (citations && citations.length > 0) {
    mainColChildren.push('table-div-foot');
    components.push({ id: 'table-div-foot', component: { Divider: {} } });

    const citationIds: string[] = [];
    citations.forEach((c: any, i: number) => {
      const citId = `cit-${i}`;
      const citLabel = typeof c === 'string' ? c : (c.id || c.title || `CIT-${i}`);
      components.push({
        id: citId,
        component: { Text: { text: litStr(`🔍 \`${citLabel}\``), usageHint: 'caption' } }
      });
      citationIds.push(citId);
    });

    mainColChildren.push('table-citations-row');
    components.push({
      id: 'table-citations-row',
      component: { Row: { children: citationIds } }
    });
  }

  components.push({
    id: 'main-col',
    component: { Column: { children: mainColChildren } }
  });

  components.push({
    id: 'root',
    component: { Card: { child: 'main-col' } }
  });

  return { root: 'root', components };
}

// Transform LineChart into pure Google A2UI declarative components
function compileLineChartToA2UI(data: any) {
  const title = data.title || 'Telemetry Timeline';
  const subtitle = data.subtitle;
  const citations = data.citations || [];
  const points: any[] = Array.isArray(data.data) ? data.data : (data.points || data.series || []);

  const components: any[] = [];
  const mainColChildren: string[] = ['line-title'];

  components.push({
    id: 'line-title',
    component: { Text: { text: litStr(`### 📈 ${title}`), usageHint: 'h3' } }
  });

  if (subtitle) {
    mainColChildren.push('line-subtitle');
    components.push({
      id: 'line-subtitle',
      component: { Text: { text: litStr(`*${subtitle}*`), usageHint: 'caption' } }
    });
  }

  mainColChildren.push('line-div-1');
  components.push({ id: 'line-div-1', component: { Divider: {} } });

  // Telemetry Header
  const headerIds = ['th-date', 'th-wellhead', 'th-ambient', 'th-delta', 'th-status'];
  components.push({ id: 'th-date', component: { Text: { text: litStr('**Date**'), usageHint: 'body' } } });
  components.push({ id: 'th-wellhead', component: { Text: { text: litStr('**Wellhead (°C)**'), usageHint: 'body' } } });
  components.push({ id: 'th-ambient', component: { Text: { text: litStr('**Ambient (°C)**'), usageHint: 'body' } } });
  components.push({ id: 'th-delta', component: { Text: { text: litStr('**ΔT Delta (°C)**'), usageHint: 'body' } } });
  components.push({ id: 'th-status', component: { Text: { text: litStr('**Status**'), usageHint: 'body' } } });

  mainColChildren.push('line-header-row');
  components.push({ id: 'line-header-row', component: { Row: { children: headerIds } } });

  mainColChildren.push('line-div-2');
  components.push({ id: 'line-div-2', component: { Divider: {} } });

  // Telemetry records
  points.forEach((p: any, idx: number) => {
    const rawDate = p.date || p.inspected_at || p.timestamp || `T-${idx}`;
    const dateStr = typeof rawDate === 'string' ? rawDate.split('T')[0] : String(rawDate);
    const wellhead = p.wellhead_temp_c !== undefined ? Number(p.wellhead_temp_c).toFixed(1) : '-';
    const ambient = p.ambient_temp_c !== undefined ? Number(p.ambient_temp_c).toFixed(1) : '-';
    
    let delta = '-';
    if (p.delta_temp_c !== undefined) {
      delta = Number(p.delta_temp_c).toFixed(1);
    } else if (p.wellhead_temp_c !== undefined && p.ambient_temp_c !== undefined) {
      delta = (Number(p.wellhead_temp_c) - Number(p.ambient_temp_c)).toFixed(1);
    }

    const isProducing = p.is_producing ?? (Number(delta) >= 15.0);
    const statusText = isProducing ? '🟢 Producing' : '🔴 Non-producing';

    const dId = `td-d-${idx}`;
    const wId = `td-w-${idx}`;
    const aId = `td-a-${idx}`;
    const delId = `td-del-${idx}`;
    const sId = `td-s-${idx}`;

    components.push({ id: dId, component: { Text: { text: litStr(dateStr), usageHint: 'body' } } });
    components.push({ id: wId, component: { Text: { text: litStr(`${wellhead} °C`), usageHint: 'body' } } });
    components.push({ id: aId, component: { Text: { text: litStr(`${ambient} °C`), usageHint: 'body' } } });
    components.push({ id: delId, component: { Text: { text: litStr(`+${delta} °C`), usageHint: 'body' } } });
    components.push({ id: sId, component: { Text: { text: litStr(statusText), usageHint: 'body' } } });

    const rowId = `line-row-${idx}`;
    components.push({ id: rowId, component: { Row: { children: [dId, wId, aId, delId, sId] } } });
    mainColChildren.push(rowId);
  });

  if (citations && citations.length > 0) {
    mainColChildren.push('line-div-foot');
    components.push({ id: 'line-div-foot', component: { Divider: {} } });

    const citationIds: string[] = [];
    citations.forEach((c: any, i: number) => {
      const citId = `cit-${i}`;
      const citLabel = typeof c === 'string' ? c : (c.id || c.title || `CIT-${i}`);
      components.push({
        id: citId,
        component: { Text: { text: litStr(`🔍 \`${citLabel}\``), usageHint: 'caption' } }
      });
      citationIds.push(citId);
    });

    mainColChildren.push('line-citations-row');
    components.push({
      id: 'line-citations-row',
      component: { Row: { children: citationIds } }
    });
  }

  components.push({
    id: 'main-col',
    component: { Column: { children: mainColChildren } }
  });

  components.push({
    id: 'root',
    component: { Card: { child: 'main-col' } }
  });

  return { root: 'root', components };
}

// Transform StatusCard into pure Google A2UI declarative components
function compileStatusCardToA2UI(data: any) {
  const assetId = data.asset_id || data.well_id || 'WELL';
  const name = data.name || data.well_name || assetId;
  const wellType = data.well_type || 'Unknown';
  const dynamicStatus = data.dynamic_status || (data.is_producing ? 'producing' : 'non_producing');
  const isProducing = dynamicStatus === 'producing';
  const wellhead = data.wellhead_temp_c !== undefined ? `${Number(data.wellhead_temp_c).toFixed(1)} °C` : 'N/A';
  const ambient = data.ambient_temp_c !== undefined ? `${Number(data.ambient_temp_c).toFixed(1)} °C` : 'N/A';
  const delta = data.delta_temp_c !== undefined ? `${Number(data.delta_temp_c).toFixed(1)} °C` : 'N/A';
  const threshold = data.threshold_delta_c !== undefined ? `${Number(data.threshold_delta_c).toFixed(1)} °C` : '15.0 °C';
  const inspectedAt = data.inspected_at || 'Recent';
  const inspectorName = data.inspector_name || 'Field Inspector';
  const reason = data.reason_for_stop || data.notes || '';
  const citations = data.citations || [];

  const components: any[] = [];
  const mainColChildren: string[] = ['status-header-row'];

  components.push({
    id: 'status-title',
    component: { Text: { text: litStr(`### ⚡ ${name} (${assetId})`), usageHint: 'h3' } }
  });
  components.push({
    id: 'status-badge',
    component: {
      Text: {
        text: litStr(isProducing ? '🟢 **DYNAMICALLY PRODUCING**' : '🔴 **NON-PRODUCING**'),
        usageHint: 'body'
      }
    }
  });

  components.push({
    id: 'status-header-row',
    component: { Row: { children: ['status-title', 'status-badge'] } }
  });

  mainColChildren.push('status-div-1');
  components.push({ id: 'status-div-1', component: { Divider: {} } });

  // Key metrics
  const metricPairs = [
    { label: 'Well Type & Threshold', value: `${wellType} (Requires ΔT ≥ ${threshold})` },
    { label: 'Wellhead Temperature', value: wellhead },
    { label: 'Ambient Air Temperature', value: ambient },
    { label: 'Temperature Delta (ΔT)', value: `${delta} (Dynamic Status: ${isProducing ? 'MET' : 'BELOW THRESHOLD'})` },
    { label: 'Last Inspected', value: `${inspectedAt} by ${inspectorName}` },
  ];

  if (!isProducing && reason) {
    metricPairs.push({ label: 'Reason for Inactivity / Stop', value: reason });
  }

  metricPairs.forEach((pair, idx) => {
    const rowId = `meta-row-${idx}`;
    const lblId = `lbl-${idx}`;
    const valId = `v-${idx}`;

    components.push({ id: lblId, component: { Text: { text: litStr(`**${pair.label}:**`), usageHint: 'body' } } });
    components.push({ id: valId, component: { Text: { text: litStr(pair.value), usageHint: 'body' } } });
    components.push({ id: rowId, component: { Row: { children: [lblId, valId] } } });
    mainColChildren.push(rowId);
  });

  if (citations && citations.length > 0) {
    mainColChildren.push('status-div-foot');
    components.push({ id: 'status-div-foot', component: { Divider: {} } });

    const citationIds: string[] = [];
    citations.forEach((c: any, i: number) => {
      const citId = `cit-${i}`;
      const citLabel = typeof c === 'string' ? c : (c.id || c.title || `CIT-${i}`);
      components.push({
        id: citId,
        component: { Text: { text: litStr(`🔍 \`${citLabel}\``), usageHint: 'caption' } }
      });
      citationIds.push(citId);
    });

    mainColChildren.push('status-citations-row');
    components.push({
      id: 'status-citations-row',
      component: { Row: { children: citationIds } }
    });
  }

  components.push({
    id: 'main-col',
    component: { Column: { children: mainColChildren } }
  });

  components.push({
    id: 'root',
    component: { Card: { child: 'main-col' } }
  });

  return { root: 'root', components };
}

// Transform Heatmap into pure Google A2UI declarative components
function compileHeatmapToA2UI(data: any) {
  const title = data.title || 'Spill Incident Heatmap';
  const subtitle = data.subtitle;
  const citations = data.citations || [];

  const xLabels: string[] = data.xLabels || data.columns || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const yLabels: string[] = data.yLabels || data.areas || (Array.isArray(data.rows) ? data.rows.map((r: any) => r.area || r.name || r.Area) : []);
  const matrix: number[][] = Array.isArray(data.data) && Array.isArray(data.data[0])
    ? data.data
    : (data.matrix || []);

  let formattedRows: any[] = [];
  if (matrix.length > 0 && yLabels.length > 0) {
    formattedRows = yLabels.map((area, yIdx) => {
      const rowObj: Record<string, any> = { Area: `**${area}**` };
      const rowData = matrix[yIdx] || [];
      xLabels.forEach((col, xIdx) => {
        const val = rowData[xIdx] ?? 0;
        if (val === 0) {
          rowObj[col] = '·';
        } else if (val >= 10) {
          rowObj[col] = `🔴 ${val}`;
        } else if (val >= 5) {
          rowObj[col] = `🟡 ${val}`;
        } else {
          rowObj[col] = `🟢 ${val}`;
        }
      });
      return rowObj;
    });
  } else if (Array.isArray(data.rows)) {
    formattedRows = data.rows;
  }

  const tableColumns = [
    { key: 'Area', header: 'GEOGRAPHIC AREA' },
    ...xLabels.map((xl) => ({ key: xl, header: xl.toUpperCase() }))
  ];

  return compileDataTableToA2UI({
    title: `🔥 ${title}`,
    subtitle: subtitle || 'Color-coded intensity matrix (🟢 Low: 1-4 | 🟡 Moderate: 5-9 | 🔴 High Hotspot: 10+)',
    citations,
    columns: tableColumns,
    rows: formattedRows
  });
}

// Transform GeoMap into pure Google A2UI declarative components
function compileGeoMapToA2UI(data: any) {
  const title = data.title || 'Field Asset Geospatial Map';
  const subtitle = data.subtitle || 'Geographic distribution and real-time operational status';
  const citations = data.citations || [];
  const points = Array.isArray(data.points) ? data.points : (Array.isArray(data.wells) ? data.wells : (Array.isArray(data.data) ? data.data : []));

  const rows = points.map((p: any, idx: number) => {
    const isProd = p.is_producing ?? (p.status === 'producing');
    return {
      'Well ID': p.asset_id || p.well_id || `WELL-${idx + 1}`,
      'Area': p.area_name || p.area_id || 'Field',
      'Well Type': p.well_type || 'T200',
      'Surface Coordinates': p.latitude && p.longitude ? `${Number(p.latitude).toFixed(4)}, ${Number(p.longitude).toFixed(4)}` : (p.location || 'Block Center'),
      'Operational Status': isProd ? '🟢 Dynamic Production' : '🔴 Shut-In / Inactive'
    };
  });

  return compileDataTableToA2UI({
    title: `🗺️ ${title}`,
    subtitle,
    citations,
    rows
  });
}

// Transform any incoming payload into a verified Google A2UI declarative surface
function compileToA2UISurface(payload: any): { root: string; components: any[]; data?: Record<string, any> } | null {
  if (!payload) return null;

  // Case 1: Already a native A2UI surface with root and components
  if (payload.root && Array.isArray(payload.components)) {
    // Normalize string properties for v0.8 schema compatibility
    const normalizedComponents = payload.components.map((comp: any) => {
      if (!comp || !comp.component) return comp;
      const compKey = Object.keys(comp.component)[0];
      const props = comp.component[compKey] || {};

      const cleanProps = { ...props };
      if (compKey === 'Text' && typeof cleanProps.text === 'string') {
        cleanProps.text = litStr(cleanProps.text);
      }
      return {
        ...comp,
        component: { [compKey]: cleanProps }
      };
    });

    return {
      root: payload.root,
      components: normalizedComponents,
      data: payload.data || {}
    };
  }

  const componentName = payload.component || payload.type;
  if (!componentName) return null;

  const data = {
    ...payload,
    ...(payload.props || {}),
    ...(payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data) ? payload.data : {}),
    data: Array.isArray(payload.data) ? payload.data : (payload.props?.data || payload.data)
  };

  switch (componentName) {
    case 'BarChart':
    case 'BarChartWidget':
      return { ...compileBarChartToA2UI(data), data: {} };

    case 'DataTable':
    case 'Table':
      return { ...compileDataTableToA2UI(data), data: {} };

    case 'LineChart':
    case 'LineChartWidget':
      return { ...compileLineChartToA2UI(data), data: {} };

    case 'StatusCard':
      return { ...compileStatusCardToA2UI(data), data: {} };

    case 'Heatmap':
    case 'HeatmapWidget':
      return { ...compileHeatmapToA2UI(data), data: {} };

    case 'GeoMap':
    case 'GeoMapWidget':
      return { ...compileGeoMapToA2UI(data), data: {} };

    case 'ConflictAlert':
    default:
      // Generic Data Table compilation for other domain views
      return {
        ...compileDataTableToA2UI({
          title: data.title || componentName,
          subtitle: data.subtitle || data.area_name,
          citations: data.citations || [],
          rows: Array.isArray(data.rows) ? data.rows : (Array.isArray(data.points) ? data.points : [data])
        }),
        data: {}
      };
  }
}

export const GenUIDispatcher: React.FC<GenUIDispatcherProps> = ({ payload }) => {
  if (!payload) return null;

  // Compile payload into official Google A2UI Declarative Surface
  const a2uiSurface = compileToA2UISurface(payload);
  if (!a2uiSurface) return null;

  // Render 100% through Google's official A2UI SDK (A2UIViewer & A2UIProvider)
  return (
    <div className="a2ui-surface-container my-3 rounded-2xl bg-[#101016] border border-white/[0.1] shadow-xl p-4 text-neutral-100 font-sans">
      <A2UIProvider>
        <A2UIViewer
          root={a2uiSurface.root}
          components={a2uiSurface.components}
          data={a2uiSurface.data || {}}
        />
      </A2UIProvider>
    </div>
  );
};
