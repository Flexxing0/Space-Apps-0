# Radar y Fingerprint — contratos v1 e interfaces

Implementación sobre `feature/backend-api`, tomando como referencia la auditoría de
`b4093bc`. La primera etapa incorporó los contratos de backend; la fase 1
posterior agrega las interfaces, sin proveedores, bases de datos ni servicios Docker.
Los endpoints anteriores conservan sus solicitudes y respuestas.

## Interfaces funcionales — fase 1

- **`/radar`**: mapa Leaflet con todas las ciudades del estudio; filtros por
  provincia, región, indicador, dirección y evidencia. Las ciudades fuera de la
  selección se conservan como marcadores atenuados. Cuando hay varios indicadores,
  el marcador informa sus resultados individuales, sin resumirlos en un puntaje.
  Tarjetas con pendiente, cambio por década, IC95% de la pendiente, p nominal,
  dirección, período, cobertura mensual/anual, fuente y fecha original. El orden
  por magnitud sólo se habilita con un indicador seleccionado. El resumen global
  y la familia no cambian al filtrar. «Investigar tendencia» abre Resultados.
- **`/fingerprint`**: selección de una o dos ciudades, tarjetas dinámicas,
  distinción de principales/extremos y gráficos Chart.js con las series **anuales
  del motor**, sin recalcular regresiones ni imputar faltantes. La comparación
  requiere compatibilidad estricta según el contrato; en otro caso se muestran
  gráficos separados. Enlaces por indicador al Explorador, Resultados y, cuando
  son compatibles, al Comparador existente. No hay gráfico radial, normalización
  ni puntuación ambiental.
- Navegación compartida en todas las páginas, con menú colapsable y estado activo.
  Conserva los colores, tipografía, tarjetas, marca y componentes del equipo.
- Carga explícita, errores con reintento, resultados vacíos y protección frente a
  respuestas tardías, con cancelación y control de secuencia. Si no carga Leaflet
  o Chart.js, se informa y se mantienen disponibles las tarjetas y sus enlaces.

La interfaz de perfiles usa por ahora el período cacheado **2000–2024**. No habilita
selección de nuevos períodos ni fuerza descargas. Radar lee exclusivamente el
artefacto existente. La comparación es descriptiva y las señales siempre se
identifican como provisionales. Se informa que POWER representa una grilla, que
la precipitación es tasa media en `mm/day` y que los extremos no son máximos o
mínimos absolutos anuales. El motor y su redondeo permanecen intactos.

Ejemplos de navegación:

```text
http://127.0.0.1:5000/radar?region=Cuyo&variable=T2M
http://127.0.0.1:5000/radar?variable=&evidence_status=provisional_signal
http://127.0.0.1:5000/fingerprint?city_id=comodoro-rivadavia
http://127.0.0.1:5000/fingerprint?city_id=mendoza&city_id_b=posadas
```

Verificación reproducible: [docker.md](../operations/docker.md). `scripts/audit/check_product_pages.py`
contrasta las respuestas reales, filtros, cambios rápidos de ambos selectores,
errores/reintento, compatibilidad, extensibilidad de tarjetas, navegación y
anchos de 1440, 1280, 820 y 390 px. Sus fixtures de errores y contratos son sólo
pruebas de software interceptadas; no se guardan como observaciones. Las capturas
usan respuestas reales. Informes/capturas en carpetas únicas ignoradas por Git:
`data/cache/reports/interfaces-phase1/`. La suite sin red está en `tests/`.

Fases 2–7 pendientes: contrato multiproveedor, pruebas reales y acceso científico
a GLDAS, MODIS, GPM y SWOT/Hydrocron, e integración posterior. No se habilitó ninguna
de esas fuentes ni se amplió la familia del estudio Radar.

## Estado científico y resultado común

Los productos reutilizan `AnalysisService.results()` y el motor existente
`services/science/trend_analysis.py`. No hay una segunda implementación de regresión.
Cada ubicación obtiene las seis variables en una única lectura/consulta mediante
el proveedor y la caché existentes; los errores de análisis se aíslan por variable.

Esquema común: `earthlens.analysis.v1`. Metodología:
`earthlens.power.annual-ols.provisional.v1`.

| Campo | Significado |
| --- | --- |
| `result_id` | Identifica ciudad y variable dentro de una familia: `mendoza:T2M`. |
| `analysis_id` | SHA-256 de ubicación, variable, período, metodología y hash de entrada. Excluye la fecha de ejecución. |
| `variable`, `indicator` | Código POWER, identificador y definición del indicador, grupo `primary` o `extreme`. |
| `unit` | Unidad recibida de NASA. Es `null` si no hay datos disponibles; no se inventa una unidad recibida. |
| `location` | ID, nombre, provincia, región, país, latitud, longitud y procedencia GeoRef. Permite colocar el marcador. |
| `period` | `start_year`, `end_year`, inclusivos. |
| `status`, `data_status` | Estado científico del resultado y disponibilidad del análisis, respectivamente. |
| `statistics` | Copia de las estadísticas entregadas por el motor, sin otro redondeo. Es `null` ante insuficiencia o error. |
| `statistics_unrounded` | Reservado para estadísticas sin redondeo suministradas por el responsable del motor. Actualmente `null`. |
| `precision` | Declara que el motor actual entrega cifras ya redondeadas y si existe una salida de precisión completa. |
| `direction` | Dirección del motor: `increasing`, `decreasing`, `stable`; `null` sin estadísticas. |
| `series` | Medias anuales del motor `[{year,value}]`. Lista vacía sin análisis; nunca se fabrican valores. |
| `coverage.monthly` | Cantidades mensuales esperadas, disponibles y nulas. |
| `coverage.annual` | Años solicitados, válidos y excluidos; proporción de cobertura y criterio del motor. |
| `coverage.by_year` | Meses disponibles/utilizables por el motor, meses excluidos y retención de cada año. |
| `source` | Proveedor, dataset histórico del contrato y metadatos NASA completos. Las fuentes originales están en `metadata.header.sources`. |
| `provenance` | `origin`, fecha UTC original `fetched_at`, SHA-256 del resultado mensual de entrada. |
| `analyzed_at` | Fecha UTC del análisis, separada de la fecha original de obtención. |
| `methodology` | Versión, hash del código del motor, versión SciPy, parámetros, agregación y dependencias científicas pendientes. |
| `evidence` | Estado provisional, indicadores de incoherencia y ajuste múltiple pendiente. |
| `error` | Código y mensaje públicos, o `null`. No contiene excepciones ni rutas locales. |
| `links` | Enlaces relativos a `/explorer` y `/results`, con ciudad, variable y período compatibles con la interfaz actual. |

`statistics` conserva los campos existentes: `slope`, `intercept`,
`change_per_decade`, `total_change`, `p_value`, `significant`, `direction`,
`confidence_interval_95`, `r_value`, `r_squared`, `std_err`, `mean`, `n_years` y el
crítico t añadido por el adaptador. La pendiente y su IC95% están en unidad/año;
el cambio por década está en unidad/década. Los p-valores no son ajustados.

El motor sigue redondeando internamente. El contrato queda preparado para recibir
`unrounded_statistics` en `make_result()`, sin redondearlo ni reconstruirlo; esta
versión no modifica su firma ni afirma disponer de estadísticas de precisión
completa. Ese cambio requiere coordinación con el integrante responsable.

### Estados

| `status` | Uso |
| --- | --- |
| `valid` | Reservado para resultados con metodología aprobada; esta versión no emite este estado científico. |
| `provisional` | Análisis calculado, pendiente de validación científica y ajuste múltiple. |
| `insufficient` | Los datos no satisfacen la cobertura anual del motor. No contiene estadísticas. |
| `error` | No se pudo obtener o analizar la variable. No contiene estadísticas. |

`data_status=valid` significa que el análisis pudo calcularse; **no significa
descubrimiento confirmado**. Un perfil puede contener resultados con estados
distintos. `summary.statuses` cuenta los cuatro estados.

| `evidence.status` | Interpretación |
| --- | --- |
| `provisional_signal` | El motor devuelve significancia nominal, todavía sin validación ni ajuste múltiple. |
| `provisional_no_signal` | El motor no devuelve señal nominal; no demuestra ausencia de cambio. |
| `provisional_inconsistent` | Hay contradicción entre el p-valor devuelto y el indicador de significancia; requiere revisión. |
| `insufficient_data` | Cobertura insuficiente. |
| `error` | Error de obtención/análisis. |
| `confirmed` | Reservado; un filtro por este valor devuelve cero resultados en esta versión. |

Todos los registros tienen `confirmed=false`, `adjustment_status=not_applied` y
`adjusted_p_value=null`. Las incoherencias del motor se señalan sin cambiar sus
estadísticas ni crear p-valores alternativos.

### Indicadores y metodología pendiente

Principales: `T2M`, `PRECTOTCORR`, `RH2M`, `WS2M`. Extremos: `T2M_MAX`, `T2M_MIN`.
La agregación vigente es la media aritmética no ponderada de meses utilizables,
con mínimo de 9 meses por año, 3 años y 70% de cobertura anual, seguida de OLS.

- `PRECTOTCORR` conserva la **tasa media en mm/day**, sin convertirse en acumulado.
- Los extremos representan medias de máximos/mínimos mensuales; no extremos
  absolutos anuales.
- `RH2M` es humedad atmosférica, no humedad del suelo.
- Son datos de grilla, no mediciones de una estación urbana.

Permanecen pendientes: aprobación metodológica, precisión completa, coherencia de
significancia y `slope_tolerance`, autocorrelación/estacionalidad, cobertura,
centinelas, agregación anual y método de comparaciones múltiples. Los perfiles
no generan puntuaciones, normalizaciones ni explicaciones causales.

## GET /api/fingerprint/{city_id}

Query admitida: `start_year`, `end_year`, enteros, por defecto 2000 y 2024. Mínimo
tres años; no se admiten períodos futuros. No acepta `force`, coordenadas libres,
variables, rutas de caché ni parámetros del motor.

Respuesta: sobre habitual `{status:"ok",data:{...},meta:{...}}`.

| Campo de `data` | Contenido |
| --- | --- |
| `schema_version` | `earthlens.fingerprint.v1` |
| `status` | Estado agregado del perfil; provisional si hay algún análisis calculado. |
| `city`, `period`, `generated_at`, `methodology` | Contexto común del perfil. |
| `groups` | Códigos de las cuatro variables principales y los dos extremos. |
| `summary` | Conteos, `data_complete` y cero descubrimientos confirmados. |
| `results` | Seis registros del contrato común. |
| `comparison` | Clave de compatibilidad descriptiva, disponibilidad y validación pendiente. |

Una ciudad desconocida devuelve 404; parámetros inválidos devuelven 400. Una
solicitud válida devuelve HTTP 200 incluso con resultados parciales o con un
perfil `status=error`: el frontend debe inspeccionar el estado del perfil y de
cada registro antes de graficar. Los endpoints anteriores mantienen sus propios
estados HTTP (por ejemplo `/api/analyze` sigue devolviendo 422 por insuficiencia).

La consulta reutiliza la caché; si no existe para el período exacto seleccionado,
puede consultar NASA mediante el servicio existente. No recorta automáticamente
otra caché más amplia. Para una comprobación Python estrictamente sin red, usar
`FingerprintService.profile(..., cache_only=True)`.

`compare_compatibility(a,b)` verifica período, metodología, indicadores, unidades,
fuente/versión API y cobertura mensual/años retenidos idénticos, además de disponibilidad de los seis
análisis. Una clave igual con datos completos habilita comparación descriptiva;
no prueba diferencias significativas entre ciudades. No se modifica `/api/compare`.

Ejemplos reales completos:

- [Comodoro Rivadavia](../examples/fingerprint-comodoro-rivadavia.json)
- [Mendoza](../examples/fingerprint-mendoza.json)
- [Posadas](../examples/fingerprint-posadas.json)

## Generación de Earth Radar

```powershell
docker compose exec -T backend python -m scripts.maintenance.generate_radar --dry-run
docker compose exec -T backend python -m scripts.maintenance.generate_radar
```

El generador utiliza el catálogo argentino completo: actualmente **25 ciudades ×
6 variables = 150 pruebas**, incluidas 100 de indicadores principales y 50 de
extremos. El conjunto se define antes de analizar. No hay filtros de selección de
ciudades o variables en el generador.

**La generación es siempre cache-only:** no consulta NASA ni escribe cachés
POWER, incluso si falta una ciudad. Registra seis errores para esa ciudad y sigue
con las demás. Para preparar otro período, usar por separado el servicio de
obtención existente, por solicitud explícita. `--start-year` y `--end-year`
permiten estudios con otros períodos ya cacheados.

El JSON derivado se guarda por defecto en `data/cache/radar/latest.json`, dentro
del montaje persistente e ignorado por Git. La escritura usa reemplazo atómico y
SHA-256 de integridad. El destino debe estar fuera de `data/cache/power`.
Una escritura fallida no sustituye el artefacto anterior. `--output` permite otro
JSON derivado y `--cache-dir` selecciona las observaciones locales.

La CLI devuelve 0 si todos los análisis están disponibles y 1 si hay errores o
insuficiencia, conservando el estudio parcial para inspección. Una configuración
inválida o fallo de persistencia devuelve 2. `--dry-run` no lee series, consulta
NASA ni escribe archivos.

El artefacto incluye:

- `study_id`: identifica familia y hashes de entrada; se conserva al repetir los
  mismos datos y metodología.
- `run_id`, `started_at`, `generated_at`: identifican cada ejecución UTC.
- `family`: ciudades, variables, manifiesto completo de pruebas y exclusiones.
  `eligible_test_ids` significa cobertura suficiente y sin incoherencia detectada;
  no significa que ya estén habilitadas para un ajuste estadístico.
- `multiple_testing`: familia global, estado `not_applied`, método no seleccionado,
  bloqueos científicos y `ready_for_adjustment=false`.
- `summary`: cantidades del estudio completo, errores, insuficiencia, señales
  nominales provisionales y cero descubrimientos confirmados.
- `results`: todos los registros, incluidos errores e insuficiencia. No se
  eliminan de la familia los análisis sin señal nominal.
- `integrity`: hash del documento completo, excluyendo el propio campo.

No se aplicó FDR ni otra corrección sobre p-valores redondeados. El ajuste futuro
requiere precisión completa y aprobación del responsable estadístico sobre la
familia y el método. Los filtros del usuario nunca podrán redefinir ese universo.

## GET /api/radar

Lee el artefacto existente. No genera estudios, ejecuta regresiones ni consulta
proveedores. Si falta el archivo: 503 `radar_unavailable`. Si está corrupto o no
cumple el contrato: 503 `radar_invalid_artifact`, sin detalles internos.

| Query | Valores |
| --- | --- |
| `province` | Nombre/ID provincial o alias existentes, como `CABA`; sin distinción de tildes/caso. |
| `region` | Regiones existentes y alias, como `Cuyo` o `centro-pampeana`. |
| `variable` | Un código POWER exacto, como `T2M` o `PRECTOTCORR`. |
| `direction` | `increasing`, `decreasing`, `stable`. |
| `evidence_status` | Uno de los estados de evidencia documentados arriba. |

Los filtros se combinan con AND. Parámetros desconocidos, repetidos, vacíos o
códigos inválidos devuelven 400. Un filtro geográfico sin coincidencias devuelve
una lista vacía. No se admiten períodos en este GET: `data.period` describe el
estudio generado previamente.

La respuesta conserva el estudio completo como contexto y sustituye `results`
por la selección. `view.count` y `meta.count` indican las filas devueltas;
`summary`, `family`, `study_id` y `multiple_testing` siguen describiendo las 150
pruebas originales. `artifact_integrity` corresponde al artefacto completo, no al
JSON filtrado. El catálogo para filtros es el snapshot persistido del estudio.

[Ejemplo real: Cuyo y T2M](../examples/radar-cuyo-t2m.json). Contiene tres marcadores,
con el manifiesto global de las 150 pruebas intacto.

## Piloto verificado — 14 de noviembre de 2026

25 ciudades, 150 series y 45.000 valores mensuales reales de 2000–2024. Se
calcularon y persistieron **150 análisis provisionales**, con 25 aciertos de caché,
sin errores ni exclusiones. Hubo **48 señales nominales provisionales**, 102
análisis sin señal nominal y **cero descubrimientos confirmados**.

| Variable | Señal nominal provisional | Sin señal nominal |
| --- | ---: | ---: |
| T2M | 13 | 12 |
| T2M_MAX | 11 | 14 |
| T2M_MIN | 7 | 18 |
| PRECTOTCORR | 8 | 17 |
| RH2M | 4 | 21 |
| WS2M | 5 | 20 |

La generación se ejecutó bloqueando `requests.sessions.Session.request` y
`JsonCache.write`: cero accesos NASA y cero escrituras en observaciones. Los 150
registros persistidos coincidieron con una segunda ejecución del servicio común
(excepto su fecha de ejecución). Para Comodoro Rivadavia, Mendoza y Posadas también
se contrastaron estadísticas con `/api/analyze` y compatibilidad de perfiles.
Los SHA-256 de las 25 cachés originales se conservaron.

## Comandos de verificación

```powershell
docker compose up -d --build --wait --wait-timeout 60
docker compose exec -T -e EARTHLENS_POWER_LIVE=0 backend python -m unittest discover -s tests -v
docker compose exec -T backend python -m pip check

# HTTP desde el propio contenedor (sin instalar curl):
docker compose exec -T backend python -c "import requests; r=requests.get('http://127.0.0.1:5000/api/fingerprint/mendoza', timeout=30); print(r.status_code, r.json()['data']['summary'])"
docker compose exec -T backend python -c "import requests; r=requests.get('http://127.0.0.1:5000/api/radar?region=Cuyo&variable=T2M', timeout=30); print(r.status_code, r.json()['data']['view'])"

Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/comodoro-rivadavia'
Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/mendoza?start_year=2000&end_year=2024'
Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/posadas'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar?region=Cuyo&variable=T2M'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar?province=Chubut&direction=increasing&evidence_status=provisional_signal'
```

No se implementan nuevas vistas. Los registros ya contienen ubicación y enlaces
para que el frontend pueda integrarlos en una etapa posterior autorizada.
