# EarthLens — ejecución local con Docker

Una única aplicación Flask sirve el frontend del equipo y la API REST en el mismo
origen. El motor estadístico corre en ese proceso con SciPy. No se necesitan Node,
npm, otro contenedor, base de datos ni un segundo Compose.

## Arranque

Iniciar Docker Desktop con contenedores Linux y ejecutar desde la raíz, en PowerShell:

```powershell
docker compose up -d --build --wait --wait-timeout 60
```

Abrir **http://127.0.0.1:5000/**. También están disponibles `/explorer`, `/results`,
`/compare`, `/missions`, `/about` y la API en `/api`. El healthcheck es
`http://127.0.0.1:5000/api/health`; no consulta NASA.

Para consultar el estado y los logs:

```powershell
docker compose ps
docker compose logs --tail 50 backend
```

Si 5000 está ocupado, elegir otro puerto antes de arrancar:

```powershell
$env:EARTHLENS_PORT = '5001'
docker compose up -d --build --wait --wait-timeout 60
# Abrir http://127.0.0.1:5001/
```

Sólo se publica la interfaz local de Windows. La imagen usa Python 3.12 y las
versiones directas verificadas de Flask, Requests y SciPy en `requirements.txt`.
NumPy se instala como dependencia de SciPy. La imagen final incluye templates,
estáticos, módulos web, motor y catálogos; no depende de una copia oculta de otra rama.

## Caché y desarrollo

`./data/cache` sigue montado en `/app/data/cache` con lectura/escritura. No se
sustituye por un volumen vacío ni se incluye en la imagen. Las 25 cachés de ciudades
2000–2024 mantienen sus hashes y fechas de obtención. Reiniciar o reconstruir el
servicio no borra esos archivos.

Los módulos Python, `templates/` y `static/` se montan con sólo lectura desde el
host; el editor puede modificarlos normalmente. Flask usa recarga sin depurador
interactivo y ejecuta como UID 10001. Al cambiar dependencias, catálogos de misiones
o Dockerfile, volver a ejecutar el comando de arranque con `--build`.

El navegador usa los CDN del frontend para Bootstrap, Leaflet, Chart.js y fuentes,
y servicios externos para mapas. Necesita Internet para esos recursos; las
consultas científicas 2000–2024 usan la caché local. Otros períodos pueden consultar
NASA. No se fuerza ninguna descarga al arrancar o importar módulos.

Para detener y volver a iniciar, conservando el entorno:

```powershell
docker compose stop
docker compose start
```

No borrar `data/cache` ni ejecutar limpiezas de volúmenes. No cambiar el montaje
persistente. Esta configuración usa el servidor de desarrollo Flask, un proceso y
bloqueo de obtención dentro de ese proceso; producción y múltiples workers quedan
pendientes.

## Pruebas y auditoría real

```powershell
docker compose exec -T -e EARTHLENS_POWER_LIVE=0 backend python -m unittest discover -s tests -v
docker compose exec -T backend python -m pip check
docker compose exec -T backend python -m flask --app app:create_app routes

# Lee las 25 cachés reales; bloquea NASA y comprueba hashes y fechas.
docker compose exec -T backend python -m scripts.audit.check_cached_integration
```

Resultado verificado el **14 de noviembre de 2026**, tras la fase 1: **137 pruebas aprobadas**
(las 134 anteriores más tres contratos de páginas/navegación/recursos), una prueba NASA
optativa omitida y ninguna dependencia rota. La auditoría real procesó 25 ciudades,
150 series, 45.000 valores mensuales y 150 análisis anuales con cero consultas NASA
ni cambios en las cachés. No implica una nueva verificación del proveedor remoto.

Verificación optativa desde el host, con Chrome instalado y Playwright:

```powershell
.\venv\Scripts\python.exe -m pip install playwright
.\venv\Scripts\python.exe scripts/audit/check_web.py
# Con otro puerto:
.\venv\Scripts\python.exe scripts/audit/check_web.py --url http://127.0.0.1:5001
```

El script abre Chrome en modo headless, verifica Inicio → Explorador → Resultados,
CSV, gráficos, Comparador, errores y recuperación, misiones, metodología y vista
móvil. Guarda capturas e informe en `data/cache/reports/web`, ignorados por Git.
La respuesta 503 interceptada es una prueba de software, no un dato científico.
No se necesita Playwright para ejecutar la aplicación.

## Obtención de datos por solicitud explícita

```powershell
# Sólo planifica; no consulta NASA ni escribe caché.
docker compose exec -T backend python -m scripts.data.fetch_power --all --start-year 2000 --end-year 2024 --dry-run

# Reutiliza caché y consulta únicamente lo que falte, si se solicita un lote.
docker compose exec -T backend python -m scripts.data.fetch_power --all --start-year 2000 --end-year 2024
```

No usar `--force` para comprobar el arranque. Contratos: [api.md](../architecture/api.md).
Diagnóstico por ramas, inventario Docker y metodología: [integration.md](../architecture/integration.md).


## Radar y Fingerprint provisionales

El mismo servicio sirve los nuevos endpoints; no hay contenedores ni dependencias
adicionales. El artefacto derivado comparte el montaje `data/cache`, en una carpeta
separada de las observaciones POWER.

```powershell
docker compose exec -T backend python -m scripts.maintenance.generate_radar --dry-run
docker compose exec -T backend python -m scripts.maintenance.generate_radar
Invoke-RestMethod 'http://127.0.0.1:5000/api/fingerprint/mendoza'
Invoke-RestMethod 'http://127.0.0.1:5000/api/radar?region=Cuyo&variable=T2M'
```

El generador no consulta NASA y los filtros HTTP no recalculan análisis ni ajustes.
La ciencia continúa provisional. Contratos, piloto y limitaciones: [products.md](../architecture/products.md).

## Interfaces Radar y Fingerprint — fase 1

```powershell
docker compose up -d --build --wait --wait-timeout 60
# http://127.0.0.1:5000/radar
# http://127.0.0.1:5000/fingerprint

docker compose exec -T -e EARTHLENS_POWER_LIVE=0 backend python -B -m unittest discover -s tests -v
# En el host, con Playwright y Chrome instalados:
.\venv\Scripts\python.exe -B scripts/audit/check_product_pages.py
```

Las dos páginas se sirven con Jinja en el servicio existente. Los montajes de
`web/`, `templates/` y `static/` incluyen todos los archivos nuevos; no hay otro
Dockerfile, servicio, volumen, base de datos ni dependencia de producción.
La caché y el estudio persistido deben estar presentes. Si falta el artefacto,
Radar muestra un error con reintento: no genera un estudio ni consulta NASA
automáticamente. El comando cache-only de generación sigue disponible arriba.

El verificador comprueba 25 perfiles reales con origen caché, interacciones y
gráficos en Chrome, y hashes de las 25 cachés, el artefacto y el motor antes/después.
Guarda evidencias en una carpeta única bajo `data/cache/reports/interfaces-phase1/`.
Las respuestas 503, la incompatibilidad de metadatos y el indicador sintético
insuficiente son fixtures de software interceptados sólo en el navegador.
Las capturas muestran exclusivamente datos reales. No es una prueba de conexión NASA.

Bootstrap, Leaflet, Chart.js, fuentes y teselas siguen usando los recursos externos
del proyecto y requieren acceso a Internet. Playwright sólo se necesita para la
verificación de navegador, no para ejecutar EarthLens.

## Inicialización desde una instalación nueva y otras fuentes

```powershell
docker compose up -d --build --wait --wait-timeout 60
docker compose exec -T backend python -m scripts.maintenance.initialize_data
```

El inicializador recupera POWER mediante las APIs reales sólo cuando falta caché,
audita los datos y regenera Radar desde caché. Repetirlo reutiliza las observaciones.
Los informes tienen nombres únicos bajo `data/cache/reports`. Si fallan datos o
análisis, no sustituye el artefacto Radar anterior y sale con código 1.

Las nuevas respuestas originales, series nativas y diagnósticos científicos viven
en `data/cache/science`, dentro del mismo bind mount persistente. No hay nuevas
dependencias, servicios ni volúmenes. `/api/science/variables` describe únicamente
datos verificados de la instalación; los contratos existentes siguen usando POWER.

Comandos de GLDAS, GPM y órdenes MODIS sin exponer tokens ni guardar el contacto:
[scientific-sources.md](../science/scientific-sources.md). GLDAS y GPM ya tienen históricos
reales en caché; el piloto SWOT usa un contrato separado. El catálogo curado
`data/water_features.json` se copia en la imagen y se monta como sólo lectura
en desarrollo; sus observaciones comparten el montaje persistente de caché.

```powershell
docker compose exec -T backend python -m scripts.audit.audit_science
docker compose exec -T backend python -m scripts.data.order_modis --poll
docker compose exec -T backend python -B -m unittest discover -s tests
# Con Playwright y Chrome en el host:
.\venv\Scripts\python.exe -B -m scripts.audit.check_scientific_pages
```

La página `http://127.0.0.1:5000/sources` y los paneles desplegables en las cinco
herramientas existentes muestran series reales con gráficos nativos. Las consultas
cacheadas no requieren Earthdata en el servidor. Para nuevas descargas autenticadas
usar `docker compose exec -T -e EARTHDATA_TOKEN ...` desde la terminal que tenga
el token; no incluir su valor en Compose, `.env` versionable, Dockerfile o comandos
compartidos. Los pedidos ORNL usan de la misma manera `EARTHLENS_ORNL_EMAIL`.
El sondeo de órdenes no exige correo ni token y nunca reenvía pedidos.
Compose activa `EARTHLENS_TEMPLATES_AUTO_RELOAD=true` para recargar Jinja durante
el desarrollo manteniendo desactivado el depurador interactivo. Los gráficos
del panel se crean sólo al consultar; los paneles cerrados no agregan lienzos
ni consultas a las interfaces originales.

## Integración de main

La configuración activa sigue siendo `compose.yaml`. Si se necesita el alias
recibido del esquema anterior, usar `docker compose -f compose.legacy.yaml`;
ambos describen el mismo backend con caché persistente, sin otro contenedor.
Time Machine está disponible en `/time-machine` y usa sólo cachés verificadas.
Sus pruebas de navegador se ejecutan con:

```powershell
.\venv\Scripts\python.exe -B -m scripts.audit.check_time_machine
```

La configuración Vercel/Cloud Run de main no fue desplegada ni verificada en
producción. No copiar cachés o credenciales al contexto de publicación.

## Reestructuración: eventos y monitoreo

SQLite persistente en `./data/runtime`, meteorolog?a horaria y un servicio opcional
`monitor` se incorporaron en Compose. Gu?a y condiciones de producci?n:
[ejecuci?n del espacio geotemporal](../architecture/workspace.md). Contin?a en localhost:5000.
