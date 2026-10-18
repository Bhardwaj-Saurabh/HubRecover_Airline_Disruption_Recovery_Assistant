"""Single-process SQLite ledger; every consequential mutation uses BEGIN IMMEDIATE."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from .jobs import enqueue


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS commands(run_id TEXT, key TEXT, hash TEXT, PRIMARY KEY(run_id,key));
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, generation INTEGER NOT NULL,
                stage TEXT NOT NULL, status TEXT NOT NULL, fence INTEGER NOT NULL, lease_until REAL NOT NULL,
                attempts INTEGER NOT NULL, error TEXT);
            ''')
            db.execute('INSERT OR IGNORE INTO control VALUES(1,?)', (json.dumps(dict(
                mode='SYNTHETIC', writes_enabled=True, version=1, history=[])),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def load(self, db, run_id):
        row = db.execute('SELECT body FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError('Unknown run')
        return json.loads(row['body'])

    def save(self, db, run):
        enqueue(db,run)
        for snapshot in run.get('snapshots',[]):
            if 'content' in snapshot:
                db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?,?)',
                           (snapshot['id'],run['id'],json.dumps(snapshot)))
                del snapshot['content']
        db.execute('INSERT INTO runs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                   (run['id'], json.dumps(run, separators=(',', ':'))))

    def control(self, db):
        return json.loads(db.execute('SELECT body FROM control WHERE id=1').fetchone()['body'])
