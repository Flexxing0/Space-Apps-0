#!/bin/sh
set -e

# /app_baked contiene la copia íntegra compilada en la imagen Docker (Rol 03 + Rol 06 + API).
# /workspace (opcional) monta el repositorio del host.
# Sincronizamos de forma NO destructiva: siempre están garantizados todos los archivos base
# de /app_baked aunque el usuario cambie a una rama de Git vacía o incompleta en el host,
# y además se incorporan archivos nuevos que existan en la rama activa del host.

sync_branches_nondestructive() {
  cp -rf /app_baked/. /app/
  if [ -d "/workspace" ]; then
    for dir in templates static services routes data tests; do
      if [ -d "/workspace/$dir" ]; then
        cp -rf "/workspace/$dir/." "/app/$dir/" 2>/dev/null || true
      fi
    done
    if [ -f "/workspace/app.py" ]; then
      cp -f "/workspace/app.py" "/app/app.py" 2>/dev/null || true
    fi
  fi
}

sync_branches_nondestructive

# Vigilar cambios de rama en segundo plano cada 3 segundos sin borrar nunca los módulos base
(
  while true; do
    sleep 3
    sync_branches_nondestructive
  done
) &

exec "$@"
