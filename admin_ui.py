"""Authenticated, read-only single-account administration and index export."""
import csv
import io
import json
import time
from datetime import datetime, timezone


def csv_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t','\r','\n')) else value


def render_export(snapshot, fmt):
    if fmt == 'json':
        return json.dumps(snapshot, ensure_ascii=False, indent=2), 'application/json; charset=utf-8', 'json'
    if fmt != 'csv':
        raise ValueError('Format must be json or csv')
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['name','path','dir'])
    for entry in snapshot['entries']:
        writer.writerow([csv_safe(entry.get(k,'')) for k in ('name','path','dir')])
    return out.getvalue(), 'text/csv; charset=utf-8', 'csv'


def snapshot(backend):
    index=backend.index
    with index._lock:
        entries=[{k:e.get(k,'') for k in ('name','path','dir')} for e in index._entries]
        building=index._building;built=index._built
    return {'schema':'mp3z-index-v1','exported_at':datetime.now(timezone.utc).isoformat(),
            'storage_mode':backend.STORAGE.mode,'building':building,'indexed_at_unix':built,
            'total_files':len(entries),'entries':entries}


def install_admin(backend):
    from metadata_service import enabled
    from flask import request, jsonify, Response
    app=backend.app

    @app.before_request
    def admin_auth():
        if request.path.startswith('/api/admin/') and not backend.check_token(request.headers.get('X-API-Key','')):
            return jsonify(error='Unauthorized'),401

    @app.after_request
    def admin_headers(response):
        if request.path == '/id3-editor' and response.status_code == 200:
            response.direct_passthrough = False
            response.set_data(response.get_data(as_text=True).replace('</html>', '<script src="/player-themes.js"></script></html>'))
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
            response.headers['Cache-Control'] = 'no-store'
        if request.path.startswith('/api/admin/'):
            response.headers['Cache-Control']='no-store'
            response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.get('/api/admin/status')
    def admin_status():
        index=backend.index
        with index._lock:
            count=len(index._entries);building=index._building;built=index._built
        return jsonify(total_files=count,building=building,index_age_seconds=round(time.time()-built) if built else None,
                       storage_mode=backend.STORAGE.mode,edit_enabled=enabled('EDIT_ENABLED'),
                       mcp_write_enabled=enabled('MCP_WRITE_ENABLED'),telegram_enabled=enabled('TELEGRAM_ENABLED'),
                       database='in-memory file index; no persistent database')

    @app.get('/api/admin/export')
    def admin_export():
        try:
            data,mime,ext=render_export(snapshot(backend),request.args.get('format','json'))
        except ValueError as exc:
            return jsonify(error=str(exc)),400
        return Response(data,content_type=mime,headers={'Content-Disposition':f'attachment; filename="mp3z-index.{ext}"'})
