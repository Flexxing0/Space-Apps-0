# Ejecución local estable de EarthLens

Abrir **http://localhost:5000/** con Docker Desktop en funcionamiento.

Desde la raíz del repositorio, en PowerShell:

```powershell
docker compose -f compose.runtime.yaml up -d --wait
docker compose -f compose.runtime.yaml ps
docker compose -f compose.runtime.yaml logs --tail 50 backend
```

Para detener esta ejecución sin borrar datos:

```powershell
docker compose -f compose.runtime.yaml stop
```

Esta configuración utiliza la imagen local `earthlens-backend:local-stable`,
previamente construida con el backend y la interfaz integrada de Time Machine.
No monta el código del directorio de trabajo: cambiar de rama no mezcla el
`app.py` de una versión con los módulos de otra. No tiene recarga automática.
Para incorporar cambios de código hay que reconstruir la imagen desde la rama
que contiene la aplicación integrada y actualizar este despliegue.

Los contenedores anteriores `earthlens-backend-1` y `earthlens-monitor-1`
quedaron detenidos. No iniciarlos simultáneamente: el primero utiliza el mismo
puerto y monta archivos de la rama activa.

## Persistencia y recuperación realizada

Los volúmenes externos `earthlens_scientific_cache` y `earthlens_runtime_data`
contienen, respectivamente, las cachés científicas y la base SQLite. Se copiaron
los datos existentes antes del arranque: **683 archivos de caché, 93.711.080
bytes**, verificados individualmente mediante SHA-256. SQLite se copió mediante
su API de backup, comprobando cantidades por tabla y `PRAGMA quick_check`.
Los originales de `data/cache` y `data/runtime` se conservaron.

El informe de migración queda en `/app/data/runtime/migration-report.json`,
dentro del volumen. Los datos nuevos de esta ejecución se guardan en los
volúmenes, no en las carpetas del repositorio.

No borrar los volúmenes. Esta configuración requiere la imagen y los volúmenes
ya preparados en esta computadora; no reemplaza un procedimiento de instalación
desde cero. El healthcheck de `/api/health` comprueba el proceso HTTP y no
certifica la disponibilidad de proveedores externos.
