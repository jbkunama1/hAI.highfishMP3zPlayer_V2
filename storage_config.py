"""Select exactly one storage backend before importing mp3z_server."""
import os
from pathlib import Path


def configure_storage(env=None):
    env = os.environ if env is None else env
    mode = env.get('STORAGE_MODE', 'host').strip().lower()
    if mode not in ('host', 'local', 'smb'):
        raise ValueError('STORAGE_MODE must be host or smb (local is a host alias)')
    if mode in ('host', 'local'):
        root = env.get('MUSIC_ROOT', '').strip()
        if not root or not Path(root).is_absolute():
            raise ValueError('Host mode requires an absolute MUSIC_ROOT; no fallback is allowed')
        path = Path(root)
        if not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
            raise ValueError('Host MUSIC_ROOT must exist and be readable inside the container; check the bind mount')
        env['MUSIC_ROOT'] = root
        env['STORAGE_MODE'] = 'local'
        # The legacy backend parses this even in local mode; inactive SMB input must not break host startup.
        env['SMB_PORT'] = '445'
        return 'host'
    missing = [key for key in ('SMB_HOST', 'SMB_SHARE', 'SMB_USER', 'SMB_PASS') if not env.get(key, '').strip()]
    if missing:
        raise ValueError('SMB mode requires: ' + ', '.join(missing))
    base = env.get('SMB_PATH', '').replace('\\', '/')
    if base.startswith('/') or any(p == '..' or ':' in p or '\x00' in p for p in base.split('/')):
        raise ValueError('SMB_PATH must be relative to the share and must not escape it')
    try:
        port = int(env.get('SMB_PORT', '445') or '445')
    except ValueError:
        raise ValueError('SMB_PORT must be an integer') from None
    if not 1 <= port <= 65535:
        raise ValueError('SMB_PORT must be between 1 and 65535')
    env['STORAGE_MODE'] = 'smb'
    env['SMB_PORT'] = str(port)
    env['MUSIC_ROOT'] = ''
    return 'smb'
