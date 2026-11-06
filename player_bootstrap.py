"""Serve the existing player with same-origin fixes and optional themes."""
from pathlib import Path
import threading


def patch_player(html):
    html = html.replace('fetch(url + endpoint', 'fetch(baseUrl + endpoint')
    html = html.replace("baseUrl || 'http://localhost'", "baseUrl || location.origin")
    html = html.replace("localStorage.getItem('mp3z_url')    || ''", "localStorage.getItem('mp3z_url')    || location.origin")
    return html.replace('</body>', '<script src="/player-themes.js"></script></body>')


def main():
    import mp3z_server as backend
    from flask import Response, request

    @backend.app.after_request
    def fix_player(response):
        if request.path == '/' and response.status_code == 200:
            response.direct_passthrough = False
            response.set_data(patch_player(response.get_data(as_text=True)))
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
            response.headers['Cache-Control'] = 'no-store'
        return response

    @backend.app.get('/player-themes.js')
    def themes():
        return Response(Path(__file__).with_name('player-themes.js').read_text(), mimetype='application/javascript')

    threading.Thread(target=backend.index._build, daemon=True).start()
    backend.app.run(host=backend.HOST, port=backend.PORT, threaded=True)


if __name__ == '__main__':
    main()
