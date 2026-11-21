# Publicar la interfaz local en Cloud Run

**Actualización verificada:** el trigger automático de main publica en
<https://earthlens-pp-224139449590.us-central1.run.app/>. La restauración `ba8ea3a`
ya se construyó y desplegó correctamente; ver [resultado](../../docs/history/restore-main.md).
El paquete manual descrito abajo apunta al servicio anterior `earthlens`, de la
URL sin `-pp`; no hace falta ejecutarlo para usar el despliegue nuevo.

El paquete se genera desde la imagen que sirve localhost, no desde los archivos
de `main`. Incluye el código, los catálogos públicos y un Dockerfile que escucha
en `PORT`; excluye credenciales, pruebas, cachés científicas y bases privadas.

Preparación desde esta computadora, con el backend local en ejecución:

```powershell
.\venv\Scripts\python.exe scripts/maintenance/prepare_cloud_release.py
```

El resultado es `dist/earthlens-cloud-release.zip`. No se añade a Git.

En Google Cloud Console, abrir Cloud Shell con una cuenta autorizada para el
proyecto del servicio `earthlens-224139449590.us-central1.run.app`. Usar el menú
de Cloud Shell para subir ese ZIP. Después ejecutar en Cloud Shell:

```bash
RELEASE_DIR=$(mktemp -d "$HOME/earthlens-release.XXXXXX")
unzip -q "$HOME/earthlens-cloud-release.zip" -d "$RELEASE_DIR"
bash "$RELEASE_DIR/deploy.sh"
```

El script resuelve el ID del proyecto a partir del número ya conocido. Conserva
un informe del tráfico anterior, construye una revisión sin tráfico, verifica el
mapa/timeline y el hash del JavaScript, y sólo entonces asigna el 100 % del tráfico
a esa revisión concreta. Si la comprobación pública falla, intenta restaurar la
distribución anterior. No modifica IAM ni elimina revisiones. Construir y ejecutar
recursos de Google Cloud puede generar cargos según el uso; no se garantiza costo
cero.

El script requiere permisos de despliegue y de construcción desde código. Si
Google solicita habilitar las APIs necesarias, revisar el mensaje en Cloud Shell.
La autenticación ocurre allí: no pegar tokens ni claves en el chat o repositorio.

## Alcance y persistencia

Este procedimiento publica el código y la interfaz; no transfiere los volúmenes
Docker. Los históricos precalculados, las cuentas/eventos privados y el proceso
de monitoreo necesitan su propia migración. El SQLite del sistema de archivos
temporal de Cloud Run no es almacenamiento persistente. No incluirlo en la imagen.

Si existe un trigger de despliegue desde `main`, corregir su rama de origen para
que apunte al código integrado antes de nuevos pushes: otro build de la aplicación
anterior puede volver a reemplazar esta revisión. El script no altera triggers.

No se considera completado el despliegue remoto hasta que `deploy.sh` finalice y
la URL pública pase la verificación. Preparar el ZIP no equivale a publicarlo.

Verificación local del procedimiento: imagen construida desde el paquete y cinco
rutas HTTP aprobadas en el puerto 8080; seis pruebas de integridad, promoción y
rollback aprobadas en Docker sin red, con Google Cloud simulado. La autenticación,
la construcción y el cambio de tráfico reales de Cloud Run siguen pendientes.

Referencias: [desplegar desde código](https://docs.cloud.google.com/run/docs/deploying-source-code),
[probar revisiones y asignar tráfico](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration).
