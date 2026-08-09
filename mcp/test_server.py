"""Test MCP server tools via direct function calls (no JSON-RPC transport)."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent


def test_tools():
    # Use the same import approach that would happen in a real MCP client
    sys.path.insert(0, str(HERE))

    os.environ['MUSIC_ROOT'] = str((HERE / 'sample_music').resolve())
    os.environ.pop('MUSIC_ROOTS', None)
    os.environ.pop('MP3Z_BASE_URL', None)
    os.environ['MP3Z_STREAM_BASE'] = 'http://localhost'

    import mcp_server

    # Test search_tracks
    r = mcp_server.search_tracks('test', 5)
    assert r['total'] >= 1, r
    assert all('path' in h and 'name' in h and 'source' in h for h in r['results']), r
    print('search_tracks OK — found', r['total'], 'tracks')

    # Test get_track_info using the first result's path
    path = r['results'][0]['path']
    r = mcp_server.get_track_info(path)
    assert r.get('name'), 'missing name'
    assert r.get('size', 0) > 0, 'missing size'
    assert r.get('format'), 'missing format'
    print('get_track_info OK —', r.get('title'), r.get('artist'))

    # Test get_stream_url using the same path
    r = mcp_server.get_stream_url(path)
    assert '/api/stream?' in r['url'], r['url']
    assert 'path=' in r['url'], r['url']
    print('get_stream_url OK —', r['url'][:60])

    # Test get_browse
    r = mcp_server.get_browse('')
    assert r['total'] >= 1, r
    assert all('type' in e and 'path' in e for e in r['entries']), r
    print('get_browse OK —', r['total'], 'entries')

    # Traversal protection test
    for bad in ('../../etc/passwd', 'Artists/../..', '..'):
        try:
            mcp_server.safe_local_path(bad)
            raise AssertionError(f'traversal allowed: {bad!r}')
        except ValueError:
            pass
    print('traversal protection OK')

    # Multi-root mode (if configured)
    if 'MUSIC_ROOTS' in os.environ:
        print('MUSIC_ROOTS present, skipping separate multi-root test')
    else:
        os.environ['MUSIC_ROOT'] = ''
        os.environ['MUSIC_ROOTS'] = json.dumps({'usb': str(HERE / 'sample_music')})
        # Re-import with new config
        import importlib
        importlib.reload(mcp_server)
        r = mcp_server.search_tracks('test', 2)
        assert any(h['path'].startswith('usb/') for h in r['results']), r
        print('multi-root search OK')

    print('ALL TOOL TESTS PASSED')


if __name__ == '__main__':
    test_tools()