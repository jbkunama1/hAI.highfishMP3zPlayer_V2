"""Shared read operations and scoped temporary stream links."""
import base64
import hashlib
import os
import secrets
import threading
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit, urlencode


def public_url(value):
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('PUBLIC_URL must be an HTTPS origin, without credentials/path/query')
    return value.rstrip('/')


class Library:
    def __init__(self, backend):
        self.b = backend
        self.links = OrderedDict()
        self.lock = threading.RLock()

    def path(self, value):
        if not isinstance(value, str) or len(value)>4096:
            raise ValueError('Invalid path')
        if value.startswith(('/', chr(92))) or any(p.startswith('.') or ':' in p or chr(0) in p for p in value.replace(chr(92),'/').split('/') if p):
            raise ValueError('Visible relative paths only')
        return value.replace(chr(92),'/').strip('/')

    def api(self, route, params=None, binary=False):
        endpoint = {'/api/browse':'browse','/api/search':'search','/api/art':'art','/api/index-status':'index_status'}[route]
        with self.b.app.test_request_context(route, query_string=params or {}):
            response = self.b.app.make_response(self.b.app.view_functions[endpoint].__wrapped__())
            try:
                response.direct_passthrough = False
                if response.status_code != 200:
                    raise ValueError('Library request failed')
                if binary:
                    data = response.get_data()
                    if len(data)>8*1024*1024: raise ValueError('Cover exceeds 8 MiB')
                    return data
                return response.get_json()
            finally:
                response.close()

    def browse(self, path='', offset=0, limit=8):
        return self.api('/api/browse', {'path':self.path(path),'offset':max(0,int(offset)),'limit':max(1,min(100,int(limit)))})

    def search(self, query, offset=0, limit=8):
        return self.api('/api/search', {'q':str(query)[:200],'offset':max(0,int(offset)),'limit':max(1,min(100,int(limit)))})

    def status(self):
        data = self.api('/api/index-status')
        return {k:v for k,v in data.items() if k != 'music_root'}

    def cover(self, path):
        return self.api('/api/art', {'path':self.path(path)}, binary=True)

    def stream_link(self, path):
        base = public_url(os.getenv('PUBLIC_URL',''))
        rel = self.path(path)
        if Path(rel).suffix.lower() not in self.b.AUDIO_EXTS or not self.b.STORAGE.isfile(rel):
            raise ValueError('Track not found')
        now = time.time()
        with self.lock:
            self.links = OrderedDict((k,v) for k,v in self.links.items() if v[1]>now)
            token = secrets.token_urlsafe(32)
            self.links[hashlib.sha256(token.encode()).digest()] = (rel, now+600)
            while len(self.links)>1024: self.links.popitem(last=False)
        return {'url':base+'/api/stream?'+urlencode({'path':rel,'media_token':token}), 'expires_in':600}

    def valid_link(self, path, token):
        if not isinstance(token,str) or len(token)>128: return False
        with self.lock:
            entry = self.links.get(hashlib.sha256(token.encode()).digest())
            return bool(entry and entry[0]==path and entry[1]>time.time())


def install_library(server, backend):
    lib = Library(backend)
    from flask import request, jsonify

    @backend.app.before_request
    def temporary_media():
        if request.path == '/api/stream' and request.args.get('media_token'):
            if request.method not in ('GET','HEAD') or not lib.valid_link(request.args.get('path',''),request.args['media_token']):
                return jsonify(error='Invalid or expired media link'),401
            return backend.app.view_functions['stream'].__wrapped__()

    @server.tool()
    def browse_library(path: str = '', offset: int = 0, limit: int = 50) -> dict:
        """Browse folders with pagination; paths are relative to the music root."""
        return lib.browse(path,offset,limit)

    @server.tool()
    def library_status() -> dict:
        """Read library index status without storage paths or credentials."""
        return lib.status()

    @server.tool()
    def read_cover(path: str) -> dict:
        """Read cover as base64, maximum 8 MiB."""
        return {'image_base64':base64.b64encode(lib.cover(path)).decode()}

    @server.tool()
    def get_stream_link(path: str) -> dict:
        """Create a shareable, track-scoped stream link valid for ten minutes; no permanent API key."""
        return lib.stream_link(path)
    return lib
