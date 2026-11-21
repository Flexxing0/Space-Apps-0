# Earth Time Machine: integración y límites

Actualización del merge autorizado de `origin/main` ce9a1e2: `/time-machine` está
integrado en Flask y GET/POST `/api/time-machine` usa el sobre común y sólo ciudades
del catálogo. `services/workspace/time_machine_service.py` obtiene POWER desde caché, filtra
el período solicitado, conserva unidades/metadatos y reutiliza el motor del equipo.
El histórico y el mapa de ciudades son reales; los resultados son provisionales.
No hay muestras de respaldo, valores ajustados artificialmente, coordenadas libres
ni cuadrantes activados. Los nuevos helpers estadísticos provienen de main; el
núcleo anterior del motor permanece intacto. Ver [decisiones del merge](../history/merge-main.md).

Queda pendiente extender esta interfaz a GLDAS, MODIS, GPM y SWOT con su método y
frecuencia adecuados, además de la revisión metodológica, límites territoriales
y observaciones espaciales. El enlace a `/sources` ofrece las series nativas de
esas fuentes. No se afirma que sus análisis estén incorporados a Time Machine.

## Historial del contrato anterior al merge

Se inspeccionó `origin/feature/earth-time-machine`, commit `8a39937`, sin fusionar
ni modificar sus archivos. La interfaz existe en esa rama; no se creó un reemplazo.
El usuario confirmó que Earth Connections todavía no está implementado.

La rama de Time Machine define otro servidor y otro contrato de ciudades y
análisis. Sustituir `app.py` por su versión eliminaría servicios locales. Además,
su servicio llama funciones estadísticas que no existen en el motor local y
conserva un camino de muestras de respaldo (`data/samples/argentina_reference_series.json`)
y consultas por coordenadas libres. Ninguno de esos caminos está habilitado aquí.

| Necesidad de la interfaz | Contrato real disponible | Trabajo pendiente |
| --- | --- | --- |
| Ubicación | `GET /api/cities`, sobre `status/data/meta`, catálogo argentino | Adaptar la lectura que espera `cities` en primer nivel; seleccionar IDs. |
| Variables y unidades | `GET /api/science/variables` | Usar proveedor, producto, versión y cobertura; retirar el respaldo visual que interpreta variables desconocidas como T2M. |
| Recorrido histórico | `POST /api/science/data` | Dibujar valores y fechas nativas; admitir `null`, compuestos de 16 días y tasas mensuales sin convertirlas silenciosamente. |
| Agua superficial | `GET /api/science/water-features`, `POST /api/science/water-data` | Vista independiente por tramo y pasos irregulares; conservar QA, incertidumbre y geometría. |
| Comparación descriptiva | `POST /api/science/compare` | Mismo producto/variable o conversión explícita POWER–IMERG; no interpretar diferencias como causalidad. |
| Anomalías, percentiles, z-score y comparación estadística de períodos | No disponibles para nuevas fuentes en este contrato | Coordinar entrada/salida y metodología con el responsable del motor; no llenar campos ausentes con ceros ni calcular otra regresión. |
| Grilla espacial y coordenadas libres | No habilitadas | Dependen del validador territorial real y de observaciones espaciales específicas; una caja no basta. |

`static/js/products/scientific.js` expone `EarthLensScience.request(path, body, signal)`
para consumir el mismo sobre HTTP. El panel de fuentes ya permite recorrer
históricos reales sin solicitudes adicionales, pero no sustituye ni confirma
la integración de la interfaz Time Machine de la otra rama.

Para avanzar: acordar con su responsable una adaptación de la interfaz existente
a las rutas actuales, incorporar sus archivos sin reemplazar el servidor y
mantener deshabilitadas las vistas estadísticas/espaciales sin contrato aprobado.
No habilitar datos de muestra como respaldo ante fallos de proveedores.
