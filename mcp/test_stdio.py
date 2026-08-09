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


class _LineReader:
    """Buffered line reader over a pipe that returns None at EOF, not a block."""

    def __init__(self, proc):
        self._buf = b''
        self._p = proc

    def next(self):
        while b'\n' not in self._buf:
            chunk = self._p.stdout.read(1)
            if not chunk:  # EOF
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return line.decode('utf-8').strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--music-root', default=str(HERE / 'sample_music'))
    args = ap.parse_args()

    env = dict(os.environ)
    env['MUSIC_ROOT'] = str(Path(args.music_root).resolve())
    env.pop('MUSIC_ROOTS', None)
    env.pop('MP3Z_BASE_URL', None)

    proc = subprocess.Popen(
        [sys.executable, str(HERE / 'mcp_server.py')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=HERE, env=env,
    )

    def send(req):
        proc.stdin.write(json.dumps(req).encode('utf-8') + b'\n')
        proc.stdin.flush()

    def read_response():
        # Read lines until one parses as a response with an 'id' we can use,
        # with a bounded timeout so a hung server surfaces as a test failure.
        reader = _LineReader(proc)
        line, deadline = reader.next(), time.time() + 15
        while line is not None:
            if time.time() > deadline:
                raise TimeoutError('no response from server within 15s')
            try:
                msg = json.loads(line)
            except ValueError:
                line, deadline = reader.next(), time.time() + 15
                continue
            if 'id' in msg:
                return msg
            line, deadline = reader.next(), time.time() + 15
        raise TimeoutError('server closed stdout before returning a response')

    try:
        # Send the MCP handshake + list first (blocking responses confirm each step),
        # then the search call. Interleaving keeps the server's stdio loop alive so
        # the final response is written before we terminate the process.
        send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
              'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                        'clientInfo': {'name': 'stdio-test', 'version': '1'}}})
        send({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}})
        send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
        send({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
              'params': {'name': 'search_tracks_tool', 'arguments': {'query': 'test', 'limit': 5}}})

        init = read_response()
        assert init.get('id') == 1 and init['result']['serverInfo']['name'] == 'mp3z', init
        print('initialize OK —', init['result']['serverInfo'])

        tlist = read_response()
        names = sorted(t['name'] for t in tlist['result']['tools'])
        assert names == ['get_browse_tool', 'get_stream_url_tool', 'get_track_info_tool', 'search_tracks_tool'], names
        print('tools/list OK —', names)

        call = read_response()
        text = call['result']['content'][0]['text']
        data = json.loads(text)
        assert data['total'] >= 1, data
        print('search_tracks via stdio OK —', text[:160])
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        stderr = proc.stderr.read().decode('utf-8', 'replace')
        if stderr.strip():
            print('stderr:', stderr[:500], file=sys.stderr)
    print('STDIO SMOKE TEST OK')


if __name__ == '__main__':
    main()