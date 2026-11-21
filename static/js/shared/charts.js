/**
 * EarthLens — Rol 03: Módulo de Gráficos, Regresión y Utilidades (charts.js)
 * Tecnologías: JavaScript (ES6+), Chart.js
 * Cumple el contrato JSON de POST /api/analyze y POST /api/compare (Página 6 del Plan)
 */

const EarthLensCharts = (() => {
  // Instancias activas de Chart.js por ID de canvas para destruirlas antes de redibujar
  const chartInstances = {};

  // Catálogo oficial de variables del MVP (Página 4 del PDF)
  const VARIABLES_META = {
    T2M: {
      code: 'T2M',
      name: 'Temperatura media a 2m',
      unit: '°C',
      apiUnit: 'deg C',
      color: '#fc3d21',
      decimals: 2
    },
    PRECTOTCORR: {
      code: 'PRECTOTCORR',
      name: 'Precipitaciones corregidas',
      unit: 'mm/día',
      apiUnit: 'mm/day',
      color: '#0ea5e9',
      decimals: 2
    },
    RH2M: {
      code: 'RH2M',
      name: 'Humedad relativa a 2m',
      unit: '%',
      apiUnit: '%',
      color: '#10b981',
      decimals: 1
    },
    WS2M: {
      code: 'WS2M',
      name: 'Velocidad del viento a 2m',
      unit: 'm/s',
      apiUnit: 'm/s',
      color: '#6366f1',
      decimals: 2
    },
    T2M_MAX: {
      code: 'T2M_MAX',
      name: 'Temperatura máxima a 2m',
      unit: '°C',
      apiUnit: 'deg C',
      color: '#e11d48',
      decimals: 2
    },
    T2M_MIN: {
      code: 'T2M_MIN',
      name: 'Temperatura mínima a 2m',
      unit: '°C',
      apiUnit: 'deg C',
      color: '#0284c7',
      decimals: 2
    }
  };

  /**
   * Calcula los puntos de la recta de regresión lineal y el intervalo de confianza (95%)
   * a partir de la serie [{year, value}] y las estadísticas del contrato JSON.
   */
  function computeRegressionLine(series, statistics = {}) {
    if (!Array.isArray(series) || series.length === 0) {
      return { trendPoints: [], upperBand: [], lowerBand: [], slope: 0, intercept: 0 };
    }

    const valid = series.filter(
      (d) => d && typeof d.year === 'number' && typeof d.value === 'number' && !Number.isNaN(d.value)
    );
    const n = valid.length;
    if (n < 2) {
      return {
        trendPoints: valid.map((d) => ({ x: d.year, y: d.value })),
        upperBand: [],
        lowerBand: [],
        slope: 0,
        intercept: valid[0]?.value || 0
      };
    }

    const meanX = valid.reduce((acc, d) => acc + d.year, 0) / n;
    const meanY = valid.reduce((acc, d) => acc + d.value, 0) / n;

    // Si el backend envía statistics.slope, se respeta; si no, se calcula por mínimos cuadrados (OLS)
    let slope = typeof statistics.slope === 'number' ? statistics.slope : null;
    const ssXX = valid.reduce((acc, d) => acc + Math.pow(d.year - meanX, 2), 0);

    if (slope === null) {
      const ssXY = valid.reduce((acc, d) => acc + (d.year - meanX) * (d.value - meanY), 0);
      slope = ssXX !== 0 ? ssXY / ssXX : 0;
    }

    const intercept =
      typeof statistics.intercept === 'number' ? statistics.intercept : meanY - slope * meanX;

    // Error estándar residual para banda de confianza al 95% (~1.96 * SE)
    const residualsSq = valid.reduce((acc, d) => {
      const yHat = intercept + slope * d.year;
      return acc + Math.pow(d.value - yHat, 2);
    }, 0);
    const sErr = n > 2 ? Math.sqrt(residualsSq / (n - 2)) : 0;
    const tCrit = statistics.t_critical_95; // SciPy, n-2 grados de libertad desde el adaptador.

    const trendPoints = [];
    const upperBand = [];
    const lowerBand = [];

    valid.forEach((d) => {
      const yHat = intercept + slope * d.year;
      const seFit =
        ssXX > 0 ? sErr * Math.sqrt(1 / n + Math.pow(d.year - meanX, 2) / ssXX) : 0;
      const margin = tCrit * seFit;

      trendPoints.push(Number(yHat.toFixed(4)));
      upperBand.push(Number((yHat + margin).toFixed(4)));
      lowerBand.push(Number((yHat - margin).toFixed(4)));
    });

    return { trendPoints, upperBand, lowerBand, slope, intercept, meanX, meanY };
  }

  /**
   * Dibuja el gráfico principal de Resultados:
   * Serie histórica anual + Línea de regresión lineal + Banda de confianza 95%
   */
  function renderTrendChart(canvasId, payload, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
    }

    const series = payload.series || [];
    const stats = payload.statistics || {};
    const varMeta = VARIABLES_META[payload.variable] || {
      name: payload.variable || 'Variable',
      unit: payload.unit || '',
      color: '#0b3d91',
      decimals: 2
    };

    const labels = series.map((item) => item.year);
    const values = series.map((item) => item.value);
    const { trendPoints, upperBand, lowerBand, slope } = computeRegressionLine(series, stats);

    const showConfidence = options.showConfidence !== false;
    const unitLabel = payload.unit === 'deg C' ? '°C' : payload.unit || varMeta.unit;
    const slopeSign = slope >= 0 ? '+' : '';

    const datasets = [
      {
        label: `${varMeta.name} (${unitLabel}) — Serie anual NASA`,
        data: values,
        borderColor: '#0b3d91',
        backgroundColor: 'rgba(11, 61, 145, 0.12)',
        pointBackgroundColor: '#0b3d91',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2.5,
        tension: 0.2,
        order: 1
      },
      {
        label: `Línea de regresión (${slopeSign}${slope.toFixed(4)} ${unitLabel}/año)`,
        data: trendPoints,
        borderColor: '#fc3d21',
        backgroundColor: 'transparent',
        borderWidth: 2.5,
        borderDash: [7, 4],
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0,
        order: 0
      }
    ];

    if (showConfidence && upperBand.length === values.length) {
      datasets.push(
        {
          label: 'IC 95% (Superior)',
          data: upperBand,
          borderColor: 'rgba(252, 61, 33, 0.2)',
          backgroundColor: 'rgba(252, 61, 33, 0.10)',
          borderWidth: 1,
          pointRadius: 0,
          fill: '+1',
          tension: 0.1,
          order: 2
        },
        {
          label: 'IC 95% (Inferior)',
          data: lowerBand,
          borderColor: 'rgba(252, 61, 33, 0.2)',
          backgroundColor: 'transparent',
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
          tension: 0.1,
          order: 3
        }
      );
    }

    const ctx = canvas.getContext('2d');
    chartInstances[canvasId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              usePointStyle: true,
              padding: 16,
              filter: (item) => !item.text.includes('IC 95% (Inferior)')
            }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 19, 43, 0.92)',
            titleFont: { size: 13, weight: 'bold' },
            bodyFont: { size: 12 },
            padding: 12,
            callbacks: {
              label: (context) => {
                if (context.dataset.label.includes('IC 95%')) {
                  return ` Banda confianza 95%: ${context.parsed.y.toFixed(2)} ${unitLabel}`;
                }
                return ` ${context.dataset.label.split('—')[0].trim()}: ${context.parsed.y.toFixed(2)} ${unitLabel}`;
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Año',
              font: { weight: '600' }
            },
            grid: {
              color: 'rgba(226, 232, 240, 0.7)'
            }
          },
          y: {
            title: {
              display: true,
              text: `${varMeta.name} (${unitLabel})`,
              font: { weight: '600' }
            },
            grid: {
              color: 'rgba(226, 232, 240, 0.7)'
            }
          }
        }
      }
    });

    return chartInstances[canvasId];
  }

  /**
   * Dibuja el gráfico de Comparación entre dos ubicaciones (Ubicación A vs Ubicación B)
   * Misma variable, misma unidad y mismo período.
   */
  function renderComparisonChart(canvasId, dataA, dataB, labelA = 'Ubicación A', labelB = 'Ubicación B', showTrend = true) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
    }

    const seriesA = dataA.series || [];
    const seriesB = dataB.series || [];

    // Unión ordenada de todos los años presentes en ambas series
    const yearSet = new Set([
      ...seriesA.map((d) => d.year),
      ...seriesB.map((d) => d.year)
    ]);
    const years = Array.from(yearSet).sort((a, b) => a - b);

    const mapA = new Map(seriesA.map((d) => [d.year, d.value]));
    const mapB = new Map(seriesB.map((d) => [d.year, d.value]));

    const valuesA = years.map((yr) => (mapA.has(yr) ? mapA.get(yr) : null));
    const valuesB = years.map((yr) => (mapB.has(yr) ? mapB.get(yr) : null));

    const regA = computeRegressionLine(seriesA, dataA.statistics);
    const regB = computeRegressionLine(seriesB, dataB.statistics);

    const trendMapA = new Map(seriesA.map((d, i) => [d.year, regA.trendPoints[i]]));
    const trendMapB = new Map(seriesB.map((d, i) => [d.year, regB.trendPoints[i]]));

    const varMeta = VARIABLES_META[dataA.variable] || {
      name: dataA.variable || 'Variable',
      unit: dataA.unit || ''
    };
    const unitLabel = dataA.unit === 'deg C' ? '°C' : dataA.unit || varMeta.unit;

    const datasets = [
      {
        label: `${labelA} (Serie anual)`,
        data: valuesA,
        borderColor: '#0b3d91',
        backgroundColor: 'rgba(11, 61, 145, 0.1)',
        pointBackgroundColor: '#0b3d91',
        pointRadius: 3.5,
        borderWidth: 2.5,
        tension: 0.2
      },
      {
        label: `${labelB} (Serie anual)`,
        data: valuesB,
        borderColor: '#fc3d21',
        backgroundColor: 'rgba(252, 61, 33, 0.1)',
        pointBackgroundColor: '#fc3d21',
        pointRadius: 3.5,
        borderWidth: 2.5,
        tension: 0.2
      }
    ];

    if (showTrend) {
      datasets.push(
        {
          label: `Tendencia ${labelA} (${regA.slope >= 0 ? '+' : ''}${(regA.slope * 10).toFixed(2)} ${unitLabel}/década)`,
          data: years.map((yr) => (trendMapA.has(yr) ? trendMapA.get(yr) : null)),
          borderColor: '#0b3d91',
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0
        },
        {
          label: `Tendencia ${labelB} (${regB.slope >= 0 ? '+' : ''}${(regB.slope * 10).toFixed(2)} ${unitLabel}/década)`,
          data: years.map((yr) => (trendMapB.has(yr) ? trendMapB.get(yr) : null)),
          borderColor: '#fc3d21',
          borderDash: [6, 4],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0
        }
      );
    }

    const ctx = canvas.getContext('2d');
    chartInstances[canvasId] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: years,
        datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              usePointStyle: true,
              padding: 15
            }
          },
          tooltip: {
            backgroundColor: 'rgba(11, 19, 43, 0.92)',
            padding: 12,
            callbacks: {
              label: (context) => {
                const val = context.parsed.y;
                if (val === null || val === undefined) return '';
                return ` ${context.dataset.label}: ${val.toFixed(2)} ${unitLabel}`;
              }
            }
          }
        },
        scales: {
          x: {
            title: { display: true, text: 'Año', font: { weight: '600' } },
            grid: { color: 'rgba(226, 232, 240, 0.7)' }
          },
          y: {
            title: {
              display: true,
              text: `${varMeta.name} (${unitLabel})`,
              font: { weight: '600' }
            },
            grid: { color: 'rgba(226, 232, 240, 0.7)' }
          }
        }
      }
    });

    return chartInstances[canvasId];
  }

  /**
   * Descarga un archivo CSV en el navegador a partir de cabeceras y filas
   */
  function downloadCSV(filename, headers, rows, metadataLines = []) {
    const csvParts = [];

    if (metadataLines.length > 0) {
      metadataLines.forEach((line) => csvParts.push(`# ${line}`));
    }

    csvParts.push(headers.join(','));
    rows.forEach((row) => {
      const formatted = row.map((cell) => {
        if (cell === null || cell === undefined) return '';
        const str = String(cell);
        return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
      });
      csvParts.push(formatted.join(','));
    });

    const csvContent = '\uFEFF' + csvParts.join('\n'); // BOM para Excel / acentos
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }


  return {
    VARIABLES_META,
    computeRegressionLine,
    renderTrendChart,
    renderComparisonChart,
    downloadCSV
  };
})();
