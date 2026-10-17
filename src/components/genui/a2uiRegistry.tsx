import React from 'react';
import { ComponentRegistry, A2UIViewer, A2UIProvider, initializeDefaultCatalog } from '@a2ui/react/v0_8';
import { injectStyles } from '@a2ui/react/styles';
import { StatusCard } from './StatusCard';
import { DataTable } from './DataTable';
import { LineChartWidget } from './LineChartWidget';
import { BarChartWidget } from './BarChartWidget';
import { GeoMapWidget } from './GeoMapWidget';
import { HeatmapWidget } from './HeatmapWidget';
import { ConflictAlert } from './ConflictAlert';

// Initialize Google's official default A2UI catalog (Card, Column, Row, Text, List, Divider, etc.)
initializeDefaultCatalog();
try {
  injectStyles();
} catch (e) {
  // Guard for server-side or non-DOM environments
}

// Adapter HOC to bridge A2UI node/surface props with domain component props
function createA2UIAdapter(
  Component: React.ComponentType<any>
): React.FC<any> {
  const Adapter: React.FC<any> = (props) => {
    // A2UI v0.8 passes { node, surfaceId } where node holds properties/data
    const resolvedData = props.node
      ? (props.node.properties || props.node.data || props.node)
      : (props.data || props);

    return <Component data={resolvedData} {...props} />;
  };
  Adapter.displayName = `A2UIAdapter(${Component.displayName || Component.name || 'Component'})`;
  return Adapter;
}

// Instantiate the singleton A2UI Component Registry
export const a2uiRegistry = ComponentRegistry.getInstance();

// Register all Generative UI domain components in Google's A2UI ComponentRegistry
a2uiRegistry.register('StatusCard', { component: createA2UIAdapter(StatusCard) });
a2uiRegistry.register('DataTable', { component: createA2UIAdapter(DataTable) });
a2uiRegistry.register('LineChart', { component: createA2UIAdapter(LineChartWidget) });
a2uiRegistry.register('LineChartWidget', { component: createA2UIAdapter(LineChartWidget) });
a2uiRegistry.register('BarChart', { component: createA2UIAdapter(BarChartWidget) });
a2uiRegistry.register('BarChartWidget', { component: createA2UIAdapter(BarChartWidget) });
a2uiRegistry.register('GeoMap', { component: createA2UIAdapter(GeoMapWidget) });
a2uiRegistry.register('GeoMapWidget', { component: createA2UIAdapter(GeoMapWidget) });
a2uiRegistry.register('Heatmap', { component: createA2UIAdapter(HeatmapWidget) });
a2uiRegistry.register('HeatmapWidget', { component: createA2UIAdapter(HeatmapWidget) });
a2uiRegistry.register('ConflictAlert', { component: createA2UIAdapter(ConflictAlert) });

export { A2UIViewer, A2UIProvider };
