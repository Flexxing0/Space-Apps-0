/* Perfiles y comparación descriptiva, sin normalización ni motor estadístico en JS. */
(() => {
  const P = EarthLensProducts, $ = id => document.getElementById(id);
  const nextRequest = P.latestRequest(), params = new URLSearchParams(location.search);
  let charts = [], catalog;
  const key = row => JSON.stringify([row.source?.provider, row.source?.dataset, row.variable, row.indicator.id]);
  function clear() {
    charts.forEach(chart => chart?.destroy());
    charts = [];
    $('fingerprint-cards').replaceChildren();
    $('fingerprint-output').hidden = true;
  }
  function compatible(profiles) {
    return profiles.length === 2 && !!profiles[0].comparison?.key && profiles[0].comparison.key === profiles[1].comparison?.key
      && profiles.every(profile => profile.comparison.all_indicators_available && profile.results.every(row => row.data_status === 'valid' && !(row.evidence?.issues || []).length));
  }
  function render(profiles) {
    const comparable = compatible(profiles), secondary = profiles.length === 2;
    $('fingerprint-title').textContent = profiles.map(profile => profile.city.name).join(' y ');
    $('fingerprint-location').textContent = profiles.map(profile => `${profile.city.province} · ${profile.city.region} · ${P.number(profile.city.latitude, 3)}, ${P.number(profile.city.longitude, 3)}`).join(' / ');
    $('fingerprint-period').textContent = profiles.map(profile => P.period(profile.period)).filter((item, index, items) => items.indexOf(item) === index).join(' / ');
    $('fingerprint-summary').textContent = profiles.map(profile => `${profile.city.name}: ${profile.summary.variables} indicadores · ${profile.summary.data_complete ? 'datos completos' : 'revisar cobertura/errores'}`).join(' | ');
    const notice = $('fingerprint-comparison-status');
    notice.hidden = !secondary;
    notice.classList.toggle('is-incompatible', secondary && !comparable);
    notice.textContent = comparable
      ? 'Perfiles compatibles en período, indicador, unidad, fuente y cobertura. La comparación es descriptiva: no prueba diferencias estadísticas entre ciudades.'
      : 'Los perfiles no cumplen todos los criterios de compatibilidad. Se muestran por separado, sin superponer series ni calcular diferencias.';
    const indicators = new Map();
    profiles.forEach((profile, index) => profile.results.forEach(row => {
      if (!indicators.has(key(row))) indicators.set(key(row), []);
      indicators.get(key(row))[index] = row;
    }));
    const chartJobs = [];
    $('fingerprint-cards').innerHTML = [...indicators.values()].map((entries, index) => {
      const rows = entries.filter(Boolean), row = rows[0];
      const stats = profiles.map((profile, cityIndex) => {
        const item = entries[cityIndex];
        return `<section class="profile-city-stats ${cityIndex ? 'is-secondary' : ''}"><h4>${P.escape(profile.city.name)}</h4>
          ${item ? `${P.badge(item)}${item.error ? `<p class="product-help mt-2">${P.escape(item.error.message)}</p>` : ''}${P.metrics(item)}${P.source(item)}
            <p class="d-flex flex-wrap gap-3 small"><a href="${P.href(item.links?.explorer)}">Abrir en Explorador</a><a href="${P.href(item.links?.results)}">Ver Resultados →</a></p>` : '<p class="product-help">Indicador no disponible en este perfil.</p>'}</section>`;
      }).join('');
      let graphs = '';
      const graphGroups = comparable ? [rows] : rows.map(item => [item]);
      graphGroups.forEach((items, graphIndex) => {
        const id = `fingerprint-chart-${index}-${graphIndex}`;
        if (!items.some(item => (item.series || []).some(point => P.finite(point.value)))) {
          graphs += '<p class="chart-unavailable">No hay una serie anual válida para graficar este indicador.</p>';
          return;
        }
        const label = `${row.indicator.name} · ${items.map(item => item.location.name).join(' y ')} · ${row.unit || 'sin unidad'}`;
        graphs += `${!comparable && secondary ? `<p class="product-help mb-0">${P.escape(items[0].location.name)}</p>` : ''}<div class="history-chart"><canvas id="${id}" role="img" aria-label="${P.escape(label)}"></canvas></div>`;
        chartJobs.push({ id, rows: items });
      });
      const comparisonQuery = new URLSearchParams({ city_id_a: profiles[0].city.id, city_id_b: profiles[1]?.city.id || '', variable: row.variable,
        start_year: row.period.start_year, end_year: row.period.end_year });
      return `<article class="el-card fingerprint-card" data-variable="${P.escape(row.variable)}"><div class="indicator-heading"><div class="d-flex justify-content-between align-items-start gap-2"><h3>${P.escape(row.indicator.name)}</h3>${P.group(row)}</div><span class="product-help">${P.escape(row.variable)} · ${P.escape(row.unit || 'Unidad no disponible')}</span></div>
        ${stats}${graphs}<p class="product-help mb-0">Historia anual · medias de meses válidos, sin imputación.</p>
        ${comparable ? `<a class="small d-inline-block mt-2" href="/compare?${P.escape(comparisonQuery)}">Abrir este indicador en el Comparador →</a>` : ''}</article>`;
    }).join('');
    $('fingerprint-methodology').innerHTML = profiles.map(P.methodology).join('<hr>');
    $('fingerprint-output').hidden = false;
    chartJobs.forEach(job => charts.push(P.history($(job.id), job.rows)));
    const hasErrors = profiles.some(profile => profile.status === 'error');
    P.status($('fingerprint-status'), hasErrors ? 'El perfil contiene errores de análisis. Revisá el estado de cada indicador.'
      : `${profiles.length === 2 ? 'Perfiles cargados' : 'Perfil cargado'} · resultados provisionales, sin descubrimientos confirmados.`, hasErrors ? 'error' : 'success');
  }
  async function load() {
    const task = nextRequest();
    const first = $('fingerprint-city').value, second = $('fingerprint-compare-city').value;
    clear();
    $('fingerprint-retry').hidden = true;
    $('fingerprint-output').setAttribute('aria-busy', 'true');
    $('fingerprint-period').textContent = '—';
    P.status($('fingerprint-status'), 'Consultando perfiles y series históricas…', 'loading');
    try {
      if (!catalog.some(city => city.id === first) || (second && !catalog.some(city => city.id === second))) throw new Error('Seleccioná una ciudad del catálogo argentino.');
      if (first === second) throw new Error('Elegí dos ciudades distintas para comparar.');
      const selected = [first, second].filter(Boolean);
      const profiles = await Promise.all(selected.map(async id => (await EarthLensAPI.request(`/api/fingerprint/${encodeURIComponent(id)}`, null, { signal: task.signal })).data));
      if (!task.current()) return;
      render(profiles);
      const query = new URLSearchParams({ city_id: first });
      if (second) query.set('city_id_b', second);
      history.replaceState(null, '', `${location.pathname}?${query}`);
    } catch (error) {
      if (!task.current()) return;
      clear();
      P.status($('fingerprint-status'), `No se pudo mostrar el perfil: ${error.message}`, 'error');
      $('fingerprint-retry').hidden = false;
    } finally {
      if (task.current()) $('fingerprint-output').setAttribute('aria-busy', 'false');
    }
  }
  async function start() {
    try {
      catalog = await EarthLensAPI.cities();
      const first = params.get('city_id') || 'comodoro-rivadavia', second = params.get('city_id_b') || '';
      EarthLensAPI.fillCities($('fingerprint-city'), catalog, first);
      EarthLensAPI.fillCities($('fingerprint-compare-city'), catalog, second);
      $('fingerprint-compare-city').prepend(new Option('Sin comparación', ''));
      $('fingerprint-compare-city').value = second;
      await load();
    } catch (error) {
      clear();
      P.status($('fingerprint-status'), `No se pudo cargar el catálogo: ${error.message}`, 'error');
      $('fingerprint-retry').hidden = false;
    }
  }
  $('fingerprint-form').addEventListener('submit', event => event.preventDefault());
  $('fingerprint-form').addEventListener('change', () => catalog && load());
  $('fingerprint-retry').addEventListener('click', () => catalog ? load() : start());
  start();
})();
