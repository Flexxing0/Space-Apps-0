# Integración de main en feature/backend-api

El usuario solicitó traer `main` y resolver conflictos. Referencias inspeccionadas
el 15/11/2026: backend `80925bf` y `origin/main` `ce9a1e2`. Se usó fetch y merge
con `--no-commit`: el resultado queda preparado para revisión, sin commit ni push,
respetando la restricción previa. Respaldo de la rama:
`backup/backend-before-main-20261115-133944`.

## Resoluciones

- Se conserva la Application Factory Flask, sus Blueprints, sobres JSON, todos
  los proveedores, unidades, caché, rutas y páginas anteriores. Main eliminaba
  Resultados/Comparador y proponía otro servidor: se preservan las vistas funcionales.
- Docker conserva Python 3.12, dependencias verificadas, puerto 5000 y montaje de
  caché. La configuración antigua queda como alias opcional `compose.legacy.yaml`,
  mediante `extends`, evitando dos configuraciones autodetectadas. El entrypoint
  heredado no se utiliza. No se desplegó en Cloud Run ni Vercel; esos descriptores
  quedan recibidos y la app expone la entrada WSGI que requieren.
- El motor toma las 298 líneas aditivas de main. Se verificó que todo el núcleo
  anterior es idéntico al de la rama local. No se cambia la metodología de Radar
  ni Fingerprint. Anomalías y comparación de épocas son provisionales y requieren
  la revisión conjunta pendiente; no se atribuye causalidad.
- Los catálogos y tests en conflicto conservan sus contratos locales. Las misiones
  de main ya están representadas en `data/guided_missions.json`. El catálogo
  estático alternativo se conserva como referencia; no sustituye unidades NASA
  ni el catálogo dinámico de variables verificadas.
- Time Machine conserva su interfaz de main, con un adaptador al backend actual:
  GET/POST `/api/time-machine`, ciudad verificada, períodos, series reales anuales,
  metadatos, procedencia y disponibilidad regional. Usa exclusivamente cachés.
  No descarga observaciones al navegar o animar el histórico. Cortar épocas
  consulta al motor de Python; el cliente no estima p-valores alternativos.
- El servicio y el cliente anteriores podían generar ajustes de valores al
  redimensionar el mapa o usar muestras ante un fallo. Esos caminos no están
  activos. Los cuadrantes, selección de coordenadas y supuestos espaciales quedan
  deshabilitados; los errores se muestran sin inventar un respaldo. El mapa
  representa ciudades de grilla, no estaciones meteorológicas.
- Si ambas épocas son constantes y distintas, se rechaza la comparación con
  422: no se publica el p-valor fijo que devolvía el helper en ese caso degenerado.
  La protección está en el adaptador y no altera el motor recibido de main.
- El código anterior y las suites ligadas a `EarthLensUnifiedHandler` quedan como
  referencias de migración, no como pruebas aprobadas del servidor nuevo:
  `tests/statistics_fixtures/main_legacy/`. Se mantienen las 193 pruebas previas y
  se prueba el contrato Flask integrado en `tests/workspace/test_time_machine.py`.

La suite integrada pasó: 201 pruebas descubiertas, 200 aprobadas y una de red
optativa omitida. También pasaron los verificadores Chrome de las interfaces
anteriores, productos, panel multiproveedor y Time Machine. No se hicieron
consultas nuevas a proveedores para verificar el merge.

## Datos conservados y recuperados

Antes del merge había 515 archivos locales de caché/reportes, con GLDAS, GPM y
MODIS. POWER y Radar no estaban presentes. Se respaldaron esos 515 archivos y
se verificó que conservaran sus hashes. Las cachés entrantes se apartaron para
validarlas, y no se añadieron al índice Git.

De main se validaron 25 cachés POWER 2000–2024, seis variables, coordenadas del
catálogo, clave canónica, fuentes, unidades y cobertura: 150 series, 45.000 valores
válidos y cero faltantes. Los 516 valores solapados con proyecciones científicas
locales coinciden exactamente. Se recuperaron esas copias sin solicitudes nuevas
a NASA. Informe local: `data/cache/reports/main-power-cache-validation.json`.

Radar se regeneró desde esas cachés: 150 análisis provisionales, 48 señales
nominales y cero descubrimientos confirmados. Los datos nuevos permanecen fuera
de Git. El respaldo previo y la cuarentena se conservan en el directorio temporal
`EarthLens-main-merge-3e45df21cfac47b1b187b6ed6edb0822` del usuario.

## Verificación reproducible

```powershell
docker compose up -d --build --wait --wait-timeout 60
docker compose exec -T backend python -B -m unittest discover -s tests
docker compose exec -T backend python -B -m scripts.audit.audit_science
.\venv\Scripts\python.exe -B -m scripts.audit.check_time_machine
.\venv\Scripts\python.exe -B scripts/audit/check_web.py
.\venv\Scripts\python.exe -B scripts/audit/check_product_pages.py
git diff --name-only --diff-filter=U
```

No descargar ni forzar actualizaciones para verificar este merge. Los resultados
finales y pendientes se registran en `docs/project/BACKEND_TASKS.md`. Una prueba omitida de red
no equivale a una consulta científica real. El despliegue productivo y la revisión
metodológica siguen pendientes.
