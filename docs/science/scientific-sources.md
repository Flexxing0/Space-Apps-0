# Fuentes científicas e inicialización multiproveedor

## Auditoría del backend — 21/11/2026

La caché de este checkout estaba vacía al comenzar. Las comprobaciones en vivo
usaron una caché temporal. Los lotes de 25 ciudades de la tabla son evidencia
histórica de una ejecución anterior. La disponibilidad del checkout se determina
por ciudad, variable y período a partir de entradas locales validadas.

| Producto integrado | Variables y resolución | Cobertura comprobada |
| --- | --- | --- |
| NASA POWER Monthly AG | `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `WS2M`, mensual. Precipitación en `mm/day`. | Lote anterior 2000–2024 para 25 ciudades. En esta auditoría Mendoza 2025 devolvió 12 meses válidos por variable. El proveedor publica meteorología desde 1981 hasta el último año anterior publicado. [NASA POWER Monthly API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/) |
| NASA POWER Daily AG | Las mismas seis variables, diarias UTC. Precipitación en `mm/day`. | Comodoro Rivadavia, 30/03–01/04/2017, 3 de 3 valores válidos de precipitación. Fuente desde 1981. EarthLens consulta históricos hasta UTC−6 días, es decir, hasta seis días antes de la fecha UTC actual. [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) |
| ERA5 por Open-Meteo Archive | Temperatura a 2 m, humedad relativa, sensación térmica, precipitación, nubosidad, viento a 10 m, ráfagas y dirección, horarios UTC. La integración histórica excluye probabilidad de precipitación y visibilidad. | Mendoza 29/03/1979, 24 de 24 temperaturas válidas, y Ushuaia 01/07/2024, 24 de 24 velocidades válidas. ERA5 se documenta desde 1940. Se aplica el mismo margen local de consulta histórica. [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) |
| GLDAS Noah 0,25° v2.1 | Cuatro capas de humedad del suelo y evapotranspiración, mensuales. CSV Giovanni y NetCDF puntual conservan revisiones de caché separadas. | Lote previo 2000–2024 de 25 ciudades, 125 series y 37.500 valores válidos. La lectura tras 2024 se comprobó con fixtures de software. Nuevas descargas requieren Earthdata. [NASA GLDAS v2](https://git.earthdata.nasa.gov/projects/ECS/repos/uvg/raw/input/README_GLDAS2.pdf?at=refs%2Fheads%2Fmaster) |
| GPM IMERG Final V07 | `precipitation` mensual a 0,1°, conservada en `mm/hr`. | Lote previo 2000–2024 de 25 ciudades, 25 series y 7.500 valores válidos. NASA cataloga el producto desde 1998. Se comprobó la lectura posterior a 2024 con fixtures de software. Nuevas descargas requieren Earthdata. [NASA Earthdata](https://search.earthdata.nasa.gov/search?q=GPM_3IMERGM_07) |

Se reprodujeron y corrigieron el corte fijo de 2024 en POWER mensual y los
rangos GLDAS/GPM, el bloqueo de ERA5 horario entre 1940 y 1980 por el límite de
POWER, el foco vacío al consultar un rango que excluía el cursor, el 500 de
POWER con fechas anteriores a 1981 y el fallo de lectura cuando una caché
POWER dañada ocultaba otra extracción válida.

`/api/workspace/frame` devuelve el producto y el intervalo efectivos. Cuando un
rango amplio no está cacheado, puede consultar el año del cursor en una sola
extracción. `/api/workspace/series` conserva la lectura parcial de la referencia
2000–2024 para solicitudes POWER que la atraviesan sin disponer de una única
extracción que cubra todo el rango. Los años completos posteriores a 2024
requieren su propia cobertura verificada. La referencia climatológica conserva
2000–2024. GLDAS y GPM mantienen su frecuencia mensual al seleccionar un día.

Los gráficos conservan los ceros y nulos del proveedor, las unidades nativas y
las fechas de la serie. La ausencia de caché compatible conserva el error
`503 cache_unavailable` en las lecturas cache-only. Una fecha fuera de la
cobertura del producto en `/frame` conserva el estado `unavailable`. Una
consulta directa POWER mensual anterior a 1981 recibe `400 invalid_request`.
El alcance de `/api/workspace/trends` sigue siendo el motor estadístico existente.

Estado comprobado el 15 de noviembre de 2026, sobre la base `e127aad`.
El alcance sigue siendo Argentina y las rutas HTTP sólo aceptan ciudades del
catálogo GeoRef; SWOT usa entidades argentinas curadas en un contrato separado.
El motor del equipo se conserva. Se agregó un panel de fuentes a las interfaces
existentes sin cambiar sus cálculos ni su familia estadística.

## Recuperación e inicialización POWER — fase 1

Docker Desktop estaba detenido y no había archivos POWER en `data/cache/power`.
El servicio existente utiliza un bind mount del host, no un volumen anónimo;
arrancarlo no recuperó las observaciones. Se descargaron realmente las 25 ciudades
del catálogo, una solicitud multivariable por ciudad, para 2000–2024:

| Comprobación | Resultado |
| --- | --- |
| Ciudades / solicitudes iniciales | 25 / 25 |
| Series mensuales | 150 |
| Registros / valores disponibles / nulos | 45.000 / 45.000 / 0 |
| Período de cada serie | 2000-01 a 2024-12, 300 meses |
| Unidades recibidas | Temperaturas `C`; precipitación `mm/day`; humedad `%`; viento `m/s` |
| Repetición del comando | 25 aciertos de caché, cero descargas |
| Radar regenerado | 150 análisis provisionales; 48 señales nominales; cero descubrimientos confirmados |

```powershell
docker compose up -d --build --wait --wait-timeout 60
docker compose exec -T backend python -m scripts.maintenance.initialize_data
```

`scripts/maintenance/initialize_data.py` obtiene sólo lo que falte mediante el servicio POWER
existente, audita unidades y cobertura y genera Radar **desde caché**. Si falla
una ciudad o queda algún análisis sin calcular, conserva el artefacto anterior y
termina con código 1. No reemplaza observaciones válidas por respuestas incompletas.
Admite `--start-year`, `--end-year`, `--cache-dir` y la actualización explícita
`--force`. Cada ejecución guarda un informe nuevo en `data/cache/reports/`.
Los datos científicos quedan fuera de la imagen y de Git, en el montaje persistente.

## Contrato y caché aditivos — fase 2

`services/science/scientific.py` separa las series nativas del contrato estadístico
provisional. No duplica el acceso POWER: delega en `EarthLensService` y conserva
intactas sus cachés originales y los contratos `get_data()`/`get_data_multi()`.

Cada registro `earthlens.scientific-series.v1` identifica proveedor, producto,
versión científica cuando se conoce, revisión de caché, variable, unidad, ubicación
argentina, período, frecuencia, resolución, fechas de obtención UTC, procedencia,
metadatos, calidad y cobertura. Los valores no disponibles son `null`. En la
proyección POWER, `YYYY-MM-01` etiqueta el mes; no es una observación instantánea.
La versión de la API POWER no se presenta como versión científica del producto.

```text
data/cache/power/                                     # contrato histórico
data/cache/radar/latest.json                          # familia POWER inalterada
data/cache/science/series/<provider>/<product>/<cache_version>/<variable>/<hash>.json
data/cache/science/raw/modis/<hash-de-url>.json         # respuestas originales
data/cache/science/discovery/                         # acceso y catálogos; no son observaciones
data/cache/reports/                                   # informes de cada ejecución
```

Las claves también distinguen coordenadas, período y política de procesamiento.
Las escrituras son atómicas y llevan integridad SHA-256. Se rechazan pérdidas de
valores disponibles y cambios de unidad, frecuencia, versión o resolución dentro
de la misma identidad. Un archivo corrupto no habilita una variable del catálogo.
Una serie totalmente nula puede conservar evidencia de QA, pero no habilita la
variable como disponible. La disponibilidad incluye ciudades y períodos probados;
no garantiza cobertura completa de cualquier otra ciudad o fecha.

Se agregan `GET /api/science/variables` y `POST /api/science/data`.
El primero deriva la disponibilidad de cachés validadas, sin red. El segundo
sirve series nativas y permite obtener otros períodos de variables ya verificadas;
la primera verificación de un proveedor se ejecuta mediante CLI. Errores públicos
consistentes, coordenadas libres bloqueadas, sin CORS ni credenciales HTTP.
Contrato: [api.md](../architecture/api.md).

## GLDAS — fase 3, piloto real verificado

Producto evaluado: **GLDAS_NOAH025_M, versión 2.1**, mensual, grilla nominal 0,25°.
CMR devolvió la colección `C1342986036-GES_DISC` y el gránulo de enero de 2000.
Variables candidatas: `SoilMoi0_10cm_inst`, `SoilMoi10_40cm_inst`,
`SoilMoi40_100cm_inst`, `SoilMoi100_200cm_inst` (`kg m-2`) y `Evap_tavg`
(`kg m-2 s-1`). No son humedad volumétrica ni evapotranspiración mensual acumulada.

El endpoint antiguo de hydro1 respondió **410**. Se descubrió en CMR el enlace
actual de OPeNDAP Cloud; la petición real a su descriptor `.dds` terminó en
Earthdata Login con **401**, sin token configurado. La migración y el retiro de
Data Rods están documentados por
[NASA GES DISC](https://github.com/nasa/gesdisc-tutorials/blob/main/user-guidance/GES_DISC_Migration_to_Earthdata_Website_and_Earthdata_Cloud.md).
Se evaluaron OPeNDAP con restricciones puntuales y Harmony HOSS para evitar
archivos globales; el diagnóstico inicial no produjo observaciones. El acceso
puntual se verificó posteriormente como se detalla a continuación.
Variables y unidades: [README oficial GLDAS](https://docserver.gesdisc.eosdis.nasa.gov/public/project/hydrology/README_GLDAS2.pdf).

Estado posterior a la configuración de permisos: el descriptor `.dds` respondió
200. La extracción falló inicialmente con 403 al leer DMR++ en S3; después de
autorizar **NASA GESDISC DATA ARCHIVE**, el piloto 2024 tuvo éxito en Mendoza,
Comodoro Rivadavia y Posadas: **15 series, 180 registros válidos y cero nulos**.
`gldas.py` delega la extracción en `gldas_points.py`: CMR verifica producto/versión
y todos los meses; OPeNDAP devuelve sólo coordenadas y cinco variables de un
píxel por mes, en NetCDF-3. SciPy lee el archivo sin dependencias adicionales.
Se conservan escala/offset, relleno, tiempo CF, metadatos globales y coordenadas
efectivas. Hay límite de tamaño y se valida tiempo/celda antes de guardar.

| Ciudad | Celda GLDAS (latitud, longitud) | Registros 2024 |
| --- | --- | --- |
| Mendoza | -32.875, -68.875 | 60 / 60 válidos |
| Comodoro Rivadavia | -45.875, -67.625 | 60 / 60 válidos |
| Posadas | -27.375, -55.875 | 60 / 60 válidos |

Informe: `scientific-gldas-20261115T143415Z-d2844834.json`. Son salidas reales de
un modelo de superficie terrestre, no mediciones de estaciones ni humedad
relativa atmosférica. Las cinco variables ya se sirven desde caché por la API
nativa; no forman parte del motor estadístico ni de la familia Radar.

### Históricos mediante Giovanni in the Cloud

El catálogo real `/configured-variables` confirma las cinco variables mensuales
GLDAS 2.1. Se obtuvo un CSV auténtico de Mendoza 2024 y se contrastaron producto,
DOI, unidad, celda y meses con NetCDF. Ejemplo de diferencia de precisión recibida:
19.6831 en CSV frente a 19.683124542236328 en NetCDF para enero, suelo 0–10 cm.
No se reconstruyen decimales ausentes ni se sobrescribe el resultado NetCDF.
`services/providers/giovanni.py` conserva el CSV y todos sus encabezados y usa
`cache_version="2.1-giovanni-csv-v1"`, con precisión explícita. `product_version`
sigue siendo `2.1`: se trata del mismo producto accedido por otra vía.

```powershell
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gldas --access giovanni --all --variables SoilMoi0_10cm_inst SoilMoi10_40cm_inst SoilMoi40_100cm_inst SoilMoi100_200cm_inst Evap_tavg --start-year 2000 --end-year 2024
```

Ese lote se ejecutó con éxito: **25 ciudades, 125 series, 37.500 registros válidos
y cero faltantes**, 2000–2024. Informe:
`scientific-gldas-20261115T144853Z-63b9c121.json`. La API prioriza
la caché NetCDF para períodos donde exista y puede reutilizar la caché CSV sin token.
No contar dos vías de acceso al mismo mes como observaciones independientes.

```powershell
# Diagnóstico sin credencial; 401 implica salida no exitosa y cero observaciones.
docker compose exec -T backend python -m scripts.data.fetch_science --provider gldas --probe

# Sólo cuando EARTHDATA_TOKEN esté configurado en el entorno de esta terminal.
# -e pasa su valor sin escribirlo en el comando, Compose, Git ni un informe.
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gldas --probe
```

El proceso no puede recibir variables exportadas después de su arranque en otra
terminal. No pegar tokens en el chat ni versionar archivos de credenciales.

Actualización del diagnóstico: el usuario ejecutó el comando anterior con token
configurado y el descriptor DAP2 respondió **HTTP 400** en el host OPeNDAP. Esto
no verifica autenticación ni extracción. El diagnóstico ahora conserva el mensaje
remoto acotado y redactado, omite formularios HTML de login y, únicamente ante
400, prueba también `.dmr.xml` (metadatos DAP4). No modifica observaciones ni
habilita variables. El token de otra sesión PowerShell no se hereda automáticamente
en el proceso del agente o el servicio HTTP; usar `exec -e` desde esa sesión.

El siguiente diagnóstico autenticado recibió HTTP 400 tanto en DAP2 como en DAP4.
El texto público de Tomcat indicó que la línea de cabecera `Authorization` no
cumplía RFC 9112. No es evidencia de un problema con las variables GLDAS ni de un
token autenticado. Se agregó una validación previa del formato Bearer: rechaza
espacios, comillas, prefijo `Bearer` y caracteres fuera del formato permitido,
antes de cualquier solicitud remota. Los fallos de configuración se devuelven
por CLI como JSON controlado, sin traza ni valor de la credencial.

Si esa validación falla, cargar el token nuevamente en **la misma terminal**,
mediante entrada oculta (PowerShell), y ejecutar el diagnóstico:

```powershell
$earthdataSecret = Read-Host 'Pegar solamente el token Earthdata' -AsSecureString
$env:EARTHDATA_TOKEN = [System.Net.NetworkCredential]::new('', $earthdataSecret).Password
Remove-Variable earthdataSecret
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gldas --probe
```

El valor queda en memoria de esa terminal. No se escribe en archivos, argumentos
de comando ni en el historial como texto del token. No imprimirlo para comprobarlo.
La validación del formato no verifica vigencia ni permisos: sigue siendo necesaria
una respuesta científica válida del proveedor antes de habilitar observaciones.

Si la entrada oculta vuelve a producir `credential_format_valid: false`, el
diagnóstico informa sólo indicadores: espacios, comillas, prefijo Bearer,
caracteres de control, caracteres no ASCII y marcas de pegado de terminal
(`has_paste_markers`). Los códigos Unicode de caracteres no permitidos no incluyen
fragmentos del token. No se elimina silenciosamente contenido interno.

Como alternativa a pegar en `Read-Host`, copiar **sólo el token** desde Earthdata y
asignarlo directamente desde el portapapeles en la terminal local:

```powershell
$env:EARTHDATA_TOKEN = (Get-Clipboard -Raw).Trim()
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gldas --probe
```

La asignación no imprime el portapapeles y sólo elimina espacios exteriores. Si se
copió JSON, una cabecera completa u otro texto, corregir la selección original;
no quitar indiscriminadamente caracteres para forzar que el formato sea aceptado.

## MODIS — fase 4, piloto de series nativas

Se consultaron realmente `/products`, `/MOD13Q1/bands`, `/dates` y `/subset` de
[ORNL DAAC REST](https://modis.ornl.gov/data/modis_webservice.html), sin autenticación.
Producto **MOD13Q1**, bandas NDVI y EVI, compuestos de 16 días, 250 m nominales.
La extracción solicitada es de un píxel nativo: no representa un promedio urbano.
El servicio declara como máximo diez fechas por petición. Este adaptador usa dos
fechas por bloque y, ante HTTP 502/503/504, divide el bloque hasta una fecha sin
reintentos ilimitados. Las respuestas originales permiten reanudar sin repetir
peticiones exitosas. Se observaron HTTP 400 al exceder diez fechas y HTTP 502 en
solicitudes mayores; no se almacenaron esas respuestas como observaciones.

La escala real del catálogo es `0.0001`, offset `0`, relleno `-3000` y rango
almacenado `-2000..10000`. Se conservan valores originales, fecha de compuesto,
tile, procesamiento y QA. Se exige fiabilidad 0 y MODLAND 0, y se excluyen nubes
adyacentes/mixtas, nieve/hielo y sombra; valores rechazados quedan `null` con sus
motivos. No hay interpolación, promedios mensuales ni relleno con cero.
La máscara tierra/agua se conserva, sin convertir una costa en un promedio de tierra.

La respuesta REST recibida **no identifica la colección científica**. Se conserva
`product_version: null` y una revisión de caché derivada del catálogo/bandas; no
se atribuye automáticamente la colección 061 a cada observación. El
[catálogo de documentación oficial ORNL](https://modis.ornl.gov/cgi-bin/sites/get_product_doc.pl)
sí declara MOD13Q1 versión 6.1, habilitado en REST, con DOI terminado en `.061`.
La declaración se guardó en `science/discovery/ornl-product-documentation.json`;
no sustituye una identificación por gránulo. Resolver esa trazabilidad antes de
mezclar descargas o interpretar tendencias. La guía de bits es la
[guía oficial MOD13](https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf);
la política aplicada queda versionada en los metadatos.

```powershell
docker compose exec -T backend python -m scripts.data.fetch_science --provider modis --cities mendoza comodoro-rivadavia posadas --variables NDVI EVI --start-year 2024 --end-year 2024

# Para ampliar el período o la selección, después de revisar QA y cobertura:
docker compose exec -T backend python -m scripts.data.fetch_science --provider modis --all --variables NDVI EVI --start-year 2000 --end-year 2024
```

El segundo comando puede hacer muchas solicitudes y **no se ejecuta al arrancar**.
Consultar los informes locales `scientific-modis-*.json` para cantidades reales;
una consulta fallida se informa por ciudad y no interrumpe las siguientes.

Resultado real del piloto ejecutado para **2024**, 23 fechas por índice:

| Ciudad | Series | Registros NDVI + EVI | Aceptados QA | Excluidos QA |
| --- | --- | --- | --- | --- |
| Mendoza | 2 | 46 | 4 | 42 |
| Comodoro Rivadavia | 2 | 46 | 14 | 32 |
| Posadas | 2 | 46 | 38 | 8 |
| Total | 6 | 138 | 56 | 82 |

Cada índice tiene respectivamente 2, 7 y 19 valores aceptados. Los 82 nulos son
exclusiones QA, no fechas fabricadas ni valores reemplazados por cero. Informe:
`data/cache/reports/scientific-modis-20261115T130201Z-ad814caa.json`. El intento
anterior con bloques mayores falló para las tres ciudades y guardó cero series;
se conserva su informe en lugar de ocultarlo. Las respuestas pequeñas exitosas
se reutilizaron al reanudar. La extensión histórica 2000–2024 a las 25 ciudades
todavía no se ejecutó; primero revisar la representatividad de píxeles urbanos,
la cobertura QA baja y la identificación de colección por observación.

## GPM — fase 5, histórico real verificado

Giovanni publicó `GPM_3IMERGM_07_precipitation`. Se verificaron en el CSV real
producto `GPM_3IMERGM.07`, parámetro `/Grid/precipitation`, Final Run, resolución
0,1°, unidad `mm/hr`, relleno `-9999.9` y DOI `10.5067/GPM/IMERG/3B-MONTH/07`.
No se infiere una revisión menor que no figura en esa respuesta.

El piloto Mendoza 2024 produjo doce valores. El lote posterior de 25 ciudades
2000–2024 produjo **25 series, 7.500 registros válidos y cero faltantes**:
`scientific-gpm-20261115T145756Z-a7cdd8ef.json`. No sumar nuevamente el piloto.
Los encabezados, CSV original, coordenadas y precisión recibida quedan conservados.

```powershell
docker compose exec -T -e EARTHDATA_TOKEN backend python -m scripts.data.fetch_science --provider gpm --all --variables precipitation --start-year 2000 --end-year 2024
```

`services/science/scientific_compare.py` compara descriptivamente con POWER cuando el
cliente pide `target_unit: "mm/day"`. Multiplica la tasa IMERG por 24 en la
proyección, conserva la fuente original en `mm/hr` y no calcula acumulados,
correlaciones ni significancias. Se advierte que resolución y métodos difieren.
Referencia del producto: [NASA IMERG V07](https://gpm.nasa.gov/resources/documents/imerg-v07-release-notes).

## SWOT — fase 6, piloto fluvial real

Se identificó el tramo SWORD **65341000051, río Chubut**, cerca de Trelew,
mediante el índice público recomendado por [SWORD Explorer](https://www.swordexplorer.com/).
Se conservaron el registro de origen y SHA-256 del índice; GeoRef ubicó su
centroide en Chubut, departamento Rawson, municipio Trelew. Esto respalda esa
entidad curada; no es un validador general de límites ni habilita coordenadas libres.

Hydrocron devolvió **31 pasos reales de 2024**, con altura superficial (`wse`)
y ancho (`width`), ambos en metros: **62 valores numéricos**, sin rellenos en
esas variables. Producto `SWOT_L2_HR_RiverSP_D`, versión D, SWORD 17b, CRID PGD0.
Se conserva la geometría LineString de 354 vértices, fechas/horas de paso,
incertidumbres, identificadores de gránulos y banderas. Hubo 29 pasos con
`reach_q=1` y dos con `reach_q=2`: disponibilidad numérica **no significa**
aceptación científica. No se filtran silenciosamente ni se presentan tendencias.
La referencia vertical requiere consultar la documentación del producto; no
interpretar la altura como cota local sin ese contexto.

Respuesta original: `data/cache/science/discovery/hydrocron-chubut-2024.json`.
Catálogo curado: `data/water_features.json`. `services/science/hydrology.py` mantiene
su propia identidad, geometría, versión y frecuencia irregular. Los registros
no se remuestrean ni mezclan con meses meteorológicos de las ciudades.
Los lagos argentinos siguen pendientes de identificar mediante IDs oficiales
con datos reales; no se usaron IDs de ejemplos de otros países.
Fuentes: [API Hydrocron](https://podaac.github.io/hydrocron/timeseries/),
[campos](https://podaac.github.io/hydrocron/user-guide/fields/) y
[versiones](https://podaac.github.io/hydrocron/user-guide/versioning/).

## MODIS histórico — órdenes asíncronas

`scripts/data/order_modis.py` solicita MOD13Q1 2000–2024, un píxel por ciudad,
mediante `/subsetOrder`; esta vía oficial admite más de diez fechas.
ORNL exige contacto para avisar la finalización. El correo autorizado sólo se
envía al servicio en memoria; no se guarda en código, cachés ni Git.
El UID admite como máximo ocho caracteres; el identificador devuelto puede
contener `:`. Ambos contratos se corrigieron a partir de respuestas reales.

```powershell
# Configurar EARTHLENS_ORNL_EMAIL localmente con el contacto autorizado.
docker compose exec -T -e EARTHLENS_ORNL_EMAIL backend python -m scripts.data.order_modis --all --start-year 2000 --end-year 2024
docker compose exec -T backend python -m scripts.data.order_modis --poll
```

Se registra el estado antes de enviar. Repetir el comando no duplica órdenes
aceptadas o inciertas; `--retry-rejected` sólo reintenta rechazos explícitos.
Una interrupción con aceptación incierta exige recuperar el enlace de resultados,
sin reenviar. Al recibir el CSV se verifica producto, colección por cada nombre
original, coordenadas, un píxel, fechas y bandas QA completas antes de publicar.
Se mantienen separadas las cachés REST sin colección declarada y las de órdenes
con colección demostrada. Un HTTP 200 de envío **no se cuenta como observaciones**.
El índice de resultados se consulta para descubrir el CSV; no se presupone su
nombre. El sondeo informa por separado el estado HTTP de entrega y el de envío.
La colección actualmente admitida por el importador es `061`; otra requiere
verificar sus metadatos y QA antes de habilitarla.

Si se recibe un enlace de una orden cuyo identificador no se conservó, registrarlo
sin volver a enviar el pedido (reemplazar el identificador del ejemplo):

```powershell
docker compose exec -T backend python -m scripts.data.order_modis --city mendoza --start-year 2000 --end-year 2024 --result-url 'https://modis.ornl.gov/subsetdata/IDENTIFICADOR_RECIBIDO'
docker compose exec -T backend python -m scripts.data.order_modis --poll
```

Se verifica dominio oficial, producto y UID correspondiente antes de registrar
el enlace; la posterior validación del CSV vuelve a comprobar ciudad y período.

## Integración — fase 7, alcance descriptivo verificado

Las nuevas series llevan `analysis.enabled: false`. No se agregan a la familia
de Radar ni a los seis indicadores actuales de Fingerprint. Las series, gráficos
nativos y comparaciones descriptivas ya se consumen desde `/sources` y desde el
panel desplegable del Explorador, Comparador, Radar, Fingerprint y Modo detective.
Conservan huecos y fechas reales; el eje temporal respeta intervalos irregulares.
El deslizador recorre la respuesta localmente sin nuevas consultas. No se
transformaron las misiones ni se calcularon estadísticas nuevas. La ampliación
de métodos requiere acordar agregación, QA, estacionalidad, compatibilidad espacial,
cobertura y familia estadística con el responsable del motor.

Time Machine se incorporó posteriormente desde `origin/main` ce9a1e2 mediante
un adaptador Flask a cachés POWER reales y funciones del motor del equipo. No
se activaron muestras, coordenadas libres ni ajustes espaciales artificiales.
La ampliación a estas otras fuentes sigue pendiente de contrato y metodología.
Ver [integración de Time Machine](../architecture/time-machine-integration.md).
El usuario confirmó que Earth Connections aún no existe. Los endpoints nativos
quedan preparados para conectarla cuando esté disponible. MERRA-2 directo y
TimesFM tampoco están integrados; no hay pronósticos ni modelos verificados.

Inventario reproducible sin red y verificación optativa de navegador:

```powershell
docker compose exec -T backend python -m scripts.audit.audit_science
docker compose exec -T backend python -m scripts.audit.check_scientific_cache
.\venv\Scripts\python.exe -B -m scripts.audit.check_scientific_pages
```

`check_scientific_cache` necesita los históricos reales inicializados. Bloquea
la red y verifica selecciones 2005–2010 de GLDAS y comparación POWER–GPM en las
tres ciudades piloto, con hashes protegidos. La capa nativa reutiliza extracciones
que contengan el período solicitado; filtrar fechas no es agregar ni remuestrear.
Conserva QA y fecha de obtención, y documenta el período original en procedencia.
