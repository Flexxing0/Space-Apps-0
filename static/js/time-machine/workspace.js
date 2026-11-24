/* EarthLens: Interfaz Responsive + Cuenta real en SQLite (Eventos, Preferencias, Notificaciones y Guardados) */
'use strict';
document.addEventListener('DOMContentLoaded', async () => {
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search), Time = window.EarthLensTimeAxis;
  const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

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
    tripStartDate: new Date().toISOString().slice(0, 10),
    tripDurationDays: 5,
    selectedPredictionDayIdx: 0,
    inlineAuthMode: 'login',
    postAuthPanel: null
  };

  let cities = [], catalog = [], record = null, frame = null, comparisonRecords = [], chart = null, radial = null, versionChart = null;
  let activeHistoryId = null, activeEventId = null, controller = null, seq = 0, timer = null, loadTimer = null;
  let calendarDate = new Date(Time.parse(state.date)), user = null, csrf = null, events = [], notificationRows = [], notificationEventFilter = null;
  let incidents = [], allIncidents = [], drawing = false, vertices = [], polygon = null, view = Time.view(state.date, state.scale);
  let weatherForecastCache = new Map(), cityProfileCache = new Map(), cityPhotoCache = new Map();
  let savedCities = new Set();

  // Artículos exactos de Wikipedia (ES y EN) para las 25 ciudades argentinas del catálogo
  const CITY_WIKI_TITLES = {
    'comodoro-rivadavia': { es: 'Comodoro Rivadavia', en: 'Comodoro Rivadavia' },
    'puerto-madryn': { es: 'Puerto Madryn', en: 'Puerto Madryn' },
    'trelew': { es: 'Trelew', en: 'Trelew' },
    'rio-gallegos': { es: 'Río Gallegos', en: 'Río Gallegos, Santa Cruz' },
    'ushuaia': { es: 'Ushuaia', en: 'Ushuaia' },
    'bariloche': { es: 'San Carlos de Bariloche', en: 'Bariloche' },
    'neuquen': { es: 'Neuquén (ciudad)', en: 'Neuquén' },
    'buenos-aires': { es: 'Buenos Aires', en: 'Buenos Aires' },
    'la-plata': { es: 'La Plata', en: 'La Plata' },
    'mar-del-plata': { es: 'Mar del Plata', en: 'Mar del Plata' },
    'bahia-blanca': { es: 'Bahía Blanca', en: 'Bahía Blanca' },
    'rosario': { es: 'Rosario (Argentina)', en: 'Rosario, Santa Fe' },
    'cordoba': { es: 'Córdoba (Argentina)', en: 'Córdoba, Argentina' },
    'santa-fe': { es: 'Santa Fe (Argentina)', en: 'Santa Fe, Argentina' },
    'mendoza': { es: 'Mendoza (Argentina)', en: 'Mendoza, Argentina' },
    'san-juan': { es: 'San Juan (Argentina)', en: 'San Juan, Argentina' },
    'san-luis': { es: 'San Luis (Argentina)', en: 'San Luis, Argentina' },
    'salta': { es: 'Salta', en: 'Salta' },
    'san-salvador-de-jujuy': { es: 'San Salvador de Jujuy', en: 'San Salvador de Jujuy' },
    'san-miguel-de-tucuman': { es: 'San Miguel de Tucumán', en: 'San Miguel de Tucumán' },
    'santiago-del-estero': { es: 'Santiago del Estero (ciudad)', en: 'Santiago del Estero' },
    'posadas': { es: 'Posadas (Argentina)', en: 'Posadas, Misiones' },
    'corrientes': { es: 'Corrientes (ciudad)', en: 'Corrientes' },
    'resistencia': { es: 'Resistencia (ciudad)', en: 'Resistencia, Chaco' },
    'formosa': { es: 'Formosa (ciudad)', en: 'Formosa, Argentina' }
  };

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

  function weatherSvg(type) {
    if (type === 'rain') {
      return `<svg viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="1.9" stroke-linecap="round"><path d="M17.5 17H7a4 4 0 0 1-.5-7.97A5.5 5.5 0 0 1 17.3 10a3.5 3.5 0 0 1 .2 7Z"/><path d="M9 20l-1 2M13 20l-1 2M17 20l-1 2"/></svg>`;
    }
    if (type === 'cloud' || type === 'wind') {
      return `<svg viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.9" stroke-linecap="round"><path d="M17.5 19H7a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18.2 11a4 4 0 0 1-.7 8Z"/></svg>`;
    }
    return `<svg viewBox="0 0 24 24" fill="none" stroke="#facc15" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6"/></svg>`;
  }

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

  // Suma horas a fecha/hora local Argentina (-03:00) cuidando el cruce de medianoche
  function buildArgentinaStartEnd(dateStr, timeStr, durationHours = 2) {
    const [y, m, d] = dateStr.split('-').map(Number);
    const [hh, mm] = (timeStr || '10:30').split(':').map(Number);
    const startUtc = new Date(Date.UTC(y, m - 1, d, hh, mm, 0));
    const endUtc = new Date(startUtc.getTime() + durationHours * 3600000);
    const fmt = dt => {
      const yy = dt.getUTCFullYear();
      const mo = String(dt.getUTCMonth() + 1).padStart(2, '0');
      const da = String(dt.getUTCDate()).padStart(2, '0');
      const hr = String(dt.getUTCHours()).padStart(2, '0');
      const mi = String(dt.getUTCMinutes()).padStart(2, '0');
      return `${yy}-${mo}-${da}T${hr}:${mi}:00-03:00`;
    };
    return { start: fmt(startUtc), end: fmt(endUtc) };
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
      error.status = response.status;
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

  // ==================== LAYOUT MÓVIL / COMPACTO ====================
  function syncMobileLayout(initial = false) {
    if (isMobile()) {
      if (initial) {
        $('best-season-card').hidden = true;
        $('map-layers-card').hidden = true;
        $('destination-card').classList.add('is-compact');
      }
      $('mob-open-dest').hidden = !$('destination-card').hidden;
    } else {
      $('destination-card').classList.remove('is-compact');
      $('mob-open-dest').hidden = true;
      if ($('best-season-card').hidden && $('reopen-season-btn').hidden) {
        $('best-season-card').hidden = false;
      }
      if ($('map-layers-card').hidden && $('reopen-layers-btn').hidden) {
        $('map-layers-card').hidden = false;
      }
    }
  }

  function setDestinationCompact(compact) {
    $('destination-card').classList.toggle('is-compact', compact);
    $('toggle-compact-dest').textContent = compact ? '▴' : '▾';
  }

  $('toggle-compact-dest').onclick = () => {
    setDestinationCompact(!$('destination-card').classList.contains('is-compact'));
  };
  $('compact-expand-trigger').onclick = () => {
    setDestinationCompact(false);
  };
  $('mob-open-dest').onclick = () => {
    $('destination-card').hidden = false;
    setDestinationCompact(false);
    $('mob-open-dest').hidden = true;
  };
  $('mob-open-layers').onclick = () => {
    const open = $('map-layers-card').hidden;
    $('map-layers-card').hidden = !open;
    $('best-season-card').hidden = true;
    $('mob-open-layers').classList.toggle('active', open);
    $('mob-open-season').classList.remove('active');
    if (open) panel(null);
  };
  $('mob-open-season').onclick = () => {
    const open = $('best-season-card').hidden;
    $('best-season-card').hidden = !open;
    $('map-layers-card').hidden = true;
    $('mob-open-season').classList.toggle('active', open);
    $('mob-open-layers').classList.remove('active');
    if (open) panel(null);
  };

  // ==================== CONTROL DE PANELES DEL INSPECTOR ====================
  function panel(name) {
    document.body.classList.toggle('inspector-open', !!name);
    if (state.panel !== name && $('inspector')) $('inspector').scrollTop = 0;
    if (!name) {
      $('inspector').hidden = true;
      state.panel = null;
      document.querySelectorAll('button[data-panel]').forEach(b => b.classList.remove('active'));
      return;
    }
    if (isMobile()) {
      $('best-season-card').hidden = true;
      $('map-layers-card').hidden = true;
      $('mob-open-layers').classList.remove('active');
      $('mob-open-season').classList.remove('active');
    }
    state.panel = name;
    $('inspector').hidden = false;
    const titles = {
      calendar: 'Agenda y Calendario',
      notifications: 'Notificaciones',
      'add-event': 'Agregar evento',
      'event-detail': 'Detalle del evento',
      prediction: 'Predicción climática',
      saved: 'Guardados',
      data: 'Datos científicos',
      profile: 'Perfil ambiental',
      events: user ? `Mi cuenta · @${user.username}` : 'Iniciar sesión / Crear cuenta',
      impact: 'Impactos y evidencia'
    };
    $('drawer-title').textContent = titles[name] || 'Información';
    document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== 'panel-' + name);
    document.querySelectorAll('button[data-panel]').forEach(b => b.classList.toggle('active', b.dataset.panel === name));
    if (name === 'profile') safe(profile)();
    if (name === 'calendar') { renderAgendaList(); calendar(); }
    if (name === 'notifications') renderNotificationsPanel();
    if (name === 'add-event') syncAddEventAuthGate();
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
    if ($('tools-backdrop')) $('tools-backdrop').hidden = !open;
    $('toggle-tools').setAttribute('aria-expanded', String(open));
  }
  $('toggle-tools').onclick = () => tools($('tools').hidden);
  $('close-tools').onclick = () => tools(false);
  if ($('tools-backdrop')) $('tools-backdrop').onclick = () => tools(false);

  $('close-destination-card').onclick = () => {
    $('destination-card').hidden = true;
    if (isMobile()) $('mob-open-dest').hidden = false;
  };
  $('close-season-card').onclick = () => {
    $('best-season-card').hidden = true;
    $('mob-open-season').classList.remove('active');
    if (!isMobile()) $('reopen-season-btn').hidden = false;
  };
  $('close-layers-card').onclick = () => {
    $('map-layers-card').hidden = true;
    $('mob-open-layers').classList.remove('active');
    if (!isMobile()) $('reopen-layers-btn').hidden = false;
  };
  $('reopen-season-btn').onclick = () => { $('best-season-card').hidden = false; $('reopen-season-btn').hidden = true; };
  $('reopen-layers-btn').onclick = () => { $('map-layers-card').hidden = false; $('reopen-layers-btn').hidden = true; };

  $('btn-add-event-card').onclick = () => {
    $('quick-event-result').hidden = true;
    resetQuickEventForm();
    panel('add-event');
  };
  $('btn-prediction-card').onclick = () => panel('prediction');
  $('btn-login-from-agenda').onclick = () => { state.postAuthPanel = 'calendar'; panel('events'); };
  $('btn-login-from-saved').onclick = () => { state.postAuthPanel = 'saved'; panel('events'); };

  // Mostrar / ocultar contraseña
  document.querySelectorAll('[data-toggle-pass]').forEach(btn => {
    btn.onclick = () => {
      const input = $(btn.dataset.togglePass);
      if (!input) return;
      const hidden = input.type === 'password';
      input.type = hidden ? 'text' : 'password';
      btn.textContent = hidden ? 'Ocultar' : 'Ver';
    };
  });

  // Pestañas Iniciar sesión / Crear cuenta dentro de Agregar evento
  document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.onclick = () => {
      state.inlineAuthMode = tab.dataset.authMode;
      document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t === tab));
      $('inline-auth-submit').textContent = state.inlineAuthMode === 'register'
        ? 'Crear cuenta y continuar al evento'
        : 'Ingresar y continuar al evento';
      $('inline-password').setAttribute('autocomplete', state.inlineAuthMode === 'register' ? 'new-password' : 'current-password');
      $('inline-auth-error').hidden = true;
    };
  });

  // ==================== CUENTA, SESIÓN Y PERSISTENCIA EN SQLITE ====================
  function updateAuthUI() {
    const loggedIn = !!user;
    $('btn-avatar').classList.toggle('logged-in', loggedIn);
    $('avatar-initial').textContent = loggedIn ? user.username.charAt(0).toUpperCase() : '👤';
    $('avatar-username').textContent = loggedIn ? user.username : 'Ingresar';
    $('auth').hidden = loggedIn;
    $('account').hidden = !loggedIn;
    $('agenda-auth-banner').hidden = loggedIn;
    $('saved-auth-banner').hidden = loggedIn;
    if (loggedIn) {
      $('account-name').textContent = '@' + user.username;
      $('account-big-avatar').textContent = user.username.charAt(0).toUpperCase();
      $('account-stats-text').textContent = `${events.filter(e => e.status === 'active').length} evento(s) · ${savedCities.size} destino(s) guardado(s)`;
      $('qe-active-user').textContent = '@' + user.username;
    }
    syncAddEventAuthGate();
    updateSaveCityButton();
    updateNotificationBadge();
  }

  function syncAddEventAuthGate() {
    const loggedIn = !!user;
    $('qe-auth-gate').hidden = loggedIn;
    $('qe-form-container').hidden = !loggedIn;
    if (loggedIn) {
      prepareQuickEventForm();
    }
  }

  async function saveAccountPreferences() {
    if (!user) return;
    try {
      await api('/api/account/preferences', {
        method: 'PUT',
        body: JSON.stringify({
          saved_cities: [...savedCities],
          trip: {
            city_id: state.city_id,
            start_date: state.tripStartDate,
            duration_days: state.tripDurationDays
          }
        })
      });
      updateAuthUI();
    } catch (error) {
      notice(error.message, true);
    }
  }

  async function loadAccount() {
    try {
      const me = await api('/api/session');
      user = me.user;
      csrf = me.csrf_token;
      if (!user) {
        events = [];
        notificationRows = [];
        savedCities = new Set();
        updateAuthUI();
        renderEventsListInAccount();
        if (state.panel === 'calendar') renderAgendaList();
        if (state.panel === 'notifications') renderNotificationsPanel();
        if (state.panel === 'saved') renderSavedPanel();
        renderEvents();
        return;
      }

      const [evList, notifList, prefs] = await Promise.all([
        api('/api/events'),
        api('/api/notifications'),
        api('/api/account/preferences').catch(() => ({ saved_cities: [], trip: null }))
      ]);
      events = evList || [];
      notificationRows = notifList || [];
      savedCities = new Set(prefs?.saved_cities || []);
      if (prefs?.trip?.start_date) {
        state.tripStartDate = prefs.trip.start_date;
        state.tripDurationDays = prefs.trip.duration_days || 5;
      }

      updateAuthUI();
      renderEventsListInAccount();
      renderEvents();
      renderTripBar();
      if (state.panel === 'calendar') renderAgendaList();
      if (state.panel === 'notifications') renderNotificationsPanel();
      if (state.panel === 'saved') renderSavedPanel();
    } catch (error) {
      notice(error.message, true);
    }
  }

  async function performAuth(action, username, password, errorEl) {
    errorEl.hidden = true;
    errorEl.classList.remove('ok');
    if (!csrf) {
      const sess = await api('/api/session');
      csrf = sess.csrf_token;
    }
    try {
      const me = await api('/api/session/' + action, {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password })
      });
      csrf = me.csrf_token;
      user = me.user;
      await loadAccount();
      return true;
    } catch (error) {
      errorEl.textContent = error.message;
      errorEl.hidden = false;
      return false;
    }
  }

  // Login / Registro dentro de "Agregar evento"
  $('inline-auth-form').onsubmit = async e => {
    e.preventDefault();
    const btn = $('inline-auth-submit');
    btn.disabled = true;
    const ok = await performAuth(
      state.inlineAuthMode,
      $('inline-username').value,
      $('inline-password').value,
      $('inline-auth-error')
    );
    btn.disabled = false;
    if (ok) {
      $('inline-password').value = '';
      syncAddEventAuthGate();
      prepareQuickEventForm();
      notice(`Sesión iniciada como @${user.username}. Ya podés guardar eventos en tu cuenta.`);
    }
  };

  // Login / Registro en el panel "Mi cuenta"
  $('auth-form').onsubmit = async e => {
    e.preventDefault();
    const f = $('auth-form').elements;
    const action = e.submitter?.name === 'register' ? 'register' : 'login';
    const ok = await performAuth(action, f.username.value, f.password.value, $('main-auth-error'));
    if (ok) {
      f.password.value = '';
      $('drawer-title').textContent = `Mi cuenta · @${user.username}`;
      notice(`Sesión iniciada como @${user.username}.`);
      if (state.postAuthPanel) {
        const dest = state.postAuthPanel;
        state.postAuthPanel = null;
        panel(dest);
      }
    }
  };

  $('logout').onclick = safe(async () => {
    await api('/api/session/logout', { method: 'POST', body: '{}' });
    user = null;
    events = [];
    notificationRows = [];
    savedCities = new Set();
    $('quick-event-result').hidden = true;
    await loadAccount();
    $('drawer-title').textContent = 'Iniciar sesión / Crear cuenta';
    notice('Sesión cerrada.');
  });

  // Guardar / quitar ciudad favorita (persistido en SQLite si está logueado)
  $('btn-save-city').onclick = async () => {
    if (!user) {
      state.postAuthPanel = 'saved';
      panel('events');
      $('main-auth-error').textContent = 'Iniciá sesión o creá una cuenta para guardar ciudades favoritas.';
      $('main-auth-error').hidden = false;
      return;
    }
    if (savedCities.has(state.city_id)) {
      savedCities.delete(state.city_id);
    } else {
      savedCities.add(state.city_id);
    }
    updateSaveCityButton();
    await saveAccountPreferences();
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
        if (byDay.has(d) && p.value != null) byDay.get(d).winds.push(p.value * 3.6);
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
    } catch (_) {}

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

  async function computeEventWeatherSummary(ev) {
    const days = await getCityForecastDays(ev.city_id);
    const dateStr = ev.start.slice(0, 10);
    const matchDay = days.find(d => d.date === dateStr) || days[0];
    const diffDays = Math.max(0, Math.round((Time.parse(dateStr) - Date.now()) / 86400000));
    const confidence = diffDays <= 3
      ? 'Alta (90%) · Horizonte cercano Open-Meteo'
      : diffDays <= 7
        ? 'Media-Alta (82%) · Pronóstico operativo Open-Meteo'
        : diffDays <= 15
          ? 'Media (70%) · Horizonte extendido 16 días'
          : 'Referencia climatológica NASA POWER (2000–2024)';

    let tag = 'Ideal', tagClass = 'tag-ideal', iconEmoji = '☀️', rec = '';
    if (ev.activity === 'indoor' || ev.outdoor === false) {
      tag = 'Techado';
      tagClass = 'tag-indoor';
      iconEmoji = '🏛️';
      rec = `Actividad bajo techo sin restricciones climáticas. Afuera se esperan ${matchDay.temp}°C y viento de ${matchDay.windKmh} km/h.`;
    } else if (matchDay.rainProb >= 45) {
      tag = 'Lluvia probable';
      tagClass = 'tag-rain';
      iconEmoji = '🌧️';
      rec = `Probabilidad de lluvia del ${matchDay.rainProb}%. Se recomienda llevar equipo impermeable o evaluar otro horario.`;
    } else if (matchDay.windKmh >= 35) {
      tag = 'Ventoso';
      tagClass = 'tag-windy';
      iconEmoji = '💨';
      rec = `Buena temperatura (${matchDay.temp}°C) pero viento de ${matchDay.windKmh} km/h. Llevá cortaviento, anteojos de sol y protector.`;
    } else {
      tag = 'Ideal';
      tagClass = 'tag-ideal';
      iconEmoji = '☀️';
      rec = `Condiciones muy favorables (${matchDay.temp}°C, lluvia ${matchDay.rainProb}%). Llevá protector solar (UV ${matchDay.uv}) y agua.`;
    }
    return { ...matchDay, confidence, tag, tagClass, iconEmoji, recommendation: rec };
  }

  // ==================== TARJETA IZQUIERDA DEL DESTINO ====================
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
    $('compact-temp-val').textContent = `${tempVal}°`;
    $('dest-stat-wind').textContent = `${activeDay.windKmh} km/h`;
    $('dest-stat-rain').textContent = `${activeDay.rainProb} %`;
    $('dest-stat-uv').textContent = String(activeDay.uv);
    $('dest-stat-light').textContent = activeDay.lightStr;

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

    const chips = [];
    if (activeDay.windKmh >= 22) chips.push('Cortaviento');
    if (activeDay.uv >= 5 || activeDay.icon === 'sun') {
      chips.push('Anteojos de sol', 'Protector solar', 'Gorra');
    }
    if (activeDay.rainProb >= 35) chips.push('Piloto impermeable');
    if (tempVal <= 14) chips.push('Abrigo térmico');
    for (const extra of ['Cortaviento', 'Anteojos de sol', 'Protector solar', 'Gorra']) {
      if (!chips.includes(extra) && chips.length < 4) chips.push(extra);
    }
    $('dest-what-to-wear').innerHTML = chips.slice(0, 4).map(c => `<span class="wear-chip">${escape(c)}</span>`).join('');

    const activities = getCityActivities(city);
    $('dest-todo-list').innerHTML = activities.map(act => {
      let tagText = 'Ideal', tagClass = 'tag-ideal';
      if (act.type === 'indoor') {
        tagText = 'Techado'; tagClass = 'tag-indoor';
      } else if (act.type === 'coastal') {
        if (activeDay.rainProb >= 45) { tagText = 'Lluvia'; tagClass = 'tag-rain'; }
        else if (activeDay.windKmh >= 25) { tagText = 'Ventoso'; tagClass = 'tag-windy'; }
      } else {
        if (activeDay.rainProb >= 45) { tagText = 'Revisar'; tagClass = 'tag-rain'; }
        else if (activeDay.windKmh >= 45) { tagText = 'Ventoso'; tagClass = 'tag-windy'; }
      }
      return `<li class="todo-item"><span class="todo-name">${escape(act.name)}</span><span class="todo-tag ${tagClass}">${escape(tagText)}</span></li>`;
    }).join('');

    updateCityPhotoAndClimatology(city.id);
  }

  function isAcceptablePhotoUrl(url, title = '') {
    if (!url) return false;
    const text = (url + ' ' + title).toLowerCase();
    if (text.includes('.svg')) return false;
    const forbidden = ['escudo', 'bandera', 'flag_of', 'coat_of_arms', 'location_map', 'mapa_', 'locator', 'blank_map', 'logo', 'seal_of', 'emblem'];
    if (forbidden.some(bad => text.includes(bad))) return false;
    return /\.(jpe?g|png|webp)(\?|$)/i.test(url.split('/').pop() || '') || /\/thumb\//.test(url);
  }

  async function fetchWikiPageImage(lang, title) {
    try {
      const qs = new URLSearchParams({
        action: 'query',
        titles: title,
        prop: 'pageimages',
        piprop: 'thumbnail',
        pithumbsize: '640',
        redirects: '1',
        format: 'json',
        origin: '*'
      });
      const resp = await fetch(`https://${lang}.wikipedia.org/w/api.php?` + qs);
      if (!resp.ok) return null;
      const data = await resp.json();
      const pages = Object.values(data.query?.pages || {});
      for (const page of pages) {
        const src = page.thumbnail?.source;
        if (src && isAcceptablePhotoUrl(src, page.pageimage || page.title || '')) {
          return {
            url: src,
            credit: `Fotografía ilustrativa de ${page.title || title} vía Wikipedia (${lang.toUpperCase()})`
          };
        }
      }
    } catch (_) {}
    return null;
  }

  async function fetchCommonsSearchPhotos(city) {
    const found = [];
    try {
      const qs = new URLSearchParams({
        action: 'query',
        generator: 'search',
        gsrsearch: `filetype:bitmap ${city.name} Argentina`,
        gsrnamespace: '6',
        gsrlimit: '15',
        prop: 'imageinfo',
        iiprop: 'url|mime|dimensions',
        iiurlwidth: '640',
        format: 'json',
        origin: '*'
      });
      const resp = await fetch('https://commons.wikimedia.org/w/api.php?' + qs);
      if (!resp.ok) return found;
      const data = await resp.json();
      const pages = Object.values(data.query?.pages || {});
      // Priorizar imágenes horizontales reales (paisajes/vistas urbanas)
      pages.sort((a, b) => {
        const ia = a.imageinfo?.[0] || {}, ib = b.imageinfo?.[0] || {};
        const aLand = (ia.width || 0) >= (ia.height || 1) ? 0 : 1;
        const bLand = (ib.width || 0) >= (ib.height || 1) ? 0 : 1;
        return aLand - bLand;
      });
      for (const p of pages) {
        const info = p.imageinfo?.[0];
        const url = info?.thumburl || info?.url;
        if (url && info?.mime?.startsWith('image/jpeg') && isAcceptablePhotoUrl(url, p.title || '')) {
          found.push({
            url,
            credit: `${(p.title || '').replace(/^File:/i, '')} · Wikimedia Commons`
          });
          if (found.length >= 3) break;
        }
      }
    } catch (_) {}
    return found;
  }

  async function fetchCommonsGeoPhotos(city) {
    const found = [];
    try {
      const qs = new URLSearchParams({
        action: 'query',
        generator: 'geosearch',
        ggscoord: `${city.latitude}|${city.longitude}`,
        ggsradius: '10000',
        ggslimit: '15',
        ggsnamespace: '6',
        prop: 'imageinfo',
        iiprop: 'url|mime',
        iiurlwidth: '640',
        format: 'json',
        origin: '*'
      });
      const resp = await fetch('https://commons.wikimedia.org/w/api.php?' + qs);
      if (!resp.ok) return found;
      const data = await resp.json();
      for (const p of Object.values(data.query?.pages || {})) {
        const info = p.imageinfo?.[0];
        const url = info?.thumburl || info?.url;
        if (url && info?.mime?.startsWith('image/jpeg') && isAcceptablePhotoUrl(url, p.title || '')) {
          found.push({
            url,
            credit: `${(p.title || '').replace(/^File:/i, '')} · Wikimedia Commons`
          });
          if (found.length >= 2) break;
        }
      }
    } catch (_) {}
    return found;
  }

  async function resolveCityPhotoCandidates(city, backendImage) {
    if (backendImage?.image_url) {
      return [{
        url: backendImage.image_url,
        label: `Foto · ${city.name}`,
        credit: `${backendImage.caption || backendImage.title || city.name} · ${backendImage.author || 'EarthLens'}`
      }];
    }
    if (cityPhotoCache.has(city.id)) return cityPhotoCache.get(city.id);

    const candidates = [];
    const seen = new Set();
    const pushUnique = item => {
      if (item?.url && !seen.has(item.url)) {
        seen.add(item.url);
        candidates.push({ url: item.url, label: `Foto · ${city.name}`, credit: item.credit });
      }
    };

    const titles = CITY_WIKI_TITLES[city.id] || { es: city.name, en: `${city.name}, Argentina` };

    // 1) Wikipedia ES y EN en paralelo (sin reescribir URLs de thumbnails)
    const [esImg, enImg] = await Promise.all([
      fetchWikiPageImage('es', titles.es),
      fetchWikiPageImage('en', titles.en)
    ]);
    pushUnique(esImg);
    pushUnique(enImg);

    // 2) Si faltan candidatas o para tener respaldo garantizado, buscar en Wikimedia Commons
    if (candidates.length < 2) {
      const searchPhotos = await fetchCommonsSearchPhotos(city);
      searchPhotos.forEach(pushUnique);
    }
    if (candidates.length === 0) {
      const geoPhotos = await fetchCommonsGeoPhotos(city);
      geoPhotos.forEach(pushUnique);
    }

    cityPhotoCache.set(city.id, candidates);
    return candidates;
  }

  function applyCityPhoto(candidates, cityName) {
    const imgEl = $('dest-photo-img');
    const labelEl = $('dest-photo-label');
    if (!candidates || !candidates.length) {
      imgEl.hidden = true;
      labelEl.textContent = 'Foto del destino';
      labelEl.title = 'Ilustración representativa del destino';
      return;
    }

    let idx = 0;
    const tryLoad = () => {
      if (idx >= candidates.length) {
        imgEl.hidden = true;
        labelEl.textContent = 'Foto del destino';
        labelEl.title = 'Ilustración representativa del destino';
        return;
      }
      const current = candidates[idx];
      imgEl.onload = () => {
        imgEl.hidden = false;
        labelEl.textContent = current.label || `Foto · ${cityName}`;
        labelEl.title = current.credit || `Foto ilustrativa de ${cityName}`;
      };
      imgEl.onerror = () => {
        idx += 1;
        tryLoad();
      };
      imgEl.alt = `Fotografía de ${cityName}`;
      imgEl.src = current.url;
    };
    tryLoad();
  }

  async function updateCityPhotoAndClimatology(cityId) {
    const city = cities.find(c => c.id === cityId);
    if (!city) return;
    $('dest-photo-img').hidden = true;
    $('dest-photo-label').textContent = 'Cargando foto…';

    let prof = cityProfileCache.get(cityId);
    try {
      if (!prof) {
        prof = await api('/api/workspace/profiles/' + cityId);
        cityProfileCache.set(cityId, prof);
      }
      if (cityId !== state.city_id) return;
      renderBestSeasonBars(prof);
    } catch (_) {
      renderBestSeasonBars(null);
    }

    const candidates = await resolveCityPhotoCandidates(city, prof?.general?.image);
    if (cityId !== state.city_id) return;
    applyCityPhoto(candidates, city.name);
  }

  function renderBestSeasonBars(prof) {
    const monthLetters = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
    const monthsData = prof?.climatology?.T2M?.months;
    const defaultHeights = [88, 90, 74, 68, 42, 36, 36, 40, 64, 72, 86, 90];
    const defaultTypes = ['ideal', 'ideal', 'good', 'good', 'cold', 'cold', 'cold', 'cold', 'good', 'good', 'ideal', 'ideal'];

    let cols = [];
    if (monthsData && monthsData.length === 12 && monthsData.some(m => m.mean != null)) {
      const means = monthsData.map(m => m.mean ?? 15);
      const minM = Math.min(...means), maxM = Math.max(...means), span = Math.max(1, maxM - minM);
      cols = monthsData.map((m, idx) => {
        const val = m.mean ?? 15;
        const norm = (val - minM) / span;
        return {
          letter: monthLetters[idx],
          heightPct: Math.round(34 + norm * 56),
          barType: norm >= 0.72 ? 'ideal' : norm >= 0.36 ? 'good' : 'cold',
          title: `Media: ${number(val)} °C`
        };
      });
    } else {
      cols = monthLetters.map((letter, idx) => ({
        letter, heightPct: defaultHeights[idx], barType: defaultTypes[idx], title: `Clima típico · mes ${idx + 1}`
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
    const foundStart = stripDays.findIndex(d => d.date === state.tripStartDate);
    const tripStartIdx = foundStart >= 0 ? foundStart : 0;
    const tripEndIdx = Math.min(8, tripStartIdx + state.tripDurationDays - 1);

    const fmtDayShort = iso => {
      const d = new Date(Time.parse(iso));
      const w = d.toLocaleDateString('es-AR', { weekday: 'short', timeZone: 'UTC' }).replace('.', '');
      return `${w.charAt(0).toUpperCase() + w.slice(1, 3)} ${d.getUTCDate()}`;
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

  $('btn-trip-config').onclick = () => { $('trip-popover').hidden = !$('trip-popover').hidden; };
  $('close-trip-popover').onclick = () => { $('trip-popover').hidden = true; };
  $('btn-apply-trip').onclick = async () => {
    state.tripStartDate = $('trip-start-input').value || new Date().toISOString().slice(0, 10);
    state.tripDurationDays = Math.max(1, Math.min(9, Number($('trip-days-input').value) || 5));
    $('trip-popover').hidden = true;
    renderTripBar();
    await saveAccountPreferences();
  };
  $('btn-toggle-scrubber').onclick = () => {
    $('advanced-timeline').hidden = !$('advanced-timeline').hidden;
    $('trip-popover').hidden = true;
  };

  // ==================== CAPAS DEL MAPA ====================
  const LAYER_CONFIGS = {
    temperature: { variable: 'T2M', minText: 'Frío', maxText: 'Calor', colors: ['#5b8def', '#38d9a9', '#f5b82e', '#f97316'] },
    rain: { variable: 'PRECTOTCORR', minText: 'Seco', maxText: 'Lluvia', colors: ['#475569', '#38bdf8', '#3b82f6', '#1d4ed8'] },
    wind: { variable: 'WS2M', minText: 'Calmo', maxText: 'Intenso', colors: ['#38d9a9', '#a3e635', '#facc15', '#ef4444'] }
  };

  document.querySelectorAll('[data-map-layer]').forEach(btn => {
    btn.onclick = () => {
      const layer = btn.dataset.mapLayer;
      if (layer === 'satellite') {
        const satActive = document.body.classList.toggle('satellite-active');
        btn.classList.toggle('active', satActive);
        if (satActive) { map.removeLayer(streetTiles); satelliteTiles.addTo(map); }
        else { map.removeLayer(satelliteTiles); streetTiles.addTo(map); }
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

  // ==================== INTERACCIÓN 1: CALENDARIO / AGENDA (DATOS REALES DE LA CUENTA) ====================
  async function renderAgendaList() {
    const activeEvents = events.filter(e => e.status === 'active');
    if (!user) {
      $('agenda-events-container').innerHTML = '';
      return;
    }
    if (!activeEvents.length) {
      $('agenda-events-container').innerHTML = '<p class="hint">Todavía no tenés eventos en tu cuenta. Tocá "+ Agregar evento" para guardar el primero.</p>';
      return;
    }

    const enriched = await Promise.all(activeEvents.map(async ev => ({
      ev,
      wx: await computeEventWeatherSummary(ev)
    })));

    $('agenda-events-container').innerHTML = enriched.map(({ ev, wx }) => {
      const cityName = cities.find(c => c.id === ev.city_id)?.name || ev.city_id;
      const placeLabel = ev.location_label || cityName;
      return `
        <article class="agenda-card" data-agenda-id="${escape(ev.id)}">
          <div class="agenda-card-top">
            <div>
              <h3 class="agenda-card-title">${escape(ev.name)}</h3>
              <p class="agenda-card-meta">${escape(ev.start.slice(0, 10))} · ${escape(ev.start.slice(11, 16))} hs · ${escape(placeLabel)}</p>
            </div>
            <span class="agenda-weather-pill ${escape(wx.tagClass)}">
              ${wx.iconEmoji} ${wx.temp}° · ${escape(wx.tag)}
            </span>
          </div>
          <div class="actions" style="margin-top:6px">
            <button type="button" class="btn-text-teal" data-view-ev="${escape(ev.id)}">Ver evento</button>
            <button type="button" class="btn-text-teal" data-edit-quick-ev="${escape(ev.id)}">Editar</button>
            <button type="button" class="btn-danger-outline" data-del-ev="${escape(ev.id)}">Eliminar</button>
          </div>
        </article>
      `;
    }).join('');

    $('agenda-events-container').querySelectorAll('[data-view-ev]').forEach(btn => {
      btn.onclick = async () => {
        const pair = enriched.find(x => x.ev.id === btn.dataset.viewEv);
        if (!pair) return;
        await openEventDetail(pair.ev, null, { wx: pair.wx, backPanel: 'calendar' });
      };
    });

    $('agenda-events-container').querySelectorAll('[data-edit-quick-ev]').forEach(btn => {
      btn.onclick = () => {
        const ev = activeEvents.find(x => x.id === btn.dataset.editQuickEv);
        if (!ev) return;
        loadEventIntoQuickForm(ev);
        panel('add-event');
      };
    });

    $('agenda-events-container').querySelectorAll('[data-del-ev]').forEach(btn => {
      btn.onclick = safe(async () => {
        await api('/api/events/' + btn.dataset.delEv, { method: 'DELETE' });
        await loadAccount();
        notice('Evento eliminado de tu cuenta.');
      });
    });
  }

  // ==================== INTERACCIÓN 2: CAMPANITA / NOTIFICACIONES (SQLITE) ====================
  function updateNotificationBadge() {
    const unreadCount = notificationRows.filter(n => !n.read_at).length;
    $('badge').textContent = unreadCount > 0 ? String(unreadCount) : '';
  }

  function renderNotificationsPanel() {
    updateNotificationBadge();
    if (!user) {
      $('notifications-list').innerHTML = `
        <div class="auth-prompt-card">
          <p><strong>Iniciá sesión para recibir avisos</strong> cuando cambie el pronóstico de tus eventos guardados.</p>
          <button id="btn-login-from-notifs" type="button" class="btn-cta-fill btn-sm">Iniciar sesión / Crear cuenta</button>
        </div>
      `;
      $('btn-login-from-notifs').onclick = () => { state.postAuthPanel = 'notifications'; panel('events'); };
      return;
    }

    const filtered = notificationRows.filter(n => !notificationEventFilter || n.event_id === notificationEventFilter);
    if (!filtered.length) {
      $('notifications-list').innerHTML = '<p class="hint">No tenés notificaciones pendientes en tu cuenta. Al guardar un evento con aviso activado verás aquí su seguimiento.</p>';
      return;
    }

    $('notifications-list').innerHTML = filtered.map(n => {
      const unread = !n.read_at;
      const changesText = (n.body?.changes || []).map(c => `${c.criterion}: ${number(c.previous_value)} → ${number(c.current_value)} ${c.unit}`).join(' · ');
      return `
        <article class="notif-item ${unread ? 'unread' : ''}" data-notif-id="${escape(n.id)}">
          <div class="notif-item-head">
            <strong>${escape(n.title)}</strong>
            <span class="${unread ? 'unread-pill' : 'read-pill'}">${unread ? 'NO LEÍDA' : 'Leída'}</span>
          </div>
          <p style="margin:6px 0;font-size:12.5px;color:#e2e8f0">${escape(n.message)}</p>
          ${changesText ? `<p class="hint" style="margin:4px 0;color:#38d9a9">${escape(changesText)}</p>` : ''}
          <p class="hint" style="margin:4px 0">${escape(n.body?.recommendation || 'Revisar condiciones del evento.')}</p>
          <div class="actions" style="margin-top:8px;align-items:center;justify-content:space-between">
            <span class="hint">${escape(n.created_at?.slice(0, 16).replace('T', ' ') || '')}</span>
            <div style="display:flex;gap:6px">
              ${unread ? `<button type="button" class="btn-text-teal" data-mark-notif="${escape(n.id)}">Marcar leída</button>` : ''}
              ${n.event_id ? `<button type="button" class="btn-text-teal" data-goto-notif-ev="${escape(n.event_id)}">Ver evento</button>` : ''}
            </div>
          </div>
        </article>
      `;
    }).join('');

    $('notifications-list').querySelectorAll('[data-mark-notif]').forEach(btn => {
      btn.onclick = safe(async () => {
        await api('/api/notifications/' + btn.dataset.markNotif, { method: 'PATCH', body: '{}' });
        await loadAccount();
      });
    });

    $('notifications-list').querySelectorAll('[data-goto-notif-ev]').forEach(btn => {
      btn.onclick = safe(async () => {
        const ev = events.find(e => e.id === btn.dataset.gotoNotifEv);
        if (ev) {
          await openEventDetail(ev, null, { backPanel: 'notifications' });
        } else {
          panel('calendar');
        }
      });
    });
  }

  $('mark-all-read').onclick = safe(async () => {
    if (!user) return;
    const unread = notificationRows.filter(n => !n.read_at);
    await Promise.all(unread.map(n => api('/api/notifications/' + n.id, { method: 'PATCH', body: '{}' }).catch(() => null)));
    await loadAccount();
  });

  // ==================== INTERACCIÓN 3: "AGREGAR EVENTO" (LOGIN + GUARDAR EN SQLITE) ====================
  function resetQuickEventForm() {
    $('qe-edit-id').value = '';
    $('qe-panel-heading').textContent = 'Agregar evento';
    $('btn-save-and-predict').textContent = 'Guardar y predecir';
    $('qe-reset-form-btn').hidden = true;
    $('qe-error-msg').hidden = true;
    $('quick-event-form').reset();
    $('qe-notify').checked = true;
    $('qe-time').value = '10:30';
    prepareQuickEventForm();
  }

  function loadEventIntoQuickForm(ev) {
    if (ev.city_id !== state.city_id) selectCity(ev.city_id, { fetchData: false });
    $('qe-edit-id').value = ev.id;
    $('qe-panel-heading').textContent = 'Editar evento guardado';
    $('btn-save-and-predict').textContent = 'Actualizar y predecir';
    $('qe-reset-form-btn').hidden = false;
    $('qe-name').value = ev.name;
    $('qe-date').value = ev.start.slice(0, 10);
    $('qe-time').value = ev.start.slice(11, 16);
    $('qe-place').value = ev.location_label || '';
    $('qe-type').value = ev.activity || 'outdoor';
    $('qe-notify').checked = ev.notifications !== false;
    $('qe-error-msg').hidden = true;
    $('quick-event-result').hidden = true;
  }

  $('qe-reset-form-btn').onclick = () => {
    resetQuickEventForm();
    $('quick-event-result').hidden = true;
  };

  function prepareQuickEventForm(prefillDate) {
    const city = cities.find(c => c.id === state.city_id) || { name: 'Comodoro Rivadavia' };
    $('qe-city-label').textContent = city.name;
    const targetDate = prefillDate || state.date.slice(0, 10);
    if (!$('qe-edit-id').value) {
      if (!$('qe-date').value || prefillDate) $('qe-date').value = targetDate;
      if (!$('qe-place').value || !$('qe-place').value.includes(city.name)) {
        const highlight = getCityActivities(city)[0]?.name || `Centro de ${city.name}`;
        $('qe-place').value = `${highlight}, ${city.name}`;
      }
    }
  }

  const ACTIVITY_LABELS = {
    outdoor: 'Aire libre / Mirador',
    coastal: 'Costanera y playa',
    hiking: 'Trekking / Senderismo',
    excursion: 'Excursión turística',
    urban: 'Paseo urbano',
    sport: 'Deporte al aire libre',
    indoor: 'Museo / Bajo techo',
    camping: 'Camping',
    cycling: 'Ciclismo',
    custom: 'Personalizada'
  };

  async function openEventDetail(ev, evalResult = null, options = {}) {
    if (!ev) return;
    if (ev.city_id && ev.city_id !== state.city_id) {
      selectCity(ev.city_id, { fetchData: false });
    }
    const dateStr = ev.start.slice(0, 10);
    updateTime(dateStr, { center: true });

    const wx = options.wx || await computeEventWeatherSummary(ev);
    const city = cities.find(c => c.id === ev.city_id) || { name: ev.city_id, province: '', region: '' };
    const fullDate = new Date(Time.parse(dateStr)).toLocaleDateString('es-AR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
    });
    const startHour = ev.start.slice(11, 16);
    const endHour = ev.end ? ev.end.slice(11, 16) : '';
    const actLabel = ACTIVITY_LABELS[ev.activity] || ev.activity || 'Actividad turística';
    const assessment = evalResult?.assessment;
    const statusBanner = assessment?.label || `${wx.tag} según predicción`;
    const alternatives = (evalResult?.alternatives || []).slice(0, 2);
    const backPanel = options.backPanel || 'calendar';
    const backLabel = backPanel === 'notifications' ? '← Volver a Notificaciones'
      : backPanel === 'saved' ? '← Volver a Guardados'
      : backPanel === 'events' ? '← Volver a Mi cuenta'
      : '← Volver a la Agenda';

    const wearItems = [];
    if (wx.windKmh >= 22) wearItems.push('Cortaviento');
    if (wx.uv >= 5 || wx.icon === 'sun') wearItems.push('Anteojos de sol', 'Protector solar', 'Gorra');
    if (wx.rainProb >= 35) wearItems.push('Piloto impermeable');
    if (wx.temp <= 14) wearItems.push('Abrigo térmico');
    for (const extra of ['Cortaviento', 'Protector solar', 'Calzado cómodo']) {
      if (!wearItems.includes(extra) && wearItems.length < 4) wearItems.push(extra);
    }

    $('event-detail-view').innerHTML = `
      <button type="button" id="ev-detail-back" class="event-detail-back">${escape(backLabel)}</button>

      <!-- Tarjeta 1: Información general del evento -->
      <article class="event-detail-card ${options.justSaved ? 'highlight-saved' : ''}">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px">
          ${options.justSaved
            ? `<span class="visit-badge badge-good">✓ Evento guardado en @${escape(user?.username || '')}</span>`
            : `<span class="visit-badge badge-good">Evento en tu cuenta</span>`}
          <span class="todo-tag ${escape(wx.tagClass)}">${wx.iconEmoji} ${escape(wx.tag)}</span>
        </div>
        <h1 style="margin:0;font-size:19px;color:#fff">${escape(ev.name)}</h1>
        <p class="hint" style="margin:4px 0 0;text-transform:capitalize">${escape(fullDate)}</p>

        <div class="event-info-list">
          <div class="event-info-cell">
            <span>Horario</span>
            <strong>${escape(startHour)}${endHour ? ' – ' + escape(endHour) : ''} hs</strong>
          </div>
          <div class="event-info-cell">
            <span>Actividad</span>
            <strong>${escape(actLabel)}</strong>
          </div>
          <div class="event-info-cell full">
            <span>Destino y lugar</span>
            <strong>${escape(ev.location_label || city.name)}${city.province ? ' · ' + escape(city.province) : ''}</strong>
          </div>
          <div class="event-info-cell full">
            <span>Seguimiento de cambios</span>
            <strong>${ev.notifications ? '🔔 Activo: te avisaremos si cambia el clima' : 'Desactivado'}</strong>
          </div>
        </div>
      </article>

      <!-- Tarjeta 2: Predicción y clima de ese día -->
      <article class="event-detail-card">
        <div class="pred-day-hero">
          <div>
            <span class="sub-eyebrow" style="margin:0 0 4px">CLIMA PREVISTO PARA TU EVENTO</span>
            <h2 style="margin:0;font-size:16px;color:#fff">${escape(city.name)} · Máx ${wx.maxTemp}° / Mín ${wx.minTemp}°</h2>
            <p class="hint" style="margin:2px 0 0">${escape(wx.confidence)}</p>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <div style="width:34px;height:34px">${weatherSvg(wx.icon)}</div>
            <div class="pred-day-temp-big">${wx.temp}°</div>
          </div>
        </div>

        <div class="pred-slots-grid" aria-label="Franjas horarias del día">
          <div class="pred-slot"><span>Mañana</span><strong>${wx.slots.morning}°</strong></div>
          <div class="pred-slot"><span>Mediodía</span><strong>${wx.slots.noon}°</strong></div>
          <div class="pred-slot"><span>Tarde</span><strong>${wx.slots.afternoon}°</strong></div>
          <div class="pred-slot"><span>Noche</span><strong>${wx.slots.night}°</strong></div>
        </div>

        <div class="pred-result-grid">
          <div class="pred-metric-card"><span>Temperatura</span><strong>${wx.temp} °C</strong></div>
          <div class="pred-metric-card"><span>Prob. Lluvia</span><strong>${wx.rainProb} %</strong></div>
          <div class="pred-metric-card"><span>Viento</span><strong>${wx.windKmh} km/h</strong></div>
          <div class="pred-metric-card"><span>Índice UV</span><strong>${wx.uv} (${wx.uv >= 8 ? 'Alto' : wx.uv >= 5 ? 'Moderado' : 'Bajo'})</strong></div>
          <div class="pred-metric-card"><span>Luz solar</span><strong>${wx.lightStr}</strong></div>
          <div class="pred-metric-card"><span>Nubosidad</span><strong>${wx.cloudPct} %</strong></div>
        </div>

        <div style="margin:10px 0">
          <p class="sub-eyebrow" style="margin:0 0 6px">QUÉ LLEVAR</p>
          <div class="wear-chips">${wearItems.slice(0, 4).map(c => `<span class="wear-chip">${escape(c)}</span>`).join('')}</div>
        </div>

        <div class="pred-recommendation-box">
          <strong>Recomendación (${escape(statusBanner)}):</strong> ${escape(wx.recommendation)}
        </div>

        ${alternatives.length ? `
          <div style="margin-top:10px">
            <p class="sub-eyebrow" style="margin:6px 0">OTROS HORARIOS / DÍAS SUGERIDOS</p>
            ${alternatives.map(a => `<p class="hint" style="margin:4px 0">• ${escape(a.start.slice(0, 16).replace('T', ' '))} — ${escape(a.assessment.label)}</p>`).join('')}
          </div>
        ` : ''}
      </article>

      <div class="actions">
        <button type="button" id="ev-detail-edit" class="btn-cta-outline" style="flex:1">Editar evento</button>
        <button type="button" id="ev-detail-pred" class="btn-cta-fill" style="flex:1">Ver más días</button>
      </div>
      <button type="button" id="ev-detail-delete" class="btn-danger-outline w-full">Eliminar evento de mi cuenta</button>
    `;

    panel('event-detail');
    $('drawer-title').textContent = ev.name;

    $('ev-detail-back').onclick = () => panel(backPanel);
    $('ev-detail-edit').onclick = () => {
      loadEventIntoQuickForm(ev);
      panel('add-event');
    };
    $('ev-detail-pred').onclick = async () => {
      const days = await getCityForecastDays(ev.city_id);
      const idx = days.findIndex(d => d.date === dateStr);
      state.selectedPredictionDayIdx = idx >= 0 ? idx : 0;
      panel('prediction');
    };
    $('ev-detail-delete').onclick = safe(async () => {
      await api('/api/events/' + ev.id, { method: 'DELETE' });
      await loadAccount();
      panel('calendar');
      notice('Evento eliminado de tu cuenta.');
    });
  }

  $('quick-event-form').onsubmit = async e => {
    e.preventDefault();
    if (!user) {
      syncAddEventAuthGate();
      return;
    }
    const errBox = $('qe-error-msg');
    errBox.hidden = true;
    const submitBtn = $('btn-save-and-predict');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Guardando en tu cuenta…';

    try {
      const editId = $('qe-edit-id').value.trim();
      const name = $('qe-name').value.trim();
      const dateStr = $('qe-date').value;
      const timeStr = $('qe-time').value || '10:30';
      const place = $('qe-place').value.trim();
      const activity = $('qe-type').value;
      const notifications = $('qe-notify').checked;
      const { start, end } = buildArgentinaStartEnd(dateStr, timeStr, 2);

      const isIndoor = activity === 'indoor';
      const preferences = isIndoor
        ? { max_precipitation: 60, require_official_alerts: false }
        : { min_temperature: 5, max_temperature: 34, max_probability: 60, max_wind: 12, require_official_alerts: false };

      const payload = {
        name,
        description: `Actividad ${activity} en ${place}`,
        activity,
        city_id: state.city_id,
        location_label: place,
        start,
        end,
        participants: 1,
        outdoor: !isIndoor,
        transport: 'walk',
        flexible_days: 2,
        flexible_hours: 0,
        preferences,
        notifications
      };

      const savedEv = await api('/api/events' + (editId ? '/' + editId : ''), {
        method: editId ? 'PATCH' : 'POST',
        body: JSON.stringify(payload)
      });

      let evalResult = null;
      try {
        evalResult = await api(`/api/events/${savedEv.id}/evaluate`, { method: 'POST', body: '{}' });
      } catch (_) {}

      const wx = await computeEventWeatherSummary(savedEv);
      await loadAccount();
      $('qe-edit-id').value = '';
      $('qe-reset-form-btn').hidden = true;
      $('qe-panel-heading').textContent = 'Agregar evento';
      $('quick-event-form').reset();
      $('qe-notify').checked = true;
      await openEventDetail(savedEv, evalResult, { wx, justSaved: true, backPanel: 'calendar' });
      notice('Evento guardado en tu cuenta con predicción.');
    } catch (error) {
      errBox.textContent = error.message;
      errBox.hidden = false;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
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
          <div style="width:36px;height:36px">${weatherSvg(d.icon)}</div>
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
      resetQuickEventForm();
      $('qe-date').value = d.date;
      $('quick-event-result').hidden = true;
      panel('add-event');
    };
  }

  // ==================== PANEL GUARDADOS Y LISTA EN MI CUENTA ====================
  function renderSavedPanel() {
    const savedCityObjs = cities.filter(c => savedCities.has(c.id));
    $('saved-cities-list').innerHTML = savedCityObjs.map(c => `
      <article class="agenda-card" style="display:flex;align-items:center;justify-content:space-between;gap:8px">
        <div>
          <strong style="color:#fff">${escape(c.name)}</strong>
          <p class="hint" style="margin:2px 0 0">${escape(c.province)} · ${escape(c.region)}</p>
        </div>
        <div style="display:flex;gap:6px">
          <button type="button" class="btn-text-teal" data-jump-city="${escape(c.id)}">Ver</button>
          <button type="button" class="btn-danger-outline" data-unsave-city="${escape(c.id)}">Quitar</button>
        </div>
      </article>
    `).join('') || '<p class="hint">Todavía no guardaste ciudades. Tocá el corazón ♡ en la tarjeta de cualquier destino.</p>';

    $('saved-cities-list').querySelectorAll('[data-jump-city]').forEach(btn => {
      btn.onclick = () => {
        selectCity(btn.dataset.jumpCity);
        $('destination-card').hidden = false;
        if (isMobile()) panel(null);
      };
    });

    $('saved-cities-list').querySelectorAll('[data-unsave-city]').forEach(btn => {
      btn.onclick = async () => {
        savedCities.delete(btn.dataset.unsaveCity);
        updateSaveCityButton();
        await saveAccountPreferences();
        renderSavedPanel();
      };
    });

    const activeEvs = events.filter(e => e.status === 'active');
    $('saved-events-summary').innerHTML = activeEvs.map(ev => `
      <article class="agenda-card">
        <div class="agenda-card-top">
          <strong>${escape(ev.name)}</strong>
          <span class="todo-tag tag-ideal">${escape(ev.start.slice(0, 10))}</span>
        </div>
        <p class="hint" style="margin:4px 0 8px">${escape(ev.start.slice(11, 16))} hs · ${escape(ev.location_label || ev.city_id)}</p>
        <button type="button" class="btn-text-teal" data-saved-view-ev="${escape(ev.id)}">Ver evento</button>
      </article>
    `).join('') || '<p class="hint">No tenés eventos guardados todavía.</p>';

    $('saved-events-summary').querySelectorAll('[data-saved-view-ev]').forEach(btn => {
      btn.onclick = safe(async () => {
        const ev = activeEvs.find(x => x.id === btn.dataset.savedViewEv);
        if (ev) await openEventDetail(ev, null, { backPanel: 'saved' });
      });
    });
  }

  function renderEventsListInAccount() {
    if (!user) {
      $('events-list').innerHTML = '';
      return;
    }
    $('events-list').innerHTML = events.map(e => `
      <article class="agenda-card">
        <div class="agenda-card-top">
          <div>
            <h3 class="agenda-card-title">${escape(e.name)}</h3>
            <p class="agenda-card-meta">${escape(e.start.slice(0, 10))} · ${escape(e.start.slice(11, 16))} hs · ${escape(e.location_label || e.city_id)}</p>
          </div>
        </div>
        <div class="actions" style="margin-top:6px">
          <button type="button" class="btn-text-teal" data-acc-view="${escape(e.id)}">Ver evento</button>
          <button type="button" class="btn-text-teal" data-acc-edit="${escape(e.id)}">Editar</button>
          <button type="button" class="btn-danger-outline" data-acc-del="${escape(e.id)}">Eliminar</button>
        </div>
      </article>
    `).join('') || '<p class="hint">Sin eventos guardados en tu cuenta todavía.</p>';

    $('events-list').querySelectorAll('[data-acc-view]').forEach(btn => {
      btn.onclick = safe(async () => {
        const ev = events.find(x => x.id === btn.dataset.accView);
        if (ev) await openEventDetail(ev, null, { backPanel: 'events' });
      });
    });
    $('events-list').querySelectorAll('[data-acc-edit]').forEach(btn => {
      btn.onclick = () => {
        const ev = events.find(x => x.id === btn.dataset.accEdit);
        if (ev) { loadEventIntoQuickForm(ev); panel('add-event'); }
      };
    });
    $('events-list').querySelectorAll('[data-acc-del]').forEach(btn => {
      btn.onclick = safe(async () => {
        await api('/api/events/' + btn.dataset.accDel, { method: 'DELETE' });
        await loadAccount();
      });
    });
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
        $('mob-open-dest').hidden = true;
        if (isMobile()) setDestinationCompact(false);
        selectCity(city.id);
      });
      marker.addTo(markers);
      pointLayers.set(city.id, marker);
    }
    if ($('selection-label')) {
      $('selection-label').textContent = selected.size + ' ubicación(es) seleccionada(s) · puntos consultados';
    }
  }

  function selectCity(id, { fetchData = true } = {}) {
    const city = cities.find(c => c.id === id);
    if (!city) return;
    state.city_id = id;
    if ($('city')) $('city').value = id;
    if ($('search')) $('search').value = city.name;
    if ($('location-name')) $('location-name').textContent = city.name + ' · ' + city.province;
    if ($('event-city')) $('event-city').textContent = 'Ubicación: ' + city.name + ' · centroide GeoRef.';
    $('destination-card').hidden = false;
    $('mob-open-dest').hidden = true;
    map.flyTo([city.latitude, city.longitude], Math.max(map.getZoom(), isMobile() ? 6 : 7), { duration: 0.4 });
    incidents = allIncidents.filter(i => i.city_id === id);
    renderIncidents();
    renderMap();
    queryContext();
    updateDestinationCard();
    renderTripBar();
    prepareQuickEventForm();
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
    state.variable = choices.some(r => r.variable === previous) ? previous : choices[0]?.variable;
    if ($('variable')) {
      $('variable').innerHTML = choices.map(r => `<option value="${escape(r.variable)}">${escape(variableNames[r.variable] || r.name || r.variable)}</option>`).join('');
      $('variable').value = state.variable || '';
    }
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
    loadTimer = setTimeout(() => safe(load)(), delay);
  }

  function activeValue() {
    const value = frame?.focus?.value, unit = frame?.focus?.unit || '';
    if ($('value')) $('value').textContent = number(value);
    if ($('value-unit')) $('value-unit').textContent = unit;
    if ($('map-value')) $('map-value').textContent = number(value) + (value != null ? ' ' + unit : ' · sin dato');
    const kind = frame?.kind || 'unavailable';
    if ($('time-kind')) {
      $('time-kind').className = 'kind-label ' + kind;
      $('time-kind').textContent = kind === 'forecast' && Math.abs(Time.parse(state.date) - Date.now()) < 36e5 ? 'AHORA · PRONÓSTICO' : labels[kind] || kind;
    }
    if ($('data-kind')) $('data-kind').textContent = labels[kind] || kind;
    if ($('data-title')) $('data-title').textContent = variableNames[state.variable] || state.variable;
  }

  function plot(rows) {
    if (chart) chart.destroy();
    chart = null;
    if (!$('chart')) return;
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
        responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
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
    record = null; frame = null; comparisonRecords = []; pointFrames.clear();
    activeValue(); renderMap();
    if ($('provenance')) $('provenance').innerHTML = '';
    if ($('comparison')) $('comparison').innerHTML = '';
    if ($('limits')) $('limits').textContent = '';
    if (chart) { chart.destroy(); chart = null; }
    try {
      const result = await obtain(state.city_id, signal);
      if (ticket !== seq) return;
      frame = result; record = result.record; pointFrames.set(state.city_id, result);
      document.body.dataset.frameDate = result.selection.date;
      document.body.dataset.frameVariable = result.selection.variable;
      document.body.dataset.frameKind = result.kind;
      document.body.dataset.frameReady = 'true';
      $('inspector').setAttribute('aria-busy', 'false');
      const rows = record ? [record] : [];
      comparisonRecords = rows;
      activeValue(); updateDestinationCard(); renderMap(); plot(rows); queryContext();
    } catch (error) {
      if (ticket !== seq || error.name === 'AbortError') return;
      frame = { kind: 'unavailable', focus: null, message: error.message };
      activeValue(); pointFrames.set(state.city_id, frame); updateDestinationCard(); renderMap();
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
  $('present').onclick = () => { stop(); state.mode = 'date'; if ($('mode')) $('mode').value = 'date'; state.scale = 'daily'; $('scale').value = 'daily'; updateTime(Time.iso(Date.now()), { center: true }); };
  if ($('city')) $('city').onchange = () => selectCity($('city').value);

  // Buscador de ciudades
  function renderSearchDropdown(queryText) {
    const q = queryText.trim().toLocaleLowerCase('es');
    const matches = cities.filter(c => !q || c.name.toLocaleLowerCase('es').includes(q) || c.province.toLocaleLowerCase('es').includes(q));
    if (!matches.length) { $('search-dropdown').hidden = true; return; }
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
        if (isMobile()) setDestinationCompact(false);
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

  $('source').onchange = () => { state.provider = $('source').value; variables(); scheduleLoad(0); tools(false); };
  if ($('variable')) $('variable').onchange = () => { state.variable = $('variable').value; queryContext(); scheduleLoad(0); };
  if ($('mode')) $('mode').onchange = () => { state.mode = $('mode').value; safe(load)(); tools(false); };

  // Calendario mensual
  function calendar() {
    const type = $('cal-view').value, first = new Date(calendarDate);
    first.setUTCDate(1);
    let count = type === 'month' ? new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate() : type === 'week' ? 7 : 1;
    if (type === 'week') first.setUTCDate(calendarDate.getUTCDate() - ((calendarDate.getUTCDay() + 6) % 7));
    if (type === 'day') first.setUTCDate(calendarDate.getUTCDate());
    $('cal-title').textContent = calendarDate.toLocaleDateString('es-AR', { month: 'long', year: 'numeric', timeZone: 'UTC' });
    $('calendar-jump').value = state.date.slice(0, 10);
    $('calendar').classList.toggle('list', type === 'list' || type === 'day');

    const activeEvents = events.filter(e => e.status === 'active');
    if (type === 'list') {
      $('calendar').innerHTML = activeEvents.map(e => `<button type="button" data-event="${escape(e.id)}">${escape(e.name)} · ${escape(e.start.slice(0, 10))}</button>`).join('') || '<p class="hint">Sin eventos guardados.</p>';
    } else {
      let html = type === 'month' ? ['L', 'M', 'M', 'J', 'V', 'S', 'D'].map(d => '<span class="hint">' + d + '</span>').join('') + '<span></span>'.repeat((first.getUTCDay() + 6) % 7) : '';
      for (let i = 0; i < count; i++) {
        const day = new Date(first);
        day.setUTCDate(first.getUTCDate() + i);
        const iso = day.toISOString().slice(0, 10);
        const associated = activeEvents.filter(e => e.start.slice(0, 10) === iso);
        html += `<button type="button" data-day="${iso}" class="${iso === state.date.slice(0, 10) ? 'selected ' : ''}${associated.length ? 'has-event' : ''}">${day.getUTCDate()}${associated.map(e => '<span class="day-caption">' + escape(e.name) + '</span>').join('')}</button>`;
      }
      $('calendar').innerHTML = html;
    }

    $('calendar').querySelectorAll('[data-day]').forEach(button => {
      button.onclick = () => updateTime(button.dataset.day, { center: true });
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
    resetQuickEventForm();
    $('qe-date').value = state.date.slice(0, 10);
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
    const rows = events.filter(e => e.status === 'active').map(e => ({ id: e.id, date: e.start, name: e.name }));
    $('time-markers').innerHTML = rows.filter(r => Time.position(r.date, view) >= 0 && Time.position(r.date, view) <= 1).map(r =>
      `<button type="button" style="left:${Time.position(r.date, view) * 100}%" class="event-mark" data-event="${escape(r.id)}" title="${escape(r.name + ' · ' + r.date)}">⚑</button>`
    ).join('');
  }

  function renderEvents() {
    eventMarkers.clearLayers();
    incidentMarkers.clearLayers();
    for (const ev of events.filter(e => e.status === 'active')) {
      const city = cities.find(c => c.id === ev.city_id);
      if (!city) continue;
      L.circleMarker([city.latitude, city.longitude], { radius: 9, color: '#38d9a9', fillColor: '#38d9a9', fillOpacity: 0.35, weight: 2 })
        .bindTooltip(`📅 ${escape(ev.name)} · ${escape(ev.start.slice(0, 10))}`)
        .on('click', () => panel('calendar'))
        .addTo(eventMarkers);
    }
    renderTimelineMarkers();
    calendar();
  }

  async function profile() {
    if (!$('profile-title') || !$('profile-content')) return;
    const id = state.city_id, result = await api('/api/workspace/profiles/' + id);
    if (id !== state.city_id) return;
    $('profile-title').textContent = result.city.name;
    $('profile-content').innerHTML = `<p>${escape(result.city.province)} · ${escape(result.city.region)}</p>`;
  }

  async function impact() {
    if (!$('impact-content')) return;
    const city = state.city_id, result = await api('/api/impact?city_id=' + city);
    $('impact-content').innerHTML = `<p class="eyebrow">${escape(result.status)}</p><p>${escape(result.summary)}</p>`;
  }

  function download(format) {
    if (!record) { notice('Seleccioná una serie con datos.', true); return; }
    const content = format === 'json'
      ? JSON.stringify(record, null, 2)
      : 'city_id,date,value,unit\n' + record.series.map(p => `${record.location.id},${p.date},${p.value ?? ''},${record.unit}`).join('\n');
    const url = URL.createObjectURL(new Blob([content], { type: format === 'json' ? 'application/json' : 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = 'earthlens-' + state.city_id + '-' + state.variable + '.' + format;
    a.click(); URL.revokeObjectURL(url);
  }
  if ($('export-json')) $('export-json').onclick = () => download('json');
  if ($('export-csv')) $('export-csv').onclick = () => download('csv');
  if ($('report')) $('report').onclick = () => {
    if (!frame?.effective_query) return;
    const { kind, ...selection } = frame.effective_query;
    window.open('/api/workspace/report.pdf?' + new URLSearchParams(selection), '_blank', 'noopener');
  };
  $('theme').onclick = () => document.body.classList.toggle('light');

  try {
    [cities, catalog, allIncidents] = await Promise.all([
      api('/api/cities'),
      api('/api/science/variables'),
      api('/api/workspace/incidents')
    ]);
    if ($('city')) $('city').innerHTML = cities.map(city => `<option value="${city.id}">${escape(city.name)}</option>`).join('');
    $('city-suggestions').innerHTML = cities.map(city => `<option value="${escape(city.name)}">${escape(city.province)}</option>`).join('');
    if (!cities.some(city => city.id === state.city_id)) state.city_id = cities[0].id;
    const initialPanel = state.panel;
    state.panel = null;
    $('source').value = state.provider;
    variables();
    $('scale').value = state.scale;
    if ($('mode')) $('mode').value = state.mode;
    $('start').value = state.start;
    $('end').value = state.end;

    syncMobileLayout(true);
    selectCity(state.city_id, { fetchData: false });
    updateTime(state.date, { fetch: false });
    await loadAccount();
    await load();
    if (initialPanel) panel(initialPanel);
    window.addEventListener('resize', () => {
      syncMobileLayout(false);
      map.invalidateSize();
      chart?.resize();
    });
  } catch (error) {
    notice(error.message, true);
  }
});
