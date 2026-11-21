"""Consultas mensuales de NASA POWER, individuales o multivariable."""

import requests

from services.providers.normalizer import normalize_data


BASE_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"


VARIABLES = {
    "T2M": {
        "name": "Temperatura media",
        "unit": "°C"
    },
    "T2M_MAX": {
        "name": "Temperatura máxima",
        "unit": "°C"
    },
    "T2M_MIN": {
        "name": "Temperatura mínima",
        "unit": "°C"
    },
    "PRECTOTCORR": {
        "name": "Precipitaciones",
        "unit": "mm/day"
    },
    "RH2M": {
        "name": "Humedad relativa",
        "unit": "%"
    },
    "WS2M": {
        "name": "Velocidad del viento",
        "unit": "m/s"
    }
}


def get_data(latitude, longitude, variable, start_year, end_year):
    """Conserva la interfaz de consulta de una única variable."""
    return get_data_multi(
        latitude, longitude, [variable], start_year, end_year
    )[variable]


def get_data_multi(latitude, longitude, variables, start_year, end_year):
    """Consulta varias variables en una petición y devuelve un mapa por código.

    Cada resultado conserva los campos de get_data() y añade los metadatos
    originales de NASA. Las unidades no se convierten y los valores faltantes
    se normalizan a None mediante el normalizador existente.
    """
    if isinstance(variables, (str, bytes)):
        raise ValueError("variables debe ser una colección de códigos")

    try:
        requested = list(variables)
    except TypeError as exc:
        raise ValueError("variables debe ser una colección de códigos") from exc

    if not requested:
        raise ValueError("Debe solicitarse al menos una variable")

    for variable in requested:
        if not isinstance(variable, str) or variable not in VARIABLES:
            raise ValueError("Variable no disponible")

    # Evitar parámetros repetidos sin cambiar el orden solicitado.
    requested = list(dict.fromkeys(requested))

    params = {
        "parameters": ",".join(requested),
        "community": "AG",
        "latitude": latitude,
        "longitude": longitude,
        "start": start_year,
        "end": end_year,
        "format": "JSON"
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    try:
        raw_parameters = data["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise ValueError("NASA POWER devolvió una respuesta sin series válidas") from exc

    if not isinstance(raw_parameters, dict):
        raise ValueError("NASA POWER devolvió una respuesta sin series válidas")

    header = data.get("header", {})
    parameters_metadata = data.get("parameters", {})
    if not isinstance(header, dict) or not isinstance(parameters_metadata, dict):
        raise ValueError("NASA POWER devolvió metadatos inválidos")

    fill_value = header.get("fill_value", -999)
    # Conservar las fuentes, versión de API, geometría, mensajes y demás
    # metadatos recibidos; la serie y los metadatos de cada variable van aparte.
    response_metadata = {
        key: value
        for key, value in data.items()
        if key not in ("properties", "parameters")
    }

    results = {}
    for variable in requested:
        if variable not in raw_parameters:
            raise ValueError(f"NASA POWER no devolvió la variable {variable}")
        raw_series = raw_parameters[variable]
        if not isinstance(raw_series, dict):
            raise ValueError(f"NASA POWER devolvió una serie inválida para {variable}")

        metadata = parameters_metadata.get(variable, {})
        if not isinstance(metadata, dict):
            raise ValueError(f"NASA POWER devolvió metadatos inválidos para {variable}")

        results[variable] = {
            "provider": "NASA POWER",
            "dataset": "MERRA-2",
            "variable": variable,
            "name": VARIABLES[variable]["name"],
            "unit": metadata.get("units", VARIABLES[variable]["unit"]),
            "latitude": latitude,
            "longitude": longitude,
            "start_year": start_year,
            "end_year": end_year,
            "frequency": "monthly",
            "series": normalize_data(raw_series, fill_value),
            "metadata": {**response_metadata, "parameter": metadata},
        }

    return results
