/**
 * EarthLens — Módulo 05 de Earth Time Machine: Proyección y Probabilidades de Anomalías
 * Archivo: static/js/time-machine/tm_forecast.js
 *
 * - Consume el bloque `forecast` de POST /api/time-machine (services/prediction/forecast.py).
 * - Al cambiar el intervalo futuro o el umbral personalizado recalcula con POST /api/forecast
 *   enviando solo la serie anual ya cargada (sin volver a descargar mapa ni red nacional).
 * - Renderiza: abanico de proyección (IP 95 % / IC 95 %), probabilidades por evento,
 *   probabilidad anual por año, conclusiones automáticas y detalle año a año.
 * - Todo el texto proveniente del servidor se inserta con textContent (sin innerHTML).
 */
(function () {
  'use strict';

  const MAX_HORIZON = 30;

  const LEVEL_CLASS = Object.freeze({
    info: 'is-info',
    success: 'is-success',
    warning: 'is-warning',
    danger: 'is-danger'
  });

  const CONFIDENCE_CLASS = Object.freeze({
    alta: 'is-success',
    media: 'is-warning',
    baja: 'is-danger'
  });

  const TABLE_EVENTS = Object.freeze([
    'high_moderate',
    'high_extreme',
    'record_high',
    'low_moderate',
    'low_extreme',
    'record_low',
    'above_mean'
  ]);

  let timeMachineData = null;
  let forecast = null;
  let customVariable = null;
  let fanChart = null;
  let probChart = null;
  let reqController = null;
  let reqSeq = 0;
  let initialized = false;

  // ----------------------------------------------------------------------------------
  // Utilidades DOM
  // ----------------------------------------------------------------------------------
  function $(id) {
    return document.getElementById(id);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function setText(id, text) {
    const node = $(id);
    if (node) node.textContent = text;
  }

  function fmt(value, digits = 2) {
    if(value===null || value===undefined || value==='') return '--';
    const num = Number(value);
    return Number.isFinite(num) ? num.toFixed(digits) : '--';
  }

  function pct(p) {
    const num = Number(p);
    if (!Number.isFinite(num)) return '--';
    if (num >= 0.995) return '> 99 %';
    if (num < 0.005) return '< 1 %';
    return `${Math.round(num * 100)} %`;
  }

  function isVisible() {
    const win = $('winForecast');
    return !!win && !win.classList.contains('d-none');
  }

  function unitOf() {
    return forecast?.unit || timeMachineData?.display_unit || '';
  }

  function lastHistoricalYear() {
    const tl = timeMachineData?.timeline || [];
    return tl.length ? Number(tl[tl.length - 1].year) : 2024;
  }

  // ----------------------------------------------------------------------------------
  // Parámetros del intervalo futuro y umbral personalizado
  // ----------------------------------------------------------------------------------
  function readWindowInputs() {
    const last = lastHistoricalYear();
    const maxYear = last + MAX_HORIZON;
    let start = parseInt($('tmFcStart')?.value, 10);
    let end = parseInt($('tmFcEnd')?.value, 10);
    if (!Number.isFinite(start)) start = last + 1;
    if (!Number.isFinite(end)) end = start + 9;
    start = Math.max(last + 1, Math.min(maxYear, start));
    end = Math.max(start, Math.min(maxYear, end));
    return { start, end };
  }

  function writeWindowInputs(start, end) {
    const last = lastHistoricalYear();
    const sIn = $('tmFcStart');
    const eIn = $('tmFcEnd');
    if (sIn) {
      sIn.min = last + 1;
      sIn.max = last + MAX_HORIZON;
      sIn.value = start;
    }
    if (eIn) {
      eIn.min = last + 1;
      eIn.max = last + MAX_HORIZON;
      eIn.value = end;
    }
  }

  function readCustomThreshold() {
    const raw = $('tmFcCustomValue')?.value;
    if (raw === undefined || raw === null || String(raw).trim() === '') return null;
    const num = Number(raw);
    return Number.isFinite(num) ? num : null;
  }

  /**
   * Parámetros que time_machine.js agrega a POST /api/time-machine para conservar
   * el intervalo elegido por el usuario al cambiar de ciudad, variable o cuadrante.
   */
  function getRequestParams(variable) {
    if (!timeMachineData) return {};
    const { start, end } = readWindowInputs();
    const params = { forecast_start: start, forecast_end: end };
    const custom = readCustomThreshold();
    if (custom !== null && customVariable && variable === customVariable) {
      params.custom_threshold = custom;
      params.custom_direction = $('tmFcCustomDir')?.value || 'above';
    }
    return params;
  }

  // ----------------------------------------------------------------------------------
  // Recalcular solo la proyección (POST /api/forecast)
  // ----------------------------------------------------------------------------------
  async function recompute() {
    if (!timeMachineData || !Array.isArray(timeMachineData.timeline)) return;
    const { start, end } = readWindowInputs();
    writeWindowInputs(start, end);

    const custom = readCustomThreshold();
    customVariable = custom !== null ? timeMachineData.variable : null;

    const body = {
      variable: timeMachineData.variable,
      city_id: timeMachineData.location.id,
      start_year: timeMachineData.period.start_year,
      end_year: timeMachineData.period.end_year,
      forecast_start: start,
      forecast_end: end
    };
    if (custom !== null) {
      body.custom_threshold = custom;
      body.custom_direction = $('tmFcCustomDir')?.value || 'above';
    }

    if (reqController) reqController.abort();
    reqController = new AbortController();
    const mySeq = ++reqSeq;
    setStatus('Recalculando…', true);

    try {
      const res = await fetch('/api/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: reqController.signal
      });
      const json = await res.json();
      if (mySeq !== reqSeq) return;
      if (!res.ok || json.status!=='ok' || !json.data?.available) {
        forecast=null;renderUnavailable(json.error?.message || 'No se pudo calcular la proyeccion.');
        setStatus(json.error?.message || 'No se pudo calcular la proyeccion.', false, true);
        return;
      }
      forecast = json.data;
      if (timeMachineData) timeMachineData.forecast = json.data;
      setStatus('', false);
      renderAll();
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      if (mySeq !== reqSeq) return;
      setStatus('Servidor no disponible: la proyección requiere el backend estadístico.', false, true);
    }
  }

  function setStatus(text, busy, isError = false) {
    const node = $('tmFcStatus');
    if (!node) return;
    node.textContent = text || '';
    node.classList.toggle('d-none', !text);
    node.classList.toggle('is-error', !!isError);
    node.classList.toggle('is-busy', !!busy);
  }

  // ----------------------------------------------------------------------------------
  // Renderizado
  // ----------------------------------------------------------------------------------
  function renderAll() {
    renderHeader();
    renderProbabilityTable();
    renderConclusions();
    renderYearTable();
    updateRailBadge();
    if (isVisible()) renderCharts();
  }

  function renderUnavailable(message) {
    setText('tmFcConfidence', 'Confianza: --');
    setText('tmFcHeadline', message);
    ['tmFcProbTableBody', 'tmFcConclusions', 'tmFcYearTableBody'].forEach((id) => {
      const node = $(id);
      if (node) node.replaceChildren();
    });
    updateRailBadge();
    if (fanChart) {
      fanChart.destroy();
      fanChart = null;
    }
    if (probChart) {
      probChart.destroy();
      probChart = null;
    }
  }

  function renderHeader() {
    const conf = forecast.confidence || '--';
    const pill = $('tmFcConfidence');
    if (pill) {
      pill.textContent = 'Exploratoria: validacion pendiente';
      pill.classList.remove('is-success', 'is-warning', 'is-danger');

    }
    setText('tmFcHeadline', forecast.headline || '');
    const m = forecast.model || {};
    const unit = unitOf();
    setText(
      'tmFcModelLine',
      `Modelo: OLS ${m.change_per_decade >= 0 ? '+' : ''}${fmt(m.change_per_decade, 3)} ${unit}/década · ` +
        `p = ${fmt(m.p_value, 4)} · R² = ${fmt(m.r_squared, 3)} · σ residual = ${fmt(m.residual_std, 3)} ${unit} · ` +
        `r1 = ${fmt(m.lag1_autocorrelation, 2)} · Historia ${forecast.history?.start_year}–${forecast.history?.end_year}`
    );
    const w = forecast.window || {};
    setText('tmFcWindowLabel', w.start_year === w.end_year ? `${w.start_year}` : `${w.start_year}–${w.end_year}`);
    setText('tmFcDisclaimer', forecast.disclaimer || '');
    setText('tmFcCustomUnit', unitOf());
    writeWindowInputs(w.start_year, w.end_year);
  }

  function probabilityBar(p, side) {
    const wrap = el('div', 'tm-fc-bar');
    const fill = el('div', `tm-fc-bar-fill ${side === 'low' ? 'is-cool' : side === 'neutral' ? 'is-neutral' : 'is-warm'}`);
    fill.style.width = `${Math.max(0, Math.min(100, Number(p) * 100)).toFixed(1)}%`;
    wrap.appendChild(fill);
    return wrap;
  }

  function sideOf(key) {
    if (key.startsWith('low') || key === 'record_low') return 'low';
    if (key === 'above_mean' || key === 'custom') return 'neutral';
    return 'high';
  }

  function renderProbabilityTable() {
    const body = $('tmFcProbTableBody');
    if (!body) return;
    body.replaceChildren();
    const labels = forecast.event_labels || {};
    const unit = unitOf();
    const keys = [...TABLE_EVENTS];
    if (forecast.summary?.custom) keys.push('custom');

    keys.forEach((key) => {
      const s = forecast.summary?.[key];
      if (!s) return;
      const tr = el('tr');

      const tdLabel = el('td');
      tdLabel.appendChild(el('div', 'tm-fc-event-name', labels[key] || key));
      const thr = key.startsWith('record') ? forecast.thresholds?.[key]?.value : s.threshold;
      const thrYear = key.startsWith('record') ? ` (${forecast.thresholds?.[key]?.year})` : '';
      tdLabel.appendChild(el('div', 'tm-fc-event-thr', `Umbral: ${fmt(thr)} ${unit}${thrYear}`));
      tr.appendChild(tdLabel);

      const tdProb = el('td');
      tdProb.appendChild(el('div', 'tm-fc-prob-val', pct(s.prob_at_least_one)));
      tdProb.appendChild(probabilityBar(s.prob_at_least_one, sideOf(key)));
      tr.appendChild(tdProb);

      tr.appendChild(el('td', 'font-monospace', `${fmt(s.expected_years, 1)} / ${fmt(s.baseline_expected_years, 1)}`));

      const rr = s.risk_ratio;
      const rrCell = el('td', 'font-monospace');
      const rrPill = el('span', 'tm-fc-rr', rr === null || rr === undefined ? '—' : `×${fmt(rr, rr >= 10 ? 0 : 1)}`);
      if (rr !== null && rr !== undefined) {
        if (rr >= 2) rrPill.classList.add('is-danger');
        else if (rr >= 1.25) rrPill.classList.add('is-warning');
        else if (rr <= 0.75) rrPill.classList.add('is-success');
      }
      rrCell.appendChild(rrPill);
      tr.appendChild(rrCell);
      body.appendChild(tr);
    });
  }

  function renderConclusions() {
    const box = $('tmFcConclusions');
    if (!box) return;
    box.replaceChildren();
    (forecast.conclusions || []).slice(1).forEach((c) => {
      const card = el('div', `tm-fc-conclusion ${LEVEL_CLASS[c.level] || 'is-info'}`);
      card.appendChild(el('div', 'tm-fc-conclusion-title', c.title));
      card.appendChild(el('p', 'tm-fc-conclusion-text mb-0', c.text));
      box.appendChild(card);
    });
  }

  function renderYearTable() {
    const body = $('tmFcYearTableBody');
    const headCustom = $('tmFcYearHeadCustom');
    if (!body) return;
    body.replaceChildren();
    const hasCustom = !!forecast.summary?.custom;
    if (headCustom) headCustom.classList.toggle('d-none', !hasCustom);

    (forecast.years || []).forEach((y) => {
      const tr = el('tr');
      tr.appendChild(el('td', 'fw-semibold', y.year));
      tr.appendChild(el('td', 'font-monospace', fmt(y.expected)));
      tr.appendChild(el('td', 'font-monospace', `${fmt(y.pi_low)} – ${fmt(y.pi_high)}`));
      tr.appendChild(el('td', 'font-monospace tm-accent-warm', pct(y.probabilities.high_moderate)));
      tr.appendChild(el('td', 'font-monospace tm-accent-cool', pct(y.probabilities.low_moderate)));
      tr.appendChild(el('td', 'font-monospace', pct(y.probabilities.record_high)));
      tr.appendChild(el('td', 'font-monospace', pct(y.probabilities.record_low)));
      const tdCustom = el('td', 'font-monospace', hasCustom ? pct(y.probabilities.custom) : '');
      if (!hasCustom) tdCustom.classList.add('d-none');
      tr.appendChild(tdCustom);
      body.appendChild(tr);
    });
  }

  function updateRailBadge() {
    const badge = $('tmDockForecastAlert');
    if (!badge) return;
    const n = forecast ? (forecast.conclusions || []).filter((c) => c.level === 'danger').length : 0;
    badge.textContent = String(n);
    badge.classList.toggle('d-none', n === 0);
  }

  function renderCharts() {
    if (!forecast || typeof Chart === 'undefined') return;
    renderFanChart();
    renderProbChart();
  }

  function renderFanChart() {
    const canvas = $('tmFcFanChart');
    if (!canvas) return;
    if (fanChart) fanChart.destroy();

    const tl = timeMachineData?.timeline || [];
    const fy = forecast.years || [];
    const unit = unitOf();
    const nh = tl.length;
    const pad = (arr, before, after) => [...Array(before).fill(null), ...arr, ...Array(after).fill(null)];

    // Si hay años sin proyectar entre el fin del registro y el inicio de la ventana, se rellenan
    // únicamente con la recta para mantener el eje continuo.
    const gapYears = [];
    const lastYear = nh ? tl[nh - 1].year : null;
    if (lastYear !== null && fy.length && fy[0].year > lastYear + 1) {
      for (let yr = lastYear + 1; yr < fy[0].year; yr++) gapYears.push(yr);
    }
    const slope = Number(forecast.model?.slope || 0);
    const intercept = Number(forecast.model?.intercept || 0);
    const allLabels = [...tl.map((p) => p.year), ...gapYears, ...fy.map((p) => p.year)];
    const ng = gapYears.length;

    const observed = pad(tl.map((p) => p.value), 0, ng + fy.length);
    const histTrend = pad(tl.map((p) => intercept + slope * p.year), 0, ng + fy.length);
    const projected = [
      ...Array(Math.max(0, nh - 1)).fill(null),
      nh ? intercept + slope * tl[nh - 1].year : null,
      ...gapYears.map((yr) => intercept + slope * yr),
      ...fy.map((p) => p.expected)
    ];
    const piHigh = pad(fy.map((p) => p.pi_high), nh + ng, 0);
    const piLow = pad(fy.map((p) => p.pi_low), nh + ng, 0);
    const ciHigh = pad(fy.map((p) => p.ci_high), nh + ng, 0);
    const ciLow = pad(fy.map((p) => p.ci_low), nh + ng, 0);
    const thr = forecast.thresholds || {};
    const constant = (v) => allLabels.map(() => v);

    const datasets = [
      {
        label: 'IP 95 % (rango probable de un año)',
        data: piHigh,
        borderColor: 'rgba(181, 83, 60, 0.0)',
        backgroundColor: 'rgba(181, 83, 60, 0.13)',
        pointRadius: 0,
        fill: '+1',
        order: 5
      },
      {
        label: '_piLow',
        data: piLow,
        borderColor: 'rgba(181, 83, 60, 0.0)',
        pointRadius: 0,
        fill: false,
        order: 5
      },
      {
        label: 'IC 95 % de la tendencia',
        data: ciHigh,
        borderColor: 'rgba(181, 83, 60, 0.0)',
        backgroundColor: 'rgba(181, 83, 60, 0.26)',
        pointRadius: 0,
        fill: '+1',
        order: 4
      },
      {
        label: '_ciLow',
        data: ciLow,
        borderColor: 'rgba(181, 83, 60, 0.0)',
        pointRadius: 0,
        fill: false,
        order: 4
      },
      {
        label: `Observado (${unit})`,
        data: observed,
        borderColor: '#2b5c8f',
        backgroundColor: '#2b5c8f',
        pointRadius: 2.5,
        borderWidth: 2,
        tension: 0.2,
        order: 1
      },
      {
        label: 'Tendencia OLS',
        data: histTrend,
        borderColor: '#64748b',
        borderDash: [4, 3],
        borderWidth: 1.5,
        pointRadius: 0,
        order: 2
      },
      {
        label: 'Proyección esperada',
        data: projected,
        borderColor: '#b5533c',
        backgroundColor: '#b5533c',
        borderWidth: 2.4,
        borderDash: [7, 4],
        pointRadius: projected.map((v, i) => (i >= nh + ng ? 2.5 : 0)),
        order: 1
      },
      {
        label: 'Umbral anomalía +1.5σ',
        data: constant(thr.high_moderate),
        borderColor: 'rgba(200, 100, 50, 0.75)',
        borderWidth: 1,
        borderDash: [2, 3],
        pointRadius: 0,
        order: 6
      },
      {
        label: 'Umbral anomalía −1.5σ',
        data: constant(thr.low_moderate),
        borderColor: 'rgba(43, 92, 143, 0.75)',
        borderWidth: 1,
        borderDash: [2, 3],
        pointRadius: 0,
        order: 6
      }
    ];

    fanChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels: allLabels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              boxWidth: 10,
              font: { size: 10 },
              filter: (item) => !String(item.text).startsWith('_')
            }
          },
          tooltip: {
            filter: (item) => !String(item.dataset.label).startsWith('_') && item.raw !== null,
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw)} ${unit}`
            }
          }
        },
        scales: {
          x: { grid: { color: 'rgba(203, 213, 225, 0.5)' }, ticks: { maxTicksLimit: 14 } },
          y: {
            title: { display: true, text: `${timeMachineData?.variable_name || ''} (${unit})` },
            grid: { color: 'rgba(203, 213, 225, 0.5)' }
          }
        }
      }
    });
  }

  function renderProbChart() {
    const canvas = $('tmFcProbChart');
    if (!canvas) return;
    if (probChart) probChart.destroy();
    const fy = forecast.years || [];
    const labels = forecast.event_labels || {};
    const toPct = (key) => fy.map((y) => Number(((y.probabilities[key] || 0) * 100).toFixed(1)));

    const datasets = [
      {
        type: 'bar',
        label: labels.high_moderate || 'Anomalía alta',
        data: toPct('high_moderate'),
        backgroundColor: 'rgba(200, 100, 50, 0.75)'
      },
      {
        type: 'bar',
        label: labels.low_moderate || 'Anomalía baja',
        data: toPct('low_moderate'),
        backgroundColor: 'rgba(43, 92, 143, 0.75)'
      },
      {
        type: 'line',
        label: 'Nuevo récord máximo',
        data: toPct('record_high'),
        borderColor: '#9e2a2b',
        backgroundColor: '#9e2a2b',
        pointRadius: 2,
        borderWidth: 1.6,
        tension: 0.25
      }
    ];
    if (forecast.summary?.custom) {
      datasets.push({
        type: 'line',
        label: labels.custom || 'Umbral personalizado',
        data: toPct('custom'),
        borderColor: '#7c3aed',
        backgroundColor: '#7c3aed',
        borderDash: [5, 3],
        pointRadius: 2,
        borderWidth: 1.6
      });
    }

    probChart = new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: { labels: fy.map((y) => y.year), datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 10, font: { size: 10 } } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} %` } }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            title: { display: true, text: 'Probabilidad anual (%)' },
            grid: { color: 'rgba(203, 213, 225, 0.5)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // ----------------------------------------------------------------------------------
  // Exportación CSV de la proyección
  // ----------------------------------------------------------------------------------
  function exportCSV() {
    if (!forecast || !forecast.years) return;
    const unit = unitOf();
    const hasCustom = !!forecast.summary?.custom;
    const header = [
      'year',
      `expected_${unit}`,
      'pi95_low',
      'pi95_high',
      'ci95_low',
      'ci95_high',
      'z_expected',
      'p_high_moderate',
      'p_high_extreme',
      'p_low_moderate',
      'p_low_extreme',
      'p_record_high',
      'p_record_low',
      'p_above_mean'
    ];
    if (hasCustom) header.push('p_custom');
    const rows = forecast.years.map((y) => {
      const p = y.probabilities;
      const row = [
        y.year, y.expected, y.pi_low, y.pi_high, y.ci_low, y.ci_high, y.z_expected,
        p.high_moderate, p.high_extreme, p.low_moderate, p.low_extreme, p.record_high, p.record_low, p.above_mean
      ];
      if (hasCustom) row.push(p.custom);
      return row.join(',');
    });
    const meta = [
      `# EarthLens · Earth Time Machine · Proyección ${forecast.variable}`,
      `# Ubicación: ${(timeMachineData?.location?.name || '').replace(/[\r\n]/g, ' ')}`,
      `# Historia ${forecast.history.start_year}-${forecast.history.end_year} · Confianza ${forecast.confidence}`,
      `# ${forecast.method}`
    ];
    const blob = new Blob([[...meta, header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `earthlens_proyeccion_${forecast.variable}_${forecast.window.start_year}_${forecast.window.end_year}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ----------------------------------------------------------------------------------
  // Eventos de la ventana
  // ----------------------------------------------------------------------------------
  function bindEvents() {
    if (initialized) return;
    initialized = true;

    $('btnFcApply')?.addEventListener('click', recompute);

    document.querySelectorAll('.tm-fc-quick').forEach((btn) => {
      btn.addEventListener('click', () => {
        const years = Number(btn.dataset.horizon) || 10;
        const last = lastHistoricalYear();
        writeWindowInputs(last + 1, Math.min(last + MAX_HORIZON, last + years));
        document.querySelectorAll('.tm-fc-quick').forEach((b) => b.classList.toggle('active', b === btn));
        recompute();
      });
    });

    ['tmFcStart', 'tmFcEnd', 'tmFcCustomValue'].forEach((id) => {
      $(id)?.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          recompute();
        }
      });
    });

    $('btnFcClearCustom')?.addEventListener('click', () => {
      const input = $('tmFcCustomValue');
      if (input) input.value = '';
      recompute();
    });

    $('btnFcExport')?.addEventListener('click', exportCSV);
  }

  // ----------------------------------------------------------------------------------
  // API pública usada por time_machine.js
  // ----------------------------------------------------------------------------------
  function setData(data) {
    bindEvents();
    reqController?.abort();reqSeq++;
    if(!data){timeMachineData=null;forecast=null;renderUnavailable('Sin datos historicos disponibles.');return;}
    const previousVariable = timeMachineData?.variable;
    timeMachineData = data;

    if (previousVariable && previousVariable !== data.variable) {
      const input = $('tmFcCustomValue');
      if (input) input.value = '';
      customVariable = null;
    }

    if (data && data.forecast && data.forecast.available) {
      forecast = data.forecast;
      setStatus('', false);
      renderAll();
      return;
    }

    if(data.forecast && !data.forecast.available){forecast=null;renderUnavailable(data.forecast.reason || 'Historico insuficiente para extrapolar.');return;}
    // Respuesta sin bloque predictivo (p. ej. datos de respaldo del cliente): se solicita al backend.
    forecast = null;
    renderUnavailable('Calculando proyección…');
    recompute();
  }

  function render() {
    bindEvents();
    if (forecast) renderCharts();
  }

  window.EarthLensForecast = Object.freeze({
    setData,
    render,
    getRequestParams,
    recompute
  });
})();
