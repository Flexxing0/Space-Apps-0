/* Contrato único: mismo origen, ciudades verificadas y errores sin datos inventados. */
window.EarthLensAPI = (() => {
  let catalog;
  async function request(url, body, options = {}) {
    const response = await fetch(url, {
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      signal: options.signal,
      ...(body ? { method: 'POST', body: JSON.stringify(body) } : {})
    });
    const result = await response.json();
    if (!response.ok || result.status !== 'ok') {
      throw new Error(result.error?.message || `No se pudo completar la consulta (${response.status}).`);
    }
    return result;
  }
  async function cities() {
    if (!catalog) catalog = request('/api/cities').then(result => result.data).catch(error => { catalog = null; throw error; });
    return catalog;
  }
  function fillCities(select, list, selected) {
    select.replaceChildren(...list.map(city => {
      const option = document.createElement('option');
      option.value = city.id;
      option.textContent = `${city.name}, ${city.province}`;
      return option;
    }));
    select.value = selected;
  }
  async function analyze(params) {
    const result = await request('/api/analyze', {
      city_id: params.city_id || params.id,
      variable: params.variable || 'T2M',
      start_year: Number(params.start_year ?? 2000), end_year: Number(params.end_year ?? 2024)
    });
    return result.data;
  }
  async function compare(params) { return (await request('/api/compare', params)).data; }
  function showError(target, error) {
    if (target) {
      target.classList.add('alert', 'alert-danger');
      target.textContent = `No se pudo completar la consulta: ${error.message}`;
    }
  }
  function escape(text) {
    const node = document.createElement('span');
    node.textContent = String(text ?? '');
    return node.innerHTML;
  }
  function evidence(data) {
    const source = data.provenance || {};
    return `<details class="small mt-3"><summary>Fuentes, cobertura y método</summary>
      <p>NASA POWER · ${escape(data.unit)} · ${escape(data.period?.start_year)}–${escape(data.period?.end_year)}.
      Origen: ${escape(source.origin)}. Obtenido: ${escape(source.fetched_at)}.
      Años válidos: ${escape(data.completeness?.valid_years)} / ${escape(data.completeness?.requested_years)}.</p>
      <p>${escape(data.method?.regression)}. Mínimo ${escape(data.method?.min_months_per_year)} meses válidos por año;
      cobertura anual mínima ${100 * (data.method?.min_coverage_ratio || 0)}%.</p>
      <ul>${(data.method?.limitations || []).map(item => `<li>${escape(item)}</li>`).join('')}</ul></details>`;
  }
  return { request, cities, fillCities, analyze, compare, showError, escape, evidence };
})();
