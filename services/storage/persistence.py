"""Persistencia SQLite con migraciones transaccionales y consultas parametrizadas."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

MIGRATIONS=["""
CREATE TABLE users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE events(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, status TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
CREATE INDEX events_owner ON events(user_id,start);
CREATE TABLE forecast_snapshots(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, fetched_at TEXT NOT NULL, fingerprint TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(event_id,fingerprint));
CREATE TABLE assessments(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, snapshot_id TEXT REFERENCES forecast_snapshots(id) ON DELETE CASCADE, event_revision INTEGER NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE notifications(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), event_id TEXT REFERENCES events(id) ON DELETE CASCADE, dedupe_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, read_at TEXT, title TEXT NOT NULL, message TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE monitoring_runs(id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE monitoring_leases(name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE login_attempts(identity TEXT PRIMARY KEY, failures INTEGER NOT NULL, last_at TEXT NOT NULL);
"""]

def encode(value):return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))

class Store:
    def __init__(self,path):self.path=Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=15)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=15000')
        try:
            db.execute('BEGIN IMMEDIATE')
            version=db.execute('PRAGMA user_version').fetchone()[0]
            if version>len(MIGRATIONS):raise RuntimeError('Base de datos creada por una versión más reciente')
            for i in range(version,len(MIGRATIONS)):
                for statement in MIGRATIONS[i].split(';'):
                    if statement.strip():db.execute(statement)
                db.execute(f'PRAGMA user_version={i+1}')
            yield db
            db.commit()
        except BaseException:
            db.rollback();raise
        finally:db.close()
