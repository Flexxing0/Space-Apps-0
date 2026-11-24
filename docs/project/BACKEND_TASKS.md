# EarthLens — estado y tareas del backend

## Infraestructura predictiva, primera etapa — 21/11/2026

Se agregó un contrato y un coordinador offline, una proyección SQLite de solo
lectura para HTTP y la migración y el adaptador de cargas offline de BigQuery.
Se conservan el pronóstico operativo, los gráficos y los endpoints de Time
Machine. El proveedor TimesFM 3.0 y la automatización siguen deshabilitados.
Quedan pendientes el transporte a BigQuery, las reservas duraderas en nube,
la publicación de proyecciones por instancia y la validación científica.
[Arquitectura, API y configuración futura](../architecture/prediction-infrastructure.md)

## Auditoría histórica antes de TimesFM — 21/11/2026

Cambios locales en `feature/backend-api`. Se repararon la resolución temporal
y la lectura cache-only de Time Machine, con regresiones automatizadas y
pruebas reales puntuales de POWER mensual/diario y ERA5. El
[informe de cobertura](../science/scientific-sources.md#auditoría-del-backend--21112026)
distingue los pilotos actuales, los lotes históricos y los casos de software.
Queda pendiente repetir descargas GLDAS/GPM con acceso Earthdata y verificar
los períodos adicionales antes de declararlos disponibles por ciudad.

## Reorganización de carpetas — 21/11/2026

Cambios locales en `refactor/project-structure`. El
[inventario de estructura](../architecture/project-structure.md) enumera los
157 movimientos. La fábrica Flask sigue en `app.py`. Las 73 reglas HTTP
coinciden con la referencia en ruta, métodos y endpoint. El motor estadístico,
los datos versionados y las muestras de referencia conservan sus bytes.

- Suite de referencia y suite final en Python 3.12, 254 casos descubiertos y 249
  aprobados. Cuatro pruebas del flujo de despliegue requieren Linux/Bash.
  La prueba optativa de NASA POWER pasó por separado con dos consultas reales.
- Flask arrancó con almacenamiento temporal. Chrome verificó el mapa, la única
  timeline y un gráfico Chart.js con datos reales. En la aceptación oficial
  aislada pasaron A–F, cobertura y móvil. G pasó con la simulación prevista,
  limitada a la base temporal. H quedó bloqueada porque TimesFM sigue sin
  implementación. No hubo errores JavaScript.
- Queda pendiente construir e iniciar la imagen con Docker y ejecutar allí las
  pruebas Linux. Este entorno Windows carece de CLI y motor Docker. Se revisaron
  las fuentes de `COPY`, la sintaxis Bash y las pruebas disponibles del verificador
  de release. No se desplegó en Cloud Run.

## Corrección prioritaria: Time Machine como aplicación

Estado vigente de interfaz: [informe y capturas A–H](../architecture/time-machine-correction.md).
Se conserva la rama `feature/backend-api`, sin commits ni push.

- `/` abre directamente Time Machine. Mapa completo, timeline inferior única,
  paneles flotantes cerrables y barra compacta; sin landing como entrada.
- Fecha compartida por cursor, reproducción, calendario, perfil, acontecimientos,
  eventos y notificaciones. Navegar no se detiene al terminar el rango histórico.
- Nuevo adaptador de selección temporal sobre los servicios existentes; conserva
  variable y elige histórico/pronóstico/climatología verificados. Nulos y variables
  sin datos futuros explícitos; fallos HTTP no se hacen pasar por climatología.
- Avisos con cambios anteriores/actuales y viaje al evento; perfil con radial
  visible, formulario de evento plegable y pronóstico primero. Persistencia y
  privacidad anteriores conservadas.
- Docker: **248 pruebas descubiertas, 247 aprobadas y una NASA live omitida**.
  A–F aprobadas en Chrome con datos reales; G aprobada como simulación aislada;
  H bloqueada/no implementada. Móvil y cobertura adicional comprobados. Sin
  errores JavaScript; capturas inspeccionadas, no sólo contadas.
- TimesFM sin dependencias/pesos/inferencia/predicciones. Restricción de licencia
  para el uso previsto y archivo F32 de 1.322.898.824 bytes frente a 1 GiB del backend.
  El backtest existente es de baselines y no valida TimesFM.

Pendientes: vía licenciada/recursos/validación TimesFM; acceso oficial SMN; capas
territoriales para impactos; límites oficiales para coordenadas libres; entregas
MODIS y revisión metodológica ya señaladas. No se presentan como completados.

## Reestructuración profesional — estado vigente 15/11/2026

Trabajo en `feature/backend-api`, sin commits ni push. Estado detallado por fase:
[docs/project/EARTHLENS_ROADMAP.md](EARTHLENS_ROADMAP.md). Contrato, comandos, metodología,
licencias y límites: [docs/architecture/workspace.md](../architecture/workspace.md). Las entradas antiguas
siguientes conservan su fecha y dependencias.

Comprobado en esta etapa:

- Time Machine unificado, timeline/calendario compartidos, selección de puntos,
  interfaz anterior conservada y perfiles dinámicos. Climatología, Fingerprint de
  tendencias, radial Z documentado y Connections/Twins exploratorios.
- POWER Daily, Open-Meteo Forecast y ERA5 con pilotos reales de Comodoro,
  contratos y caché independientes de los históricos mensuales.
- SQLite/migración, cuentas privadas con CSRF/permisos, CRUD de eventos,
  compatibilidad por preferencias, alternativas por fecha/hora y guardado explícito.
- Monitoreo CLI independiente, snapshots/versiones, lease, fallos y notificaciones
  internas deduplicadas, gráfico por variable/hora; contenedor independiente activo.
- PDF científico con comparación de ciudades y épocas, PDF privado y CSV/JSON.
- Elevación GLO-90 de 25 centroides y 12 fotografías ilustrativas geolocalizadas,
  con autor/licencia/enlace de Wikimedia; 13 accesos fotográficos fallaron.
- MODIS ampliado a nueve ciudades: 18 series colección 061, 10.296 registros,
  2.006 aceptados por QA y 8.290 excluidos/nulos, sin imputaciones.
- 462 archivos científicos originales comparados por SHA-256 sin cambios ni
  faltantes; POWER 45.000, GLDAS 37.500 y GPM 7.500 mensuales conservados.
- Docker construido y saludable; `pip check` correcto. Suite ampliada:
  **237 descubiertas, 236 aprobadas y una de red optativa omitida**.
- Chrome: ocho grupos aprobados y cero errores JavaScript. Demos históricas y de
  planificación con datos reales y base privada temporal. Cambio de pronóstico
  para probar notificaciones únicamente simulado en pruebas aisladas de software.

Pendientes/bloqueos: acceso oficial SMN (401), suscripción comercial Open-Meteo,
TimesFM 3.0 con vía licenciada y validación, quince órdenes MODIS sin entrega y
enlace de Mendoza, capas Earth Impact/límites oficiales, sitios/rutas exactos,
fuente censal de población, completar fotografías donde el acceso falló,
validación científica y producción con DB externa/secretos/scheduler.
**No están científicamente validados** Radar, nuevas asociaciones, similitud o
perfiles Z por disponer de una interfaz. La revisión conjunta sigue pendiente.

Actualización: **15 de noviembre de 2026**. Equipo: **Patagonia Prime**.
Desafío: **Earth System Trend Detective**, NASA Space Apps Challenge 2026.

**Alcance exclusivo: República Argentina.** No incluir ciudades internacionales.
El catálogo inicial de 25 ciudades puede ampliarse; las investigaciones futuras
admitirán cualquier ubicación argentina con validación territorial verificable.
Una caja rectangular no es una validación definitiva de pertenencia al país.

Este documento refleja el código local y las verificaciones realizadas. Las tareas
pendientes no autorizan avanzar automáticamente. Ver [AGENTS.md](../../AGENTS.md).

## Estado actual comprobado

El backend consulta datos mensuales de NASA POWER y dispone de catálogo argentino,
caché JSON, obtención masiva y API REST con Flask. El frontend y el motor real del
equipo están integrados para análisis exploratorio y comparación de ciudades.
Earth Radar y Earth Fingerprint tienen backend provisional, contrato común, API,
estudio persistido e interfaces completas `/radar` y `/fingerprint` (fase 1).
La confirmación científica y el ajuste múltiple permanecen pendientes de B06.
El entorno de desarrollo Docker está construido, iniciado y verificado. En esta
instalación faltaban las observaciones: se descargaron las 25 ciudades 2000–2024
y se comprobó después su reutilización completa sin nuevas descargas.
La capa multiproveedor y sus contratos nativos están implementados. GLDAS y GPM
tienen históricos reales 2000–2024 de las 25 ciudades. MODIS tiene un piloto
verificado de tres ciudades y órdenes históricas en procesamiento; SWOT tiene
un tramo argentino con observaciones reales. El panel de fuentes está conectado
al Explorador, Comparador, Radar, Fingerprint y Modo detective, sin ampliar sus
métodos estadísticos. Time Machine se incorporó posteriormente desde main para
POWER por ciudad, con resultados provisionales y sin cuadrantes simulados. El usuario confirmó
que Earth Connections todavía no existe. Las secciones de diagnóstico conservan
sus estados históricos; el cierre de fuentes al final refleja el estado vigente.

| Componente/tarea | Estado | Evidencia |
| --- | --- | --- |
| Proveedor POWER mensual y consulta individual | Implementado y conservado | `services/providers/power.py`, `get_data()`. |
| Seis variables y consulta multivariable | Implementado y reutilizado | `get_data_multi()`: `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `WS2M`. |
| Normalización, unidades, fuentes y metadatos | Implementado y conservado | Normalizador y resultados del proveedor; relleno a `None`, exclusión de `YYYY13`, sin conversiones implícitas. |
| **B01 — catálogo argentino** | Completada para las 25 ciudades solicitadas | `data/cities.json`, `services/geography/cities.py`; listado, búsqueda por ID y filtros por provincia/región. |
| Procedencia geográfica y reconstrucción | Implementada con GeoRef real | `coordinate_source` conserva centroide, registro, consulta, ID y fecha; `scripts/data/build_city_catalog.py`. |
| **B03 — caché local** | Completada para POWER | `services/providers/cache.py`, `data/cache/.gitignore`; clave canónica, fechas UTC y reemplazo atómico. |
| **B04 — obtención masiva** | Implementada; recuperación real de 25 ciudades verificada en Docker | 25 descargas reales, 150 series y 45.000 registros disponibles 2000–2024. Repetición: 25 aciertos, cero descargas y cero fallos. |
| Protección de caché ante respuestas incompletas o degradadas | Implementada y probada | Seis series, meses completos, contexto, fuentes y unidades; no reemplaza valores disponibles por nulos. |
| Arquitectura para coordenadas libres argentinas | Preparada; falta el adaptador territorial real | `services/geography/geography.py`, `TerritoryEvidence`, `collect_location()`. |
| **B05 — API REST básica** | Completada y probada con el cliente Flask | `app.py`, Blueprint `api/routes.py`, servicio `services/api_service.py`; seis endpoints documentados. |
| **B02 — instalación y dependencias** | Instalación limpia verificada en Docker Linux/amd64 | Python 3.12.16, Flask 3.1.3 y Requests 2.34.2 instalados desde `requirements.txt`; `pip check` y suite satisfactorios. Sin lock transitivo. |
| **B19 — Docker para desarrollo** | Completada para el alcance autorizado | `Dockerfile`, `compose.yaml`, `.dockerignore`, `docs/operations/docker.md`; backend saludable, recarga y caché persistente verificadas. |
| Pruebas sin red | Regresión original de 137 conservada; suite ampliada en esta fase | `tests/`; resultados de la ampliación al final. Sólo NASA de red optativa omitida en Docker. |
| Script manual y documentación previa | Conservados | `scripts/audit/probe_nasa_power.py`, `docs/science/nasa-power.md`. |
| Documentación | Actualizada | `AGENTS.md`, este archivo y contrato para frontend en `docs/architecture/api.md`; documentación previa conservada. |

### Catálogo inicial

| Región del proyecto | Ciudades |
| --- | --- |
| Patagonia | Comodoro Rivadavia, Puerto Madryn, Trelew, Río Gallegos, Ushuaia, Bariloche y Neuquén. |
| Centro y región pampeana | Buenos Aires, La Plata, Mar del Plata, Bahía Blanca, Rosario, Córdoba y Santa Fe. |
| Cuyo | Mendoza, San Juan y San Luis. |
| NOA | Salta, San Salvador de Jujuy, San Miguel de Tucumán y Santiago del Estero. |
| NEA | Posadas, Corrientes, Resistencia y Formosa. |

Las coordenadas y provincias proceden de la API oficial GeoRef. Las regiones son
la agrupación solicitada por el proyecto. Se conservan las denominaciones oficiales
en el registro fuente y los nombres de presentación en el catálogo. Los centroides
son ubicaciones de consulta de la grilla, no estaciones ni promedios urbanos.
El cargador no fija un límite de 25 localidades.

### Verificaciones realizadas

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado de la etapa Flask: **72 pruebas descubiertas; 71 aprobadas y 1 omitida**.
Las 48 pruebas anteriores siguen funcionando. La omitida es la
integración previa `test_power_provider_live.py`, optativa mediante
`EARTHLENS_POWER_LIVE=1`. Los datos sintéticos de las pruebas son exclusivamente
para verificar software; no representan observaciones científicas.

- En la etapa anterior, GeoRef resolvió las 25 localidades y se conservaron sus registros.
- En la etapa anterior se hicieron tres consultas NASA reales: Comodoro Rivadavia, Mendoza y Posadas,
  período **2000–2024**, una petición con seis variables por ciudad.
- Las tres ciudades devolvieron 300 registros mensuales disponibles por variable,
  sin faltantes en esas respuestas concretas.
- Repetición de la CLI con acceso de red bloqueado en la comprobación: tres aciertos
  de caché, cero peticiones y archivos/fechas de obtención sin cambios.
- Pruebas simuladas: recorrido de las 25 ciudades, errores individuales, respuestas
  incompletas, nuevos nulos, series totalmente nulas, valores no finitos, fuentes
  ausentes, vencimiento, corrupción y fallos de reemplazo atómico.

Durante la inspección previa a Flask se encontraron **25 entradas de caché ya
existentes**, todas de 2000–2024. Se comprobó su estructura con el validador actual;
no se atribuye su descarga a esta etapa ni se infiere cobertura de todo el país.
Las verificaciones reales anteriores del proveedor quedan documentadas en
`docs/science/nasa-power.md` y en la conversación.

Verificaciones específicas de la API:

- `tests/http/test_api.py`: 23 pruebas con cliente Flask, NASA simulada y cachés temporales.
- Catálogos, filtros, detalle por ID, regiones, tipos, años, variables, JSON inválido,
  tamaño de cuerpo, métodos HTTP, CORS desactivado y rechazo de coordenadas libres.
- Selección de variables reutilizando la misma caché de seis; faltantes a `null`,
  actualización forzada, conservación ante fallo y advertencias públicas seguras.
- Errores externos con estados 502/503/504 y fallos internos 500, sin textos privados,
  credenciales ni rutas locales en las respuestas.
- Cliente Flask sobre las cachés reales de Comodoro Rivadavia, Mendoza y Posadas:
  HTTP 200 y origen `cache`, 300 meses de T2M por ciudad. La red estuvo bloqueada en
  esa comprobación; los 25 archivos preexistentes conservaron su contenido.
- `flask --app app:create_app routes` mostró los seis endpoints previstos.
- En la etapa Flask, `pip check` no encontró dependencias rotas; todavía no se había
  verificado una instalación desde cero. Esa comprobación se completó posteriormente
  en Docker, como se detalla a continuación. El despliegue productivo sigue pendiente.

Esta etapa no realizó solicitudes a NASA ni a GeoRef.

### Verificación Docker y lote completo

Se construyó `earthlens-backend:dev` desde `python:3.12-slim`, con instalación
limpia de dependencias y ejecución no root (UID 10001). Compose inició un único
servicio `backend` con puerto `127.0.0.1:5000` y estado `healthy`. No se encontró
frontend en el repositorio y no se creó un servicio para él ni una base de datos.

- Suite dentro del contenedor: **72 descubiertas, 71 aprobadas y una integración
  real omitida**, con `EARTHLENS_POWER_LIVE=0`; respuestas externas simuladas.
- Seis endpoints verificados desde Windows: HTTP 200 para salud, variables, listado
  filtrado, detalle de ciudad, regiones y POST de datos. El POST reutilizó caché.
- Recarga automática confirmada por logs al cambiar temporalmente sólo la fecha
  de `app.py`; contenido y fecha original restaurados. Depurador deshabilitado.
- `pip check` sin dependencias rotas en Python 3.12.16 Linux/amd64.
- Lectura y escritura temporal de la caché montada verificadas con UID 10001.
- SHA-256 de las **25 cachés anteriores idénticos** antes y después de verificaciones
  y lote; fechas originales de obtención conservadas. No se incorporó caché a la imagen.

Sólo después de comprobar Docker se ejecutó el comando autorizado:

```powershell
docker compose exec -T backend python -m scripts.data.fetch_power --all --start-year 2000 --end-year 2024
```

| Resultado comprobado | Cantidad |
| --- | ---: |
| Ciudades correctas | 25 |
| Reutilizadas desde caché | 25 |
| Descargas nuevas / solicitudes NASA | 0 |
| Consultas fallidas | 0 |
| Series | 150 |
| Registros mensuales totales | 45.000 |
| Registros con valor disponible | 45.000 |
| Faltantes | 0 |

Cada ciudad del catálogo tiene seis series de 300 meses, equivalentes a 1.800
registros por ciudad. Los conteos se verificaron leyendo las cachés con el validador
existente y comparando su cobertura con el informe del lote. Son datos previamente
obtenidos y reutilizados; no se presentan como descargas nuevas ni como análisis.

Informe local: `data/cache/reports/power-2000-2024-docker.json`, ignorado por Git.
Incluye estados por ciudad, cobertura, fechas y totales auditados. La lista completa
de ciudades y comandos compartibles está en [docs/operations/docker.md](../operations/docker.md).
El contenedor queda iniciado para desarrollo; el despliegue productivo sigue pendiente.

### Contrato operativo y límites

- Período por defecto 2000–2024, configurable; comunidad `AG`, frecuencia mensual y
  las seis variables existentes. Procesamiento secuencial, intervalo mínimo de un
  segundo por defecto y sin reintentos automáticos.
- CLI con selector explícito: `--city`, `--cities`, `--province`, `--region` o `--all`.
  `--dry-run` no consulta NASA ni escribe cachés.
- Caché JSON en `data/cache/power/`, ignorada por Git. Guarda consulta, ubicación,
  procedencia GeoRef, series, unidades, metadatos y `fetched_at` UTC.
- Reutilización hasta `--force` o vencimiento opcional con `--max-age-days`; no se
  supone que NASA nunca revise datos históricos. No se aproxima la ubicación ni
  se comparten entradas entre períodos diferentes.
- Los nulos científicos se conservan y cuentan. Variables/meses ausentes, series
  totalmente nulas, metadatos esenciales ausentes y actualizaciones que pierdan
  valores disponibles impiden sustituir una caché válida. No se mezclan respuestas.
- Un refresco fallido informa error y `cache_preserved`; mantiene la fecha anterior
  y no presenta datos viejos como una descarga nueva.
- Escrituras atómicas; sin bloqueo entre procesos en esta versión. Ejecutar un único
  lote por directorio de caché. Un fallo de escritura se informa como advertencia
  con `cache_written=false` si los datos remotos obtenidos son válidos.
- Para coordenadas libres se exige evidencia de límites oficiales de Argentina.
  **El adaptador real está pendiente**: por defecto se devuelve
  `TerritoryValidationUnavailable` antes de consultar NASA. La arquitectura admite
  incorporar ubicaciones argentinas arbitrarias mediante B18, sin limitarse al
  catálogo ni aceptar una caja rectangular como prueba territorial.

Comandos y ejemplos de uso: [docs/science/bulk-power.md](../science/bulk-power.md).

### API disponible para frontend

Application Factory en `app.py`, Blueprint en `api/routes.py`, sobre de respuestas
en `api/responses.py` y mapeo seguro de errores en `api/errors.py`. Las rutas delegan
validación y adaptación a `services/api_service.py`, que usa los módulos existentes
de ciudades, obtención, caché y proveedor, sin modificar su implementación.

| Método | Ruta | Alcance verificado |
| --- | --- | --- |
| GET | `/api/health` | Estado del proceso HTTP, sin sondeo externo. |
| GET | `/api/variables` | Catálogo del proveedor con unidades y fuentes. |
| GET | `/api/cities` | Ciudades argentinas, filtros `province` y `region`. |
| GET | `/api/cities/{city_id}` | Detalle por ID; 404 para una ciudad inexistente. |
| GET | `/api/regions` | Regiones y conteos derivados del catálogo. |
| POST | `/api/data` | Una ciudad, variables seleccionadas y período; caché prioritaria, `force` opcional. |

Frontend y API comparten origen; CORS permanece desactivado. Las coordenadas libres
siguen rechazadas. La obtención se serializa dentro del proceso; el despliegue
multiproceso permanece pendiente. Los nuevos contratos están en `docs/architecture/api.md`.

Contrato completo, ejemplos JSON, estados HTTP y comandos: [docs/architecture/api.md](../architecture/api.md).

```powershell
.\venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
```

## Pendientes, prioridades y dependencias

**P1:** base necesaria. **P2:** integración y producto. **P3:** complemento.
B01, B02, B03, B04, B05 y B19 están completadas para su alcance de desarrollo actual.
No se afirma un lock de dependencias transitivas ni un despliegue productivo.
B07, B12 y B15 están completadas para análisis exploratorio del catálogo argentino,
según el contrato técnico existente del motor. B06 conserva revisión metodológica
pendiente; no se afirma aprobación del compañero de nuevos métodos. B17 continúa.

| ID | Prioridad | Tarea pendiente | Dependencias y criterio de finalización |
| --- | --- | --- | --- |
| B18 | P1 | Incorporar adaptador real de límites oficiales de Argentina. | Verificar fuente, geometrías y cobertura. Probar interiores, exteriores, costas y fronteras con procedencia/versionado; nunca usar sólo una caja rectangular. |
| B06 | P1 | Revisar criterios científicos con el responsable del motor. | Contrato técnico inspeccionado e integrado (`docs/architecture/integration.md`). Falta precisión completa, coherencia p-valor/significancia/slope_tolerance, revisión conjunta de estacionalidad, autocorrelación, cobertura, centinelas, acumulados y comparaciones múltiples. Bloquea confirmación de hallazgos, no el procesamiento provisional explícito autorizado. |
| B13 | P2 | Completar MODIS histórico e integración de productos; MERRA-2 directo sigue sin cliente. | GLDAS 2.1 y GPM 07 verificados con Giovanni/Earthdata en 25 ciudades. MODIS requiere resultados de las órdenes, validación de colección y QA; métodos nuevos dependen de B06. |
| B14 | P3 | Ampliar SWOT/Hydrocron más allá del piloto fluvial. | Río Chubut verificado: 31 pasos, altura/ancho e incertidumbres. Faltan lagos argentinos con ID verificado y revisión de banderas/metodología; no aplicar el OLS de ciudades. |
| B16 | P2 | Definir investigaciones guiadas argentinas. | Interfaz original, tres misiones, hipótesis y recomendador incorporados desde `origin/datasets-missions`; falta revisión conjunta de recorridos e interpretación científica. |
| B17 | P2 — continua | Ampliar integración y CI. | B02 y módulos incorporados. Mantener pruebas sin red separadas de comprobaciones reales optativas; contratos HTTP, motor y flujo de navegador incorporados; falta CI del equipo. |

No iniciar descargas completas automáticamente. El período 2000–2024 se verificó
con 25 cachés intactas. B18 y la revisión científica de B06 siguen pendientes.
Radar y Fingerprint están implementados como productos provisionales; no se
presentan descubrimientos confirmados ni se aplica un ajuste aún no acordado. El motor y la interfaz se integraron por solicitud
explícita del usuario; no se implementan etapas futuras por iniciativa propia.

## Historial de la etapa Docker inicial y coordinación

Modificados en la etapa Docker: `AGENTS.md`, `docs/project/BACKEND_TASKS.md` y `docs/architecture/api.md`.

Creados en la etapa Docker:

- `Dockerfile`, `compose.yaml` y `.dockerignore`.
- `docs/operations/docker.md`.
- Informe local ignorado: `data/cache/reports/power-2000-2024-docker.json`.

La etapa Docker no editó aplicación, rutas, servicios, proveedor, normalizador,
catálogo, scripts, pruebas ni dependencias anteriores. Las 25 cachés existentes
permanecen intactas. No se realizaron
commits ni push. El motor y el frontend pertenecen a otros integrantes y quedan
fuera de las modificaciones de esta etapa.


## Integración del proyecto completo — 14 de noviembre de 2026

| Tarea | Estado del alcance solicitado | Evidencia |
| --- | --- | --- |
| Diagnóstico y comparación de ramas | Completado | `docs/architecture/integration.md`: HEAD 9066cdd, main d56d8ae y motor en results-charts e33c76d; inventario de ambos Docker/Compose. |
| B07 — adaptador al motor existente | Completado para consultas exploratorias | `services/science/analysis_service.py`; `services/science/trend_analysis.py` idéntico al del compañero; SciPy 1.18.1. No incluye validación metodológica conjunta pendiente de B06. |
| B12 — análisis y comparación | Completado para ciudades del catálogo | `api/routes.py`, errores públicos, unidades/cobertura compatibles y `tests/browser/test_web_integration.py`. Coordenadas libres/regiones arbitrarias pendientes de sus contratos y B18. |
| B15 — frontend conectado | Completado para el flujo actual | `web/routes.py`, `templates/`, `static/js/shared/api.js`; Chrome real mediante `scripts/audit/check_web.py`: datos, gráficos, CSV, comparación y errores sin fallback simulado. |
| Docker unificado | Completado | `Dockerfile`, `compose.yaml`: un servicio Flask, mismo origen, puerto 5000, caché original persistente, estado healthy. |
| Regresión backend y motor | Completada | 104 descubiertas, 103 aprobadas, una NASA de red optativa omitida dentro de Docker; `pip check` correcto. Las 71 pruebas originales no se editaron. |
| Auditoría científica sin nuevas descargas | Completada | `scripts/audit/check_cached_integration.py`: 25 ciudades, 150 series, 45.000 valores y 150 análisis; red NASA bloqueada, hashes y fechas iguales. |

No se modificó `main`, no se hicieron commits ni push ni se eliminaron volúmenes.
El archivo local sin seguimiento preexistente `docs/history/initial-git-status.txt` se conservó.
Los datos sintéticos heredados quedaron identificados y aislados bajo `tests/`.
No se habilitaron fuentes distintas de POWER ni coordenadas libres.

Arranque: `docker compose up -d --build --wait --wait-timeout 60`.
Navegador: **http://127.0.0.1:5000/**. Guía: `docs/operations/docker.md`.
Evidencias locales: `data/cache/reports/web/` e
`data/cache/reports/integrated-cache-audit.json`, ignoradas por Git.


## Resultado común, Fingerprint y Radar provisional — 14 de noviembre de 2026

Etapa autorizada por el usuario a partir de la auditoría de `b4093bc`.

| Componente/tarea | Estado del alcance autorizado | Evidencia |
| --- | --- | --- |
| Resultado común | Implementado, sin un motor duplicado | `services/science/analysis_results.py`, `AnalysisService.results()`; indicador, unidad, ubicación, período, cobertura mensual/anual, estadísticas, hashes y metodología. |
| Precisión y estados | Preparado; entrega completa pendiente del compañero | Estados `valid` (reservado), `provisional`, `insufficient`, `error`; `data_status=valid` no confirma ciencia. Copia las estadísticas actuales y deja `statistics_unrounded=null`; no reconstruye cifras ni cambia el motor. |
| B09 — Fingerprint | Backend v1 implementado y probado; validación científica pendiente | `services/science/fingerprint.py`: seis variables, cuatro principales y dos extremos; compatibilidad descriptiva, sin puntajes ni normalizaciones. |
| B08 — Radar | Backend v1 implementado y probado; descubrimientos confirmados pendientes de B06 | `services/science/radar.py`: familia completa de 150 pruebas, cobertura, errores y exclusiones; ajuste múltiple preparado pero no aplicado. |
| B10 — generador | Implementado y piloto completo ejecutado | `scripts/maintenance/generate_radar.py`; cache-only, dry-run, IDs de estudio/ejecución, fecha UTC, hash de integridad y escritura atómica. |
| B11 — endpoints de producto | Implementados | `GET /api/fingerprint/{city_id}` y `GET /api/radar`; contratos y ejemplos en `docs/architecture/api.md`, `docs/architecture/products.md`, `docs/examples/`. |
| Obtención sin red | Implementada como opción interna explícita | `PowerBulkService.collect_cities(cache_only=True)` y `EarthLensService.get_data(cache_only=True)`; un faltante o caché vencida se informa sin consultar NASA. No se habilita como configuración HTTP. |
| Filtros de Radar | Implementados sin recalcular | Provincia, región, variable, dirección y evidencia. El manifiesto, la familia y el ajuste pendiente se conservan íntegros al filtrar. |
| Verificación | 134 aprobadas, una NASA de red omitida | 135 descubiertas en Docker, `pip check` correcto, 31 pruebas nuevas de contrato, caché, errores, compatibilidad, CLI, atomicidad y filtros. Flujos anteriores comprobados en Chrome con cero errores JavaScript. |

Piloto 2000–2024: 25 ciudades, 150 series reales y 45.000 valores mensuales.
25 aciertos de caché, **150 resultados provisionales**, 48 señales nominales
provisionales, 102 sin señal nominal, cero errores, cero exclusiones y **cero
hallazgos confirmados**. Distribución de señales nominales: T2M 13, T2M_MAX 11,
T2M_MIN 7, PRECTOTCORR 8, RH2M 4 y WS2M 5. No son resultados corregidos por
comparaciones múltiples ni evidencia causal.

Se ejecutó la generación bloqueando solicitudes externas y `JsonCache.write`.
Los 150 registros persistidos coincidieron con una segunda ejecución del análisis
(excluyendo la fecha de ejecución); para Comodoro Rivadavia, Mendoza y Posadas se
contrastaron estadísticas con el análisis anterior y compatibilidad de perfiles.
Los 25 JSON originales conservaron sus hashes y fechas. El motor, `static/` y
`templates/` también conservaron sus hashes.

Artefacto derivado local ignorado por Git: `data/cache/radar/latest.json`.
Ejemplos reales versionables: tres perfiles completos y Radar Cuyo/T2M en
`docs/examples/`. Cada resultado incluye coordenadas y enlaces a las páginas
existentes. No se modificaron frontend, motor estadístico, dependencias, Docker,
proveedores nuevos ni bases de datos. No se hicieron commits ni push ni cambios
en `main`.

Pendientes de coordinación: B06 antes de confirmar resultados o aplicar ajuste;
B18 para coordenadas libres; nuevas interfaces de Radar/Fingerprint y correcciones
de la interfaz detectadas en la auditoría (respuesta del comparador asociada al
selector cambiante, ampliación automática de años), sólo con autorización del
responsable del frontend. B13/B14 y el despliegue productivo permanecen pendientes.

```powershell
docker compose exec -T backend python -m scripts.maintenance.generate_radar --dry-run
docker compose exec -T backend python -m scripts.maintenance.generate_radar
Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/mendoza?start_year=2000&end_year=2024'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar?region=Cuyo&variable=T2M'
```

## FASE 1 — interfaces Radar y Fingerprint verificadas

Autorización posterior del usuario para implementar ambas interfaces y compartir
la navegación. Se inspeccionaron arquitectura, contratos, documentación y estado
Git antes de editar. Rama: `feature/backend-api`, base `87db1b4`; no se modificó
`main`, no se hicieron commits ni push. La fase no agrega proveedores científicos.

| Alcance | Estado comprobado | Archivos/evidencia |
| --- | --- | --- |
| Earth Radar | Funcional con datos reales | `/radar`, mapa Leaflet con 25 marcadores, cinco filtros, resumen global, tarjetas y orden por ciudad/indicador/p nominal; magnitud sólo con una variable. Enlace a Resultados y leyenda sin puntajes. |
| Earth Fingerprint | Funcional con datos reales | `/fingerprint`, selector argentino, seis tarjetas/gráficos históricos anuales, principales/extremos, fuentes y metodología. Comparación descriptiva con unidades y compatibilidad estricta; sin gráfico radial. |
| Navegación | Integrada en todas las páginas | Parcial Jinja único; conserva marca, estilos y el enlace Inicio → Explorador con la ciudad seleccionada. |
| Selecciones rápidas | Verificadas en Chrome | AbortController y secuencia; respuestas tardías no reemplazan ciudades, filtros, títulos ni gráficos actuales. Probado con y sin cancelación. |
| Carga/error/vacío | Verificados | Estados visibles, reintentos, ocultación de resultados previos; filtro real de confirmados sin resultados. Fixtures de 503, incompatibilidad e indicador dinámico insuficiente sólo en navegador. |
| Responsive y enlaces | Verificados | 1440, 1280, 820 y 390 px sin desborde horizontal; menú móvil, comparación móvil, enlaces al Explorador, Resultados y Comparador. |
| Regresión sin red | 137 aprobadas, una remota optativa omitida | Suite completa: 138 descubiertas en Docker; las 134 anteriores más tres pruebas nuevas. Tras el ajuste final de navegación se repitieron satisfactoriamente los tres contratos de páginas. |
| Navegador | 9 grupos de verificaciones nuevas y 10 anteriores aprobados | `scripts/audit/check_product_pages.py` y `scripts/audit/check_web.py`, Chrome real, cero errores JavaScript. Capturas inspeccionadas en escritorio y móvil. |
| Integración científica sin descargas | 25 perfiles, 150 análisis y 45.000 valores mensuales | Cliente Flask dentro de Docker con `requests.sessions.Session.request` y `JsonCache.write` bloqueados. Cero consultas NASA y cero escrituras; estadísticas, series, cobertura, indicador, unidad, IDs y procedencia coinciden con el estudio persistido. |
| Preservación | Comprobada por SHA-256 | Las 25 cachés, `data/cache/radar/latest.json` y `services/science/trend_analysis.py` permanecen idénticos. No se regeneró el estudio. |
| Docker | Reconstruido y saludable | Mismo servicio, puerto y bind mounts; sin cambios en Dockerfile, Compose, volúmenes, dependencias ni motor. |

Resultados reales del estudio **existente** mostrado por la interfaz: 25 ciudades,
150 resultados provisionales, 48 señales nominales, 102 sin señal nominal,
cero errores/exclusiones y **cero descubrimientos confirmados**. Son p-valores sin
ajuste; no se ejecutó un nuevo estudio ni se amplió su familia.

Ejemplos comprobados de T2M para 2000–2024 (unidad NASA `C`; cobertura 25/25 años,
300/300 meses en cada ciudad):

| Ciudad | Cambio por década (C/década) | IC95% de pendiente (C/año) | p nominal | Evidencia |
| --- | --- | --- | --- | --- |
| Comodoro Rivadavia | 0,2464 | [0,00186; 0,04741] | 0,03521 | Señal nominal provisional |
| Mendoza | 0,3412 | [0,00405; 0,06419] | 0,02787 | Señal nominal provisional |
| Posadas | 0,267 | [-0,00309; 0,0565] | 0,0766 | Sin señal nominal |

### Archivos de la fase

Creados:

- `templates/components/_navigation.html`, `templates/components/_provisional_notice.html`,
  `templates/pages/radar.html`, `templates/pages/fingerprint.html`.
- `static/css/pages/products.css`, `static/js/products/products.js`, `static/js/products/radar.js`,
  `static/js/products/fingerprint.js`.
- `tests/browser/test_product_pages.py`, `scripts/audit/check_product_pages.py`.

Modificados:

- `web/routes.py`: dos páginas nuevas; `static/js/shared/api.js`: señal de cancelación
  opcional, conservando las llamadas anteriores.
- `templates/layouts/base.html`, `templates/pages/index.html`, `templates/pages/explorer.html`,
  `templates/pages/results.html`, `templates/pages/compare.html`: inclusión de navegación
  compartida; contenido y lógica de las páginas conservados.
- `static/css/global/styles.css`: ajuste de la marca en pantallas pequeñas.
- `AGENTS.md`, `docs/project/BACKEND_TASKS.md`, `README.md`, `docs/architecture/api.md`, `docs/operations/docker.md`,
  `docs/architecture/products.md`: estado, contratos web, limitaciones y ejecución.

Evidencias locales ignoradas, sin reemplazar informes anteriores:

- `data/cache/reports/interfaces-phase1/20261114T212310541717Z/`: informe de
  nueve grupos de comprobaciones, hashes, origen de los 25 perfiles y capturas
  reales de ambas interfaces, incluida comparación móvil.
- `data/cache/reports/interfaces-phase1/20261114T212313856622Z/legacy/`:
  regresión de los diez recorridos anteriores y sus capturas.

### Ejecución y límites

```powershell
docker compose up -d --build --wait --wait-timeout 60
# Abrir http://127.0.0.1:5000/radar
# Abrir http://127.0.0.1:5000/fingerprint?city_id=comodoro-rivadavia
# Comparar http://127.0.0.1:5000/fingerprint?city_id=mendoza&city_id_b=posadas

docker compose exec -T -e EARTHLENS_POWER_LIVE=0 backend python -B -m unittest discover -s tests -v
.\venv\Scripts\python.exe -B scripts/audit/check_product_pages.py
.\venv\Scripts\python.exe -B scripts/audit/check_web.py
```

La comprobación de navegador requiere Playwright y Chrome en el host. La aplicación
no requiere Node ni Playwright. Sus recursos CDN y teselas requieren Internet.
Si falta el artefacto Radar, la interfaz muestra el error sin generar ni descargar
datos. Fingerprint usa el período cacheado 2000–2024 y no agrega controles para
descargas de períodos nuevos. Las tarjetas y gráficos se generan desde el contrato
recibido para admitir indicadores adicionales en fases futuras.

Pendientes científicos: validación metodológica B06, autocorrelación/supuestos OLS,
cobertura, ajuste múltiple, entrega de precisión completa y agregación anual
acordada, especialmente precipitación. No se modificó ninguno de esos criterios.
La comparación no prueba diferencias significativas entre ciudades. Continúan
pendientes el adaptador territorial B18 y el despliegue productivo.

**Estado al cierre de las interfaces del 14/11 — fases 2–7 no iniciadas**: arquitectura multiproveedor, consultas reales GLDAS,
MODIS, GPM y SWOT/Hydrocron e integración general se abordarán en ese orden tras
esta fase. No hay nuevas variables habilitadas ni ampliación automática de Radar.

## Historial inicial de recuperación y primeras fuentes multiproveedor — 15/11/2026

Base inspeccionada: `e127aad`, rama `feature/backend-api`. Esta sección reemplaza
el estado futuro de las fases 2–4 del cierre anterior. No se hicieron commits ni
push; se conservaron motor, frontend, proveedor POWER, normalizador y caché histórica.
Guía completa, fuentes oficiales y comandos: [docs/science/scientific-sources.md](../science/scientific-sources.md).

| Fase / prioridad | Estado comprobado | Evidencia y dependencia |
| --- | --- | --- |
| 1 — Recuperación POWER, P0 | Completada | Docker Desktop iniciado; bind mount persistente existente, sin observaciones recuperables. Descarga real de 25 ciudades, seis variables por petición, 2000–2024. |
| 1 — Cobertura y unidades, P0 | Comprobadas | 150 series, 45.000 registros disponibles, 300 meses por serie, cero nulos/fallos. Unidades `C`, `mm/day`, `%`, `m/s`, fuentes NASA conservadas. |
| 1 — Inicialización reproducible, P0 | Implementada y comprobada | `scripts/maintenance/initialize_data.py`; repetición: 25 aciertos de caché y cero descargas. Informes únicos, falla con código 1 si faltan datos/análisis. |
| 1 — Radar, P0 | Regenerado desde observaciones reales cacheadas | 150 análisis provisionales, 48 señales nominales y cero confirmados. Misma familia POWER; ninguna variable MODIS añadida. |
| 2 — Contrato y almacenamiento nativos, P1 | Implementados para proveedores puntuales | `services/science/scientific.py`, cachés separadas por proveedor/producto/revisión/variable, cobertura, QA, procedencia e integridad SHA-256. POWER delegado al servicio existente. SWOT necesitará geometría/identidad propia. |
| 2 — Catálogo dinámico y API aditiva, P1 | Implementados y verificados | `api/scientific.py`: `/api/science/variables` sólo publica datos con valores reales en cachés validadas; `/api/science/data` conserva frecuencias nativas. Endpoints anteriores intactos. |
| 3 — GLDAS, P1 | Parcial; bloqueada la extracción por acceso Earthdata | CMR verificó `GLDAS_NOAH025_M` 2.1 y Cloud OPeNDAP. Descriptor real: HTTP 401. Servidor antiguo: 410. `gldas.py` sólo descubre/prueba acceso; cero observaciones; variables deshabilitadas. |
| 4 — MODIS, P1 | Adaptador y piloto real verificados; ampliación pendiente | MOD13Q1/ORNL, NDVI/EVI, tres ciudades, 2024; 6 series, 138 registros, 56 aceptados y 82 excluidos QA. Sin convertirlos a meses ni inventar valores. |
| 4 — Colección y representatividad, P1 | Revisión pendiente | Catálogo documental ORNL declara 6.1, pero REST no identifica la colección por observación. Se mantiene versión científica `null`. QA aceptada por índice: Mendoza 2/23, Comodoro 7/23, Posadas 19/23. |
| 5–6 — GPM y SWOT, P2 | No implementadas en esta etapa | Verificar IMERG Final mensual V07 y Hydrocron; autenticación/cobertura/geometría propias. |
| 7 — Integración general, P2 | Pendiente | Radar/Fingerprint/motor conservan las seis variables POWER. Las series nativas nuevas llevan `analysis.enabled: false`; faltan acuerdos metodológicos y coordinación de interfaces ajenas. |

### Pruebas y preservación

- Suite final en Docker: **155 descubiertas, 154 aprobadas y una prueba remota
  optativa omitida**. Las 137 originales siguen aprobadas; 17 nuevas verifican
  almacenamiento, validación, API, escala/QA, partición ante HTTP 502, GLDAS sin
  credenciales persistidas e inicialización con fallos.
- Diez solicitudes del cliente Flask con datos reales y red bloqueada: seis
  endpoints originales, Radar/Fingerprint y dos endpoints nuevos, todos HTTP 200;
  las cachés inspeccionadas conservaron sus hashes. Informe local
  `data/cache/reports/api-multisource-check.json`.
- SHA-256 de las 25 cachés POWER sin cambios después de la recuperación y la
  repetición. Motor y todos los archivos de frontend idénticos a la inspección
  inicial; no se modificaron dependencias, Dockerfile ni Compose.
- Imagen Docker reconstruida satisfactoriamente; persistencia en el mismo montaje
  `data/cache`. No hay servicios adicionales ni credenciales dentro de la imagen.
- Contenedor recreado y saludable; HTTP real devolvió ocho variables verificadas
  (seis POWER y dos MODIS), 25 ciudades y cinco regiones. Las series MODIS de
  Posadas devolvieron 23 registros por índice con la cobertura QA esperada.
- Repetición del CLI MODIS con red y escrituras de observaciones bloqueadas:
  tres ciudades exitosas; los 31 archivos POWER/MODIS conservaron sus hashes.
  Informe `scientific-modis-20261115T130541Z-7c19a03f.json`; no es una descarga nueva.

Informes reales conservados en `data/cache/reports/` (ignorados por Git):
`initialization-2000-2024.json` (25 descargas),
`initialization-2000-2024-bbb23b72ed.json` (25 aciertos),
`scientific-modis-20261115T124457Z-7dc51607.json` (fallos del primer intento) y
`scientific-modis-20261115T130201Z-ad814caa.json` (piloto completo).
Los diagnósticos públicos se guardan por separado bajo `science/discovery/` y no
cuentan como observaciones disponibles. No se probó acceso GLDAS autenticado.

### Siguiente trabajo concreto y dependencias

1. Con Earthdata configurado localmente, repetir `--provider gldas --probe` y
   verificar la extracción de un píxel real antes de implementar/publicar las cinco
   variables. Luego ejecutar Mendoza, Comodoro y Posadas; sólo con éxito extender a
   25 ciudades. Un descriptor autenticado no completa esta tarea.
2. Revisar colección y representatividad de píxeles MODIS con la cobertura QA
   obtenida; ampliar período/ciudades mediante CLI reutilizando las respuestas.
   El histórico 2000–2024 de las 25 ciudades MODIS todavía no está descargado.
3. Abordar GPM y SWOT con productos independientes y procedencia verificable.
4. Coordinar con B06 la agregación y los criterios de uso de las nuevas series,
   antes de integrar análisis, visualizaciones o ampliar la familia de Radar.

### Historial del diagnóstico GLDAS con token en otra sesión PowerShell — 15/11/2026

- El usuario verificó que su terminal pasa `EARTHDATA_TOKEN` a Docker. El proceso
  del agente y el servicio HTTP no heredan esa variable; las pruebas autenticadas
  se ejecutaron mediante el comando `docker compose exec -T -e EARTHDATA_TOKEN`.
- CMR confirmó nuevamente el producto/versión. Las consultas de descriptor DAP2
  y DAP4 recibieron **HTTP 400**, no un descriptor científico. El mensaje público
  de Tomcat rechazó la cabecera `Authorization` por incumplimiento de RFC 9112.
  Esto no verifica vigencia/permisos del token ni acceso a observaciones GLDAS.
- Se amplió `services/providers/gldas.py` con diagnóstico público redactado,
  exclusión de formularios/scripts HTML, intento DAP4 acotado ante HTTP 400 y
  validación local del formato Bearer antes de la red. No se guarda el token.
- `scripts/data/fetch_science.py --probe` devuelve errores de configuración como JSON
  controlado; se documentó carga del token con entrada oculta en PowerShell.
  Ver [docs/science/scientific-sources.md](../science/scientific-sources.md).
- `tests/providers/test_gldas_provider.py`: ocho pruebas, cinco adicionales. Suite completa
  Docker: **160 descubiertas, 159 aprobadas y una remota optativa omitida**.
  Backend saludable y las 31 cachés POWER/MODIS conservan sus hashes.
- **GLDAS sigue parcial y deshabilitado: cero observaciones, extractor pendiente**.
  Falta obtener un descriptor válido y verificar una extracción puntual real.
  El resultado del diagnóstico con la nueva validación local queda pendiente del usuario.
  No se ampliaron MODIS, GPM, SWOT, la familia de Radar ni las interfaces durante
  este diagnóstico, conforme al orden solicitado: primero verificar GLDAS.
- No se hicieron commits/push ni se modificaron archivos del motor o frontend.

#### Validación local posterior

El usuario recibió `credential_format_valid: false`; esa ejecución fue rechazada
antes de acceder a la red. Se añadieron indicadores de espacios, comillas, prefijo
Bearer, controles, Unicode y marcas de pegado, sin devolver fragmentos del token.
Se documentó la asignación local desde portapapeles como alternativa a `Read-Host`.
Pruebas GLDAS específicas: **10 aprobadas**, incluidas dos nuevas sobre el
diagnóstico de formato. La última suite completa anterior conserva su resultado
de 159 aprobadas y una omitida; esta comprobación específica no se presenta como
una nueva ejecución completa. GLDAS continuaba sin datos verificados en ese diagnóstico.

## Continuación verificada después de autorizar Earthdata — 15/11/2026

Este apartado reemplaza los estados iniciales de acceso que figuran en el
historial anterior. Los errores 400/401/403 no describen el estado actual de GLDAS.

| Fase | Estado real | Evidencia y cantidades |
| --- | --- | --- |
| 1 — recuperación | Completada | POWER: 25 ciudades, 150 series y 45.000 registros mensuales 2000–2024, sin nulos. Inicializador reproducible y Radar regenerado sin ampliar la familia. |
| 2 — arquitectura | Implementada para datos nativos | `services/science/scientific.py`, cachés por proveedor/producto/revisión/variable, catálogo derivado de datos verificados y contratos HTTP aditivos. Identidad, SHA-256, unidades y refrescos degradados comprobados. |
| 3 — GLDAS | Histórico verificado | `gldas.py`, `gldas_points.py`, `giovanni.py`: 3 ciudades NetCDF 2024 (15 series/180 registros) y 25 ciudades Giovanni 2000–2024 (125 series/37.500 registros válidos). Mismo producto 2.1; no sumar pilotos duplicados. |
| 4 — MODIS | Piloto verificado; histórico solicitado al servicio externo | REST: 3 ciudades 2024, 6 series/138 registros, 56 aceptados y 82 excluidos QA. Se solicitaron 25 órdenes 2000–2024: 24 identificadores guardados; Mendoza recibió HTTP 200 pero su identificador no se conservó y falta recuperar el enlace, sin reenvío. Todavía sin CSV histórico validado. |
| 5 — GPM | Histórico verificado | `GPM_3IMERGM.07`, IMERG Final mensual por Giovanni: 25 ciudades, 25 series/7.500 registros 2000–2024, sin nulos, `mm/hr`. Comparación descriptiva con POWER mediante conversión explícita a `mm/day`. |
| 6 — SWOT | Piloto fluvial verificado; ampliación pendiente | Hydrocron, río Chubut `65341000051`, producto D/SWORD 17b, 31 pasos en 2024, altura/ancho en metros: 62 valores numéricos, incertidumbres, banderas y geometría. Lagos argentinos todavía sin ID/datos verificados. |
| 7 — interfaces | Integración descriptiva parcial verificada | Panel aditivo en Explorador, Comparador, Radar, Fingerprint y Modo detective, más `/sources`. Gráficos nativos, QA/metadatos, comparación y recorrido histórico. No amplía métodos, misiones, indicadores ni familia de Radar. |
| 7 — Time Machine | Pendiente de adaptar contrato | Rama `origin/feature/earth-time-machine` 8a39937 inspeccionada, sin fusionar. Espera otro servidor/API, funciones ausentes del motor local y un camino de muestras/coordenadas libres. Ver `docs/architecture/time-machine-integration.md`. |
| 7 — Earth Connections | Pendiente de implementación del equipo | El usuario confirmó que todavía no existe; contrato científico disponible para conectarla posteriormente. |

Los históricos mensuales principales suman **300 series y 90.000 registros**
entre POWER, GLDAS y GPM. El piloto MODIS y las observaciones SWOT se informan
separadamente, con sus frecuencias y calidad. Los pilotos GLDAS/GPM solapados y
las proyecciones POWER no se suman como observaciones nuevas. El catálogo puede
mostrar variantes de acceso de una misma variable; no equivalen a variables nuevas.

Informes reales conservados bajo `data/cache/reports/`:

- GLDAS puntual: `scientific-gldas-20261115T143415Z-d2844834.json`.
- GLDAS histórico: `scientific-gldas-20261115T144853Z-63b9c121.json`.
- GPM histórico: `scientific-gpm-20261115T145756Z-a7cdd8ef.json`.
- MODIS piloto: `scientific-modis-20261115T130201Z-ad814caa.json`.
- SWOT original: `data/cache/science/discovery/hydrocron-chubut-2024.json`.

### Archivos incorporados o modificados

- Núcleo y acceso: `services/science/scientific.py`, `services/science/scientific_compare.py`,
  `services/science/hydrology.py`, `services/providers/{gldas,gldas_points,giovanni,modis}.py`,
  `api/scientific.py`, `api/errors.py`, `app.py`, `data/water_features.json`.
- Comandos: `scripts/{initialize_data,fetch_science,probe_giovanni,order_modis,audit_science,check_scientific_pages,check_scientific_cache}.py`.
- Interfaz aditiva: `templates/{_scientific_panel,scientific}.html`,
  `static/js/products/scientific.js`, `static/css/components/scientific.css`, enlace del panel en
  `templates/components/_navigation.html` y ruta `/sources` en `web/routes.py`.
- Ejecución/documentación: `Dockerfile`, `compose.yaml`, `AGENTS.md`, este archivo,
  `docs/{api,docker,scientific-sources,time-machine-integration}.md`.
- Pruebas nuevas: `tests/test_{scientific,scientific_compare,gldas_provider,gldas_points,giovanni_provider,giovanni_probe,hydrology,initialize_data,modis_orders}.py`.

El motor `services/science/trend_analysis.py`, el proveedor/normalizador POWER, los
archivos originales de cada página y las pruebas originales se conservan.
El correo sólo se envió en memoria a ORNL; tokens y contactos no se escriben en Git.
No se hicieron commits ni push.

### Verificación y siguientes dependencias

La última suite completa ejecutada en Docker descubrió **193 pruebas**:
**192 aprobadas y una de red optativa omitida**; `pip check` sin conflictos.
Después se comprobó el rechazo de colecciones MODIS no admitidas sin perder
cachés anteriores: sus cuatro pruebas específicas pasaron.
Chrome pasó nueve grupos de verificaciones con cachés reales, sin errores JavaScript:
paneles en cinco herramientas, GLDAS, conversión POWER–IMERG, MODIS con huecos QA,
SWOT con incertidumbre, histórico sin nuevas solicitudes, vista móvil y respuesta
tardía descartada. Se conservaron hashes de las 25 cachés POWER, Radar y motor.
Informe final: `data/cache/reports/scientific-pages/20261115T155859Z/report.json`.
También pasaron los nueve grupos originales Radar/Fingerprint y los diez grupos
de `scripts/audit/check_web.py`, sin errores JavaScript. Informe de producto:
`data/cache/reports/interfaces-phase1/20261115T154506468804Z/`.
La imagen se reconstruyó y Compose quedó saludable en `127.0.0.1:5000`, con el
mismo montaje persistente. Se activó recarga de plantillas sólo en desarrollo,
sin depurador interactivo. El inventario cache-only no detectó archivos inválidos.
El escaneo de 646 archivos de código/datos no encontró el contacto autorizado ni
cadenas con formato de JWT. No se imprimió ni se almacenó el token.

Se corrigió además la selección de períodos parciales en la capa nativa: puede
filtrar fechas de una extracción más amplia sin nuevas consultas ni cambios de
unidades, QA o fecha de obtención. No combina versiones, políticas o vías de acceso.
POWER delega en su servicio original usando el período fuente válido y proyecta
la selección; sus cachés originales y contratos HTTP previos se conservan.
Dos pruebas incluidas en la suite comprueban esa reutilización y preservación.
La verificación real con red bloqueada también pasó: tres ciudades, GLDAS y
comparación POWER–GPM, 72 meses por serie, hashes protegidos conservados.
Comando reproducible: `scripts/audit/check_scientific_cache.py`.

El último sondeo ORNL conservó 24 órdenes con identificador, todas con resultados
todavía HTTP 404, y la orden de Mendoza con HTTP 200 de envío e identificador
pendiente. Cero históricos MODIS publicados; no se cuentan pedidos como datos.
Inventario local sin cachés inválidas: `data/cache/reports/scientific-inventory-20261115.json`.

Prioridad inmediata: recuperar el enlace de Mendoza y consultar las órdenes ORNL
sin reenviarlas; validar CSV/colección/píxel/fechas/QA antes de habilitar el histórico.
Después, coordinar la adaptación de Time Machine y la metodología de nuevas
variables con B06. Lagos SWOT requieren identificadores oficiales y consultas reales.
Connections depende de su implementación. B18, CI, MERRA-2 directo, TimesFM y el
despliegue productivo siguen pendientes; no se presentan como trabajos terminados.

## Merge autorizado de origin/main — 15/11/2026

Se combinaron `feature/backend-api` `80925bf` y `origin/main` `ce9a1e2`, con
19 conflictos resueltos. El merge se prepara **sin commit ni push** por la
restricción vigente. Respaldo: `backup/backend-before-main-20261115-133944`.
Decisiones y comandos: [docs/history/merge-main.md](../history/merge-main.md).

- Se mantienen Application Factory, Blueprints, API, proveedores, dependencias
  verificadas, Docker, puerto 5000 y todas las vistas anteriores. Los cambios
  de main que eliminaban Resultados/Comparador no se aplican sobre esas vistas.
- El motor incorpora las funciones aditivas del compañero; todo el código
  anterior se conserva sin cambios. Radar mantiene 150 pruebas y Fingerprint
  sus seis indicadores. No se implementa otra regresión ni se amplía su familia.
- Time Machine: `/time-machine`, GET/POST `/api/time-machine`, adaptador
  `services/workspace/time_machine_service.py`, cachés POWER por ciudad y período, metadata,
  procedencia, mapa regional e interpretación provisional. Sin consultas NASA al
  navegar, muestras, coordenadas libres ni ajustes artificiales de cuadrantes.
- Las muestras y suites del servidor anterior se conservan como referencias de
  migración en `tests/statistics_fixtures/main_legacy/`; no se contabilizan como
  pruebas aprobadas del nuevo servidor. Se agregan ocho pruebas Flask del
  contrato integrado y un verificador de navegador `scripts/audit/check_time_machine.py`.
- `compose.yaml` continúa como configuración activa; `compose.legacy.yaml` es un
  alias opcional del mismo servicio. Los descriptores Cloud Run/Vercel recibidos
  no implican despliegue verificado ni autorización para publicar.

Antes del merge se respaldaron 515 archivos locales, sin POWER ni Radar. Sus
hashes se conservaron. Se apartaron las cachés entrantes y se validaron 25 POWER
2000–2024: 150 series, 45.000 registros válidos, cero faltantes. Los 516 valores
solapados con las proyecciones locales coinciden exactamente; se recuperaron
esas copias sin solicitudes nuevas a NASA y permanecen fuera de Git.
Informe: `data/cache/reports/main-power-cache-validation.json`.
Radar se regeneró cache-only: 150 análisis provisionales, 48 señales nominales,
cero descubrimientos confirmados. GLDAS, GPM y MODIS originales se conservaron.

La ampliación de Time Machine a fuentes nuevas, áreas reales y coordenadas libres
sigue pendiente de contrato/metodología y B18. B06, Connections, entrega MODIS y
despliegue productivo conservan sus dependencias previas. `services/geography/geography.py`
no se modificó durante este merge.

Verificación final de la combinación:

- Docker: **201 pruebas descubiertas, 200 aprobadas y una NASA de red optativa
  omitida**. `pip check` sin conflictos. Se conservan las 193 pruebas anteriores.
- Chrome: 10 grupos del flujo anterior, 9 de Radar/Fingerprint, 9 del panel
  científico y 5 de Time Machine, sin errores JavaScript. La prueba de Time
  Machine comprueba respuesta real, dos gráficos, cambio de ciudad, móvil,
  deslizador sin nuevas solicitudes y 503 sin respaldo.
- Los 515 archivos anteriores conservan sus hashes al cierre. Una proyección
  POWER equivalente creada durante la verificación se restauró desde el respaldo
  para conservar también su procedencia original; las series y unidades coincidían.
- Radar/Fingerprint: `data/cache/reports/interfaces-phase1/20261115T170911757725Z/`.
  Panel científico: `data/cache/reports/scientific-pages/20261115T171023Z/report.json`.
  Capturas Time Machine: `data/cache/reports/time-machine-merge-{desktop,mobile}.png`.
- Cero archivos de caché añadidos al índice; cero conflictos Git pendientes.
  No se hizo commit, push ni despliegue. La confirmación del merge sigue pendiente.
- Se bloquea el caso degenerado de dos épocas constantes distintas: el helper
  heredado devuelve un p-valor fijo allí, y el adaptador devuelve 422 en vez de
  publicarlo como significancia calculada. No se modificó el motor del compañero.

## Actualización de main — proyecciones y Gunicorn

El usuario confirmó el merge anterior en `9c1ee9f` y autorizó completar el nuevo
merge de `origin/main` `4157789`, sin push. Se resolvieron seis conflictos.
Se incorporan `services/prediction/forecast.py`, adaptador de caché por ciudad, endpoint
`/api/forecast`, panel predictivo y arranque Gunicorn respetando `PORT`.
Las proyecciones son OLS/t de Student provisionales; no TimesFM ni observaciones
NASA futuras. No se usan series arbitrarias del cliente ni inferencias causales;
la revisión y calibración siguen pendientes de B06.

Resultado: **210 pruebas descubiertas, 209 aprobadas y una de red omitida**;
Gunicorn health 200 y dependencias sanas. Una comprobación breve del panel y
recálculo pasó sin errores JavaScript, sin repetir suites largas de navegador.
POWER/Radar se recuperaron de copias locales verificadas, sin descargas nuevas.
Las 542 cachés/reportes previos se conservaron. Detalles: [merge-forecast.md](../history/merge-forecast.md).


## Restauraci?n autorizada de main ? 15/11/2026

El usuario autoriz? restaurar y publicar `feature/backend-api` (`529c7a9`) sobre
el `main` reemplazado por pushes cruzados (`56c5e1e`). Se usa un commit nuevo,
sin force-push ni reescritura del historial. Se mantienen los helpers de despliegue
validados en `deployment/cloud-run` y se recupera la configuraci?n Docker estable.
Los datos cient?ficos y la base local se conservan fuera del seguimiento de Git.

Verificaci?n: imagen de la restauraci?n construida, **254 pruebas Docker sin red
ejecutadas: 253 aprobadas y una NASA live optativa omitida**. Seis rutas HTTP
aprobadas en `PORT=8080`, mapa/timeline presentes y JavaScript igual al local.
Las seis pruebas de publicaci?n y rollback usan Google Cloud simulado.

La construcci?n/activaci?n real de Cloud Run, la revisi?n de sus triggers y la
migraci?n de almacenamiento y monitor permanecen pendientes de acceso y operaci?n
en la nube. El push del c?digo no equivale a una verificaci?n del despliegue.
Detalles y comandos: [docs/history/restore-main.md](../history/restore-main.md).

### Publicación automática verificada

La restauración se publicó en main como `ba8ea3a`. El trigger existente
`cloudrun-earthlens-pp-us-central1-Arbitta-Space-Apps-mhin` completó Pull, Build,
Push y Deploy correctamente, con build `76528ae7-98ea-442e-86c5-988baf2a959a`.
El destino automático es **earthlens-pp**, no el servicio anterior **earthlens**.

URL vigente: <https://earthlens-pp-224139449590.us-central1.run.app/>.
Verificados en la URL pública: raíz, health y JavaScript con HTTP 200; hash de
JavaScript igual a localhost; Chrome con mapa/timeline, frame de pronóstico real,
vista móvil y cero errores JavaScript. La URL sin `-pp` sigue sirviendo otro
despliegue. No se modificó ese servicio ni su tráfico.

Se preservaron los hashes de los 684 archivos locales de caché/base. Las
dependencias de persistencia y migración de datos a la nube siguen pendientes.
