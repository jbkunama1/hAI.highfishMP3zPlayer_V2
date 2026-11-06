#!/usr/bin/env python3
"""
MP3z Samba Player Backend
hAI.highfishMP3zPlayer by TheRealTeacher / Highfish AI

Musikquelle per ENV:
  STORAGE_MODE=local  -> MUSIC_ROOT (lokales/gemountetes Verzeichnis)
  STORAGE_MODE=smb    -> SMB_HOST, SMB_SHARE, [SMB_PATH], SMB_USER, SMB_PASS,
                         [SMB_DOMAIN], [SMB_PORT], [SMB_ENCRYPT]

Start:
  python3 mp3z_server.py
"""

import os, re, io, time, mimetypes, threading, secrets, hashlib
from pathlib import Path
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, send_file, abort
from flask_cors import CORS

load_dotenv(Path(__file__).parent / '.env')


def _env_bool(name, default=False):
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return v.strip().lower() in ('1', 'true', 'yes', 'on', 'ja')


# ── KONFIGURATION ────────────────────────────────────────────────────────────
STORAGE_MODE = (os.getenv('STORAGE_MODE', 'local') or 'local').strip().lower()
MUSIC_ROOT   = Path(os.getenv('MUSIC_ROOT', '/mnt/USBHDD_MP3z'))
HOST         = os.getenv('HOST', '0.0.0.0')
PORT         = int(os.getenv('PORT', '80'))
SMB_USER     = os.getenv('SMB_USER', 'user')
SMB_PASS     = os.getenv('SMB_PASS', '')
SMB_HOST     = os.getenv('SMB_HOST', '').strip()
SMB_SHARE    = os.getenv('SMB_SHARE', '').strip().strip('/\\')
SMB_PATH     = os.getenv('SMB_PATH', '')
SMB_DOMAIN   = os.getenv('SMB_DOMAIN', '').strip()
SMB_PORT     = int(os.getenv('SMB_PORT', '445') or 445)
SMB_ENCRYPT  = _env_bool('SMB_ENCRYPT')
API_KEY      = os.getenv('API_KEY_OVERRIDE') or SMB_PASS
DEFAULT_URL  = os.getenv('DEFAULT_URL', 'http://localhost')

if not API_KEY:
    print('⚠  Kein API-Key gesetzt (API_KEY_OVERRIDE oder SMB_PASS)!')
elif STORAGE_MODE == 'smb' and not os.getenv('API_KEY_OVERRIDE'):
    print('⚠  SMB-Modus ohne API_KEY_OVERRIDE: SMB_PASS dient als Web-Key. Bitte eigenen Key setzen.')

API_KEY_HASH = hashlib.sha256(API_KEY.encode()).hexdigest()

# ── KONSTANTEN ────────────────────────────────────────────────────────────────
AUDIO_EXTS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.aac', '.opus', '.wma'}
IMG_EXTS   = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
ART_TAG_EXTS = {'.mp3', '.flac', '.m4a', '.mp4', '.aac'}
COVER_NAMES = ('cover.jpg', 'cover.jpeg', 'cover.png', 'folder.jpg', 'folder.png')
PAGE_SIZE  = 80
CHUNK_SIZE = 64 * 1024
INDEX_TTL  = 3600
MAX_COVER_BYTES = 10 * 1024 * 1024
MAX_TAG_HEAD    = 8 * 1024 * 1024
MAX_TAG_FILE    = 64 * 1024 * 1024

app = Flask(__name__)
CORS(app, origins='*')

try:
    from mutagen.id3  import ID3
    from mutagen.mp4  import MP4
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

try:
    from smbprotocol.exceptions import SMBException, SMBOSError
except ImportError:
    class SMBException(Exception): pass
    class SMBOSError(OSError): pass


# ── PFAD-HILFSFUNKTIONEN ─────────────────────────────────────────────────────
def _split_rel(rel):
    """Relativen Pfad in Segmente zerlegen. None bei Traversal/NUL."""
    rel = (rel or '').replace('\\', '/')
    parts = []
    for p in rel.split('/'):
        if p in ('', '.'):
            continue
        if p == '..' or '\x00' in p:
            return None
        parts.append(p)
    return parts


def clean_rel(rel):
    parts = _split_rel(rel)
    if parts is None:
        abort(403)
    return '/'.join(parts)


def _parent(rel):
    return rel.rsplit('/', 1)[0] if '/' in rel else ''


def _join(folder, name):
    return f'{folder}/{name}' if folder else name


# ── STORAGE: LOKAL ──────────────────────────────────────────────────────────
class LocalStorage:
    mode = 'local'

    def __init__(self, root):
        self.root = Path(root)

    def describe(self):
        return str(self.root)

    def _full(self, rel):
        root = self.root.resolve()
        full = (root / rel).resolve()
        if not full.is_relative_to(root):
            abort(403)
        return full

    def check(self):
        if self.root.is_dir():
            return True, f'{self.root} erreichbar'
        return False, f'MUSIC_ROOT nicht gefunden: {self.root}'

    def isdir(self, rel):
        return self._full(rel).is_dir()

    def isfile(self, rel):
        return self._full(rel).is_file()

    def size(self, rel):
        return self._full(rel).stat().st_size

    def listdir(self, rel):
        out = []
        with os.scandir(self._full(rel)) as it:
            for e in it:
                try:
                    d = e.is_dir()
                    out.append({'name': e.name, 'is_dir': d,
                                'size': None if d else e.stat().st_size})
                except OSError:
                    continue
        return out

    def open(self, rel):
        return open(self._full(rel), 'rb')

    def walk(self):
        root = self.root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            rd = os.path.relpath(dirpath, root).replace(os.sep, '/')
            yield ('' if rd == '.' else rd), filenames

    def mutagen_source(self, rel):
        return self._full(rel)


# ── STORAGE: SMB (direkt im Container) ──────────────────────────────────
class SmbStorage:
    mode = 'smb'

    def __init__(self, host, share, base, user, password, domain, port, encrypt):
        try:
            import smbclient
        except ImportError:
            raise SystemExit('smbprotocol fehlt: pip install smbprotocol')
        self.sc = smbclient
        self.host, self.share = host, share
        self.user, self.password = user, password
        self.domain, self.port, self.encrypt = domain, port, encrypt
        parts = _split_rel(base)
        if parts is None:
            raise SystemExit('SMB_PATH enthält ungültige Segmente (..)')
        self.base = '/'.join(parts)
        self._lock = threading.Lock()
        self._ready = False

    def describe(self):
        tail = f'/{self.base}' if self.base else ''
        return f'//{self.host}/{self.share}{tail}'

    def _login(self):
        with self._lock:
            if self._ready:
                return
            u = f'{self.domain}\\{self.user}' if self.domain else self.user
            try:
                self.sc.register_session(self.host, username=u, password=self.password,
                                         port=self.port, encrypt=self.encrypt,
                                         connection_timeout=15)
            except Exception as e:
                raise ConnectionError(f'SMB-Login fehlgeschlagen: {e}')
            self._ready = True

    def _reset(self):
        with self._lock:
            self._ready = False
            try:
                self.sc.reset_connection_cache()
            except Exception:
                pass

    def _do(self, fn):
        for attempt in (1, 2):
            self._login()
            try:
                return fn()
            except SMBOSError:
                raise
            except (SMBException, ConnectionError, TimeoutError):
                if attempt == 2:
                    raise
                self._reset()

    def _unc(self, rel):
        parts = [p for p in (self.base + '/' + rel).replace('\\', '/').split('/') if p]
        if any(':' in p for p in parts):
            abort(403)
        tail = ('\\' + '\\'.join(parts)) if parts else ''
        return f'\\\\{self.host}\\{self.share}{tail}'

    def check(self):
        try:
            n = len(self.listdir(''))
            return True, f'{self.describe()} erreichbar ({n} Einträge im Root)'
        except Exception as e:
            return False, f'SMB nicht erreichbar: {e}'

    def isdir(self, rel):
        return self._do(lambda: self.sc.path.isdir(self._unc(rel)))

    def isfile(self, rel):
        return self._do(lambda: self.sc.path.isfile(self._unc(rel)))

    def size(self, rel):
        return self._do(lambda: self.sc.stat(self._unc(rel)).st_size)

    def listdir(self, rel):
        def f():
            out = []
            for e in self.sc.scandir(self._unc(rel)):
                try:
                    d = e.is_dir()
                    out.append({'name': e.name, 'is_dir': d,
                                'size': None if d else e.stat().st_size})
                except OSError:
                    continue
            return out
        return self._do(f)

    def open(self, rel):
        return self._do(lambda: self.sc.open_file(self._unc(rel), mode='rb', share_access='r'))

    def walk(self):
        self._login()
        top = self._unc('')
        for dirpath, dirnames, filenames in self.sc.walk(top):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            rd = dirpath[len(top):].lstrip('\\').replace('\\', '/')
            yield rd, filenames

    def mutagen_source(self, rel):
        ext = Path(rel).suffix.lower()
        size = self.size(rel)
        limit = MAX_TAG_HEAD if ext in ('.mp3', '.flac') else MAX_TAG_FILE
        if ext not in ('.mp3', '.flac') and size > limit:
            return None
        with self.open(rel) as f:
            return io.BytesIO(f.read(min(size, limit)))


def make_storage():
    if STORAGE_MODE == 'local':
        return LocalStorage(MUSIC_ROOT)
    if STORAGE_MODE == 'smb':
        need = (('SMB_HOST', SMB_HOST), ('SMB_SHARE', SMB_SHARE),
                ('SMB_USER', os.getenv('SMB_USER', '')), ('SMB_PASS', SMB_PASS))
        missing = [n for n, v in need if not v]
        if missing:
            raise SystemExit('STORAGE_MODE=smb, aber fehlend: ' + ', '.join(missing))
        return SmbStorage(SMB_HOST, SMB_SHARE, SMB_PATH, SMB_USER, SMB_PASS,
                          SMB_DOMAIN, SMB_PORT, SMB_ENCRYPT)
    raise SystemExit(f'STORAGE_MODE muss "local" oder "smb" sein, nicht {STORAGE_MODE!r}')


STORAGE = make_storage()


# ── FEHLERBEHANDLUNG FÜR SPEICHERZUGRIFF ──────────────────────────────────
def _err_404(e):
    return jsonify({'error': 'Nicht gefunden'}), 404


def _err_403(e):
    return jsonify({'error': 'Kein Zugriff'}), 403


def _err_502(e):
    print(f'⚠ Speicherfehler: {e}', flush=True)
    return jsonify({'error': 'Speicher nicht erreichbar'}), 502


for _exc in (FileNotFoundError, NotADirectoryError):
    app.register_error_handler(_exc, _err_404)
app.register_error_handler(PermissionError, _err_403)
for _exc in (OSError, SMBException):
    app.register_error_handler(_exc, _err_502)


# ── AUTH ──────────────────────────────────────────────────────────────────────
def check_token(token: str) -> bool:
    if not token or not API_KEY:
        return False
    h = hashlib.sha256(token.encode()).hexdigest()
    return secrets.compare_digest(h, API_KEY_HASH)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = (
            request.headers.get('X-API-Key') or
            request.headers.get('X-Auth')    or
            request.args.get('apikey')        or
            request.args.get('auth')          or ''
        )
        if not check_token(token):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/api/verify', methods=['POST'])
def verify():
    data  = request.get_json(silent=True) or {}
    token = data.get('apikey', '').strip()
    if check_token(token):
        return jsonify({'ok': True, 'user': SMB_USER})
    return jsonify({'ok': False, 'error': 'Falsches Passwort'}), 401


@app.route('/api/client-config')
def client_config():
    """Öffentliche Konfiguration für den Login-Screen."""
    return jsonify({
        'default_url':  DEFAULT_URL,
        'app_name':     'MP3z Samba Player',
        'version':      '2.0.0',
        'storage_mode': STORAGE.mode,
    })


# ── IN-MEMORY INDEX ───────────────────────────────────────────────────────────
class FileIndex:
    def __init__(self):
        self._lock     = threading.Lock()
        self._entries  = []
        self._built    = 0.0
        self._building = False

    def get(self):
        if (time.time() - self._built > INDEX_TTL) and not self._building:
            threading.Thread(target=self._build, daemon=True).start()
        with self._lock:
            return list(self._entries)

    def _build(self):
        if self._building:
            return
        self._building = True
        print(f'🔍 Baue Datei-Index ({STORAGE.mode}) …', flush=True)
        t0, result, failed = time.time(), [], False
        try:
            for rel_dir, filenames in STORAGE.walk():
                for fn in filenames:
                    if fn.startswith('.'):
                        continue
                    if Path(fn).suffix.lower() not in AUDIO_EXTS:
                        continue
                    result.append({'name': fn, 'path': _join(rel_dir, fn),
                                   'dir': rel_dir or '/'})
        except Exception as e:
            failed = True
            print(f'⚠ Index-Fehler: {e}', flush=True)
        with self._lock:
            if result or not failed:
                self._entries = result
        # Bei Fehler schon nach 60 s erneut versuchen
        self._built    = time.time() - INDEX_TTL + 60 if failed else time.time()
        self._building = False
        print(f'✓ Index: {len(result)} Dateien in {time.time()-t0:.1f}s', flush=True)


index = FileIndex()


# ── API: BROWSE ───────────────────────────────────────────────────────────────
@app.route('/api/browse')
@require_auth
def browse():
    rel    = clean_rel(request.args.get('path', ''))
    offset = int(request.args.get('offset', 0))
    limit  = min(int(request.args.get('limit', PAGE_SIZE)), 500)
    try:
        items = STORAGE.listdir(rel)
    except PermissionError:
        return jsonify({'error': 'Kein Zugriff'}), 403
    except (FileNotFoundError, NotADirectoryError):
        return jsonify({'error': 'Kein Verzeichnis'}), 404
    items.sort(key=lambda e: (not e['is_dir'], e['name'].lower()))
    entries = []
    for it in items:
        name = it['name']
        if name.startswith('.'):
            continue
        if it['is_dir']:
            entries.append({'type': 'dir', 'name': name, 'path': _join(rel, name)})
        elif Path(name).suffix.lower() in (AUDIO_EXTS | IMG_EXTS):
            entries.append({'type': 'file', 'name': name, 'path': _join(rel, name),
                            'size': it['size']})
    total = len(entries)
    page  = entries[offset:offset+limit]
    return jsonify({'path': rel, 'entries': page, 'offset': offset,
                    'limit': limit, 'total': total, 'has_more': (offset+limit) < total})


# ── API: SEARCH ───────────────────────────────────────────────────────────────
@app.route('/api/search')
@require_auth
def search():
    q      = request.args.get('q', '').lower().strip()
    offset = int(request.args.get('offset', 0))
    limit  = min(int(request.args.get('limit', 100)), 500)
    if not q or len(q) < 2:
        return jsonify({'results': [], 'total': 0, 'has_more': False})
    all_files = index.get()
    exact, contains = [], []
    for e in all_files:
        nl = e['name'].lower()
        if nl.startswith(q):                        exact.append(e)
        elif q in nl or q in e['dir'].lower():      contains.append(e)
    matched = exact + contains
    total   = len(matched)
    page    = matched[offset:offset+limit]
    return jsonify({'query': q,
                    'results': [{'type': 'file', 'name': e['name'],
                                 'path': e['path'], 'dir': e['dir']} for e in page],
                    'total': total, 'offset': offset, 'has_more': (offset+limit) < total})


# ── API: STREAM ───────────────────────────────────────────────────────────────
@app.route('/api/stream')
@require_auth
def stream():
    rel = clean_rel(request.args.get('path', ''))
    if Path(rel).suffix.lower() not in AUDIO_EXTS or not STORAGE.isfile(rel):
        abort(404)
    file_size = STORAGE.size(rel)
    mime      = mimetypes.guess_type(rel)[0] or 'audio/mpeg'
    range_hdr = request.headers.get('Range')
    if range_hdr:
        m = re.match(r'bytes=(\d+)-(\d*)', range_hdr)
        if m:
            start = int(m.group(1))
            end   = int(m.group(2)) if m.group(2) else file_size - 1
            end   = min(end, file_size - 1)
            if start >= file_size or end < start:
                return Response(status=416, headers={'Content-Range': f'bytes */{file_size}'})
            length = end - start + 1
            def gen():
                with STORAGE.open(rel) as f:
                    f.seek(start); rem = length
                    while rem > 0:
                        chunk = f.read(min(CHUNK_SIZE, rem))
                        if not chunk: break
                        rem -= len(chunk); yield chunk
            return Response(gen(), 206, headers={
                'Content-Range':  f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges':  'bytes',
                'Content-Length': str(length),
                'Content-Type':   mime})
    def gen_full():
        with STORAGE.open(rel) as f:
            while chunk := f.read(CHUNK_SIZE): yield chunk
    return Response(gen_full(), 200, headers={
        'Accept-Ranges':  'bytes',
        'Content-Length': str(file_size),
        'Content-Type':   mime})


# ── API: ALBUM ART ────────────────────────────────────────────────────────────
@app.route('/api/art')
@require_auth
def art():
    rel    = clean_rel(request.args.get('path', ''))
    suffix = Path(rel).suffix.lower()
    art_data, art_mime = None, 'image/jpeg'
    is_file = suffix in AUDIO_EXTS and STORAGE.isfile(rel)
    if is_file and MUTAGEN_OK and suffix in ART_TAG_EXTS:
        try:
            src = STORAGE.mutagen_source(rel)
            if src is not None:
                if suffix == '.mp3':
                    tags = ID3(src)
                    for k in tags.keys():
                        if k.startswith('APIC'):
                            art_data = tags[k].data; art_mime = tags[k].mime; break
                elif suffix in ('.m4a', '.mp4', '.aac'):
                    tags = MP4(src)
                    if 'covr' in tags: art_data = bytes(tags['covr'][0])
                elif suffix == '.flac':
                    tags = FLAC(src)
                    if tags.pictures:
                        art_data = tags.pictures[0].data
                        art_mime = tags.pictures[0].mime
        except Exception:
            pass
    if art_data:
        return Response(art_data, mimetype=art_mime,
                        headers={'Cache-Control': 'public, max-age=86400'})
    folder  = _parent(rel) if is_file else rel
    entries = STORAGE.listdir(folder)
    files   = {e['name'].lower(): e['name'] for e in entries if not e['is_dir']}
    chosen  = next((files[n] for n in COVER_NAMES if n in files), None)
    if not chosen:
        imgs = sorted((e['name'] for e in entries
                       if not e['is_dir'] and not e['name'].startswith('.')
                       and Path(e['name']).suffix.lower() in IMG_EXTS), key=str.lower)
        chosen = imgs[0] if imgs else None
    if not chosen:
        abort(404)
    with STORAGE.open(_join(folder, chosen)) as f:
        data = f.read(MAX_COVER_BYTES)
    return Response(data, mimetype=mimetypes.guess_type(chosen)[0] or 'image/jpeg',
                    headers={'Cache-Control': 'public, max-age=86400'})


# ── API: INDEX STATUS ─────────────────────────────────────────────────────────
@app.route('/api/index-status')
@require_auth
def index_status():
    entries = index.get()
    return jsonify({'total_files': len(entries),
                    'built_ago':   round(time.time() - index._built),
                    'building':    index._building,
                    'storage':     STORAGE.mode,
                    'music_root':  STORAGE.describe()})


# ── STATIC FILES ──────────────────────────────────────────────────────────────
HERE = Path(__file__).parent


@app.route('/')
def idx():
    p = HERE / 'samba-player.html'
    return send_file(p) if p.exists() else ('<h1>samba-player.html fehlt</h1>', 404)


@app.route('/sw.js')
def service_worker():
    p = HERE / 'sw.js'
    if not p.exists(): abort(404)
    return send_file(p, mimetype='application/javascript',
                     max_age=0,
                     conditional=True)


@app.route('/manifest.json')
def manifest():
    return jsonify({
        'name':             'MP3z Samba Player',
        'short_name':       'MP3z',
        'description':      'Self-hosted Heimmusik-Streaming — 60k Tracks',
        'start_url':        '/',
        'display':          'standalone',
        'background_color': '#0a0a0f',
        'theme_color':      '#0a0a0f',
        'orientation':      'portrait',
        'icons': [
            {'src': '/icon-192.png', 'sizes': '192x192',
             'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/icon-512.png', 'sizes': '512x512',
             'type': 'image/png', 'purpose': 'any maskable'},
        ],
        'shortcuts': [{
            'name':       'Musik durchsuchen',
            'short_name': 'Browse',
            'url':        '/',
            'icons':      [{'src': '/icon-192.png', 'sizes': '192x192'}]
        }]
    })


@app.route('/icon-<int:size>.png')
def icon(size):
    """Serviert Icons — generiert sie on-the-fly falls nicht vorhanden."""
    p = HERE / f'icon-{size}.png'
    if p.exists():
        return send_file(p, mimetype='image/png',
                         max_age=86400)
    try:
        from PIL import Image, ImageDraw
        img = _generate_icon(size)
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)
        return Response(buf.read(), mimetype='image/png',
                        headers={'Cache-Control': 'public, max-age=86400'})
    except ImportError:
        abort(404)


def _generate_icon(size):
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    d   = ImageDraw.Draw(img)
    pad = size * 0.04
    d.ellipse([pad, pad, size-pad, size-pad], fill=(10,10,15,255))
    ring_w = max(4, size // 20)
    for i in range(20):
        t = i / 19
        r = int(255 * (1 - t * 0.4)); g = int(94 + t * 60); b = int(58 * (1 - t * 0.6))
        box = [pad+ring_w//2, pad+ring_w//2, size-pad-ring_w//2, size-pad-ring_w//2]
        d.arc(box, i*18-90, i*18-71, fill=(r,g,b,255), width=ring_w)
    cc = size * 0.28; cx = cy = size / 2
    d.ellipse([cx-cc, cy-cc, cx+cc, cy+cc], fill=(255,94,58,255))
    ci = cc * 0.6
    d.ellipse([cx-ci, cy-ci, cx+ci, cy+ci], fill=(255,154,60,255))
    nh, nw = cc*0.38, cc*0.46; nx, ny = cx-cc*0.05, cy+cc*0.32
    d.ellipse([nx-nw, ny-nh, nx+nw, ny+nh], fill=(10,10,15,255))
    sw = max(2, int(size*0.028)); sh = cc*0.9; sx = nx+nw-sw//2
    d.rectangle([sx, ny-sh, sx+sw, ny], fill=(10,10,15,255))
    d.arc([sx, ny-sh, sx+cc*0.76, ny-sh+cc*0.64], -90, 45,
          fill=(10,10,15,255), width=sw)
    return img


@app.route('/api/ping')
def ping():
    return jsonify({'status': 'ok', 'version': '2.0.0'})


# ── START ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('━' * 50)
    print(' 🎵 hAI.highfishMP3zPlayer  v2.0.0')
    print('━' * 50)
    print(f'  Storage   : {STORAGE.mode}')
    print(f'  Quelle    : {STORAGE.describe()}')
    print(f'  User      : {SMB_USER}')
    print(f'  URL       : http://{HOST}:{PORT}')
    print(f'  API-Key   : {"✓ gesetzt" if API_KEY else "⚠ NICHT GESETZT!"}')
    print('━' * 50)
    ok, msg = STORAGE.check()
    print(('✓ ' if ok else '⚠ ') + msg, flush=True)
    threading.Thread(target=index._build, daemon=True).start()
    print(f'Starte Server auf Port {PORT}')
    app.run(host=HOST, port=PORT, threaded=True)
