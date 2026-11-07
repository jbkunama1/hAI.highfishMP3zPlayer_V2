"""Validated cover uploads for embedded MP3 artwork and folder cover.jpg."""
import base64
import binascii
import hashlib
import io
import os
import secrets
import shutil
import stat
import uuid
import warnings
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from metadata_service import MetadataService, LOCK, LIMIT, enabled

MAX_IMAGE = 8 * 1024 * 1024
MAX_PIXELS = 16000000


def normalize_image(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMAGE:
        raise ValueError('Image required; maximum 8 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                if img.format not in ('JPEG', 'PNG', 'WEBP') or getattr(img, 'n_frames', 1) != 1:
                    raise ValueError('Only single-frame JPEG, PNG or WEBP')
                if img.width * img.height > MAX_PIXELS:
                    raise ValueError('Maximum 16 megapixels')
                img.load()
                img = ImageOps.exif_transpose(img)
                rgba = img.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                background.alpha_composite(rgba)
                rgb = background.convert('RGB')
                rgb.thumbnail((1600, 1600))
                out = io.BytesIO()
                rgb.save(out, format='JPEG', quality=90)
                return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Invalid or unsafe image') from exc


class CoverService(MetadataService):
    def folder_target(self, value):
        if not isinstance(value, str) or len(value) > 4000:
            raise ValueError('Invalid folder')
        rel = value.replace(chr(92), '/')
        parts = rel.split('/') if rel else []
        if any(not p or p.startswith('.') or ':' in p or chr(0) in p for p in parts):
            raise ValueError('Only visible relative folders allowed')
        dest = (rel + '/' if rel else '') + 'cover.jpg'
        if self.s.mode == 'local':
            folder = self.s._full(rel)
            cur = self.s.root.resolve()
            for part in parts + ['cover.jpg']:
                cur = cur / part
                if cur.is_symlink():
                    raise ValueError('Symlinks not allowed')
            if not folder.is_dir():
                raise ValueError('Folder not found')
            self.s._full(dest)
        else:
            self.s._login()
            cur = ''
            for part in parts + ['cover.jpg']:
                cur = (cur + '/' + part).lstrip('/')
                try:
                    info = self.s.sc.lstat(self.s._unc(cur), port=self.s.port)
                except FileNotFoundError:
                    if cur == dest:
                        continue
                    raise
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('SMB links/reparse points not allowed')
            if not self.s.sc.path.isdir(self.s._unc(rel), port=self.s.port):
                raise ValueError('Folder not found')
        return dest

    def current(self, path, target):
        if target == 'embedded':
            rel = self.path(path)
            return rel, self.read_bytes(rel)
        if target != 'folder':
            raise ValueError('Target must be embedded or folder')
        rel = self.folder_target(path)
        try:
            data = self.read_bytes(rel)
        except FileNotFoundError:
            data = None
        if data is not None and len(data) > MAX_IMAGE:
            raise ValueError('Existing cover exceeds 8 MiB')
        return rel, data

    def inspect(self, path, target='embedded'):
        with LOCK:
            rel, data = self.current(path, target)
            return {'path': rel, 'target': target,
                    'revision': hashlib.sha256(data).hexdigest() if data is not None else 'missing'}

    def replace(self, rel, data, original):
        folder, _, name = rel.rpartition('/')
        prefix = folder + '/' if folder else ''
        ident = uuid.uuid4().hex
        backup = prefix + '.mp3z-' + ident + '-' + name + '.bak' if original is not None else None
        temp = prefix + '.mp3z-' + ident + '.tmp'
        if self.s.mode == 'local':
            dst, tmp = self.s._full(rel), self.s._full(temp)
            try:
                with open(tmp, 'xb') as out:
                    out.write(data); out.flush(); os.fsync(out.fileno())
                if backup:
                    shutil.copy2(dst, self.s._full(backup))
                    shutil.copymode(dst, tmp)
                os.replace(tmp, dst)
            finally:
                tmp.unlink(missing_ok=True)
        else:
            sc, port = self.s.sc, self.s.port
            if backup:
                with sc.open_file(self.s._unc(backup), mode='xb', port=port) as out:
                    out.write(original)
            try:
                with sc.open_file(self.s._unc(temp), mode='xb', port=port) as out:
                    out.write(data)
                if original is None and sc.path.exists(self.s._unc(rel), port=port):
                    raise ValueError('Cover appeared during upload; reload revision')
                sc.replace(self.s._unc(temp), self.s._unc(rel), port=port)
            finally:
                try:
                    sc.remove(self.s._unc(temp), port=port)
                except FileNotFoundError:
                    pass
        return backup

    def upload(self, path, image, target, revision):
        if not enabled('EDIT_ENABLED'):
            raise PermissionError('Cover writes disabled: EDIT_ENABLED=true required')
        image = normalize_image(image)
        with LOCK:
            rel, original = self.current(path, target)
            current = hashlib.sha256(original).hexdigest() if original is not None else 'missing'
            if not isinstance(revision, str) or not revision.isascii() or not secrets.compare_digest(revision, current):
                raise ValueError('Stale or missing revision: inspect cover again')
            data = image
            if target == 'embedded':
                buffer = io.BytesIO(original)
                try:
                    tags = ID3(buffer)
                except ID3NoHeaderError:
                    tags = ID3()
                kept = [pic for pic in tags.getall('APIC') if pic.type != 3]
                tags.delall('APIC')
                for pic in kept:
                    tags.add(pic)
                desc = 'MP3z front cover'
                while any(pic.desc == desc for pic in kept):
                    desc += '_'
                tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc=desc, data=image))
                tags.save(buffer, v2_version=4)
                data = buffer.getvalue()
                if len(data) > LIMIT:
                    raise ValueError('Result exceeds 128 MiB')
            backup = self.replace(rel, data, original)
            return {'ok': True, 'path': rel, 'target': target, 'backup': backup,
                    'revision': hashlib.sha256(data).hexdigest()}


def register_mcp(server, service):
    covers = CoverService(service.s)

    @server.tool()
    def inspect_cover(path: str, target: str = 'embedded') -> dict:
        """Get revision for one embedded MP3 cover or folder cover.jpg. Empty folder path means root."""
        return covers.inspect(path, target)

    @server.tool()
    def upload_cover(path: str, image_base64: str, revision: str, target: str = 'embedded') -> dict:
        """Upload validated JPEG/PNG/WEBP after user approval. Requires both write flags. Creates backup."""
        if not enabled('MCP_WRITE_ENABLED'):
            raise PermissionError('MCP writes disabled')
        if len(image_base64) > 4 * ((MAX_IMAGE + 2) // 3):
            raise ValueError('Image too large')
        try:
            data = base64.b64decode(image_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('Invalid base64') from exc
        return covers.upload(path, data, target, revision)


def install_web(backend, service):
    from flask import request, jsonify, Response
    from werkzeug.exceptions import RequestEntityTooLarge
    covers, app = CoverService(service.s), backend.app
    app.config['MAX_CONTENT_LENGTH'] = MAX_IMAGE + 65536

    @app.before_request
    def cover_auth():
        if request.path == '/api/cover-upload' and not backend.check_token(request.headers.get('X-API-Key', '')):
            return jsonify(error='Unauthorized'), 401

    @app.after_request
    def cover_headers(response):
        if request.path == '/id3-editor' and response.status_code == 200:
            response.direct_passthrough = False
            response.set_data(response.get_data(as_text=True).replace('</html>', '<script src="/cover-ui.js"></script></html>'))
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
        if request.path in ('/api/cover-upload', '/api/art', '/id3-editor'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/cover-ui.js')
    def cover_ui():
        return Response(Path(__file__).with_name('cover-ui.js').read_text(), mimetype='application/javascript')

    @app.route('/api/cover-upload', methods=['GET', 'POST'])
    def cover_upload():
        try:
            if request.method == 'GET':
                return jsonify(covers.inspect(request.args.get('path', ''), request.args.get('target', 'embedded')))
            f = request.files.get('cover')
            result = covers.upload(request.form.get('path', ''), f.read(MAX_IMAGE + 1) if f else b'',
                                   request.form.get('target', 'embedded'), request.form.get('revision', ''))
            app.logger.info('Cover updated: %r; backup: %r', result['path'], result['backup'])
            return jsonify(result)
        except RequestEntityTooLarge:
            return jsonify(error='Upload too large; maximum image size 8 MiB'), 413
        except PermissionError as exc:
            return jsonify(error=str(exc)), 403
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except FileNotFoundError:
            return jsonify(error='Target not found'), 404
        except Exception:
            app.logger.warning('Cover storage operation failed')
            return jsonify(error='Storage failure; check permissions and backups'), 502
