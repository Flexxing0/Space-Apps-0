/**
 * EarthLens — Mapa Interactivo con Leaflet y OpenStreetMap (map.js)
 * Responsable: 02 / Mapa interactivo y explorador
 *
 * Implementa el mapa mundial, clics, marcador arrastrable, celda geográfica
 * de referencia NASA POWER / MERRA-2 (0.5° x 0.625°) y sincronización de coordenadas.
 */

(function (window) {
  'use strict';

  // Coordenadas iniciales por defecto (Consulta de prueba del plan: Comodoro Rivadavia)
  const DEFAULT_LOCATION = {
    latitude: -45.86,
    longitude: -67.50,
    label: 'Comodoro Rivadavia, Argentina (Caso de prueba)',
    zoom: 6
  };

  // Resolución espacial aproximada de NASA POWER / MERRA-2 (0.5° lat x 0.625° lon)
  const MERRA2_LAT_RES = 0.5;
  const MERRA2_LON_RES = 0.625;

  let mapInstance = null;
  let activeMarker = null;
  let gridCellRectangle = null;
  let currentCoords = {
    latitude: DEFAULT_LOCATION.latitude,
    longitude: DEFAULT_LOCATION.longitude,
    label: DEFAULT_LOCATION.label
  };
  let onLocationChangeCallback = null;

  /**
   * Normaliza y limita coordenadas dentro de rangos geográficos válidos.
   */
  function normalizeCoords(lat, lon) {
    const parsedLat = Number(lat);
    const parsedLon = Number(lon);
    if (!Number.isFinite(parsedLat) || !Number.isFinite(parsedLon)) {
      return null;
    }
    const clampedLat = Math.max(-90, Math.min(90, parsedLat));
    // Normalizar longitud entre -180 y 180 si el usuario desplaza el mapa horizontalmente
    let wrappedLon = ((parsedLon + 180) % 360 + 360) % 360 - 180;
    if (parsedLon === 180) wrappedLon = 180;

    return {
      latitude: Number(clampedLat.toFixed(4)),
      longitude: Number(wrappedLon.toFixed(4))
    };
  }

  /**
   * Calcula los bordes de la celda geográfica NASA POWER / MERRA-2 (0.5° x 0.625°)
   * centrada en torno al punto consultado.
   */
  function getMerraCellBounds(lat, lon) {
    const halfLat = MERRA2_LAT_RES / 2;
    const halfLon = MERRA2_LON_RES / 2;
    const south = Math.max(-90, lat - halfLat);
    const north = Math.min(90, lat + halfLat);
    const west = Math.max(-180, lon - halfLon);
    const east = Math.min(180, lon + halfLon);
    return [
      [south, west],
      [north, east]
    ];
  }

  /**
   * Construye el contenido HTML del popup informativo sobre el marcador.
   */
  function buildPopupHtml(lat, lon, label) {
    const latHemisphere = lat >= 0 ? 'N' : 'S';
    const lonHemisphere = lon >= 0 ? 'E' : 'O';
    const safeLabel = label ? escapeHtml(label) : 'Punto de muestreo seleccionado';

    return `
      <div class="earthlens-popup">
        <div class="earthlens-popup-title">${safeLabel}</div>
        <div class="earthlens-popup-coords">
          Lat: ${lat.toFixed(4)}° (${Math.abs(lat).toFixed(2)}° ${latHemisphere})<br>
          Lon: ${lon.toFixed(4)}° (${Math.abs(lon).toFixed(2)}° ${lonHemisphere})
        </div>
        <div class="earthlens-popup-note">
          Celda NASA POWER / MERRA-2 (~0.5° × 0.625°). Selecciona otra ciudad del catálogo.
        </div>
      </div>
    `;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  /**
   * Crea o mueve el marcador y el rectángulo de celda MERRA-2 en el mapa.
   */
  function updateMarkerAndCell(lat, lon, label, options = {}) {
    if (!mapInstance) return;

    const normalized = normalizeCoords(lat, lon);
    if (!normalized) return;

    currentCoords = {
      latitude: normalized.latitude,
      longitude: normalized.longitude,
      label: label || 'Ubicación personalizada'
    };

    const latLng = [currentCoords.latitude, currentCoords.longitude];
    const cellBounds = getMerraCellBounds(currentCoords.latitude, currentCoords.longitude);

    if (!activeMarker) {
      activeMarker = L.marker(latLng, {
        draggable: false,
        title: 'Ciudad del catálogo argentino'
      }).addTo(mapInstance);

      activeMarker.on('dragend', function (event) {
        const pos = event.target.getLatLng();
        updateMarkerAndCell(pos.lat, pos.lng, 'Coordenadas ajustadas manualmente', {
          panTo: true,
          openPopup: true,
          notify: true
        });
      });
    } else {
      activeMarker.setLatLng(latLng);
    }

    if (!gridCellRectangle) {
      gridCellRectangle = L.rectangle(cellBounds, {
        color: '#00b4d8',
        weight: 1.5,
        fillColor: '#00b4d8',
        fillOpacity: 0.14,
        dashArray: '4, 4',
        interactive: false
      }).addTo(mapInstance);
    } else {
      gridCellRectangle.setBounds(cellBounds);
    }

    activeMarker.bindPopup(buildPopupHtml(currentCoords.latitude, currentCoords.longitude, currentCoords.label));

    if (options.openPopup !== false) {
      activeMarker.openPopup();
    }

    if (options.flyTo && typeof options.zoom === 'number') {
      mapInstance.flyTo(latLng, options.zoom, { duration: 0.8 });
    } else if (options.panTo) {
      mapInstance.panTo(latLng);
    }

    // Actualizar indicador flotante inferior del mapa si existe en el DOM
    const liveCoordEl = document.getElementById('map-live-coords');
    if (liveCoordEl) {
      liveCoordEl.textContent = `${currentCoords.latitude.toFixed(4)}°, ${currentCoords.longitude.toFixed(4)}°`;
    }

    if (options.notify !== false) {
      notifyLocationChange(currentCoords);
    }
  }

  /**
   * Notifica a explorer.js mediante callback y evento DOM personalizado.
   */
  function notifyLocationChange(coords) {
    if (typeof onLocationChangeCallback === 'function') {
      onLocationChangeCallback({ ...coords });
    }
    const event = new CustomEvent('earthlens:location-changed', {
      detail: { ...coords }
    });
    window.dispatchEvent(event);
  }

  /**
   * Inicializa el mapa Leaflet dentro del contenedor indicado.
   */
  function init(containerId = 'explorer-map', options = {}) {
    const container = document.getElementById(containerId);
    if (!container || typeof L === 'undefined') {
      console.error('[EarthLensMap] No se encontró el contenedor del mapa o la librería Leaflet.');
      return null;
    }

    if (typeof options.onLocationChange === 'function') {
      onLocationChangeCallback = options.onLocationChange;
    }

    const initialLat = Number.isFinite(options.latitude) ? options.latitude : DEFAULT_LOCATION.latitude;
    const initialLon = Number.isFinite(options.longitude) ? options.longitude : DEFAULT_LOCATION.longitude;
    const initialZoom = Number.isFinite(options.zoom) ? options.zoom : DEFAULT_LOCATION.zoom;
    const initialLabel = options.label || DEFAULT_LOCATION.label;

    // Capas base científicas
    const osmStandard = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });

    const topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 17,
      attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap'
    });

    const satelliteLayer = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 17,
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, NOAA, USGS, NASA'
      }
    );

    mapInstance = L.map(containerId, {
      center: [initialLat, initialLon],
      zoom: initialZoom,
      minZoom: 2,
      worldCopyJump: true,
      layers: [osmStandard]
    });

    // Control de capas y escala
    const baseLayers = {
      'Mapa Estándar (OSM)': osmStandard,
      'Topográfico / Relieve': topoLayer,
      'Vista Satelital (Esri)': satelliteLayer
    };
    L.control.layers(baseLayers, null, { position: 'topleft' }).addTo(mapInstance);
    L.control.scale({ metric: true, imperial: false, position: 'bottomright' }).addTo(mapInstance);

    // Clic sobre cualquier punto del mapa para seleccionar coordenadas


    // Colocar marcador inicial
    updateMarkerAndCell(initialLat, initialLon, initialLabel, {
      openPopup: true,
      notify: true
    });

    // Asegurar renderizado correcto de tiles cuando cambia el layout
    setTimeout(function () {
      if (mapInstance) mapInstance.invalidateSize();
    }, 150);

    return mapInstance;
  }

  /**
   * Permite fijar ubicación desde controles externos (inputs, presets o misiones).
   */
  function setLocation(lat, lon, label = 'Ubicación seleccionada', zoom = null, notify = true) {
    const normalized = normalizeCoords(lat, lon);
    if (!normalized) return false;

    const targetZoom = typeof zoom === 'number' ? zoom : (mapInstance ? Math.max(mapInstance.getZoom(), 5) : 6);
    updateMarkerAndCell(normalized.latitude, normalized.longitude, label, {
      flyTo: true,
      zoom: targetZoom,
      openPopup: true,
      notify: notify
    });
    return true;
  }

  /**
   * Centra el mapa en una vista global completa.
   */
  function resetWorldView() {
    if (!mapInstance) return;
    mapInstance.flyTo([-39, -64], 4, { duration: 0.8 });
  }

  /**
   * Usa la API de Geolocalización del navegador para posicionar el marcador en la ubicación del usuario.
   */
  function locateUser(onSuccess, onError) {
    if (!navigator.geolocation) {
      if (typeof onError === 'function') {
        onError('Tu navegador no soporta geolocalización automática.');
      }
      return;
    }

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        const lat = pos.coords.latitude;
        const lon = pos.coords.longitude;
        setLocation(lat, lon, 'Mi ubicación actual', 8, true);
        if (typeof onSuccess === 'function') {
          onSuccess({ latitude: lat, longitude: lon });
        }
      },
      function (err) {
        if (typeof onError === 'function') {
          onError('No se pudo obtener tu ubicación actual (' + err.message + '). Selecciona un punto en el mapa.');
        }
      },
      { enableHighAccuracy: false, timeout: 7000 }
    );
  }

  function getLocation() {
    return { ...currentCoords };
  }

  // Exponer API pública
  window.EarthLensMap = {
    init: init,
    setLocation: setLocation,
    getLocation: getLocation,
    resetWorldView: resetWorldView,
    locateUser: locateUser,
    normalizeCoords: normalizeCoords,
    DEFAULT_LOCATION: DEFAULT_LOCATION
  };
})(window);
