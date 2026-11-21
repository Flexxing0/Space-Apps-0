# Infraestructura predictiva de EarthLens

## Estado y alcance

La rama `feature/backend-api` ya contiene la auditoría histórica de POWER,
GLDAS, GPM y ERA5. La infraestructura nueva reutiliza el catálogo argentino,
el servicio meteorológico y el baseline diario del backtest existente. Time
Machine mantiene su API actual. El proveedor BigQuery TimesFM 3.0 y el proceso
programado quedan deshabilitados en esta etapa.

## Flujo de datos

1. Un proceso offline convierte una extracción existente en
   `HistoricalSeries`: una ciudad, coordenadas, variable, unidad y frecuencia
   nativa. Valida fechas alineadas en UTC, orden estricto y valores finitos.
   Conserva nulos y huecos. El baseline exige una grilla diaria completa,
   sin imputación. Cada muestra mensual se identifica con el primer día del mes.
2. `PredictionJob` acepta un plan con alcance, primera fecha, pasos y revisión
   de los datos. Verifica el centroide GeoRef y calcula una huella a partir del
   proveedor, revisión del proveedor, ámbito, historia, revisión y horizonte.
   La reserva transaccional local reutiliza versiones completadas e impide
   ejecuciones simultáneas para la misma huella. La revisión debe provenir del
   contenido o de un slot operativo estable, no de un valor aleatorio.
3. El proveedor devuelve un lote con procedencia, versión, fecha de generación,
   historia utilizada e incertidumbre cuando la fuente la entrega. La escritura
   local publica versión, puntos y estado final en una sola transacción.
   Una nueva extracción o revisión material produce una versión distinta.
4. La API consulta únicamente la proyección SQLite con una conexión de solo
   lectura. No crea la base. El adaptador BigQuery independiente genera NDJSON
   y nombres deterministas de jobs de carga. Esta fase no incluye el transporte
   a BigQuery ni ejecuta la migración.

| Proveedor | Semántica y fuente |
| --- | --- |
| `open-meteo` | Reutiliza `WeatherService` y publica pronósticos horarios operativos, con su variable y unidad nativas. Conserva `generated_at: null` cuando el endpoint no informa emisión. La fecha de obtención va en procedencia. |
| `climatology` | Media mensual entre años anteriores, con recuento de muestras. Publica `climatology_reference` y `reference_only`. Los meses sin muestras quedan nulos. |
| `seasonal-baseline` | Repite la última semana de datos diarios con el mismo método del backtest existente. Publica `not_validated` y no agrega intervalos. |
| `bigquery-timesfm` | Proveedor deshabilitado. Solo la fase futura invocará `AI.FORECAST` con `MODEL => 'TimesFM 3.0'`. Google aplica los términos de Google Cloud al modelo alojado. [TimesFM en BigQuery](https://docs.cloud.google.com/bigquery/docs/timesfm-model) |

`horizon` empieza en 1 y cuenta pasos de la frecuencia declarada. Los
pronósticos de modelo empiezan inmediatamente después de la última muestra
del entrenamiento. Para un pronóstico operativo indica la posición en el
recorte solicitado. Un intervalo lleva límites y nivel de confianza entregados
por la fuente. Los cuantiles se guardan como pares ordenados y sin cruces.
`published_at` identifica la publicación de la versión en EarthLens.

## API local

```http
GET /api/predictions?city_id=mendoza&variable=T2M&start=2026-12-01&end=2026-12-07
```

Las fechas del filtro son días UTC inclusivos. `provider` y `frequency` son
opcionales y por defecto usan `bigquery-timesfm` y `daily`. El límite es de
31 días para frecuencia horaria y 366 días para las demás. `version_id`
permite escoger una versión publicada específica. Por defecto se lee la última
versión de esa ciudad, variable, frecuencia y proveedor. Los puntos provienen
de una sola versión.

El cuerpo conserva el sobre `status/data/meta`. Dentro de `data`, el estado
es `available` o `unavailable` y `result.kind` declara la semántica del
lote. Sin versión, `result` es nulo y el motivo es `no_saved_version`.
Los otros motivos son `no_points_in_range` y `no_valid_values`. En este último
caso se devuelven los puntos nulos guardados, junto con su procedencia.

`EARTHLENS_PREDICTION_DATABASE_PATH` permite señalar la proyección SQLite.
La ubicación predeterminada es `data/runtime/predictions.sqlite3` con la
configuración habitual de caché. El servicio web puede recibir la proyección
como archivo de solo lectura. Las operaciones del proceso offline se habilitan
por inyección explícita de `PredictionJob(enabled=True)` y el proveedor TimesFM
sigue deshabilitado incluso en ese modo. No hay un ejecutor programado en esta etapa.

## Migración de BigQuery

[DDL inicial](../../deployment/bigquery/001_prediction_tables.sql). Los nombres
`__PROJECT__` y `__DATASET__` son marcadores. El dataset y su ubicación deben
aprobarse antes de aplicar el DDL.

| Tabla | Identidad lógica | Partición |
| --- | --- | --- |
| `historical_series` | `history_id, observed_at`, unidad nativa, nulo y fuente | Fecha observada |
| `prediction_versions` | `version_id`, ejecución, modelo, historia y manifiesto de publicación | Fecha de publicación |
| `prediction_points` | `version_id, target`, horizonte, estimación e incertidumbre opcional | Fecha objetivo |
| `prediction_runs` | `run_id, status, event_at`, intento, error seguro, estimación y métricas de job | Fecha del evento |
| `prediction_backtests` | Ejecución, modelo, corte y horizonte, MAE, RMSE y cobertura si hubo intervalos | Fecha de evaluación |

El adaptador prepara primero los puntos y después el manifiesto de versión.
El publicador futuro debe fijar los bytes del artefacto y sus IDs de carga,
confirmar todas las cargas y comprobar el recuento de puntos antes de exponer la
versión. BigQuery no sustituye al coordinador transaccional. En despliegues con
varias instancias se necesita una reserva duradera y compartida y una proyección
de lectura publicada fuera del proceso HTTP.

## Siguiente fase y controles

- Configurar explícitamente proyecto, dataset, ubicación, entorno y lista
  permitida de ciudades, variables, productos y frecuencias. Seleccionar
  ventanas e horizontes por variable antes de asignar un presupuesto. BigQuery
  documenta para TimesFM 3.0 un contexto de 64 a 2.048 puntos en múltiplos de 32.
  Revisar disponibilidad y tarifa del servicio alojado antes del piloto.
  [AI.FORECAST](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-forecast)
- Usar una identidad de Scheduler con `roles/run.invoker` en el Job concreto
  y OAuth para la API de Jobs. Usar otra identidad adjunta al Job con ADC,
  permiso para crear jobs en el proyecto ejecutor y permisos de lectura y
  escritura acotados a las tablas o datasets necesarios. Aplicar el DDL con una
  identidad distinta. El servicio HTTP consume una proyección local y no recibe
  permisos de BigQuery. Evitar claves de cuentas de servicio.
  [Cloud Run Jobs y Scheduler](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
- Hacer que cada disparo enumere combinaciones aprobadas y reserve trabajo
  por huella antes de inferir. Registrar ID de job, intento, estado, códigos de
  error, bytes facturados y estimación en microunidades monetarias con moneda
  fija por entorno. Ante un timeout, reconciliar el job original por su ID antes
  de reintentar. El coordinador SQLite no recupera automáticamente ejecuciones
  abortadas que quedaron en `running`.
- Preparar topes de puntos, horizonte, combinaciones por ejecución, paralelismo,
  cuotas y presupuesto diario antes de ejecutar. El coordinador local reserva
  costo estimado por día UTC, con presupuesto predeterminado cero. El futuro
  worker debe estimar bytes con dry run cuando corresponda y fijar
  `maximumBytesBilled` para consultas on-demand. Estimar por separado tokens
  de inferencia cuando apliquen. Una alerta presupuestaria no impone un tope.
  [Controles de costo](https://docs.cloud.google.com/bigquery/docs/best-practices-costs),
  [Precios de BigQuery](https://cloud.google.com/bigquery/pricing)
- Reconciliar estados y verificar disponibilidad del modelo, sintaxis y
  respuesta en la región elegida. Evaluar ventanas de origen móvil sobre datos
  reales y comparar por variable, frecuencia y horizonte con el baseline.
  Publicar cualquier banda solo cuando la entregue el modelo, con su nivel y
  cobertura empírica reportada por separado. La suite local valida el contrato
  y los esquemas de filas, no la exactitud del modelo ni la ejecución del DDL.
