"""Adaptador de carga BigQuery offline. Produce NDJSON sin clientes ni credenciales."""

from dataclasses import asdict, dataclass

from services.prediction.contracts import canonical, digest, timestamp


@dataclass(frozen=True)
class BigQueryLoad:
    table: str
    ndjson: str
    job_id: str

    @classmethod
    def build(cls, table, rows):
        ndjson = ''.join(canonical(row) + '\n' for row in rows)
        return cls(table, ndjson, f'earthlens_{table}_{digest(ndjson)}')


class BigQueryPredictionWarehouse:
    @staticmethod
    def historical(history):
        history_id = digest(asdict(history))
        metadata = {**asdict(history.key), 'history_id': history_id, 'product': history.product,
                    'provenance': history.provenance}
        return history_id, BigQueryLoad.build('historical_series', (
            {**metadata, 'observed_at': stamp, 'value': value} for stamp, value in history.observations))

    @staticmethod
    def publication(*, version_id, run_id, published_at, batch, history_id=None):
        published_at = timestamp(published_at).isoformat()
        first, last = batch.historical_period or (None, None)
        if (history_id is None) != (first is None):
            raise ValueError('La versión debe identificar exactamente su snapshot histórico.')
        version = {**asdict(batch.key), 'version_id': version_id, 'run_id': run_id, 'history_id': history_id,
                   'provider': batch.provider, 'kind': batch.kind, 'model': batch.model,
                   'model_version': batch.model_version, 'generated_at': batch.generated_at,
                   'published_at': published_at, 'historical_start': first, 'historical_end': last,
                   'validation_status': batch.validation_status, 'provenance': batch.provenance,
                   'point_count': len(batch.points), 'first_target': batch.points[0].target,
                   'last_target': batch.points[-1].target}
        points = []
        for point in batch.points:
            lower, upper, level = point.interval or (None, None, None)
            points.append({'version_id': version_id, 'city_id': batch.key.city_id,
                           'variable': batch.key.variable, 'provider': batch.provider,
                           'target': point.target, 'horizon': point.horizon, 'value': point.value,
                           'interval_lower': lower, 'interval_upper': upper, 'interval_level': level,
                           'quantiles': [{'quantile': q, 'value': value} for q, value in point.quantiles]})
        # El manifiesto de la versión es el marcador de publicación y se carga último.
        return (BigQueryLoad.build('prediction_points', points),
                BigQueryLoad.build('prediction_versions', [version]))

    @staticmethod
    def run_event(*, run_id, request_key, attempt, status, event_at, provider, city_id, variable,
                  estimated_cost_micros, details, error_code=None, cloud_job_id=None, bytes_billed=None):
        return BigQueryLoad.build('prediction_runs', [{
            'run_id': run_id, 'request_key': request_key, 'attempt': attempt, 'status': status,
            'event_at': timestamp(event_at).isoformat(), 'provider': provider, 'city_id': city_id,
            'variable': variable, 'estimated_cost_micros': estimated_cost_micros, 'details': details,
            'error_code': error_code, 'cloud_job_id': cloud_job_id, 'bytes_billed': bytes_billed}])

    @staticmethod
    def backtest(*, run_id, history_id, evaluated_at, key, report):
        if key.frequency != report['frequency']:
            raise ValueError('La frecuencia del backtest no coincide con la serie.')
        return BigQueryLoad.build('prediction_backtests', (
            {**asdict(key), **row, 'run_id': run_id, 'history_id': history_id,
             'evaluated_at': timestamp(evaluated_at).isoformat(), 'method': report['method']}
            for row in report['rows']))
