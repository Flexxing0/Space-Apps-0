/* Vista del estudio persistido: filtrar nunca cambia su familia estadística. */
(() => {
  const P = EarthLensProducts, $ = id => document.getElementById(id);
  const form = $('radar-filters'), initial = new URLSearchParams(location.search);
  const fields = ['province', 'region', 'variable', 'direction', 'evidence_status'];
  const defaults = { variable: 'T2M' };
  const nextRequest = P.latestRequest();
  let study, initialized = false, map, markers, bounds;
  function filters() { return Object.fromEntries(fields.map(key => [key, form.elements[key].value])); }
  function initialize(data) {
    for (const [field, values, label] of [
      ['province', data.cities.map(city => city.province), 'Todas las provincias'],
      ['region', data.cities.map(city => city.region), 'Todas las regiones']
    ]) {
      form.elements[field].innerHTML = `<option value="">${label}</option>` + [...new Set(values)].sort((a, b) => a.localeCompare(b, 'es')).map(value => `<option value="${P.escape(value)}">${P.escape(value)}</option>`).join('');
    }
    const tests = data.family.tests || [];
    const indicators = new Map(tests.map(test => [test.variable, test.indicator]));
    form.elements.variable.innerHTML = '<option value="">Todos los indicadores (sin mezclar unidades)</option>' + [...indicators].map(([code, indicator]) => `<option value="${P.escape(code)}">${P.escape(code)} · ${P.escape(indicator.name)}</option>`).join('');
    for (const key of fields) {
      const value = initial.has(key) ? initial.get(key) : (defaults[key] || '');
      // Alias válidos del API se conservan aunque no sean la etiqueta del catálogo.
      if (value && ![...form.elements[key].options].some(option => option.value === value)) {
        form.elements[key].add(new Option(value, value));
      }
      form.elements[key].value = value;
    }
    initialized = true;
  }
  function initMap(cities) {
    if (!window.L) {
      $('radar-map-message').hidden = false;
      $('radar-map-message').textContent = 'No se pudo cargar el mapa. Consultá las mismas ciudades y tendencias en el listado.';
      return;
    }
    if (map) return;
    map = L.map('radar-map', { scrollWheelZoom: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 17
    }).addTo(map);
    bounds = L.latLngBounds(cities.map(city => [city.latitude, city.longitude]));
    map.fitBounds(bounds, { padding: [25, 25] });
    markers = L.layerGroup().addTo(map);
  }
  function renderMap(cities, results) {
    initMap(cities);
    if (!markers) return;
    markers.clearLayers();
    cities.forEach(city => {
      const rows = results.filter(row => row.location.id === city.id);
      const row = rows[0], state = row?.evidence?.status;
      let color = '#94a3b8';
      if (rows.length > 1) color = '#0891b2';
      else if (state === 'provisional_signal') color = row.direction === 'increasing' ? '#b91c1c' : '#0369a1';
      else if (state === 'provisional_no_signal') color = '#64748b';
      else if (rows.length) color = '#b45309';
      const marker = L.circleMarker([city.latitude, city.longitude], {
        radius: rows.length ? 7 : 5, color, fillColor: color, fillOpacity: rows.length ? .85 : .05, weight: 2
      }).addTo(markers);
      marker.bindTooltip(`${city.name} · ${rows.length} resultado(s)`);
      marker.bindPopup(`<div class="radar-city-popup"><strong>${P.escape(city.name)}</strong><br>${P.escape(city.province)} · ${P.escape(city.region)}
        <br>${P.number(city.latitude, 3)}, ${P.number(city.longitude, 3)}
        ${rows.length ? `<ul>${rows.map(item => `<li>${P.escape(item.variable)}: ${P.escape(P.evidenceName(item))}<br><a href="${P.href(item.links?.results)}">Investigar tendencia</a></li>`).join('')}</ul>` : '<p>Sin resultados para los filtros actuales.</p>'}
        <a href="/fingerprint?city_id=${encodeURIComponent(city.id)}">Ver perfil ambiental</a></div>`);
    });
  }
  function renderCards() {
    if (!study) return;
    const oneVariable = !!form.elements.variable.value;
    for (const option of $('radar-sort').options) if (option.value.startsWith('change_')) option.disabled = !oneVariable;
    if (!oneVariable && $('radar-sort').value.startsWith('change_')) $('radar-sort').value = 'city';
    $('radar-sort-help').hidden = oneVariable;
    const order = $('radar-sort').value;
    const rows = [...study.results].sort((a, b) => {
      const tie = a.location.name.localeCompare(b.location.name, 'es') || a.variable.localeCompare(b.variable);
      if (order === 'variable') return a.indicator.name.localeCompare(b.indicator.name, 'es') || tie;
      if (['p_value', 'change_desc', 'change_asc'].includes(order)) {
        const key = order === 'p_value' ? 'p_value' : 'change_per_decade';
        const x = a.statistics?.[key], y = b.statistics?.[key];
        if (!P.finite(x)) return P.finite(y) ? 1 : tie;
        if (!P.finite(y)) return -1;
        return (x - y) * (order === 'change_desc' ? -1 : 1) || tie;
      }
      return tie;
    });
    $('radar-results').innerHTML = rows.map(row => `<article class="el-card result-card" data-city-id="${P.escape(row.location.id)}" data-variable="${P.escape(row.variable)}">
      <div class="result-card-header"><div><h3>${P.escape(row.location.name)}</h3><span class="product-help">${P.escape(row.location.province)} · ${P.escape(row.location.region)}</span></div>${P.group(row)}</div>
      <p class="indicator-label">${P.escape(row.variable)} · ${P.escape(row.indicator.name)}</p>${P.badge(row)}
      ${row.error ? `<p class="product-help mt-2">${P.escape(row.error.message)}</p>` : ''}${P.metrics(row)}${P.source(row)}
      <div class="result-card-footer"><a class="btn btn-sm btn-primary" href="${P.href(row.links?.results)}">Investigar tendencia →</a><a class="small" href="/fingerprint?city_id=${encodeURIComponent(row.location.id)}">Ver perfil</a></div></article>`).join('');
    $('radar-empty').hidden = rows.length !== 0;
    $('radar-list-description').textContent = `${rows.length} resultados visibles. Las magnitudes conservan sus unidades originales.`;
  }
  function render(data) {
    study = data;
    $('radar-city-count').textContent = data.summary.cities;
    $('radar-test-count').textContent = data.summary.tests;
    $('radar-signal-count').textContent = data.summary.provisional_signals;
    $('radar-visible-count').textContent = data.view.count;
    $('radar-period').textContent = `${P.period(data.period)} · familia sin cambios`;
    $('radar-study-details').innerHTML = `<p>Período: ${P.escape(P.period(data.period))}. ${P.number(data.summary.computed, 0)} análisis calculados;
      ${P.number(data.summary.confirmed_discoveries, 0)} descubrimientos confirmados. Las ${P.number(data.family.planned_tests, 0)} pruebas pertenecen al estudio completo.</p>
      <p>Estudio: <code>${P.escape(data.study_id)}</code>.<br>Ejecutado: ${P.escape(P.date(data.generated_at))}.<br>
      Método: <code>${P.escape(data.methodology.version)}</code>. Regresión ${P.escape(data.methodology.regression)} sobre medias anuales de meses válidos.
      Mínimo ${P.number(data.methodology.min_months_per_year, 0)} meses/año. Sin imputación y sin ajuste por comparaciones múltiples.</p>
      <p>NASA POWER, datos de grilla. ${P.number(data.summary.cache_hit_cities, 0)} ciudades del estudio se obtuvieron desde caché.
      La precipitación sigue siendo tasa media (mm/day), no acumulación. Los extremos son medias de extremos mensuales.
      Los filtros no recalculan el estudio. <a href="/about">Metodología y límites</a>.</p>`;
    renderMap(data.cities, data.results);
    renderCards();
  }
  async function load() {
    const task = nextRequest();
    $('radar-retry').hidden = true;
    $('radar-empty').hidden = true;
    $('radar-results').replaceChildren();
    $('radar-results-panel').setAttribute('aria-busy', 'true');
    $('radar-visible-count').textContent = '—';
    if (study) renderMap(study.cities, []);
    study = null;
    P.status($('radar-status'), 'Consultando el estudio persistido…', 'loading');
    const values = initialized ? filters() : Object.fromEntries(fields.map(key => [key, initial.has(key) ? initial.get(key) : defaults[key] || '']));
    const query = new URLSearchParams(Object.entries(values).filter(([, value]) => value));
    try {
      const { data } = await EarthLensAPI.request(`/api/radar?${query}`, null, { signal: task.signal });
      if (!task.current()) return;
      if (!initialized) initialize(data);
      render(data);
      const shared = new URLSearchParams(Object.entries(values).filter(([key, value]) => value || key === 'variable'));
      history.replaceState(null, '', `${location.pathname}?${shared}`);
      P.status($('radar-status'), `${data.view.count} resultados visibles · estudio provisional ${P.period(data.period)}.`, 'success');
    } catch (error) {
      if (!task.current()) return;
      study = null;
      $('radar-results').replaceChildren();
      $('radar-visible-count').textContent = '—';
      for (const id of ['radar-city-count', 'radar-test-count', 'radar-signal-count', 'radar-period']) $(id).textContent = '—';
      $('radar-study-details').textContent = 'El estudio no está disponible. Reintentá la consulta.';
      P.status($('radar-status'), `No se pudo cargar el estudio: ${error.message}`, 'error');
      $('radar-retry').hidden = false;
    } finally {
      if (task.current()) $('radar-results-panel').setAttribute('aria-busy', 'false');
    }
  }
  function reset() {
    fields.forEach(key => initial.delete(key));
    for (const key of fields) form.elements[key].value = defaults[key] || '';
    load();
  }
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('change', load);
  $('radar-sort').addEventListener('change', renderCards);
  $('radar-reset').addEventListener('click', reset);
  $('radar-empty-reset').addEventListener('click', reset);
  $('radar-retry').addEventListener('click', load);
  $('radar-map-reset').addEventListener('click', () => map?.fitBounds(bounds, { padding: [25, 25] }));
  load();
})();
