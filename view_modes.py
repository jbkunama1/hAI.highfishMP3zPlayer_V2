"""Serve optional view selection without replacing playback or search code."""
from pathlib import Path


def install_views(backend):
    from flask import request, Response

    @backend.app.get('/view-modes.js')
    def view_modes_script():
        response=Response(Path(__file__).with_name('view-modes.js').read_text(),mimetype='application/javascript')
        response.headers['Cache-Control']='no-store'
        return response

    @backend.app.after_request
    def add_view_modes(response):
        if request.path == '/' and response.status_code == 200:
            response.direct_passthrough=False
            response.set_data(response.get_data(as_text=True).replace('</body>','<script src="/view-modes.js"></script></body>'))
            response.headers.pop('ETag',None)
            response.headers.pop('Last-Modified',None)
            response.headers['Cache-Control']='no-store'
        return response
