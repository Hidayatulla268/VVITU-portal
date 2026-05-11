"""
VVIT Portal — Production Settings
===================================
This file is loaded on Render / Railway (and any other cloud host).
It imports everything from the base settings.py and then overrides
the handful of values that must change in a live environment:
  • DEBUG must be False (security critical)
  • SECRET_KEY must come from an environment variable, never hardcoded
  • Database must be PostgreSQL (SQLite doesn't work on ephemeral cloud disks)
  • Static files served by WhiteNoise (no separate Nginx needed on free tier)
  • Allowed hosts pulled from the env so the same file works on any domain
"""

import os
from .settings import *          # pull in every base setting first

# ── Security ────────────────────────────────────────────────────────────────
DEBUG      = False
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)  # override with env var

# Render / Railway set ALLOWED_HOSTS automatically via environment.
# If it's not set we still add localhost so manage.py commands don't error.
_hosts_env   = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _hosts_env.split(',') if h.strip()] or ['localhost', '127.0.0.1']

# Allow all subdomains of onrender.com and up.railway.app automatically
ALLOWED_HOSTS += ['.onrender.com', '.up.railway.app']

# ── Database (PostgreSQL from DATABASE_URL env var) ─────────────────────────
# Render and Railway both inject DATABASE_URL automatically when you attach
# a Postgres service to your project.  dj-database-url parses that URL into
# the dict Django expects.  We fall back to SQLite only when the env var is
# absent (useful for testing the prod settings locally).
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES = {'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)}
    except ImportError:
        # dj-database-url not installed — parse the URL manually
        # Format: postgres://USER:PASSWORD@HOST:PORT/NAME
        import urllib.parse as up
        r = up.urlparse(DATABASE_URL)
        DATABASES = {
            'default': {
                'ENGINE':   'django.db.backends.postgresql',
                'NAME':     r.path.lstrip('/'),
                'USER':     r.username,
                'PASSWORD': r.password,
                'HOST':     r.hostname,
                'PORT':     str(r.port or 5432),
            }
        }
# If DATABASE_URL is absent we keep the SQLite default from settings.py.

# ── Static files (WhiteNoise serves them directly from Gunicorn) ─────────────
# This removes the need for a separate Nginx static-file server on free-tier
# deployments, which can't run multiple processes.
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Make sure WhiteNoise middleware is right after SecurityMiddleware
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# ── HTTPS / cookie security ──────────────────────────────────────────────────
# These settings prevent session hijacking over plain HTTP.
# Only enable them when you are behind HTTPS (Render/Railway provide it).
SECURE_SSL_REDIRECT         = True
SESSION_COOKIE_SECURE       = True
CSRF_COOKIE_SECURE          = True
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'

# Tell Django it's sitting behind the cloud provider's HTTPS proxy.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── Email (configure via environment variables) ──────────────────────────────
EMAIL_BACKEND       = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST          = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# ── Logging (surface errors in Render / Railway log viewer) ─────────────────
LOGGING = {
    'version':                  1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style':  '{',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level':    'WARNING',
    },
    'loggers': {
        'django': {
            'handlers':  ['console'],
            'level':     os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
    },
}
