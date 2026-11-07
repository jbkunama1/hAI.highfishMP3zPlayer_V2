"""Dedicated app credentials and bounded, revocable in-memory sessions."""
import hashlib
import os
import re
import secrets
import threading
import time
from collections import OrderedDict


def digest(value):
    return hashlib.sha256(value.encode()).digest()


class AppLogin:
    def __init__(self, username, password):
        if not username or username != username.strip() or not password:
            raise ValueError('APP_USERNAME and APP_PASSWORD must be explicitly set')
        self.username = username
        self.user_hash, self.password_hash = digest(username), digest(password)
        self.sessions = OrderedDict()
        self.attempts = OrderedDict()
        self.lock = threading.RLock()

    def authenticate(self, username, password, peer, now=None):
        now = time.time() if now is None else now
        with self.lock:
            start, count = self.attempts.get(peer, (now, 0))
            if now - start >= 60:
                start, count = now, 0
            if count >= 10:
                return None, 429
            self.attempts[peer] = (start, count + 1)
            self.attempts.move_to_end(peer)
            while len(self.attempts) > 1024:
                self.attempts.popitem(last=False)
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 128 or len(password) > 4096:
                return None, 401
            user_ok = secrets.compare_digest(digest(username), self.user_hash)
            pass_ok = secrets.compare_digest(digest(password), self.password_hash)
            if not (user_ok and pass_ok):
                return None, 401
            self.sessions = OrderedDict((k,v) for k,v in self.sessions.items() if v > now)
            token = secrets.token_urlsafe(32)
            self.sessions[digest(token)] = now + 43200
            while len(self.sessions) > 256:
                self.sessions.popitem(last=False)
            return token, 200

    def valid(self, token, now=None):
        if not isinstance(token, str) or len(token) > 256:
            return False
        now = time.time() if now is None else now
        with self.lock:
            return self.sessions.get(digest(token), 0) > now

    def revoke(self, token):
        if isinstance(token, str):
            with self.lock:
                self.sessions.pop(digest(token), None)


def patch_login(html):
    replacements = {
        'Samba Player': 'Musikplayer',
        'Gib dein Samba-Passwort ein um auf deine Musiksammlung zuzugreifen.': 'Melde dich mit deinem MP3z-Benutzernamen und App-Passwort an.',
        'Passwort = Samba-Freigabe-Passwort': 'Eigener MP3z-Zugang, unabhaengig von Samba',
        'JSON.stringify({ apikey: pass })': 'JSON.stringify({ username: user, password: pass })',
        "const url   = baseUrl || 'http://localhost';": 'const url   = location.origin;',
        "localStorage.getItem('mp3z_url')    || ''": 'location.origin',
        "const newPass = $('s-pass').value;": "const newPass = '';",
        'function logout() {': "function logout() {\n  fetch('/api/logout', {method:'POST',headers:{'X-API-Key':apiKey}}).catch(()=>{}); audio.pause();",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    html, count = re.subn(r'apiKey\s*=\s*pass;', "apiKey = data.token; lPass.value = '';", html)
    if count != 1:
        raise ValueError('Login frontend changed; patch needs review')
    migration = "<script>if(localStorage.getItem('mp3z_auth_version')!=='app-v1'){localStorage.removeItem('mp3z_apikey');localStorage.removeItem('mp3z_user');localStorage.setItem('mp3z_auth_version','app-v1');}</script>"
    html = html.replace('<head>', '<head>' + migration)
    html = html.replace('</head>', "<style>.s-row:has(#s-pass){display:none}</style></head>")
    return html


def install_login(backend):
    from flask import request, jsonify
    auth = AppLogin(os.getenv('APP_USERNAME', ''), os.getenv('APP_PASSWORD', ''))
    original_check = backend.check_token
    backend.check_token = lambda token: auth.valid(token) or original_check(token)

    def verify():
        data = request.get_json(silent=True)
        data = data if isinstance(data, dict) else {}
        token, status = auth.authenticate(data.get('username'), data.get('password'), request.remote_addr or 'unknown')
        if token:
            return jsonify(ok=True, user=auth.username, token=token, expires_in=43200)
        response = jsonify(ok=False, error='Zu viele Versuche. Bitte warten.' if status == 429 else 'Benutzername oder App-Passwort falsch')
        if status == 429:
            response.headers['Retry-After'] = '60'
        return response, status

    backend.app.view_functions['verify'] = verify

    @backend.app.post('/api/logout')
    def app_logout():
        auth.revoke(request.headers.get('X-API-Key', ''))
        return jsonify(ok=True)

    @backend.app.after_request
    def login_frontend(response):
        if request.path == '/' and response.status_code == 200:
            response.direct_passthrough = False
            response.set_data(patch_login(response.get_data(as_text=True)))
            response.headers.pop('ETag', None)
            response.headers.pop('Last-Modified', None)
        if request.path in ('/', '/api/verify', '/api/logout'):
            response.headers['Cache-Control'] = 'no-store'
        return response
