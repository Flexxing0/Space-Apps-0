"""Proveedores invocados exclusivamente por procesos de preparación offline."""

from collections import defaultdict
from statistics import mean
from typing import Protocol

from services.prediction.contracts import PredictionBatch, PredictionPlan, PredictionPoint, SeriesKey, timestamp
from services.prediction.prediction import seasonal_naive_7d
from services.providers.cache import utc_now


class PredictionProvider(Protocol):
    name: str
    revision: str
    enabled: bool

    def produce(self, plan: PredictionPlan) -> PredictionBatch: ...


class OpenMeteoProvider:
    name = 'open-meteo'
    revision = 'adapter-v1'
    enabled = True

    def __init__(self, weather):
        self.weather = weather

    def produce(self, plan):
        if plan.key.frequency != 'hourly' or plan.history is not None:
            raise ValueError('Open-Meteo requiere una selección horaria sin entrenamiento local.')
        requested = plan.targets()
        row = self.weather.series(plan.key.city_id, kind='forecast', variable=plan.key.variable,
                                  start=requested[0][:10], end=requested[-1][:10])
        city = row['location']
        source_key = SeriesKey(city['id'], city['latitude'], city['longitude'],
                               row['variable'], row['unit'], row['frequency'])
        if source_key != plan.key or row['kind'] != 'forecast' or row['provider'] != 'Open-Meteo':
            raise ValueError('El pronóstico operativo no coincide con la selección.')
        values = {timestamp(p['date']).isoformat(): p['value'] for p in row['series']}
        return PredictionBatch(plan.key, self.name, 'operational_forecast', row['product'],
                               None, row['issued_at'], None, 'not_validated',
                               {**row['provenance'], 'fetched_at': row['fetched_at'],
                                'issuance_status': row['issuance_status']},
                               tuple(PredictionPoint(date, i, values[date])
                                     for i, date in enumerate(requested, 1)))


class MonthlyClimatology:
    name = 'climatology'
    revision = 'monthly-mean-v1'
    enabled = True

    def produce(self, plan):
        history = plan.history
        if history is None or plan.key.frequency != 'monthly' or history.period[1] >= plan.first_target:
            raise ValueError('La referencia requiere historia mensual anterior al período objetivo.')
        months = defaultdict(list)
        for stamp, value in history.observations:
            if value is not None:
                months[stamp[5:7]].append(value)
        points = tuple(PredictionPoint(stamp, i, mean(months[stamp[5:7]]) if months[stamp[5:7]] else None)
                       for i, stamp in enumerate(plan.targets(), 1))
        return PredictionBatch(plan.key, self.name, 'climatology_reference', 'monthly_mean', self.revision,
                               utc_now(), history.period, 'reference_only',
                               {**history.provenance, 'historical_product': history.product,
                                'samples_per_month': {month: len(values) for month, values in months.items()}}, points)


class SeasonalBaseline:
    name = 'seasonal-baseline'
    revision = 'seasonal-naive-7d-v1'
    enabled = True

    def produce(self, plan):
        history = plan.history
        if history is None or plan.key.frequency != 'daily' or len(history.observations) < 7:
            raise ValueError('El baseline requiere al menos siete días de historia.')
        history.require_complete()
        values = seasonal_naive_7d([value for _, value in history.observations], plan.steps)
        return PredictionBatch(plan.key, self.name, 'model_forecast', 'seasonal_naive_7d', self.revision,
                               utc_now(), history.period, 'not_validated',
                               {**history.provenance, 'historical_product': history.product},
                               tuple(PredictionPoint(stamp, i, value)
                                     for i, (stamp, value) in enumerate(zip(plan.targets(), values), 1)))


class BigQueryTimesFM:
    name = 'bigquery-timesfm'
    revision = 'TimesFM 3.0'
    enabled = False

    def produce(self, plan):
        raise RuntimeError('BigQuery TimesFM 3.0 está deshabilitado.')
