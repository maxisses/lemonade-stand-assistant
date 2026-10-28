"""Exercise checkpoint recovery boundaries without any cluster or model calls."""
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import checkpoint


DDL = {
    'campaigns.sqlite': '''CREATE TABLE campaigns(id TEXT PRIMARY KEY,idempotency_key TEXT,
        request_identity TEXT,status TEXT,created_at REAL,document TEXT);''',
    'audience.sqlite': '''CREATE TABLE window(id INTEGER PRIMARY KEY,closes REAL,opened REAL);
        INSERT INTO window VALUES(1,0,0);
        CREATE TABLE sessions(id TEXT PRIMARY KEY,persona TEXT,created REAL,expires REAL);
        CREATE TABLE events(id INTEGER PRIMARY KEY,session TEXT,started REAL,finished REAL,outcome TEXT,latency REAL);
        CREATE TABLE profiles(id TEXT PRIMARY KEY,name TEXT,profile TEXT,options TEXT,revision INTEGER,created REAL);''',
    'provider.sqlite': '''CREATE TABLE calls(id INTEGER PRIMARY KEY,started REAL,role TEXT,
        generation INTEGER,tokens INTEGER,estimated INTEGER,status TEXT,model TEXT);
        CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT);''',
}


@contextmanager
def database(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.destination = self.root / 'destination'
        self.source.mkdir()
        self.destination.mkdir()
        for directory in (self.source, self.destination):
            for name, ddl in DDL.items():
                with database(directory / name) as db:
                    db.executescript(ddl)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self):
        return {name: base64.b64encode((self.source / name).read_bytes()).decode() for name in DDL}

    def insert_campaign(self, path, status='completed'):
        with database(path) as db:
            db.execute('INSERT INTO campaigns VALUES(?,?,?,?,?,?)', ('run-1', 'key-1', '{}', status, 1, '{}'))

    def hashes(self):
        return {name: hashlib.sha256((self.destination / name).read_bytes()).hexdigest() for name in DDL}

    def test_snapshot_includes_committed_wal(self):
        path = self.source / 'campaigns.sqlite'
        db = sqlite3.connect(path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA wal_autocheckpoint=0')
            db.execute("INSERT INTO campaigns VALUES('wal-run','key','{}','completed',1,'{}')")
            db.commit()
            self.assertTrue(Path(str(path) + '-wal').exists())
            snapshot = self.root / 'snapshot.sqlite'
            snapshot.write_bytes(checkpoint.snapshot_database(path, path.name))
            with database(snapshot) as restored:
                self.assertEqual(restored.execute('SELECT id FROM campaigns').fetchall(), [('wal-run',)])
        finally:
            db.close()

    def test_snapshot_rejects_active_campaign_and_foreign_schema(self):
        self.insert_campaign(self.source / 'campaigns.sqlite', 'running')
        with self.assertRaisesRegex(RuntimeError, 'active work'):
            checkpoint.snapshot_database(self.source / 'campaigns.sqlite', 'campaigns.sqlite')
        other = self.root / 'other.sqlite'
        with database(other) as db:
            db.execute('CREATE TABLE unrelated(id TEXT)')
        with self.assertRaisesRegex(RuntimeError, 'schema'):
            checkpoint.check_database(other, 'provider.sqlite')

    def test_restore_rejects_existing_campaign(self):
        self.insert_campaign(self.destination / 'campaigns.sqlite')
        before = self.hashes()
        with self.assertRaisesRegex(RuntimeError, 'existing evidence'):
            checkpoint.restore_databases(self.payload(), self.destination, self.destination)
        self.assertEqual(self.hashes(), before)

    def test_later_existing_evidence_leaves_every_target_unchanged(self):
        self.insert_campaign(self.source / 'campaigns.sqlite')
        with database(self.destination / 'provider.sqlite') as db:
            db.execute("INSERT INTO calls VALUES(1,1,'target',1,10,0,'completed','qwen38-27b')")
        before = self.hashes()
        with self.assertRaisesRegex(RuntimeError, 'existing evidence'):
            checkpoint.restore_databases(self.payload(), self.destination, self.destination)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(list(self.destination.glob('*.restore*')), [])

    def test_later_corrupt_payload_leaves_every_target_unchanged(self):
        self.insert_campaign(self.source / 'campaigns.sqlite')
        payload = self.payload()
        payload['provider.sqlite'] = base64.b64encode(b'not sqlite').decode()
        before = self.hashes()
        with self.assertRaises(sqlite3.DatabaseError):
            checkpoint.restore_databases(payload, self.destination, self.destination)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(list(self.destination.glob('*.restore*')), [])

    def test_provider_settings_are_not_silently_overwritten(self):
        with database(self.destination / 'provider.sqlite') as db:
            db.execute("INSERT INTO state VALUES('concurrency','2')")
        before = self.hashes()
        with self.assertRaisesRegex(RuntimeError, 'provider configuration'):
            checkpoint.restore_databases(self.payload(), self.destination, self.destination)
        self.assertEqual(self.hashes(), before)

    def test_remote_helpers_restore_into_fresh_databases(self):
        self.insert_campaign(self.source / 'campaigns.sqlite')
        with database(self.source / 'provider.sqlite') as db:
            db.execute("INSERT INTO state VALUES('concurrency','1')")
        with database(self.destination / 'provider.sqlite') as db:
            db.executemany('INSERT INTO state VALUES(?,?)', [('model', 'qwen38-27b'), ('concurrency', '1'), ('paused', '')])
        namespace = {}
        exec(checkpoint.remote_helpers(), namespace)
        namespace['restore_databases'](self.payload(), self.destination, self.destination)
        with database(self.destination / 'campaigns.sqlite') as db:
            self.assertEqual(db.execute('SELECT id FROM campaigns').fetchall(), [('run-1',)])
        for name in DDL:
            checkpoint.check_database(self.destination / name, name)
            self.assertEqual((self.destination / name).stat().st_mode & 0o777, 0o600)

    def test_manifest_checksum_catches_corruption(self):
        manifest = {'databases': {name: {'sha256': hashlib.sha256((self.source / name).read_bytes()).hexdigest()} for name in DDL}}
        (self.source / 'manifest.json').write_text(json.dumps(manifest))
        checkpoint.verify(self.source)
        with (self.source / 'audience.sqlite').open('ab') as output:
            output.write(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            checkpoint.verify(self.source)

    def test_quiescence_requires_zero_replicas_and_no_terminating_pods(self):
        deployment = {'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': 'entry'}}}}
        with patch.object(checkpoint, 'oc', return_value=json.dumps(deployment).encode()):
            with self.assertRaisesRegex(RuntimeError, 'zero'):
                checkpoint.require_stopped(('entry',))
        deployment['spec']['replicas'] = 0
        with patch.object(checkpoint, 'oc', side_effect=[json.dumps(deployment).encode(), b'{"items":[{"metadata":{"deletionTimestamp":"now"}}]}']):
            with self.assertRaisesRegex(RuntimeError, 'terminate'):
                checkpoint.require_stopped(('entry',))


if __name__ == '__main__':
    unittest.main()
