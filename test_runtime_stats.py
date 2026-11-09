import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from runtime_stats import Stats


def database(path):
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute('CREATE TABLE playlists(id TEXT PRIMARY KEY,data TEXT)')
            db.execute('INSERT INTO playlists VALUES (?,?)', ('keep','unchanged'))


class StatsTests(unittest.TestCase):
    def test_restart_and_shared_db(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'playlists.sqlite3'; database(p); clock=[0]
            a=Stats(p,clock=lambda:clock[0]); clock[0]=120
            a.save(); a.save(); a.record('index_runs'); a.close(); a.close()
            clock[0]=1000; b=Stats(p,clock=lambda:clock[0])
            self.assertEqual(b.snapshot()['uptime_seconds'],120)
            self.assertEqual(b.snapshot()['starts'],2)
            self.assertEqual(b.snapshot()['index_failures'],1)
            c=Stats(p); self.assertFalse(c.persistent); c.close()
            with closing(sqlite3.connect(p)) as db:
                self.assertEqual(db.execute('SELECT data FROM playlists').fetchone()[0],'unchanged')
                with db: db.execute('INSERT INTO playlists VALUES (?,?)', ('new','allowed'))
            b.close()
            self.assertEqual([x.name for x in Path(d).iterdir()],['playlists.sqlite3'])
    def test_corrupt_row_does_not_replace_database(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'playlists.sqlite3'; database(p)
            a=Stats(p); a.close()
            with closing(sqlite3.connect(p)) as db:
                with db: db.execute("UPDATE mp3z_runtime_stats SET data='{bad' WHERE id=1")
            b=Stats(p); self.assertTrue(b.persistent); b.close()
            with closing(sqlite3.connect(p)) as db:
                self.assertEqual(db.execute('SELECT data FROM playlists').fetchone()[0],'unchanged')
    def test_legacy_import_once(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'playlists.sqlite3'; database(p); old=Path(d)/'old.json'
            old.write_text(json.dumps(dict(version=1,uptime_seconds=3600,since=1,last_index=None,starts=5,index_runs=0,index_successes=0,index_failures=0)))
            with patch.dict('os.environ',{'MP3Z_STATS_PATH':str(old)}):
                a=Stats(p); self.assertEqual(a.snapshot()['starts'],6); a.close()
                b=Stats(p); self.assertEqual(b.snapshot()['starts'],7); b.close()
            self.assertTrue(old.exists())
    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'missing.sqlite3'; a=Stats(p)
            self.assertFalse(a.persistent); a.close(); self.assertFalse(p.exists())


if __name__=='__main__': unittest.main()
