/**
 * EarthLens — Lógica del Explorador Ambiental (explorer.js)
 * Responsable: 02 / Mapa interactivo y explorador
 *
 * Gestiona el selector de variables NASA POWER, ubicación, rango de años,
 * validación de formulario, envío al endpoint POST /api/analyze, estados de carga,
 * manejo de errores, datos de prueba etiquetados y transición a Resultados.
 */

(function (window, document) {
  'use strict';

  // Catálogo oficial de variables del MVP (Página 4 del Plan de Desarrollo)
  const MVP_VARIABLES = [
    {
      code: 'T2M',
      name: 'Temperatura media a 2 metros',
      shortName: 'Temperatura media',
      unit: 'deg C',
      displayUnit: '°C',
      priority: 'Primera',
      source: 'NASA POWER / MERRA-2',
      description: 'Promedio anual de la temperatura del aire a 2 metros sobre la superficie. Variable principal del MVP.'
    },
    {
      code: 'PRECTOTCORR',
      name: 'Precipitaciones corregidas',
      shortName: 'Precipitaciones',
      unit: 'mm/day',
      displayUnit: 'mm/día',
      priority: 'Alta',
      source: 'NASA POWER / MERRA-2',
      description: 'Precipitación total corregida promedio. Permite analizar sequías o incrementos de lluvias.'
    },
    {
      code: 'RH2M',
      name: 'Humedad relativa a 2 metros',
      shortName: 'Humedad relativa',
      unit: '%',
      displayUnit: '%',
      priority: 'Alta',
      source: 'NASA POWER / MERRA-2',
      description: 'Porcentaje de humedad atmosférica a 2 metros. Nota científica: la humedad relativa no equivale a la humedad del suelo.'
    },
    {
      code: 'WS2M',
      name: 'Velocidad del viento a 2 metros',
      shortName: 'Velocidad del viento',
      unit: 'm/s',
      displayUnit: 'm/s',
      priority: 'Alta',
      source: 'NASA POWER / MERRA-2',
      description: 'Velocidad media del viento a 2 metros de altura. Útil para evaluar cambios en regímenes eólicos.'
    },
    {
      code: 'T2M_MAX',
      name: 'Temperatura máxima a 2 metros',
      shortName: 'Temperatura máxima',
      unit: 'deg C',
      displayUnit: '°C',
      priority: 'Secundaria',
      source: 'NASA POWER / MERRA-2',
      description: 'Temperatura máxima registrada a 2 metros para evaluar extremos cálidos.'
    },
    {
      code: 'T2M_MIN',
      name: 'Temperatura mínima a 2 metros',
      shortName: 'Temperatura mínima',
      unit: 'deg C',
      displayUnit: '°C',
      priority: 'Secundaria',
      source: 'NASA POWER / MERRA-2',
      description: 'Temperatura mínima registrada a 2 metros para evaluar extremos fríos y heladas.'
    }
  ];

  // Casos guiados / Misiones que reutilizan el explorador (Página 7 del Plan)
  const PRESET_LOCATIONS = [
    {
      id: 'comodoro',
      name: 'Comodoro Rivadavia (Prueba MVP)',
      missionTitle: 'Caso 01 / Patagonia cambiante: ¿Está aumentando la temperatura?',
      latitude: -45.86,
      longitude: -67.50,
      variable: 'T2M',
      start_year: 2000,
      end_year: 2024,
      zoom: 6
    },
    {
      id: 'agua-cuyo',
      name: 'Mendoza / Andes Centrales',
      missionTitle: 'Caso 02 / En busca del agua: ¿Están disminuyendo las precipitaciones?',
      latitude: -32.89,
      longitude: -68.84,
      variable: 'PRECTOTCORR',
      start_year: 2000,
      end_year: 2024,
      zoom: 6
    },
    {
      id: 'viento-austral',
      name: 'Río Gallegos (Patagonia Austral)',
      missionTitle: 'Caso 03 / El misterio del viento: ¿Está cambiando la velocidad del viento?',
      latitude: -51.62,
      longitude: -69.22,
      variable: 'WS2M',
      start_year: 2000,
      end_year: 2024,
      zoom: 6
    },
  ];

  const MIN_ALLOWED_YEAR = 1981;
  const MAX_ALLOWED_YEAR = 2024;
  const MIN_YEAR_SPAN = 3;

  let variablesCatalog = [...MVP_VARIABLES];
  let cities = [];
  let currentCity;

  // Referencias a elementos del DOM
  const els = {};
  const escapeHtml = window.EarthLensAPI.escape;

  function cacheElements() {
    els.form = document.getElementById('explorer-form');
    els.latInput = document.getElementById('input-latitude');
    els.lonInput = document.getElementById('input-longitude');
    els.locationName = document.getElementById('location-label-display');
    els.variableSelect = document.getElementById('select-variable');
    els.variableCodeBadge = document.getElementById('var-code-badge');
    els.variableUnitBadge = document.getElementById('var-unit-badge');
    els.variablePriorityBadge = document.getElementById('var-priority-badge');
    els.variableDesc = document.getElementById('var-description');
    els.startYearInput = document.getElementById('input-start-year');
    els.endYearInput = document.getElementById('input-end-year');
    els.yearSpanBadge = document.getElementById('year-span-badge');
    els.yearWarning = document.getElementById('year-span-warning');
    els.analyzeBtn = document.getElementById('btn-analyze');
    els.analyzeBtnText = document.getElementById('btn-analyze-text');
    els.analyzeSpinner = document.getElementById('btn-analyze-spinner');
    els.statusBox = document.getElementById('explorer-status-box');

    els.autoRedirectToggle = document.getElementById('toggle-auto-redirect');
    els.missionBanner = document.getElementById('active-mission-banner');
    els.missionBannerText = document.getElementById('active-mission-text');
    els.previewSection = document.getElementById('analysis-preview-section');
    els.btnLocateMe = document.getElementById('btn-locate-me');
    els.btnResetWorld = document.getElementById('btn-reset-world');
    els.btnCompareLink = document.getElementById('btn-send-to-compare');
  }

  /**
   * Pobla el selector de variables y sincroniza la tarjeta descriptiva.
   */
  function populateVariableSelector(selectedCode = 'T2M') {
    if (!els.variableSelect) return;
    els.variableSelect.innerHTML = '';

    variablesCatalog.forEach(function (v) {
      const opt = document.createElement('option');
      opt.value = v.code;
      opt.textContent = `${v.shortName} (${v.code}) — [${v.displayUnit || v.unit}]`;
      if (v.code === selectedCode) {
        opt.selected = true;
      }
      els.variableSelect.appendChild(opt);
    });

    updateVariableInfoCard(selectedCode);
  }

  /**
   * Intenta obtener variables desde GET /api/variables manteniendo el catálogo MVP como base.
   */
  async function loadVariablesFromBackend() {
    if (window.location.protocol === 'file:') return;
    try {
      const response = await fetch('/api/variables', {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!response.ok) return;
      const data = await response.json();
      const list = Array.isArray(data) ? data : (Array.isArray(data.data) ? data.data : null);
      if (list && list.length > 0) {
        // Enriquecer o combinar con metadatos locales del MVP
        variablesCatalog = list.map(function (remoteVar) {
          const localMatch = MVP_VARIABLES.find(function (m) {
            return m.code === remoteVar.code;
          });
          return Object.assign({}, localMatch || {}, remoteVar);
        });
        populateVariableSelector(els.variableSelect ? els.variableSelect.value : 'T2M');
      }
    } catch (_) {
      // Si el backend no está activo aún, se conserva MVP_VARIABLES silenciosamente
    }
  }

  /**
   * Actualiza el recuadro de detalles científicos de la variable elegida.
   */
  function updateVariableInfoCard(code) {
    const variable = variablesCatalog.find(function (v) {
      return v.code === code;
    }) || MVP_VARIABLES[0];

    if (els.variableCodeBadge) els.variableCodeBadge.textContent = variable.code;
    if (els.variableUnitBadge) els.variableUnitBadge.textContent = `Unidad: ${variable.unit}`;
    if (els.variablePriorityBadge) els.variablePriorityBadge.textContent = `Prioridad: ${variable.priority || 'MVP'}`;
    if (els.variableDesc) els.variableDesc.textContent = variable.description || '';
  }

  /**
   * Calcula y muestra la cantidad de años seleccionados y alertas estadísticas.
   */
  function updateYearSpanIndicator() {
    if (!els.startYearInput || !els.endYearInput) return;
    const start = parseInt(els.startYearInput.value, 10);
    const end = parseInt(els.endYearInput.value, 10);

    if (!Number.isInteger(start) || !Number.isInteger(end) || end <= start) {
      if (els.yearSpanBadge) {
        els.yearSpanBadge.textContent = 'Período inválido';
        els.yearSpanBadge.className = 'badge bg-danger-subtle text-danger';
      }
      return;
    }

    const totalYears = end - start + 1;
    if (els.yearSpanBadge) {
      els.yearSpanBadge.textContent = `${totalYears} años (${start}–${end})`;
      els.yearSpanBadge.className = totalYears >= 10
        ? 'badge bg-info-subtle text-info-emphasis'
        : 'badge bg-warning-subtle text-warning-emphasis';
    }

    if (els.yearWarning) {
      if (totalYears < 10) {
        els.yearWarning.classList.remove('d-none');
      } else {
        els.yearWarning.classList.add('d-none');
      }
    }
  }

  /**
   * Valida todos los parámetros del formulario antes de consultar el backend.
   */
  function validateFormParams() {
    const errors = [];
    const rawLat = els.latInput ? els.latInput.value.trim() : '';
    const rawLon = els.lonInput ? els.lonInput.value.trim() : '';
    const lat = Number(rawLat);
    const lon = Number(rawLon);
    const variable = els.variableSelect ? els.variableSelect.value.trim() : '';
    const startYear = parseInt(els.startYearInput ? els.startYearInput.value : '', 10);
    const endYear = parseInt(els.endYearInput ? els.endYearInput.value : '', 10);

    if (rawLat === '' || !Number.isFinite(lat) || lat < -90 || lat > 90) {
      errors.push('La latitud debe ser un número válido entre -90° y 90°.');
    }

    if (rawLon === '' || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      errors.push('La longitud debe ser un número válido entre -180° y 180°.');
    }

    const validCodes = variablesCatalog.map(function (v) { return v.code; });
    if (!variable || !validCodes.includes(variable)) {
      errors.push('Debes seleccionar una variable climática válida del catálogo NASA POWER.');
    }

    if (!Number.isInteger(startYear) || startYear < MIN_ALLOWED_YEAR || startYear > MAX_ALLOWED_YEAR) {
      errors.push(`El año inicial debe estar entre ${MIN_ALLOWED_YEAR} y ${MAX_ALLOWED_YEAR}.`);
    }

    if (!Number.isInteger(endYear) || endYear < MIN_ALLOWED_YEAR || endYear > MAX_ALLOWED_YEAR) {
      errors.push(`El año final debe estar entre ${MIN_ALLOWED_YEAR} y ${MAX_ALLOWED_YEAR}.`);
    }

    if (Number.isInteger(startYear) && Number.isInteger(endYear)) {
      if (startYear >= endYear) {
        errors.push('El año inicial debe ser estrictamente menor que el año final.');
      } else if (endYear - startYear + 1 < MIN_YEAR_SPAN) {
        errors.push(`Selecciona un período de al menos ${MIN_YEAR_SPAN} años para poder calcular una regresión lineal.`);
      }
    }

    return {
      isValid: errors.length === 0,
      errors: errors,
      payload: {
        latitude: Number(lat.toFixed(4)),
        longitude: Number(lon.toFixed(4)),
        variable: variable,
        start_year: startYear,
        end_year: endYear
      }
    };
  }

  /**
   * Muestra mensajes de estado (error, advertencia, carga o éxito) en el panel.
   */
  function showStatusMessage(type, title, messages) {
    if (!els.statusBox) return;
    els.statusBox.classList.remove('d-none', 'alert-danger', 'alert-warning', 'alert-info', 'alert-success');

    const alertClassMap = {
      error: 'alert-danger',
      warning: 'alert-warning',
      info: 'alert-info',
      success: 'alert-success'
    };
    els.statusBox.classList.add(alertClassMap[type] || 'alert-info');

    const listHtml = Array.isArray(messages)
      ? `<ul class="mb-0 mt-1 ps-3 small">${messages.map(m => `<li>${escapeHtml(m)}</li>`).join('')}</ul>`
      : `<div class="small mt-1">${escapeHtml(messages)}</div>`;

    els.statusBox.innerHTML = `
      <div class="fw-semibold">${escapeHtml(title)}</div>
      ${listHtml}
    `;
  }

  function hideStatusMessage() {
    if (els.statusBox) {
      els.statusBox.classList.add('d-none');
      els.statusBox.innerHTML = '';
    }
  }

  function setLoadingState(isLoading) {
    if (!els.analyzeBtn) return;
    els.analyzeBtn.disabled = isLoading;
    if (els.analyzeSpinner) {
      els.analyzeSpinner.classList.toggle('d-none', !isLoading);
    }
    if (els.analyzeBtnText) {
      els.analyzeBtnText.textContent = isLoading
        ? 'Consultando NASA POWER y analizando...'
        : 'Analizar tendencia';
    }
  }

  /**
   * Genera datos de prueba claramente etiquetados que respetan el Contrato de la API (Página 6)
   * para poder probar el explorador y resultados cuando el backend aún no está disponible.
   */


  /**
   * Envía la solicitud a POST /api/analyze o usa window.EarthLensAPI si está disponible.
   */
  async function sendAnalyzeRequest(payload) {
    return window.EarthLensAPI.analyze(payload);
  }

  /**
   * Guarda tanto la consulta como la respuesta en sessionStorage y localStorage
   * para que results.html (Persona 3) pueda leerlos inmediatamente.
   */
  function persistAnalysisForResultsPage(payload, responseData, locationLabel) {
    const enrichedRecord = {
      timestamp: new Date().toISOString(),
      location_label: locationLabel || `${payload.latitude}, ${payload.longitude}`,
      request: payload,
      response: responseData
    };

    try {
      sessionStorage.setItem('earthlens_last_request', JSON.stringify(payload));
      sessionStorage.setItem('earthlens_last_result', JSON.stringify(responseData));
      sessionStorage.setItem('earthlens_analysis_bundle', JSON.stringify(enrichedRecord));

      localStorage.setItem('earthlens_last_request', JSON.stringify(payload));
      localStorage.setItem('earthlens_last_result', JSON.stringify(responseData));
      localStorage.setItem('earthlens_analysis_bundle', JSON.stringify(enrichedRecord));
    } catch (storageErr) {
      console.warn('[EarthLensExplorer] No se pudo guardar en storage:', storageErr);
    }
  }

  /**
   * Renderiza la tarjeta de resumen preliminar y botón de paso a Resultados.
   */
  function renderAnalysisPreview(payload, result, locationLabel) {
    if (!els.previewSection) return;

    const stats = result.statistics || {};
    const isMock = Boolean(result.is_mock);
    const unit = result.unit || 'unidad';
    const slopeSign = stats.slope > 0 ? '+' : '';
    const decadeSign = stats.change_per_decade > 0 ? '+' : '';
    const totalSign = stats.total_change > 0 ? '+' : '';

    const directionLabelMap = {
      increasing: 'Ascendente ↑',
      decreasing: 'Descendente ↓',
      stable: 'Sin tendencia clara ↔'
    };
    const directionBadgeClass = stats.direction === 'increasing'
      ? 'bg-danger-subtle text-danger-emphasis'
      : (stats.direction === 'decreasing' ? 'bg-primary-subtle text-primary-emphasis' : 'bg-secondary-subtle text-secondary');

    // Construir URL hacia resultados pasando también query params por si results.html los lee de la URL
    const queryString = new URLSearchParams({
      city_id: payload.city_id,
      variable: payload.variable,
      start_year: payload.start_year,
      end_year: payload.end_year,
      label: locationLabel || ''
    }).toString();

    const resultsHref = window.location.protocol === 'file:'
      ? `results.html?${queryString}`
      : `/results?${queryString}`;

    els.previewSection.classList.remove('d-none');
    els.previewSection.innerHTML = `
      <div class="el-card analysis-preview-card p-3 p-md-4 mt-4">
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <div>
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <h2 class="h5 fw-bold mb-0">Paso 4 · Consulta lista para Resultados</h2>
              ${isMock
                ? '<span class="el-mock-badge">⚠️ DATOS DE PRUEBA (Modo Desarrollo)</span>'
                : '<span class="badge bg-success-subtle text-success-emphasis border border-success-subtle">✓ Datos reales NASA POWER</span>'}
            </div>
            <p class="text-muted small mb-0 mt-1">
              Ubicación: <strong>${escapeHtml(locationLabel || 'Punto seleccionado')}</strong>
              (${payload.latitude}°, ${payload.longitude}°) · Variable: <strong>${escapeHtml(result.variable || payload.variable)}</strong>
              · Período: <strong>${payload.start_year}–${payload.end_year}</strong> (${(result.series || []).length} años)
            </p>
          </div>
          <div class="d-flex gap-2">
            <a href="${resultsHref}" class="btn btn-primary fw-semibold px-3">
              Ir a Pantalla de Resultados &rarr;
            </a>
          </div>
        </div>

        <div class="row g-2 g-md-3 mb-3">
          <div class="col-6 col-md-3">
            <div class="stat-mini-box">
              <div class="stat-mini-label">Pendiente anual</div>
              <div class="stat-mini-value">${slopeSign}${stats.slope ?? '—'} <small class="fw-normal text-muted">${escapeHtml(unit)}/año</small></div>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="stat-mini-box">
              <div class="stat-mini-label">Cambio por década</div>
              <div class="stat-mini-value">${decadeSign}${stats.change_per_decade ?? '—'} <small class="fw-normal text-muted">${escapeHtml(unit)}</small></div>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="stat-mini-box">
              <div class="stat-mini-label">Cambio total (${payload.start_year}–${payload.end_year})</div>
              <div class="stat-mini-value">${totalSign}${stats.total_change ?? '—'} <small class="fw-normal text-muted">${escapeHtml(unit)}</small></div>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="stat-mini-box">
              <div class="stat-mini-label">Evidencia estadística (p-valor)</div>
              <div class="stat-mini-value">
                p = ${stats.p_value ?? '—'}
                <span class="badge ${directionBadgeClass} ms-1 fw-medium" style="font-size:0.7rem;">
                  ${directionLabelMap[stats.direction] || stats.direction || '—'}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="alert ${stats.significant ? 'alert-info' : 'alert-secondary'} mb-3 py-2 px-3 small">
          <strong>Conclusión preliminar:</strong> ${escapeHtml(result.conclusion || 'Sin conclusión disponible.')}
          <span class="text-muted ms-1">(Fuente: ${escapeHtml(result.source || 'NASA POWER / MERRA-2')})</span>
        </div>

        <details class="small">
          <summary class="text-muted fw-medium" style="cursor:pointer;">
            Ver contrato JSON enviado y recibido (para integración con Backend y Resultados)
          </summary>
          <div class="row g-2 mt-2">
            <div class="col-md-5">
              <div class="fw-semibold text-muted mb-1">Solicitud (POST /api/analyze):</div>
              <pre class="bg-dark text-light p-2 rounded mb-0" style="font-size:0.75rem; max-height:200px; overflow:auto;">${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
            </div>
            <div class="col-md-7">
              <div class="fw-semibold text-muted mb-1">Respuesta recibida (Contrato JSON):</div>
              <pre class="bg-dark text-light p-2 rounded mb-0" style="font-size:0.75rem; max-height:200px; overflow:auto;">${escapeHtml(JSON.stringify(result, null, 2))}</pre>
            </div>
          </div>
        </details>
      </div>
    `;

    els.previewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /**
   * Maneja el envío del formulario de análisis.
   */
  async function handleFormSubmit(event) {
    event.preventDefault();
    hideStatusMessage();
    const validation = validateFormParams();
    if (!validation.isValid || !currentCity) {
      showStatusMessage('error', 'Revisa la consulta', validation.errors);
      return;
    }
    const selectedCity = currentCity;
    const payload = { ...validation.payload, city_id: selectedCity.id };
    setLoadingState(true);
    if (els.previewSection) els.previewSection.classList.add('d-none');
    try {
      const responseData = await sendAnalyzeRequest(payload);
      persistAnalysisForResultsPage(payload, responseData, selectedCity.name);
      showStatusMessage('success', 'Análisis completado con datos reales.', `Origen: ${responseData.provenance.origin}. Obtenido: ${responseData.provenance.fetched_at}`);
      renderAnalysisPreview(payload, responseData, selectedCity.name);
      els.previewSection.insertAdjacentHTML('beforeend', window.EarthLensAPI.evidence(responseData));
      if (els.autoRedirectToggle?.checked) {
        window.location.href = '/results?' + new URLSearchParams({city_id: selectedCity.id, variable: payload.variable, start_year: payload.start_year, end_year: payload.end_year});
      }
    } catch (error) {
      showStatusMessage('error', 'No se pudo completar el análisis.', error.message);
    } finally { setLoadingState(false); }
  }

  /**
   * Aplica una ubicación predefinida o misión sobre el formulario y el mapa.
   */
  function applyPreset(presetId) {
    const preset = PRESET_LOCATIONS.find(item => item.id === presetId);
    if (!preset) return;
    const ids = {comodoro: 'comodoro-rivadavia', 'agua-cuyo': 'mendoza', 'viento-austral': 'rio-gallegos'};
    selectCity(ids[presetId]);
    els.variableSelect.value = preset.variable;
    updateVariableInfoCard(preset.variable);
    els.startYearInput.value = preset.start_year;
    els.endYearInput.value = preset.end_year;
    updateYearSpanIndicator();
    updateCompareLink();
    if (els.missionBannerText) els.missionBannerText.textContent = preset.missionTitle;
    els.missionBanner?.classList.remove('d-none');
  }

  /**
   * Lee parámetros de la URL (?lat=...&lon=...&variable=...&start_year=...&end_year=...&mission=...)
   * para permitir que Modo Detective (Persona 5) o Inicio reutilicen el explorador.
   */
  function applyUrlQueryParams() {
    const params = new URLSearchParams(window.location.search);
    if (params.has('city_id')) selectCity(params.get('city_id'));
    if (variablesCatalog.some(item => item.code === params.get('variable'))) {
      els.variableSelect.value = params.get('variable');
      updateVariableInfoCard(els.variableSelect.value);
    }
    for (const [key, element] of [['start_year', els.startYearInput], ['end_year', els.endYearInput]]) {
      if (params.has(key)) element.value = params.get(key);
    }
    const preset = params.get('mission') || params.get('preset');
    if (preset) applyPreset(preset);
    updateYearSpanIndicator();
    updateCompareLink();
    return params.size > 0;
  }

  /**
   * Actualiza el enlace hacia el Comparador llevando la ubicación actual como Punto A.
   */
  function updateCompareLink() {
    if (!els.btnCompareLink || !currentCity) return;
    els.btnCompareLink.href = '/compare?' + new URLSearchParams({city_id_a: currentCity.id, city_id_b: 'ushuaia', variable: els.variableSelect.value, start_year: els.startYearInput.value, end_year: els.endYearInput.value});
  }

  /**
   * Sincroniza cambios manuales en los inputs numéricos de latitud y longitud hacia el mapa.
   */


  /**
   * Inicializa eventos y componentes del Explorador.
   */
  function selectCity(id) {
    const city = cities.find(item => item.id === id);
    if (!city) { showStatusMessage('error', 'Ciudad no disponible.', 'Selecciona una ciudad argentina del catálogo.'); return; }
    currentCity = city;
    document.getElementById('select-city').value = id;
    els.latInput.value = city.latitude.toFixed(6);
    els.lonInput.value = city.longitude.toFixed(6);
    els.locationName.textContent = `${city.name}, ${city.province}`;
    window.EarthLensMap?.setLocation(city.latitude, city.longitude, city.name, 6, false);
    updateCompareLink();
  }

  async function initExplorer() {
    cacheElements();
    populateVariableSelector('T2M');
    await loadVariablesFromBackend();
    try {
      cities = await window.EarthLensAPI.cities();
      const select = document.getElementById('select-city');
      window.EarthLensAPI.fillCities(select, cities, 'comodoro-rivadavia');
      if (window.EarthLensMap && typeof L !== 'undefined') {
        const map = window.EarthLensMap.init('explorer-map', {latitude: -45.86, longitude: -67.5, zoom: 5});
        for (const city of cities) {
          L.circleMarker([city.latitude, city.longitude], {radius: 6}).addTo(map)
            .bindTooltip(city.name).on('click', () => selectCity(city.id));
        }
      }
      selectCity('comodoro-rivadavia');
      select.addEventListener('change', () => selectCity(select.value));
      els.variableSelect.addEventListener('change', () => { updateVariableInfoCard(els.variableSelect.value); updateCompareLink(); });
      for (const input of [els.startYearInput, els.endYearInput]) input.addEventListener('input', () => {updateYearSpanIndicator(); updateCompareLink();});
      document.querySelectorAll('[data-year-range]').forEach(btn => btn.addEventListener('click', () => {
        const [start,end] = btn.dataset.yearRange.split('-');
        els.startYearInput.value = start; els.endYearInput.value = end;
        updateYearSpanIndicator(); updateCompareLink();
      }));
      document.querySelectorAll('[data-preset-id]').forEach(btn => btn.addEventListener('click', () => applyPreset(btn.dataset.presetId)));
      els.btnResetWorld?.addEventListener('click', () => window.EarthLensMap?.resetWorldView());
      els.form.addEventListener('submit', handleFormSubmit);
      applyUrlQueryParams();
    } catch (error) { showStatusMessage('error', 'No se pudo cargar el catálogo.', error.message); els.analyzeBtn.disabled = true; }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initExplorer);
  } else {
    initExplorer();
  }
})(window, document);
