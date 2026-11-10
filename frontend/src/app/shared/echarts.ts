import { BarChart, HeatmapChart, LineChart } from 'echarts/charts';
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  AriaComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export { echarts };

/**
 * Chart ink/surface values, read straight from the design tokens on <html> so
 * a chart can never drift from the UI around it (and re-skins on theme
 * toggle). Falls back to the light values if a property is missing.
 */
export interface ChartTheme {
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  brand: string;
  categorical: [string, string, string, string];
}

function token(name: string, fallback: string): string {
  if (typeof getComputedStyle !== 'function') return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return raw ? `rgb(${raw})` : fallback;
}

export function chartTheme(): ChartTheme {
  return {
    ink: token('--ink-950', 'rgb(23 23 26)'),
    muted: token('--ink-400', 'rgb(161 161 170)'),
    grid: token('--stroke-200', 'rgb(235 235 237)'),
    surface: token('--surface-0', 'rgb(255 255 255)'),
    brand: token('--brand-500', 'rgb(219 118 88)'),
    // Fixed order — the ordering is the colour-blind-safety mechanism.
    categorical: [
      token('--chart-1', 'rgb(42 120 214)'),
      token('--chart-2', 'rgb(237 161 0)'),
      token('--chart-3', 'rgb(27 175 122)'),
      token('--chart-4', 'rgb(74 58 167)'),
    ],
  };
}

/** Shared base: recessive axes, hairline grid, tooltip on the card surface. */
export function baseChartOptions(theme: ChartTheme) {
  return {
    aria: { enabled: true },
    animationDuration: 320,
    textStyle: {
      color: theme.muted,
      fontFamily: 'Inter Variable, Inter, ui-sans-serif, system-ui, sans-serif',
      fontSize: 12,
    },
    tooltip: {
      backgroundColor: theme.surface,
      borderColor: theme.grid,
      borderWidth: 1,
      padding: [6, 10],
      textStyle: { color: theme.ink, fontSize: 12 },
      extraCssText: 'box-shadow: 0 6px 16px -4px rgb(0 0 0 / 0.18); border-radius: 8px;',
    },
  };
}
