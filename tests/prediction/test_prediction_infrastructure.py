"""Fixtures de software. Ninguna observación, credencial ni consulta real."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock, patch

from app import create_app
from services.geography.cities import get_city
from services.prediction.contracts import HistoricalSeries, PredictionPlan, PredictionPoint, SeriesKey
from services.prediction.job import JobLimits, PredictionJob
from services.prediction.prediction import backtest_daily
from services.prediction.providers import BigQueryTimesFM, MonthlyClimatology, OpenMeteoProvider, SeasonalBaseline
from services.storage.prediction_bigquery import BigQueryPredictionWarehouse
from services.storage.predictions import SQLitePredictions


CITY = get_city('mendoza')
KEY = SeriesKey(CITY['id'], CITY['latitude'], CITY['longitude'], 'T2M', 'C', 'daily')
STAMP = '2026-11-21T12:00:00+00:00'


def daily_plan(revision='fixture-v1', initial_value=0):
    start = date(2024, 2, 24)
    history = HistoricalSeries(KEY, 'SOFTWARE_TEST_ONLY',
                               tuple(((start + timedelta(days=i)).isoformat(), initial_value + i) for i in range(9)),
                               {'software_test_only': True})
    return PredictionPlan(KEY, '2024-03-04', 3, revision, history)


class PredictionContractsTests(unittest.TestCase):
    def test_history_rejects_invalid_values_dates_and_duplicate_utc_stamps(self):
        cases = (
            (('2024-02-29', True),),
            (('2024-02-29', float('nan')),),
            (('2024-02-29', 10**500),),
            (('2024-02-29T00:00:00', 0),),
            (('2024-02-29', 0), ('2024-02-28T21:00:00-03:00', 1)),
            (('2024-02-29', 0), ('2024-02-28', 1)),
        )
        for observations in cases:
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                HistoricalSeries(KEY, 'fixture', observations, {'test': True})

    def test_snapshot_preserves_null_and_gap_but_baseline_rejects_them(self):
        plan = daily_plan()
        for observations in (plan.history.observations[1:2] + plan.history.observations[3:],
                             (*plan.history.observations[:-1], (plan.history.period[1], None))):
            with self.subTest(observations=observations):
                history = replace(plan.history, observations=observations)
                with self.assertRaises(ValueError):
                    SeasonalBaseline().produce(replace(plan, history=history))

    def test_interval_and_quantile_validation(self):
        point = PredictionPoint('2024-02-29', 1, 0, (-2, 2, .95), ((.05, -1), (.95, 1)))
        self.assertEqual(point.value, 0)
        for kwargs in ({'interval': (2, -2, .95)}, {'interval': (-2, 2, 1)},
                       {'quantiles': ((.1, 2), (.9, -2))}, {'quantiles': ((.1, 0), (.1, 1))}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PredictionPoint('2024-02-29', 1, 0, **kwargs)

    def test_baseline_reuses_backtest_method_and_rejects_skipped_first_step(self):
        plan = daily_plan()
        batch = SeasonalBaseline().produce(plan)
        self.assertEqual([p.value for p in batch.points], [2, 3, 4])
        self.assertEqual(batch.historical_period, plan.history.period)
        self.assertEqual(batch.validation_status, 'not_validated')
        self.assertIsNone(batch.points[0].interval)
        with self.assertRaises(ValueError):
            SeasonalBaseline().produce(replace(plan, first_target='2024-03-05'))

    def test_climatology_is_a_reference_with_no_bands_and_preserves_missing_months(self):
        key = replace(KEY, frequency='monthly')
        history = HistoricalSeries(key, 'fixture',
                                   (('2022-01-01', 0), ('2023-01-01', 2), ('2023-02-01', None)), {'test': True})
        batch = MonthlyClimatology().produce(PredictionPlan(key, '2025-01-01', 2, '1', history))
        self.assertEqual((batch.kind, batch.validation_status), ('climatology_reference', 'reference_only'))
        self.assertEqual([p.value for p in batch.points], [1, None])
        self.assertTrue(all(p.interval is None and not p.quantiles for p in batch.points))

    def test_open_meteo_adapter_preserves_native_metadata_and_does_not_invent_issuance(self):
        key = replace(KEY, frequency='hourly', variable='temperature_2m', unit='°C')
        weather = Mock()
        weather.series.return_value = {
            'provider': 'Open-Meteo', 'product': 'best_match', 'location': CITY,
            'unit': key.unit, 'frequency': key.frequency, 'variable': key.variable,
            'kind': 'forecast', 'issued_at': None, 'issuance_status': 'not_provided_by_endpoint',
            'provenance': {'software_test_only': True}, 'fetched_at': STAMP,
            'series': [{'date': STAMP, 'value': 0}, {'date': '2026-11-21T13:00:00Z', 'value': None}]}
        plan = PredictionPlan(key, STAMP, 2, 'slot-fixture')
        batch = OpenMeteoProvider(weather).produce(plan)
        weather.series.assert_called_once_with('mendoza', kind='forecast', variable='temperature_2m',
                                              start='2026-11-21', end='2026-11-21')
        self.assertEqual(batch.kind, 'operational_forecast')
        self.assertIsNone(batch.generated_at)
        self.assertIsNone(batch.model_version)
        self.assertEqual(batch.provenance['fetched_at'], STAMP)
        self.assertEqual([p.value for p in batch.points], [0, None])
        weather.series.return_value['unit'] = 'K'
        with self.assertRaises(ValueError):
            OpenMeteoProvider(weather).produce(plan)


class PredictionStorageTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / 'runtime' / 'predictions.sqlite3'
        self.store = SQLitePredictions(self.path)
        self.job = PredictionJob(self.store, enabled=True)
        self.app = create_app({'TESTING': True, 'CACHE_DIR': Path(directory) / 'power',
                               'PREDICTION_DATABASE_PATH': self.path})
        self.client = self.app.test_client()

    def query(self, **kwargs):
        return self.client.get('/api/predictions', query_string={
            'city_id': 'mendoza', 'variable': 'T2M', 'start': '2024-03-04', 'end': '2024-03-04', **kwargs})

    def test_absence_does_not_create_database_or_invoke_inference(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('Network')), \
                patch.object(BigQueryTimesFM, 'produce', side_effect=AssertionError('Inference')), \
                patch.object(PredictionJob, 'run', side_effect=AssertionError('Run')):
            response = self.query()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['data']['reason'], 'no_saved_version')
        self.assertIsNone(response.json['data']['result'])
        self.assertFalse(self.path.parent.exists())
        self.assertEqual(self.query(city_id='paris').status_code, 404)
        self.assertEqual(self.query(frequency='hourly', end='2024-09-04').status_code, 400)
        self.assertEqual(self.query(version_id='invalid').status_code, 400)
        self.assertEqual(self.client.post('/api/predictions').status_code, 405)

    def test_duplicate_lock_blocks_concurrent_inference_and_reuses_version(self):
        entered, release = Event(), Event()
        baseline = SeasonalBaseline()
        plan = daily_plan()
        original = baseline.produce

        def delayed(request):
            entered.set()
            if not release.wait(5):
                raise TimeoutError()
            return original(request)

        with patch.object(baseline, 'produce', side_effect=delayed) as produce, ThreadPoolExecutor() as executor:
            initial = executor.submit(self.job.run, baseline, plan, estimated_cost_micros=0)
            try:
                self.assertTrue(entered.wait(5))
                duplicate = self.job.run(baseline, plan, estimated_cost_micros=0)
                self.assertEqual(duplicate.status, 'in_progress')
                self.assertEqual(self.query(provider=baseline.name).json['data']['reason'], 'no_saved_version')
            finally:
                release.set()
            finished = initial.result(timeout=5)
            reused = self.job.run(baseline, plan, estimated_cost_micros=0)
        self.assertEqual(finished.status, 'completed')
        self.assertEqual((reused.status, reused.version_id), ('reused', finished.version_id))
        produce.assert_called_once()

    def test_versioning_and_http_do_not_mix_executions_or_infer(self):
        provider = SeasonalBaseline()
        first = self.job.run(provider, daily_plan(), estimated_cost_micros=0)
        latest = self.job.run(provider, daily_plan(initial_value=100), estimated_cost_micros=0)
        self.assertNotEqual(first.version_id, latest.version_id)
        with patch.object(SeasonalBaseline, 'produce', side_effect=AssertionError('Inference')):
            response = self.query(provider=provider.name)
            old = self.query(provider=provider.name, version_id=first.version_id)
            outside = self.query(provider=provider.name, start='2024-03-03', end='2024-03-03')
        new_data, old_data = response.json['data']['result'], old.json['data']['result']
        self.assertEqual((new_data['version_id'], new_data['points'][0]['value']), (latest.version_id, 102))
        self.assertEqual((old_data['version_id'], old_data['points'][0]['value']), (first.version_id, 2))
        self.assertEqual(outside.json['data']['reason'], 'no_points_in_range')

    def test_missing_reference_value_is_returned_as_null(self):
        key = replace(KEY, frequency='monthly')
        history = HistoricalSeries(key, 'fixture', (('2023-01-01', 0),), {'test': True})
        plan = PredictionPlan(key, '2024-02-01', 1, '1', history)
        self.job.run(MonthlyClimatology(), plan, estimated_cost_micros=0)
        payload = self.query(start='2024-02-01', end='2024-02-29',
                             provider='climatology', frequency='monthly').json['data']
        self.assertEqual((payload['status'], payload['reason']), ('unavailable', 'no_valid_values'))
        self.assertEqual(payload['result']['kind'], 'climatology_reference')
        self.assertIsNone(payload['result']['points'][0]['value'])

    def test_disabled_limits_budget_and_failure_recovery(self):
        provider = SeasonalBaseline()
        plan = daily_plan()
        self.assertEqual(PredictionJob(self.store).run(provider, plan, estimated_cost_micros=0).status, 'disabled')
        self.assertEqual(self.job.run(BigQueryTimesFM(), plan, estimated_cost_micros=0).status, 'disabled')
        self.assertFalse(self.path.exists())
        with self.assertRaises(RuntimeError):
            BigQueryTimesFM().produce(plan)
        with self.assertRaises(ValueError):
            self.job.run(provider, replace(plan, steps=169), estimated_cost_micros=0)
        self.assertEqual(self.job.run(provider, plan, estimated_cost_micros=1).status, 'budget_exceeded')
        budgeted = PredictionJob(self.store, enabled=True, limits=JobLimits(daily_budget_micros=3))
        with patch.object(provider, 'produce', side_effect=ValueError('private diagnostics')):
            with self.assertRaises(ValueError):
                budgeted.run(provider, plan, estimated_cost_micros=2)
            self.assertEqual(budgeted.run(provider, plan, estimated_cost_micros=0).status, 'failed')
        self.assertEqual(budgeted.run(provider, plan, estimated_cost_micros=2, retry_failed=True).status, 'budget_exceeded')
        self.assertEqual(budgeted.run(provider, plan, estimated_cost_micros=1, retry_failed=True).status, 'completed')
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        rows = connection.execute('SELECT attempt,status,error_code FROM prediction_runs ORDER BY attempt').fetchall()
        self.assertEqual(rows, [(1, 'failed', 'ValueError'), (2, 'completed', None)])


class BigQueryArtifactTests(unittest.TestCase):
    def test_artifacts_match_ddl_fields_without_a_cloud_client(self):
        warehouse = BigQueryPredictionWarehouse()
        plan = daily_plan()
        history_id, history_load = warehouse.historical(plan.history)
        batch = SeasonalBaseline().produce(plan)
        publication = dict(version_id='version', run_id='run', published_at=STAMP, batch=batch, history_id=history_id)
        point_load, version_load = warehouse.publication(**publication)
        self.assertEqual(warehouse.publication(**publication), (point_load, version_load))
        self.assertEqual([point_load.table, version_load.table], ['prediction_points', 'prediction_versions'])
        run_load = warehouse.run_event(run_id='run', request_key='request', attempt=1, status='completed',
                                       event_at=STAMP, provider=batch.provider, city_id=KEY.city_id, variable=KEY.variable,
                                       estimated_cost_micros=0, details={'software_test_only': True})
        report = backtest_daily([{'date': d[:10], 'value': v} for d, v in plan.history.observations], [7], horizons=(1, 2))
        backtest_load = warehouse.backtest(run_id='run', history_id=history_id, evaluated_at=STAMP, key=KEY, report=report)
        ddl = (Path(__file__).resolve().parents[2] / 'deployment' / 'bigquery' / '001_prediction_tables.sql').read_text()
        for load in (history_load, point_load, version_load, run_load, backtest_load):
            with self.subTest(table=load.table):
                fields = re.search(rf'\.{load.table}` \(\n(.*?)\n\)', ddl, re.S)[1]
                expected = {line.strip().split()[0] for line in fields.splitlines()}
                rows = [json.loads(line) for line in load.ndjson.splitlines()]
                self.assertTrue(rows)
                for row in rows:
                    self.assertEqual(set(row), expected)
        self.assertIsNone(json.loads(point_load.ndjson.splitlines()[0])['interval_level'])
        self.assertIsNone(json.loads(backtest_load.ndjson.splitlines()[0])['interval_coverage'])
