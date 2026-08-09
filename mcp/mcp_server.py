#!/usr/bin/env python3
"""
MCP server for the MP3z music library.

Exposes the MP3z collection to MCP clients (Claude Desktop, Copilot, …):

  search_tracks(query, limit)  → {name, path, source, dir}
  get_track_info(path)         → mutagen metadata (title, artist, album, …)
  get_stream_url(path)         → MP3z stream/download URL (with apikey)
  get_browse(path)             → directory listing

Two backends, chosen by env:
  - Local mode  (default): reads MUSIC_ROOT / MUSIC_ROOTS directly from disk.
  - HTTP mode   (MP3Z_BASE_URL set): calls the mp3z server's /api/* endpoints.

Transport:
  - stdio (default):           mcp_server.py
  - streamable HTTP (--http):  mcp_server.py --http --port 8080

Selftest (no MCP client needed):
  python mcp_server.py --selftest --music-root ./sample_music
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

AUDIO_EXTS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.aac', '.opus', '.wma'}
IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

MCP_DISPLAY_NAME = os.getenv('MCP_DISPLAY_NAME', 'mp3z')
MCP_SERVER_NAME = re.sub(r'[^a-z0-9_-]', '_', MCP_DISPLAY_NAME.lower())


# ── backend selection ──────────────────────────────────────────────────────────
class Config:
    def __init__(self):
        self.base_url = os.getenv('MP3Z_BASE_URL', '').rstrip('/')
        self.api_key = os.getenv('MP3Z_API_KEY', '')
        self.music_root = os.getenv('MUSIC_ROOT', '')
        self.music_roots = self._parse_roots(os.getenv('MUSIC_ROOTS', ''))
        self.stream_base = os.getenv('MP3Z_STREAM_BASE', self.base_url).rstrip('/')
        self.http_mode = bool(self.base_url)

    def _parse_roots(self, raw):
        """MUSIC_ROOTS: JSON object {'source': '/abs/path', …} or list of paths."""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if v}
        if isinstance(data, list):
            return {str(Path(p).name): str(p) for p in data if p}
        return {}

    def list_roots(self):
        roots = dict(self.music_roots)
        if self.music_root and 'default' not in roots:
            roots = {'default': self.music_root, **roots}
        return roots

    def resolve_source(self, path):
        """'src/rel' → (source, rel) or (None, path)."""
        if '/' not in path:
            return None, path
        source, _, rest = path.partition('/')
        if source in self.music_roots:
            return source, rest
        if source == 'default' and 'default' in self.list_roots():
            return 'default', rest
        return None, path

    def to_display_path(self, root_label, rel):
        """'rel' in root 'default' → 'rel'; other roots keep their prefix."""
        rel = rel.replace('\\', '/')
        if root_label == 'default':
            return rel
        return f'{root_label}/{rel}'


CONF = Config()


# ── path safety (local mode) ───────────────────────────────────────────────────
def _split(path: str):
    """Split a display path into (root_label, rel) and validate traversal."""
    path = path.replace('\\', '/').lstrip('/')
    if path.startswith('.'):
        raise ValueError('path must not start with a dot')
    roots = CONF.list_roots()
    if path == '' or path == '.':
        return 'default', ''
    first, _, rest = path.partition('/')
    if first in roots:
        root_label = first
        rel = rest
    else:
        root_label = 'default'
        rel = path
    parts = [p for p in rel.split('/') if p not in ('', '.')]
    if any(p == '..' for p in parts):
        raise ValueError('path traversal not allowed')
    return root_label, '/'.join(parts)


def safe_local_path(path: str) -> Path:
    """Resolve a display path inside its configured root, rejecting traversal."""
    if CONF.http_mode:
        raise ValueError('not available in HTTP mode')
    root_label, rel = _split(path)
    roots = CONF.list_roots()
    if root_label not in roots:
        raise ValueError(f'unknown music root: {root_label!r}')
    base = Path(roots[root_label]).resolve()
    full = (base / rel).resolve()
    if not full.is_relative_to(base):
        raise ValueError('path traversal not allowed')
    return full


# ── metadata ───────────────────────────────────────────────────────────────────
# Map format-specific Mutagen keys to canonical metadata fields.
_TAG_KEYS = {
    'TIT2': 'title', '©nam': 'title', '\xa9nam': 'title',
    'TPE1': 'artist', '©ART': 'artist', '\xa9ART': 'artist',
    'TALB': 'album', '©alb': 'album', '\xa9alb': 'album',
}


def _canonical_tags(tags: dict) -> dict:
    out = {}
    for k, v in tags.items():
        key = _TAG_KEYS.get(k, k)
        out[key] = v
    return out


def read_tags(path: Path):
    try:
        from mutagen.id3 import ID3
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
    except ImportError:
        return {}
    try:
        suffix = path.suffix.lower()
        if suffix == '.mp3':
            return _canonical_tags(
                {k: str(v) for k, v in ID3(path).items() if not k.startswith('APIC')})
        if suffix == '.flac':
            t = FLAC(path)
            tags = {}
            for k, v in t.tags.items():
                tags[k] = str(v[0]) if isinstance(v, list) and v else str(v)
            return tags
        if suffix in ('.m4a', '.mp4', '.aac'):
            t = MP4(path)
            return _canonical_tags(
                {k: str(v[0]) if isinstance(v, list) and v else str(v)
                 for k, v in t.tags.items() if k != 'covr'})
    except Exception:
        return {}
    return {}


def _fmt_dur(sec):
    if sec is None:
        return None
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def track_info(path: Path):
    stat = path.stat()
    tags = read_tags(path)
    duration = None
    try:
        from mutagen import File as MFile
        m = MFile(path)
        if m is not None:
            duration = m.info.length if getattr(m, 'info', None) and m.info.length else None
    except Exception:
        pass
    dur_fmt = _fmt_dur(duration)
    d = {
        'path': str(path),
        'name': path.name,
        'size': stat.st_size,
        'format': path.suffix.lower().lstrip('.'),
        'duration': dur_fmt,
        'duration_sec': duration,
    }
    for k in ('title', 'artist', 'album'):
        d[k] = tags.get(k)
    title = tags.get('title') or path.stem
    artist = tags.get('artist')
    d['title'] = title
    d['artist'] = artist
    return d


def _http_get(route: str, params: dict):
    url = f'{CONF.base_url}{route}?' + urllib.parse.urlencode(params)
    headers = {'Accept': 'application/json'}
    if CONF.api_key:
        headers['X-API-Key'] = CONF.api_key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _stream_url(path: str) -> str:
    if not CONF.stream_base:
        raise ValueError('MP3Z_STREAM_BASE (or MP3Z_BASE_URL) must be set to build a stream URL')
    qs = urllib.parse.urlencode({'path': path})
    if CONF.api_key:
        qs += '&' + urllib.parse.urlencode({'apikey': CONF.api_key})
    return f'{CONF.stream_base}/api/stream?{qs}'


# ── tool implementations ───────────────────────────────────────────────────────
def search_tracks(query: str, limit: int = 20):
    q = (query or '').strip().lower()
    if not q or len(q) < 2:
        return {'query': query or '', 'results': [], 'total': 0}
    # Normalize limit: reject negative/invalid, clamp to max 500
    try:
        limit = max(0, min(int(limit), 500))
    except (ValueError, TypeError):
        limit = 20
    if CONF.http_mode:
        data = _http_get('/api/search', {'q': q, 'limit': min(int(limit), 500)})
        return {'query': data.get('query', q), 'total': data.get('total', 0),
                'results': [
                    {'name': r.get('name'), 'path': r.get('path'),
                     'source': r.get('dir', '').lstrip('/'),
                     'dir': r.get('dir', '')}
                    for r in data.get('results', [])]}
    hits = []
    for label, root in CONF.list_roots().items():
        base = Path(root).resolve()
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            dp = Path(dirpath)
            rel_dir = str(dp.relative_to(base)).replace('\\', '/')
            if rel_dir == '.':
                rel_dir = ''
            for fn in filenames:
                if fn.startswith('.') or Path(fn).suffix.lower() not in AUDIO_EXTS:
                    continue
                nl = fn.lower()
                if nl.startswith(q) or q in nl or q in rel_dir.lower():
                    rel = (rel_dir + '/' + fn).lstrip('/')
                    hits.append({'name': fn, 'path': CONF.to_display_path(label, rel),
                                 'source': label, 'dir': rel_dir or '/'})
    hits.sort(key=lambda h: (not h['name'].lower().startswith(q), h['name'].lower()))
    return {'query': q, 'total': len(hits), 'results': hits[:int(limit)]}


def get_track_info(path: str):
    if CONF.http_mode:
        data = _http_get('/api/search', {'q': Path(path).stem, 'limit': 20})
        results = data.get('results', [])
        match = None
        for r in results:
            if r.get('path') == path:
                match = r
                break
        if not match:
            raise ValueError(f'track not found: {path}')
        rel_path = Path(path)
        if rel_path.suffix.lower() not in {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.aac', '.opus', '.wma'}:
            raise ValueError(f'not an audio file: {path}')
        return {
            'path': path,
            'name': match.get('name', Path(path).name),
            'size': None,
            'format': rel_path.suffix.lower().lstrip('.'),
            'duration': None,
            'duration_sec': None,
            'title': rel_path.stem,
            'artist': None,
            'album': None,
            'source': match.get('source'),
            'dir': match.get('dir'),
        }
    p = safe_local_path(path)
    if not p.is_file():
        raise ValueError(f'not a file: {path}')
    if p.suffix.lower() not in AUDIO_EXTS:
        raise ValueError(f'not an audio file: {path}')
    d = track_info(p)
    d['path'] = path
    d['file'] = str(p)
    return d


def get_stream_url(path: str):
    if CONF.http_mode:
        return {'path': path, 'url': _stream_url(path),
                'description': 'Download/stream URL on the MP3z server'}
    # Validate the file exists locally before handing out a URL.
    p = safe_local_path(path)
    if not p.is_file() or p.suffix.lower() not in AUDIO_EXTS:
        raise ValueError(f'not an audio file: {path}')
    return {'path': path, 'url': _stream_url(path),
            'description': 'Download/stream URL on the MP3z server'}


def get_browse(path: str = ''):
    if CONF.http_mode:
        data = _http_get('/api/browse', {'path': path, 'limit': 500})
        return {'path': data.get('path', path),
                'entries': [
                    {'type': e.get('type'), 'name': e.get('name'),
                     'path': e.get('path'), 'size': e.get('size')}
                    for e in data.get('entries', [])],
                'total': data.get('total', 0)}
    p = safe_local_path(path)
    if not p.is_dir():
        raise ValueError(f'not a directory: {path}')
    root_label, _ = _split(path)
    base = Path(CONF.list_roots()[root_label]).resolve()
    entries = []
    for item in sorted(p.iterdir(), key=lambda i: (i.is_file(), i.name.lower())):
        if item.name.startswith('.'):
            continue
        sub = str(item.relative_to(base)).replace('\\', '/')
        if item.is_dir():
            entries.append({'type': 'dir', 'name': item.name,
                            'path': CONF.to_display_path(root_label, sub),
                            'size': None})
        elif item.suffix.lower() in (AUDIO_EXTS | IMG_EXTS):
            entries.append({'type': 'file', 'name': item.name,
                            'path': CONF.to_display_path(root_label, sub),
                            'size': item.stat().st_size})
    return {'path': path, 'entries': entries, 'total': len(entries)}


# ── MCP wiring ─────────────────────────────────────────────────────────────────
def build_server(port: int = 8000):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(name=MCP_SERVER_NAME,
                     settings={'host': '0.0.0.0', 'port': port})

    @server.tool()
    def search_tracks_tool(query: str, limit: int = 20) -> dict:
        """Search the music library by name or folder.

        Args:
            query: search term (min. 2 characters)
            limit: max number of results (default 20)
        """
        return search_tracks(query, limit)

    @server.tool()
    def get_track_info_tool(path: str) -> dict:
        """Return metadata for one track (title, artist, album, duration, size, format).

        Args:
            path: track path as returned by search_tracks / get_browse
        """
        return get_track_info(path)

    @server.tool()
    def get_stream_url_tool(path: str) -> dict:
        """Return the MP3z stream/download URL for a track.

        Args:
            path: track path as returned by search_tracks / get_browse
        """
        return get_stream_url(path)

    @server.tool()
    def get_browse_tool(path: str = '') -> dict:
        """List a directory of the music library (folders and audio files).

        Args:
            path: directory path; empty = music root
        """
        return get_browse(path)

    return server


# ── selftest ───────────────────────────────────────────────────────────────────
def _selftest_music_root(root: Path, title: str):
    """Create a small real MP3 and a FLAC with ID3/Vorbis tags for the selftest."""
    root.mkdir(parents=True, exist_ok=True)
    albums = root / 'Artists' / 'Test Artist' / 'Test Album'
    albums.mkdir(parents=True, exist_ok=True)
    (albums / 'cover.jpg').write_bytes(b'\xff\xd8\xff\xe0' + b'0' * 64)

    mp3 = albums / 'Test Song.mp3'
    if not mp3.exists():
        frame = (b'TIT2' + b'\x00\x00\x00\x00\x00\x00' + title.encode())
        id3 = b'ID3\x04\x00\x00\x00\x00\x00\x00' + frame
        mp3.write_bytes(id3 + b'\xff\xfb\x90' + (b'\x00' * 512))

    flac = albums / 'Test Flac.flac'
    if not flac.exists():
        import struct
        # Minimal valid FLAC: 'fLaC' + STREAMINFO block (sample_rate=44100, 2ch, 16bit)
        si = struct.pack('>HH', 4096, 4096)
        si += b'\x00\x00\x00' + b'\x00\x00\x00'           # min/max framesize (unknown)
        packed = (44100 << 44) | (1 << 41) | (15 << 36)   # sr|ch-1|bps-1|samples
        si += struct.pack('>Q', packed) + b'\x00' * 16    # 8B header + md5
        flac.write_bytes(b'fLaC' + b'\x80\x00\x00\x22' + si)
        from mutagen.flac import FLAC
        f = FLAC(flac)
        f['title'] = title
        f['artist'] = 'Test Artist'
        f['album'] = 'Test Album'
        f.save()
    return root


def run_selftest(argv):
    ap = argparse.ArgumentParser(prog='mcp_server.py --selftest')
    ap.add_argument('--music-root', default='./sample_music')
    ap.add_argument('--http-url', default='')
    ap.add_argument('--http-key', default='')
    args = ap.parse_args(argv)

    if args.http_url:
        os.environ['MP3Z_BASE_URL'] = args.http_url
        if args.http_key:
            os.environ['MP3Z_API_KEY'] = args.http_key
    else:
        root = Path(args.music_root).resolve()
        os.environ['MUSIC_ROOT'] = str(root)
        os.environ.setdefault('MP3Z_STREAM_BASE', 'http://localhost')
        _selftest_music_root(root, 'MCP Test Song')

    global CONF
    CONF = Config()
    if not CONF.list_roots():
        print('ERROR: no music root configured')
        return 1

    results = []
    try:
        r = search_tracks('test', 10)
        print('search_tracks("test"):', json.dumps(r, ensure_ascii=False)[:400])
        assert r['total'] >= 1, 'search should find at least one track'
        assert all('path' in h and 'name' in h and 'source' in h for h in r['results']), \
            'hits need name/path/source'
        results.append('search_tracks')

        tp = r['results'][0]['path']
        r = get_track_info(tp)
        print('get_track_info:', json.dumps(r, ensure_ascii=False))
        assert r.get('name'), 'missing name'
        assert r.get('size', 0) > 0, 'missing size'
        assert r.get('format'), 'missing format'
        results.append('get_track_info')

        r = get_stream_url(tp)
        print('get_stream_url:', json.dumps(r, ensure_ascii=False))
        assert '/api/stream?' in r['url'], 'stream URL missing /api/stream'
        assert 'path=' in r['url'], 'stream URL missing path param'
        results.append('get_stream_url')

        r = get_browse('')
        print('get_browse(""):', json.dumps(r, ensure_ascii=False)[:400])
        assert r['total'] >= 1, 'browse should list entries'
        assert all('type' in e and 'path' in e for e in r['entries']), \
            'entries need type/path'
        results.append('get_browse')

        if not CONF.http_mode:
            for bad in ('../../etc/passwd', 'Artists/../..', '..'):
                try:
                    safe_local_path(bad)
                    print(f'TRAVERSAL NOT BLOCKED: {bad!r}')
                    return 1
                except ValueError:
                    pass
            print('path traversal protection: OK')
            results.append('traversal-protection')
    except Exception as e:
        print(f'SELFTEST FAILED: {e}', file=sys.stderr)
        return 1

    print(f'SELFTEST OK: {", ".join(results)}')
    return 0


# ── entrypoint ─────────────────────────────────────────────────────────────────
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == '--selftest':
        return run_selftest(argv[1:])

    ap = argparse.ArgumentParser(prog='mcp_server.py')
    ap.add_argument('--http', action='store_true',
                    help='serve streamable HTTP instead of stdio')
    ap.add_argument('--port', type=int, default=8000,
                    help='port for --http (default 8000)')
    args = ap.parse_args(argv)

    if not CONF.http_mode and not CONF.list_roots():
        print('WARNING: no MUSIC_ROOT / MUSIC_ROOTS set; search/browse will return empty. '
              'Set MUSIC_ROOT or MP3Z_BASE_URL (HTTP mode).', file=sys.stderr)

    server = build_server(port=args.port)
    transport = 'streamable-http' if args.http else 'stdio'
    server.run(transport=transport)
    return 0


if __name__ == '__main__':
    sys.exit(main())
