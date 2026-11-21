# Restauración de la versión integrada en main — 15/11/2026

## Resultado verificado

Commit de restauración: `ba8ea3a`. El despliegue automático de ese commit terminó
correctamente en Cloud Build: [build 76528ae7-98ea-442e-86c5-988baf2a959a](https://console.cloud.google.com/cloud-build/builds;region=us-central1/76528ae7-98ea-442e-86c5-988baf2a959a?project=224139449590).

**Abrir <https://earthlens-pp-224139449590.us-central1.run.app/>.**
El trigger publica en `earthlens-pp`. La URL anterior sin `-pp` pertenece al
servicio `earthlens` y sigue sirviendo la otra versión. La raíz, `/api/health` y
`/static/js/workspace.js` del servicio nuevo devolvieron 200. El JavaScript coincide
con localhost; Chrome verificó mapa, timeline, pronóstico real cargado, vista móvil
y ausencia de errores JavaScript. Las capturas quedan localmente en
`dist/cloud-main-verification/`, fuera de Git.

## Procedimiento de recuperación

El usuario autorizó publicar de nuevo su rama `feature/backend-api` en `main`
después de los pushes cruzados del equipo. Se tomó como fuente `529c7a9` y como
base del commit de restauración `origin/main` `56c5e1e`.

La rama del backend ya era antecesora de main; un merge normal no recuperaba los
archivos reemplazados posteriormente. Se restauró su árbol en una copia aislada
y se preparó un commit nuevo sobre main. No se reescribe el historial ni se usa
force-push; el código previo continúa accesible en sus commits anteriores.

La aplicación recupera `app.py`, los Blueprints, los proveedores, los servicios,
las pruebas, la documentación y `pages/workspace.html`. La entrada `/` vuelve a abrir
el mismo mapa y la timeline que la imagen local. Se conservan los nuevos helpers
de publicación en `deployment/cloud-run` y se incluyen en el Dockerfile para que
sus pruebas funcionen dentro del contenedor. Los artefactos locales, las copias
de integración, las cachés científicas y la base SQLite quedan fuera de Git y
del contexto de construcción.

Las copias locales de cachés/base se respaldaron antes de actualizar el checkout.
Los volúmenes `earthlens_scientific_cache` y `earthlens_runtime_data`, utilizados
por los contenedores activos, no se modifican durante la restauración.

Validación del árbol publicado:

- Imagen `earthlens-main-restore:verification` construida correctamente.
- Suite Docker sin red: **254 pruebas ejecutadas, 253 aprobadas y una NASA live
  opcional omitida**. Las seis pruebas nuevas de despliegue usan Google Cloud
  simulado; no representan consultas científicas ni una publicación real.
- Arranque Gunicorn con `PORT=8080`: `/`, `/index.html`, `/time-machine`,
  `/api/health`, `/api/cities` y `/static/js/workspace.js` responden 200.
- El JavaScript de la interfaz coincide con localhost al normalizar finales de línea.

Publicar main actualiza el código en GitHub. La construcción y activación de una
revisión de Cloud Run requiere su pipeline o una sesión autorizada. No se considera
verificado ese despliegue por haber aprobado las pruebas locales.

Si el servicio no tiene un trigger automático para main, desde un checkout nuevo
de esta rama, en Cloud Shell con el proyecto correcto seleccionado:

```bash
gcloud run deploy earthlens --source . --region us-central1 --port 8080 --memory 1Gi
```

Para probar una revisión sin tráfico antes de activarla, utilizar el procedimiento
en [deployment/cloud-run](../../deployment/cloud-run/README.md). La persistencia de
datos, usuarios y monitoreo continúa siendo una dependencia del despliegue.
