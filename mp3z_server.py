#!/usr/bin/env python3
"""
MP3z Samba Player Backend
hAI.highfishMP3zPlayer by TheRealTeacher / Highfish AI

Install:
  pip install flask flask-cors mutagen python-dotenv pillow --break-system-packages

Konfiguration:
  cp .env.example .env && joe .env

Start:
  python3 mp3z_server.py
"""

import os, re, json, time, mimetypes, threading, secrets, hashlib
from pathlib import Path
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, send_file, abort
from flask_cors import CORS

# ── .env laden ────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / '.env')

# ── KONFIGURATION (aus .env) ──────────────────────────────────────────────────
# Musikquellen: MUSIC_ROOTS als JSON-Objekt {name: pfad} — rückwärtskompatibel
# mit MUSIC_ROOT (wird als Quelle "music" geführt). Names sind "slugified".
def _slug(name: str) -> str:
    return re.sub(r'[^a-z0-9_-]+', '-', name.lower()).strip('-') or 'music'


def _parse_music_roots(env: str) -> dict:
    """Validiert MUSIC_ROOTS-JSON. Nur Objekte mit string-Keys/-Werten sind
    gültig; doppelte Slug-Namen und leere/ungültige Werte führen zum
    Fallback auf MUSIC_ROOT."""
    try:
        data = json.loads(env)
    except json.JSONDecodeError:
        print('⚠  MUSIC_ROOTS ist kein gültiges JSON — falle auf MUSIC_ROOT zurück.')
        return {}
    if not isinstance(data, dict):
        print('⚠  MUSIC_ROOTS muss ein JSON-Objekt sein — falle auf MUSIC_ROOT zurück.')
        return {}
    out = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str) or not v:
            print(f'⚠  MUSIC_ROOTS-Eintrag übersprungen (kein String): {k!r}')
            continue
        slug = _slug(k)
        if slug in out:
            print(f'⚠  MUSIC_ROOTS: doppelter Quellenname "{slug}" — übersprungen.')
            continue
        out[slug] = Path(v).expanduser()
    return out


_roots_env = os.getenv('MUSIC_ROOTS')
MUSIC_ROOTS = _parse_music_roots(_roots_env) if _roots_env else {}
if not MUSIC_ROOTS:
    MUSIC_ROOTS = {'music': Path(os.getenv('MUSIC_ROOT', '/mnt/USBHDD_MP3z')).expanduser()}
HOST        = os.getenv('HOST',             '0.0.0.0')
PORT        = int(os.getenv('PORT',         '80'))
SMB_USER    = os.getenv('SMB_USER',         'user')
SMB_PASS    = os.getenv('SMB_PASS',         '')
API_KEY     = os.getenv('API_KEY_OVERRIDE') or SMB_PASS
DEFAULT_URL = os.getenv('DEFAULT_URL',      'http://localhost')

if not API_KEY:
    print('⚠  Kein Passwort gesetzt! Bitte .env konfigurieren.')

API_KEY_HASH = hashlib.sha256(API_KEY.encode()).hexdigest()

# ── KONSTANTEN ────────────────────────────────────────────────────────────────
AUDIO_EXTS = {'.mp3','.flac','.ogg','.m4a','.wav','.aac','.opus','.wma'}
IMG_EXTS   = {'.jpg','.jpeg','.png','.webp','.gif'}
PAGE_SIZE  = 80
CHUNK_SIZE = 64 * 1024
INDEX_TTL  = 3600

app = Flask(__name__)
CORS(app, origins='*')

try:
    from mutagen.id3  import ID3
    from mutagen.mp4  import MP4
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

# ── AUTH ──────────────────────────────────────────────────────────────────────
def check_token(token: str) -> bool:
    if not token:
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

# ── LOGIN VERIFY ──────────────────────────────────────────────────────────────
@app.route('/api/verify', methods=['POST'])
def verify():
    data  = request.get_json(silent=True) or {}
    token = data.get('apikey', '').strip()
    if check_token(token):
        return jsonify({'ok': True, 'user': SMB_USER})
    return jsonify({'ok': False, 'error': 'Falsches Passwort'}), 401

# ── CLIENT CONFIG (kein Auth nötig) ──────────────────────────────────────────
@app.route('/api/client-config')
def client_config():
    """Gibt öffentliche Konfiguration für den Login-Screen zurück."""
    return jsonify({
        'default_url': DEFAULT_URL,
        'app_name':    'MP3z Samba Player',
        'version':     '2.0.0',
    })

# ── SICHERHEIT ────────────────────────────────────────────────────────────────
def split_source(rel: str):
    """Trennt Quellen-Präfix vom quellenrelativen Pfad → (root, rel_part).
    Leerer Pfad ('') = Quellen-Übersicht bzw. Wurzel der Default-Quelle."""
    rel  = (rel or '').replace('\\', '/').lstrip('/')
    if not rel:
        return None, ''
    first, _, rest = rel.partition('/')
    if first in MUSIC_ROOTS:
        return MUSIC_ROOTS[first], rest
    return None, rel

def _resolve_fallback(rel: str):
    """Einzelner Root: akzeptiert zusätzlich Pfade ohne Quellen-Präfix."""
    src, r = split_source(rel)
    if src is None and len(MUSIC_ROOTS) == 1:
        return next(iter(MUSIC_ROOTS.values())), r
    return src, r

def resolve_source(rel: str) -> Path:
    """Löst einen Pfad gegen seine Quelle auf — 403 bei unbekannter Quelle
    oder Directory-Traversal außerhalb der Quelle."""
    src, r = _resolve_fallback(rel)
    if src is None:
        abort(403)
    src_resolved = src.resolve()
    full = (src / r).resolve()
    try:
        full.relative_to(src_resolved)
    except ValueError:
        abort(403)
    return full

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
        self._building = True
        print('🔍 Baue Datei-Index über {} Quelle(n) …'.format(len(MUSIC_ROOTS)), flush=True)
        t0, result = time.time(), []
        for src_name, root in MUSIC_ROOTS.items():
            root = root.resolve()
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                    rel_dir = str(Path(dirpath).relative_to(root))
                    if rel_dir == '.': rel_dir = ''
                    for fn in filenames:
                        if fn.startswith('.'): continue
                        if Path(fn).suffix.lower() not in AUDIO_EXTS: continue
                        rel_path = src_name + '/' + (rel_dir + '/' if rel_dir else '') + fn
                        result.append({'name': fn, 'path': rel_path,
                                       'dir': (src_name + '/' + rel_dir) if rel_dir else src_name})
            except Exception as e:
                print(f'⚠ Index-Fehler ({src_name}): {e}', flush=True)
        with self._lock:
            self._entries = result
        self._built    = time.time()
        self._building = False
        print(f'✓ Index: {len(result)} Dateien in {time.time()-t0:.1f}s', flush=True)

index = FileIndex()

# ── API: BROWSE ───────────────────────────────────────────────────────────────
@app.route('/api/browse')
@require_auth
def browse():
    rel    = request.args.get('path', '')
    offset = int(request.args.get('offset', 0))
    limit  = min(int(request.args.get('limit', PAGE_SIZE)), 500)
    src, r = _resolve_fallback(rel)
    # Keine Quelle und kein Pfad → Quellen-Übersicht (nur bei >1 Quelle)
    if src is None and not r:
        entries = [{'type': 'dir', 'name': k, 'path': k} for k in MUSIC_ROOTS]
        total = len(entries)
        page  = entries[offset:offset+limit]
        return jsonify({'path': '', 'entries': page, 'offset': offset,
                        'limit': limit, 'total': total, 'has_more': (offset+limit) < total})
    path = resolve_source(rel)
    if not path.is_dir():
        return jsonify({'error': 'Kein Verzeichnis'}), 404
    try:
        items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return jsonify({'error': 'Kein Zugriff'}), 403
    source_prefix = [k for k, v in MUSIC_ROOTS.items() if v == src]
    prefix = source_prefix[0] if source_prefix else ''

    entries = []
    for item in items:
        if item.name.startswith('.'): continue
        sx = item.suffix.lower()
        rel_item = str(item.relative_to(src)).replace('\\', '/')
        base_path = f"{prefix}/{rel_item}" if prefix else rel_item
        if item.is_dir():
            entries.append({'type': 'dir', 'name': item.name, 'path': base_path})
        elif item.is_file() and sx in (AUDIO_EXTS | IMG_EXTS):
            entries.append({'type': 'file', 'name': item.name, 'path': base_path,
                            'size': item.stat().st_size})
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
    rel  = request.args.get('path', '')
    path = resolve_source(rel)
    if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
        abort(404)
    file_size = path.stat().st_size
    mime      = mimetypes.guess_type(str(path))[0] or 'audio/mpeg'
    range_hdr = request.headers.get('Range')
    if range_hdr:
        m = re.match(r'bytes=(\d+)-(\d*)', range_hdr)
        if m:
            start  = int(m.group(1))
            end    = int(m.group(2)) if m.group(2) else file_size - 1
            length = end - start + 1
            def gen():
                with open(path, 'rb') as f:
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
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE): yield chunk
    return Response(gen_full(), 200, headers={
        'Accept-Ranges':  'bytes',
        'Content-Length': str(file_size),
        'Content-Type':   mime})

# ── API: ALBUM ART ────────────────────────────────────────────────────────────
@app.route('/api/art')
@require_auth
def art():
    rel    = request.args.get('path', '')
    path   = resolve_source(rel)
    suffix = path.suffix.lower()
    art_data, art_mime = None, 'image/jpeg'
    if MUTAGEN_OK:
        try:
            if suffix == '.mp3':
                tags = ID3(path)
                for k in tags.keys():
                    if k.startswith('APIC'):
                        art_data = tags[k].data; art_mime = tags[k].mime; break
            elif suffix in ('.m4a', '.mp4', '.aac'):
                tags = MP4(path)
                if 'covr' in tags: art_data = bytes(tags['covr'][0])
            elif suffix == '.flac':
                tags = FLAC(path)
                if tags.pictures:
                    art_data = tags.pictures[0].data
                    art_mime = tags.pictures[0].mime
        except Exception: pass
    if art_data:
        return Response(art_data, mimetype=art_mime,
                        headers={'Cache-Control': 'public, max-age=86400'})
    folder = path.parent if path.is_file() else path
    for name in ('cover.jpg', 'cover.jpeg', 'cover.png', 'folder.jpg', 'folder.png'):
        c = folder / name
        if c.exists(): return send_file(c)
    for item in folder.iterdir():
        if item.suffix.lower() in IMG_EXTS: return send_file(item)
    abort(404)

# ── API: INDEX STATUS ─────────────────────────────────────────────────────────
@app.route('/api/index-status')
@require_auth
def index_status():
    entries = index.get()
    roots = {k: str(v) for k, v in MUSIC_ROOTS.items()}
    return jsonify({'total_files': len(entries),
                    'built_ago':   round(time.time() - index._built),
                    'building':    index._building,
                    'music_root':  next(iter(roots.values()), None),
                    'music_roots': roots})

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
    # On-the-fly generieren
    try:
        from PIL import Image, ImageDraw
        img = _generate_icon(size)
        import io
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
    print(f'  User         : {SMB_USER}')
    print(f'  Music-Roots  : {len(MUSIC_ROOTS)} Quelle(n)')
    for n, p in MUSIC_ROOTS.items():
        mark = ' ✓' if p.exists() else ' ⚠ fehlt'
        print(f'    {n}: {p}{mark}')
    print(f'  URL          : http://{HOST}:{PORT}')
    print(f'  API-Key      : {"✓ gesetzt" if API_KEY else "⚠ NICHT GESETZT!"}')
    print('━' * 50)
    for n, p in MUSIC_ROOTS.items():
        if not p.exists():
            print(f'⚠  Quelle "{n}" nicht gefunden: {p}')
    threading.Thread(target=index._build, daemon=True).start()
    app.run(host=HOST, port=PORT, threaded=True)

# ══════════════════════════════════════════════════════════════════════════════
# SYSTEMD: /etc/systemd/system/mp3z.service
# [Unit]
# Description=MP3z Samba Player Backend
# After=network.target
# [Service]
# Type=simple
# User=root
# WorkingDirectory=/opt/mp3z
# ExecStart=/usr/bin/python3 /opt/mp3z/mp3z_server.py
# Restart=always
# RestartSec=5
# [Install]
# WantedBy=multi-user.target
# ══════════════════════════════════════════════════════════════════════════════
