/**
 * NTRO Industrial Fire AI - Analytics & Chart.js Visualizer
 */

export class AnalyticsManager {
  constructor() {
    this.categoryChart = null;
    this.frpChart = null;
    this.featureChart = null;
    this.confusionMatrixEl = document.getElementById('confusion-matrix-table');
  }

  renderCategoryDoughnut(canvasId, breakdown) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (this.categoryChart) {
      this.categoryChart.destroy();
    }

    const labels = Object.keys(breakdown);
    const counts = labels.map(k => breakdown[k].count);

    const colors = labels.map(k => {
      if (k.includes('ACCIDENTAL')) return '#ff2a55';
      if (k.includes('PERSISTENT')) return '#ff9800';
      if (k.includes('FOREST') || k.includes('WILDFIRE')) return '#10b981';
      if (k.includes('AGRICULTURAL')) return '#eab308';
      if (k.includes('COAL') || k.includes('MINING')) return '#a855f7';
      return '#06b6d4';
    });

    this.categoryChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels.map(l => l.replace(/_/g, ' ')),
        datasets: [{
          data: counts,
          backgroundColor: colors,
          borderColor: '#121826',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#94a3b8', font: { size: 10, family: 'Inter' } }
          }
        }
      }
    });
  }

  renderFrpDistribution(canvasId, frpBuckets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (this.frpChart) {
      this.frpChart.destroy();
    }

    const labels = Object.keys(frpBuckets);
    const counts = Object.values(frpBuckets);

    this.frpChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Detections by FRP',
          data: counts,
          backgroundColor: '#06b6d4',
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
          y: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  renderFeatureImportances(canvasId, importances) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (this.featureChart) {
      this.featureChart.destroy();
    }

    const entries = Object.entries(importances).slice(0, 8);
    const labels = entries.map(e => e[0].replace(/_/g, ' '));
    const values = entries.map(e => (e[1] * 100).toFixed(1));

    this.featureChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Importance Weight (%)',
          data: values,
          backgroundColor: '#3b82f6',
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
          y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  renderConfusionMatrix(containerId, classes, matrix) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 11px; text-align: center;">
          <thead>
            <tr>
              <th style="padding: 6px; color: #64748b; font-size: 10px; border-bottom: 1px solid rgba(255,255,255,0.1);">True \\ Pred</th>
    `;

    classes.forEach(c => {
      const short = c.replace(/_/g, ' ').slice(0, 10);
      html += `<th style="padding: 6px; color: #06b6d4; border-bottom: 1px solid rgba(255,255,255,0.1);">${short}</th>`;
    });
    html += `</tr></thead><tbody>`;

    matrix.forEach((row, i) => {
      const trueShort = classes[i].replace(/_/g, ' ').slice(0, 10);
      html += `<tr><td style="padding: 6px; color: #94a3b8; text-align: left; font-weight: 600; border-right: 1px solid rgba(255,255,255,0.1);">${trueShort}</td>`;
      row.forEach((val, j) => {
        const isDiag = i === j;
        const bg = isDiag ? 'rgba(6, 182, 212, 0.25)' : (val > 0 ? 'rgba(255, 42, 85, 0.3)' : 'transparent');
        const color = isDiag ? '#fff' : (val > 0 ? '#ff7b92' : '#64748b');
        html += `<td style="padding: 6px; background: ${bg}; color: ${color}; font-weight: ${isDiag ? '700' : '400'}; border: 1px solid rgba(255,255,255,0.05);">${val}</td>`;
      });
      html += `</tr>`;
    });

    html += `</tbody></table></div>`;
    container.innerHTML = html;
  }
}
