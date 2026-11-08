"""Serve original music themes without changing playback or authentication."""
from pathlib import Path


def install_themes(backend):
    from flask import request, Response

    @backend.app.get('/music-themes.js')
    def music_themes_script():
        return Response(Path(__file__).with_name('music-themes.js').read_text(),mimetype='application/javascript',headers={'Cache-Control':'no-store'})

    @backend.app.after_request
    def music_themes_html(response):
        if request.path=='/' and response.status_code==200:
            response.direct_passthrough=False
            html=response.get_data(as_text=True)
            if 'src="/music-themes.js"' not in html:
                response.set_data(html.replace('</body>','<script defer src="/music-themes.js"></script></body>'))
            response.headers.pop('ETag',None)
            response.headers.pop('Last-Modified',None)
            response.headers['Cache-Control']='no-store'
        return response
