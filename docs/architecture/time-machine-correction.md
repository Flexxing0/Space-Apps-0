# Corrección prioritaria: EarthLens es Time Machine

15/11/2026 · rama `feature/backend-api` · sin commits, push ni despliegue.
Esta corrección reemplaza el estado de interfaz descrito en la primera entrega
de la reestructuración; conserva sus servicios y datos.

## Problemas comprobados antes de modificar

La inspección de código y Chrome confirmó que `/` servía `index.html`, una pantalla
distinta de la herramienta. La vista reservaba columnas para ambos paneles y su
versión móvil convertía el mapa en un bloque dentro de una página larga.

El deslizador llamaba a `updateTime()`: cambiaba la fecha y buscaba un valor en la
serie que ya estaba cargada. No resolvía el producto correspondiente a una fecha
nueva. `step()` se detenía en los límites del intervalo y «Presente» cambiaba fuente,
variable/rango en un camino separado. El calendario sólo solicitaba nuevos datos
si ya se había elegido el proveedor de pronósticos. Una fecha seleccionable no
garantizaba contenido ambiental asociado.

Otros defectos: el perfil dejaba el radial fuera del primer pantallazo, la edición
extensa ocultaba el pronóstico de un evento, los avisos no viajaban al contexto del
evento y las capturas podían tomar un panel a mitad de su transición. Una regla
móvil heredada `top:0` desplazaba la timeline hacia arriba incluso usando `fixed`.

Los registros previos de pruebas comprobaban servicios aislados y no bastaban para
aprobar estos recorridos de usuario. Se sustituyó el verificador de workspace por
la aceptación integrada A–H.

## Flujo corregido

`/`, `/index.html` y `/time-machine` abren la misma herramienta. El mapa ocupa el
viewport; header compacto y timeline inferior permanecen sobre él. Las herramientas
izquierdas y el inspector derecho se abren a pedido y se cierran con su botón o
Escape. Calendario, perfil, eventos, impactos y notificaciones usan ese inspector.
No se necesita navegar a una landing ni a otra página para esas acciones.

Hay un único estado de ciudad, variable y fecha. Arrastrar, avanzar, retroceder,
reproducir, volver al presente, elegir fecha exacta, calendario, acontecimiento,
perfil, evento o notificación pasa por la misma selección temporal. El viewport
de la timeline es independiente del rango de análisis y de la cobertura del
proveedor. Avanzar más allá de su borde recentra la vista; no detiene el viaje.
El zoom temporal no crea observaciones. La escala de navegación no altera la
frecuencia científica de los datos.

`GET /api/workspace/frame` reutiliza WorkspaceService y WeatherService:

Parámetros: `city_id`, `date` obligatorios; `variable=T2M`, `provider=power`,
`scale=daily`, `mode=date`, `start`/`end` opcionales como par. Fechas/horas del
selector se interpretan en UTC; un offset explícito se convierte a UTC. Escalas:
`hourly`, `daily`, `monthly`, `yearly`. Se rechazan parámetros repetidos,
coordenadas libres y proveedores desconocidos antes de consultar la red.

El sobre sigue siendo `status/data/meta`. `data` conserva `selection`, `location`,
`status`, `kind`, `record`, `focus`, `climatology`, `message` y `effective_query`.
`focus` identifica valor/unidad/fecha de muestra nativa. Un mes sigue siendo un
mes aunque se navegue por días. `record` mantiene procedencia y metadatos; un
caso sin pronóstico no fabrica ese registro. Ausencia de cobertura conocida:
HTTP 200 y `data.status=unavailable`. Timeout del proveedor: HTTP 504 y el error
JSON público existente. Una climatología no se devuelve para disimular ese fallo.

```powershell
Invoke-RestMethod 'http://localhost:5000/api/workspace/frame?city_id=comodoro-rivadavia&date=2017-03-31&variable=PRECTOTCORR&scale=daily'
```

- Históricos mensuales verificados: POWER o proveedor nativo seleccionado.
- Históricos diarios: POWER Daily; horarios compatibles: ERA5. Reutiliza una
  extracción histórica que ya contenga el día antes de pedir otra. No descarga
  automáticamente las 25 ciudades.
- Presente y próximos 16 días: pronóstico horario Open-Meteo para variables
  compatibles. La variable seleccionada se conserva; el producto y unidad usados
  se muestran por separado.
- Más allá del horizonte: referencia mensual POWER 2000–2024 cuando existe,
  identificada como **climatología, no pronóstico de ese día**. No genera una serie
  de observaciones futuras.
- Variables sin pronóstico, huecos, nulos, calidad insuficiente o fechas fuera de
  cobertura: valor ausente explícito. Nunca arrastra el último valor histórico.
- Los fallos de red no se presentan como climatología ni como una descarga nueva.

POWER WS2M es viento a 2 m y Open-Meteo usa viento a 10 m: se informa la diferencia.
Precipitación mensual POWER conserva mm/day; la acumulación horaria del pronóstico
conserva mm. No se concatenan como una serie homogénea. T2M_MAX/T2M_MIN mensuales
no se convierten silenciosamente en extremos meteorológicos diarios futuros.

El mapa etiqueta únicamente puntos realmente consultados. Las demás ciudades son
ubicaciones GeoRef sin valor para esa fecha. Selección múltiple, provincia, región
y polígono siguen seleccionando puntos del catálogo; no se construyen superficies
interpoladas. La comparación informa errores individuales y el límite de cinco
series visibles. No hay validación de coordenadas libres ni recorridos activados.

El perfil reutiliza una plantilla, muestra el radial real al abrirse y conserva
foto/atribución, geografía, climatología, tendencias y herramientas existentes.
Sus acontecimientos y selector de fecha viajan en el mapa sin perder la ciudad.
Las secciones extensas quedan desplegables; no se eliminó su información científica.

Los eventos mantienen SQLite, migraciones, propiedad por usuario, CSRF y CRUD.
Se puede abrir un evento desde calendario, timeline, mapa o notificación. El
formulario de edición queda plegado para mostrar primero el evento y su evaluación.
Incluye alternativas, historial y acceso a avisos relacionados. La reprogramación
necesita guardar explícitamente. El monitor sigue siendo un proceso independiente.
Los avisos nuevos incluyen valores anteriores/actuales y unidades, contexto del
evento, fuente/actualización, límites, recomendación y alternativas.

## Pruebas de aceptación reales

Ejecutor: `python -m scripts.audit.check_time_machine_acceptance`, con Chrome instalado.
Los recorridos públicos A–D abren el backend real en `127.0.0.1:5000`. Los
recorridos privados continúan en la misma aplicación en `127.0.0.1:5052`, con
SQLite temporal y cookie separada; no crean cuentas/eventos en la base del usuario.
`--isolated` permite usar sólo ese servidor temporal si Docker no está iniciado.
Los datos A–F vienen de cachés y proveedores reales, sin fixtures. Para un
entorno nuevo, precargá las seis series mensuales de Comodoro para 2000–2024
en la caché que usará el servidor. El catálogo necesita esos registros
verificados para habilitar las variables POWER del recorrido. El reporte no
marca aprobada una ejecución incompleta: comienza como `running` y sólo finaliza
`complete` si terminan los recorridos y las comprobaciones de integridad.

| Prueba | Resultado | Comprobación |
| --- | --- | --- |
| A · Inicio | Aprobada | `/` abre mapa completo, paneles cerrados y timeline visible. |
| B · Pasado | Aprobada | Comodoro, 31/03/2017, precipitación POWER Daily real; mapa y gráfico cambian. |
| C · Futuro | Aprobada | Arrastre físico del mismo deslizador a mañana y +7 días; Open-Meteo real para temperatura, precipitación, probabilidad, viento, ráfagas, humedad y nubosidad. |
| D · Calendario | Aprobada | Desplegado sobre mapa; fecha, cursor, celda y pronóstico sincronizados. |
| E · Evento | Aprobada | Guardado privado, persiste al recargar, aparece en calendario/timeline/mapa y permite consultar pronóstico/alternativas. |
| F · Perfil | Aprobada | Comodoro, foto/atribución y radial de datos reales correspondiente a esa ciudad, dentro del panel. |
| G · Notificaciones | Aprobada sólo como simulación controlada | Cambio y aviso en base temporal, valores anteriores/actuales, deduplicación y viaje al evento; las cachés meteorológicas no se alteran por la simulación. |
| H · TimesFM | **Bloqueada; no implementado** | Auditoría real de entorno/modelo. No se aprobó mediante mocks ni se generaron predicciones TimesFM. |
| Cobertura adicional | Aprobada | Futuro distante climatológico identificado y variable GLDAS sin valores futuros inventados. |
| Móvil | Aprobada | Sin desborde horizontal; timeline permanece en el borde inferior, no sobre la barra superior. |

Suite completa Docker: **248 pruebas, 247 aprobadas y una NASA live optativa
omitida**. Las 11 nuevas de resolución temporal son sin red, con datos sintéticos
claramente limitados a software. Se conservan las verificaciones anteriores de
privacidad, caché y servicios. Chrome: cero errores JavaScript en los recorridos.
Se inspeccionaron también las capturas para corregir composición y legibilidad.
Se compararon además los 230 archivos numéricos/derivados del manifiesto previo:
ninguno cambió ni desapareció. La base de usuario conserva cero cuentas y cero
eventos de prueba. Backend Docker saludable y monitor independiente operativo.

Capturas reales, en `data/cache/reports/time-machine-correction/acceptance/`:

- [A: inicio](../../data/cache/reports/time-machine-correction/acceptance/A-inicio.png)
- [B: pasado](../../data/cache/reports/time-machine-correction/acceptance/B-pasado-2017.png)
- [C: futuro](../../data/cache/reports/time-machine-correction/acceptance/C-futuro-7-dias.png)
- [D: calendario](../../data/cache/reports/time-machine-correction/acceptance/D-calendario.png)
- [E: evento/pronóstico](../../data/cache/reports/time-machine-correction/acceptance/E-evento-pronostico.png)
- [F: perfil](../../data/cache/reports/time-machine-correction/acceptance/F-perfil-comodoro.png)
- [G: evento desde un aviso](../../data/cache/reports/time-machine-correction/acceptance/G-evento-desde-notificacion.png)
- [Móvil](../../data/cache/reports/time-machine-correction/acceptance/mobile-mapa.png)
- [Reporte A–H y valores verificados](../../data/cache/reports/time-machine-correction/acceptance/report.json)

## TimesFM 3.0: estado comprobado

No están instalados PyTorch, `timesfm` ni `timesfm3`. No hay checkpoints locales,
servicio de inferencia, endpoint de inferencia, predicciones generadas ni pruebas
de precisión del modelo. `services/prediction/prediction.py` contiene capacidades deshabilitadas
y un arnés de backtesting; **no constituye integración TimesFM**. El backtest real
existente usa persistencia y naive semanal sobre POWER diario. `/api/forecast`
conserva la proyección OLS heredada; tampoco es TimesFM y no se usa para sustituir
pronósticos operativos en esta interfaz.

La [documentación oficial](https://github.com/google-research/timesfm#license-notice-for-pretrained-weights)
separa el código Apache-2.0 de los pesos descargables 3.0, restringidos a uso no
comercial/no productivo. Las vías autorizadas de Google Cloud tienen condiciones
distintas; no hay acceso de inferencia configurado para ellas en este proyecto.

Los metadatos oficiales del checkpoint `google/timesfm-3.0-pytorch` verificados el
15/11/2026 informan `model.safetensors` F32 de **1.322.898.824 bytes**. El límite real
del backend Docker es **1.073.741.824 bytes (1 GiB)** y Docker Desktop dispone de
aproximadamente 4 GB totales. El archivo supera ese límite antes de considerar
PyTorch/activaciones; no se ha demostrado inferencia viable en esta configuración.
El paquete oficial requiere Python >=3.10; la aplicación usa 3.12 en Docker.
Los cuantiles/covariables del modelo no prueban precisión meteorológica.

Por estas condiciones no se descargaron pesos ni se habilitó una inferencia para
el producto previsto. Una investigación no comercial aislada requeriría un entorno
y recursos adecuados, y backtesting del modelo real antes de incorporarlo a la
timeline. No se sustituyó el modelo por otro ni se contrataron servicios.
El pronóstico meteorológico real permanece operativo sin TimesFM.

```powershell
docker compose exec -T backend python -m scripts.audit.audit_timesfm
```

También se guardó la [auditoría del contenedor real](../../data/cache/reports/time-machine-correction/timesfm-docker-audit.json).

## Archivos de esta corrección

- `web/routes.py`: entrada directa a la herramienta.
- `templates/pages/workspace.html`, `components/_workspace_header.html`, `components/_workspace_timeline.html`:
  estructura unificada, paneles, calendario y eventos.
- `static/css/components/time_machine_shell.css`: mapa completo, overlays, timeline inferior,
  responsive y composición contextual. `workspace.css` conserva estilos reutilizados.
- `static/js/time-machine/workspace.js`, `static/js/time-machine/time_axis.js`: selección compartida,
  transporte/zoom, proveedor según fecha, marcadores y navegación contextual.
- `services/workspace/time_navigation.py`, `api/workspace.py`, `app.py`: adaptador de selección
  temporal sobre los servicios científicos/meteorológicos existentes.
- `services/events/monitoring.py`: contexto y valores de cambio en avisos propios.
- `services/prediction/prediction.py`, `scripts/audit/audit_timesfm.py`: estado real explícito.
- `tests/workspace/test_time_navigation.py`, ajustes de `test_workspace_v2.py` y
  `test_product_pages.py`: contratos, nulos, errores, navegación y avisos.
- `scripts/audit/check_time_machine_acceptance.py`, `scripts/audit/check_workspace.py`: aceptación
  vigente y comando compatible para ejecutarla.
- Documentación: `AGENTS.md`, `docs/project/BACKEND_TASKS.md`, `docs/project/EARTHLENS_ROADMAP.md`,
  `docs/architecture/api.md`, `docs/architecture/workspace.md` y este informe.

No se modifican el motor estadístico, la familia de Radar, proveedores originales,
catálogo argentino ni cachés científicas de POWER/GLDAS/GPM/MODIS/SWOT.
Las comprobaciones comparan sus hashes antes/después. La meteorología puede
refrescarse realmente conforme a su TTL; la simulación G no escribe observaciones.

## Ejecución y pendientes

```powershell
docker compose --profile monitoring up -d --build
# Abrir http://localhost:5000/
docker compose exec -T backend python -m unittest discover -s tests
.\venv\Scripts\python.exe -m scripts.audit.check_time_machine_acceptance
```

Persisten bloqueos externos: acceso oficial SMN; vía licenciada, recursos y
validación de TimesFM; capas de susceptibilidad/calles/DEM continuo para impactos
de sitios; límites oficiales para coordenadas libres. El DEM puntual de los
centroides no reemplaza esas capas. No se afirman inundaciones, transitabilidad,
polvo ni estrés térmico sin evidencia adecuada. Las órdenes MODIS no entregadas
y la revisión científica pendiente de los análisis originales conservan su estado.
No se declara listo un despliegue productivo ni se añaden mensajes externos.
