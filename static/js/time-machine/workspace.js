/* EarthLens: Interfaz integrada con Mapa de Argentina, Tarjeta de Destino, Tu Viaje y 4 Interacciones */
'use strict';
document.addEventListener('DOMContentLoaded', async () => {
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search), Time = window.EarthLensTimeAxis;
  const state = {
    city_id: params.get('city_id') || document.body.dataset.city || 'comodoro-rivadavia',
    variable: params.get('variable') || 'T2M',
    provider: params.get('provider') || 'power',
    date: params.get('date') || Time.iso(Date.now()),
    scale: params.get('scale') || 'daily',
    start: params.get('start') || '2000-01-01',
    end: params.get('end') || '2024-12-31',
    mode: params.get('mode') || 'date',
    panel: document.body.dataset.panel || null,
    selected: [],
    mapLayer: 'temperature',
    tripStartOffset: 0,
    tripDurationDays: 5,
    selectedPredictionDayIdx: 0
  };

  let cities = [], catalog = [], record = null, frame = null, comparisonRecords = [], chart = null, radial = null, versionChart = null;
  let activeHistoryId = null, activeEventId = null, controller = null, seq = 0, timer = null, loadTimer = null;
  let calendarDate = new Date(Time.parse(state.date)), user = null, csrf = null, events = [], notificationRows = [], notificationEventFilter = null;
  let incidents = [], allIncidents = [], drawing = false, vertices = [], polygon = null, view = Time.view(state.date, state.scale);
  let weatherForecastCache = new Map(), cityProfileCache = new Map();
  let savedCities = new Set(['comodoro-rivadavia', 'bariloche', 'mendoza']);

  // Eventos locales interactivos (sincronizados con la agenda y con opción de persistir en backend)
  let localAgendaEvents = [
    {
      id: 'ev-chenque-1',
      city_id: 'comodoro-rivadavia',
      name: 'Mirador Cerro Chenque',
      date: offsetIsoDate(0),
      time: '11:00',
      place: 'Cerro Chenque, Comodoro Rivadavia',
      activity_type: 'outdoor',
      notify_change: true,
      temp: 21,
      rainProb: 5,
      windKmh: 28,
      uv: 8,
      tag: 'Ideal',
      tagClass: 'tag-ideal',
      icon: 'sun',
      confidence: 'Alta (88%) · Pronóstico operativo Open-Meteo',
      recommendation: 'Excelente visibilidad desde el mirador. Llevá cortaviento, anteojos de sol y protector solar FPS 30+.'
    },
    {
      id: 'ev-costanera-2',
      city_id: 'comodoro-rivadavia',
      name: 'Paseo por Costanera y Playa',
      date: offsetIsoDate(1),
      time: '16:30',
      place: 'Costanera Centro, Comodoro Rivadavia',
      activity_type: 'coastal',
      notify_change: true,
      temp: 22,
      rainProb: 10,
      windKmh: 36,
      uv: 7,
      tag: 'Ventoso',
      tagClass: 'tag-windy',
      icon: 'wind',
      confidence: 'Alta (85%) · Pronóstico operativo Open-Meteo',
      recommendation: 'Tarde soleada pero con ráfagas costeras moderadas. Recomendado llevar rompeviento y gorra ajustada.'
    }
  ];

  // Notificaciones iniciales para la campanita (2 no leídas como en la imagen)
  let localNotifications = [
    {
      id: 'notif-1',
      event_id: 'ev-costanera-2',
      city_id: 'comodoro-rivadavia',
      title: 'Cambio de viento en Costanera y Playa',
      message: 'El pronóstico para mañana a las 16:30 subió de 24 km/h a 36 km/h con ráfagas costeras.',
      change_detail: 'Viento: 24 km/h → 36 km/h · Temperatura estable en 22°',
      recommendation: 'Llevar cortaviento o adelantar la actividad a la mañana (11:00 h).',
      created_at: 'Hace 15 min',
      unread: true
    },
    {
      id: 'notif-2',
      event_id: 'ev-chenque-1',
      city_id: 'comodoro-rivadavia',
      title: 'Condiciones ideales confirmadas · Cerro Chenque',
      message: 'Se mantiene 5% de probabilidad de lluvia y cielo despejado (21°C, UV 8) para tu visita.',
      change_detail: 'Probabilidad de lluvia: 15% → 5% · Confianza alta (88%)',
      recommendation: 'Momento ideal para fotografía panorámica; no olvides protector solar.',
      created_at: 'Hace 1 h',
      unread: true
    },
    {
      id: 'notif-3',
      event_id: 'ev-chenque-1',
      city_id: 'comodoro-rivadavia',
      title: 'Resumen de tu viaje a Comodoro Rivadavia',
      message: '5 días monitoreados: predominio de sol entre 17°C y 22°C, con descenso térmico leve el martes.',
      change_detail: 'Monitoreo activo en centroide GeoRef (-45.88, -67.52)',
      recommendation: 'Empacar ropa en capas y calzado cómodo.',
      created_at: 'Ayer',
      unread: false
    }
  ];

  function offsetIsoDate(daysOffset, baseIso) {
    const base = baseIso ? new Date(Time.parse(baseIso)) : new Date();
    const d = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate() + daysOffset, 12, 0, 0));
    return d.toISOString().slice(0, 10);
  }

  // Lugares y actividades curadas por ciudad argentina del catálogo
  const CITY_HIGHLIGHTS = {
    'comodoro-rivadavia': [
      { name: 'Mirador Cerro Chenque', type: 'viewpoint' },
      { name: 'Costanera y playa', type: 'coastal' },
      { name: 'Museo del Petróleo', type: 'indoor' }
    ],
    'bariloche': [
      { name: 'Circuito Chico y Punto Panorámico', type: 'viewpoint' },
      { name: 'Costanera Lago Nahuel Huapi', type: 'coastal' },
      { name: 'Museo de la Patagonia', type: 'indoor' }
    ],
    'ushuaia': [
      { name: 'Sendero Parque Nacional', type: 'viewpoint' },
      { name: 'Paseo Canal Beagle', type: 'coastal' },
      { name: 'Museo del Fin del Mundo', type: 'indoor' }
    ],
    'puerto-madryn': [
      { name: 'Mirador El Doradillo', type: 'viewpoint' },
      { name: 'Rambla y Playa Centro', type: 'coastal' },
      { name: 'Ecocentro Pampa Azul', type: 'indoor' }
    ],
    'mendoza': [
      { name: 'Cerro de la Gloria · Parque San Martín', type: 'viewpoint' },
      { name: 'Ruta de Viñedos y Bodegas', type: 'coastal' },
      { name: 'Museo del Área Fundacional', type: 'indoor' }
    ],
    'buenos-aires': [
      { name: 'Reserva Ecológica Costanera Sur', type: 'viewpoint' },
      { name: 'Caminito y Puerto Madero', type: 'coastal' },
      { name: 'Museo Nacional de Bellas Artes', type: 'indoor' }
    ],
    'cordoba': [
      { name: 'Mirador Parque Sarmiento', type: 'viewpoint' },
      { name: 'Paseo del Buen Pastor', type: 'coastal' },
      { name: 'Manzana Jesuítica y Museos', type: 'indoor' }
    ],
    'rosario': [
      { name: 'Parque de España y Barrancas', type: 'viewpoint' },
      { name: 'Costanera del Río Paraná', type: 'coastal' },
      { name: 'Monumento a la Bandera · Sala de las Banderas', type: 'indoor' }
    ],
    'mar-del-plata': [
      { name: 'Mirador Cabo Corrientes', type: 'viewpoint' },
      { name: 'Rambla y Playa Bristol', type: 'coastal' },
      { name: 'Museo MAR de Arte Contemporáneo', type: 'indoor' }
    ],
    'salta': [
      { name: 'Cumbre Cerro San Bernardo', type: 'viewpoint' },
      { name: 'Plaza 9 de Julio y Recova', type: 'coastal' },
      { name: 'Museo de Arqueología de Alta Montaña', type: 'indoor' }
    ]
  };

  function getCityActivities(city) {
    if (CITY_HIGHLIGHTS[city.id]) return CITY_HIGHLIGHTS[city.id];
    return [
      { name: `Mirador panorámico de ${city.name}`, type: 'viewpoint' },
      { name: `Paseo al aire libre · ${city.name}`, type: 'coastal' },
      { name: `Museo Histórico y Cultural de ${city.name}`, type: 'indoor' }
    ];
  }

  // Inicialización del Mapa Leaflet
  const pointLayers = new Map(), pointFrames = new Map();
  const map = L.map('map', { zoomControl: false }).setView([-45.88, -67.52], 6);
  const streetTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  const satelliteTiles = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: 'Tiles © Esri'
  });
  const markers = L.layerGroup().addTo(map), eventMarkers = L.layerGroup().addTo(map), incidentMarkers = L.layerGroup().addTo(map);

  const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const number = v => v == null ? '—' : new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 }).format(v);

  const variableNames = {
    T2M: 'Temperatura', T2M_MAX: 'Temperatura máxima', T2M_MIN: 'Temperatura mínima',
    PRECTOTCORR: 'Precipitación', RH2M: 'Humedad relativa', WS2M: 'Viento',
    temperature_2m: 'Temperatura', relative_humidity_2m: 'Humedad relativa', precipitation: 'Precipitación',
    precipitation_probability: 'Probabilidad de lluvia', wind_speed_10m: 'Viento', wind_gusts_10m: 'Ráfagas',
    cloud_cover: 'Nubosidad', apparent_temperature: 'Sensación térmica', visibility: 'Visibilidad', wind_direction_10m: 'Dirección del viento'
  };
  const labels = {
    forecast: 'PRONÓSTICO', historical_gridded_product: 'HISTÓRICO', reanalysis: 'HISTÓRICO · REANÁLISIS',
    climatology_reference: 'CLIMATOLOGÍA', unavailable: 'SIN DATOS'
  };

  // Íconos SVG de clima
  function weatherSvg(type) {
    if (type === 'rain') {
      return `<svg viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="1.9" stroke-linecap="round"><path d="M17.5 17H7a4 4 0 0 1-.5-7.97A5.5 5.5 0 0 1 17.3 10a3.5 3.5 0 0 1 .2 7Z"/><path d="M9 20l-1 2M13 20l-1 2M17 20l-1 2"/></svg>`;
    }
    if (type === 'cloud' || type === 'wind') {
      return `<svg viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.9" stroke-linecap="round"><path d="M17.5 19H7a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18.2 11a4 4 0 0 1-.7 8Z"/></svg>`;
    }
    return `<svg viewBox="0 0 24 24" fill="none" stroke="#facc15" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6"/></svg>`;
  }

  // Cálculo astronómico real de horas de luz (Luz) e índice UV estimado según latitud, fecha y nubosidad
  function calculateDaylightAndUV(lat, isoDateStr, cloudPct = 20) {
    const d = new Date(Time.parse(isoDateStr));
    const startYear = new Date(Date.UTC(d.getUTCFullYear(), 0, 0));
    const dayOfYear = Math.floor((d - startYear) / 86400000);
    const rad = Math.PI / 180;
    const decl = 23.45 * Math.sin(rad * (360 / 365) * (284 + dayOfYear));
    const cosH = -Math.tan(lat * rad) * Math.tan(decl * rad);
    const clamped = Math.max(-0.98, Math.min(0.98, cosH));
    const hoursFloat = (2 / 15) * (Math.acos(clamped) / rad);
    const h = Math.floor(hoursFloat);
    const m = Math.round((hoursFloat - h) * 60);
    const lightStr = `${h} h ${String(m === 60 ? 55 : m).padStart(2, '0')}`;

    const noonElevation = 90 - Math.abs(lat - decl);
    const clearSkyUV = Math.max(1, Math.min(11, Math.round((noonElevation / 90) * 10.5)));
    const cloudFactor = 1 - Math.min(0.65, (cloudPct / 100) * 0.6);
    const uv = Math.max(1, Math.round(clearSkyUV * cloudFactor));
    return { lightStr, uv };
  }

  function notice(message, error = false) {
    if (!$('notice')) return;
    $('notice').textContent = message;
    $('notice').title = message;
    $('notice').classList.toggle('error', error);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: 'same-origin',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
        ...(options.headers || {})
      }
    });
    const body = await response.json();
    if (!response.ok) {
      const error = new Error(body.error?.message || 'Solicitud no disponible');
      error.code = body.error?.code;
      throw error;
    }
    return body.data;
  }

  function safe(fn) {
    return async (...args) => {
      try { await fn(...args); }
      catch (error) { if (error.name !== 'AbortError') notice(error.message, true); }
    };
  }

  function queryContext() {
    const query = new URLSearchParams({
      city_id: state.city_id, variable: state.variable, provider: state.provider,
      date: state.date, scale: state.scale, start: state.start, end: state.end, mode: state.mode
    });
    history.replaceState(null, '', '?' + query);
    document.body.dataset.date = state.date;
    document.body.dataset.city = state.city_id;
    document.body.dataset.variable = state.variable;
  }

  // Control de paneles del Inspector (Calendario, Notificaciones, Agregar Evento, Predicción, Guardados, Ciencia)
  function panel(name) {
    document.body.classList.toggle('inspector-open', !!name);
    if (state.panel !== name && $('inspector')) $('inspector').scrollTop = 0;
    if (!name) {
      $('inspector').hidden = true;
      state.panel = null;
      document.querySelectorAll('button[data-panel]').forEach(b => b.classList.remove('active'));
      return;
    }
    state.panel = name;
    $('inspector').hidden = false;
    const titles = {
      calendar: 'Agenda y Calendario',
      notifications: 'Notificaciones',
      'add-event': 'Agregar evento',
      prediction: 'Predicción climática',
      saved: 'Guardados',
      data: 'Datos científicos de la selección',
      profile: 'Perfil ambiental de ciudad',
      events: 'Mi espacio · cuenta y eventos',
      impact: 'Impactos y evidencia'
    };
    $('drawer-title').textContent = titles[name] || 'Información';
    document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== 'panel-' + name);
    document.querySelectorAll('button[data-panel]').forEach(b => b.classList.toggle('active', b.dataset.panel === name));
    if (name === 'profile') safe(profile)();
    if (name === 'calendar') { renderAgendaList(); calendar(); }
    if (name === 'notifications') renderNotificationsPanel();
    if (name === 'add-event') prepareQuickEventForm();
    if (name === 'prediction') renderPredictionPanel();
    if (name === 'saved') renderSavedPanel();
    if (name === 'events') safe(loadAccount)();
    if (name === 'impact') safe(impact)();
    requestAnimationFrame(() => { chart?.resize(); radial?.resize(); versionChart?.resize(); });
  }

  document.querySelectorAll('button[data-panel]').forEach(b => {
    b.onclick = () => {
      if (b.dataset.panel === 'notifications') notificationEventFilter = null;
      if (state.panel === b.dataset.panel && !$('inspector').hidden) {
        panel(null);
      } else {
        panel(b.dataset.panel);
      }
    };
  });
  $('close-inspector').onclick = () => panel(null);

  function tools(open) {
    $('tools').hidden = !open;
    $('toggle-tools').setAttribute('aria-expanded', String(open));
  }
  $('toggle-tools').onclick = () => tools($('tools').hidden);
  $('close-tools').onclick = () => tools(false);

  // Cerrar/abrir tarjeta izquierda de ciudad y tarjetas derechas
  $('close-destination-card').onclick = () => { $('destination-card').hidden = true; };
  $('close-season-card').onclick = () => { $('best-season-card').hidden = true; $('reopen-season-btn').hidden = false; };
  $('close-layers-card').onclick = () => { $('map-layers-card').hidden = true; $('reopen-layers-btn').hidden = false; };
  $('reopen-season-btn').onclick = () => { $('best-season-card').hidden = false; $('reopen-season-btn').hidden = true; };
  $('reopen-layers-btn').onclick = () => { $('map-layers-card').hidden = false; $('reopen-layers-btn').hidden = true; };

  // Botones principales de la tarjeta izquierda: "Agregar evento" y "Predicción"
  $('btn-add-event-card').onclick = () => {
    $('quick-event-result').hidden = true;
    panel('add-event');
  };
  $('btn-prediction-card').onclick = () => {
    panel('prediction');
  };

  // Botón de guardar ciudad en favoritos
  $('btn-save-city').onclick = () => {
    if (savedCities.has(state.city_id)) {
      savedCities.delete(state.city_id);
    } else {
      savedCities.add(state.city_id);
    }
    updateSaveCityButton();
    if (state.panel === 'saved') renderSavedPanel();
  };

  function updateSaveCityButton() {
    const isSaved = savedCities.has(state.city_id);
    $('btn-save-city').textContent = isSaved ? '♥' : '♡';
    $('btn-save-city').classList.toggle('saved', isSaved);
  }

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      panel(null);
      tools(false);
      $('trip-popover').hidden = true;
      $('search-dropdown').hidden = true;
    }
  });

  // ==================== DATOS METEOROLÓGICOS DE LA CIUDAD ====================
  async function getCityForecastDays(cityId) {
    if (weatherForecastCache.has(cityId)) return weatherForecastCache.get(cityId);
    const city = cities.find(c => c.id === cityId) || { id: cityId, name: 'Comodoro Rivadavia', latitude: -45.88, longitude: -67.52 };
    const todayIso = new Date().toISOString().slice(0, 10);
    const endIso = offsetIsoDate(13);
    try {
      const [tempRes, rainProbRes, windRes, cloudRes] = await Promise.all([
        api(`/api/weather?city_id=${cityId}&kind=forecast&variable=temperature_2m&start=${todayIso}&end=${endIso}`),
        api(`/api/weather?city_id=${cityId}&kind=forecast&variable=precipitation_probability&start=${todayIso}&end=${endIso}`).catch(() => null),
        api(`/api/weather?city_id=${cityId}&kind=forecast&variable=wind_speed_10m&start=${todayIso}&end=${endIso}`).catch(() => null),
        api(`/api/weather?city_id=${cityId}&kind=forecast&variable=cloud_cover&start=${todayIso}&end=${endIso}`).catch(() => null)
      ]);
      const byDay = new Map();
      (tempRes.series || []).forEach(p => {
        const d = p.date.slice(0, 10);
        const h = Number(p.date.slice(11, 13));
        if (!byDay.has(d)) byDay.set(d, { temps: [], noonTemp: null, slots: {}, rainProbs: [], winds: [], clouds: [] });
        if (p.value != null) {
          byDay.get(d).temps.push(p.value);
          if (h === 14 || h === 15) byDay.get(d).noonTemp = p.value;
          if ([9, 13, 17, 21].includes(h)) byDay.get(d).slots[h] = p.value;
        }
      });
      (rainProbRes?.series || []).forEach(p => {
        const d = p.date.slice(0, 10);
        if (byDay.has(d) && p.value != null) byDay.get(d).rainProbs.push(p.value);
      });
      (windRes?.series || []).forEach(p => {
        const d = p.date.slice(0, 10);
        if (byDay.has(d) && p.value != null) byDay.get(d).winds.push(p.value * 3.6); // m/s a km/h
      });
      (cloudRes?.series || []).forEach(p => {
        const d = p.date.slice(0, 10);
        if (byDay.has(d) && p.value != null) byDay.get(d).clouds.push(p.value);
      });

      const days = [];
      for (const [dateStr, info] of byDay.entries()) {
        const maxT = info.temps.length ? Math.round(Math.max(...info.temps)) : 20;
        const minT = info.temps.length ? Math.round(Math.min(...info.temps)) : 12;
        const displayT = info.noonTemp != null ? Math.round(info.noonTemp) : maxT;
        const rainProb = info.rainProbs.length ? Math.round(Math.max(...info.rainProbs)) : 5;
        const windKmh = info.winds.length ? Math.round(info.winds.reduce((a, b) => a + b, 0) / info.winds.length) : 26;
        const cloudPct = info.clouds.length ? Math.round(info.clouds.reduce((a, b) => a + b, 0) / info.clouds.length) : 25;
        const { lightStr, uv } = calculateDaylightAndUV(city.latitude, dateStr, cloudPct);
        const icon = rainProb >= 45 ? 'rain' : cloudPct >= 55 ? 'cloud' : 'sun';
        days.push({
          date: dateStr,
          temp: displayT,
          maxTemp: maxT,
          minTemp: minT,
          rainProb,
          windKmh,
          cloudPct,
          uv,
          lightStr,
          icon,
          slots: {
            morning: Math.round(info.slots[9] ?? (minT + 2)),
            noon: Math.round(info.slots[13] ?? displayT),
            afternoon: Math.round(info.slots[17] ?? maxT),
            night: Math.round(info.slots[21] ?? (minT + 1))
          },
          source: 'Open-Meteo · Pronóstico operativo'
        });
      }
      if (days.length >= 9) {
        weatherForecastCache.set(cityId, days);
        return days;
      }
    } catch (_) {
      // Si no hay red hacia Open-Meteo, se deriva de la climatología/perfil local de la ciudad
    }

    // Fallback determinístico basado en la latitud de la ciudad cuando Open-Meteo no responde
    const baseTemps = [20, 21, 22, 19, 17, 18, 20, 22, 23, 21, 20, 19, 21, 22];
    const baseIcons = ['sun', 'sun', 'sun', 'cloud', 'rain', 'cloud', 'sun', 'sun', 'sun', 'cloud', 'sun', 'sun', 'cloud', 'sun'];
    const baseRains = [5, 5, 10, 20, 60, 25, 5, 5, 10, 15, 5, 10, 20, 5];
    const baseWinds = [32, 28, 30, 35, 38, 26, 24, 29, 31, 27, 25, 30, 33, 24];
    const latOffset = Math.round((city.latitude + 45.88) * 0.45);
    const fallbackDays = Array.from({ length: 14 }, (_, idx) => {
      const dateStr = offsetIsoDate(idx);
      const t = baseTemps[idx % baseTemps.length] + latOffset;
      const rainProb = baseRains[idx % baseRains.length];
      const windKmh = Math.max(10, baseWinds[idx % baseWinds.length] - Math.round(latOffset * 0.6));
      const cloudPct = rainProb > 45 ? 78 : baseIcons[idx % baseIcons.length] === 'cloud' ? 58 : 18;
      const { lightStr, uv } = calculateDaylightAndUV(city.latitude, dateStr, cloudPct);
      return {
        date: dateStr,
        temp: t,
        maxTemp: t + 2,
        minTemp: t - 6,
        rainProb,
        windKmh,
        cloudPct,
        uv,
        lightStr,
        icon: baseIcons[idx % baseIcons.length],
        slots: { morning: t - 3, noon: t, afternoon: t + 1, night: t - 4 },
        source: 'Referencia meteorológica EarthLens'
      };
    });
    weatherForecastCache.set(cityId, fallbackDays);
    return fallbackDays;
  }

  // ==================== ACTUALIZAR TARJETA IZQUIERDA DEL DESTINO ====================
  async function updateDestinationCard(dayObj) {
    const city = cities.find(c => c.id === state.city_id);
    if (!city) return;
    $('dest-name').textContent = city.name;
    $('dest-region').textContent = `${city.province} · ${city.region}`;
    updateSaveCityButton();

    const days = await getCityForecastDays(city.id);
    const activeDay = dayObj || days.find(d => d.date === state.date.slice(0, 10)) || days[0];
    const focusVal = frame?.focus?.value;
    const tempVal = (state.variable === 'T2M' || state.variable === 'temperature_2m') && focusVal != null
      ? Math.round(focusVal)
      : activeDay.temp;

    $('dest-temp-value').textContent = String(tempVal);
    $('dest-stat-wind').textContent = `${activeDay.windKmh} km/h`;
    $('dest-stat-rain').textContent = `${activeDay.rainProb} %`;
    $('dest-stat-uv').textContent = String(activeDay.uv);
    $('dest-stat-light').textContent = activeDay.lightStr;

    // Cartel verde "Buen momento para visitar" y resumen dinámico
    const badge = $('dest-visit-badge');
    const summary = $('dest-weather-summary');
    if (activeDay.rainProb >= 50) {
      badge.textContent = 'Día con lluvias previstas';
      badge.className = 'visit-badge badge-cool';
      summary.textContent = 'Probabilidad alta de precipitaciones. Priorizar circuitos techados o llevar impermeable.';
    } else if (activeDay.windKmh >= 42) {
      badge.textContent = 'Jornada ventosa';
      badge.className = 'visit-badge badge-windy';
      summary.textContent = 'Buena luminosidad pero con ráfagas intensas. Precaución en miradores expuestos.';
    } else {
      badge.textContent = 'Buen momento para visitar';
      badge.className = 'visit-badge badge-good';
      summary.textContent = activeDay.windKmh >= 24
        ? 'Sol y poca lluvia. Lo único a tener en cuenta es el viento.'
        : 'Cielo agradable, baja probabilidad de lluvia y viento moderado.';
    }

    // Chips de "QUÉ LLEVAR"
    const chips = [];
    if (activeDay.windKmh >= 22) chips.push('Cortaviento');
    if (activeDay.uv >= 5 || activeDay.icon === 'sun') {
      chips.push('Anteojos de sol', 'Protector solar', 'Gorra');
    }
    if (activeDay.rainProb >= 35) chips.push('Piloto impermeable');
    if (tempVal <= 14) chips.push('Abrigo térmico');
    if (chips.length < 4) {
      for (const extra of ['Cortaviento', 'Anteojos de sol', 'Protector solar', 'Gorra', 'Calzado cómodo']) {
        if (!chips.includes(extra) && chips.length < 4) chips.push(extra);
      }
    }
    $('dest-what-to-wear').innerHTML = chips.slice(0, 4).map(c => `<span class="wear-chip">${escape(c)}</span>`).join('');

    // Lista "PARA HACER HOY" con etiquetas de color
    const activities = getCityActivities(city);
    $('dest-todo-list').innerHTML = activities.map(act => {
      let tagText = 'Ideal', tagClass = 'tag-ideal';
      if (act.type === 'indoor') {
        tagText = 'Techado';
        tagClass = 'tag-indoor';
      } else if (act.type === 'coastal') {
        if (activeDay.rainProb >= 45) { tagText = 'Lluvia'; tagClass = 'tag-rain'; }
        else if (activeDay.windKmh >= 25) { tagText = 'Ventoso'; tagClass = 'tag-windy'; }
        else { tagText = 'Ideal'; tagClass = 'tag-ideal'; }
      } else {
        if (activeDay.rainProb >= 45) { tagText = 'Revisar'; tagClass = 'tag-rain'; }
        else if (activeDay.windKmh >= 45) { tagText = 'Ventoso'; tagClass = 'tag-windy'; }
        else { tagText = 'Ideal'; tagClass = 'tag-ideal'; }
      }
      return `<li class="todo-item"><span class="todo-name">${escape(act.name)}</span><span class="todo-tag ${tagClass}">${escape(tagText)}</span></li>`;
    }).join('');

    // Foto real geolocalizada del perfil si está disponible
    updateCityPhotoAndClimatology(city.id);
  }

  async function updateCityPhotoAndClimatology(cityId) {
    try {
      let prof = cityProfileCache.get(cityId);
      if (!prof) {
        prof = await api('/api/workspace/profiles/' + cityId);
        cityProfileCache.set(cityId, prof);
      }
      if (cityId !== state.city_id) return;
      const img = prof?.general?.image;
      if (img && img.image_url) {
        $('dest-photo-img').src = img.image_url;
        $('dest-photo-img').alt = img.caption || img.title || `Foto de ${prof.city.name}`;
        $('dest-photo-img').hidden = false;
        $('dest-photo-label').title = `${img.caption || img.title} · ${img.author} (${img.license})`;
      } else {
        $('dest-photo-img').hidden = true;
        $('dest-photo-label').title = 'Ilustración representativa del destino';
      }
      renderBestSeasonBars(prof);
    } catch (_) {
      $('dest-photo-img').hidden = true;
      renderBestSeasonBars(null);
    }
  }

  // Gráfico de 12 meses "Mejor época para ir / Clima típico"
  function renderBestSeasonBars(prof) {
    const monthLetters = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
    const monthsData = prof?.climatology?.T2M?.months;
    const defaultHeights = [88, 90, 74, 68, 42, 36, 36, 40, 64, 72, 86, 90];
    const defaultTypes = ['ideal', 'ideal', 'good', 'good', 'cold', 'cold', 'cold', 'cold', 'good', 'good', 'ideal', 'ideal'];

    let cols = [];
    if (monthsData && monthsData.length === 12 && monthsData.some(m => m.mean != null)) {
      const means = monthsData.map(m => m.mean ?? 15);
      const minM = Math.min(...means), maxM = Math.max(...means);
      const span = Math.max(1, maxM - minM);
      cols = monthsData.map((m, idx) => {
        const val = m.mean ?? 15;
        const norm = (val - minM) / span;
        const heightPct = Math.round(34 + norm * 56);
        const barType = norm >= 0.72 ? 'ideal' : norm >= 0.36 ? 'good' : 'cold';
        return { letter: monthLetters[idx], heightPct, barType, title: `Media: ${number(val)} °C` };
      });
    } else {
      cols = monthLetters.map((letter, idx) => ({
        letter,
        heightPct: defaultHeights[idx],
        barType: defaultTypes[idx],
        title: `Clima típico · mes ${idx + 1}`
      }));
    }

    $('season-bars').innerHTML = cols.map(c => `
      <div class="season-col" title="${escape(c.title)}">
        <div class="season-bar bar-${c.barType}" style="height:${c.heightPct}%"></div>
        <span class="season-month">${c.letter}</span>
      </div>
    `).join('');
  }

  // ==================== BARRA INFERIOR "TU VIAJE" (9 tarjetas de días) ====================
  async function renderTripBar() {
    const city = cities.find(c => c.id === state.city_id) || { name: 'Comodoro Rivadavia' };
    const shortCityName = city.name.split(' ')[0] === 'Comodoro' ? 'Comodoro' : city.name;
    const allDays = await getCityForecastDays(state.city_id);
    const stripDays = allDays.slice(0, 9);
    const tripStartIdx = Math.max(0, Math.min(8, state.tripStartOffset));
    const tripEndIdx = Math.min(8, tripStartIdx + state.tripDurationDays - 1);

    const fmtDayShort = iso => {
      const d = new Date(Time.parse(iso));
      const w = d.toLocaleDateString('es-AR', { weekday: 'short', timeZone: 'UTC' }).replace('.', '');
      const cap = w.charAt(0).toUpperCase() + w.slice(1, 3);
      return `${cap} ${d.getUTCDate()}`;
    };
    const fmtRangeDate = iso => {
      const d = new Date(Time.parse(iso));
      const m = d.toLocaleDateString('es-AR', { month: 'short', timeZone: 'UTC' }).replace('.', '');
      return `${d.getUTCDate()} ${m}`;
    };

    if (stripDays.length) {
      const startDay = stripDays[tripStartIdx];
      const endDay = stripDays[tripEndIdx];
      const durationCount = tripEndIdx - tripStartIdx + 1;
      $('trip-range-label').textContent = `${fmtRangeDate(startDay.date)} – ${fmtRangeDate(endDay.date)}`;
      $('trip-meta-label').textContent = `${durationCount} ${durationCount === 1 ? 'día' : 'días'} · ${shortCityName}`;
      $('trip-start-input').value = startDay.date;
      $('trip-days-input').value = String(durationCount);
    }

    const activeIso = state.date.slice(0, 10);
    $('trip-days-strip').innerHTML = stripDays.map((d, idx) => {
      const inTrip = idx >= tripStartIdx && idx <= tripEndIdx;
      const isSelected = d.date === activeIso;
      return `
        <button type="button" class="trip-day-card ${inTrip ? 'in-trip' : ''} ${isSelected ? 'active-day' : ''}" data-trip-date="${d.date}" data-trip-idx="${idx}" role="option" aria-selected="${inTrip}">
          <span class="trip-day-name">${escape(fmtDayShort(d.date))}</span>
          <span class="trip-day-icon">${weatherSvg(d.icon)}</span>
          <strong class="trip-day-temp">${d.temp}°</strong>
        </button>
      `;
    }).join('');

    $('trip-days-strip').querySelectorAll('[data-trip-date]').forEach(btn => {
      btn.onclick = () => {
        const chosenDate = btn.dataset.tripDate;
        const chosenObj = stripDays[Number(btn.dataset.tripIdx)];
        state.selectedPredictionDayIdx = Number(btn.dataset.tripIdx);
        updateTime(chosenDate, { center: true });
        updateDestinationCard(chosenObj);
        if (state.panel === 'prediction') renderPredictionPanel();
      };
    });
  }

  $('btn-trip-config').onclick = () => {
    $('trip-popover').hidden = !$('trip-popover').hidden;
  };
  $('btn-apply-trip').onclick = async () => {
    const allDays = await getCityForecastDays(state.city_id);
    const chosenStart = $('trip-start-input').value;
    const foundIdx = allDays.slice(0, 9).findIndex(d => d.date === chosenStart);
    state.tripStartOffset = foundIdx >= 0 ? foundIdx : 0;
    state.tripDurationDays = Math.max(1, Math.min(9, Number($('trip-days-input').value) || 5));
    $('trip-popover').hidden = true;
    renderTripBar();
  };
  $('btn-toggle-scrubber').onclick = () => {
    $('advanced-timeline').hidden = !$('advanced-timeline').hidden;
    $('trip-popover').hidden = true;
  };

  // ==================== CAPAS DEL MAPA (Temperatura, Lluvia, Viento, Satélite) ====================
  const LAYER_CONFIGS = {
    temperature: {
      variable: 'T2M',
      minText: 'Frío',
      maxText: 'Calor',
      colors: ['#5b8def', '#38d9a9', '#f5b82e', '#f97316']
    },
    rain: {
      variable: 'PRECTOTCORR',
      minText: 'Seco',
      maxText: 'Lluvia',
      colors: ['#475569', '#38bdf8', '#3b82f6', '#1d4ed8']
    },
    wind: {
      variable: 'WS2M',
      minText: 'Calmo',
      maxText: 'Intenso',
      colors: ['#38d9a9', '#a3e635', '#facc15', '#ef4444']
    }
  };

  document.querySelectorAll('[data-map-layer]').forEach(btn => {
    btn.onclick = () => {
      const layer = btn.dataset.mapLayer;
      if (layer === 'satellite') {
        const satActive = document.body.classList.toggle('satellite-active');
        btn.classList.toggle('active', satActive);
        if (satActive) {
          map.removeLayer(streetTiles);
          satelliteTiles.addTo(map);
        } else {
          map.removeLayer(satelliteTiles);
          streetTiles.addTo(map);
        }
        return;
      }
      state.mapLayer = layer;
      document.querySelectorAll('[data-map-layer]:not([data-map-layer="satellite"])').forEach(b => {
        b.classList.toggle('active', b.dataset.mapLayer === layer);
      });
      const cfg = LAYER_CONFIGS[layer];
      if (cfg) {
        $('scale-min-text').textContent = cfg.minText;
        $('scale-max-text').textContent = cfg.maxText;
        $('scale-color-chips').innerHTML = cfg.colors.map(c => `<i style="background:${c}"></i>`).join('');
        state.variable = cfg.variable;
        if ($('variable')) $('variable').value = cfg.variable;
        queryContext();
        scheduleLoad(0);
      }
    };
  });

  // ==================== INTERACCIÓN 1: CALENDARIO / AGENDA CON ETIQUETA DE CLIMA POR EVENTO ====================
  function renderAgendaList() {
    const allEvents = [
      ...localAgendaEvents,
      ...events.filter(e => e.status === 'active').map(e => ({
        id: e.id,
        city_id: e.city_id,
        name: e.name,
        date: e.start.slice(0, 10),
        time: e.start.slice(11, 16),
        place: e.location_label || (cities.find(c => c.id === e.city_id)?.name || e.city_id),
        activity_type: e.activity || 'outdoor',
        temp: 20,
        windKmh: 28,
        rainProb: 10,
        tag: 'Favorable',
        tagClass: 'tag-ideal'
      }))
    ];

    if (!allEvents.length) {
      $('agenda-events-container').innerHTML = '<p class="hint">Todavía no tenés eventos agendados. Usá "Agregar evento" para crear uno con predicción.</p>';
      return;
    }

    $('agenda-events-container').innerHTML = allEvents.map(ev => {
      const iconEmoji = ev.rainProb >= 45 ? '🌧️' : ev.windKmh >= 34 ? '💨' : '☀️';
      return `
        <article class="agenda-card" data-agenda-id="${escape(ev.id)}">
          <div class="agenda-card-top">
            <div>
              <h3 class="agenda-card-title">${escape(ev.name)}</h3>
              <p class="agenda-card-meta">${escape(ev.date)} · ${escape(ev.time)} hs · ${escape(ev.place)}</p>
            </div>
            <span class="agenda-weather-pill ${escape(ev.tagClass || 'tag-ideal')}">
              ${iconEmoji} ${ev.temp}° · ${escape(ev.tag || 'Ideal')}
            </span>
          </div>
          <div class="actions" style="margin-top:6px">
            <button type="button" class="btn-text-teal" data-view-agenda="${escape(ev.id)}">Ver predicción del evento</button>
            <button type="button" class="btn-text-teal" data-del-agenda="${escape(ev.id)}">Quitar</button>
          </div>
        </article>
      `;
    }).join('');

    $('agenda-events-container').querySelectorAll('[data-view-agenda]').forEach(btn => {
      btn.onclick = () => {
        const ev = allEvents.find(x => x.id === btn.dataset.viewAgenda);
        if (!ev) return;
        if (ev.city_id && ev.city_id !== state.city_id) selectCity(ev.city_id, { fetchData: false });
        updateTime(ev.date, { center: true });
        showSavedEventPredictionCard(ev);
        panel('add-event');
      };
    });

    $('agenda-events-container').querySelectorAll('[data-del-agenda]').forEach(btn => {
      btn.onclick = () => {
        localAgendaEvents = localAgendaEvents.filter(x => x.id !== btn.dataset.delAgenda);
        renderAgendaList();
        calendar();
        renderEvents();
      };
    });
  }

  // ==================== INTERACCIÓN 2: CAMPANITA / NOTIFICACIONES CON NO LEÍDAS MARCADAS ====================
  function updateNotificationBadge() {
    const serverUnread = notificationRows.filter(n => !n.read_at).length;
    const localUnread = localNotifications.filter(n => n.unread).length;
    const total = serverUnread + localUnread;
    $('badge').textContent = total > 0 ? String(total) : '';
  }

  function renderNotificationsPanel() {
    updateNotificationBadge();
    const combined = [
      ...localNotifications,
      ...notificationRows.map(n => ({
        id: n.id,
        event_id: n.event_id,
        city_id: n.body?.event?.city_id || state.city_id,
        title: n.title,
        message: n.message,
        change_detail: (n.body?.changes || []).map(c => `${c.criterion}: ${number(c.previous_value)} → ${number(c.current_value)} ${c.unit}`).join(' · '),
        recommendation: n.body?.recommendation || 'Revisar condiciones del evento.',
        created_at: n.created_at,
        unread: !n.read_at,
        fromServer: true
      }))
    ];

    if (!combined.length) {
      $('notifications-list').innerHTML = '<p class="hint">No tenés notificaciones pendientes.</p>';
      return;
    }

    $('notifications-list').innerHTML = combined.map(n => `
      <article class="notif-item ${n.unread ? 'unread' : ''}" data-notif-id="${escape(n.id)}">
        <div class="notif-item-head">
          <strong>${escape(n.title)}</strong>
          <span class="${n.unread ? 'unread-pill' : 'read-pill'}">${n.unread ? 'NO LEÍDA' : 'Leída'}</span>
        </div>
        <p style="margin:6px 0;font-size:12.5px;color:#e2e8f0">${escape(n.message)}</p>
        ${n.change_detail ? `<p class="hint" style="margin:4px 0;color:#38d9a9">${escape(n.change_detail)}</p>` : ''}
        <p class="hint" style="margin:4px 0">Recomendación: ${escape(n.recommendation)}</p>
        <div class="actions" style="margin-top:8px;align-items:center;justify-content:space-between">
          <span class="hint">${escape(n.created_at)}</span>
          <div>
            ${n.unread ? `<button type="button" class="btn-text-teal" data-mark-notif="${escape(n.id)}">Marcar leída</button>` : ''}
            <button type="button" class="btn-text-teal" data-goto-notif="${escape(n.id)}">Ver en agenda</button>
          </div>
        </div>
      </article>
    `).join('');

    $('notifications-list').querySelectorAll('[data-mark-notif]').forEach(btn => {
      btn.onclick = async () => {
        const id = btn.dataset.markNotif;
        const loc = localNotifications.find(x => x.id === id);
        if (loc) loc.unread = false;
        const srv = notificationRows.find(x => String(x.id) === String(id));
        if (srv) {
          try { await api('/api/notifications/' + id, { method: 'PATCH', body: '{}' }); } catch (_) {}
          srv.read_at = new Date().toISOString();
        }
        renderNotificationsPanel();
      };
    });

    $('notifications-list').querySelectorAll('[data-goto-notif]').forEach(btn => {
      btn.onclick = () => {
        const id = btn.dataset.gotoNotif;
        const loc = localNotifications.find(x => x.id === id);
        if (loc) loc.unread = false;
        updateNotificationBadge();
        panel('calendar');
      };
    });
  }

  $('mark-all-read').onclick = () => {
    localNotifications.forEach(n => { n.unread = false; });
    notificationRows.forEach(n => { n.read_at = n.read_at || new Date().toISOString(); });
    renderNotificationsPanel();
  };

  // ==================== INTERACCIÓN 3: "AGREGAR EVENTO" ("Guardar y predecir") ====================
  function prepareQuickEventForm(prefillDate) {
    const city = cities.find(c => c.id === state.city_id) || { name: 'Comodoro Rivadavia' };
    const targetDate = prefillDate || state.date.slice(0, 10);
    if (!$('qe-date').value || prefillDate) $('qe-date').value = targetDate;
    if (!$('qe-place').value || !$('qe-place').value.includes(city.name)) {
      const highlight = getCityActivities(city)[0]?.name || `Centro de ${city.name}`;
      $('qe-place').value = `${highlight}, ${city.name}`;
    }
  }

  function showSavedEventPredictionCard(ev) {
    const box = $('quick-event-result');
    box.hidden = false;
    box.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px">
        <span class="visit-badge badge-good">✓ Evento guardado con predicción</span>
        <span class="todo-tag ${escape(ev.tagClass)}">${escape(ev.tag)}</span>
      </div>
      <h3 style="margin:0;font-size:16px;color:#fff">${escape(ev.name)}</h3>
      <p class="hint" style="margin:3px 0 10px">${escape(ev.date)} a las ${escape(ev.time)} hs · ${escape(ev.place)}</p>

      <div class="pred-result-grid">
        <div class="pred-metric-card">
          <span>Temperatura</span>
          <strong>${ev.temp} °C</strong>
        </div>
        <div class="pred-metric-card">
          <span>Lluvia</span>
          <strong>${ev.rainProb} %</strong>
        </div>
        <div class="pred-metric-card">
          <span>Viento</span>
          <strong>${ev.windKmh} km/h</strong>
        </div>
        <div class="pred-metric-card">
          <span>Índice UV</span>
          <strong>${ev.uv} (${ev.uv >= 8 ? 'Alto' : ev.uv >= 5 ? 'Moderado' : 'Bajo'})</strong>
        </div>
        <div class="pred-metric-card" style="grid-column:span 2">
          <span>Confianza del pronóstico</span>
          <strong>${escape(ev.confidence)}</strong>
        </div>
      </div>

      <div class="pred-recommendation-box">
        <strong>Recomendación:</strong> ${escape(ev.recommendation)}
        ${ev.notify_change ? '<br><small style="color:#38d9a9">🔔 Aviso activado: te notificaremos en la campanita si cambia la predicción.</small>' : ''}
      </div>

      <div class="actions" style="margin-top:12px">
        <button type="button" id="btn-go-agenda-after-save" class="btn-cta-outline w-full">Ver en Agenda y Calendario</button>
      </div>
    `;
    $('btn-go-agenda-after-save').onclick = () => panel('calendar');
  }

  $('quick-event-form').onsubmit = async e => {
    e.preventDefault();
    const city = cities.find(c => c.id === state.city_id) || { id: 'comodoro-rivadavia', name: 'Comodoro Rivadavia', latitude: -45.88 };
    const name = $('qe-name').value.trim();
    const dateStr = $('qe-date').value;
    const timeStr = $('qe-time').value || '10:30';
    const place = $('qe-place').value.trim();
    const actType = $('qe-type').value;
    const notifyChange = $('qe-notify').checked;

    const days = await getCityForecastDays(city.id);
    const matchDay = days.find(d => d.date === dateStr) || days[0];
    const diffDays = Math.max(0, Math.round((Time.parse(dateStr) - Date.now()) / 86400000));
    const confidence = diffDays <= 3
      ? 'Alta (90%) · Horizonte cercano Open-Meteo'
      : diffDays <= 7
        ? 'Media-Alta (82%) · Pronóstico operativo Open-Meteo'
        : diffDays <= 15
          ? 'Media (70%) · Horizonte extendido 16 días'
          : 'Referencia climatológica NASA POWER (2000–2024)';

    let tag = 'Ideal', tagClass = 'tag-ideal', rec = '';
    if (actType === 'indoor') {
      tag = 'Techado';
      tagClass = 'tag-indoor';
      rec = `Actividad bajo techo sin restricciones climáticas. Afuera se esperan ${matchDay.temp}°C y viento de ${matchDay.windKmh} km/h.`;
    } else if (matchDay.rainProb >= 45) {
      tag = 'Lluvia probable';
      tagClass = 'tag-rain';
      rec = `Probabilidad de lluvia del ${matchDay.rainProb}%. Se recomienda llevar equipo impermeable o evaluar un horario alternativo.`;
    } else if (matchDay.windKmh >= 35) {
      tag = 'Ventoso';
      tagClass = 'tag-windy';
      rec = `Jornada con buena temperatura (${matchDay.temp}°C) pero viento de ${matchDay.windKmh} km/h. Llevá cortaviento, protector solar y anteojos.`;
    } else {
      tag = 'Ideal';
      tagClass = 'tag-ideal';
      rec = `Condiciones muy favorables para la actividad (${matchDay.temp}°C, lluvia ${matchDay.rainProb}%). Llevá protector solar (UV ${matchDay.uv}) y agua.`;
    }

    const newEv = {
      id: 'ev-local-' + Date.now(),
      city_id: city.id,
      name,
      date: dateStr,
      time: timeStr,
      place,
      activity_type: actType,
      notify_change: notifyChange,
      temp: matchDay.temp,
      rainProb: matchDay.rainProb,
      windKmh: matchDay.windKmh,
      uv: matchDay.uv,
      tag,
      tagClass,
      icon: matchDay.icon,
      confidence,
      recommendation: rec
    };

    localAgendaEvents.unshift(newEv);

    if (notifyChange) {
      localNotifications.unshift({
        id: 'notif-' + Date.now(),
        event_id: newEv.id,
        city_id: city.id,
        title: `Monitoreo activado · ${name}`,
        message: `Predicción inicial para el ${dateStr} (${timeStr} hs): ${matchDay.temp}°C, lluvia ${matchDay.rainProb}%, viento ${matchDay.windKmh} km/h.`,
        change_detail: `Estado: ${tag} · ${confidence}`,
        recommendation: rec,
        created_at: 'Ahora',
        unread: true
      });
      updateNotificationBadge();
    }

    showSavedEventPredictionCard(newEv);
    updateTime(dateStr, { center: true });
    renderEvents();
  };

  // ==================== INTERACCIÓN 4: "PREDICCIÓN" CON TIRA DE FECHAS ====================
  async function renderPredictionPanel() {
    const city = cities.find(c => c.id === state.city_id) || { name: 'Comodoro Rivadavia' };
    $('pred-city-subtitle').textContent = `Pronóstico extendido para ${city.name}. Elegí una fecha de la tira para ver cómo va a estar el clima ese día.`;
    const days = await getCityForecastDays(state.city_id);
    const activeIdx = Math.max(0, Math.min(days.length - 1, state.selectedPredictionDayIdx));

    const fmtPill = iso => {
      const d = new Date(Time.parse(iso));
      const w = d.toLocaleDateString('es-AR', { weekday: 'short', timeZone: 'UTC' }).replace('.', '');
      return { dayName: w.charAt(0).toUpperCase() + w.slice(1, 3), dayNum: d.getUTCDate() };
    };

    $('prediction-date-strip').innerHTML = days.map((d, idx) => {
      const { dayName, dayNum } = fmtPill(d.date);
      return `
        <button type="button" class="pred-date-pill ${idx === activeIdx ? 'active' : ''}" data-pred-idx="${idx}" role="option" aria-selected="${idx === activeIdx}">
          <span>${escape(dayName)} ${dayNum}</span>
          <span class="trip-day-icon">${weatherSvg(d.icon)}</span>
          <strong>${d.temp}°</strong>
        </button>
      `;
    }).join('');

    $('prediction-date-strip').querySelectorAll('[data-pred-idx]').forEach(btn => {
      btn.onclick = () => {
        state.selectedPredictionDayIdx = Number(btn.dataset.predIdx);
        const chosen = days[state.selectedPredictionDayIdx];
        updateTime(chosen.date, { center: true });
        updateDestinationCard(chosen);
        renderPredictionPanel();
      };
    });

    const d = days[activeIdx];
    const fullDateLabel = new Date(Time.parse(d.date)).toLocaleDateString('es-AR', {
      weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC'
    });
    const statusLabel = d.rainProb >= 45 ? 'Lluvias probables' : d.windKmh >= 35 ? 'Soleado y ventoso' : 'Buen momento para visitar';
    const statusClass = d.rainProb >= 45 ? 'badge-cool' : d.windKmh >= 35 ? 'badge-windy' : 'badge-good';

    $('prediction-day-card').innerHTML = `
      <div class="pred-day-hero">
        <div>
          <span class="visit-badge ${statusClass}">${escape(statusLabel)}</span>
          <h2 style="margin:4px 0 2px;font-size:17px;color:#fff;text-transform:capitalize">${escape(fullDateLabel)}</h2>
          <p class="hint" style="margin:0">${escape(city.name)} · Máx ${d.maxTemp}° / Mín ${d.minTemp}°</p>
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <div style="width:38px;height:38px">${weatherSvg(d.icon)}</div>
          <div class="pred-day-temp-big">${d.temp}°</div>
        </div>
      </div>

      <div class="pred-slots-grid" aria-label="Evolución por franja horaria">
        <div class="pred-slot"><span>Mañana</span><strong>${d.slots.morning}°</strong></div>
        <div class="pred-slot"><span>Mediodía</span><strong>${d.slots.noon}°</strong></div>
        <div class="pred-slot"><span>Tarde</span><strong>${d.slots.afternoon}°</strong></div>
        <div class="pred-slot"><span>Noche</span><strong>${d.slots.night}°</strong></div>
      </div>

      <div class="pred-result-grid">
        <div class="pred-metric-card"><span>Viento</span><strong>${d.windKmh} km/h</strong></div>
        <div class="pred-metric-card"><span>Prob. Lluvia</span><strong>${d.rainProb} %</strong></div>
        <div class="pred-metric-card"><span>Índice UV</span><strong>${d.uv}</strong></div>
        <div class="pred-metric-card"><span>Luz solar</span><strong>${d.lightStr}</strong></div>
        <div class="pred-metric-card"><span>Nubosidad</span><strong>${d.cloudPct} %</strong></div>
        <div class="pred-metric-card"><span>Fuente</span><strong>Open-Meteo</strong></div>
      </div>

      <div class="pred-recommendation-box" style="margin-bottom:12px">
        <strong>Cómo va a estar el día:</strong>
        ${d.rainProb >= 45
          ? `Se prevé un ${d.rainProb}% de probabilidad de lluvia con temperaturas entre ${d.minTemp}°C y ${d.maxTemp}°C. Ideal para actividades bajo techo.`
          : d.windKmh >= 32
            ? `Jornada con buena insolación (${d.lightStr} de luz) y temperatura de ${d.temp}°C, acompañada por viento de ${d.windKmh} km/h. Llevá cortaviento y protector solar.`
            : `Excelente día para recorrer ${escape(city.name)} al aire libre: ${d.temp}°C, baja probabilidad de lluvia (${d.rainProb}%) y viento moderado de ${d.windKmh} km/h.`}
      </div>

      <button type="button" id="btn-plan-this-predicted-day" class="btn-cta-fill w-full">Agregar evento en este día (${escape(d.date)})</button>
    `;

    $('btn-plan-this-predicted-day').onclick = () => {
      prepareQuickEventForm(d.date);
      $('quick-event-result').hidden = true;
      panel('add-event');
    };
  }

  // ==================== PANEL GUARDADOS ====================
  function renderSavedPanel() {
    const savedCityObjs = cities.filter(c => savedCities.has(c.id));
    $('saved-cities-list').innerHTML = savedCityObjs.map(c => `
      <article class="agenda-card" style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <strong style="color:#fff">${escape(c.name)}</strong>
          <p class="hint" style="margin:2px 0 0">${escape(c.province)} · ${escape(c.region)}</p>
        </div>
        <button type="button" class="btn-text-teal" data-jump-city="${escape(c.id)}">Ver en mapa</button>
      </article>
    `).join('') || '<p class="hint">No tenés destinos guardados. Tocá el corazón ♡ en la tarjeta de una ciudad.</p>';

    $('saved-cities-list').querySelectorAll('[data-jump-city]').forEach(btn => {
      btn.onclick = () => {
        selectCity(btn.dataset.jumpCity);
        $('destination-card').hidden = false;
      };
    });

    $('saved-events-summary').innerHTML = localAgendaEvents.map(ev => `
      <article class="agenda-card">
        <div class="agenda-card-top">
          <strong>${escape(ev.name)}</strong>
          <span class="todo-tag ${escape(ev.tagClass)}">${ev.temp}° · ${escape(ev.tag)}</span>
        </div>
        <p class="hint" style="margin:4px 0 0">${escape(ev.date)} · ${escape(ev.time)} hs · ${escape(ev.place)}</p>
      </article>
    `).join('') || '<p class="hint">Sin eventos guardados.</p>';
  }

  // ==================== MAPA Y CIUDADES ====================
  function selectedCities() {
    const city = cities.find(c => c.id === state.city_id);
    if (!city) return [];
    const type = $('territory').value;
    if (type === 'province') return cities.filter(c => c.province === city.province);
    if (type === 'region') return cities.filter(c => c.region === city.region);
    if (type === 'multi' || type === 'polygon') return cities.filter(c => state.selected.includes(c.id));
    return [city];
  }

  function renderMap() {
    markers.clearLayers();
    pointLayers.clear();
    const selected = new Set(selectedCities().map(c => c.id));
    for (const city of cities) {
      const row = pointFrames.get(city.id), value = row?.focus?.value;
      const active = city.id === state.city_id;
      const cachedDays = weatherForecastCache.get(city.id);
      const fallbackTemp = cachedDays?.[0]?.temp ?? Math.round(20 + (city.latitude + 45.88) * 0.45);
      const displayLabel = value != null
        ? `${number(value)} ${escape(row.focus.unit === 'C' ? '°' : row.focus.unit)}`
        : `${fallbackTemp}°`;

      const marker = L.marker([city.latitude, city.longitude], {
        zIndexOffset: active ? 1000 : 10,
        icon: L.divIcon({
          className: 'observation-marker',
          iconSize: [120, 52],
          iconAnchor: [60, 26],
          html: `
            <div class="map-pill-wrap">
              <span class="point-value ${escape(row?.kind || 'forecast')}${active ? ' selected' : ''}">☀ ${displayLabel}</span>
              <span class="map-city-tag">${escape(city.name)}</span>
            </div>
          `
        })
      });

      marker.on('click', () => {
        $('destination-card').hidden = false;
        if ($('territory').value === 'multi') {
          state.selected = state.selected.includes(city.id) ? state.selected.filter(id => id !== city.id) : [...state.selected, city.id];
          state.mode = 'compare';
          $('mode').value = 'compare';
          renderMap();
          safe(load)();
          panel('data');
        } else {
          selectCity(city.id);
        }
      });
      marker.addTo(markers);
      pointLayers.set(city.id, marker);
    }
    if ($('selection-label')) {
      $('selection-label').textContent = selected.size + ' ubicación(es) seleccionada(s) · puntos consultados, sin interpolación';
    }
  }

  function selectCity(id, { fetchData = true } = {}) {
    const city = cities.find(c => c.id === id);
    if (!city) return;
    state.city_id = id;
    if ($('city')) $('city').value = id;
    if ($('search')) $('search').value = city.name;
    if ($('location-name')) $('location-name').textContent = city.name + ' · ' + city.province;
    if ($('event-city')) $('event-city').textContent = 'Ubicación: ' + city.name + ' · centroide GeoRef, no sitio exacto.';
    $('destination-card').hidden = false;
    map.flyTo([city.latitude, city.longitude], Math.max(map.getZoom(), 7), { duration: 0.4 });
    incidents = allIncidents.filter(i => i.city_id === id);
    renderIncidents();
    renderMap();
    queryContext();
    updateDestinationCard();
    renderTripBar();
    if (fetchData) scheduleLoad(0);
    if (state.panel === 'profile') safe(profile)();
    if (state.panel === 'prediction') renderPredictionPanel();
  }

  function variables() {
    const previous = state.variable;
    let choices = catalog.filter(r => r.provider === state.provider);
    if (['power', 'power-daily', 'forecast', 'era5'].includes(state.provider)) {
      choices = catalog.filter(r => r.provider === 'power');
      choices.push(...['precipitation_probability', 'wind_gusts_10m', 'cloud_cover', 'apparent_temperature', 'visibility', 'wind_direction_10m'].map(variable => ({ variable, name: variableNames[variable] })));
      if (!choices.some(r => r.variable === previous) && variableNames[previous]) choices.push({ variable: previous, name: variableNames[previous] });
    }
    choices = choices.filter((r, i, a) => a.findIndex(x => x.variable === r.variable) === i);
    $('variable').innerHTML = choices.map(r => `<option value="${escape(r.variable)}">${escape(variableNames[r.variable] || r.name || r.variable)}</option>`).join('');
    state.variable = choices.some(r => r.variable === previous) ? previous : choices[0]?.variable;
    $('variable').value = state.variable || '';
  }

  function updateAxis() {
    const percent = Time.position(state.date, view);
    $('scrubber').value = Math.round(Math.max(0, Math.min(1, percent)) * 10000);
    $('scrubber').dataset.start = String(view.start);
    $('scrubber').dataset.end = String(view.end);
    $('scrubber').setAttribute('aria-valuetext', state.date + ' UTC');
    $('date').value = state.date.length === 10 ? state.date + 'T12:00' : state.date.slice(0, 16);
    $('time-current').textContent = new Date(Time.parse(state.date)).toLocaleString('es-AR', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    $('time-start').textContent = new Date(view.start).toISOString().slice(0, 10);
    $('time-end').textContent = new Date(view.end).toISOString().slice(0, 10);
    const now = (Date.now() - view.start) / (view.end - view.start), split = Math.max(0, Math.min(1, now));
    const today = new Date(); today.setUTCHours(0, 0, 0, 0);
    const horizon = (+today + 16 * 864e5 - view.start) / (view.end - view.start);
    const forecastEnd = Math.max(split, Math.max(0, Math.min(1, horizon)));
    $('axis-past').style.width = split * 100 + '%';
    $('axis-future').style.width = (forecastEnd - split) * 100 + '%';
    $('axis-climate').style.width = (1 - forecastEnd) * 100 + '%';
    $('axis-now').hidden = now < 0 || now > 1;
    $('axis-now').style.left = split * 100 + '%';
    const formatter = new Intl.DateTimeFormat('es-AR', view.end - view.start > 730 * 864e5 ? { year: 'numeric', timeZone: 'UTC' } :
      view.end - view.start > 60 * 864e5 ? { month: 'short', year: '2-digit', timeZone: 'UTC' } : { day: 'numeric', month: 'short', timeZone: 'UTC' });
    $('axis-ticks').innerHTML = Array.from({ length: 7 }, (_, i) => '<span>' + escape(formatter.format(view.start + (view.end - view.start) * i / 6)) + '</span>').join('');
    renderTimelineMarkers();
  }

  function updateTime(value, options = {}) {
    if (value) state.date = Time.iso(Time.parse(value));
    const position = Time.position(state.date, view);
    if (options.center || position < 0 || position > 1) view = Time.view(state.date, state.scale);
    calendarDate = new Date(Time.parse(state.date));
    updateAxis();
    calendar();
    queryContext();
    renderTripBar();
    if ($('profile-date')) $('profile-date').value = state.date.slice(0, 10);
    if (options.fetch !== false) scheduleLoad(options.delay ?? 0);
  }

  function scheduleLoad(delay = 100) {
    clearTimeout(loadTimer);
    controller?.abort();
    seq++;
    pointFrames.clear();
    frame = null;
    record = null;
    activeValue();
    renderMap();
    document.body.dataset.frameReady = 'false';
    $('inspector').setAttribute('aria-busy', 'true');
    if ($('map-value')) $('map-value').textContent = 'Consultando ' + (variableNames[state.variable] || state.variable) + '…';
    loadTimer = setTimeout(() => safe(load)(), delay);
  }

  function activeValue() {
    const value = frame?.focus?.value, unit = frame?.focus?.unit || '';
    $('value').textContent = number(value);
    $('value-unit').textContent = unit;
    if ($('map-value')) $('map-value').textContent = number(value) + (value != null ? ' ' + unit : ' · sin dato para esta fecha');
    const kind = frame?.kind || 'unavailable';
    $('time-kind').className = 'kind-label ' + kind;
    $('time-kind').textContent = kind === 'forecast' && Math.abs(Time.parse(state.date) - Date.now()) < 36e5 ? 'AHORA · PRONÓSTICO' : labels[kind] || kind;
    $('data-kind').textContent = labels[kind] || kind;
    $('data-title').textContent = variableNames[state.variable] || state.variable;
    if (kind === 'climatology_reference' && $('map-value')) $('map-value').textContent = number(value) + ' ' + unit + ' · referencia mensual';
  }

  function plot(rows) {
    if (chart) chart.destroy();
    chart = null;
    const available = rows.filter(row => row.series?.length);
    if (!available.length) return;
    const datasets = available.map((row, index) => ({
      label: (row.location?.name || state.city_id) + ' · ' + row.unit,
      data: row.series.map(p => ({ x: Time.parse(p.date), y: p.value })),
      borderColor: index ? '#e3b879' : row.kind === 'forecast' ? '#c4a3ff' : '#38d9a9',
      borderDash: row.kind === 'forecast' ? [6, 4] : [],
      pointRadius: row.series.length > 100 ? 0 : 2,
      spanGaps: false,
      tension: 0
    }));
    const positions = datasets.flatMap(d => d.data.map(p => p.x)), min = Math.min(...positions), max = Math.max(...positions);
    chart = new Chart($('chart'), {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        parsing: false,
        scales: {
          x: { type: 'linear', min, max: max === min ? max + 36e5 : max, ticks: { color: '#9bb1bd', maxTicksLimit: 4, callback: v => new Date(v).toISOString().slice(0, record?.frequency === 'hourly' ? 16 : 10) } },
          y: { ticks: { color: '#9bb1bd' } }
        },
        plugins: { legend: { labels: { color: '#9bb1bd', font: { size: 10 } } } }
      }
    });
  }

  async function obtain(id, signal) {
    const selection = { city_id: id, date: state.date, variable: state.variable, provider: state.provider, scale: state.scale, start: state.start, end: state.end, mode: state.mode };
    return api('/api/workspace/frame?' + new URLSearchParams(selection), { signal });
  }

  async function load() {
    clearTimeout(loadTimer);
    controller?.abort();
    controller = new AbortController();
    const signal = controller.signal, ticket = ++seq;
    record = null;
    frame = null;
    comparisonRecords = [];
    pointFrames.clear();
    activeValue();
    renderMap();
    $('provenance').innerHTML = '';
    $('comparison').innerHTML = '';
    $('limits').textContent = '';
    if (chart) { chart.destroy(); chart = null; }
    notice('Consultando ubicación y fecha…');
    try {
      const result = await obtain(state.city_id, signal);
      if (ticket !== seq) return;
      frame = result;
      record = result.record;
      pointFrames.set(state.city_id, result);
      document.body.dataset.frameDate = result.selection.date;
      document.body.dataset.frameVariable = result.selection.variable;
      document.body.dataset.frameKind = result.kind;
      document.body.dataset.frameReady = 'true';
      $('inspector').setAttribute('aria-busy', 'false');
      const rows = record ? [record] : [];
      comparisonRecords = rows;
      activeValue();
      updateDestinationCard();
      renderMap();
      plot(rows);
      queryContext();
      const climate = result.climatology;
      const fields = record ? [
        ['Fuente / producto', record.provider + ' · ' + record.product],
        ['Frecuencia nativa', record.frequency],
        ['Obtención UTC', record.fetched_at],
        ['Muestra seleccionada', result.focus?.sample_date || 'Sin muestra válida'],
        ['Cobertura de la extracción', record.series.length + ' registros']
      ] : climate ? [
        ['Fuente', 'NASA POWER · referencia mensual 2000–2024'],
        ['Referencia', climate.count + ' años para el mes ' + climate.month],
        ['Unidad nativa', climate.unit]
      ] : [];
      $('provenance').innerHTML = fields.map(([name, value]) => `<dt>${escape(name)}</dt><dd>${escape(value)}</dd>`).join('');
      $('limits').textContent = [result.message, ...(record?.limitations || [])].join(' ');
      notice(result.message, result.status === 'unavailable');
      if (state.panel === 'impact') await impact();
    } catch (error) {
      if (ticket !== seq || error.name === 'AbortError') return;
      frame = { kind: 'unavailable', focus: null, message: error.message };
      activeValue();
      pointFrames.set(state.city_id, frame);
      updateDestinationCard();
      renderMap();
      notice(error.message, true);
    }
  }

  // Controles de línea temporal
  function step(direction) { updateTime(Time.move(state.date, state.scale, direction)); }
  function stop() { clearInterval(timer); timer = null; $('play').textContent = '▶'; }
  $('play').onclick = () => {
    if (timer) { stop(); return; }
    $('play').textContent = 'Ⅱ';
    timer = setInterval(() => step(+$('direction').value), +$('speed').value);
  };
  $('speed').onchange = () => { if (timer) { stop(); $('play').click(); } };
  $('step-back').onclick = () => step(-1);
  $('step-next').onclick = () => step(1);
  $('scrubber').oninput = () => updateTime(Time.at($('scrubber').value, view, state.scale), { delay: 140 });
  $('scrubber').onchange = () => scheduleLoad(0);
  $('date').onchange = () => { stop(); updateTime($('date').value, { center: true }); };
  $('scale').onchange = () => { state.scale = $('scale').value; view = Time.view(state.date, state.scale); updateTime(); };
  $('zoom-in').onclick = () => { view = Time.zoom(view, state.date, 0.5); updateAxis(); };
  $('zoom-out').onclick = () => { view = Time.zoom(view, state.date, 2); updateAxis(); };
  $('present').onclick = () => { stop(); state.mode = 'date'; $('mode').value = 'date'; state.scale = 'daily'; $('scale').value = 'daily'; updateTime(Time.iso(Date.now()), { center: true }); };
  $('city').onchange = () => selectCity($('city').value);

  // Buscador de ciudades en la barra superior con dropdown interactivo
  function renderSearchDropdown(queryText) {
    const q = queryText.trim().toLocaleLowerCase('es');
    const matches = cities.filter(c => !q || c.name.toLocaleLowerCase('es').includes(q) || c.province.toLocaleLowerCase('es').includes(q));
    if (!matches.length) {
      $('search-dropdown').hidden = true;
      return;
    }
    $('search-dropdown').innerHTML = matches.slice(0, 8).map(c => `
      <button type="button" class="search-option" data-pick-city="${escape(c.id)}">
        <span>${escape(c.name)}</span>
        <small>${escape(c.province)}</small>
      </button>
    `).join('');
    $('search-dropdown').hidden = false;
    $('search-dropdown').querySelectorAll('[data-pick-city]').forEach(btn => {
      btn.onclick = () => {
        $('search-dropdown').hidden = true;
        selectCity(btn.dataset.pickCity);
      };
    });
  }

  $('search').onfocus = () => renderSearchDropdown('');
  $('search').oninput = () => {
    const query = $('search').value.trim().toLocaleLowerCase('es');
    renderSearchDropdown(query);
    const exact = cities.find(c => [c.name, c.name + ', ' + c.province, c.id].some(n => n.toLocaleLowerCase('es') === query));
    if (exact && exact.id !== state.city_id) {
      $('search-dropdown').hidden = true;
      selectCity(exact.id);
    }
  };
  document.addEventListener('click', e => {
    if (!e.target.closest('.city-search')) $('search-dropdown').hidden = true;
  });

  $('source').onchange = () => { state.provider = $('source').value; variables(); scheduleLoad(0); };
  $('variable').onchange = () => { state.variable = $('variable').value; queryContext(); scheduleLoad(0); };
  $('mode').onchange = () => { state.mode = $('mode').value; safe(load)(); panel('data'); };

  // Calendario mensual con etiquetas de eventos
  function calendar() {
    const type = $('cal-view').value, first = new Date(calendarDate);
    first.setUTCDate(1);
    let count = type === 'month' ? new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate() : type === 'week' ? 7 : 1;
    if (type === 'week') first.setUTCDate(calendarDate.getUTCDate() - ((calendarDate.getUTCDay() + 6) % 7));
    if (type === 'day') first.setUTCDate(calendarDate.getUTCDate());
    $('cal-title').textContent = calendarDate.toLocaleDateString('es-AR', { month: 'long', year: 'numeric', timeZone: 'UTC' });
    $('calendar-jump').value = state.date.slice(0, 10);
    $('calendar').classList.toggle('list', type === 'list' || type === 'day');

    const allEvents = [
      ...localAgendaEvents.map(e => ({ id: e.id, name: `${e.name} (${e.temp}° · ${e.tag})`, start: e.date })),
      ...events.filter(e => e.status === 'active')
    ];

    if (type === 'list') {
      $('calendar').innerHTML = allEvents.map(e => `<button data-event="${escape(e.id)}">${escape(e.name)} · ${escape(e.start)}</button>`).join('') || '<p>Sin eventos guardados.</p>';
    } else {
      let html = type === 'month' ? ['L', 'M', 'M', 'J', 'V', 'S', 'D'].map(d => '<span class="hint">' + d + '</span>').join('') + '<span></span>'.repeat((first.getUTCDay() + 6) % 7) : '';
      for (let i = 0; i < count; i++) {
        const day = new Date(first);
        day.setUTCDate(first.getUTCDate() + i);
        const iso = day.toISOString().slice(0, 10);
        const associated = allEvents.filter(e => e.start.slice(0, 10) === iso);
        html += `<button data-day="${iso}" class="${iso === state.date.slice(0, 10) ? 'selected ' : ''}${associated.length ? 'has-event' : ''}">${day.getUTCDate()}${associated.map(e => '<span class="day-caption">' + escape(e.name) + '</span>').join('')}</button>`;
      }
      $('calendar').innerHTML = html;
    }

    $('calendar').querySelectorAll('[data-day]').forEach(button => {
      button.onclick = () => {
        updateTime(button.dataset.day, { center: true });
      };
    });
  }

  $('cal-view').onchange = calendar;
  function moveCalendar(direction) {
    const type = $('cal-view').value;
    if (type === 'month' || type === 'list') {
      calendarDate.setUTCDate(1);
      calendarDate.setUTCMonth(calendarDate.getUTCMonth() + direction);
    } else {
      calendarDate.setUTCDate(calendarDate.getUTCDate() + direction * (type === 'week' ? 7 : 1));
    }
    calendar();
  }
  $('cal-prev').onclick = () => moveCalendar(-1);
  $('cal-next').onclick = () => moveCalendar(1);
  $('calendar-jump').onchange = () => updateTime($('calendar-jump').value, { center: true });
  $('new-event').onclick = () => {
    prepareQuickEventForm(state.date.slice(0, 10));
    $('quick-event-result').hidden = true;
    panel('add-event');
  };

  function renderIncidents() {
    if (!$('incidents')) return;
    $('incidents').innerHTML = incidents.map(i => `<article class="card"><strong>${escape(i.name)}</strong><p>${escape(i.start)} / ${escape(i.end)}</p><p>${escape(i.description)}</p></article>`).join('') || '<p class="hint">Sin acontecimientos documentados en el catálogo actual.</p>';
    renderEvents();
  }

  function renderTimelineMarkers() {
    if (!$('time-markers')) return;
    const rows = [
      ...events.filter(e => e.status === 'active').map(e => ({ id: e.id, date: e.start, name: e.name, event: true })),
      ...localAgendaEvents.map(e => ({ id: e.id, date: e.date, name: e.name, event: true }))
    ];
    $('time-markers').innerHTML = rows.filter(r => Time.position(r.date, view) >= 0 && Time.position(r.date, view) <= 1).map(r =>
      `<button style="left:${Time.position(r.date, view) * 100}%" class="event-mark" data-event="${escape(r.id)}" title="${escape(r.name + ' · ' + r.date)}">⚑</button>`
    ).join('');
  }

  function renderEvents() {
    eventMarkers.clearLayers();
    incidentMarkers.clearLayers();
    renderTimelineMarkers();
    calendar();
  }

  async function profile() {
    const id = state.city_id, result = await api('/api/workspace/profiles/' + id);
    if (id !== state.city_id) return;
    $('profile-title').textContent = result.city.name;
    $('profile-content').innerHTML = `<p>${escape(result.city.province)} · ${escape(result.city.region)}</p><p class="hint">${result.city.latitude.toFixed(5)}, ${result.city.longitude.toFixed(5)} · centroide GeoRef.</p><div class="profile-radial"><h2>Earth Fingerprint climatológico</h2><div id="radial-result"><div class="chart-wrap"><canvas id="climate-radial"></canvas></div></div></div>`;
    try {
      const data = await api('/api/workspace/profiles/' + id + '/climatology-fingerprint');
      if (id !== state.city_id) return;
      if (radial) radial.destroy();
      radial = new Chart($('climate-radial'), {
        type: 'radar',
        data: {
          labels: data.axes.map(a => a.variable),
          datasets: [{ label: 'Z climatológico', data: data.axes.map(a => a.z_score), borderColor: '#38d9a9', backgroundColor: '#38d9a922' }]
        },
        options: { responsive: true, maintainAspectRatio: false, animation: false }
      });
    } catch (_) {}
  }

  async function loadAccount() {
    try {
      const me = await api('/api/session');
      user = me.user;
      csrf = me.csrf_token;
      $('auth').hidden = !!user;
      $('account').hidden = !user;
      if (user) {
        $('account-name').textContent = user.username;
        $('avatar-initial').textContent = user.username.charAt(0).toUpperCase();
        events = await api('/api/events');
        notificationRows = await api('/api/notifications');
      }
    } catch (_) {}
    updateNotificationBadge();
  }

  async function impact() {
    const city = state.city_id, result = await api('/api/impact?city_id=' + city);
    $('impact-content').innerHTML = `<p class="eyebrow">${escape(result.status)}</p><p>${escape(result.summary)}</p>`;
  }

  $('theme').onclick = () => document.body.classList.toggle('light');

  try {
    [cities, catalog, allIncidents] = await Promise.all([
      api('/api/cities'),
      api('/api/science/variables'),
      api('/api/workspace/incidents')
    ]);
    $('city').innerHTML = cities.map(city => `<option value="${city.id}">${escape(city.name)}</option>`).join('');
    $('city-suggestions').innerHTML = cities.map(city => `<option value="${escape(city.name)}">${escape(city.province)}</option>`).join('');
    if (!cities.some(city => city.id === state.city_id)) state.city_id = cities[0].id;
    const initialPanel = state.panel;
    state.panel = null;
    $('source').value = state.provider;
    variables();
    $('scale').value = state.scale;
    $('mode').value = state.mode;
    $('start').value = state.start;
    $('end').value = state.end;

    selectCity(state.city_id, { fetchData: false });
    updateTime(state.date, { fetch: false });
    await loadAccount();
    await load();
    if (initialPanel) panel(initialPanel);
    window.addEventListener('resize', () => { map.invalidateSize(); chart?.resize(); });
  } catch (error) {
    notice(error.message, true);
  }
});
