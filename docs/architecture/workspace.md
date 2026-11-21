# EarthLens: interfaz geotemporal y planificación

La [corrección prioritaria vigente](time-machine-correction.md) sustituye la primera
composición visual: abrir `/` lleva al mapa directamente, con timeline única y
paneles flotantes. Usar `GET /api/workspace/frame` para sincronizar una fecha y
variable con el producto real disponible; el contrato científico anterior se conserva.

Implementación de desarrollo del 15 de noviembre de 2026, sobre
`feature/backend-api` (`5f7fe09`). No se publicaron servicios ni se hicieron commits.
Estado por fase y pendientes: [docs/project/EARTHLENS_ROADMAP.md](../project/EARTHLENS_ROADMAP.md).

## Ejecución y persistencia

```powershell
docker compose up -d --build backend
# Abrir http://127.0.0.1:5000/time-machine
docker compose exec -T backend python -m unittest discover -s tests
docker compose exec -T backend python -m scripts.maintenance.monitor_events --once
# Monitoreo independiente opcional, también con el navegador cerrado:
docker compose --profile monitoring up -d monitor
docker compose logs --tail 30 monitor
# Detener sólo el proceso de monitoreo:
docker compose --profile monitoring stop monitor
```

`./data/cache` conserva las observaciones y los derivados. `./data/runtime`
conserva SQLite (`earthlens.sqlite3`); ambos se montan con escritura, no se copian
a la imagen ni se versionan. El código continúa montado como sólo lectura.
No usar `down -v`. El monitor hereda los montajes y configuración del backend,
no publica puertos y usa una concesión temporal en SQLite para coordinar procesos.
La imagen usa Python 3.12-slim, UID 10001 y límite Compose de 1 GiB.

SQLite aplica migraciones versionadas (`PRAGMA user_version`) al primer acceso,
en una transacción; rechaza versiones futuras. Un respaldo debe incluir la base
con el servicio detenido o realizarse mediante la API de backup SQLite. Las
preferencias, ubicación descriptiva y perfil de actividad se guardan dentro del
evento; snapshots, evaluaciones, notificaciones y ejecuciones tienen tablas propias.
El incidente público curado vive en el catálogo de código, no en una tabla editable.

Las sesiones de desarrollo usan una clave aleatoria al iniciar el proceso; reiniciar
o recargar Python cierra las sesiones, pero conserva usuarios y eventos. Para una
instalación estable configurar `EARTHLENS_SECRET_KEY` como secreto externo, y en
HTTPS `EARTHLENS_SESSION_COOKIE_SECURE=true`. No pegar claves en documentos/Git.
La cookie es HttpOnly y SameSite=Lax. No hay recuperación de contraseña ni correo.

Compose transmite `EARTHLENS_SECRET_KEY`, `EARTHLENS_WEATHER_COMMERCIAL` y
`OPEN_METEO_API_KEY` desde el entorno del host, sin escribir sus valores en archivos.
Una clave de sesión vacía usa una aleatoria de desarrollo; nunca una clave vacía.

En Cloud Run, el disco del contenedor es efímero: **esta configuración SQLite local
no permite declarar listo un despliegue multiinstancia**. Se requiere PostgreSQL
administrado, migración de persistencia, almacenamiento de cachés compartido,
Secret Manager y un trabajo de Cloud Run invocado por Cloud Scheduler (u otro
scheduler), además de configurar licencias comerciales. No se desplegó ni contrató
infraestructura. El monitor no usa un scheduler interno de Flask.

## Interfaz y tipos temporales

`/time-machine` es el espacio unificado: mapa Leaflet, catálogo de ciudades,
fuentes, selección múltiple/provincia/región/polígono, gráficos Chart.js, inspector,
calendario, eventos, notificaciones y línea temporal. `/cities/{city_id}` reutiliza
la misma plantilla con el perfil abierto. `/my-space` abre eventos. El Laboratorio
conserva Explorador, Radar, Fingerprint, Comparador y Detective.
La interfaz original del equipo sigue en `/time-machine/legacy`.

El polígono selecciona **centroides del catálogo**, no promedia superficies, no
valida pertenencia territorial y no habilita coordenadas arbitrarias. Tampoco se
simulan cuadrantes, mapas continuos ni riesgos urbanos. La comparación territorial
muestra hasta cinco series de puntos seleccionados, sin interpretarlos como media
provincial. Los recorridos turísticos todavía no tienen un adaptador territorial.

La fecha y el calendario comparten estado; reproducir/avanzar no descarga muestras
mensuales adicionales. Los cambios de consulta usan AbortController y secuencia.
Las escalas son de navegación: una muestra mensual sigue representando un mes,
nunca una observación diaria. La selección anual muestra media descriptiva de las
muestras disponibles; no precipitación acumulada ni récord meteorológico.
Las anomalías mensuales usan la media del mismo mes del rango seleccionado,
mostrando esa referencia. Las tendencias anuales llaman al motor ya existente;
no se ajusta una regresión alternativa en JavaScript.

Históricos de grilla, reanálisis horarios, pronósticos operativos y climatologías se
mantienen separados. La línea discontinua identifica el pronóstico. Un hueco se
muestra vacío; el tramo 2025–presente no se rellena con históricos mensuales. Fuera
del horizonte operativo se puede consultar la media mensual 2000–2024, claramente
identificada como climatología, con su desviación descriptiva, sin crear valores
para días futuros. Las proyecciones OLS heredadas siguen siendo experimentales en
la interfaz original y en `/api/forecast`; **no son TimesFM**.

## Fuentes meteorológicas y licencias

- [NASA POWER Daily](https://power.larc.nasa.gov/docs/services/api/temporal/daily/):
  seis parámetros originales, una petición multivariable, tiempo UTC. Valores de
  relleno pasan a nulos; meses/días faltantes no se inventan. Caché independiente
  de POWER mensual. PRECTOTCORR conserva `mm/day`.
- [Open-Meteo Forecast](https://open-meteo.com/en/docs): producto `best_match`,
  horario UTC, diez variables, hasta 16 días. Incluye temperatura, sensación,
  humedad, precipitación, probabilidad, nubosidad, viento, ráfagas, dirección y
  visibilidad. La resolución depende de los modelos globales elegidos por el
  proveedor. Viento solicitado explícitamente en m/s; precipitación en mm por hora.
- [Open-Meteo Historical](https://open-meteo.com/en/docs/historical-weather-api):
  selección explícita `models=era5`, horario, grilla 0,25°, ocho variables; no
  inventa probabilidad/visibilidad. ERA5-Land está evaluado, no integrado.
- [Condiciones Open-Meteo](https://open-meteo.com/en/terms): distinguir licencia de
  los datos (CC BY 4.0) de las condiciones del servicio gratuito (no comercial).
  El modo predeterminado es educativo/no comercial. Un producto para empresas
  requiere suscripción y `OPEN_METEO_API_KEY`, junto a
  `EARTHLENS_WEATHER_COMMERCIAL=true`; usa hosts `customer-*`. No se contrató acceso.
- SMN: la [documentación oficial](https://api-test.smn.gob.ar/v1/swagger-ui.html)
  responde, pero los descriptores API probados devolvieron 401. Estado de alertas:
  `unavailable`, **nunca** lista vacía interpretada como ausencia de avisos.
  Se enlaza [SMN alertas](https://www.smn.gob.ar/alertas). Falta acceso oficial,
  contrato de geometrías/vigencia y verificación real antes de habilitarlo.

Cada respuesta identifica producto, tipo, unidad, frecuencia, resolución,
coordenadas solicitadas, metadatos, fuente, obtención y calidad. `issued_at=null`
significa que el endpoint no informa una emisión única: la obtención no la
sustituye. Tampoco se fabrican bandas de incertidumbre. Un pronóstico es una
estimación de modelo, no una observación. Los registros horarios son UTC; el
formulario de actividades usa hora argentina con offset obligatorio `-03:00`.

La caché de pronóstico es multivariable por ciudad y día, con TTL de una hora.
Se guarda hasta 16 días para reutilizarla entre eventos. Las peticiones históricas
se limitan a 367 días. Las actualizaciones que pierden valores válidos se rechazan;
un fallo conserva la copia anterior sin presentar datos vencidos como actuales.
Hay reintentos limitados para errores transitorios; las consultas no se realizan
al importar módulos o iniciar Flask. No hay descarga automática de 25 ciudades.

## API nueva

Se conserva el sobre `status/data/meta` y los endpoints anteriores.

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/api/workspace/series` | `city_id`, `provider`, `variable`, `start`, `end`; sólo caché científica |
| GET | `/api/workspace/profiles/{id}` | Climatología mensual y dimensiones nativas disponibles |
| GET | `/api/workspace/profiles/{id}/connections` | Pares y asociación descriptiva, sin significancia causal |
| GET | `/api/workspace/profiles/{id}/twins` | Similitud climatológica reproducible |
| GET | `/api/workspace/profiles/{id}/climatology-fingerprint` | Ejes Z independientes y referencia |
| GET | `/api/workspace/incidents?city_id=...` | Incidentes documentados del catálogo |
| GET | `/api/workspace/climatology?city_id=...&date=2030-01-15` | Contexto mensual habitual, sin pronóstico diario |
| GET | `/api/workspace/trends` | Motor POWER cache-only, ciudad, variable, inicio/fin de años completos |
| GET | `/api/workspace/report.pdf` | PDF científico descriptivo de la selección |
| GET | `/api/weather` | `city_id`, `kind`, `variable`, `start`, `end` |
| GET | `/api/weather/alerts` | Estado público explícito de acceso a SMN |
| GET | `/api/impact?city_id=...` | Evidencia/capas del piloto, sin geometrías inventadas |
| GET | `/api/prediction/capabilities` | Disponibilidad y bloqueo de TimesFM |
| GET | `/api/session` | Usuario actual y token CSRF para la misma sesión |
| POST | `/api/session/register`, `/api/session/login`, `/api/session/logout` | Credenciales/acción; requiere CSRF |
| GET, POST | `/api/events` | Listar/crear eventos propios |
| GET, PATCH, DELETE | `/api/events/{id}` | Leer, editar, reprogramar, cancelar o eliminar |
| POST | `/api/events/preview` | Evaluar un formulario y alternativas, sin guardarlo |
| GET | `/api/events/{id}/history` | Historial propio de evaluaciones y versiones |
| GET | `/api/events/{id}/forecast-history` | Revisiones por `variable` y `valid_time` dentro del evento |
| GET | `/api/events/{id}/report.pdf` | Informe del evento y última evaluación guardada |
| GET | `/api/notifications` | Notificaciones internas propias |
| PATCH | `/api/notifications/{id}` | Marcar leída |

Ejemplos públicos en PowerShell:

```powershell
Invoke-RestMethod 'http://localhost:5000/api/workspace/series?city_id=mendoza&provider=gldas&variable=SoilMoi0_10cm_inst&start=2000-01-01&end=2024-12-31'
Invoke-RestMethod 'http://localhost:5000/api/workspace/profiles/comodoro-rivadavia'
Invoke-RestMethod 'http://localhost:5000/api/weather?city_id=comodoro-rivadavia&kind=power-daily&variable=PRECTOTCORR&start=2017-03-29&end=2017-04-08'
Invoke-RestMethod 'http://localhost:5000/api/prediction/capabilities'
```

Ejemplo de cuerpo de evento (solicitud ilustrativa, no observaciones científicas):

```json
{
  "name": "Excursión",
  "description": "Plan de actividad",
  "activity": "excursion",
  "city_id": "comodoro-rivadavia",
  "location_label": "Punto de encuentro a confirmar",
  "start": "2026-11-18T10:00:00-03:00",
  "end": "2026-11-18T12:00:00-03:00",
  "participants": 8,
  "outdoor": true,
  "transport": "walk",
  "flexible_days": 2,
  "preferences": {"max_temperature": 28, "max_wind": 10, "require_official_alerts": true},
  "notifications": true
}
```

Crear sesión primero con `GET /api/session`; conservar la cookie y enviar
`X-CSRF-Token` en cada mutación, incluido login/registro. Contraseñas de 12–200
caracteres, hash scrypt de Werkzeug. Sin credenciales en logs. Diez intentos
fallidos bloquean esa combinación IP/usuario quince minutos. Los eventos y
notificaciones se consultan siempre por propietario; acceder a un ID ajeno da 404.
Respuestas privadas `Cache-Control: no-store`. CORS continúa desactivado.

Validación: códigos/ciudades del catálogo, fechas ISO, horas con offset, cantidades
enteras, booleanos reales y umbrales finitos. Los campos desconocidos se rechazan.
No acepta coordenadas ni recorridos libres. Un `location_label` es una descripción;
el punto guardado sigue siendo el centroide de la ciudad, **no el sitio exacto**.
HTTP: 400 formato, 401 sesión, 403 CSRF, 404 recurso/propietario, 409 usuario ya
existente, 422 cobertura/horizonte, 429 intentos, 502/503/504 proveedor. No se
exponen mensajes internos ni credenciales.

## Compatibilidad, alternativas y monitoreo

No existen umbrales universales predefinidos ni puntuación 0–100. Cada evento tiene
tipo, exposición, transporte y preferencias editables. El motor sólo activa reglas
expresamente configuradas por su usuario: comodidad (temperatura/sensación/RH),
operación (precipitación horaria/probabilidad/viento/ráfagas/visibilidad) y estado
de alertas oficiales. Guardar actividades distintas no hereda límites de otra.
Si faltan criterios o alguna hora requerida, la evaluación es `insufficient`.
Con umbrales incumplidos es `unfavorable`; si falta verificar alertas exigidas es
`review`. `favorable` significa sólo que las preferencias configuradas se cumplen.
No hay certificación de seguridad ni validación profesional de estos criterios.

Se comparan las horas que intersectan el evento, excluyendo su extremo final.
No se mezclan una climatología o un dato mensual con un pronóstico horario. Las
alternativas mantienen ciudad y duración dentro de ±0–7 días y ±0–6 horas; ordenan
por suficiencia, incumplimientos y cercanía. Muestran la misma incertidumbre y los
avisos pendientes. Usar una alternativa cambia el formulario; sólo Guardar
confirma la reprogramación. Las horas se desplazan en pasos de una hora según
`flexible_hours`; no optimiza rutas sin evidencia territorial.

El trabajo registra pronóstico completo, preferencias/revisión del evento,
evaluación y alternativas. Conserva cada actualización de valores, notifica sólo
cambios de decisión/criterios o primera evaluación y deduplica reejecuciones.
Predeterminado: revisar cada hora a menos de tres días, cada día en el resto del
horizonte. Eventos fuera de 16 días no generan falsos pronósticos. Una actualización
no cambia ni reprograma eventos automáticamente. Un fallo queda como insuficiencia.
El lease dura 30 minutos y se renueva al guardar. Cancelaciones/ediciones durante
el trabajo impiden publicar una evaluación para una revisión obsoleta.
No se envían emails, SMS, WhatsApp ni mensajes externos.

El historial privado muestra evaluaciones y un gráfico de revisiones por variable
para una misma hora pronosticada. El eje usa fecha de obtención, sin inventar
emisiones ausentes. La base conserva los snapshots completos. Falta el contraste
posterior con observaciones/archivo de pronósticos emitidos.

## Perfil, métodos exploratorios e impactos

La climatología es una media de cada mes entre años 2000–2024, con recuento y desvío
poblacional. Los extremos son de valores **mensuales**, no récords diarios.
WS2M no permite inferir dirección predominante. Hay elevación estática para los 25
centroides: Copernicus DEM GLO-90 (90 m) vía Open-Meteo, con unidades y procedencia.
No es la altitud media/oficial de la ciudad ni un modelo hidrológico. Atribuir a
Copernicus/Open-Meteo y [citar el DEM](https://doi.org/10.5270/ESA-c5d3d65).
Se incorporaron 12 fotografías JPEG geolocalizadas de Wikimedia Commons con
licencia compatible, autor y enlace a la página original; 13 accesos fallaron y
no generan imágenes de respaldo. Son ilustraciones, no observaciones ambientales.
La fotografía de Comodoro cargó correctamente en Chrome. Población sigue vacía
hasta incorporar una fuente censal verificable.

```powershell
docker compose exec -T backend python -m scripts.data.fetch_city_context --elevation --all
docker compose exec -T backend python -m scripts.data.fetch_city_context --photos --all
```

Las descargas de contexto son explícitas; abrir el perfil sólo lee la caché.
El programa conserva elevaciones/fotos válidas si una actualización falla. No
se copia información del municipio a partir de una imagen ni se interpreta su
geolocalización como validación territorial para coordenadas libres.

El radial climatológico usa cada eje por separado: media de 300 meses, convertida
a Z contra las medias de las ciudades con cobertura completa. Se publican media,
desvío, unidades originales y ciudades de referencia. No agrega ejes ni crea índice
de salud. El Fingerprint de tendencias conserva sus seis variables originales.
Su evaluación científica continúa provisional.

Connections empareja meses válidos POWER/GLDAS y calcula Pearson descriptivo,
sin p-valor ni interpretación causal; estacionalidad y autocorrelación permanecen.
Twins usa 48 rasgos (12 meses × T2M, precipitación, RH2M, WS2M), estandarización por
rasgo contra el catálogo y distancia RMS. Igual peso explícito por rasgo; excluye
rasgos constantes y ciudades sin 25 años completos. Es una similitud climatológica
dependiente de esa referencia, no una comparación de tendencias o riesgos.

El temporal de Comodoro del 29/03 al 08/04/2017 está documentado por
[IGN](https://www.ign.gob.ar/odc-14-Paredes) y
[SEGEMAR](https://archivointemin.segemar.gov.ar/handle/308849217/5102).
No se reproducen cifras de impacto ni imágenes sin autorización. Las otras ciudades
muestran «sin acontecimientos documentados en el catálogo actual».
Earth Impact presenta un inventario de evidencia, no una simulación hidrológica:
sin DEM/susceptibilidad/calles verificados no genera polígonos o impactos urbanos.
La consulta acotada a Overpass dio 406 y un segundo servicio 429; no se guardaron
geometrías parciales. `scripts/data/fetch_impact.py` permite reintentar explícitamente.

## TimesFM y evaluación retrospectiva

La [documentación oficial](https://github.com/google-research/timesfm) distingue el
código Apache-2.0 de los pesos 3.0 con licencia no comercial/no productiva. Los
servicios autorizados de Google Cloud tienen condiciones diferentes. No se descargan
pesos ni se habilita el modelo para empresas sin una vía licenciada y validación.
No se reemplaza silenciosamente por 2.5 ni se llama TimesFM al OLS heredado.

El paquete oficial declara Python >=3.10 y backend PyTorch opcional; ejemplos 3.0
admiten series uni/multivariadas, covariables y cuantiles 0,1–0,9. Nada de esto
equivale a precisión meteorológica demostrada. No se midió RAM/tiempo de inferencia
local ni se agregaron dependencias Torch al contenedor de la aplicación.

`services/prediction/prediction.py` expone capacidades deshabilitadas y un arnés de backtesting
inyectable. Recibe únicamente datos diarios contiguos; el predictor sólo ve el
pasado de cada corte. Baselines: persistencia y naive semanal. MAE/RMSE por corte
y horizonte; cobertura sólo cuando existen intervalos válidos. No usa históricos
mensuales para pronosticar días ni completa faltantes.

```powershell
docker compose exec -T backend python -m scripts.audit.backtest_weather --city comodoro-rivadavia --year 2023 --variable T2M
```

Se ejecutó con 365 valores diarios reales POWER: tres cortes, horizontes 1/3/7 días,
18 combinaciones de métricas de baselines. Resultado en `data/cache/reports/`.
**No se ejecutó ni validó TimesFM**, ni se recomienda una fecha usando ese modelo.
Faltan además pronósticos operativos archivados para un contraste retrospectivo.

## Verificación reproducible

Para una instalación nueva, después de levantar Docker:

```powershell
# Recupera o descarga POWER y regenera Radar con la familia original:
docker compose exec -T backend python -m scripts.maintenance.initialize_data
# Con EARTHDATA_TOKEN únicamente en el entorno de tu terminal:
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gldas --access giovanni --all --variables SoilMoi0_10cm_inst SoilMoi10_40cm_inst SoilMoi40_100cm_inst SoilMoi100_200cm_inst Evap_tavg --start-year 2000 --end-year 2024
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gpm --all --variables precipitation --start-year 2000 --end-year 2024
# Pilotos acotados; no descarga meteorología de las 25 ciudades automáticamente:
docker compose exec -T backend python -m scripts.data.probe_weather
```

Estos comandos se proporcionan para reproducir la instalación; no se forzó una
redescarga de las cachés mensuales durante esta reestructuración. MODIS se recupera
mediante órdenes ya existentes; no reenviar órdenes/correos para suplir un 404.

```powershell
docker compose exec -T backend python -m scripts.audit.audit_science
docker compose exec -T backend python -m scripts.data.probe_weather
docker compose exec -T backend python -m scripts.data.order_modis --poll
.\venv\Scripts\python.exe -m scripts.audit.check_workspace
```

El último comando requiere Playwright/Chrome local: usa los datos científicos reales
y una base temporal que elimina al terminar; no agrega usuarios/eventos a tu base.
El cambio de pronóstico que prueba notificaciones se simula **sólo** en las pruebas
unitarias identificadas como software, nunca en las cachés científicas de producción.
Las consultas meteorológicas reales se mantienen optativas, separadas de unittest.
