/**
 * EarthLens — Rol 03: Lógica del Dashboard de Resultados (results.js)
 * Conectado al contrato JSON de POST /api/analyze y con soporte de datos de prueba etiquetados.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Estado actual del análisis mostrado en pantalla
  let currentPayload = null;
  let currentRequestParams = {
    latitude: -45.86,
    longitude: -67.50,
    locationName: 'Comodoro Rivadavia, Chubut',
    variable: 'T2M',
    start_year: 2000,
    end_year: 2024
  };

  // Presets de ubicaciones para probar rápido desde Resultados
  let LOCATION_PRESETS = {};

  /**
   * 1. Lee parámetros desde la URL (?lat=...&lon=...&variable=...&start_year=...&end_year=...)
   *    o desde sessionStorage (si el Explorador guardó el resultado previamente).
   */
  function loadInitialParams() {
    const params = new URLSearchParams(window.location.search);
    currentRequestParams.city_id = params.get('city_id') || 'comodoro-rivadavia';
    for (const key of ['variable', 'start_year', 'end_year']) {
      if (params.has(key)) currentRequestParams[key] = params.get(key);
    }
  }

  /**
   * 2. Consulta al endpoint POST /api/analyze respetando el contrato de la Página 6.
   *    Los fallos se muestran sin generar datos de reemplazo.
   */
  async function fetchAnalysisData(reqParams) {
    setLoadingState(true);
    document.getElementById('results-output').hidden = true;
    currentPayload = null;
    try {
      const data = await window.EarthLensAPI.analyze(reqParams);
      Object.assign(currentRequestParams, {latitude: data.location.latitude, longitude: data.location.longitude, locationName: data.location.name});
      document.getElementById('dataModeText').classList.remove('alert', 'alert-danger');
      return data;
    } catch (error) {
      document.getElementById('dataModeBanner').classList.remove('is-live');
      window.EarthLensAPI.showError(document.getElementById('dataModeText'), error);
      return null;
    } finally { setLoadingState(false); }
  }

  /**
   * 3. Renderiza todos los indicadores del dashboard, la conclusión, la tabla y el gráfico Chart.js
   */
  function renderDashboard(data) {
    if (!data) return;
    document.getElementById('results-output').hidden = false;
    currentPayload = data;
    document.getElementById('results-evidence')?.remove();
    document.getElementById('results-output').insertAdjacentHTML('beforeend', '<div id="results-evidence">' + window.EarthLensAPI.evidence(data) + '</div>');
    const stats = data.statistics || {};
    const series = data.series || [];
    const varMeta = EarthLensCharts.VARIABLES_META[data.variable] || {
      name: data.variable,
      unit: data.unit || '',
      decimals: 2
    };
    const unitDisplay = data.unit === 'deg C' ? '°C' : data.unit || varMeta.unit;

    // Banner de modo de datos (Prueba vs API Real)
    const banner = document.getElementById('dataModeBanner');
    const bannerText = document.getElementById('dataModeText');
    if (banner && bannerText) {
      if (data.is_mock) {
        banner.classList.remove('is-live');
        bannerText.innerHTML =
          '<strong>MODO DATOS DE PRUEBA (Contrato JSON):</strong> Mostrando serie simulada de referencia (Comodoro Rivadavia / Patagonia 2000–2024) mientras el endpoint <code>POST /api/analyze</code> del backend no esté activo.';
      } else {
        banner.classList.add('is-live');
        bannerText.innerHTML =
          '<strong>CONECTADO AL BACKEND NASA POWER:</strong> Datos científicos reales obtenidos desde <code>POST /api/analyze</code>.';
      }
    }

    // Encabezado de contexto
    const locName = data.location?.name || currentRequestParams.locationName;
    const lat = data.location?.latitude ?? currentRequestParams.latitude;
    const lon = data.location?.longitude ?? currentRequestParams.longitude;
    const startYr = series[0]?.year ?? currentRequestParams.start_year;
    const endYr = series[series.length - 1]?.year ?? currentRequestParams.end_year;

    setText('resLocationTitle', locName);
    setText('resCoordinates', `Lat: ${Number(lat).toFixed(2)}° · Lon: ${Number(lon).toFixed(2)}°`);
    setText('resVariableBadge', `${varMeta.name} (${data.variable})`);
    setText('resPeriodBadge', `Período: ${startYr} – ${endYr} (${series.length} años)`);
    setText('resSourceText', data.source || 'NASA POWER / MERRA-2');

    // Métrica 1: Pendiente lineal (slope)
    const slope = Number(stats.slope ?? 0);
    const slopeSign = slope >= 0 ? '+' : '';
    setText('metricSlope', `${slopeSign}${slope.toFixed(4)} ${unitDisplay}/año`);

    const decadal = Number(stats.change_per_decade ?? slope * 10);
    const decadalSign = decadal >= 0 ? '+' : '';
    setText('metricDecade', `Cambio por década: ${decadalSign}${decadal.toFixed(3)} ${unitDisplay}/década`);

    // Métrica 2: Magnitud del cambio total en el período
    const totalChange = Number(stats.total_change ?? slope * (endYr - startYr));
    const totalSign = totalChange >= 0 ? '+' : '';
    setText('metricTotalChange', `${totalSign}${totalChange.toFixed(2)} ${unitDisplay}`);
    setText('metricTotalSub', `Cambio estimado entre ${startYr} y ${endYr}`);

    // Métrica 3: p-valor y significancia estadística (umbral α = 0.05)
    const pVal = Number(stats.p_value ?? 1);
    const isSig = Boolean(stats.significant ?? pVal < 0.05);
    setText('metricPValue', pVal < 0.0001 ? '< 0.0001' : pVal.toFixed(4));

    const sigBadge = document.getElementById('metricSigBadge');
    if (sigBadge) {
      sigBadge.className = `badge rounded-pill ${isSig ? 'badge-sig-yes' : 'badge-sig-no'}`;
      sigBadge.textContent = isSig
        ? 'Evidencia significativa (p < 0.05)'
        : 'No significativo (p ≥ 0.05)';
    }

    // Métrica 4: Dirección e intervalo de confianza
    const dirMap = {
      increasing: { label: 'Tendencia Ascendente ↑', icon: '📈' },
      decreasing: { label: 'Tendencia Descendente ↓', icon: '📉' },
      stable: { label: 'Sin tendencia clara →', icon: '➖' }
    };
    const dirInfo = dirMap[stats.direction] || dirMap.stable;
    setText('metricDirection', `${dirInfo.icon} ${dirInfo.label}`);

    if (Array.isArray(stats.confidence_interval_95) && stats.confidence_interval_95.length === 2) {
      setText(
        'metricConfidence',
        `IC 95% pendiente: [${stats.confidence_interval_95[0]}, ${stats.confidence_interval_95[1]}] ${unitDisplay}/año`
      );
    } else {
      const values = series.map((s) => s.value);
      const meanVal = values.length
        ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2)
        : '--';
      setText('metricConfidence', `Promedio del período: ${meanVal} ${unitDisplay}`);
    }

    // Conclusión e interpretación basada en evidencia
    setText('resConclusionText', data.conclusion || 'Análisis completado.');
    const conclusionBox = document.getElementById('resConclusionBox');
    if (conclusionBox) {
      conclusionBox.className = 'conclusion-box mb-4';
      if (isSig && stats.direction === 'increasing') {
        conclusionBox.classList.add('significant-increasing');
      } else if (isSig && stats.direction === 'decreasing') {
        conclusionBox.classList.add('significant-decreasing');
      }
    }

    // Renderizar gráfico con Chart.js
    const showCICheckbox = document.getElementById('toggleConfidenceBand');
    const showConfidence = showCICheckbox ? showCICheckbox.checked : true;
    EarthLensCharts.renderTrendChart('resultsTrendChart', data, { showConfidence });

    // Poblar tabla anual con valores observados y estimados por la regresión
    renderSeriesTable(series, stats, unitDisplay);

    // Actualizar enlace hacia el Comparador pre-cargando la Ubicación A
    const compareLink = document.getElementById('btnGoToCompare');
    if (compareLink) {
      const q = new URLSearchParams({
        latA: lat,
        lonA: lon,
        nameA: locName,
        variable: data.variable,
        start_year: startYr,
        end_year: endYr
      });
      q.set('city_id_a', data.location.id);
      q.set('city_id_b', 'ushuaia');
      compareLink.href = `/compare?${q.toString()}`;
    }
  }

  /**
   * 4. Llena la tabla desplegable de datos anuales + valores ajustados por regresión
   */
  function renderSeriesTable(series, stats, unitDisplay) {
    const tbody = document.getElementById('seriesTableBody');
    if (!tbody) return;

    const { trendPoints } = EarthLensCharts.computeRegressionLine(series, stats);
    const meanVal =
      series.length > 0 ? series.reduce((acc, d) => acc + d.value, 0) / series.length : 0;

    tbody.innerHTML = series
      .map((item, idx) => {
        const fit = trendPoints[idx] ?? item.value;
        const anomaly = item.value - meanVal;
        const anomSign = anomaly >= 0 ? '+' : '';
        return `
          <tr>
            <td class="fw-semibold">${item.year}</td>
            <td>${item.value.toFixed(2)} ${unitDisplay}</td>
            <td>${fit.toFixed(2)} ${unitDisplay}</td>
            <td class="${anomaly >= 0 ? 'text-danger' : 'text-primary'}">${anomSign}${anomaly.toFixed(2)} ${unitDisplay}</td>
          </tr>
        `;
      })
      .join('');
  }

  /**
   * 5. Exporta la serie actual y sus métricas estadísticas a CSV
   */
  function handleExportCSV() {
    if (!currentPayload) return;

    const series = currentPayload.series || [];
    const stats = currentPayload.statistics || {};
    const { trendPoints } = EarthLensCharts.computeRegressionLine(series, stats);
    const locName = currentPayload.location?.name || currentRequestParams.locationName;

    const metadata = [
      `Proyecto: EarthLens - NASA Space Apps Challenge 2026`,
      `Ubicacion: ${locName} (${currentRequestParams.latitude}, ${currentRequestParams.longitude})`,
      `Variable: ${currentPayload.variable} (${currentPayload.unit})`,
      `Fuente: ${currentPayload.source}`,
      `Origen: ${currentPayload.provenance.origin} | Obtenido: ${currentPayload.provenance.fetched_at}`,
      `Agregacion: ${currentPayload.method.regression} | Cobertura: ${currentPayload.completeness.coverage_ratio}`,
      `Pendiente anual: ${stats.slope} | Cambio por decada: ${stats.change_per_decade} | Cambio total: ${stats.total_change}`,
      `p-valor: ${stats.p_value} | Significativo (p<0.05): ${stats.significant} | Direccion: ${stats.direction}`,
      `Conclusion: ${currentPayload.conclusion}`
    ];

    const headers = ['anio', 'valor_observado', 'valor_regresion_lineal', 'unidad', 'variable'];
    const rows = series.map((item, idx) => [
      item.year,
      item.value,
      trendPoints[idx] ?? '',
      currentPayload.unit,
      currentPayload.variable
    ]);

    const safeVar = (currentPayload.variable || 'serie').toLowerCase();
    const startYr = series[0]?.year || 2000;
    const endYr = series[series.length - 1]?.year || 2024;
    EarthLensCharts.downloadCSV(
      `earthlens_${safeVar}_${startYr}_${endYr}.csv`,
      headers,
      rows,
      metadata
    );
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  function setLoadingState(isLoading) {
    const spinner = document.getElementById('resultsLoadingSpinner');
    if (spinner) {
      spinner.classList.toggle('d-none', !isLoading);
    }
  }

  /**
   * 6. Sincroniza controles interactivos del panel superior
   */
  function bindControls() {
    const varSelect = document.getElementById('quickVariableSelect');
    const locSelect = document.getElementById('quickLocationSelect');
    const startInput = document.getElementById('quickStartYear');
    const endInput = document.getElementById('quickEndYear');
    const btnApply = document.getElementById('btnUpdateResults');
    const btnExportCSV = document.getElementById('btnExportCSV');
    const toggleCI = document.getElementById('toggleConfidenceBand');

    if (varSelect) varSelect.value = currentRequestParams.variable;
    if (startInput) startInput.value = currentRequestParams.start_year;
    if (endInput) endInput.value = currentRequestParams.end_year;

    if (locSelect) {
      locSelect.addEventListener('change', () => {
        const preset = LOCATION_PRESETS[locSelect.value];
        if (preset) {
          currentRequestParams.city_id = preset.id;
          currentRequestParams.latitude = preset.latitude;
          currentRequestParams.longitude = preset.longitude;
          currentRequestParams.locationName = preset.name;
        }
      });
    }

    if (btnApply) {
      btnApply.addEventListener('click', async () => {
        if (varSelect) currentRequestParams.variable = varSelect.value;
        if (startInput && endInput) {
          const s = parseInt(startInput.value, 10) || 2000;
          const e = parseInt(endInput.value, 10) || 2024;
          currentRequestParams.start_year = Math.min(s, e - 2);
          currentRequestParams.end_year = Math.max(s + 2, e);
          startInput.value = currentRequestParams.start_year;
          endInput.value = currentRequestParams.end_year;
        }
        const data = await fetchAnalysisData(currentRequestParams);
        renderDashboard(data);
      });
    }

    if (toggleCI) {
      toggleCI.addEventListener('change', () => {
        if (currentPayload) {
          EarthLensCharts.renderTrendChart('resultsTrendChart', currentPayload, {
            showConfidence: toggleCI.checked
          });
        }
      });
    }

    if (btnExportCSV) {
      btnExportCSV.addEventListener('click', handleExportCSV);
    }
  }

  // Inicialización principal
  (async function init() {
    loadInitialParams();
    try {
      const cities = await window.EarthLensAPI.cities();
      LOCATION_PRESETS = Object.fromEntries(cities.map(city => [city.id, city]));
      window.EarthLensAPI.fillCities(document.getElementById('quickLocationSelect'), cities, currentRequestParams.city_id);
    } catch (error) { window.EarthLensAPI.showError(document.getElementById('dataModeText'), error); return; }
    bindControls();
    const initialData = await fetchAnalysisData(currentRequestParams);
    renderDashboard(initialData);
  })();
});
