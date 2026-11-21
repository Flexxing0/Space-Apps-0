# EarthLens — contrato de API REST, versión 1

La selección geotemporal unificada usa ahora `GET /api/workspace/frame`;
ver [contrato y aceptación de la corrección](time-machine-correction.md).
La entrada `/` es Time Machine; las APIs anteriores siguen disponibles.

La reestructuración agrega meteorología, perfiles, eventos privados, notificaciones
e informes sin retirar los endpoints anteriores. Consultar
[la API geotemporal](workspace.md#api-nueva) para rutas, autenticación, CSRF,
licencias y límites. Estado: [roadmap](../project/EARTHLENS_ROADMAP.md).

API para el equipo de frontend de Patagonia Prime. Alcance exclusivo: **Argentina**.
Sólo se admiten ciudades del catálogo verificado. El motor del equipo está integrado
para análisis y comparación; Radar y Fingerprint están disponibles con resultados
provisionales. Las coordenadas libres y la validación científica siguen pendientes.
La interfaz y la API comparten origen.

La capa multiproveedor agrega `/api/science/variables` y `/api/science/data`,
documentados al final. Los endpoints anteriores conservan el contrato POWER.

## Instalación y ejecución local

Desde la raíz del repositorio, en PowerShell:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
```

La URL local es `http://127.0.0.1:5000`. El comando usa el servidor de desarrollo y
no activa el depurador. No se descargan datos al importar módulos o crear la app.
`requirements.txt` fija las versiones directas verificadas localmente; no es un
lock de dependencias transitivas. La instalación limpia se verificó posteriormente
en Docker con Python 3.12.16 Linux/amd64; ver [ejecución con Docker](../operations/docker.md).

## Convenciones comunes

Todas las respuestas de los endpoints son JSON UTF-8. El sobre de éxito es
`{"status":"ok","data":...,"meta":{"api_version":"1",...}}`. Los campos `data`
y `meta` varían por recurso; `status` y `meta.api_version` son comunes para permitir
reutilizar el contrato en servicios futuros.

Los errores usan este sobre y un estado HTTP no exitoso:

```json
{
  "status": "error",
  "error": {
    "code": "invalid_request",
    "message": "force debe ser un booleano JSON.",
    "details": {"field": "force"}
  },
  "meta": {"api_version": "1"}
}
```

El frontend debe decidir por `error.code` y el estado HTTP; el texto es explicativo.
`details` siempre es un objeto y puede estar vacío. No se devuelven rutas locales,
credenciales, trazas ni mensajes crudos de excepciones. Las advertencias de caché
tienen códigos y textos públicos controlados. Los metadatos científicos originales
sí se conservan en los datos.

No se admiten parámetros de query desconocidos, vacíos o repetidos. En los GET sin
filtros y en POST `/api/data`, la query debe estar vacía. Los GET también admiten
HEAD y las respuestas automáticas OPTIONS de Flask; un método incorrecto devuelve
405 JSON con su encabezado `Allow`.

## GET /api/health

Comprueba que el proceso HTTP responde. No consulta NASA ni verifica la red, el
catálogo o la disponibilidad del proveedor.

Solicitud: `GET /api/health`. Respuesta 200:

```json
{
  "status": "ok",
  "data": {"service": "EarthLens", "status": "up", "country_code": "AR"},
  "meta": {"api_version": "1"}
}
```

## GET /api/variables

Catálogo obtenido de `services/providers/power.py`, sin consultar NASA. `data` es
una lista con las seis variables; cada elemento contiene `code`, `name`, `unit`,
`provider`, `dataset`, `frequency` y `sources` (nombre y URL).

Solicitud: `GET /api/variables`. Extracto de respuesta 200, con sólo el primer
elemento de la lista de seis:

```json
{
  "status": "ok",
  "data": [{
    "code": "T2M",
    "name": "Temperatura media",
    "unit": "°C",
    "provider": "NASA POWER",
    "dataset": "MERRA-2",
    "frequency": "monthly",
    "sources": [{"name": "NASA POWER", "url": "https://power.larc.nasa.gov/api/temporal/monthly/point"}]
  }],
  "meta": {"api_version": "1", "count": 6}
}
```

| Código | Nombre del catálogo | Unidad del catálogo |
| --- | --- | --- |
| T2M | Temperatura media | °C |
| T2M_MAX | Temperatura máxima | °C |
| T2M_MIN | Temperatura mínima | °C |
| PRECTOTCORR | Precipitaciones | mm/day |
| RH2M | Humedad relativa | % |
| WS2M | Velocidad del viento | m/s |

Estas unidades son las del catálogo de respaldo existente. En `/api/data` se
conservan exactamente las recibidas de NASA, por ejemplo `C` para temperatura.
Usar la unidad de la serie al mostrar los datos. No se convierten valores ni se
interpreta `mm/day` como un acumulado mensual. El catálogo identifica al proveedor;
las fuentes concretas recibidas también figuran en `metadata.header.sources`.

## GET /api/cities

Lista las 25 ciudades iniciales. Filtros opcionales: `province` y `region`, combinados
por intersección. Ignoran caso y tildes; provincia admite nombre o ID GeoRef, `CABA`
y `Tierra del Fuego`. Región admite su nombre y el alias `centro-pampeana`.
Un filtro de texto válido sin coincidencias devuelve 200, `data=[]` y `count=0`.

Solicitud: `GET /api/cities?province=Misiones&region=NEA`. Extracto de respuesta 200
con los campos de procedencia abreviados:

```json
{
  "status": "ok",
  "data": [{
    "id": "posadas", "name": "Posadas",
    "province": "Misiones", "province_id": "54", "region": "NEA",
    "country": "Argentina", "country_code": "AR",
    "latitude": -27.3896545260435, "longitude": -55.9193081767805,
    "coordinate_source": {"name": "GeoRef Argentina", "entity_id": "54028030"}
  }],
  "meta": {"api_version": "1", "count": 1, "filters": {"province": "Misiones", "region": "NEA"}}
}
```

Cada ciudad incluye el `coordinate_source` completo del catálogo: URL, consulta,
registro oficial, ID, campo `centroide` y fecha de obtención. No se pierde esa
procedencia en la respuesta real.

## GET /api/cities/{city_id}

Solicitud: `GET /api/cities/posadas`. Devuelve 200 con `data` igual al objeto de
ciudad del listado. Extracto con la procedencia abreviada:

```json
{
  "status": "ok",
  "data": {
    "id": "posadas", "name": "Posadas",
    "province": "Misiones", "province_id": "54", "region": "NEA",
    "country": "Argentina", "country_code": "AR",
    "latitude": -27.3896545260435, "longitude": -55.9193081767805,
    "coordinate_source": {"name": "GeoRef Argentina", "entity_id": "54028030"}
  },
  "meta": {"api_version": "1"}
}
```

Los IDs usan minúsculas ASCII, números y guiones, como `comodoro-rivadavia`.
Un formato incorrecto devuelve 400; un ID bien formado que no existe devuelve 404
con `error.code="city_not_found"`.

## GET /api/regions

Regiones y cantidad de ciudades presentes, derivadas del catálogo. La clasificación
regional es del proyecto; `city_count` es un conteo, no una puntuación ambiental.

Solicitud: `GET /api/regions`. Respuesta 200:

```json
{
  "status": "ok",
  "data": [
    {"name": "Patagonia", "city_count": 7},
    {"name": "Centro y región pampeana", "city_count": 7},
    {"name": "Cuyo", "city_count": 3},
    {"name": "NOA", "city_count": 4},
    {"name": "NEA", "city_count": 4}
  ],
  "meta": {"api_version": "1", "count": 5}
}
```

## POST /api/data

Requiere `Content-Type: application/json` y un objeto JSON de hasta 16 KiB por
defecto. Consulta una ciudad y devuelve únicamente las variables seleccionadas.

| Campo | Tipo | Regla / valor por defecto |
| --- | --- | --- |
| city_id | string | Obligatorio, ID de una ciudad argentina del catálogo. |
| variables | array de strings | Opcional; las seis por defecto. Lista no vacía de códigos exactos; duplicados eliminados conservando el orden. |
| start_year | integer | Opcional, 2000. Desde 1981, sin strings, booleanos ni decimales. |
| end_year | integer | Opcional, 2024. Mayor o igual al inicio; no se admiten años futuros respecto del año UTC del servidor. |
| force | boolean | Opcional, false. Intenta actualizar aunque exista una caché válida. |

No se admiten otros campos. `latitude`, `longitude`, `lat`, `lon` o `coordinates`
devuelven 400 `coordinates_not_supported`. No hay selección de varias ciudades
en este endpoint. El período utiliza años completos; no se admiten fechas diarias.
Que un año sea válido no garantiza cobertura completa de NASA para ese año.

Solicitud de ejemplo:

```json
{"city_id":"mendoza","variables":["T2M"],"start_year":2000,"end_year":2024,"force":false}
```

Extracto de respuesta 200 con datos reales de la caché previamente verificada de
Mendoza. Se muestran sólo dos de los 300 meses y parte de los campos de ciudad y
metadatos; la respuesta real conserva todos esos campos y la serie completa:

```json
{
  "status": "ok",
  "data": {
    "city": {"id":"mendoza","name":"Mendoza","country_code":"AR"},
    "provider":"NASA POWER", "dataset":"MERRA-2", "frequency":"monthly",
    "start_year":2000, "end_year":2024,
    "variables": {
      "T2M": {
        "provider":"NASA POWER", "dataset":"MERRA-2", "variable":"T2M",
        "name":"Temperatura media", "unit":"C",
        "latitude":-32.8985811304419, "longitude":-68.8464060446987,
        "start_year":2000, "end_year":2024, "frequency":"monthly",
        "series":[{"date":"2000-01","value":24.74},{"date":"2000-02","value":23.5}],
        "metadata":{
          "header":{"sources":["MERRA2","POWER"],"fill_value":-999.0,"time_standard":"LST"},
          "parameter":{"units":"C","longname":"Temperature at 2 Meters"}
        }
      }
    }
  },
  "meta": {
    "api_version":"1", "origin":"cache",
    "fetched_at":"2026-11-14T17:44:54.775518+00:00",
    "requested_variables":["T2M"],
    "quality":{"T2M":{"expected_count":300,"valid_count":300,"missing_count":0}},
    "cache_available":true, "warnings":[]
  }
}
```

Los registros de `series` tienen `date=YYYY-MM` y `value` numérico o `null` para
faltantes. No se interpola ni se transforma un faltante en cero. `quality` conserva
conteos por variable; no expresa significancia estadística ni salud ambiental.

### Caché, proveedor y fallos

Se reutiliza `PowerBulkService` y su caché existente de seis variables. Pedir sólo
`T2M` también puede llenar esa caché completa mediante una única petición NASA;
la respuesta HTTP sólo incluye lo solicitado. Otra selección de variables para la
misma ubicación/período reutiliza la misma entrada, sin nuevas consultas.

`meta.origin` es `cache` o `nasa_power`. `fetched_at` es la fecha UTC de obtención;
una lectura de caché no la cambia. `cache_available` indica que los datos están en
caché o que la escritura terminó correctamente. No se revela la ruta del archivo.

Si falla una actualización, no se sobrescribe una caché válida ni se devuelve éxito
con datos viejos. El error puede añadir `meta.cache_preserved=true` y
`meta.previous_fetched_at`. Una consulta posterior sin `force` puede reutilizarla.
Una descarga válida con error de escritura devuelve 200, `cache_available=false`
y advertencia `cache_write_failed`. Una caché inválida recuperada mediante una
descarga válida informa `cache_recovered`. No hay reintentos automáticos.

El proveedor conserva su timeout de 60 segundos. Las obtenciones se serializan
dentro de cada proceso para reutilizar la caché entre solicitudes concurrentes;
las rutas de catálogo y salud no esperan ese bloqueo. Las esperas pueden aumentar
si hay solicitudes de datos en cola. No hay coordinación entre múltiples procesos:
la ejecución local documentada usa un proceso; el despliegue multiproceso queda pendiente.

## Estados HTTP y códigos de error

| HTTP | error.code | Significado |
| --- | --- | --- |
| 400 | invalid_request | JSON, campos, filtros, variables, tipos, IDs o años inválidos. |
| 400 | coordinates_not_supported | Coordenadas libres no habilitadas. |
| 404 | city_not_found | ID válido fuera del catálogo argentino. |
| 404 | not_found | Ruta inexistente, incluidas funcionalidades futuras aún no implementadas. |
| 405 | method_not_allowed | Método incorrecto; se conserva `Allow`. |
| 413 | request_too_large | Cuerpo superior al límite configurado. |
| 415 | unsupported_media_type | Content-Type no JSON. |
| 500 | internal_error | Fallo interno, sin detalles privados. |
| 502 | provider_error | Error HTTP u otro fallo de respuesta externa. |
| 502 | provider_invalid_response | JSON externo inválido, datos incompletos o actualización que degradaría la caché. |
| 503 | provider_unavailable | No se pudo establecer comunicación con NASA POWER. |
| 504 | provider_timeout | NASA POWER excedió su tiempo de espera. |

## Integración desde frontend y CORS

El frontend HTML/Jinja se sirve desde la misma aplicación Flask. CORS permanece
desactivado; `static/js/shared/api.js` usa URLs relativas para `/api`. No se necesita un
origen externo ni un comodín. Si se separan los servidores en el futuro, acordar
una lista explícita de orígenes antes de habilitar CORS.

```javascript
const response = await fetch('/api/data', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({city_id: 'mendoza', variables: ['T2M', 'RH2M'], start_year: 2000, end_year: 2024})
});
const payload = await response.json();
if (!response.ok) throw new Error(`${payload.error.code}: ${payload.error.message}`);
const temperature = payload.data.variables.T2M;
// Usar temperature.unit, temperature.series y temperature.metadata.
```

Ejemplos para compartir desde PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/health
Invoke-RestMethod 'http://127.0.0.1:5000/api/cities?province=Chubut&region=Patagonia'
$earthlensBody = @{ city_id='mendoza'; variables=@('T2M','RH2M'); start_year=2000; end_year=2024 } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:5000/api/data -Method Post -ContentType 'application/json' -Body $earthlensBody
```

Configuración opcional del servidor mediante `create_app(config)` o variables de
entorno con prefijo `EARTHLENS_`: `CACHE_DIR`, `CATALOG_PATH`, `POWER_REQUEST_DELAY`,
`POWER_CACHE_MAX_AGE_DAYS` y `MAX_CONTENT_LENGTH`. Los valores numéricos usan sintaxis
JSON en el entorno. La configuración no se acepta desde las solicitudes HTTP.

## Verificación

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m flask --app app:create_app routes
.\venv\Scripts\python.exe -m pip check
```

El cliente de pruebas usa NASA simulada y cachés temporales. Se verificaron además
lecturas HTTP de las cachés reales preexistentes de Comodoro Rivadavia, Mendoza y
Posadas, con el acceso a NASA bloqueado: ninguna petición externa ni cambio en los
25 archivos de caché existentes. La integración de red previa sigue siendo optativa.

La arquitectura sigue las recomendaciones oficiales de Flask para
[Application Factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/),
[Blueprints](https://flask.palletsprojects.com/en/stable/blueprints/) y
[cliente de pruebas](https://flask.palletsprojects.com/en/stable/testing/).


## Análisis y comparación integrados

Los seis endpoints anteriores conservan su contrato. Se agregan:

| Método | Ruta | Entrada |
| --- | --- | --- |
| GET | `/api/summary` | Query `city_id`, `start_year` y `end_year` opcionales. Resume seis variables con una única lectura/obtención mensual. |
| POST | `/api/analyze` | JSON `city_id`, `variable` opcional (T2M por defecto), `start_year` y `end_year` opcionales (2000–2024). |
| POST | `/api/compare` | JSON `city_id_a`, `city_id_b`, variable y período compartidos opcionales. |
| GET | `/api/missions` | Catálogo de preguntas de investigación del equipo. |
| GET | `/api/missions/{mission_id}` | Detalle, hipótesis, pistas y enlace con IDs argentinos o 404. |
| GET | `/api/catalog` | Variables y fenómenos del recomendador, proyectados al método vigente. |
| GET | `/api/variables/recommend` | Query `phenomenon`: variables sugeridas por el catálogo curado del equipo. |

Todas las respuestas usan el mismo sobre `status`, `data`, `meta`. Las rutas de
análisis no aceptan coordenadas libres, `force`, ajustes del motor ni configuración.
El período debe abarcar al menos tres años. Los campos desconocidos se rechazan.
Las unidades y la fecha original de obtención se conservan.

```javascript
const response = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ city_id: 'mendoza', variable: 'T2M', start_year: 2000, end_year: 2024 })
});
const payload = await response.json();
if (!response.ok) throw new Error(payload.error.message);
const analysis = payload.data;
// analysis.series: [{year, value}], medias anuales del motor real.
// analysis.statistics: pendiente, IC95%, p-valor, dirección y evidencia.
// analysis.unit, metadata, provenance, completeness, method: contexto trazable.
```

`/api/summary` entrega `data.estimations` por código. Si una variable no cumple la
cobertura anual, esa entrada lleva `status=insufficient_data` y `completeness`, sin
estadísticas. `/api/compare` entrega `location_a`, `location_b`, `deltas` y
`comparison_conclusion` del motor. Exige iguales unidades y años válidos; no prueba
la significancia de la diferencia entre ciudades.

Errores nuevos: 422 `insufficient_data`, 422 `incompatible_analysis` y
503 `analysis_unavailable` (falta SciPy). Los errores del proveedor conservan sus
estados y códigos públicos. No hay reemplazo por datos simulados.

Contrato del motor, criterios de cobertura y limitaciones: [integration.md](integration.md).

## Earth Fingerprint y Earth Radar — versión provisional

| Método | Ruta | Alcance |
| --- | --- | --- |
| GET | `/api/fingerprint/{city_id}` | Seis indicadores por ciudad; `start_year` y `end_year` opcionales, por defecto 2000–2024. |
| GET | `/api/radar` | Lectura de un estudio persistido, con filtros `province`, `region`, `variable`, `direction`, `evidence_status`. |

Contrato completo, estados, metodología, compatibilidad, errores y ejemplos reales:
[products.md](products.md). El resultado común vive en `services/science/analysis_results.py`
y lo produce `AnalysisService.results()` sin duplicar ni modificar el motor.

Los análisis calculados se identifican como `provisional`; `data_status=valid`
sólo indica disponibilidad. No hay descubrimientos confirmados ni ajuste múltiple
aplicado. `statistics` conserva la precisión entregada por el motor;
`statistics_unrounded=null` hasta recibir ese contrato del responsable estadístico.
La precipitación conserva la tasa media en `mm/day`; los extremos son medias de
extremos mensuales. No se generan puntuaciones ambientales.

Fingerprint devuelve HTTP 200 con un perfil completo o parcial y estados por
variable. Validaciones de ciudad/período siguen devolviendo 400/404. Radar devuelve
503 `radar_unavailable` antes de generar el estudio y 503 `radar_invalid_artifact`
si el archivo no es válido. Los códigos y respuestas anteriores no cambian.

```powershell
# Familia completa: 25 ciudades x 6 variables, siempre desde caché y sin red.
docker compose exec -T backend python -m scripts.maintenance.generate_radar

Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/mendoza?start_year=2000&end_year=2024'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar?region=Cuyo&variable=T2M&evidence_status=provisional_signal'
```

Los filtros de Radar seleccionan filas del artefacto; no cambian `family`,
`summary` ni `multiple_testing` y nunca vuelven a ejecutar análisis o correcciones.
Cada registro tiene coordenadas, procedencia y enlaces a Explorador y Resultados.

Ejemplos JSON completos de la caché real:
[Comodoro Rivadavia](../examples/fingerprint-comodoro-rivadavia.json),
[Mendoza](../examples/fingerprint-mendoza.json),
[Posadas](../examples/fingerprint-posadas.json),
[Radar Cuyo/T2M](../examples/radar-cuyo-t2m.json).

### Interfaces de producto (fase 1)

`GET /radar` y `GET /fingerprint` sirven HTML en el mismo origen de la API.
No modifican los contratos JSON. Radar pasa los cinco filtros documentados a
`/api/radar`; ordena las filas en el navegador sin recalcular estadísticas.
Su resumen siempre corresponde al estudio completo. En los enlaces compartidos,
`variable=` indica todos los indicadores; la vista inicial usa `T2M`.

Fingerprint consume `/api/cities` y uno o dos perfiles, sin parámetros de años
(2000–2024, período ya cacheado). Sus parámetros **web**, `city_id` y
`city_id_b`, seleccionan las ciudades; no se agregan al contrato del endpoint
de perfiles. La superposición histórica exige claves `comparison.key` iguales,
disponibilidad completa y ausencia de incoherencias de evidencia. Si no se
cumple, los perfiles y gráficos se muestran separados. No se infieren diferencias
significativas entre ciudades. La interfaz genera tarjetas desde `results`,
con nombres, unidades, grupos y enlaces recibidos; no fija seis códigos en JS.

Ambas interfaces descartan respuestas anteriores ante cambios rápidos y ocultan
resultados previos durante una nueva consulta o error. Las rutas anteriores de
Explorador, Resultados y Comparador mantienen sus parámetros y comportamiento.


## API aditiva de series científicas nativas

`GET /api/science/variables` devuelve únicamente variables con valores reales en
cachés validadas de esta instalación. No hace consultas externas. Cada entrada
incluye proveedor, producto, versión conocida o `null`, variable, unidad,
frecuencia, resolución y `verification` con ciudades, períodos, cobertura y fechas.
`available: true` no garantiza cobertura universal ni habilita análisis estadísticos.
`meta.availability` es `verified_cached_data`; `meta.radar_family_changed` es `false`.
El endpoint histórico `/api/variables` sigue devolviendo el catálogo POWER de seis
variables, incluso antes de inicializar sus datos.

`POST /api/science/data` usa JSON con estos campos:

| Campo | Tipo y contrato |
| --- | --- |
| `provider` | Obligatorio: `power`, `modis`, `gldas` o `gpm`; disponibilidad comprobada en el catálogo dinámico. |
| `city_id` | ID obligatorio del catálogo argentino. |
| `variables` | Lista no vacía de códigos ya verificados en `/api/science/variables`. |
| `start_year`, `end_year` | Enteros; por defecto 2000 y 2024. Sin fechas futuras ni período invertido. |
| `force` | Booleano, por defecto `false`; actualización remota explícita. |

Se rechazan campos extra y coordenadas libres. La primera verificación se hace
con `scripts.data.fetch_science`; HTTP no habilita candidatos sin observaciones.
Se prioriza la caché. Un fallo o una actualización degradada conserva la serie
anterior, pero devuelve error; no presenta esa serie como descarga nueva.
Si una extracción validada abarca un período mayor, se seleccionan sólo las
fechas solicitadas sin consultar al proveedor. Se conservan valores, QA y fecha
de obtención original; `provenance.cache_selection` documenta el período de origen
y `operation: "date_filter_only"`. No se combinan versiones, políticas QA ni vías
de acceso para completar una selección. `force: true` omite esta reutilización.
Esta mejora corresponde a `/api/science`; el contrato de `/api/data` se conserva.

Solicitud de una serie POWER existente:

```json
{
  "provider": "power",
  "city_id": "mendoza",
  "variables": ["T2M"],
  "start_year": 2000,
  "end_year": 2024
}
```

La respuesta 200 mantiene el sobre `status`, `data`, `meta`. `data` es una lista de
registros `earthlens.scientific-series.v1`, uno por variable: `provider`, `product`,
`product_version`, `cache_version`, `variable`, `unit`, `location`, `period`,
`frequency`, `spatial_resolution`, `series`, `coverage`, `fetched_at`, `metadata`,
`provenance` y `analysis`. Cada punto tiene `date` ISO y `value` numérico o `null`.
MODIS agrega `raw_value` y `quality` con las banderas originales y los motivos de
exclusión. `coverage.missing_count` incluye los valores excluidos por QA; no implica
que el proveedor haya omitido esas fechas.

No asumir doce registros por año: MODIS conserva sus compuestos de 16 días. En
POWER, el día 01 etiqueta el mes completo. La versión científica puede ser `null`;
no inferirla de `cache_version`. `analysis.enabled` y `meta.analysis_enabled` son
`false`: este contrato todavía no alimenta el motor ni amplía Radar/Fingerprint.

Ejemplos PowerShell, usando sólo variables publicadas en el catálogo dinámico:

```powershell
Invoke-RestMethod 'http://127.0.0.1:5000/api/science/variables'

$body = @{ provider='modis'; city_id='posadas'; variables=@('NDVI','EVI'); start_year=2024; end_year=2024 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5000/api/science/data' -ContentType 'application/json' -Body $body
```

Errores: 400 `invalid_request`, 404 `city_not_found`, 502
`provider_invalid_response`, 503 `provider_not_verified`, `provider_auth_required`
o `provider_unavailable`, 504 `provider_timeout`. Los detalles internos y tokens
no se exponen. GLDAS y GPM ya tienen históricos reales 2000–2024 en las 25
ciudades. Procedencia, comandos y límites:
[scientific-sources.md](../science/scientific-sources.md).

### Comparaciones descriptivas: `POST /api/science/compare`

Requiere dos selecciones con `provider`, `city_id` y `variable`, y años enteros.
Admite la misma variable del mismo producto/versión en dos ciudades o la
comparación explícita POWER–IMERG. Rechaza coordenadas libres, campos extra,
productos/variables incompatibles y frecuencias diferentes; no remuestrea.

```json
{
  "selections": [
    {"provider":"power","city_id":"mendoza","variable":"PRECTOTCORR"},
    {"provider":"gpm","city_id":"mendoza","variable":"precipitation"}
  ],
  "start_year":2000,
  "end_year":2024,
  "target_unit":"mm/day"
}
```

La respuesta contiene `data.sources` (dos contratos nativos sin transformar),
`data.plots` (dos proyecciones con ciudad, `source_unit`, `display_unit`, `factor`
y `series`) y `data.comparison` (`scope: "descriptive_only"`,
`statistical_test_performed: false`, fechas comunes válidas y advertencias).
POWER conserva factor 1; GPM pasa de `mm/hr` a `mm/day` con factor 24. Los nulos
siguen siendo nulos. No es una conversión a acumulados mensuales. Grillas y
métodos son diferentes; no se supone equivalencia ni causalidad. Una incompatibilidad
devuelve 422 `incompatible_analysis`; la falta de conversión explícita devuelve 400.

### Entidades hidrológicas: `GET /api/science/water-features`

Devuelve el catálogo argentino curado con `id`, `type`, `feature_id` del proveedor,
nombre, provincia, producto, versión, SWORD y evidencia geográfica. Actualmente
contiene `chubut-trelew`, tramo `65341000051`. El centroide GeoRef documentado
corresponde a esa entidad curada: no habilita coordenadas libres ni sustituye un
validador territorial general.

### Observaciones de agua: `POST /api/science/water-data`

```json
{
  "feature_id":"chubut-trelew",
  "start_time":"2024-01-01T00:00:00Z",
  "end_time":"2024-12-31T23:59:59Z",
  "force":false
}
```

Se exige identificador del catálogo, fechas ISO con zona horaria y período no
futuro ni invertido; `force` es booleano opcional. Prioriza la caché exacta.
La respuesta usa `earthlens.hydrology-series.v1`: `feature`, `product`,
`product_version`, `sword_version`, `period`, `frequency`, `geometries`,
`variables`, `fetched_at`, `provenance` y `analysis.enabled: false`.
`variables.wse` y `variables.width` conservan unidades `m`, cobertura y series
con fecha de paso, valor, valor original, incertidumbre, geometría, calidad y
atributos originales. Los 31 pasos reales del piloto 2024 no se transforman en
doce meses. `quality.review_required: true` impide interpretar disponibilidad
numérica como aceptación científica automática. No se generan tendencias.

Un ID desconocido devuelve 404 `water_feature_not_found`; tipos/fechas/campos
inválidos devuelven 400. Rigen los errores de proveedor 502/503/504 y mensajes
públicos controlados. No se admiten IDs externos arbitrarios, coordenadas ni
configuración remota en el cuerpo.

### Consumidores actuales

`/sources` y el panel desplegable en `/explorer`, `/compare`, `/radar`,
`/fingerprint` y `/missions` consumen estos contratos, mostrando QA, procedencia,
unidades y gráficos nativos. El deslizador recorre la respuesta ya recibida.
Cerrar el panel evita cargar su catálogo. La familia estadística de Radar y los
indicadores de Fingerprint mantienen su contrato POWER previo. Time Machine y
Connections todavía no consumen estos endpoints en sus interfaces. Time Machine
usa el contrato POWER específico documentado debajo; las otras fuentes se
consultan mediante su enlace a `/sources`.

## Earth Time Machine: GET/POST `/api/time-machine`

La página vive en `/time-machine`; también se conservan los alias con guion bajo
y extensión `.html`. No sustituye la portada ni las páginas anteriores.

```json
{"city_id":"mendoza","variable":"T2M","start_year":2000,"end_year":2024,"split_year":2012,"include_regional":true}
```

Ciudad obligatoria del catálogo argentino; variable POWER admitida; años enteros
no futuros, al menos cuatro años; corte opcional con al menos dos años por época.
`include_regional` es booleano, por defecto `true`; `region` es un filtro opcional.
No se admiten campos extra, coordenadas, áreas, configuraciones del motor ni `force`.
GET admite esos mismos filtros como query; `include_regional` acepta `true/false`
o `1/0` y la ciudad por defecto es Comodoro Rivadavia.

La respuesta usa el sobre común. `data` contiene `location`, `period`, `variable`,
`unit`, `source`, `timeline`, `statistics`, `completeness`, `anomalies`,
`period_comparison`, `regional_cities`, `regional_errors`, `metadata`, `provenance`
y `scientific_status: "provisional"`. La línea temporal incluye valores anuales,
anomalías relativas a la media del período y colores calculados por el motor del
equipo. `provenance.source_period` identifica el histórico cacheado del que se
seleccionaron las fechas, conservando la fecha original de obtención.

El acceso es **sólo caché**: no descarga al navegar, animar o consultar ciudades.
La falta de caché de la ciudad principal devuelve 503 `cache_unavailable`, sin
muestras ni valores generados. Los fallos regionales se informan por ciudad sin
presentarlos como observaciones. La revisión científica de anomalías/comparación
de épocas sigue pendiente; no amplía Radar ni confirma descubrimientos.

`spatial_zone.enabled` es `false`, `spatial_zone.cells` está vacío y
`capabilities` deshabilita coordenadas libres, redimensionamiento espacial y
pronósticos. La grilla artificial de la versión anterior no está habilitada.

### Actualización de main: POST `/api/forecast`

```json
{"city_id":"mendoza","variable":"T2M","start_year":2000,"end_year":2024,"forecast_start":2025,"forecast_end":2030,"custom_threshold":20.0,"custom_direction":"above"}
```

Se usan exclusivamente históricos cacheados: cinco años válidos como mínimo,
ciudad del catálogo y variable POWER. Los años futuros son enteros posteriores
al último dato, hasta 30 años de horizonte. `forecast_horizon` es opcional;
el umbral debe ser finito y su dirección `above` o `below`. No se aceptan series,
coordenadas, unidades sobreescritas ni campos extra. Errores: 400 por parámetros,
422 por cobertura insuficiente y 503 por caché ausente, sin descargas ni muestras.

El sobre común contiene la proyección en `data`: `years`, `history`, `window`,
`model`, `summary`, `conclusions`, ciudad, unidades, metadata y procedencia.
Se identifica como `record_type: "model_projection"`, científicamente
`provisional`, con validación pendiente. No se mezcla con las observaciones,
no atribuye causalidad y la heurística de confianza no se presenta como validación.
Time Machine ahora incluye `forecast` y habilita esa capacidad; sigue sin áreas
simuladas ni coordenadas libres. No es TimesFM ni un modelo climático físico.
