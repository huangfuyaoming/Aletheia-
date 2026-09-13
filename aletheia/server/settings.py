import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings():
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('\"\''))
    production = os.getenv('APP_ENV', 'development') == 'production'
    secret = os.getenv('SECRET_KEY')
    # The access-key gate was removed by request: the site is open to anyone with
    # the URL. SECRET_KEY stays mandatory in production because it signs visitor
    # cookies, and rotating it would orphan every visitor's saved history.
    if production and (not secret or len(secret) < 32):
        raise RuntimeError('Production requires SECRET_KEY (32+ chars).')
    data = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
    return dict(
        SECRET_KEY=secret or secrets.token_hex(32),
        DATA_DIR=data, DATABASE=data / 'aletheia.sqlite3',
        LEGACY_ROOT=Path(os.getenv('LEGACY_ROOT', '/root/autodl-tmp/sys_all')).resolve(),
        LEGACY_MODULE=os.getenv('LEGACY_MODULE', 'sys.py'),
        MAX_CONTENT_LENGTH=(int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024) + 65536,
        MAX_UPLOAD_BYTES=int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024,
        MAX_IMAGE_PIXELS=int(os.getenv('MAX_IMAGE_PIXELS', '16000000')),
        TRUFOR_MAX_SIDE=int(os.getenv('TRUFOR_MAX_SIDE', '1536')),
        QUEUE_CAPACITY=int(os.getenv('QUEUE_CAPACITY', '8')),
        RETENTION_DAYS=int(os.getenv('RETENTION_DAYS', '30')),
        PUBLIC_ORIGIN=os.getenv('PUBLIC_ORIGIN', '').rstrip('/'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', '0') == '1',
        LLM_URL=os.getenv('LLM_URL', ''), LLM_API_KEY=os.getenv('LLM_API_KEY', ''),
        LLM_MODEL=os.getenv('LLM_MODEL', ''), LLM_TIMEOUT=int(os.getenv('LLM_TIMEOUT', '90')),
        PRODUCTION=production,
    )
