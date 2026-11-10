import * as echarts from 'echarts/core';
import { HeatmapChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
echarts.use([
  HeatmapChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  AriaComponent,
  CanvasRenderer,
]);
export { echarts };
