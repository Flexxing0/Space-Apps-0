/* Inicio conectado al catálogo y a la caché NASA POWER. */
document.addEventListener('DOMContentLoaded', async () => {
  const api = window.EarthLensAPI;
  const container = document.getElementById('estimations-rows');
  const select = document.getElementById('home-city-select');
  const badge = document.getElementById('data-source-status');
  let map, marker, sequence = 0;
  const icons = { T2M: '🌡️', T2M_MAX: '☀️', T2M_MIN: '❄️', PRECTOTCORR: '🌧️', RH2M: '💧', WS2M: '💨' };
  try {
    const [cities, variables] = await Promise.all([api.cities(), api.request('/api/variables')]);
    api.fillCities(select, cities, 'buenos-aires');
    if (typeof L !== 'undefined') {
      map = L.map('home-location-map').setView([-39, -64], 4);
      const standard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap', maxZoom: 18
      }).addTo(map);
      const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri, NASA' });
      L.control.layers({ 'Mapa estándar': standard, 'Vista satelital': satellite }).addTo(map);
      for (const city of cities) {
        L.circleMarker([city.latitude, city.longitude], { radius: 5 }).addTo(map)
          .bindTooltip(city.name).on('click', () => { select.value = city.id; load(); });
      }
    }
    async function load() {
      const currentSequence = ++sequence;
      const city = cities.find(item => item.id === select.value);
      document.getElementById('user-location-name').textContent = `${city.name}, ${city.province}`;
      document.getElementById('user-location-coords').textContent = `(${city.latitude.toFixed(4)}°, ${city.longitude.toFixed(4)}°)`;
      document.querySelectorAll('.js-go-explorer-link').forEach(link => { link.href = `/explorer?city_id=${city.id}`; });
      if (map) {
        if (marker) marker.remove();
        marker = L.marker([city.latitude, city.longitude]).addTo(map);
        map.panTo([city.latitude, city.longitude]);
      }
      badge.textContent = 'Consultando datos y motor…';
      container.classList.remove('alert', 'alert-danger');
      container.textContent = 'Cargando…';
      try {
        const result = await api.request(`/api/summary?city_id=${city.id}`);
        if (currentSequence !== sequence) return;
        badge.className = 'badge bg-success-subtle text-success-emphasis';
        badge.textContent = `Datos reales NASA POWER · ${result.meta.origin === 'cache' ? 'caché' : 'descarga'}`;
        container.innerHTML = variables.data.map(variable => {
          const item = result.data.estimations[variable.code];
          const stats = item.statistics;
          const link = `/explorer?city_id=${city.id}&variable=${variable.code}`;
          return `<div class="data-row-item"><div class="data-row-var"><span class="data-row-icon">${icons[variable.code]}</span>
            <div><strong>${api.escape(variable.name)}</strong><br><code>${variable.code}</code></div></div>
            <div class="data-row-metric"><span class="data-row-metric-label">Media anual histórica</span>
            <strong>${item.mean_value ?? '—'} ${api.escape(item.unit)}</strong></div>
            <div class="data-row-metric"><span class="data-row-metric-label">Cambio por década</span>
            <strong>${stats?.change_per_decade ?? '—'} ${api.escape(item.unit)}</strong></div>
            <div class="data-row-metric"><span class="data-row-metric-label">Evidencia</span>
            <span>${stats ? `p = ${stats.p_value}; ${stats.significant ? 'tendencia significativa' : 'evidencia insuficiente'}` : 'Cobertura insuficiente'}</span></div>
            <a class="btn btn-sm btn-outline-primary" href="${link}">Ver en Explorador →</a></div>`;
        }).join('');
        const evidence = Object.values(result.data.estimations).find(item => item.statistics);
        if (evidence) container.insertAdjacentHTML('beforeend', api.evidence(evidence));
      } catch (error) {
        if (currentSequence !== sequence) return;
        badge.textContent = 'Consulta no disponible';
        badge.className = 'badge bg-danger';
        container.replaceChildren();
        api.showError(container, error);
      }
    }
    select.addEventListener('change', load);
    await load();
  } catch (error) { api.showError(container, error); badge.textContent = 'Consulta no disponible'; }
});
