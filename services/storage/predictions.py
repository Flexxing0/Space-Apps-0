"""Proyección SQLite local y contratos separados de lectura y preparación."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3
from typing import Protocol
from uuid import uuid4

from services.prediction.contracts import PredictionBatch, canonical, timestamp
from services.providers.cache import utc_now


class PredictionReader(Protocol):
    def lookup(self, *, city_id, variable, frequency, provider, start, end, version_id=None): ...


@dataclass(frozen=True)
class RunClaim:
    status: str
    run_id: str | None = None
    version_id: str | None = None


class PredictionStore(PredictionReader, Protocol):
    def claim(self, request_key, details, *, estimated_cost_micros, daily_budget_micros, retry_failed) -> RunClaim: ...
    def publish(self, run_id, batch: PredictionBatch): ...
    def fail(self, run_id, error_code): ...


SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS prediction_runs (
    id TEXT PRIMARY KEY, request_key TEXT NOT NULL, attempt INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
    started_at TEXT NOT NULL, finished_at TEXT, error_code TEXT,
    estimated_cost_micros INTEGER NOT NULL CHECK(estimated_cost_micros>=0), details TEXT NOT NULL,
    UNIQUE(request_key, attempt)
);
CREATE INDEX IF NOT EXISTS prediction_runs_by_day ON prediction_runs(started_at);
CREATE TABLE IF NOT EXISTS prediction_versions (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES prediction_runs(id),
    city_id TEXT NOT NULL, variable TEXT NOT NULL, frequency TEXT NOT NULL,
    provider TEXT NOT NULL, published_at TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS prediction_version_selection
ON prediction_versions(city_id, variable, frequency, provider, published_at DESC, id DESC);
CREATE TABLE IF NOT EXISTS prediction_points (
    version_id TEXT NOT NULL REFERENCES prediction_versions(id),
    target TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(version_id, target)
);
COMMIT;
"""


class SQLitePredictions:
    def __init__(self, path, clock=utc_now):
        self.path = Path(path).resolve()
        self.clock = clock

    @contextmanager
    def _write(self, *, initialize=False):
        if initialize:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            if initialize:
                db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        finally:
            db.close()

    def claim(self, request_key, details, *, estimated_cost_micros, daily_budget_micros, retry_failed=False):
        with self._write(initialize=True) as db:
            previous = db.execute(
                'SELECT id, attempt, status FROM prediction_runs WHERE request_key=? ORDER BY attempt DESC LIMIT 1',
                (request_key,)).fetchone()
            if previous and previous['status'] == 'completed':
                return RunClaim('reused', previous['id'], request_key)
            if previous and (previous['status'] == 'running' or not retry_failed):
                return RunClaim('in_progress' if previous['status'] == 'running' else 'failed', previous['id'])
            stamp = timestamp(self.clock()).isoformat()
            reserved = db.execute(
                'SELECT COALESCE(SUM(estimated_cost_micros), 0) FROM prediction_runs WHERE started_at BETWEEN ? AND ?',
                (stamp[:10] + 'T', stamp[:10] + 'U')).fetchone()[0]
            if reserved + estimated_cost_micros > daily_budget_micros:
                return RunClaim('budget_exceeded')
            run_id = uuid4().hex
            db.execute(
                '''INSERT INTO prediction_runs
                   (id,request_key,attempt,status,started_at,estimated_cost_micros,details)
                   VALUES (?,?,?,'running',?,?,?)''',
                (run_id, request_key, previous['attempt'] + 1 if previous else 1, stamp,
                 estimated_cost_micros, canonical(details)))
            return RunClaim('claimed', run_id)

    def publish(self, run_id, batch):
        metadata = asdict(batch)
        points = metadata.pop('points')
        with self._write() as db:
            run = db.execute('SELECT request_key FROM prediction_runs WHERE id=? AND status=?',
                             (run_id, 'running')).fetchone()
            if run is None:
                raise ValueError('La ejecución no está activa.')
            version_id, stamp = run['request_key'], timestamp(self.clock()).isoformat()
            key = batch.key
            db.execute('INSERT INTO prediction_versions VALUES (?,?,?,?,?,?,?,?)',
                       (version_id, run_id, key.city_id, key.variable, key.frequency,
                        batch.provider, stamp, canonical(metadata)))
            db.executemany('INSERT INTO prediction_points VALUES (?,?,?)',
                           ((version_id, point['target'], canonical(point)) for point in points))
            db.execute("UPDATE prediction_runs SET status='completed',finished_at=? WHERE id=?", (stamp, run_id))
        return version_id

    def fail(self, run_id, error_code):
        with self._write() as db:
            db.execute("""UPDATE prediction_runs SET status='failed',finished_at=?,error_code=?
                          WHERE id=? AND status='running'""", (timestamp(self.clock()).isoformat(), error_code, run_id))

    def lookup(self, *, city_id, variable, frequency, provider, start, end, version_id=None):
        try:
            db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5)
        except sqlite3.OperationalError:
            if not self.path.exists():
                return None
            raise
        db.row_factory = sqlite3.Row
        try:
            # A new file may exist before its first schema transaction commits.
            db.execute('BEGIN')
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='prediction_versions'").fetchone():
                return None
            query = ('SELECT id, run_id, published_at, metadata FROM prediction_versions '
                     'WHERE city_id=? AND variable=? AND frequency=? AND provider=?')
            args = (city_id, variable, frequency, provider)
            if version_id is not None:
                query += ' AND id=?'
                args += (version_id,)
            version = db.execute(query + ' ORDER BY published_at DESC, id DESC LIMIT 1', args).fetchone()
            if version is None:
                return None
            points = db.execute(
                '''SELECT body FROM prediction_points
                   WHERE version_id=? AND target BETWEEN ? AND ? ORDER BY target''',
                (version['id'], start + 'T', end + 'U'))
            return {**json.loads(version['metadata']), 'version_id': version['id'],
                    'run_id': version['run_id'], 'published_at': version['published_at'],
                    'points': [json.loads(p['body']) for p in points]}
        finally:
            db.close()
