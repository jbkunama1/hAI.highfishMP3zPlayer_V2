"""MP3 ID3 editing shared by REST and MCP. Single-process writer."""
import hashlib
import io
import os
import secrets
import shutil
import stat
import threading
import uuid
from pathlib import Path
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TPE2, TRCK, TPOS, TDRC, TCON

FIELDS = dict(title=TIT2, artist=TPE1, album=TALB, album_artist=TPE2,
              track=TRCK, disc=TPOS, year=TDRC, genre=TCON)
LIMIT = 128 * 1024 * 1024
LOCK = threading.RLock()


def enabled(name):
    return os.getenv(name, '').lower() in ('true', '1', 'yes')


class MetadataService:
    def __init__(self, storage):
        self.s = storage

    def path(self, value):
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError('Invalid path')
        rel = value.replace(chr(92), '/')
        parts = rel.split('/')
        if not rel or any(not p or p.startswith('.') or ':' in p or chr(0) in p for p in parts):
            raise ValueError('Only visible relative paths allowed')
        if Path(rel).suffix.lower() != '.mp3':
            raise ValueError('Only MP3 ID3 editing is supported')
        if self.s.mode == 'local':
            self.s._full(rel)
            cur = self.s.root.resolve()
            for part in parts:
                cur = cur / part
                if cur.is_symlink():
                    raise ValueError('Symlinks not allowed')
        else:
            self.s._login()
            cur = ''
            for part in parts:
                cur = (cur + '/' + part).lstrip('/')
                info = self.s.sc.lstat(self.s._unc(cur), port=self.s.port)
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('SMB links/reparse points not allowed')
        return rel

    def read_bytes(self, rel):
        if self.s.mode == 'local':
            size = self.s.size(rel)
            handle = lambda: self.s.open(rel)
        else:
            self.s._login()
            size = self.s.sc.stat(self.s._unc(rel), port=self.s.port).st_size
            handle = lambda: self.s.sc.open_file(self.s._unc(rel), mode='rb', port=self.s.port)
        if size > LIMIT:
            raise ValueError('Editing limit: 128 MiB')
        with handle() as src:
            data = src.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError('Editing limit: 128 MiB')
        return data

    def decode(self, rel, data):
        try:
            tags = ID3(io.BytesIO(data))
        except ID3NoHeaderError:
            tags = ID3()
        return {'path': rel, 'revision': hashlib.sha256(data).hexdigest(),
                'tags': {name: str(tags.get(cls.__name__, '')) for name, cls in FIELDS.items()}}

    def read(self, path):
        with LOCK:
            rel = self.path(path)
            return self.decode(rel, self.read_bytes(rel))

    def update(self, path, changes, revision):
        if not enabled('EDIT_ENABLED'):
            raise PermissionError('Set EDIT_ENABLED=true to enable writes')
        if not isinstance(changes, dict) or not changes or set(changes) - set(FIELDS):
            raise ValueError('Unknown or empty tag fields')
        if any(not isinstance(v, str) or len(v) > 2000 or chr(0) in v for v in changes.values()):
            raise ValueError('Tag values must be strings, max 2000 characters')
        if not isinstance(revision, str) or len(revision) != 64 or any(c not in '0123456789abcdef' for c in revision):
            raise ValueError('Revision required')
        with LOCK:
            rel = self.path(path)
            original = self.read_bytes(rel)
            if not secrets.compare_digest(hashlib.sha256(original).hexdigest(), revision):
                raise ValueError('Stale revision: reload tags')
            buffer = io.BytesIO(original)
            try:
                tags = ID3(buffer)
            except ID3NoHeaderError:
                tags = ID3()
            for name, value in changes.items():
                cls = FIELDS[name]
                tags.delall(cls.__name__)
                if value:
                    tags.add(cls(encoding=3, text=[value]))
            tags.save(buffer, v2_version=4)
            data = buffer.getvalue()
            folder, _, name = rel.rpartition('/')
            prefix = (folder + '/') if folder else ''
            ident = uuid.uuid4().hex
            backup = prefix + '.mp3z-' + ident + '-' + name + '.bak'
            temp = prefix + '.mp3z-' + ident + '.tmp'
            if self.s.mode == 'local':
                dst, tmp = self.s._full(rel), self.s._full(temp)
                try:
                    with open(tmp, 'xb') as out:
                        out.write(data)
                        out.flush()
                        os.fsync(out.fileno())
                    shutil.copy2(dst, self.s._full(backup))
                    shutil.copymode(dst, tmp)
                    os.replace(tmp, dst)
                finally:
                    tmp.unlink(missing_ok=True)
            else:
                sc, port = self.s.sc, self.s.port
                with sc.open_file(self.s._unc(backup), mode='xb', port=port) as out:
                    out.write(original)
                try:
                    with sc.open_file(self.s._unc(temp), mode='xb', port=port) as out:
                        out.write(data)
                    sc.replace(self.s._unc(temp), self.s._unc(rel), port=port)
                finally:
                    try:
                        sc.remove(self.s._unc(temp), port=port)
                    except FileNotFoundError:
                        pass
            result = self.decode(rel, data)
            result.update(ok=True, backup=backup)
            return result


class BearerAuth:
    def __init__(self, app, key):
        if not key or key != key.strip() or not key.isascii():
            raise ValueError('MCP_API_KEY must be a nonempty ASCII key without surrounding whitespace')
        self.app, self.expected = app, ('Bearer ' + key).encode()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        if not secrets.compare_digest(headers.get(b'authorization', b''), self.expected):
            await send({'type':'http.response.start', 'status':401,
                        'headers':[(b'www-authenticate', b'Bearer'), (b'cache-control', b'no-store')]})
            return await send({'type':'http.response.body', 'body':b'Unauthorized'})
        return await self.app(scope, receive, send)
