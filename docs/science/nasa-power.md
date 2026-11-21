# NASA POWER: consultas mensuales

Esta etapa sólo modifica el proveedor `services/providers/power.py`. El normalizador
y el script existente `scripts/audit/probe_nasa_power.py` se conservan.

## Uso

```python
from services.providers.power import VARIABLES, get_data, get_data_multi

# Interfaz existente, con los mismos argumentos y campos de resultado.
temperature = get_data(-45.86, -67.50, "T2M", 2000, 2024)

# Una sola petición HTTP para las seis variables.
results = get_data_multi(-45.86, -67.50, list(VARIABLES), 2000, 2024)
temperature_series = results["T2M"]["series"]
humidity_series = results["RH2M"]["series"]
```

`get_data_multi()` recibe una colección no vacía de códigos y devuelve un diccionario
por código. Elimina duplicados conservando el orden. Cada resultado tiene los campos
de `get_data()` y un campo adicional `metadata`. Ambos métodos usan la misma lógica.
Las variables inválidas se rechazan antes de acceder a la red. Si NASA omite una
variable solicitada o devuelve una estructura inválida, se lanza `ValueError`; no se
entregan resultados parciales. Los errores HTTP, de conexión y de JSON se propagan.

## Variables verificadas

Verificación con una respuesta real de la API mensual, comunidad `AG`, coordenadas
`(-45.86, -67.50)`, período `2024–2024`: HTTP 200 y 12 registros mensuales por variable.
Las unidades siguientes son las recibidas de NASA, sin conversión:

| Código | Magnitud | Unidad recibida |
| --- | --- | --- |
| `T2M` | Temperatura a 2 m | `C` |
| `T2M_MAX` | Temperatura máxima a 2 m, producto mensual | `C` |
| `T2M_MIN` | Temperatura mínima a 2 m, producto mensual | `C` |
| `PRECTOTCORR` | Precipitación corregida | `mm/day` |
| `RH2M` | Humedad relativa a 2 m | `%` |
| `WS2M` | Velocidad del viento a 2 m | `m/s` |

`PRECTOTCORR` mantiene la tasa del producto mensual en `mm/day`: no representa un
acumulado mensual en milímetros. Los valores de máxima y mínima pertenecen al
producto mensual de NASA; el proveedor no calcula ni redefine esos extremos.

La respuesta verificada identifica las fuentes `MERRA2` y `POWER`. El campo histórico
`dataset="MERRA-2"` se conserva por compatibilidad. `metadata.header` guarda las
fuentes originales, versión de API, intervalo, estándar horario y valor de relleno;
`metadata.parameter` conserva los metadatos de la variable, incluidos `units` y
`longname`. También se conservan geometría, mensajes y demás metadatos de primer
nivel. La consulta usa datos de grilla del producto, no una estación meteorológica.

El normalizador existente ordena los meses, excluye el registro anual `YYYY13` y
convierte el valor de relleno indicado por NASA en `None` (`null` en JSON). Conserva
los ceros y los nulos originales. No interpola ni crea meses ausentes. Si faltan
metadatos opcionales, se mantienen los valores de respaldo anteriores del proveedor.

Documentación oficial:
[API mensual de NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/),
[diccionario de parámetros](https://power.larc.nasa.gov/parameters/).

## Pruebas

Desde la raíz del repositorio, en PowerShell:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas sin red usan valores sintéticos para verificar el contrato de software;
no son observaciones ni resultados científicos. No requieren dependencias nuevas.
La verificación real es optativa y realiza dos consultas a NASA:

```powershell
$env:EARTHLENS_POWER_LIVE = "1"
try {
    .\venv\Scripts\python.exe -m unittest discover -s tests -p test_power_provider_live.py -v
} finally {
    Remove-Item Env:\EARTHLENS_POWER_LIVE
}
```

Esta última verifica las seis variables en 2024 y la consulta original de humedad
de 2000 a 2024, comparando las series del año compartido.
