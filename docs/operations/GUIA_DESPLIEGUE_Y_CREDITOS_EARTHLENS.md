# Guía de Despliegue Seguro y Protección de Créditos — EarthLens (NASA Space Apps 2026)

Esta guía reúne el paso a paso completo para publicar **EarthLens** utilizando **Google Cloud Run**, **Vercel**, **Cloudflare** y **GoDaddy**, asegurando un **costo $0.00** y protegiendo al 100 % los créditos de la prueba gratuita de Google Cloud.

---

## Parte 1: Cómo NO quemar los créditos de la Prueba Gratuita de Google Cloud

### 1.1. La regla de oro de la cuenta "Prueba Gratuita" (Free Trial)
- Mientras tu cuenta de Google Cloud permanezca en estado **Prueba gratuita (Free Trial)** y **NO** presiones el botón *"Actualizar a cuenta de pago" (Upgrade to a paid account)*:
  - **Google NO puede realizar cargos automáticos a tu tarjeta.**
  - Si se agotan los $300 USD promocionales o vencen los 90 días, Google simplemente detiene los servicios hasta que tú decidas manualmente si deseas pasar a una cuenta paga.
- **Acción clave**: En **Facturación (Billing) → Descripción general**, verifica que tu cuenta diga *Cuenta de prueba gratuita* y no la pases a cuenta de pago.

---

### 1.2. Servicios de Google Cloud que DEBES EVITAR (Consumen créditos 24/7)
Nunca actives ni crees los siguientes recursos para este proyecto, ya que cobran por hora aunque nadie visite la página:
1. **NO usar Google Kubernetes Engine (GKE)**: Crea clústeres y nodos encendidos las 24 h (~$70 a $150 USD/mes).
2. **NO usar App Engine Flexible** ni máquinas virtuales grandes en **Compute Engine**: Cobran de forma continua las 24 h.
3. **NO usar Cloud SQL**: Una instancia de base de datos relacional encendida 24/7 cuesta entre $10 y $50 USD/mes. **EarthLens no la necesita** porque utiliza archivos JSON locales (`data/`) y caché en memoria/disco.
4. **NO crear un Cloud Load Balancer global**: El balanceador de carga externo cobra ~$18 USD/mes fijos. **Cloud Run ya entrega gratuitamente una URL `https://...run.app` con certificado SSL (HTTPS) integrado.**

---

### 1.3. Comando exacto de despliegue en Cloud Run con límites duros ($0.00)
Cuando despliegues el backend de Python/Docker en **Google Cloud Run**, utiliza siempre la región `us-central1` (incluida en el *Always Free Tier* de Google Cloud) con estas banderas de protección:

```bash
gcloud run deploy earthlens \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --cpu=1 \
  --memory=256Mi \
  --concurrency=80 \
  --timeout=60s \
  --cpu-throttling
```

#### ¿Por qué cada parámetro protege tus créditos?
- `--min-instances=0`: **Fundamental**. Cuando no hay usuarios activos en la página, el contenedor escala a **0 instancias** y el consumo es **$0.00 por hora**.
- `--max-instances=2`: Pone un techo estricto. Si recibes un pico masivo de tráfico o bots, Google Cloud jamás levantará más de 2 contenedores simultáneos.
- `--cpu-throttling`: Garantiza que solo se contabilice CPU durante los milisegundos exactos en que el servidor procesa una petición HTTP, y no mientras el usuario observa el mapa en su navegador.
- `--memory=256Mi` y `--cpu=1`: EarthLens está escrito en Python estándar sin librerías pesadas y consume ~40 MB de RAM; `256Mi` es más que suficiente y minimiza el consumo de cuota.

---

### 1.4. Cuidado con el almacenamiento de imágenes en Artifact Registry
Cada vez que ejecutas `gcloud run deploy --source .`, Cloud Build guarda la imagen Docker compilada en **Artifact Registry** (los primeros **500 MB** son gratuitos; el excedente cuesta $0.10 USD/GB al mes).
- **Ya está configurado `.gcloudignore`** en la raíz del repositorio para excluir `.git/`, `tests/`, `.venv/`, `*.pdf`, `*.docx` y documentos pesados.
- **Recomendación si despliegas muchas veces**: Entra en la consola de Google Cloud a **Artifact Registry → Repositorios → cloud-run-source-deploy** y elimina las imágenes antiguas dejando solo la última versión.

---

### 1.5. Crear una Alerta de Presupuesto de $5 USD (1 minuto)
1. En la consola de Google Cloud, abre **Facturación (Billing) → Presupuestos y alertas (Budgets & alerts)**.
2. Haz clic en **Crear presupuesto (Create Budget)**.
3. Asígnale un monto de **$5 USD** (aplica también sobre el consumo de créditos gratuitos).
4. Configura alertas al **50 % ($2.50)**, **90 %** y **100 %** para recibir un correo inmediato ante cualquier consumo inesperado.

---

## Parte 2: Flujo Completo de Despliegue y Hosting (GoDaddy → Cloudflare → Vercel → Cloud Run)

### 2.1. Arquitectura General

```text
[ Dominio en GoDaddy ]
         │  1. Delegación de Nameservers (NS)
         ▼
[ Cloudflare (DNS + Firewall / Anti-DDoS + SSL) ]
         │  2. Registros DNS (A y CNAME) apuntando a Vercel
         ▼
[ Vercel (Frontend / Edge CDN + Rewrites en vercel.json) ]
         │  3. Redirección transparente de rutas /api/* o app completa
         ▼
[ Google Cloud Run (Contenedor Python/Docker serverless) ]
```

---

### 2.2. Paso 1 — Desplegar el Backend Python/Docker en Google Cloud Run
1. Instala e inicia sesión en Google Cloud CLI (o usa **Google Cloud Shell** desde el navegador subiendo el repositorio desde GitHub):
   ```bash
   gcloud auth login
   gcloud config set project TU_ID_DE_PROYECTO
   ```
2. Ejecuta el comando seguro desde la carpeta del proyecto (`Space-Apps`):
   ```bash
   gcloud run deploy earthlens \
     --source . \
     --region us-central1 \
     --allow-unauthenticated \
     --min-instances=0 \
     --max-instances=2 \
     --cpu=1 \
     --memory=256Mi \
     --concurrency=80 \
     --timeout=60s \
     --cpu-throttling
   ```
3. Al finalizar, Google Cloud te pedirá habilitar las APIs de *Cloud Run* y *Artifact Registry* (responde `y`) y te entregará tu URL pública:
   - Ejemplo: `https://earthlens-xxxxxxxxxx-uc.a.run.app`
4. Abre esa URL en el navegador y verifica que `/`, `/explorer`, `/results`, `/compare` y `/time-machine` carguen correctamente.

---

### 2.3. Paso 2 — Conectar y Hostear en Vercel
Para que Vercel sirva tu aplicación y se conecte de forma transparente con el backend en Cloud Run, crea un archivo `vercel.json` en la raíz del proyecto con la URL que te dio Cloud Run:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "https://earthlens-xxxxxxxxxx-uc.a.run.app/$1"
    }
  ]
}
```
*(Reemplaza `https://earthlens-xxxxxxxxxx-uc.a.run.app` por la URL real de tu servicio en Cloud Run).*

1. Sube tu repositorio a **GitHub**.
2. Entra en [vercel.com](https://vercel.com), haz clic en **Add New... → Project** e importa tu repositorio de GitHub.
3. En **Framework Preset**, selecciona **Other** y presiona **Deploy**.
4. Vercel publicará tu sitio en una URL `https://tu-proyecto.vercel.app`.
5. Ve a **Project Settings → Domains** en Vercel y escribe tu dominio personalizado (ej. `tudominio.com` y `www.tudominio.com`). Vercel te mostrará los registros DNS que debes cargar en Cloudflare.

---

### 2.4. Paso 3 — Delegar el Dominio de GoDaddy a Cloudflare
1. Crea una cuenta gratuita en [cloudflare.com](https://www.cloudflare.com/) y haz clic en **Add a domain (Agregar un dominio)**.
2. Ingresa tu dominio comprado en GoDaddy y elige el plan **Free ($0)**.
3. Cloudflare te asignará **2 Nameservers** (por ejemplo: `ada.ns.cloudflare.com` y `bob.ns.cloudflare.com`).
4. Entra a tu cuenta de **GoDaddy → Mis Productos → Dominios → Administrar DNS → Servidores de nombres (Nameservers)**.
5. Elige **"Usaré mis propios servidores de nombres"** y pega los 2 Nameservers de Cloudflare. Guarda los cambios.

---

### 2.5. Paso 4 — Apuntar Cloudflare hacia Vercel (DNS y SSL)
1. En el panel de **Cloudflare → DNS → Records**, agrega los dos registros que pide Vercel:
   - **Tipo `A`**:
     - Nombre (`Name`): `@` (raíz del dominio)
     - Dirección IPv4 (`Content`): `76.76.21.21`
     - Estado del Proxy: **DNS Only (nube gris)** inicialmente para que Vercel emita el certificado SSL en segundos.
   - **Tipo `CNAME`**:
     - Nombre (`Name`): `www`
     - Destino (`Target`): `cname.vercel-dns.com`
     - Estado del Proxy: **DNS Only (nube gris)** inicialmente.
2. **Importante para evitar el error `ERR_TOO_MANY_REDIRECTS` si activas la nube naranja (Proxied) en Cloudflare**:
   - Ve en Cloudflare a **SSL/TLS → Overview** y selecciona el modo de cifrado **Full (Strict)** (nunca lo dejes en *Flexible*, porque Vercel ya usa HTTPS y el modo *Flexible* genera un bucle infinito de redirecciones).

---

## Resumen de Verificación Final (Checklist)
- [ ] Cuenta de Google Cloud en modo **Free Trial** (sin actualizar a cuenta paga).
- [ ] Alerta de presupuesto configurada en **$5 USD** en Google Cloud Billing.
- [ ] Archivo `.gcloudignore` presente en la raíz del proyecto.
- [ ] Servicio desplegado en **Cloud Run** con `--min-instances=0` y `--max-instances=2`.
- [ ] Proyecto conectado en **Vercel** con `vercel.json` apuntando al servicio de Cloud Run.
- [ ] Nameservers de **GoDaddy** delegados a **Cloudflare**.
- [ ] Registros `A` (`76.76.21.21`) y `CNAME` (`cname.vercel-dns.com`) creados en **Cloudflare** con SSL en modo **Full (Strict)**.

