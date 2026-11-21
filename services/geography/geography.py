"""Restricción a Argentina y contrato para incorporar límites oficiales."""

from dataclasses import asdict, dataclass
import math
from typing import Callable


class TerritoryValidationUnavailable(ValueError):
    """Todavía no se configuró un validador territorial definitivo."""


class OutsideArgentina(ValueError):
    """La ubicación no fue identificada dentro de Argentina."""


@dataclass(frozen=True)
class TerritoryEvidence:
    inside: bool
    country_code: str
    method: str
    source: str


TerritoryValidator = Callable[[float, float], TerritoryEvidence]


def validate_coordinates(latitude, longitude):
    """Valida formato y rangos mundiales; no prueba pertenencia a Argentina."""
    for name, value, lower, upper in (
        ("latitude", latitude, -90, 90),
        ("longitude", longitude, -180, 180),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not lower <= value <= upper):
            raise ValueError(f"{name} debe ser un número finito entre {lower} y {upper}")
    return float(latitude), float(longitude)


def validate_argentina_location(latitude, longitude, validator=None):
    """Requiere evidencia territorial para coordenadas ajenas al catálogo.

    El futuro adaptador deberá consultar límites oficiales (punto en polígono
    o servicio de límites). Una caja rectangular nunca habilita una consulta.
    """
    latitude, longitude = validate_coordinates(latitude, longitude)
    if validator is None:
        raise TerritoryValidationUnavailable(
            "Configurar un validador de límites oficiales de Argentina para ubicaciones fuera del catálogo"
        )
    evidence = validator(latitude, longitude)
    if (not isinstance(evidence, TerritoryEvidence)
            or evidence.method not in {"point_in_polygon", "official_boundary_service"}
            or not isinstance(evidence.source, str) or not evidence.source.strip()):
        raise TerritoryValidationUnavailable("El validador no aportó evidencia de límites oficiales")
    if evidence.inside is not True or evidence.country_code != "AR":
        raise OutsideArgentina("La ubicación debe pertenecer a la República Argentina")
    return asdict(evidence)
