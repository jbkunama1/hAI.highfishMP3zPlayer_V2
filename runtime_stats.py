"""Service statistics in the existing application SQLite database."""
import atexit
import copy
import fcntl
import json
import logging
import math
import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

LOG = logging.getLogger('mp3z.stats')
COUNTERS = ('starts', 'index_runs', 'index_successes', 'index_failures')


class Stats:
    def __init__(self, filename, clock=time.monotonic):
        self.path, self.clock = Path(filename), clock
        self.lock = threading.RLock()
        self.started = clock()
        self.stop = threading.Event()
        self.closed = False
        self.writer = None
        self.persistent = False
        self.data = dict(version=1, uptime_seconds=0, since=time.time(), last_index=None, **dict.fromkeys(COUNTERS, 0))
        try:
            # Lock the existing database inode; no separate directory or lock file.
            self.writer = open(self.path, 'rb')
            fcntl.flock(self.writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with closing(self.connect()) as db:
                with db:
                    db.execute('CREATE TABLE IF NOT EXISTS mp3z_runtime_stats (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)')
                row = db.execute('SELECT data FROM mp3z_runtime_stats WHERE id=1').fetchone()
            raw = row[0] if row else None
            legacy = os.getenv('MP3Z_STATS_PATH', '')
            if raw is None and legacy and Path(legacy).resolve() != self.path.resolve():
                try:
                    old = Path(legacy)
                    if old.is_file() and old.stat().st_size <= 65536:
                        raw = old.read_text(encoding='utf-8')
                except OSError:
                    LOG.warning('Legacy statistics unavailable; database remains usable')
            if raw is not None:
                try:
                    if len(raw) > 65536: raise ValueError()
                    loaded = json.loads(raw)
                    self.validate(loaded)
                    self.data = {k: loaded[k] for k in self.data}
                    if self.data['last_index'] is not None:
                        self.data['last_index'] = {k: self.data['last_index'][k] for k in ('at', 'duration', 'files', 'bytes')}
                except (ValueError, TypeError, KeyError):
                    LOG.warning('Invalid statistics row ignored; other database tables unchanged')
            self.persistent = True
        except (OSError, sqlite3.Error, ValueError, TypeError):
            LOG.warning('Statistics persistence unavailable; using session-only counters')
        pending = max(0, self.data['index_runs']-self.data['index_successes']-self.data['index_failures'])
        self.data['index_failures'] += pending
        self.base = self.data['uptime_seconds']
        self.data['starts'] += 1
        self.save()

    def connect(self):
        return sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw', uri=True, timeout=10)

    @staticmethod
    def validate(data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError()
        for key in (*COUNTERS, 'uptime_seconds', 'since'):
            value = data[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError()
            if key in COUNTERS and not isinstance(value, int):
                raise ValueError()
        last = data['last_index']
        if last is not None:
            if not isinstance(last, dict):
                raise ValueError()
            for key in ('at', 'duration', 'files'):
                value = last[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError()
            if last['bytes'] is not None and (type(last['bytes']) is not int or last['bytes'] < 0):
                raise ValueError()

    def snapshot(self):
        with self.lock:
            data = copy.deepcopy(self.data)
            data['session_seconds'] = max(0, self.clock()-self.started)
            data['uptime_seconds'] = self.base + data['session_seconds']
            data['persistent'] = self.persistent
            return data

    def save(self):
        with self.lock:
            if not self.persistent or self.closed:
                return
            try:
                data = self.snapshot()
                data.pop('session_seconds'); data.pop('persistent')
                raw = json.dumps(data, allow_nan=False)
                with closing(self.connect()) as db:
                    with db:
                        db.execute('INSERT INTO mp3z_runtime_stats(id,data) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (raw,))
            except (OSError, sqlite3.Error, ValueError, TypeError):
                self.persistent = False
                LOG.warning('Statistics checkpoint failed; persistence disabled for this process')

    def record(self, key, last=None):
        with self.lock:
            self.data[key] += 1
            if last is not None:
                self.data['last_index'] = last
            self.save()

    def close(self):
        with self.lock:
            if self.closed: return
            self.stop.set(); self.save(); self.closed = True
            if self.writer:
                self.writer.close()

    def run(self):
        while not self.stop.wait(60):
            self.save()


def install(backend, filename):
    if hasattr(backend, 'runtime_stats'):
        return backend.runtime_stats
    stats = backend.runtime_stats = Stats(filename)
    atexit.register(stats.close)
    threading.Thread(target=stats.run, name='mp3z-stats', daemon=True).start()

    class PersistentIndex(backend.FileIndex):
        def __init__(self):
            super().__init__()
            self.scan_lock = threading.Lock()
            self.completed = False

        def _build(self):
            if not self.scan_lock.acquire(blocking=False): return
            self._building = True
            started = time.monotonic()
            stats.record('index_runs')
            try:
                storage = backend.STORAGE
                ok, _ = storage.check()
                if not ok: raise OSError('Storage unavailable')
                def fail(error): raise error
                if storage.mode == 'local':
                    root = storage.root.resolve()
                    walks = os.walk(root, onerror=fail)
                else:
                    storage._login()
                    root = storage._unc('')
                    walks = storage.sc.walk(root, onerror=fail)
                result, total, complete = [], 0, True
                for raw, dirs, names in walks:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    folder = os.path.relpath(raw, root).replace(os.sep, '/') if storage.mode == 'local' else raw[len(root):].lstrip(chr(92)).replace(chr(92), '/')
                    if folder == '.': folder = ''
                    for name in names:
                        if name.startswith('.') or Path(name).suffix.lower() not in backend.AUDIO_EXTS: continue
                        rel = backend._join(folder, name)
                        result.append(dict(name=name, path=rel, dir=folder or '/'))
                        try:
                            size = storage.size(rel)
                            if type(size) is not int or size < 0: raise ValueError()
                            total += size
                        except Exception: complete = False
                last = dict(at=time.time(), duration=max(0,time.monotonic()-started), files=len(result), bytes=total if complete else None)
                with self._lock:
                    self._entries = result
                    self._built = time.time()
                    self.completed = True
                stats.record('index_successes', last)
            except Exception:
                stats.record('index_failures')
                self._built = time.time()-backend.INDEX_TTL+60
                LOG.warning('Index failed; keeping previous successful snapshot')
            finally:
                self._building = False
                self.scan_lock.release()

    backend.index = PersistentIndex()
    original_status = backend.app.view_functions['index_status']
    def index_status_with_stats():
        response = backend.app.make_response(original_status.__wrapped__())
        data = response.get_json()
        data['stats'] = stats.snapshot()
        data['stats']['snapshot_source'] = 'current' if backend.index.completed else 'saved'
        response.set_data(backend.app.json.dumps(data))
        response.headers['Cache-Control'] = 'no-store'
        return response
    backend.app.view_functions['index_status'] = backend.require_auth(index_status_with_stats)
    return stats
