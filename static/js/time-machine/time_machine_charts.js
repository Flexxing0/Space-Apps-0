/* Gráfico del equipo: sólo presenta anomalías recibidas del backend. */
(() => {
  const chartInstances = {};
  function renderAnomalyBarChart(canvasId, timeline = [], variable = 'T2M', unitLabel = '°C', activeYear = null, onYearClick = null) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') return null;

    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
      delete chartInstances[canvasId];
    }

    const years = timeline.map((p) => p.year);
    const anomalies = timeline.map((p) => Number(p.anomaly.toFixed(3)));
    const colors = timeline.map((p) => p.color || '#64748b');
    const borderWidths = timeline.map((p) => (p.year === Number(activeYear) ? 2.5 : 1));
    const borderColors = timeline.map((p) => (p.year === Number(activeYear) ? '#0f172a' : 'rgba(15, 23, 42, 0.25)'));

    const ctx = canvas.getContext('2d');
    chartInstances[canvasId] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: years,
        datasets: [
          {
            label: `Anomalía vs media del período (${unitLabel})`,
            data: anomalies,
            backgroundColor: colors,
            borderColor: borderColors,
            borderWidth: borderWidths,
            borderRadius: 3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (_, elements) => {
          if (typeof onYearClick === 'function' && elements && elements.length > 0) {
            const idx = elements[0].index;
            if (years[idx] !== undefined) onYearClick(years[idx]);
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(11, 19, 43, 0.94)',
            callbacks: {
              label: (context) => {
                const pt = timeline[context.dataIndex];
                const sign = context.parsed.y >= 0 ? '+' : '';
                const zStr = pt ? ` (z = ${pt.z_score >= 0 ? '+' : ''}${pt.z_score.toFixed(2)})` : '';
                return ` Anomalía: ${sign}${context.parsed.y.toFixed(2)} ${unitLabel}${zStr}`;
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 13 }
          },
          y: {
            title: { display: true, text: `Anomalía (${unitLabel})`, font: { weight: '600' } },
            grid: { color: 'rgba(226, 232, 240, 0.7)' }
          }
        }
      }
    });

    return chartInstances[canvasId];
  }

  Object.assign(EarthLensCharts, {renderAnomalyBarChart});
})();
