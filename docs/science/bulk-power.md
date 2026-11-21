# Catálogo argentino, obtención masiva y caché de NASA POWER

EarthLens está restringido a la **República Argentina**. Esta etapa incorpora las
25 ciudades indicadas por Patagonia Prime; no incorpora análisis estadístico,
Earth Radar, Earth Fingerprint ni una API Flask.

## Catálogo y procedencia

`data/cities.json` conserva nombre, ID propio estable, provincia/jurisdicción y su
ID oficial, región del proyecto, país `Argentina`/`AR`, latitud, longitud y
`coordinate_source`. Esta última contiene la consulta, el ID de localidad censal,
la fecha de obtención y el registro original de GeoRef.

Las coordenadas se obtuvieron mediante la
[API oficial de localidades censales GeoRef](https://datosgobar.github.io/georef-ar-api/referencia/operations/localidades-censales/get/),
usando su modalidad de [consultas por lotes](https://datosgobar.github.io/georef-ar-api/bulk/).
Se conservan los centroides recibidos, sin inventar ni redondear coordenadas. GeoRef
usa nombres oficiales como `San Carlos de Bariloche` y `Ciudad Autónoma de Buenos
Aires`; el catálogo conserva los nombres de presentación `Bariloche` y `Buenos Aires`.
Las cinco regiones siguen la selección del proyecto, no una regionalización de GeoRef.

```python
from services.geography.cities import get_city, list_cities

all_cities = list_cities()
patagonia = list_cities(region="Patagonia")
chubut = list_cities(province="Chubut")
city = get_city("comodoro-rivadavia")  # None si el ID no existe
```

Los filtros ignoran caso y tildes; aceptan ID provincial, `CABA`, `Tierra del Fuego`
y el alias de región `centro-pampeana`. Para ampliar el catálogo con localidades
argentinas, agregar una selección explícita a `CITY_SPECS` de
`scripts/data/build_city_catalog.py`, conservando los IDs existentes, y reconstruir:

```powershell
.\venv\Scripts\python.exe -m scripts.data.build_city_catalog --check-only
.\venv\Scripts\python.exe -m scripts.data.build_city_catalog
```

Ambos comandos consultan GeoRef; sólo el segundo escribe el catálogo. Una búsqueda
ambigua, provincia incorrecta o respuesta incompleta falla antes de sustituirlo.
No se exige un tamaño fijo de 25 en el cargador: es el catálogo inicial.

## Ejecución desde la raíz del repositorio

La CLI requiere un selector explícito, no descarga nada al ejecutarse sin argumentos.
Los siguientes comandos usan **2000–2024** y las seis variables por defecto.

```powershell
# Planificar las 25 ciudades sin consultar NASA ni escribir cachés.
.\venv\Scripts\python.exe -m scripts.data.fetch_power --all --dry-run

# Una ciudad o el subconjunto inicial de verificación.
.\venv\Scripts\python.exe -m scripts.data.fetch_power --city comodoro-rivadavia
.\venv\Scripts\python.exe -m scripts.data.fetch_power --cities comodoro-rivadavia mendoza posadas

# Selecciones por región o provincia.
.\venv\Scripts\python.exe -m scripts.data.fetch_power --region Cuyo
.\venv\Scripts\python.exe -m scripts.data.fetch_power --province Chubut

# Período configurable y actualización forzada.
.\venv\Scripts\python.exe -m scripts.data.fetch_power --city mendoza --start-year 2010 --end-year 2024
.\venv\Scripts\python.exe -m scripts.data.fetch_power --city mendoza --force

# Catálogo completo: ejecución manual posterior; no se ejecutó en esta etapa.
.\venv\Scripts\python.exe -m scripts.data.fetch_power --all
```

`--cache-dir RUTA` cambia el directorio; `--max-age-days N` configura una vigencia
opcional; `--delay N` modifica el intervalo mínimo entre inicios de consultas. El
valor por defecto es un segundo y el servicio es secuencial, atendiendo a las
[indicaciones de NASA sobre consultas múltiples](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/).
No se realizan reintentos automáticos. La CLI devuelve 0 si todas las ubicaciones
terminan correctamente, 1 si hay errores individuales y 2 ante argumentos inválidos.

La salida JSON muestra estado, procedencia (`nasa_power` o `cache`), fechas,
cobertura, advertencias y ruta de caché por ubicación. Las series completas quedan
en la caché; el servicio Python también las devuelve en memoria:

```python
from services.providers.bulk import PowerBulkService

service = PowerBulkService()
report = service.collect_cities(city_ids=["comodoro-rivadavia", "mendoza", "posadas"])
single = service.collect_city("mendoza", start_year=2000, end_year=2024)
regional = service.collect_cities(region="NEA")
# También admite province=..., catálogo completo sin filtros y force=True.
```

## Caché, errores y faltantes

El directorio por defecto es `data/cache/power/`; sus archivos están ignorados por
`data/cache/.gitignore`. Las claves SHA-256 provienen de una consulta JSON canónica
que distingue proveedor, dataset, endpoint, comunidad, frecuencia, coordenadas,
variables y años. Los archivos contienen `schema_version`, `query`, `fetched_at`,
`location` y `data`, con las seis series normalizadas, unidades y metadatos originales.
Las fechas son UTC con zona horaria; un acierto conserva la fecha de obtención.

Sin vencimiento configurado, se reutilizan los datos históricos hasta una
actualización explícita. Esto no implica que NASA nunca revise sus productos.
`--force`/`force=True` siempre intenta una nueva consulta. La caché no comparte
resultados entre períodos distintos ni aproxima coordenadas para unificarlas.

Antes de guardar se exige que estén las seis variables y todos los meses del
período, con unidades, fuentes y contexto de consulta coherentes. Se rechazan
valores no finitos y rellenos sin normalizar. Los nulos científicos sí se conservan
como `null`: se informan `expected_count`, `valid_count` y `missing_count` por serie,
sin imputar ni aplicar umbrales arbitrarios. Una serie completamente nula es un error.

Una actualización que pierda valores disponibles reemplazándolos por nulos también
se rechaza. No se mezclan valores viejos y nuevos. Una falla de red o respuesta
incompleta deja intacta la caché previa y devuelve `status="error"`,
`cache_preserved=true` y su fecha anterior. Una consulta posterior sin forzar puede
seguir leyéndola. No se presenta la caché conservada como una descarga exitosa.

Las escrituras usan un archivo temporal y reemplazo atómico: se evita dejar JSON
parcial. Si la descarga fue válida pero falla la escritura, se devuelve el dato en
memoria con `cache_written=false` y una advertencia. Una caché corrupta se informa
y se intenta recuperar con una consulta nueva; nunca se escribe la respuesta fallida.
El procesamiento continúa con las otras ciudades. La versión actual no coordina
bloqueos entre varios procesos; ejecutar un único lote por directorio de caché.

## Ubicaciones argentinas fuera del catálogo

La arquitectura permite `PowerBulkService.collect_location(latitude, longitude)`
con un `territory_validator` inyectable que devuelva `TerritoryEvidence`. Debe
aportar pertenencia `AR`, resultado interior y fuente de límites oficiales con método
`point_in_polygon` u `official_boundary_service`. El validador debe tratar costas,
fronteras y casos ambiguos según esos límites, no según la lista de ciudades.

**El adaptador real de límites queda pendiente.** Por defecto, una ubicación libre
produce `TerritoryValidationUnavailable` antes de consultar NASA, aunque esté dentro
de una caja rectangular aproximada de Argentina. No hay un indicador que permita
omitir esta validación. Los validadores simulados de las pruebas no son aptos para
uso científico. El proveedor POWER existente mantiene su contrato técnico; las
futuras rutas HTTP deberán pasar por los servicios con esta restricción.

Los centroides de ciudades son ubicaciones de consulta de una grilla NASA POWER;
no representan mediciones de estaciones ni promedios territoriales urbanos.

## Verificación realizada

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas sin red simulan respuestas NASA y GeoRef, incluidos fallos parciales,
cambios de período, vencimiento, caché corrupta, actualizaciones degradadas y
reemplazos interrumpidos. El recorrido de las 25 ciudades sólo se prueba con NASA
simulada.

El 14 de noviembre de 2026 se realizaron **tres consultas NASA reales**, exclusivamente
para Comodoro Rivadavia, Mendoza y Posadas en 2000–2024. Cada ciudad devolvió las seis
variables con 300 registros mensuales disponibles por variable. Una repetición del
mismo comando, bloqueando la función de acceso a red en la comprobación, produjo
tres aciertos de caché, cero peticiones y archivos/fechas de obtención sin cambios.
Las otras 22 ciudades no se consultaron en NASA en esta etapa.
