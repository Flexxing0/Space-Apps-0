/**
 * EarthLens — Controlador de Earth Time Machine (static/js/time-machine/time_machine.js)
 * Interfaz Satelital Científica:
 *  - Sincronización completa de barra superior con sessionStorage, URL y eventos pageshow/visibilitychange.
 *  - Cuadrante de análisis redimensionable (achicar/expandir con botones o arrastrando vértices en el mapa).
 *  - Botones de solo icono con tooltip explicativo al pasar el puntero.
 *  - Cero emojis y paleta espectral meteorológica sobria.
 */

document.addEventListener('DOMContentLoaded', () => {
  let currentData = null;
  let activeYear = 2000;
  let isPlaying = false;
  let playTimer = null;
  let playSpeedMs = 700;
  let mapMode = 'national'; // 'zone' | 'national'
  let openWindowId = null;

  let activeAbortController = null;
  let requestSeq = 0;

  let mapInstance = null;
  let weatherPlumeGroup = null;
  let zoneLayerGroup = null;
  let nationalLayerGroup = null;
  let resizeHandlesGroup = null;
  let outerBoundingRect = null;
  let zoneCellLayers = [];
  let nationalLayers = [];
  let trendChartInstance = null;

  let state = {
    city_id: 'comodoro-rivadavia',
    latitude: -45.8806,
    longitude: -67.5195,
    locationName: 'Comodoro Rivadavia, Chubut',
    variable: 'T2M',
    start_year: 2000,
    end_year: 2024,
    split_year: 2012,
    lat_span: 1.5,
    lon_span: 1.875
  };

  /**
   * Paletas meteorológicas satelitales sobrias (sin colores genéricos estridentes ni emojis)
   */
  const SATELLITE_TV_METADATA = {
    T2M: {
      title: 'Temperatura media (T2M)',
      minLabel: 'Frío (-2σ)',
      maxLabel: 'Cálido (+2σ)',
      scaleClass: 'tm-scale-thermal'
    },
    T2M_MAX: {
      title: 'Temperatura máxima (T2M_MAX)',
      minLabel: 'Templado (-2σ)',
      maxLabel: 'Extremo (+2σ)',
      scaleClass: 'tm-scale-thermal'
    },
    T2M_MIN: {
      title: 'Temperatura mínima (T2M_MIN)',
      minLabel: 'Helada (-2σ)',
      maxLabel: 'Templado (+2σ)',
      scaleClass: 'tm-scale-thermal'
    },
    PRECTOTCORR: {
      title: 'Precipitación corregida (POWER)',
      minLabel: 'Déficit (-2σ)',
      maxLabel: 'Exceso (+2σ)',
      scaleClass: 'tm-scale-precip'
    },
    RH2M: {
      title: 'Humedad relativa del aire (RH2M)',
      minLabel: 'Seco (-2σ)',
      maxLabel: 'Saturado (+2σ)',
      scaleClass: 'tm-scale-humidity'
    },
    WS2M: {
      title: 'Campo de Viento Superficial (WS2M)',
      minLabel: 'Calma (-2σ)',
      maxLabel: 'Intenso (+2σ)',
      scaleClass: 'tm-scale-wind'
    }
  };

  function getSatelliteWeatherColor(variable, zScore) {
    const varCode = (variable || 'T2M').toUpperCase();
    const z = Number(zScore || 0);

    if (varCode === 'PRECTOTCORR') {
      if (z <= -1.8) return '#6b4c35';
      if (z <= -1.0) return '#a67c52';
      if (z <= -0.3) return '#b8a868';
      if (z < 0.35) return '#5f9e8f';
      if (z < 1.1) return '#38829e';
      if (z < 1.8) return '#295f8a';
      return '#203e6b';
    }

    if (varCode === 'RH2M') {
      if (z <= -1.8) return '#7c5836';
      if (z <= -1.0) return '#b58952';
      if (z <= -0.3) return '#b8ab7a';
      if (z < 0.4) return '#6aa395';
      if (z < 1.2) return '#3b8ea5';
      if (z < 1.9) return '#27688a';
      return '#1d466b';
    }

    if (varCode === 'WS2M') {
      if (z <= -1.6) return '#1a293d';
      if (z <= -0.8) return '#2a5679';
      if (z <= 0.2) return '#3c829e';
      if (z < 1.0) return '#6476a2';
      if (z < 1.7) return '#895b8a';
      return '#a84a6c';
    }

    // Espectro Térmico IR (T2M, T2M_MAX, T2M_MIN)
    if (z <= -1.9) return '#1b2a4a';
    if (z <= -1.1) return '#2b5c8f';
    if (z <= -0.35) return '#3d8c95';
    if (z < 0.35) return '#7ca968';
    if (z < 1.1) return '#d4a349';
    if (z < 1.8) return '#c86432';
    return '#9e2a2b';
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  /**
   * 1. Sincronización de estado con URL y sessionStorage (evita desincronización al cambiar de pestaña)
   */
  function loadStateFromStorageOrURL() {
    const params = new URLSearchParams(window.location.search);
    const hasUrlParams =
      params.has('city_id') ||
      params.has('latitude') ||
      params.has('lat') ||
      params.has('variable');

    if (hasUrlParams) {
      if (params.has('city_id')) {
        state.city_id = params.get('city_id') || null;
      }
      if (params.has('latitude') || params.has('lat')) {
        const lat = parseFloat(params.get('latitude') || params.get('lat'));
        const lon = parseFloat(params.get('longitude') || params.get('lon'));
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          state.latitude = lat;
          state.longitude = lon;
        }
      }
      if (params.has('location') || params.has('label')) {
        state.locationName = params.get('location') || params.get('label');
      }
      if (params.has('variable')) {
        const v = String(params.get('variable')).toUpperCase();
        if (EarthLensCharts.VARIABLES_META[v]) state.variable = v;
      }
      if (params.has('start_year')) {
        const s = parseInt(params.get('start_year'), 10);
        if (Number.isInteger(s)) state.start_year = Math.max(1981, Math.min(2021, s));
      }
      if (params.has('end_year')) {
        const e = parseInt(params.get('end_year'), 10);
        if (Number.isInteger(e)) state.end_year = Math.max(state.start_year + 3, Math.min(2024, e));
      }
      if (params.has('lat_span')) {
        const ls = parseFloat(params.get('lat_span'));
        if (Number.isFinite(ls)) state.lat_span = Math.max(0.3, Math.min(30, ls));
      }
      if (params.has('lon_span')) {
        const lns = parseFloat(params.get('lon_span'));
        if (Number.isFinite(lns)) state.lon_span = Math.max(0.3, Math.min(36, lns));
      }
      if (params.has('year')) {
        const y = parseInt(params.get('year'), 10);
        if (Number.isInteger(y)) activeYear = y;
      }
    } else {
      // Si no hay query params en la URL, leemos el estado compartido con Explorador / Resultados / Comparador
      try {
        const savedTm = sessionStorage.getItem('earthlens_timemachine_state');
        const savedLast = sessionStorage.getItem('earthlens_last_request');
        const savedBundle = sessionStorage.getItem('earthlens_analysis_bundle');

        if (savedLast) {
          const req = JSON.parse(savedLast);
          if (req && Number.isFinite(Number(req.latitude)) && Number.isFinite(Number(req.longitude))) {
            state.latitude = Number(req.latitude);
            state.longitude = Number(req.longitude);
            if (req.locationName || req.location_name) {
              state.locationName = req.locationName || req.location_name;
            }
            if (req.variable && EarthLensCharts.VARIABLES_META[String(req.variable).toUpperCase()]) {
              state.variable = String(req.variable).toUpperCase();
            }
            if (req.start_year) state.start_year = Math.max(1981, Math.min(2021, Number(req.start_year)));
            if (req.end_year) state.end_year = Math.max(state.start_year + 3, Math.min(2024, Number(req.end_year)));
          }
        } else if (savedBundle) {
          const bundle = JSON.parse(savedBundle);
          if (bundle?.request) {
            state.latitude = Number(bundle.request.latitude ?? state.latitude);
            state.longitude = Number(bundle.request.longitude ?? state.longitude);
            state.locationName = bundle.location_label || bundle.request.locationName || state.locationName;
            if (bundle.request.variable) state.variable = String(bundle.request.variable).toUpperCase();
          }
        }

        if (savedTm) {
          const tmObj = JSON.parse(savedTm);
          if (Number.isFinite(tmObj?.lat_span)) state.lat_span = tmObj.lat_span;
          if (Number.isFinite(tmObj?.lon_span)) state.lon_span = tmObj.lon_span;
          if (tmObj?.mapMode) mapMode = tmObj.mapMode;
        }
      } catch (e) {
        // Ignorar errores de lectura de storage
      }
    }

    syncTopBarControlsWithState();
  }

  function persistStateToStorageAndURL() {
    try {
      sessionStorage.setItem(
        'earthlens_last_request',
        JSON.stringify({
          latitude: state.latitude,
          longitude: state.longitude,
          locationName: state.locationName,
          variable: state.variable,
          start_year: state.start_year,
          end_year: state.end_year
        })
      );
      sessionStorage.setItem(
        'earthlens_timemachine_state',
        JSON.stringify({
          city_id: state.city_id,
          latitude: state.latitude,
          longitude: state.longitude,
          locationName: state.locationName,
          variable: state.variable,
          start_year: state.start_year,
          end_year: state.end_year,
          lat_span: state.lat_span,
          lon_span: state.lon_span,
          mapMode
        })
      );

      const q = new URLSearchParams({
        latitude: Number(state.latitude).toFixed(4),
        longitude: Number(state.longitude).toFixed(4),
        location: state.locationName,
        variable: state.variable,
        start_year: String(state.start_year),
        end_year: String(state.end_year),
        lat_span: Number(state.lat_span).toFixed(2),
        lon_span: Number(state.lon_span).toFixed(2)
      });
      if (state.city_id) q.set('city_id', state.city_id);
      window.history.replaceState(null, '', `${window.location.pathname}?${q.toString()}`);
    } catch (e) {
      // Ignorar si history o storage no están disponibles
    }
  }

  /**
   * Fuerza que todos los selectores y etiquetas de la barra superior reflejen exactamente `state`
   */
  function syncTopBarControlsWithState() {
    syncCitySelectWithCoords(state.latitude, state.longitude, state.locationName);

    const varSelect = document.getElementById('tmVariableSelect');
    if (varSelect && EarthLensCharts.VARIABLES_META[state.variable]) {
      varSelect.value = state.variable;
    }

    const modeSelect = document.getElementById('tmMapModeSelect');
    if (modeSelect) {
      modeSelect.value = mapMode;
    }

    const startInput = document.getElementById('tmStartYear');
    const endInput = document.getElementById('tmEndYear');
    if (startInput) startInput.value = state.start_year;
    if (endInput) endInput.value = state.end_year;

    const varMeta = EarthLensCharts.VARIABLES_META[state.variable] || EarthLensCharts.VARIABLES_META.T2M;
    setText('tmTitleLocation', state.locationName);
    setText('tmVariableBadge', `${varMeta.name} (${state.variable})`);
    setText('tmPeriodBadge', `${state.start_year}–${state.end_year}`);
    setText(
      'tmCoordsText',
      `Lat: ${Number(state.latitude).toFixed(2)}° · Lon: ${Number(state.longitude).toFixed(2)}°`
    );
    setText(
      'tmBoxSpanText',
      'Ciudad verificada; datos de grilla NASA POWER'
    );
  }

  function syncCitySelectWithCoords(lat, lon, locName) {
    const citySelect = document.getElementById('tmCitySelect');
    if (!citySelect) return;

    const options = Array.from(citySelect.querySelectorAll('option'));
    for (const opt of options) {
      if (opt.value === 'custom') continue;
      const oLat = parseFloat(opt.dataset.lat);
      const oLon = parseFloat(opt.dataset.lon);
      if (Math.abs(oLat - lat) < 0.22 && Math.abs(oLon - lon) < 0.22) {
        citySelect.value = opt.value;
        state.city_id = opt.value;
        state.locationName = opt.textContent;
        return;
      }
    }

    let customOpt = citySelect.querySelector('option[value="custom"]');
    if (!customOpt) {
      customOpt = document.createElement('option');
      customOpt.value = 'custom';
      citySelect.prepend(customOpt);
    }
    const cleanLabel =
      locName && !locName.startsWith('Zona (') && !locName.startsWith('Coordenada (')
        ? locName
        : `Zona seleccionada (${Number(lat).toFixed(2)}°, ${Number(lon).toFixed(2)}°)`;
    customOpt.dataset.lat = String(lat);
    customOpt.dataset.lon = String(lon);
    customOpt.textContent = cleanLabel;
    citySelect.value = 'custom';
    state.city_id = null;
    state.locationName = cleanLabel;
  }

  /**
   * Sincroniza la altura visible real en navegadores móviles (ej. Chrome iOS/Android con barra inferior)
   */
  function syncViewportHeight() {
    const vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    if (vh && vh > 100) {
      document.documentElement.style.setProperty('--app-height', `${Math.round(vh)}px`);
    }
  }

  /**
   * Calcula el zoom mínimo para que el mapa ocupe toda la pantalla sin repetirse ni mostrar bandas vacías en los polos
   */
  function computeMinWorldZoom(container) {
    const w = (container && container.clientWidth) || window.innerWidth || 1280;
    const h = (container && container.clientHeight) || window.innerHeight || 800;
    const maxDim = Math.max(w, h);
    return Math.max(2.75, Math.ceil(Math.log2(maxDim / 256) * 4) / 4);
  }

  /**
   * 2. Inicializa el mapa Leaflet con vista Satelital + Cuadrante Redimensionable
   */
  function initLeafletMap() {
    syncViewportHeight();
    const mapContainer = document.getElementById('timeMachineMap');
    if (!mapContainer || typeof L === 'undefined') return;

    const minWorldZoom = computeMinWorldZoom(mapContainer);

    mapInstance = L.map('timeMachineMap', {
      center: [state.latitude, state.longitude],
      zoom: Math.max(7, minWorldZoom),
      minZoom: minWorldZoom,
      maxZoom: 17,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      zoomControl: false,
      worldCopyJump: true,
      maxBounds: [
        [-85, -Infinity],
        [85, Infinity]
      ],
      maxBoundsViscosity: 1.0
    });

    // Cuando se llega al zoom mínimo (final del mapa) y el usuario sigue scrolleando hacia atrás,
    // desplazar horizontalmente el planeta de forma continua en lugar de repetir el mapa.
    mapContainer.addEventListener(
      'wheel',
      (ev) => {
        if (!mapInstance) return;
        const currentZ = mapInstance.getZoom();
        const minZ = mapInstance.getMinZoom();
        if (currentZ <= minZ + 0.05 && ev.deltaY > 0) {
          ev.preventDefault();
          ev.stopPropagation();
          const stepX = Math.max(-180, Math.min(180, ev.deltaY * 1.4));
          mapInstance.panBy([stepX, 0], { animate: false });
        }
      },
      { passive: false, capture: true }
    );

    L.control.zoom({ position: 'bottomright' }).addTo(mapInstance);

    const satelliteLayer = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 17,
        attribution: 'Satélite &copy; Esri · NASA Earthdata MERRA-2'
      }
    );

    const labelsOverlay = L.tileLayer(
      'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 17,
        opacity: 0.78
      }
    );

    const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors'
    });

    satelliteLayer.addTo(mapInstance);
    labelsOverlay.addTo(mapInstance);

    L.control
      .layers(
        { 'Imagen Satelital': satelliteLayer, 'Mapa Base (OSM)': osmLayer },
        { 'Límites y Localidades': labelsOverlay },
        { position: 'bottomright' }
      )
      .addTo(mapInstance);

    const plumePane = mapInstance.createPane('satelliteWeatherPane');
    plumePane.style.zIndex = 380;
    plumePane.classList.add('leaflet-satellite-weather-pane');

    weatherPlumeGroup = L.layerGroup().addTo(mapInstance);
    zoneLayerGroup = L.layerGroup().addTo(mapInstance);
    resizeHandlesGroup = L.layerGroup().addTo(mapInstance);
    nationalLayerGroup = L.layerGroup();

    mapInstance.on('click', () => { document.getElementById('tmDataNotice').textContent='Seleccionar una ciudad del catalogo; las coordenadas libres todavia no estan habilitadas.'; });
  }

  /**
   * 3. Consulta POST /api/time-machine incluyendo lat_span y lon_span del cuadrante
   */
  async function loadTimeMachineData(options = {}) {
    activeAbortController?.abort();
    activeAbortController = new AbortController();
    const mySeq = ++requestSeq;
    const spinner = document.getElementById('tmLoadingSpinner');
    spinner?.classList.remove('d-none');
    const notice = document.getElementById('tmDataNotice');
    window.EarthLensForecast?.setData(null);
    notice.textContent='Consultando la ciudad y el período seleccionados…';
    syncTopBarControlsWithState();
    persistStateToStorageAndURL();
    try {
      if (!state.city_id) throw new Error('Seleccionar una ciudad argentina del catalogo.');
      const res = await fetch('/api/time-machine', {method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({city_id:state.city_id,variable:state.variable,start_year:state.start_year,
          end_year:state.end_year,split_year:state.split_year,include_regional:true}),signal:activeAbortController.signal});
      const value = await res.json();
      if (!res.ok || value.status !== 'ok') throw new Error(value.error?.message || 'No hay datos verificados para esta seleccion.');
      if (mySeq !== requestSeq) return;
      notice.textContent = 'Datos reales de ciudades verificadas. Analisis exploratorio provisional; proyecciones exploratorias separadas del historico.';
      notice.dataset.error = 'false';
      mapMode='national';
      const mode=document.getElementById('tmMapModeSelect');if(mode)mode.value='national';
      ['btnShrinkBox','btnExpandBox','btnResetBox','btnSlideZoomZone'].forEach(id=>{const button=document.getElementById(id);if(button){button.disabled=true;button.title='Seleccion espacial pendiente de validacion territorial y datos reales.';}});
      applyTimeMachinePayload(value.data, options);
    } catch (error) {
      if (mySeq !== requestSeq || error.name === 'AbortError') return;
      stopPlayback();currentData=null;
      [weatherPlumeGroup,zoneLayerGroup,nationalLayerGroup,resizeHandlesGroup].forEach(group=>group?.clearLayers());
      document.getElementById('tmTimelineTableBody')?.replaceChildren();
      trendChartInstance?.destroy();trendChartInstance=null;
      ['tmActiveValue','tmActiveAnomaly','tmActiveLevelBadge','tmActiveYearDisplay'].forEach(id=>setText(id,'--'));
      notice.textContent=error.message;notice.dataset.error='true';
    } finally {if(mySeq===requestSeq)spinner?.classList.add('d-none');}
  }

  function applyTimeMachinePayload(data, options = {}) {
    if (!data || !Array.isArray(data.timeline) || data.timeline.length === 0) return;
    currentData = data;

    // Actualizar state con la ubicación resuelta por el backend
    if (data.location) {
      state.latitude = Number(data.location.latitude);
      state.longitude = Number(data.location.longitude);
      state.locationName = data.location.name || state.locationName;
      if (data.location.id && data.location.id !== 'custom') {
        state.city_id = data.location.id;
      }
    }

    const minYr = data.timeline[0].year;
    const maxYr = data.timeline[data.timeline.length - 1].year;
    if (activeYear < minYr || activeYear > maxYr) {
      activeYear = maxYr;
    }

    const slider = document.getElementById('tmYearSlider');
    if (slider) {
      slider.min = minYr;
      slider.max = maxYr;
      slider.value = activeYear;
    }
    setText('tmSliderMinLabel', String(minYr));
    setText('tmSliderMaxLabel', String(maxYr));

    const splitSlider = document.getElementById('tmSplitYearSlider');
    const splitYr = data.period?.split_year || Math.floor((minYr + maxYr) / 2);
    state.split_year = splitYr;
    if (splitSlider) {
      splitSlider.min = minYr + 2;
      splitSlider.max = maxYr - 1;
      splitSlider.value = splitYr;
    }

    const unitDisp = data.display_unit || (data.unit === 'deg C' ? '°C' : data.unit);
    setText('tmRegionBadge', `${data.location?.region || 'Argentina'}`);
    syncTopBarControlsWithState();
    persistStateToStorageAndURL();

    updateWeatherLegend(data.variable);
    updateNavigationLinks(data);
    renderSliderStripes(data.timeline, data.variable);
    renderEpochComparisonUI(data.period_comparison, unitDisp);
    renderExtremeRecords(data.anomalies, unitDisp);
    renderAnomalyCards(data.anomalies, unitDisp);
    renderTimelineTable(data.timeline, unitDisp, data.variable);
    window.EarthLensForecast?.setData(data);

    rebuildMapLayers(data, !options.preserveZoom);
    setActiveYear(activeYear);
  }

  function updateWeatherLegend(variable) {
    const meta = SATELLITE_TV_METADATA[variable] || SATELLITE_TV_METADATA.T2M;
    setText('tmWeatherTvTitle', meta.title);
    setText('tmScaleMinText', meta.minLabel);
    setText('tmScaleMaxText', meta.maxLabel);
    const bar = document.getElementById('tmColorScaleBar');
    if (bar) {
      bar.className = `tm-color-scale-bar flex-grow-1 ${meta.scaleClass}`;
    }
  }

  /**
   * Mantiene sincronizados tanto los botones de riel como los links del navbar superior
   */
  function updateNavigationLinks(data) {
    const qRes = new URLSearchParams({
      city_id: data.location.id,
      location: data.location.name,
      variable: data.variable,
      start_year: data.period.start_year,
      end_year: data.period.end_year
    });
    const resUrl = `/results?${qRes.toString()}`;
    const resLink = document.getElementById('tmLinkToResults');
    const navRes = document.getElementById('navLinkResults');
    if (resLink) resLink.href = resUrl;
    if (navRes) navRes.href = resUrl;

    const qCmp = new URLSearchParams({
      city_id_a: data.location.id,
      nameA: data.location.name,
      variable: data.variable,
      start_year: data.period.start_year,
      end_year: data.period.end_year
    });
    const cmpUrl = `/compare?${qCmp.toString()}`;
    const cmpLink = document.getElementById('tmLinkToCompare');
    const navCmp = document.getElementById('navLinkCompare');
    if (cmpLink) cmpLink.href = cmpUrl;
    if (navCmp) navCmp.href = cmpUrl;
  }

  /**
   * 5. Construye las capas meteorológicas + Cuadrante Editable (con manijas de arrastre en las esquinas)
   */
  function rebuildMapLayers(data, shouldZoom = true) {
    if (!mapInstance || !zoneLayerGroup || !nationalLayerGroup || !weatherPlumeGroup || !resizeHandlesGroup) return;

    weatherPlumeGroup.clearLayers();
    zoneLayerGroup.clearLayers();
    resizeHandlesGroup.clearLayers();
    nationalLayerGroup.clearLayers();
    zoneCellLayers = [];
    nationalLayers = [];

    const cells = data.spatial_zone?.cells || [];
    const latStep = Number(data.spatial_zone?.cell_resolution_deg?.lat || state.lat_span / 3);
    const lonStep = Number(data.spatial_zone?.cell_resolution_deg?.lon || state.lon_span / 3);
    // Radio de la pluma proporcional al tamaño actual del cuadrante
    const baseRadiusMeters = Math.max(12000, Math.min(950000, ((latStep + lonStep) / 2) * 105000));

    cells.forEach((cell) => {
      const plumeCircle = L.circle([cell.latitude, cell.longitude], {
        pane: 'satelliteWeatherPane',
        radius: cell.is_center ? baseRadiusMeters * 1.15 : baseRadiusMeters * 0.95,
        stroke: false,
        fillColor: '#3d8c95',
        fillOpacity: cell.is_center ? 0.78 : 0.62
      });

      const rect = L.rectangle(cell.bounds, {
        color: cell.is_center ? 'rgba(125, 211, 252, 0.72)' : 'rgba(226, 232, 240, 0.24)',
        weight: cell.is_center ? 1.5 : 0.75,
        dashArray: cell.is_center ? null : '3, 4',
        fillColor: '#3d8c95',
        fillOpacity: 0.08
      });
      rect.bindTooltip('', { sticky: true, className: 'tm-sat-city-tooltip' });

      rect.addTo(zoneLayerGroup);
      zoneCellLayers.push({ cell, rect, plumeCircle });
    });

    // Marco exterior del cuadrante + 4 manijas arrastrables en los vértices para achicar o expandir
    if (data.spatial_zone?.zone_bounds) {
      const bounds = data.spatial_zone.zone_bounds;
      outerBoundingRect = L.rectangle(bounds, {
        color: '#7dd3fc',
        weight: 2.1,
        opacity: 0.92,
        fill: false,
        interactive: false
      }).addTo(zoneLayerGroup);

      buildResizableCornerHandles(bounds);
    }

    // Punto central
    const centerMarker = L.circleMarker([data.location.latitude, data.location.longitude], {
      radius: 5.5,
      color: '#38bdf8',
      weight: 2.2,
      fillColor: '#080c14',
      fillOpacity: 1
    }).bindTooltip(`${data.location.name}`, {
      permanent: false,
      direction: 'top',
      className: 'tm-sat-city-tooltip'
    });
    centerMarker.addTo(zoneLayerGroup);

    // Red de 25 estaciones argentinas
    const cities = data.regional_cities || [];
    cities.forEach((city) => {
      const isSelectedCity =
        Math.abs(city.latitude - data.location.latitude) < 0.2 &&
        Math.abs(city.longitude - data.location.longitude) < 0.2;

      const plume = L.circle([city.latitude, city.longitude], {
        pane: 'satelliteWeatherPane',
        radius: isSelectedCity ? 230000 : 185000,
        stroke: false,
        fillColor: '#3d8c95',
        fillOpacity: 0.68
      });

      const marker = L.circleMarker([city.latitude, city.longitude], {
        radius: isSelectedCity ? 8.5 : 6,
        color: '#ffffff',
        weight: isSelectedCity ? 2.2 : 1.1,
        fillColor: '#3d8c95',
        fillOpacity: 0.95
      });

      marker.on('click', () => {
        state.city_id = city.id;
        state.latitude = city.latitude;
        state.longitude = city.longitude;
        state.locationName = `${city.name}, ${city.province}`;
        syncTopBarControlsWithState();
        persistStateToStorageAndURL();
        loadTimeMachineData();
      });

      marker.addTo(nationalLayerGroup);
      nationalLayers.push({ city, marker, plume, isSelectedCity });
    });

    applyMapModeView(shouldZoom);
  }

  /**
   * Crea 4 vértices arrastrables sobre el cuadrante para achicarlo o expandirlo libremente
   */
  function buildResizableCornerHandles(bounds) {
    if (!resizeHandlesGroup) return;
    resizeHandlesGroup.clearLayers();

    const south = bounds[0][0];
    const west = bounds[0][1];
    const north = bounds[1][0];
    const east = bounds[1][1];

    const corners = [
      { pos: [north, west], label: 'Arrastrar vértice NO para redimensionar cuadrante' },
      { pos: [north, east], label: 'Arrastrar vértice NE para redimensionar cuadrante' },
      { pos: [south, west], label: 'Arrastrar vértice SO para redimensionar cuadrante' },
      { pos: [south, east], label: 'Arrastrar vértice SE para redimensionar cuadrante' }
    ];

    const handleIcon = L.divIcon({
      className: 'tm-resize-handle',
      iconSize: [12, 12],
      iconAnchor: [6, 6]
    });

    corners.forEach((corner) => {
      const handle = L.marker(corner.pos, {
        icon: handleIcon,
        draggable: true,
        title: corner.label
      });

      handle.on('drag', (ev) => {
        const latlng = ev.target.getLatLng();
        const newLatSpan = Math.max(0.3, Math.min(30.0, Math.abs(latlng.lat - state.latitude) * 2));
        const newLonSpan = Math.max(0.3, Math.min(36.0, Math.abs(latlng.lng - state.longitude) * 2));
        if (outerBoundingRect) {
          outerBoundingRect.setBounds([
            [state.latitude - newLatSpan / 2, state.longitude - newLonSpan / 2],
            [state.latitude + newLatSpan / 2, state.longitude + newLonSpan / 2]
          ]);
        }
        setText('tmBoxSpanText', `Cuadrante: ${newLatSpan.toFixed(2)}° × ${newLonSpan.toFixed(2)}°`);
      });

      handle.on('dragend', (ev) => {
        const latlng = ev.target.getLatLng();
        state.lat_span = Number(
          Math.max(0.3, Math.min(30.0, Math.abs(latlng.lat - state.latitude) * 2)).toFixed(3)
        );
        state.lon_span = Number(
          Math.max(0.3, Math.min(36.0, Math.abs(latlng.lng - state.longitude) * 2)).toFixed(3)
        );
        loadTimeMachineData({ preserveZoom: true });
      });

      handle.addTo(resizeHandlesGroup);
    });
  }

  /**
   * Escala el cuadrante por un factor (ej. 0.7 para achicar, 1.4 para expandir)
   */
  function scaleZoneBoundingBox(factor, reset = false) {
    if (reset) {
      state.lat_span = 1.5;
      state.lon_span = 1.875;
    } else {
      state.lat_span = Number(Math.max(0.3, Math.min(30.0, state.lat_span * factor)).toFixed(3));
      state.lon_span = Number(Math.max(0.3, Math.min(36.0, state.lon_span * factor)).toFixed(3));
    }
    if (mapMode !== 'zone') {
      mapMode = 'zone';
      const modeSelect = document.getElementById('tmMapModeSelect');
      if (modeSelect) modeSelect.value = 'zone';
    }
    loadTimeMachineData({ preserveZoom: false });
  }

  /**
   * Calcula los márgenes seguros del mapa según el tamaño real de las barras HUD
   * para que el cuadrante nunca quede oculto detrás de las barras ni botones
   */
  function getSafeMapBoundsOptions() {
    const topEl = document.querySelector('.tm-hud-top');
    const bottomEl = document.getElementById('tmBottomBar');
    const leftEl = document.getElementById('tmLeftRail');
    const rightEl = document.getElementById('tmRightRail');

    const topPad = (topEl ? topEl.offsetHeight : 54) + 24;
    const bottomPad = (bottomEl ? bottomEl.offsetHeight : 84) + 24;
    const leftPad = (leftEl ? leftEl.offsetWidth : 38) + 24;
    const rightPad = (rightEl ? rightEl.offsetWidth : 38) + 24;

    return {
      paddingTopLeft: [leftPad, topPad],
      paddingBottomRight: [rightPad, bottomPad],
      duration: 0.55
    };
  }

  function applyMapModeView(shouldZoom = true) {
    if (!mapInstance || !currentData) return;
    if (!currentData.capabilities?.spatial_resize) mapMode='national';

    weatherPlumeGroup.clearLayers();

    if (mapMode === 'national') {
      if (mapInstance.hasLayer(zoneLayerGroup)) mapInstance.removeLayer(zoneLayerGroup);
      if (mapInstance.hasLayer(resizeHandlesGroup)) mapInstance.removeLayer(resizeHandlesGroup);
      if (!mapInstance.hasLayer(nationalLayerGroup)) nationalLayerGroup.addTo(mapInstance);
      nationalLayers.forEach(({ plume }) => plume.addTo(weatherPlumeGroup));
      setText('tmCellHudInfo', `Red Nacional: ${(currentData.regional_cities || []).length} ciudades de grilla`);
      if (shouldZoom) {
        mapInstance.flyTo([-38.5, -64.0], 4, { duration: 0.6 });
      }
    } else {
      if (mapInstance.hasLayer(nationalLayerGroup)) mapInstance.removeLayer(nationalLayerGroup);
      if (!mapInstance.hasLayer(zoneLayerGroup)) zoneLayerGroup.addTo(mapInstance);
      if (!mapInstance.hasLayer(resizeHandlesGroup)) resizeHandlesGroup.addTo(mapInstance);
      zoneCellLayers.forEach(({ plumeCircle }) => plumeCircle.addTo(weatherPlumeGroup));
      setText(
        'tmCellHudInfo',
        `Cuadrante ${state.lat_span.toFixed(2)}° × ${state.lon_span.toFixed(2)}° (arrastra vértices)`
      );
      if (shouldZoom && currentData.spatial_zone?.zone_bounds) {
        mapInstance.flyToBounds(currentData.spatial_zone.zone_bounds, getSafeMapBoundsOptions());
      }
    }
    updateMapColorsForYear(activeYear);
  }

  /**
   * 6. Actualiza el año activo en mapa, barra inferior y gráficos
   */
  function setActiveYear(year) {
    if (!currentData || !Array.isArray(currentData.timeline)) return;
    const yrNum = Number(year);
    const point = currentData.timeline.find((p) => p.year === yrNum) || currentData.timeline[0];
    if (!point) return;

    activeYear = point.year;
    const unitDisp = currentData.display_unit || '°C';
    const satColor = getSatelliteWeatherColor(currentData.variable, point.z_score);

    const slider = document.getElementById('tmYearSlider');
    if (slider && Number(slider.value) !== activeYear) {
      slider.value = activeYear;
    }

    setText('tmActiveYearDisplay', String(activeYear));
    setText('tmActiveValue', `${point.value.toFixed(1)} ${unitDisp}`);

    const anomSign = point.anomaly >= 0 ? '+' : '';
    const anomEl = document.getElementById('tmActiveAnomaly');
    if (anomEl) {
      anomEl.textContent = `${anomSign}${point.anomaly.toFixed(2)} ${unitDisp}`;
      anomEl.style.backgroundColor = satColor;
      anomEl.style.color = '#ffffff';
    }

    const levelLabels = {
      extreme_high: 'Anomalía alta extrema (+2σ)',
      moderate_high: 'Superior al promedio (+1.5σ)',
      mild_high: 'Ligeramente sobre la media',
      normal: 'Dentro del rango normal',
      mild_low: 'Ligeramente bajo la media',
      moderate_low: 'Inferior al promedio (-1.5σ)',
      extreme_low: 'Anomalía baja extrema (-2σ)'
    };
    const levelText = levelLabels[point.anomaly_level] || 'Dentro del rango normal';
    const levelBadge = document.getElementById('tmActiveLevelBadge');
    if (levelBadge) {
      levelBadge.textContent = levelText;
    }
    const levelBadgeMobile = document.getElementById('tmActiveLevelBadgeMobile');
    if (levelBadgeMobile) {
      levelBadgeMobile.textContent = levelText;
    }

    document.querySelectorAll('.tm-stripe-item').forEach((el) => {
      el.classList.toggle('is-active', Number(el.dataset.year) === activeYear);
    });
    document.querySelectorAll('.tm-anomaly-card').forEach((el) => {
      el.classList.toggle('is-selected', Number(el.dataset.year) === activeYear);
    });
    document.querySelectorAll('#tmTimelineTableBody tr').forEach((row) => {
      row.classList.toggle('table-active', Number(row.dataset.year) === activeYear);
    });

    updateMapColorsForYear(activeYear);
    renderSynchronizedCharts(currentData, activeYear);
  }

  function updateMapColorsForYear(year) {
    if (!currentData) return;
    const yrKey = String(year);
    const unitDisp = currentData.display_unit || '°C';
    const varCode = currentData.variable;

    zoneCellLayers.forEach(({ cell, rect, plumeCircle }) => {
      const yrData = cell.by_year?.[yrKey];
      if (!yrData) return;
      const satColor = getSatelliteWeatherColor(varCode, yrData.z_score);

      plumeCircle.setStyle({
        fillColor: satColor,
        fillOpacity: cell.is_center ? 0.82 : 0.64
      });
      rect.setStyle({
        fillColor: satColor,
        fillOpacity: cell.is_center ? 0.2 : 0.08
      });

      const sign = yrData.anomaly >= 0 ? '+' : '';
      rect.setTooltipContent(
        `<strong>${cell.label}</strong> (${year})<br>` +
          `Valor: <strong>${yrData.value.toFixed(2)} ${unitDisp}</strong><br>` +
          `Anomalía: ${sign}${yrData.anomaly.toFixed(2)} ${unitDisp} (z = ${yrData.z_score >= 0 ? '+' : ''}${yrData.z_score})`
      );
    });

    nationalLayers.forEach(({ city, marker, plume, isSelectedCity }) => {
      const yrData = city.by_year?.[yrKey];
      if (!yrData) return;
      const satColor = getSatelliteWeatherColor(varCode, yrData.z_score);

      plume.setStyle({
        fillColor: satColor,
        fillOpacity: isSelectedCity ? 0.82 : 0.64
      });
      marker.setStyle({
        fillColor: satColor,
        radius: isSelectedCity ? 9.5 : yrData.is_anomaly ? 8 : 6
      });

      const sign = yrData.anomaly >= 0 ? '+' : '';
      marker.bindTooltip(
        `<strong>${city.name}</strong> (${year})<br>` +
          `Valor: <strong>${yrData.value.toFixed(2)} ${unitDisp}</strong> (${sign}${yrData.anomaly.toFixed(2)} ${unitDisp})`,
        { direction: 'top', className: 'tm-sat-city-tooltip' }
      );
    });
  }

  /**
   * 7. Renderiza la cinta cromática bajo el slider inferior
   */
  function renderSliderStripes(timeline, variable) {
    const stripesEl = document.getElementById('tmClimateStripes');
    const unitDisp = currentData?.display_unit || '°C';

    if (stripesEl) {
      stripesEl.innerHTML = timeline
        .map((pt) => {
          const satColor = getSatelliteWeatherColor(variable, pt.z_score);
          return `<div class="tm-stripe-item ${pt.year === activeYear ? 'is-active' : ''}" data-year="${pt.year}" style="background-color: ${satColor};" title="${pt.year}: ${pt.value.toFixed(2)} ${unitDisp}"></div>`;
        })
        .join('');
      stripesEl.querySelectorAll('.tm-stripe-item').forEach((el) => {
        el.addEventListener('click', () => {
          stopPlayback();
          setActiveYear(Number(el.dataset.year));
        });
      });
    }

    const anomCount = timeline.filter((p) => p.is_anomaly).length;
    setText('tmDockAnomalyCount', String(anomCount));
  }

  /**
   * 8. Renderiza los dos gráficos dentro de sus respectivas ventanitas
   */
  function renderSynchronizedCharts(data, highlightedYear) {
    const timeline = data.timeline || [];
    const unitDisp = data.display_unit || '°C';
    const slope = Number(data.statistics?.slope ?? 0);
    const meanVal = Number(data.statistics?.mean ?? 0);

    setText('tmSlopeBadge', `Pendiente: ${slope >= 0 ? '+' : ''}${(slope * 10).toFixed(2)} ${unitDisp}/década`);
    setText('tmMeanBadge', `Media: ${meanVal.toFixed(2)} ${unitDisp}`);

    const canvas1 = document.getElementById('tmTrendChart');
    if (canvas1 && typeof Chart !== 'undefined') {
      if (trendChartInstance) {
        trendChartInstance.destroy();
      }
      const years = timeline.map((p) => p.year);
      const values = timeline.map((p) => p.value);
      const trends = timeline.map((p) => p.trend_value);
      const pointRadii = timeline.map((p) => (p.year === highlightedYear ? 7.5 : 3.5));
      const pointColors = timeline.map((p) =>
        p.year === highlightedYear ? '#9e2a2b' : getSatelliteWeatherColor(data.variable, p.z_score)
      );

      trendChartInstance = new Chart(canvas1.getContext('2d'), {
        type: 'line',
        data: {
          labels: years,
          datasets: [
            {
              label: `Valor observado (${unitDisp})`,
              data: values,
              borderColor: '#2b5c8f',
              backgroundColor: 'rgba(43, 92, 143, 0.10)',
              pointBackgroundColor: pointColors,
              pointBorderColor: '#ffffff',
              pointBorderWidth: 1.5,
              pointRadius: pointRadii,
              borderWidth: 2.2,
              tension: 0.2
            },
            {
              label: `Tendencia lineal OLS`,
              data: trends,
              borderColor: '#b5533c',
              borderDash: [6, 4],
              borderWidth: 2,
              pointRadius: 0,
              tension: 0
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          onClick: (_, elements) => {
            if (elements && elements.length > 0) {
              const idx = elements[0].index;
              if (years[idx] !== undefined) {
                stopPlayback();
                setActiveYear(years[idx]);
              }
            }
          },
          plugins: {
            legend: { position: 'top' }
          },
          scales: {
            x: { grid: { color: 'rgba(203, 213, 225, 0.5)' } },
            y: {
              title: { display: true, text: `${data.variable_name} (${unitDisp})` },
              grid: { color: 'rgba(203, 213, 225, 0.5)' }
            }
          }
        }
      });
    }

    EarthLensCharts.renderAnomalyBarChart(
      'tmAnomalyBarChart',
      timeline,
      data.variable,
      unitDisp,
      highlightedYear,
      (clickedYr) => {
        stopPlayback();
        setActiveYear(clickedYr);
      }
    );
  }

  /**
   * 9. Comparador de Épocas y Detector de Anomalías (Ventanita 3)
   */
  function renderEpochComparisonUI(cmp, unitDisp) {
    if (!cmp) return;
    const pA = cmp.period_a;
    const pB = cmp.period_b;

    setText('tmSplitYearLabel', `Corte ${cmp.split_year} (${pA.label} vs ${pB.label})`);
    setText('tmEpochPeriodA', `${pA.label}`);
    setText('tmEpochMeanA', `${pA.mean.toFixed(2)} ${unitDisp}`);
    setText('tmEpochStatsA', `σ: ${pA.std_dev.toFixed(2)} · Pend: ${pA.change_per_decade >= 0 ? '+' : ''}${pA.change_per_decade.toFixed(2)}/déc`);

    setText('tmEpochPeriodB', `${pB.label}`);
    setText('tmEpochMeanB', `${pB.mean.toFixed(2)} ${unitDisp}`);
    setText('tmEpochStatsB', `σ: ${pB.std_dev.toFixed(2)} · Pend: ${pB.change_per_decade >= 0 ? '+' : ''}${pB.change_per_decade.toFixed(2)}/déc`);

    const dSign = cmp.delta_mean >= 0 ? '+' : '';
    setText('tmEpochDeltaMean', `${dSign}${cmp.delta_mean.toFixed(2)} ${unitDisp}`);
    setText('tmEpochDeltaPct', `(${dSign}${cmp.delta_percent.toFixed(1)}%)`);
    setText('tmEpochPValue', `p = ${cmp.p_value < 0.0001 ? '< 0.0001' : cmp.p_value.toFixed(4)}`);
    setText('tmEpochSummaryText', cmp.summary);

    const badge = document.getElementById('tmEpochShiftBadge');
    if (badge) {
      badge.textContent = cmp.significant_shift ? 'Cambio significativo (p < 0.05)' : 'Variación no significativa (p ≥ 0.05)';
    }
  }

  function renderExtremeRecords(anomalies, unitDisp) {
    const maxRec = anomalies?.max_record;
    const minRec = anomalies?.min_record;
    if (maxRec) {
      setText('tmMaxRecordVal', `${maxRec.value.toFixed(2)} ${unitDisp}`);
      setText('tmMaxRecordYr', `Año ${maxRec.year} (z = +${maxRec.z_score.toFixed(2)})`);
      const btnMax = document.getElementById('btnJumpMaxRecord');
      if (btnMax) {
        btnMax.onclick = () => {
          stopPlayback();
          setActiveYear(maxRec.year);
        };
      }
    }
    if (minRec) {
      setText('tmMinRecordVal', `${minRec.value.toFixed(2)} ${unitDisp}`);
      setText('tmMinRecordYr', `Año ${minRec.year} (z = ${minRec.z_score.toFixed(2)})`);
      const btnMin = document.getElementById('btnJumpMinRecord');
      if (btnMin) {
        btnMin.onclick = () => {
          stopPlayback();
          setActiveYear(minRec.year);
        };
      }
    }
  }

  function renderAnomalyCards(anomalies, unitDisp) {
    const container = document.getElementById('tmAnomaliesContainer');
    const events = anomalies?.events || [];
    setText('tmAnomalyListCount', `${events.length} eventos`);
    if (!container) return;

    if (events.length === 0) {
      container.innerHTML = `
        <div class="text-secondary small p-3 tm-subpanel">
          No se registraron anomalías extremas (|z| ≥ 1.5) en este período.
        </div>`;
      return;
    }

    container.innerHTML = events
      .map((ev) => {
        const cleanBadge = String(ev.badge || 'Anomalía').replace(/[^\w\sÁÉÍÓÚáéíóúÑñ()+-]/g, '').trim();
        const satColor = getSatelliteWeatherColor(currentData?.variable, ev.z_score);
        return `
        <div class="tm-anomaly-card ${ev.year === activeYear ? 'is-selected' : ''}" data-year="${ev.year}">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-bold text-light small">Año ${ev.year} · <span style="color:${satColor}">${cleanBadge}</span></span>
            <button type="button" class="btn btn-sm tm-hud-btn py-0 px-2 js-jump-year" data-year="${ev.year}">
              Posicionar
            </button>
          </div>
          <p class="small text-secondary mb-0" style="font-size: 0.74rem;">${ev.description || `Valor: ${ev.value.toFixed(2)} ${unitDisp} (z = ${ev.z_score})`}</p>
        </div>`;
      })
      .join('');

    container.querySelectorAll('.js-jump-year').forEach((btn) => {
      btn.addEventListener('click', () => {
        stopPlayback();
        setActiveYear(Number(btn.dataset.year));
      });
    });
  }

  function renderTimelineTable(timeline, unitDisp, variable) {
    const tbody = document.getElementById('tmTimelineTableBody');
    if (!tbody) return;

    tbody.innerHTML = timeline
      .map((pt) => {
        const sign = pt.anomaly >= 0 ? '+' : '';
        const satColor = getSatelliteWeatherColor(variable, pt.z_score);
        const isCurrent = pt.year === activeYear;
        return `
          <tr data-year="${pt.year}" style="cursor: pointer;" class="${isCurrent ? 'table-active' : ''}">
            <td class="fw-bold font-monospace">${pt.year}</td>
            <td>${pt.value.toFixed(2)} ${unitDisp}</td>
            <td>${pt.trend_value.toFixed(2)} ${unitDisp}</td>
            <td class="fw-semibold" style="color: ${satColor};">${sign}${pt.anomaly.toFixed(2)} ${unitDisp}</td>
            <td class="font-monospace">${pt.z_score >= 0 ? '+' : ''}${pt.z_score.toFixed(2)}</td>
            <td>${pt.is_anomaly ? '<span class="tm-stat-pill">Anomalía</span>' : '<span class="text-secondary small">Normal</span>'}</td>
          </tr>`;
      })
      .join('');

    tbody.querySelectorAll('tr').forEach((row) => {
      row.addEventListener('click', () => {
        stopPlayback();
        setActiveYear(Number(row.dataset.year));
      });
    });
  }

  /**
   * 10. Gestión de Ventanitas Flotantes
   */
  function togglePopupWindow(windowId) {
    const allWindows = document.querySelectorAll('.tm-popup-window');
    const allButtons = document.querySelectorAll('.tm-icon-btn[data-window-target]');

    if (openWindowId === windowId) {
      allWindows.forEach((w) => w.classList.add('d-none'));
      allButtons.forEach((b) => b.classList.remove('is-active'));
      openWindowId = null;
      return;
    }

    allWindows.forEach((w) => {
      w.classList.toggle('d-none', w.id !== windowId);
    });
    allButtons.forEach((b) => {
      b.classList.toggle('is-active', b.dataset.windowTarget === windowId);
    });
    openWindowId = windowId;

    if(windowId === 'winForecast')setTimeout(()=>window.EarthLensForecast?.render(),40);
    if (currentData && (windowId === 'winTrend' || windowId === 'winAnomaliesBar')) {
      setTimeout(() => renderSynchronizedCharts(currentData, activeYear), 40);
    }
  }

  /**
   * 11. Reproducción automática (Play / Pause con iconos SVG limpios)
   */
  function setPlayButtonSvg(playing) {
    const svg = document.getElementById('tmPlayIconSvg');
    if (!svg) return;
    if (playing) {
      svg.innerHTML = '<rect x="6" y="4" width="4" height="16" fill="currentColor"></rect><rect x="14" y="4" width="4" height="16" fill="currentColor"></rect>';
    } else {
      svg.innerHTML = '<polygon points="6 4 20 12 6 20 6 4" fill="currentColor"></polygon>';
    }
  }

  function togglePlayback() {
    if (isPlaying) {
      stopPlayback();
    } else {
      startPlayback();
    }
  }

  function startPlayback() {
    if (!currentData || !currentData.timeline?.length) return;
    isPlaying = true;
    setPlayButtonSvg(true);

    const years = currentData.timeline.map((p) => p.year);
    if (activeYear >= years[years.length - 1]) {
      setActiveYear(years[0]);
    }

    playTimer = setInterval(() => {
      const idx = years.indexOf(activeYear);
      if (idx < years.length - 1) {
        setActiveYear(years[idx + 1]);
      } else {
        setActiveYear(years[0]);
      }
    }, playSpeedMs);
  }

  function stopPlayback() {
    isPlaying = false;
    if (playTimer) {
      clearInterval(playTimer);
      playTimer = null;
    }
    setPlayButtonSvg(false);
  }

  function exportTimeMachineCSV() {
    if (!currentData || !currentData.timeline) return;
    const loc = currentData.location || {};
    const stats = currentData.statistics || {};
    const cmp = currentData.period_comparison || {};

    const metadata = [
      `Proyecto: EarthLens - Earth Time Machine (NASA Space Apps 2026)`,
      `Ubicacion: ${loc.name} (${loc.latitude}, ${loc.longitude}) | Region: ${loc.region}`,
      `Cuadrante: ${state.lat_span} deg lat x ${state.lon_span} deg lon`,
      `Variable: ${currentData.variable} (${currentData.display_unit}) | Fuente: ${currentData.source}`,
      `Tendencia: ${stats.change_per_decade} ${currentData.display_unit}/decada (p=${stats.p_value})`,
      `Comparacion Epocas (${cmp.period_a?.label} vs ${cmp.period_b?.label}): Delta=${cmp.delta_mean} (p=${cmp.p_value})`
    ];

    const headers = [
      'anio',
      'valor_observado',
      'tendencia_ols',
      'anomalia_vs_media',
      'z_score',
      'percentil',
      'es_anomalia',
      'unidad'
    ];
    const rows = currentData.timeline.map((pt) => [
      pt.year,
      pt.value,
      pt.trend_value,
      pt.anomaly,
      pt.z_score,
      pt.percentile,
      pt.is_anomaly,
      currentData.display_unit
    ]);

    EarthLensCharts.downloadCSV(
      `earthlens_timemachine_${currentData.variable.toLowerCase()}_${currentData.period.start_year}_${currentData.period.end_year}.csv`,
      headers,
      rows,
      metadata
    );
  }

  /**
   * 12. Enlace de eventos DOM, redimensionamiento de cuadrante y sincronización entre pestañas
   */
  function bindEvents() {
    const citySelect = document.getElementById('tmCitySelect');
    const varSelect = document.getElementById('tmVariableSelect');
    const startInput = document.getElementById('tmStartYear');
    const endInput = document.getElementById('tmEndYear');
    const btnLoad = document.getElementById('btnLoadTimeMachine');
    const slider = document.getElementById('tmYearSlider');
    const splitSlider = document.getElementById('tmSplitYearSlider');
    const btnPlay = document.getElementById('btnPlayPause');
    const btnPrev = document.getElementById('btnPrevYear');
    const btnNext = document.getElementById('btnNextYear');
    const mapModeSelect = document.getElementById('tmMapModeSelect');
    const btnZoomZone = document.getElementById('btnSlideZoomZone');
    const btnZoomArg = document.getElementById('btnSlideZoomArg');
    const btnShrinkBox = document.getElementById('btnShrinkBox');
    const btnExpandBox = document.getElementById('btnExpandBox');
    const btnResetBox = document.getElementById('btnResetBox');
    const btnExport = document.getElementById('btnExportTimeMachineCSV');
    const btnToggleTopFilters = document.getElementById('btnToggleTopFilters');
    const topFiltersCollapse = document.getElementById('tmTopFiltersCollapse');
    const btnToggleLeftRail = document.getElementById('btnToggleLeftRail');
    const leftRail = document.getElementById('tmLeftRail');
    const btnToggleRightRail = document.getElementById('btnToggleRightRail');
    const rightRail = document.getElementById('tmRightRail');
    const btnToggleBottomBar = document.getElementById('btnToggleBottomBar');
    const bottomBar = document.getElementById('tmBottomBar');

    // En pantallas muy pequeñas (< 576px), iniciar la barra derecha plegada para despejar el mapa
    if (window.innerWidth < 576 && rightRail && btnToggleRightRail) {
      rightRail.classList.remove('is-expanded');
      btnToggleRightRail.setAttribute('aria-expanded', 'false');
    }

    // Recalcular altura visible y límites del mapa al cambiar el tamaño de la ventana o barra móvil
    const handleViewportResize = () => {
      syncViewportHeight();
      if (mapInstance) {
        mapInstance.invalidateSize();
        const container = document.getElementById('timeMachineMap');
        const newMinZoom = computeMinWorldZoom(container);
        mapInstance.setMinZoom(newMinZoom);
        if (mapInstance.getZoom() < newMinZoom) {
          mapInstance.setZoom(newMinZoom);
        }
      }
    };

    window.addEventListener('resize', handleViewportResize);
    window.addEventListener('orientationchange', handleViewportResize);
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', handleViewportResize);
    }

    // Barra plegable superior (filtros en pantallas medianas/pequeñas)
    if (btnToggleTopFilters && topFiltersCollapse) {
      btnToggleTopFilters.addEventListener('click', () => {
        const isOpen = topFiltersCollapse.classList.toggle('is-open');
        btnToggleTopFilters.classList.toggle('is-active', isOpen);
        btnToggleTopFilters.setAttribute('aria-expanded', String(isOpen));
        setTimeout(() => {
          if (mapInstance) mapInstance.invalidateSize();
        }, 240);
      });
    }

    // Barra plegable izquierda (ventanas de análisis)
    if (btnToggleLeftRail && leftRail) {
      btnToggleLeftRail.addEventListener('click', () => {
        const expanded = leftRail.classList.toggle('is-expanded');
        btnToggleLeftRail.setAttribute('aria-expanded', String(expanded));
      });
    }

    // Barra plegable derecha (controles del cuadrante y vista)
    if (btnToggleRightRail && rightRail) {
      btnToggleRightRail.addEventListener('click', () => {
        const expanded = rightRail.classList.toggle('is-expanded');
        btnToggleRightRail.setAttribute('aria-expanded', String(expanded));
      });
    }

    // Barra plegable inferior (cinta cromática y leyenda en móviles)
    if (btnToggleBottomBar && bottomBar) {
      btnToggleBottomBar.addEventListener('click', () => {
        const expanded = bottomBar.classList.toggle('is-expanded');
        btnToggleBottomBar.setAttribute('aria-expanded', String(expanded));
      });
    }

    // Sincronizar automáticamente cuando el usuario vuelve desde otra pestaña o con el botón Atrás
    window.addEventListener('pageshow', () => {
      syncTopBarControlsWithState();
    });

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        try {
          const savedLast = sessionStorage.getItem('earthlens_last_request');
          if (savedLast) {
            const req = JSON.parse(savedLast);
            const changed =
              req &&
              (Math.abs(Number(req.latitude) - state.latitude) > 0.01 ||
                Math.abs(Number(req.longitude) - state.longitude) > 0.01 ||
                (req.variable && String(req.variable).toUpperCase() !== state.variable));
            if (changed) {
              state.latitude = Number(req.latitude);
              state.longitude = Number(req.longitude);
              state.locationName = req.locationName || req.location_name || state.locationName;
              if (req.variable) state.variable = String(req.variable).toUpperCase();
              syncTopBarControlsWithState();
              loadTimeMachineData();
              return;
            }
          }
        } catch (e) {
          // Ignorar errores de storage
        }
        syncTopBarControlsWithState();
      }
    });

    // Botones de icono que abren las 4 ventanitas flotantes
    document.querySelectorAll('.tm-icon-btn[data-window-target]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.dataset.windowTarget;
        if (targetId) togglePopupWindow(targetId);
      });
    });

    // Cerrar ventanitas
    document.querySelectorAll('.tm-window-close').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.dataset.closeWindow;
        if (targetId) togglePopupWindow(targetId);
      });
    });

    // Controles para achicar, expandir o restablecer el cuadrante de análisis
    if (btnShrinkBox) {
      btnShrinkBox.addEventListener('click', () => scaleZoneBoundingBox(0.68));
    }
    if (btnExpandBox) {
      btnExpandBox.addEventListener('click', () => scaleZoneBoundingBox(1.45));
    }
    if (btnResetBox) {
      btnResetBox.addEventListener('click', () => scaleZoneBoundingBox(1.0, true));
    }

    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && openWindowId) {
        togglePopupWindow(openWindowId);
      } else if (ev.target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(ev.target.tagName)) {
        return;
      } else if (ev.key === 'ArrowRight' && currentData?.timeline) {
        stopPlayback();
        const years = currentData.timeline.map((p) => p.year);
        const idx = years.indexOf(activeYear);
        if (idx < years.length - 1) setActiveYear(years[idx + 1]);
      } else if (ev.key === 'ArrowLeft' && currentData?.timeline) {
        stopPlayback();
        const years = currentData.timeline.map((p) => p.year);
        const idx = years.indexOf(activeYear);
        if (idx > 0) setActiveYear(years[idx - 1]);
      } else if (ev.key === ' ') {
        ev.preventDefault();
        togglePlayback();
      }
    });

    if (citySelect) {
      citySelect.addEventListener('change', () => {
        const opt = citySelect.selectedOptions[0];
        if (!opt) return;
        state.city_id = opt.value !== 'custom' ? opt.value : null;
        state.latitude = parseFloat(opt.dataset.lat);
        state.longitude = parseFloat(opt.dataset.lon);
        state.locationName = opt.textContent;
        syncTopBarControlsWithState();
        persistStateToStorageAndURL();
        loadTimeMachineData();
      });
    }

    if (varSelect) {
      varSelect.addEventListener('change', () => {
        state.variable = varSelect.value;
        syncTopBarControlsWithState();
        persistStateToStorageAndURL();
        loadTimeMachineData({ preserveZoom: true });
      });
    }

    if (btnLoad) {
      btnLoad.addEventListener('click', () => {
        if (startInput && endInput) {
          let s = parseInt(startInput.value, 10) || 2000;
          let e = parseInt(endInput.value, 10) || 2024;
          e = Math.max(1984, Math.min(2024, e));
          s = Math.max(1981, Math.min(e - 3, s));
          state.start_year = s;
          state.end_year = e;
          startInput.value = s;
          endInput.value = e;
        }
        syncTopBarControlsWithState();
        persistStateToStorageAndURL();
        loadTimeMachineData({ preserveZoom: true });
      });
    }

    if (slider) {
      slider.addEventListener('input', () => {
        stopPlayback();
        setActiveYear(Number(slider.value));
      });
    }

    if (splitSlider) {
      splitSlider.addEventListener('change', () => {if(!currentData)return;state.split_year=Number(splitSlider.value);loadTimeMachineData({preserveZoom:true});});
    }

    if (btnPlay) btnPlay.addEventListener('click', togglePlayback);

    if (btnPrev) {
      btnPrev.addEventListener('click', () => {
        stopPlayback();
        if (!currentData?.timeline) return;
        const years = currentData.timeline.map((p) => p.year);
        const idx = years.indexOf(activeYear);
        if (idx > 0) setActiveYear(years[idx - 1]);
      });
    }

    if (btnNext) {
      btnNext.addEventListener('click', () => {
        stopPlayback();
        if (!currentData?.timeline) return;
        const years = currentData.timeline.map((p) => p.year);
        const idx = years.indexOf(activeYear);
        if (idx < years.length - 1) setActiveYear(years[idx + 1]);
      });
    }

    document.querySelectorAll('.tm-speed-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tm-speed-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        playSpeedMs = Number(btn.dataset.speed) || 700;
        if (isPlaying) {
          stopPlayback();
          startPlayback();
        }
      });
    });

    if (mapModeSelect) {
      mapModeSelect.addEventListener('change', () => {
        mapMode = mapModeSelect.value;
        persistStateToStorageAndURL();
        applyMapModeView(true);
      });
    }

    if (btnZoomZone) {
      btnZoomZone.addEventListener('click', () => {
        mapMode = 'zone';
        if (mapModeSelect) mapModeSelect.value = 'zone';
        persistStateToStorageAndURL();
        applyMapModeView(true);
      });
    }

    if (btnZoomArg) {
      btnZoomArg.addEventListener('click', () => {
        mapMode = 'national';
        if (mapModeSelect) mapModeSelect.value = 'national';
        persistStateToStorageAndURL();
        applyMapModeView(true);
      });
    }

    if (btnExport) {
      btnExport.addEventListener('click', exportTimeMachineCSV);
    }
  }

  loadStateFromStorageOrURL();
  initLeafletMap();
  bindEvents();
  loadTimeMachineData();
});
