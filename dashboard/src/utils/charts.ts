/**
 * SVG Chart utilities for Truth Core Dashboard
 * No external dependencies - pure SVG generation
 */

export interface ChartData {
  label: string;
  value: number;
  color?: string;
}

export interface BarChartOptions {
  width: number;
  height: number;
  barGap?: number;
  showValues?: boolean;
  showLabels?: boolean;
  valueFormatter?: (value: number) => string;
}

export interface PieChartOptions {
  width: number;
  height: number;
  innerRadius?: number;
  showLegend?: boolean;
  showValues?: boolean;
}

/**
 * Generate a bar chart SVG
 */
export function generateBarChart(
  data: ChartData[],
  options: BarChartOptions
): string {
  const { width, height, barGap = 4, showValues = true, showLabels = true } = options;
  
  const margin = { top: 20, right: 20, bottom: showLabels ? 60 : 20, left: 40 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  
  const maxValue = Math.max(...data.map(d => d.value), 1);
  const barWidth = (chartWidth - (data.length - 1) * barGap) / data.length;
  
  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" class="tc-chart tc-bar-chart">`;
  
  // Background
  svg += `<rect width="${width}" height="${height}" fill="var(--bg-secondary, #f5f5f5)" rx="4"/>`;
  
  // Y-axis grid lines
  const gridCount = 5;
  for (let i = 0; i <= gridCount; i++) {
    const y = margin.top + (chartHeight * i) / gridCount;
    const value = Math.round(maxValue * (gridCount - i) / gridCount);
    svg += `<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" stroke="var(--border-color, #ddd)" stroke-width="1" stroke-dasharray="2,2"/>`;
    svg += `<text x="${margin.left - 5}" y="${y + 3}" text-anchor="end" font-size="10" fill="var(--text-secondary, #666)">${value}</text>`;
  }
  
  // Bars
  data.forEach((d, i) => {
    const barHeight = (d.value / maxValue) * chartHeight;
    const x = margin.left + i * (barWidth + barGap);
    const y = margin.top + chartHeight - barHeight;
    const color = d.color || 'var(--primary, #2563eb)';
    
    svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="${color}" rx="2">`;
    svg += `<title>${d.label}: ${d.value}</title>`;
    svg += `</rect>`;
    
    // Value label
    if (showValues && d.value > 0) {
      svg += `<text x="${x + barWidth / 2}" y="${y - 5}" text-anchor="middle" font-size="10" fill="var(--text-primary, #333)">${d.value}</text>`;
    }
    
    // X-axis label
    if (showLabels) {
      const labelY = height - 10;
      svg += `<text x="${x + barWidth / 2}" y="${labelY}" text-anchor="middle" font-size="10" fill="var(--text-secondary, #666)" transform="rotate(-45, ${x + barWidth / 2}, ${labelY})">${escapeHtml(d.label)}</text>`;
    }
  });
  
  svg += '</svg>';
  return svg;
}

/**
 * Generate a pie/donut chart SVG
 */
export function generatePieChart(
  data: ChartData[],
  options: PieChartOptions
): string {
  const { width, height, innerRadius = 0, showLegend = true } = options;
  
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 20;
  
  const total = data.reduce((sum, d) => sum + d.value, 0);
  let currentAngle = -Math.PI / 2; // Start at top
  
  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" class="tc-chart tc-pie-chart">`;
  
  // Background
  svg += `<rect width="${width}" height="${height}" fill="var(--bg-secondary, #f5f5f5)" rx="4"/>`;
  
  // Default colors
  const defaultColors = [
    '#dc2626', '#ea580c', '#d97706', '#65a30d', '#16a34a', 
    '#0891b2', '#2563eb', '#7c3aed', '#9333ea', '#c026d3'
  ];
  
  // Slices
  data.forEach((d, i) => {
    if (d.value === 0) return;
    
    const sliceAngle = (d.value / total) * 2 * Math.PI;
    const endAngle = currentAngle + sliceAngle;
    
    const x1 = centerX + radius * Math.cos(currentAngle);
    const y1 = centerY + radius * Math.sin(currentAngle);
    const x2 = centerX + radius * Math.cos(endAngle);
    const y2 = centerY + radius * Math.sin(endAngle);
    
    const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;
    
    let path;
    if (innerRadius > 0) {
      // Donut chart
      const innerX1 = centerX + innerRadius * Math.cos(currentAngle);
      const innerY1 = centerY + innerRadius * Math.sin(currentAngle);
      const innerX2 = centerX + innerRadius * Math.cos(endAngle);
      const innerY2 = centerY + innerRadius * Math.sin(endAngle);
      
      path = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2} L ${innerX2} ${innerY2} A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${innerX1} ${innerY1} Z`;
    } else {
      // Pie chart
      path = `M ${centerX} ${centerY} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2} Z`;
    }
    
    const color = d.color || defaultColors[i % defaultColors.length];
    svg += `<path d="${path}" fill="${color}" stroke="white" stroke-width="2">`;
    svg += `<title>${d.label}: ${d.value} (${((d.value / total) * 100).toFixed(1)}%)</title>`;
    svg += `</path>`;
    
    currentAngle = endAngle;
  });
  
  // Legend
  if (showLegend) {
    const legendX = width - 100;
    const legendY = 20;
    
    data.forEach((d, i) => {
      if (d.value === 0) return;
      
      const y = legendY + i * 20;
      const color = d.color || defaultColors[i % defaultColors.length];
      
      svg += `<rect x="${legendX}" y="${y}" width="12" height="12" fill="${color}" rx="2"/>`;
      svg += `<text x="${legendX + 18}" y="${y + 9}" font-size="11" fill="var(--text-primary, #333)">${escapeHtml(d.label)} (${d.value})</text>`;
    });
  }
  
  svg += '</svg>';
  return svg;
}

/**
 * Generate a line/trend chart SVG
 */
export function generateTrendChart(
  data: { x: string; y: number }[],
  options: { width: number; height: number; showPoints?: boolean }
): string {
  const { width, height, showPoints = true } = options;
  
  const margin = { top: 20, right: 20, bottom: 40, left: 40 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  
  const maxY = Math.max(...data.map(d => d.y), 1);
  const minY = Math.min(...data.map(d => d.y), 0);
  const yRange = maxY - minY || 1;
  
  let svg = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" class="tc-chart tc-trend-chart">`;
  
  // Background
  svg += `<rect width="${width}" height="${height}" fill="var(--bg-secondary, #f5f5f5)" rx="4"/>`;
  
  // Grid lines
  const gridCount = 5;
  for (let i = 0; i <= gridCount; i++) {
    const y = margin.top + (chartHeight * i) / gridCount;
    const value = Math.round(maxY - (yRange * i) / gridCount);
    svg += `<line x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}" stroke="var(--border-color, #ddd)" stroke-width="1" stroke-dasharray="2,2"/>`;
    svg += `<text x="${margin.left - 5}" y="${y + 3}" text-anchor="end" font-size="10" fill="var(--text-secondary, #666)">${value}</text>`;
  }
  
  // Line path
  if (data.length > 1) {
    let path = '';
    data.forEach((d, i) => {
      const x = margin.left + (i / (data.length - 1)) * chartWidth;
      const y = margin.top + chartHeight - ((d.y - minY) / yRange) * chartHeight;
      path += (i === 0 ? 'M' : 'L') + ` ${x} ${y}`;
    });
    
    svg += `<path d="${path}" fill="none" stroke="var(--primary, #2563eb)" stroke-width="2"/>`;
  }
  
  // Points
  if (showPoints) {
    data.forEach((d, i) => {
      const x = margin.left + (i / (data.length - 1)) * chartWidth;
      const y = margin.top + chartHeight - ((d.y - minY) / yRange) * chartHeight;
      
      svg += `<circle cx="${x}" cy="${y}" r="4" fill="var(--primary, #2563eb)" stroke="white" stroke-width="2">`;
      svg += `<title>${d.x}: ${d.y}</title>`;
      svg += `</circle>`;
    });
  }
  
  // X-axis labels (show every nth label if many)
  const labelInterval = Math.ceil(data.length / 6);
  data.forEach((d, i) => {
    if (i % labelInterval === 0 || i === data.length - 1) {
      const x = margin.left + (i / (data.length - 1)) * chartWidth;
      svg += `<text x="${x}" y="${height - 10}" text-anchor="middle" font-size="10" fill="var(--text-secondary, #666)">${escapeHtml(d.x)}</text>`;
    }
  });
  
  svg += '</svg>';
  return svg;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
