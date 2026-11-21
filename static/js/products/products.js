/* Presentación del contrato común. Los cálculos científicos pertenecen al motor. */
window.EarthLensProducts = (() => {
  const escape = value => EarthLensAPI.escape(value).replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = (value, digits = 5) => finite(value)
    ? new Intl.NumberFormat('es-AR', { maximumFractionDigits: digits }).format(value) : '—';
  const period = value => value ? `${value.start_year}–${value.end_year}` : '—';
  const date = value => {
    const parsed = new Date(value);
    return value && !Number.isNaN(parsed.valueOf())
      ? `${parsed.toLocaleString('es-AR', { timeZone: 'UTC' })} UTC` : '—';
  };
  const directions = { increasing: '↑ Ascendente', decreasing: '↓ Descendente', stable: 'Sin dirección clara' };
  const evidenceNames = {
    provisional_signal: 'Señal nominal provisional', provisional_no_signal: 'Sin señal nominal',
    provisional_inconsistent: 'Requiere revisión', insufficient_data: 'Cobertura insuficiente',
    error: 'Error de análisis', confirmed: 'Confirmado'
  };
  const evidenceName = row => evidenceNames[row?.evidence?.status] || 'Evidencia no disponible';
  function badge(row) {
    const state = row?.evidence?.status;
    return `<span class="evidence-badge ${state === 'provisional_signal' ? 'is-signal' : state === 'error' ? 'is-error' : ''}">${escape(evidenceName(row))}</span>`;
  }
  function group(row) {
    const type = row.indicator?.group;
    return `<span class="indicator-group ${type === 'extreme' ? 'is-extreme' : ''}">${type === 'primary' ? 'Principal' : type === 'extreme' ? 'Extremo mensual' : 'Indicador adicional'}</span>`;
  }
  function metrics(row) {
    const stats = row.statistics || {}, annual = row.coverage?.annual || {};
    const interval = stats.confidence_interval_95;
    const unit = escape(row.unit || 'unidad no disponible');
    const p = stats.p_value === 0 ? '&lt;0,00001 (redondeado por el motor)' : number(stats.p_value);
    const entries = [
      ['Pendiente', `${number(stats.slope)} <small>${unit}/año</small>`],
      ['Cambio por década', `${number(stats.change_per_decade)} <small>${unit}/década</small>`],
      ['IC 95% de la pendiente', `${Array.isArray(interval) ? `${number(interval[0])} a ${number(interval[1])}` : '—'} <small>${unit}/año</small>`],
      ['p-valor nominal', p], ['Dirección estimada', escape(directions[row.direction] || 'No disponible')],
      ['Cobertura anual', `${number(annual.valid_years, 0)}/${number(annual.requested_years, 0)} años · ${number(finite(annual.coverage_ratio) ? annual.coverage_ratio * 100 : null, 1)}%`]
    ];
    return `<dl class="product-metrics">${entries.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join('')}</dl>`;
  }
  function source(row) {
    const monthly = row.coverage?.monthly || {};
    const originals = row.source?.metadata?.header?.sources || [];
    return `<p class="profile-source mb-2">${escape(row.source?.provider || 'Fuente no disponible')} · ${escape(row.variable)} · ${escape(row.unit || '—')}
      ${originals.length ? `· fuentes originales: ${escape(originals.join(', '))}` : ''}<br>
      ${escape(period(row.period))} · meses disponibles: ${number(monthly.valid_count, 0)}/${number(monthly.expected_count, 0)}.
      Obtenido: ${escape(date(row.provenance?.fetched_at))}.</p>`;
  }
  function href(value) {
    try {
      const url = new URL(value, location.origin);
      if (url.origin === location.origin && ['/explorer', '/results', '/compare', '/fingerprint'].includes(url.pathname)) {
        return escape(url.pathname + url.search);
      }
    } catch (_) { /* Un enlace inválido nunca se utiliza como destino. */ }
    return '#';
  }
  function status(element, message, kind = '') {
    element.className = `product-status mb-3 ${kind ? `is-${kind}` : ''}`;
    element.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    element.textContent = message;
  }
  function latestRequest() {
    let sequence = 0, controller;
    return () => {
      controller?.abort();
      controller = new AbortController();
      const current = ++sequence;
      return { signal: controller.signal, current: () => sequence === current };
    };
  }
  function history(canvas, rows) {
    if (!window.Chart) {
      canvas.parentElement.innerHTML = '<p class="chart-unavailable">No se pudo cargar la biblioteca de gráficos. Las estadísticas y los enlaces a los datos siguen disponibles.</p>';
      return null;
    }
    const years = [...new Set(rows.flatMap(row => {
      const start = row.period?.start_year, end = row.period?.end_year;
      return Number.isInteger(start) && Number.isInteger(end)
        ? Array.from({ length: end - start + 1 }, (_, index) => start + index) : (row.series || []).map(point => point.year);
    }))].sort((a, b) => a - b);
    const colors = ['#0d6efd', '#b45309'];
    return new Chart(canvas, {
      type: 'line',
      data: { labels: years, datasets: rows.map((row, index) => {
        const values = new Map((row.series || []).map(point => [point.year, point.value]));
        return { label: row.location.name, data: years.map(year => finite(values.get(year)) ? values.get(year) : null),
          borderColor: colors[index % colors.length], backgroundColor: colors[index % colors.length],
          borderWidth: 2, pointRadius: 2, tension: 0, spanGaps: false };
      }) },
      options: { responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: rows.length > 1, position: 'bottom' },
          tooltip: { callbacks: { label: item => `${item.dataset.label}: ${number(item.parsed.y)} ${rows[0].unit || ''}` } } },
        scales: { x: { ticks: { maxTicksLimit: 6 }, grid: { display: false }, title: { display: true, text: 'Año' } },
          y: { title: { display: true, text: rows[0].unit || 'Unidad no disponible' }, ticks: { maxTicksLimit: 5 } } }
      }
    });
  }
  function methodology(profile) {
    const method = profile.methodology || {};
    return `<div class="product-method"><p><strong>${escape(profile.city.name)}</strong> · ${escape(period(profile.period))}.
      Regresión ${escape(method.regression || 'no disponible')} sobre medias anuales de meses válidos, sin ponderar por días.
      Mínimo ${number(method.min_months_per_year, 0)} meses por año y ${number(method.min_valid_years, 0)} años;
      cobertura anual mínima ${number(finite(method.min_coverage_ratio) ? method.min_coverage_ratio * 100 : null, 0)}%.</p>
      <p>Los gráficos muestran las series anuales entregadas por el motor, no observaciones mensuales ni estaciones locales.
      La precipitación es una tasa media en mm/day, sin acumulación anual. Los extremos son medias de extremos mensuales.
      No se imputan faltantes. Las cifras conservan el redondeo que entrega el motor; no se reconstruye precisión.</p>
      <p>Versión metodológica: <code>${escape(method.version)}</code>. Análisis: ${escape(date(profile.generated_at))}.
      Sin puntuaciones ambientales ni normalización radial. Las comparaciones son descriptivas.</p>
      <details><summary>Decisiones científicas pendientes</summary><ul>${(method.pending_dependencies || []).map(item => `<li>${escape(item.description)}</li>`).join('')}</ul></details></div>`;
  }
  return { escape, finite, number, period, date, evidenceName, badge, group, metrics, source, href, status, latestRequest, history, methodology };
})();
