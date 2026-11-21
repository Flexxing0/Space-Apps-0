# EarthLens — reestructuración e informe de implementación

**Corrección de interfaz vigente:** [Time Machine como aplicación principal](../architecture/time-machine-correction.md).
El primer diseño descrito abajo fue corregido: `/` abre el mapa, los paneles son
flotantes y el mismo cursor carga datos hacia pasado/futuro. La aceptación vigente
es A–H en Chrome; H continúa bloqueada/no implementada. Suite actual: 248 pruebas,
247 aprobadas y una omitida. Los registros siguientes conservan el avance anterior.

Patagonia Prime · Argentina · 15/11/2026.
**EarthLens — Comprendé el pasado. Anticipá el futuro.**

Rama de trabajo: `feature/backend-api`, base `5f7fe09`. El `main` inspeccionado
(`9300942`) agregó datos a `4157789`, no cambios nuevos de código. Su código ya
estaba integrado en la rama de backend. Se recuperaron sus cachés desde un respaldo
local al cambiar de rama; no se reconstruyó el backend sobre la aplicación antigua
de `main`. No hay commits, push ni despliegue de esta reestructuración.

## Estado por fase

«Probado» se refiere a software o acceso real según se indica; no equivale a
validación científica. La interfaz y los servicios entregados son de desarrollo.

| Fase solicitada | Implementado | Verificación / límite actual |
| --- | --- | --- |
| Auditoría | Rama, código de main/equipo, proveedores, cachés, Docker y documentación | Base: 210 pruebas, 209 aprobadas y una de red omitida. Datos originales preservados. |
| Time Machine 2.0 | Vista unificada mapa/controles/inspector, navegación profesional, selección territorial de puntos, perfiles y acceso al Laboratorio | Chrome real; interfaz original en `/time-machine/legacy`. Áreas dibujadas no son mediciones de superficies. Sin rutas geográficas. |
| Tiempo histórico/futuro | Fecha/rango, reproducción, pasos, velocidad, zoom, calendario compartido; datos faltantes explícitos | Históricos mensuales y diarios separados; el selector no aumenta resolución científica. Sin mapas divididos. |
| Datos diarios/horarios | POWER Daily, Open-Meteo Forecast, ERA5 horario, multivariable, caché propia, unidades/tiempos/faltantes | Tres consultas reales Comodoro exitosas. ERA5-Land evaluado, no integrado. SMN automatizado bloqueado por autenticación. |
| Sistema híbrido | Histórico, reanálisis, pronóstico y climatología distinguidos; horizonte operativo y ausencia de emisión/bandas explícitos | No une productos ni completa 2025–presente. TimesFM no habilitado. Proyección anual anterior conservada como experimental. |
| City Profile | Plantilla dinámica, climatología, perfil Z, Fingerprint original, Connections, Twins, incidente documentado y planificación | Chrome y datos reales. Elevación de 25 centroides (GLO-90); 12 fotos atribuidas con licencia compatible. Población sin fuente censal incorporada. Falta validación científica de asociaciones y similitud. |
| Calendario/eventos | Mes/semana/día/lista, formularios, CRUD, reprogramación/cancelación, SQLite y migración, autenticación/CSRF/propiedad | Base persistente Docker y pruebas de aislamiento entre usuarios. Sitio exacto y rutas libres siguen bloqueados por validación territorial pendiente. |
| Compatibilidad/alternativas | Reglas configuradas por evento, razones/unidades/cobertura, alternativas ±7 días/±6 horas y guardado explícito | Sin puntajes ni umbrales universales. No certifica seguridad; alertas SMN desconocidas requieren revisión. |
| Monitoreo/notificaciones | CLI independiente, frecuencia por cercanía, snapshots, versiones, gráfico por variable/hora válida, lease, fallos, deduplicación, centro interno y lectura | Demo de cambio sólo en base temporal con datos sintéticos identificados. Ejecución real CLI sin eventos privados. Sin envíos externos. |
| Earth Impact Comodoro | Catálogo del temporal 2017, fuentes IGN/SEGEMAR e inventario explícito de capas ausentes | **Parcial**: no hay DEM/calles/polígonos operativos. Overpass: 406; segundo acceso: 429. No se generan mapas de riesgo ni impactos de sitios. |
| TimesFM 3.0 | Investigación oficial, contrato de capacidades y arnés desacoplado de backtesting | **Bloqueado para producto comercial** por licencia de pesos descargables y falta de servicio autorizado. No instalado ni validado; no recomienda fechas. |
| Backtesting | Cortes diarios sin filtración, persistencia/naive semanal, MAE/RMSE/cobertura cuando existe intervalo | Baselines ejecutados con 365 datos POWER reales de 2023; 18 combinaciones. Sin comparación de archivos meteorológicos emitidos; no valida TimesFM. |
| Informes/exportación | PDF científico con gráfico/tabla/fuentes y tendencias/comparación de épocas/ciudades del motor POWER, PDF privado de evento e historial, JSON/CSV de series comparadas | Chrome descargó PDF real; permisos comprobados. PDF de dos ciudades reales probado con red bloqueada. |
| Docker/despliegue | Imagen Python 3.12-slim, ReportLab, DB/cache persistentes, servicio de monitoreo independiente y Gunicorn conservado | Backend saludable y monitor ejecutándose. SQLite conserva ejecuciones después de recrear el contenedor. Build y `pip check` correctos. Producción multiinstancia/Cloud Run no desplegada. |

## Datos reales verificados

Inventario: `python -m scripts.audit.audit_science`. No sumar versiones, pilotos ni
subperíodos solapados como observaciones independientes.

| Producto | Cobertura | Series / registros | Calidad |
| --- | --- | --- | --- |
| POWER mensual AG | 25 ciudades, 2000–2024 | 150 / 45.000 | Todos disponibles |
| GLDAS_NOAH025_M 2.1, Giovanni CSV | 25 ciudades, 2000–2024 | 125 / 37.500 | Todos disponibles; acceso/precisión CSV identificados |
| GPM_3IMERGM Final V07 | 25 ciudades, 2000–2024 | 25 / 7.500 | Todos disponibles; mm/hr |
| MOD13Q1 colección 061, órdenes ORNL | 9 ciudades, fechas nativas 2000–2024 | 18 / 10.296 | 2.006 aceptados; 8.290 nulos/excluidos por política QA; no imputados |
| MOD13Q1 piloto REST, colección no informada | 3 ciudades, 2024 | 6 / 138 | 56 aceptados; 82 excluidos, versión separada |
| SWOT_L2_HR_RiverSP_D | Río Chubut/Trelew, pasadas de 2024 | WSE y ancho, 31 pasadas / 62 valores numéricos | Calidad pendiente; análisis deshabilitado |
| POWER Daily AG, incidente 2017 | Comodoro, 29/03–08/04 | 6 / 66 | Sin nulos |
| ERA5 vía Open-Meteo | Comodoro, 29/03–08/04/2017 | 8 / 2.112 | Sin nulos |
| Open-Meteo best_match | Comodoro, 15–21/11/2026, piloto visible de siete días | 10 / 1.680 | Sin nulos; extracción cacheada completa de 16 días: 3.840 valores |
| POWER Daily AG, backtesting 2023 | Comodoro, año 2023 | 6 / 2.190 | 365 valores de T2M utilizados; no se fabricaron observaciones |
| Copernicus DEM GLO-90 vía Open-Meteo | 25 centroides, elevación estática | 25 valores, m, píxel de 90 m | No constituye un DEM continuo del ejido ni un mapa de riesgo |

MODIS ampliado: Bariloche, Buenos Aires, Comodoro Rivadavia, La Plata, Neuquén,
Puerto Madryn, Río Gallegos, Trelew y Ushuaia. 15 órdenes todavía devolvieron 404;
la de Mendoza sigue sin identificador de entrega, sin reenviar el pedido ni correo.
El parser ahora descubre el CSV combinado original desde `csv/`; no importa los
CSV filtrados/estadísticos como si fueran datos brutos. Comprueba colección 061,
gránulo, coordenadas de un píxel, fechas esperadas y bandas de calidad antes de guardar.
La disponibilidad MODIS empieza en la primera fecha nativa de 2000, no el 1 de enero.

También se conservan las extracciones POWER de otros períodos y los pilotos
GLDAS/GPM. Ninguna caché tiene formato inválido en el inventario. Se compararon
**462 archivos científicos originales** contra el respaldo: cero cambios y cero
faltantes. Las órdenes/reportes de progreso se actualizan por separado.

## Archivos y decisiones

- Interfaz: `templates/pages/workspace.html`, `static/js/time-machine/workspace.js`,
  `static/css/pages/workspace.css`, `templates/pages/laboratory.html`; ajustes de navegación,
  inicio y rutas web. Se conservan plantillas y scripts del equipo.
- Datos de interfaz: `services/workspace/workspace.py`, `api/workspace.py`; reutilizan
  POWER, ScientificService y el motor estadístico existentes sin descargas mensuales.
- Meteorología: `services/weather/weather.py`, `api/weather.py`, `scripts/data/probe_weather.py`.
- Persistencia/autenticación: `services/storage/persistence.py`, `services/events/events.py`,
  `api/events.py`; SQL parametrizado, contraseñas scrypt, CSRF, permisos por usuario,
  rate limit de login y caché HTTP privada desactivada.
- Planificación/trabajos: `services/events/planning.py`, `services/events/monitoring.py`,
  `scripts/maintenance/monitor_events.py`; preferencias del usuario, sin sustitución por IA.
- Impactos: `services/science/impact.py`, `scripts/data/fetch_impact.py`; ninguna capa simulada.
- Evaluación: `services/prediction/prediction.py`, `scripts/audit/backtest_weather.py`.
- Exportación: `services/workspace/reports.py`; nueva dependencia directa ReportLab 5.1.0.
- Contexto urbano: `scripts/data/fetch_city_context.py`, elevaciones y fotografías
  atribuidas/identificadas por ciudad. No usa fotos como observaciones ambientales.
- MODIS: corrección acotada de `scripts/data/order_modis.py`, prueba añadida de índice.
- Aplicación/Docker: `app.py`, `api/errors.py`, `compose.yaml`, `Dockerfile`,
  `requirements.txt`, exclusiones de cachés/base/secretos.
- Pruebas: `tests/workspace/test_workspace_v2.py`, `scripts/audit/check_workspace.py`;
  prueba de forecast actualizada para comprobar la vista original en su nueva ruta
  y conservar el contrato del proveedor heredado, sin eliminar sus verificaciones.

No se modifican los cálculos de `services/science/trend_analysis.py`, las seis variables de
Radar, el normalizador mensual ni los proveedores existentes. Los nuevos métodos
descriptivos no sustituyen al motor ni producen descubrimientos confirmados.

## Verificación y demostraciones

Base: 209 aprobadas y una optativa omitida. Nuevas pruebas cubren contratos, CRUD,
autenticación/CSRF, permisos entre cuentas, SQLite/migración, caché/refresh fallido,
horizontes, faltantes, criterios, alternativas, monitoreo/versiones/notificaciones,
lease, rate limit, informes privados, backtesting y descubrimiento MODIS.
Resultado final ampliado en Docker: **237 descubiertas, 236 aprobadas y una de red
optativa omitida**, en 36,40 segundos. `git diff --check` sin errores. Los últimos
ajustes de validación, contexto e informes pasaron además las 26 pruebas nuevas.

Chrome real: interfaz/mapa/serie histórica; sincronización calendario/fecha;
incidente 2017 + POWER diario + descarga PDF; pronóstico operativo; perfil dinámico,
radial documentado, tendencias originales, Connections/Twins; evento privado y
alternativas; móvil sin desborde. Último reporte: ocho grupos aprobados y
**cero errores JavaScript**, con la demo de monitoreo añadida. La cuenta y base de demostración son temporales,
se eliminan al terminar y no se agregan al espacio del usuario.

Demo 3 está comprobada mediante prueba automática y navegador aislados: primera evaluación,
reejecución sin duplicado, cambio de criterios incumplidos por pronóstico sintético
de software, nueva notificación e historial. No se alteró el pronóstico real para
simular un cambio en producción. Falta demostrar un cambio meteorológico real
entre emisiones futuras; no se afirma que ya ocurrió.

## Bloqueos y próximos pasos

1. Obtener acceso oficial SMN y validar avisos por geometría, vigencia y actualización.
2. Elegir y configurar una vía comercial de Open-Meteo antes de operar para empresas.
3. Aportar el enlace ORNL de Mendoza y esperar resultados de las otras 15 órdenes.
4. Validar capas oficiales de terreno/susceptibilidad y límites argentinos; sólo
   después activar sitios exactos, recorridos e intersecciones Earth Impact.
5. Acordar validación científica de reglas de actividad, radial Z, Connections/Twins
   y cambios metodológicos del motor. Radar sigue con 150 pruebas y cero confirmados.
6. Resolver vía/licencia TimesFM, medir recursos en un servicio independiente,
   backtest del modelo real y archivo de pronósticos antes de habilitar recomendaciones.
7. Incorporar fuente censal de población y completar imágenes donde el acceso
   Wikimedia falló (13 ciudades). Ampliar revisión científica de informes/criterios.
8. Preparar PostgreSQL/almacenamiento compartido/Secret Manager/scheduler externo,
   recuperación de cuenta y revisión de seguridad antes de despliegue multiusuario.

Guía operativa, endpoints, ejemplos, licencias, métodos y límites:
[docs/architecture/workspace.md](../architecture/workspace.md).
