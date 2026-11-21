# Actualización de main: proyecciones y Gunicorn

Se integra `origin/main` `4157789` sobre `9c1ee9f`, con seis conflictos resueltos.
El usuario autorizó completar el commit de merge local; no se hace push ni despliegue.

El modelo del compañero, `services/prediction/forecast.py`, se conserva. Es extrapolación
OLS/t de Student, no TimesFM ni observaciones futuras de NASA. El adaptador
`services/prediction/forecast_service.py` obtiene históricos POWER cacheados por ciudad,
mantiene unidades/procedencia y rechaza series arbitrarias y coordenadas HTTP.
El resultado es `model_projection`, científicamente provisional. Se separa del
histórico, no modifica Radar/Fingerprint y no presenta impactos causales ni la
heurística de confianza del modelo como validación predictiva.

`POST /api/forecast` y el bloque `forecast` de Time Machine conservan el sobre
Flask. El cliente recalcula por ciudad/período; no reenvía observaciones. Los
errores no generan datos de respaldo. La calibración y revisión B06 siguen pendientes.

La imagen incorpora Gunicorn 27.0.1 en Linux, usa `${PORT:-5000}` y adapta el
healthcheck. Compose mantiene Flask con recarga. Se verificó Gunicorn con health
200 y `pip check` correcto; no se publicaron servicios Cloud Run/Vercel.
Paquete oficial: https://pypi.org/project/gunicorn/27.0.1/.

Verificación concentrada por pedido del usuario: una suite completa, 210 pruebas
descubiertas, 209 aprobadas y una de red omitida; una comprobación breve de Chrome
con 25 años históricos, dos gráficos de proyección y recálculo 2025–2030 (6 filas),
sin errores JavaScript. No se repitieron los recorridos largos de navegador.

POWER y Radar faltaban al iniciar. Se recuperaron 25 copias locales previamente
validadas y el artefacto Radar, sin solicitudes nuevas a NASA. Las 542 cachés y
reportes preexistentes se conservaron; las observaciones no se añaden a Git.
