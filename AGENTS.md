# EarthLens — contexto e instrucciones del proyecto

La [estructura y el inventario de movimientos](docs/architecture/project-structure.md)
documentan la reorganización en la rama `refactor/project-structure`.

## Corrección prioritaria de interfaz — vigente

**EarthLens es Time Machine.** `/`, `/index.html` y `/time-machine` deben abrir
directamente el mapa completo con una única timeline inferior. No restaurar una
landing ni navegación separada hacia pasado/futuro. Paneles laterales flotantes,
cerrados al iniciar y desplegados a pedido; calendario, eventos, perfiles y avisos
comparten ciudad/fecha con la herramienta. La timeline mantiene un viewport
independiente del rango de análisis y de los límites del proveedor.

`services/workspace/time_navigation.py` y `GET /api/workspace/frame` resuelven el producto
según fecha/variable/escala, reutilizando servicios existentes. No arrastrar valores
antiguos a fechas futuras, no ocultar nulos y no convertir un fallo de proveedor
en climatología. Meteorología, históricos y referencia climatológica se distinguen.

TimesFM 3.0 **no está implementado**: capacidades deshabilitadas y arnés de
backtesting no equivalen a inferencia. Auditoría: `scripts/audit/audit_timesfm.py`.
El pronóstico operativo debe funcionar independientemente de ese modelo.

La aceptación vigente es `scripts/audit/check_time_machine_acceptance.py`: Chrome real,
datos reales A–F y simulación G sólo en base temporal. H no se aprueba con mocks.
Informe, capturas, archivos y límites: [docs/architecture/time-machine-correction.md](docs/architecture/time-machine-correction.md).

## Reestructuración vigente — 15/11/2026

El usuario autorizó una plataforma profesional de inteligencia ambiental y
geográfica para investigación y planificación, exclusiva de Argentina. Eslogan:
**EarthLens — Comprendé el pasado. Anticipá el futuro.** El trabajo se hace en
`feature/backend-api`, sin commits ni push. Este alcance amplía las etapas antiguas
sin eliminar proveedores, motor o interfaces del equipo. Estado comprobado y
pendientes: [docs/project/EARTHLENS_ROADMAP.md](docs/project/EARTHLENS_ROADMAP.md).
Contrato y operación: [docs/architecture/workspace.md](docs/architecture/workspace.md).

- `/time-machine`: `pages/workspace.html`, mapa/timeline/calendario/eventos sincronizados.
  La interfaz anterior sigue en `/time-machine/legacy`.
- Navegación principal: Inicio, Time Machine, Ciudades, Laboratorio, Mi espacio,
  Fuentes científicas. Las herramientas originales siguen en el Laboratorio.
- POWER Daily, Open-Meteo Forecast y ERA5 horario tienen pilotos reales de
  Comodoro. El acceso gratuito Open-Meteo es no comercial; las empresas requieren
  suscripción/configuración comercial. No guardar API keys en Git.
- SQLite (`data/runtime/earthlens.sqlite3`) conserva usuarios/eventos, preferencias,
  versiones meteorológicas, evaluaciones, notificaciones y ejecuciones. CSRF y
  permisos por propietario son obligatorios. No hay usuario compartido global.
- `scripts.maintenance.monitor_events.py` funciona independientemente de Flask; perfil Compose
  `monitoring`. No enviar avisos externos sin consentimiento y configuración.
- Compatibilidad con umbrales explícitos del usuario. Sin criterios o datos,
  insuficiencia. SMN desconocido no equivale a ausencia de alertas. Una evaluación
  favorable no garantiza seguridad; no introducir puntuaciones arbitrarias.
- Los ejes Z climatológicos y Connections/Twins son descriptivos, separados de
  tendencias y de índices de riesgo/salud. No expanden la familia de Radar.
- TimesFM 3.0 descargable restringe uso comercial/productivo. Sigue deshabilitado;
  no confundir baselines ni OLS heredado con TimesFM validado.
- Earth Impact es parcial: fuentes de Comodoro documentadas, sin DEM/calles/
  susceptibilidad operativos. No inventar impactos ni mapas de riesgo.
- Los polígonos de interfaz seleccionan centroides del catálogo; no validan
  territorio ni habilitan sitios exactos/recorridos libres sin límites oficiales.
- Base y cachés necesitan persistencia. Cloud Run local es efímero: no declarar
  producción lista sin DB externa, secretos estables, almacenamiento y licencias.

Las secciones siguientes conservan contexto y contratos anteriores. Para el
estado actual consultar los documentos de reestructuración y la evidencia del código.

Este archivo aplica a todo el repositorio. Describe el contexto y las reglas de
trabajo; el estado de las tareas y sus dependencias se mantiene en
[docs/project/BACKEND_TASKS.md](docs/project/BACKEND_TASKS.md). Revisar el código antes de dar una tarea por
completada. Los componentes propuestos en estos documentos no implican que existan.

## Contexto, objetivos y responsabilidades

- Proyecto: **EarthLens**.
- Equipo: **Patagonia Prime**.
- Evento: **NASA Space Apps Challenge 2026**.
- Desafío: **Earth System Trend Detective**.
- Objetivo: explorar datos ambientales históricos reales, identificar tendencias
  con respaldo estadístico y presentar resultados comprensibles y trazables.
- Alcance geográfico exclusivo: **República Argentina**. No incluir ciudades
  internacionales. El catálogo inicial contiene 25 ciudades argentinas y puede
  ampliarse; las investigaciones futuras deben admitir cualquier ubicación dentro
  de Argentina, sin limitarse a ese catálogo.
- El usuario es responsable del backend, consumo de APIs y, desde la fase 1,
  interfaces de Earth Radar y Earth Fingerprint.
- El motor estadístico corresponde a otro integrante del equipo. Acordar su contrato
  de entrada y salida antes de integrarlo; no inventar su interfaz ni reemplazarlo
  con cálculos o resultados ficticios.

## Funcionalidades del producto

Las siguientes son funcionalidades objetivo. Actualmente existen el proveedor y
normalizador NASA POWER, el catálogo argentino, la caché local y la obtención masiva;
también existen la API HTTP, el frontend Flask y la integración del motor del equipo
para análisis exploratorios. Ver `docs/architecture/integration.md` para el contrato inspeccionado
y sus limitaciones; la revisión metodológica conjunta sigue pendiente.

| Funcionalidad | Alcance previsto | Estado de la funcionalidad completa |
| --- | --- | --- |
| Explorador ambiental | Consultar variables ambientales por ubicación argentina y período, conservando unidades y procedencia. | Interfaz conectada a catálogo, caché y análisis exploratorio por ciudad. |
| Tendencias y significancia estadística | Integrar los análisis y evidencias del motor del equipo. | Motor existente integrado; revisión metodológica para ampliar usos pendiente. |
| Earth Radar | Descubrir automáticamente tendencias ambientales en el catálogo inicial de 25 ciudades argentinas. | Backend provisional, estudio de 150 pruebas e interfaz `/radar` disponibles; validación científica y ajuste pendientes; sin descubrimientos confirmados. |
| Earth Fingerprint | Generar un perfil de tendencias históricas de temperatura, precipitación, humedad y viento por ciudad. | Perfil provisional, endpoint e interfaz `/fingerprint` con seis indicadores y comparación descriptiva; sin puntajes; validación científica pendiente. |
| Comparador de regiones | Comparar resultados con períodos, unidades, cobertura y criterios compatibles. | Comparación descriptiva de dos ciudades implementada; comparación de regiones arbitrarias pendiente. |
| Investigaciones guiadas | Orientar preguntas y recorridos basados en datos y análisis disponibles. | Interfaz y recomendador del equipo conectados; validación científica de recorridos pendiente. |

## Tecnologías y arquitectura actuales

El código actual usa **Python, Flask, Requests, SciPy y JSON**, con módulos de proveedores
de datos. `app.py` expone `create_app(config=None)` y registra un Blueprint en
`/api`, además del Blueprint web y los estáticos en el mismo origen. Las dependencias directas verificadas localmente figuran en `requirements.txt`;
la instalación limpia y las pruebas se verificaron en Docker con Python 3.12.16
Linux/amd64. El despliegue productivo sigue pendiente.

Archivos existentes relevantes:

```text
app.py
requirements.txt
Dockerfile
compose.yaml
.dockerignore
api/
  __init__.py
  routes.py
  responses.py
  errors.py
services/
  __init__.py
  api_service.py
  cities.py
  geography.py
  cache.py
  bulk.py
  normalizer.py
  providers/
    __init__.py
    power.py
tests/
  test_api.py
  test_cities.py
  test_geography.py
  test_cache.py
  test_bulk.py
  test_city_catalog_builder.py
  test_power_provider.py
  test_power_provider_live.py
scripts/audit/probe_nasa_power.py
docs/science/nasa-power.md
docs/science/bulk-power.md
docs/architecture/api.md
docs/operations/docker.md
data/cities.json
data/cache/.gitignore
scripts/data/build_city_catalog.py
scripts/data/fetch_power.py
```

Flujo actual: un consumidor Python o `scripts/data/fetch_power.py` selecciona ciudades
argentinas y llama a `PowerBulkService`; el servicio reutiliza cachés válidas o
consulta el proveedor multivariable, que normaliza la respuesta NASA. Los consumidores
existentes también pueden seguir usando directamente `get_data()` y `get_data_multi()`.
La API delega en `services/api_service.py`, que reutiliza esos servicios, valida las
solicitudes y proyecta al cliente sólo las variables seleccionadas. La lógica de
obtención y caché no se duplica en las rutas.

### Contrato del proveedor NASA POWER

- Archivo: `services/providers/power.py`.
- Endpoint remoto configurado: `https://power.larc.nasa.gov/api/temporal/monthly/point`.
- Comunidad: `AG`; frecuencia: mensual; timeout actual: 60 segundos.
- `get_data(latitude, longitude, variable, start_year, end_year)` conserva la
  interfaz existente para una variable.
- `get_data_multi(latitude, longitude, variables, start_year, end_year)` consulta
  varias variables en una petición y devuelve un diccionario por código. Requiere
  una colección no vacía y elimina duplicados conservando el orden solicitado.
- Variables admitidas: `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M` y `WS2M`.
- Cada resultado contiene `provider`, `dataset`, `variable`, `name`, `unit`,
  `latitude`, `longitude`, `start_year`, `end_year`, `frequency`, `series` y `metadata`.
- `series` contiene registros `{"date": "YYYY-MM", "value": número_o_None}`.
- `metadata.header` conserva las fuentes originales y los metadatos de cabecera;
  `metadata.parameter` contiene los metadatos de esa variable. También se conservan
  geometría, mensajes y otros metadatos de primer nivel recibidos.
- `dataset="MERRA-2"` es un campo histórico del contrato. Conservarlo y consultar
  también las fuentes originales en los metadatos; no interpretarlo como prueba de
  que exista un proveedor directo de MERRA-2.
- Las unidades recibidas de NASA tienen prioridad sobre los valores de respaldo
  del catálogo local. No modificar unidades sin una conversión explícita y trazable.
- Se rechazan variables inválidas antes de acceder a la red y se informa con
  `ValueError` si falta una variable solicitada o la estructura esperada es inválida.
  Los errores HTTP, de conexión y de JSON se propagan; no se fabrican resultados.

### Normalización actual

`services/providers/normalizer.py` ordena los registros, conserva los meses `01` a `12`, excluye
el registro anual `YYYY13` y convierte el valor de relleno informado por NASA en
`None`. Conserva los ceros y nulos existentes; no interpola ni crea meses ausentes.

La precipitación `PRECTOTCORR` se conserva en `mm/day`, sin convertirla en un
acumulado mensual. Los extremos de temperatura conservan la definición del producto
mensual de NASA. Los datos del producto corresponden a una grilla; no presentarlos
como mediciones de una estación local.

## Catálogo argentino, caché y obtención masiva

- `data/cities.json` contiene las 25 ciudades acordadas, con ID estable, nombre,
  provincia/jurisdicción, región, país, coordenadas y procedencia GeoRef. Conserva
  el registro oficial, ID de entidad, consulta y fecha de obtención del centroide.
- `services/geography/cities.py` ofrece `list_cities(province=None, region=None)` y
  `get_city(city_id)`; este último devuelve `None` para un ID inexistente. La cantidad
  de localidades no está fijada en el cargador. Los filtros admiten tildes/caso
  indistintos, ID provincial y alias documentados como `CABA` y `centro-pampeana`.
- Las regiones son la agrupación definida por el proyecto: Patagonia, Centro y
  región pampeana, Cuyo, NOA y NEA; no atribuir esta clasificación a GeoRef.
- `scripts/data/build_city_catalog.py` permite reconstruir el catálogo con una consulta
  por lotes a GeoRef. No ejecutar la reconstrucción automáticamente al importar módulos.
- `services/providers/bulk.py` ofrece `PowerBulkService.collect_city()`, `collect_cities()` y
  `plan_cities()`. Permite seleccionar un ID, un subconjunto, provincia, región o
  catálogo completo. El período por defecto es **2000–2024**, configurable.
- Cada ubicación remota usa una petición con las seis variables del proveedor
  existente. Las consultas son secuenciales, con intervalo mínimo configurable de
  un segundo por defecto; los fallos se informan por ubicación y no detienen el lote.
- `services/providers/cache.py` almacena JSON en `data/cache/power/`, ignorado por Git mediante
  `data/cache/.gitignore`. La clave distingue proveedor, dataset, endpoint, comunidad,
  frecuencia, coordenadas, variables y período. Conserva series, unidades, metadatos,
  ubicación y fechas de obtención en UTC.
- La caché se reutiliza hasta `force=True`/`--force` o el vencimiento opcional
  `max_age_days`/`--max-age-days`. Un acierto no cambia la fecha de obtención original.
- Validar las seis series y todos los meses del período antes de guardar. Los nulos
  científicos se conservan y cuentan; una serie totalmente nula, una variable o mes
  ausente, valores no finitos o metadatos esenciales ausentes producen un error.
  Una actualización que sustituye valores disponibles por nulos se rechaza.
- Las escrituras usan reemplazo atómico. Una respuesta fallida/incompleta no
  sobrescribe una caché válida. Un refresco fallido se informa como error con
  `cache_preserved`, sin presentar los datos anteriores como una descarga nueva.
- `scripts/data/fetch_power.py` exige una selección explícita. `--dry-run` sólo muestra
  el plan; no consulta NASA ni escribe cachés. Ver [docs/science/bulk-power.md](docs/science/bulk-power.md).

## Validación territorial: estado y límite actual

Las ciudades del catálogo se respaldan en localidades argentinas de GeoRef. Para
coordenadas libres, `services/geography/geography.py` define `TerritoryEvidence` y el contrato
de un validador inyectable de límites oficiales. `collect_location()` admite una
ubicación fuera del catálogo sólo con evidencia de pertenencia a Argentina.

**Todavía no hay un adaptador real de límites/polígonos configurado.** Sin ese
adaptador, las coordenadas libres se rechazan antes de consultar NASA, incluso si
parecen argentinas. Una caja rectangular o el mero rango mundial de latitud/longitud
no validan territorio. Las pruebas de este contrato usan un validador simulado,
que nunca debe usarse para habilitar coordenadas en producción.

El proveedor POWER de bajo nivel mantiene su interfaz existente; la restricción
territorial corresponde a los servicios de aplicación y a las futuras rutas HTTP.
No habilitar una ruta de coordenadas libres que eluda esta validación.

## API REST básica disponible

Contrato y ejemplos para frontend: [docs/architecture/api.md](docs/architecture/api.md).

- `GET /api/health`: disponibilidad del proceso HTTP, sin sondear NASA.
- `GET /api/variables`: códigos, nombres, unidades de catálogo y fuentes.
- `GET /api/cities`: catálogo argentino con filtros `province` y `region`.
- `GET /api/cities/{city_id}`: detalle de una ciudad verificada.
- `GET /api/regions`: regiones presentes y conteos derivados del catálogo.
- `POST /api/data`: una ciudad, una lista opcional de variables, años y `force`.

La consulta HTTP reutiliza la caché de las seis variables; devuelve sólo las
seleccionadas, con unidades recibidas, metadatos, cobertura, origen y fecha UTC.
La obtención se serializa dentro de cada proceso para evitar descargas duplicadas.
No hay bloqueo entre varios procesos ni despliegue multiproceso verificado.

Las respuestas usan `status`, `data` y `meta`; los errores usan `status`, `error`
y `meta`, con estados HTTP y códigos públicos documentados. No devolver mensajes
crudos de excepciones, rutas locales o advertencias internas. No habilitar
coordenadas libres ni aceptar parámetros de configuración desde el cuerpo HTTP.

Frontend y API comparten origen; CORS permanece desactivado. Si el equipo define
orígenes distintos, acordar una lista explícita antes de habilitarlo. No aplicar
un comodín. `static/js/shared/api.js` consume el contrato documentado en `docs/architecture/api.md`.

## Docker para desarrollo local

`Dockerfile` usa `python:3.12-slim`; `compose.yaml` define un único servicio
`backend`, sin base de datos. Sirve el frontend HTML/Jinja y el motor en el mismo
proceso; no requiere Node ni otro contenedor. Usa `app:create_app`, se publica en
`127.0.0.1:5000` y tiene healthcheck sobre `/api/health`. Flask admite recarga de
código sin habilitar el depurador interactivo. Ejecuta como UID 10001.

El código y el catálogo se montan desde el host con sólo lectura en el contenedor;
`./data/cache` se monta con lectura/escritura en `/app/data/cache` y mantiene la
caché original de POWER. No copiar cachés científicas ni credenciales a la imagen.
No sustituir ese montaje por un volumen vacío que oculte datos ya obtenidos.

Las 71 pruebas originales siguen intactas. La suite ampliada y las páginas se
verificaron dentro de Docker y con Chrome real; ver `docs/project/BACKEND_TASKS.md`.
El lote completo de 25 ciudades para 2000–2024 se ejecutó por indicación explícita
del usuario: 25 aciertos de caché, 150 series, 45.000 valores mensuales disponibles,
sin faltantes ni fallos; no se hicieron descargas nuevas. Se verificó que las 25
cachés anteriores conservaran sus hashes y fechas de obtención.

Guía y comandos: [docs/operations/docker.md](docs/operations/docker.md). Frontend y motor se incorporaron
desde las ramas del equipo sin reemplazar el proveedor ni su caché. Diagnóstico e
inventario Docker: [docs/architecture/integration.md](docs/architecture/integration.md).

## Arquitectura prevista — todavía pendiente

Mantener los proveedores separados de la lógica de producto. Las siguientes capas
se incorporarán por etapas autorizadas:

1. Adaptador territorial con límites oficiales de Argentina para coordenadas libres.
2. Despliegue productivo de la API y ampliación de rutas cuando existan los servicios
   de análisis y producto. La instalación limpia para desarrollo ya se verificó en Docker.
3. Revisión metodológica conjunta del motor ya integrado antes de ampliar usos científicos.
4. Validación científica y futuras vistas para Radar/Fingerprint; sus servicios y generador provisionales ya existen.
5. CI y ampliación de contratos; el flujo actual del frontend y sus pruebas ya están conectados.

Rutas de producto **implementadas con evidencia provisional**: `/api/radar` y
`/api/fingerprint/{city_id}`. `/api/analyze`, `/api/compare`, `/api/summary`,
`/api/missions`, `/api/catalog` y `/api/variables/recommend` están integradas.
Las tres primeras usan el motor real y el proveedor/caché existentes; los
catálogos de misiones y recomendaciones nunca descargan ni fabrican datos.

## Fuentes científicas

Priorizar NASA POWER, MERRA-2, Giovanni, GPM y GLDAS según la variable y el caso de
uso. Evaluar SWOT como recurso complementario, incluyendo Hydrocron como posible
vía de acceso. Estas prioridades no equivalen a integraciones terminadas.

NASA POWER mantiene el acceso meteorológico y estadístico existente. La capa
aditiva `services/science/scientific.py` y el adaptador MODIS/ORNL conservan series nativas
separadas; su disponibilidad depende de observaciones reales verificadas en caché.
GLDAS_NOAH025_M 2.1 tiene extracción puntual OPeNDAP verificada para las tres
ciudades piloto en 2024: 15 series y 180 registros disponibles, sin faltantes.
Giovanni in the Cloud se verificó con una serie real y ofrece un adaptador
mensual para ampliar históricos. Sus CSV pueden venir redondeados: se separan
de NetCDF por revisión/política de caché y se conserva esa limitación de precisión.
Consultar [docs/science/scientific-sources.md](docs/science/scientific-sources.md) y los informes
locales para cobertura y limitaciones reales. MERRA-2 figura en el contrato POWER;
no hay un cliente directo de MERRA-2. Giovanni es una vía de acceso/análisis
verificada mediante servicios oficiales NASA Earthdata; no tratarlo como un dataset
único ni suponer que todos los productos comparten variables o resolución.

Antes de agregar una fuente, verificar documentación oficial, acceso y autenticación,
cobertura espacial y temporal, frecuencia, unidades, valores faltantes y metadatos
del producto concreto. No suponer equivalencias entre productos de POWER, GPM,
GLDAS y SWOT ni combinar sus series sin justificar su compatibilidad.

## Restricciones científicas y de colaboración

- Inspeccionar primero los archivos y conservar las funcionalidades que ya funcionan,
  especialmente la compatibilidad de `get_data()`.
- No modificar archivos de compañeros sin autorización. El motor estadístico y el
  frontend son puntos de coordinación, no autorización para editar código ajeno.
- Trabajar por etapas. Completar y probar la etapa autorizada, explicar los cambios
  y esperar indicación antes de implementar la siguiente.
- Mantener el alcance exclusivo argentino. No agregar ciudades internacionales ni
  sustituir una validación territorial por una caja rectangular. El catálogo no
  define un límite permanente para las ubicaciones investigables dentro del país.
- No inventar observaciones, tendencias, pendientes, significancias ni conclusiones.
  Los datos sintéticos sólo se permiten como pruebas de software claramente
  identificadas y separadas de los resultados científicos.
- No introducir puntuaciones ambientales arbitrarias. Earth Fingerprint debe
  describir resultados y evidencias, con su método y contexto.
- Mantener unidades, fuentes, metadatos, período, frecuencia y cobertura. Explicitar
  cualquier agregación, transformación o limitación de resolución.
- No reemplazar faltantes por cero ni imputarlos silenciosamente. Acordar con el
  responsable del motor los criterios de cobertura, estacionalidad, incertidumbre
  y comparaciones múltiples antes de presentar descubrimientos de Earth Radar.
- No confundir correlación con causalidad ni presentar significancia estadística
  como una explicación causal. No presentar resultados del motor si aún no existe
  una integración verificable.
- No hacer commits ni push sin autorización. Conservar los cambios locales y los
  archivos sin seguimiento preexistentes; no limpiar el repositorio por iniciativa propia.
- No incluir credenciales en código, documentación, cachés o resultados versionables.

## Verificación y mantenimiento

Ejecutar desde la raíz, en PowerShell:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite sin red usa valores sintéticos identificados como tales. La prueba real de
NASA POWER es optativa: requiere `EARTHLENS_POWER_LIVE=1`, acceso a Internet y hace
dos consultas. Ver instrucciones en [docs/science/nasa-power.md](docs/science/nasa-power.md).
Un resultado `skipped` no equivale a una verificación de red satisfactoria.

Las pruebas de catálogo, caché, selección masiva y geografía son sin red. El lote de
25 ubicaciones se prueba con NASA simulada. La primera verificación real de NASA se
limitó a tres ciudades; en la etapa Docker se ejecutó el lote de 25 con cachés
preexistentes verificadas, sin solicitudes nuevas. No forzar una actualización
completa por iniciativa propia; reutilizar la caché conforme a la tarea autorizada.
Los comandos están en `docs/science/bulk-power.md` y `docs/operations/docker.md`.
Las pruebas de API usan el cliente Flask, NASA simulada y cachés temporales; no
consultan proveedores reales. Las verificaciones adicionales pueden leer la caché
real existente bloqueando la red y comprobando que no se modifique.

`scripts/audit/probe_nasa_power.py` es un script manual que consulta NASA al ejecutarse o importarse;
evitar importarlo como parte de verificaciones sin red. Mantener la separación
entre pruebas automáticas de contrato y comprobaciones reales de los proveedores.

Al completar trabajo autorizado, actualizar el estado y las dependencias en
`docs/project/BACKEND_TASKS.md`, citar los archivos que lo respaldan e informar qué se verificó
y qué quedó pendiente. No marcar una funcionalidad de producto como completada
por disponer solamente de su proveedor de datos.


## Integración de frontend y motor — contrato vigente

`services/science/trend_analysis.py` conserva el motor de `origin/results-charts` e33c76d;
`services/science/analysis_service.py` adapta series mensuales reales a sus entradas y
mantiene unidades, metadatos, cobertura y fechas. El motor requiere SciPy y aplica
medias aritméticas anuales con mínimo 9 meses válidos, 3 años y 70% de cobertura.
La comparación exige idénticas unidades y años válidos. No reemplazar el motor
ni activar proveedores con respaldo sintético.

Las misiones originales de `origin/datasets-missions` fbd7d0a se conservan en
`services/science/guided_missions.py`, catálogos separados y su interfaz. Su agregador
anual alternativo permanece disponible como código del compañero y pruebas; no
se usa en el flujo estadístico actual. `services/science/mission_service.py` proyecta el
catálogo al método y las unidades vigentes y usa IDs de ciudades verificadas.

`tests/statistics_fixtures/` y `tests/data/` contienen recursos heredados sólo para
pruebas de software. La aplicación no usa esas muestras ni genera series de
respaldo. Los scripts `check_cached_integration.py` y `check_web.py` verifican
respectivamente las cachés reales con NASA bloqueada y el flujo de navegador.

Consultar `docs/architecture/integration.md` antes de ampliar métodos, misiones o resultados.
Earth Radar y Earth Fingerprint tienen backend provisional, según `docs/architecture/products.md`.
La falta de corrección de autocorrelación y comparaciones múltiples impide tratar
este análisis exploratorio como un servicio de descubrimientos confirmados.


## Contrato común y productos provisionales

`services/science/analysis_results.py` define el contrato común v1 y los indicadores de las
seis variables; `AnalysisService.results()` reutiliza el motor y la obtención
existentes. No agregar regresiones alternativas. `statistics` conserva lo recibido;
`statistics_unrounded` queda reservado para la salida completa del compañero,
actualmente ausente. Todos los análisis calculados son científicamente
`provisional`, aunque `data_status` sea `valid`.

`services/science/fingerprint.py` produce perfiles y verifica compatibilidad descriptiva.
`services/science/radar.py` define la familia completa del catálogo x seis variables y
persiste sus resultados. `scripts/maintenance/generate_radar.py` es siempre cache-only; nunca
actualiza observaciones. El artefacto derivado vive en `data/cache/radar/latest.json`
y se escribe atómicamente con integridad SHA-256, fuera de `power/`.

`GET /api/radar` sólo lee el artefacto y filtra filas: no genera estudios, descarga
series ni ajusta p-valores. Los filtros no cambian la familia, resumen ni estado
de ajuste. `GET /api/fingerprint/{city_id}` conserva el período solicitado y las
seis variables. No habilitar coordenadas libres ni configuración HTTP del motor.

No marcar ninguna señal nominal provisional como descubrimiento confirmado. La
aprobación metodológica, precisión completa y correcciones científicas continúan
bajo coordinación de B06. Los perfiles no contienen puntuaciones arbitrarias.

## Interfaces de producto — fase 1

El usuario autorizó las interfaces de Radar/Fingerprint y su incorporación a la
navegación. `templates/components/_navigation.html` es la navegación compartida; conservar
el enlace del Inicio al Explorador que mantiene la ciudad seleccionada.
Las vistas viven en `templates/pages/radar.html`, `templates/pages/fingerprint.html`,
`static/css/pages/products.css` y `static/js/{products,radar,fingerprint}.js`.
No calculan estadísticas: presentan el contrato común y sus series anuales.
La selección rápida utiliza AbortController y un número de secuencia para impedir
que respuestas anteriores reemplacen la vista actual.

Fingerprint conserva las unidades e indicadores recibidos y agrega tarjetas
dinámicamente. La superposición de perfiles exige `comparison.key` iguales,
disponibilidad completa y ausencia de incoherencias. No introducir gráficos
radiales ni normalizaciones sin metodología acordada. El período de la interfaz
es el cacheado 2000–2024; Radar no modifica la familia al filtrar.

Ver `docs/architecture/products.md`, `tests/browser/test_product_pages.py` y el verificador optativo
`scripts/audit/check_product_pages.py`. Los proveedores nuevos requieren documentación
oficial y observaciones reales antes de habilitarse; no quedan incorporados a estas
interfaces por aparecer en el catálogo multiproveedor.

## Recuperación y capa multiproveedor — noviembre de 2026

`scripts/maintenance/initialize_data.py` permite inicializar una instalación nueva: reutiliza
POWER, descarga sólo las cachés faltantes, audita unidades/cobertura y regenera
Radar mediante su generador cache-only. No amplía su familia de 150 pruebas.
Si fallan datos o análisis, conserva el artefacto anterior. La recuperación del
15/11 encontró las cachés ausentes y descargó realmente las 25 ciudades para
2000–2024: 150 series, 45.000 valores y cero nulos. Su repetición reutilizó las 25
cachés sin descargas. Esto es distinto del lote histórico anterior de sólo caché.

La API aditiva `/api/science/variables` publica disponibilidad basada en cachés
validadas; `/api/science/data` sirve frecuencias nativas, con análisis desactivado.
Los endpoints POWER existentes no cambian. Las cachés nuevas se separan en
`data/cache/science/series/<provider>/<product>/<cache_version>/<variable>/` y
preservan unidades, QA, versiones conocidas e integridad. No atribuir una versión
científica a partir de una versión de API o de un identificador local de caché.

MODIS usa MOD13Q1 puntual, NDVI/EVI escalados desde metadatos reales, compuestos
de 16 días y QA conservada. La colección no está identificada en la respuesta
REST recibida: se informa `product_version: null`. No mezclarla con colecciones
supuestas ni trasladarla al OLS mensual sin acuerdo metodológico. El acceso GLDAS
se verificó después de autorizar NASA GESDISC DATA ARCHIVE; los errores 401/400/403
anteriores no representan el estado final del piloto. Configurar tokens sólo en
el entorno local, sin Git ni chat. La API sirve cachés verificadas sin requerir
el token en el proceso HTTP; las descargas nuevas sí requieren autenticación.

El motor del compañero se conserva. La API nativa y el panel aditivo de fuentes
no calculan tendencias nuevas ni amplían los seis indicadores de Fingerprint o
la familia de 150 pruebas de Radar. La revisión metodológica continúa pendiente.

### Estado verificado de fuentes e interfaces

- GLDAS `GLDAS_NOAH025_M.2.1`: cuatro capas de humedad del suelo en `kg m-2`
  y evapotranspiración en `kg m-2 s-1`. Piloto NetCDF puntual: 3 ciudades, 2024,
  15 series/180 registros. Histórico Giovanni: 25 ciudades, 2000–2024,
  125 series/37.500 registros válidos. Son accesos al mismo producto; no sumar
  el piloto al histórico como observaciones independientes. CSV y NetCDF tienen
  cachés distintas porque el CSV redondea algunos valores.
- GPM `GPM_3IMERGM.07`, IMERG Final mensual: 25 ciudades, 2000–2024,
  25 series/7.500 registros válidos, conservados en `mm/hr`. La comparación con
  POWER exige `target_unit: "mm/day"` y multiplica explícitamente por 24 sólo
  la proyección gráfica. Los originales permanecen intactos; no se acumula lluvia.
- MODIS `MOD13Q1`: piloto REST 2024 de 3 ciudades, 6 series/138 registros,
  56 aceptados y 82 excluidos por QA. Las órdenes históricas ORNL se gestionan
  mediante `scripts/data/order_modis.py`, con contacto sólo en memoria. Una orden
  aceptada no equivale a una descarga verificada: consultar su estado y validar
  CSV, colección por gránulo, píxel, fechas y QA antes de publicar las series.
- SWOT Hydrocron: tramo argentino `65341000051`, río Chubut cerca de Trelew,
  `SWOT_L2_HR_RiverSP_D`, SWORD 17b. Piloto 2024 con 31 pasos, altura y ancho
  en metros, incertidumbres, banderas y geometría propios. No es una serie de
  ciudad, no usa el OLS mensual y sus banderas requieren revisión. No hay lagos
  argentinos verificados todavía. Catálogo: `data/water_features.json`.

`services/science/hydrology.py` y `/api/science/water-*` conservan el contrato hidrológico
independiente. `/api/science/compare` es descriptivo. El panel compartido en
`templates/components/_scientific_panel.html`, `static/js/products/scientific.js` y
`static/css/components/scientific.css` presenta datos reales en Explorador, Comparador,
Radar, Fingerprint y Modo detective, y en `/sources`. Se carga al abrirlo;
los gráficos respetan fechas nativas, huecos y unidades. El recorrido histórico
del deslizador no hace consultas nuevas. No sustituye los análisis o misiones
existentes ni crea relaciones causales.

Time Machine se incorporó desde `origin/main` ce9a1e2 durante el merge autorizado.
`/time-machine` y `/api/time-machine` usan `services/workspace/time_machine_service.py`,
cachés POWER verificadas y funciones aditivas del motor del equipo. El núcleo
anterior del motor se conserva sin cambios. La interpretación es provisional;
la familia de Radar no se amplía. No habilitar muestras de respaldo, ajustes
espaciales artificiales, coordenadas libres ni cuadrantes sin datos/validación.
El código anterior que dependía del servidor alternativo y sus muestras queda
como referencia de migración en `tests/statistics_fixtures/main_legacy/`, fuera
del flujo de producción. Ver `docs/history/merge-main.md` y `docs/architecture/time-machine-integration.md`.
El usuario confirmó que Earth Connections todavía no existe. La extensión de
Time Machine a las otras fuentes depende de su metodología y contrato; Connections
depende de disponer de su código.

La actualización `4157789` incorpora el modelo `services/prediction/forecast.py`, adaptado
en `services/prediction/forecast_service.py` a históricos POWER cacheados por ciudad.
Son extrapolaciones OLS/t de Student provisionales, no TimesFM ni observaciones
futuras. Conservar unidades, procedencia y separación del histórico; no aceptar
series arbitrarias del cliente ni presentar causalidad o heurísticas de confianza
como validación científica. Ver `docs/history/merge-forecast.md`.

`scripts/audit/audit_science.py` audita las cachés sin red, agrupando versiones, vías
de acceso y períodos para evitar contabilizar pilotos y proyecciones dos veces.
`scripts/audit/check_scientific_pages.py` verifica con Chrome real las cinco interfaces,
gráficos, comparación, QA, recorrido histórico y descarte de respuestas tardías.
