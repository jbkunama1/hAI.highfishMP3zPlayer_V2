"""Raw stdio JSON-RPC smoke test for mcp_server.py — needs no MCP client SDK.

Spawns the server, sends initialize + tools/list + a tools/call, asserts plausible
results, then shuts down. Usage: python test_stdio.py [--music-root PATH]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--music-root', default=str(HERE / 'sample_music'))
    args = ap.parse_args()

    env = dict(os.environ)
    env['MUSIC_ROOT'] = str(Path(args.music_root).resolve())
    env.pop('MUSIC_ROOTS', None)
    env.pop('MP3Z_BASE_URL', None)

    # Build requests: initialize, tools/list, search_tracks
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                    'clientInfo': {'name': 'stdio-test', 'version': '1'}}},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
         'params': {'name': 'search_tracks', 'arguments': {'query': 'test', 'limit': 5}}},
    ]
    payload = '\n'.join(json.dumps(r) for r in requests).encode('utf-8') + b'\n'

    proc = subprocess.Popen(
        [sys.executable, str(HERE / 'mcp_server.py')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=HERE, env=env,
    )
    try:
        stdout, stderr = proc.communicate(input=payload, timeout=15)
        lines = [l for l in stdout.decode('utf-8').strip().split('\n') if l.strip()]
        print(f'received {len(lines)} lines')

        init = json.loads(lines[0])
        assert init['result']['serverInfo']['name'] == 'mp3z', init
        print('initialize OK —', init['result']['serverInfo'])

        tlist = json.loads(lines[1])
        names = sorted(t['name'] for t in tlist['result']['tools'])
        assert names == ['get_browse', 'get_stream_url', 'get_track_info', 'search_tracks'], names
        print('tools/list OK —', names)

        call = json.loads(lines[2])
        text = call['result']['content'][0]['text']
        data = json.loads(text)
        assert data['total'] >= 1, data
        print('search_tracks via stdio OK —', text[:160])
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
        stderr = stderr.decode('utf-8', 'replace')
        if stderr.strip():
            print('stderr:', stderr[:500], file=sys.stderr)
    print('STDIO SMOKE TEST OK')


if __name__ == '__main__':
    main()