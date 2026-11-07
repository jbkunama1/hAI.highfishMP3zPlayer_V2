"""Run authenticated MCP and the existing player on one HTTP port."""
import hashlib
import os
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from metadata_service import MetadataService, BearerAuth, enabled


def build_mcp(service, backend):
    from mcp.server.fastmcp import FastMCP
    transport_factory = globals().get('mcp_transport_security')
    kwargs = {'stateless_http': True, 'json_response': True}
    if transport_factory:
        kwargs['transport_security'] = transport_factory()
    server = FastMCP('MP3z', **kwargs)

    @server.tool()
    def read_id3(path: str) -> dict:
        """Read MP3 tags and revision; paths are relative to configured music root."""
        return service.read(path)

    @server.tool()
    def update_id3(path: str, tags: dict[str, str], revision: str) -> dict:
        """Write specified MP3 tags after user approval. Creates backup. Reload revision first."""
        if not enabled('MCP_WRITE_ENABLED'):
            raise PermissionError('MCP writes disabled')
        return service.update(path, tags, revision)

    @server.tool()
    def search_tracks(query: str, offset: int = 0, limit: int = 50) -> dict:
        """Search filenames and folder names, with pagination."""
        q = query.lower().strip()
        if len(q) < 2:
            return {'results': [], 'total': 0}
        hits = [e for e in backend.index.get() if q in e['name'].lower() or q in e['dir'].lower()]
        offset, limit = max(0, offset), max(1, min(500, limit))
        return {'results': hits[offset:offset+limit], 'total':len(hits), 'offset':offset}
    return server


def main():
    import mp3z_server as backend
    import uvicorn
    from flask import request, jsonify, Response, send_file
    from starlette.applications import Starlette
    from starlette.middleware.wsgi import WSGIMiddleware
    from starlette.routing import Mount
    from player_bootstrap import patch_player
    key = os.getenv('API_KEY_OVERRIDE', '')
    if not key or key != key.strip():
        raise RuntimeError('Explicit API_KEY_OVERRIDE required; SMB password fallback disabled')
    backend.API_KEY = key
    backend.API_KEY_HASH = hashlib.sha256(key.encode()).hexdigest()
    service = MetadataService(backend.STORAGE)
    app = backend.app
    app.config['MAX_CONTENT_LENGTH'] = 32768

    @app.before_request
    def editor_auth():
        if request.path.startswith('/api/id3'):
            if not backend.check_token(request.headers.get('X-API-Key', '')):
                return jsonify(error='Unauthorized'), 401

    @app.after_request
    def frontend(response):
        if request.path == '/' and response.status_code == 200:
            response.direct_passthrough = False
            html = patch_player(response.get_data(as_text=True))
            html = html.replace('</body>', '<a href="/id3-editor" style="position:fixed;right:12px;top:65px;z-index:190;background:var(--surf);color:var(--text);padding:10px">ID3-Editor</a></body>')
            response.set_data(html)
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
        if request.path == '/' or request.path.startswith('/api/') or request.path == '/id3-editor':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/player-themes.js')
    def themes():
        return Response(Path(__file__).with_name('player-themes.js').read_text(), mimetype='application/javascript')

    @app.get('/id3-editor')
    def editor():
        return send_file(Path(__file__).with_name('id3-editor.html'))

    @app.route('/api/id3', methods=['GET', 'POST'])
    def id3():
        try:
            if request.method == 'GET':
                return jsonify(service.read(request.args.get('path', '')))
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                raise ValueError('JSON object required')
            result = service.update(data.get('path', ''), data.get('tags'), data.get('revision'))
            app.logger.info('ID3 updated: %r; backup: %r', result['path'], result['backup'])
            return jsonify(result)
        except PermissionError as exc:
            return jsonify(error=str(exc)), 403
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except FileNotFoundError:
            return jsonify(error='Track not found'), 404
        except Exception:
            app.logger.warning('ID3 storage operation failed')
            return jsonify(error='Storage operation failed; check permissions and backups'), 502

    mcp = build_mcp(service, backend)
    gated = BearerAuth(mcp.streamable_http_app(), os.getenv('MCP_API_KEY', ''))

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    asgi = Starlette(routes=[Mount('/agent', app=gated), Mount('/', app=WSGIMiddleware(app))], lifespan=lifespan)
    threading.Thread(target=backend.index._build, daemon=True).start()
    uvicorn.run(asgi, host=backend.HOST, port=backend.PORT, access_log=False)


if __name__ == '__main__':
    main()
