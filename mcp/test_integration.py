"""Multi-root + HTTP-mode integration checks for mcp_server.py (no MCP client needed)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

sample = (Path(__file__).parent / 'sample_music').resolve()


def local_multiroot():
    os.environ['MUSIC_ROOT'] = ''
    os.environ['MUSIC_ROOTS'] = json.dumps({'usb': str(sample), 'nas': str(sample)})
    os.environ.pop('MP3Z_BASE_URL', None)
    import mcp_server
    mcp_server.CONF = mcp_server.Config()
    assert set(mcp_server.CONF.list_roots()) == {'usb', 'nas'}, mcp_server.CONF.list_roots()

    r = mcp_server.search_tracks('test', 5)
    assert r['total'] >= 1, r
    assert all(h['path'].startswith('usb/') or h['path'].startswith('nas/')
               for h in r['results']), r
    print('multi-root search OK:', json.dumps(r['results'][0]))

    b = mcp_server.get_browse('usb')
    assert b['total'] >= 1 and all(e['path'].startswith('usb/') for e in b['entries']), b
    print('multi-root browse OK:', json.dumps(b['entries'][0]))

    for bad in ('usb/../../etc/passwd', 'nas/..'):
        try:
            mcp_server.safe_local_path(bad)
            raise AssertionError(f'traversal allowed: {bad!r}')
        except ValueError:
            pass
    print('multi-root traversal OK')


def http_mode():
    base = os.environ.get('MP3Z_TEST_URL')
    if not base:
        print('http-mode: skipped (set MP3Z_TEST_URL to test)')
        return
    os.environ['MUSIC_ROOT'] = ''
    os.environ['MP3Z_BASE_URL'] = base
    os.environ['MP3Z_API_KEY'] = os.environ.get('MP3Z_TEST_KEY', '')
    import mcp_server
    mcp_server.CONF = mcp_server.Config()
    assert mcp_server.CONF.http_mode
    r = mcp_server.search_tracks('test', 5)
    print('http search:', json.dumps(r, ensure_ascii=False)[:300])
    u = mcp_server.get_stream_url(r['results'][0]['path'])
    print('http stream url:', u['url'])


if __name__ == '__main__':
    local_multiroot()
    http_mode()
    print('ALL INTEGRATION CHECKS PASSED')
