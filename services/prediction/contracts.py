"""Contratos de series nativas y resultados precalculados."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import re


FREQUENCIES = {'hourly', 'daily', 'monthly'}
IDENTIFIER = re.compile(r'[A-Za-z0-9_.-]{1,100}', re.ASCII)
VALIDATION_STATES = {'not_validated', 'backtested', 'validated', 'reference_only'}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Se requiere una fecha ISO.')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        value += 'T00:00:00+00:00'
    point = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if point.utcoffset() is None:
        raise ValueError('La fecha y hora requiere zona horaria.')
    return point.astimezone(timezone.utc)


def aligned(value, frequency):
    point = timestamp(value)
    if point.minute or point.second or point.microsecond or (frequency != 'hourly' and point.hour):
        raise ValueError('Fecha fuera de la grilla UTC.')
    if frequency == 'monthly' and point.day != 1:
        raise ValueError('El primer día identifica el mes de la muestra.')
    return point


def advance(point, frequency, count=1):
    if frequency == 'monthly':
        year, month = divmod(point.year * 12 + point.month - 1 + count, 12)
        return point.replace(year=year, month=month + 1)
    return point + count * (timedelta(hours=1) if frequency == 'hourly' else timedelta(days=1))


def finite(value):
    try:
        return type(value) in {int, float} and isfinite(value)
    except OverflowError:
        return False


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class SeriesKey:
    city_id: str
    latitude: float
    longitude: float
    variable: str
    unit: str
    frequency: str

    def __post_init__(self):
        if not all(isinstance(v, str) and IDENTIFIER.fullmatch(v) for v in (self.city_id, self.variable)):
            raise ValueError('Identificador de ciudad o variable inválido.')
        if not finite(self.latitude) or not finite(self.longitude) or not (
                -90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValueError('Coordenadas inválidas.')
        if self.frequency not in FREQUENCIES or not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError('Frecuencia o unidad inválida.')


@dataclass(frozen=True)
class HistoricalSeries:
    key: SeriesKey
    product: str
    observations: tuple
    provenance: dict

    def __post_init__(self):
        if (not self.observations or not isinstance(self.product, str) or not self.product.strip()
                or not isinstance(self.provenance, dict) or not self.provenance):
            raise ValueError('Se requieren observaciones, producto y procedencia.')
        normalized = []
        previous = None
        for stamp, value in self.observations:
            current = aligned(stamp, self.key.frequency)
            if (previous is not None and current <= previous) or (value is not None and not finite(value)):
                raise ValueError('Serie desordenada, duplicada o con valores inválidos.')
            normalized.append((current.isoformat(), value))
            previous = current
        object.__setattr__(self, 'observations', tuple(normalized))
        canonical(self.provenance)

    @classmethod
    def from_record(cls, record):
        city = record['location']
        key = SeriesKey(city['id'], city['latitude'], city['longitude'],
                        record['variable'], record['unit'], record['frequency'])
        return cls(key, record['product'], tuple((p['date'], p['value']) for p in record['series']),
                   {**record['provenance'], 'fetched_at': record['fetched_at'],
                    'product_version': record.get('product_version')})

    def require_complete(self):
        previous = None
        for stamp, value in self.observations:
            current = timestamp(stamp)
            if value is None or (previous is not None and current != advance(previous, self.key.frequency)):
                raise ValueError('El modelo requiere una grilla regular y valores disponibles.')
            previous = current

    @property
    def period(self):
        return self.observations[0][0], self.observations[-1][0]


@dataclass(frozen=True)
class PredictionPoint:
    target: str
    horizon: int
    value: float | None
    interval: tuple | None = None
    quantiles: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, 'target', timestamp(self.target).isoformat())
        if type(self.horizon) is not int or self.horizon < 1 or (self.value is not None and not finite(self.value)):
            raise ValueError('Horizonte o estimación inválidos.')
        if self.value is None and (self.interval is not None or self.quantiles):
            raise ValueError('No hay incertidumbre publicable sin estimación.')
        if self.interval is not None:
            lower, upper, level = self.interval
            if not all(finite(v) for v in (lower, upper, level)) or lower > upper or not 0 < level < 1:
                raise ValueError('Intervalo inválido.')
            object.__setattr__(self, 'interval', (lower, upper, level))
        previous_q, previous_value = 0, float('-inf')
        quantiles = tuple(tuple(pair) for pair in self.quantiles)
        for quantile, value in quantiles:
            if not finite(quantile) or not finite(value) or not previous_q < quantile < 1 or value < previous_value:
                raise ValueError('Cuantiles inválidos o cruzados.')
            previous_q, previous_value = quantile, value
        object.__setattr__(self, 'quantiles', quantiles)


@dataclass(frozen=True)
class PredictionBatch:
    key: SeriesKey
    provider: str
    kind: str
    model: str
    model_version: str | None
    generated_at: str | None
    historical_period: tuple | None
    validation_status: str
    provenance: dict
    points: tuple

    def __post_init__(self):
        if (not isinstance(self.provider, str) or not IDENTIFIER.fullmatch(self.provider)
                or not isinstance(self.model, str) or not self.model.strip()
                or not isinstance(self.provenance, dict) or not self.provenance or not self.points):
            raise ValueError('Faltan identidad, procedencia o puntos del resultado.')
        if self.kind not in {'operational_forecast', 'climatology_reference', 'model_forecast'}:
            raise ValueError('Tipo de resultado inválido.')
        if self.validation_status not in VALIDATION_STATES or (
                (self.kind == 'climatology_reference') != (self.validation_status == 'reference_only')):
            raise ValueError('Estado de validación incompatible.')
        if self.kind != 'operational_forecast' and (not self.generated_at or not self.historical_period or not self.model_version):
            raise ValueError('Falta la procedencia temporal o la versión del modelo.')
        if self.generated_at is not None:
            object.__setattr__(self, 'generated_at', timestamp(self.generated_at).isoformat())
        history_end = None
        if self.historical_period is not None:
            first, history_end = (aligned(value, self.key.frequency) for value in self.historical_period)
            if first > history_end:
                raise ValueError('Período histórico inválido.')
            object.__setattr__(self, 'historical_period', (first.isoformat(), history_end.isoformat()))
        previous = None
        for index, point in enumerate(self.points, 1):
            current = aligned(point.target, self.key.frequency)
            if point.horizon != index or (previous is not None and current != advance(previous, self.key.frequency)):
                raise ValueError('El resultado debe seguir su frecuencia y horizonte.')
            if previous is None and self.kind == 'model_forecast' and current != advance(history_end, self.key.frequency):
                raise ValueError('El horizonte debe empezar después de la muestra de entrenamiento final.')
            if self.kind == 'climatology_reference' and (point.interval is not None or point.quantiles):
                raise ValueError('La climatología no publica incertidumbre predictiva.')
            previous = current
        object.__setattr__(self, 'points', tuple(self.points))
        canonical(self.provenance)


@dataclass(frozen=True)
class PredictionPlan:
    key: SeriesKey
    first_target: str
    steps: int
    source_revision: str
    history: HistoricalSeries | None = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.steps) is not int or self.steps < 1 or not isinstance(self.source_revision, str) or not self.source_revision.strip():
            raise ValueError('Se requiere horizonte y revisión explícita de los datos.')
        if self.history is not None and self.history.key != self.key:
            raise ValueError('La historia debe tener la misma ciudad, variable, unidad y frecuencia.')
        object.__setattr__(self, 'first_target', aligned(self.first_target, self.key.frequency).isoformat())

    def targets(self):
        first = timestamp(self.first_target)
        return tuple(advance(first, self.key.frequency, i).isoformat() for i in range(self.steps))
