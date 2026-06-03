"""
VVITU Portal — Django Settings
Production-ready configuration for Vasireddy Venkatadri International Technological University ERP.
"""

import os
from pathlib import Path
from decouple import config, Csv

# ─────────────────────────────────────────────
# BASE PATHS
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────
# CORE SECURITY  (override via env vars / .env)
# ─────────────────────────────────────────────
SECRET_KEY = config(
    'DJANGO_SECRET_KEY',
    default='vvitu-dev-fallback-key-DO-NOT-USE-in-production-replace-me-immediately-2024'
)

DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='*', cast=Csv())

# ── Production HTTPS / Cookie security ──────
# These are SAFE to leave as-is in dev (DEBUG=True bypasses most of them).
# In production set DJANGO_DEBUG=False and point to your real HTTPS domain.
SECURE_SSL_REDIRECT          = not DEBUG  # redirect HTTP → HTTPS in prod
SECURE_HSTS_SECONDS          = 0 if DEBUG else 31536000  # 1 year HSTS in prod
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD          = not DEBUG
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS              = 'DENY'
SESSION_COOKIE_SECURE        = not DEBUG
CSRF_COOKIE_SECURE           = not DEBUG
SESSION_COOKIE_HTTPONLY      = True
CSRF_COOKIE_HTTPONLY         = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE           = 60 * 60 * 12  # 12 hours

# ─────────────────────────────────────────────
# INSTALLED APPS
# ─────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',
    'rest_framework',

    # Project apps
    'accounts',
    'core',
    'student',
    'faculty',
    'admin_dashboard',
    'hod',
    'deo',
]

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'VVITU_Portal.middleware.LoginRateLimitMiddleware',   # Rate limiting brute force protection
    'whitenoise.middleware.WhiteNoiseMiddleware',         # serve static in prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'VVITU_Portal.middleware.RoleBasedAccessMiddleware',  # custom middleware
]

ROOT_URLCONF = 'VVITU_Portal.urls'

# ─────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'VVITU_Portal.wsgi.application'

# ─────────────────────────────────────────────
# DATABASE — SQLite for dev, PostgreSQL for prod
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # Production: switch to PostgreSQL:
        # 'ENGINE': 'django.db.backends.postgresql',
        # 'NAME': os.environ.get('DB_NAME', 'VVITU_Portal'),
        # 'USER': os.environ.get('DB_USER', 'postgres'),
        # 'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        # 'HOST': os.environ.get('DB_HOST', 'localhost'),
        # 'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# ─────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/redirect/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─────────────────────────────────────────────
# CACHING — Use Redis in production
# ─────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vvit-cache',
        # Production: use Redis:
        # 'BACKEND': 'django_redis.cache.RedisCache',
        # 'LOCATION': 'redis://127.0.0.1:6379/1',
        # 'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}
CACHE_MIDDLEWARE_SECONDS = 300

# ─────────────────────────────────────────────
# INTERNATIONALIZATION
# ─────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────
# STATIC & MEDIA FILES
# ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────
# PAGINATION
# ─────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20

# ─────────────────────────────────────────────
# REST FRAMEWORK
# ─────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ─────────────────────────────────────────────
# EMAIL (configure for production)
# ─────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Production:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = 'noreply@vvitu.ac.in'

# ─────────────────────────────────────────────
# ATTENDANCE CONFIG
# ─────────────────────────────────────────────
ATTENDANCE_EDIT_WINDOW_DAYS = 2   # Faculty can edit attendance within last 2 days
LOW_ATTENDANCE_THRESHOLD = 75     # Alert if below 75%

# ─────────────────────────────────────────────
# COLLEGE INFO
# ─────────────────────────────────────────────
COLLEGE_NAME = 'Vasireddy Venkatadri International Technological University'
COLLEGE_SHORT = 'VVITU'
COLLEGE_LOCATION = 'Nambur, Guntur District, Andhra Pradesh'
COLLEGE_WEBSITE = 'https://www.vvitu.ac.in'

# Django admin site header customisation
ADMIN_SITE_HEADER = 'VVITU Portal Administration'
ADMIN_SITE_TITLE  = 'VVITU Admin'
ADMIN_INDEX_TITLE = 'VVITU Site Administration'

# ─────────────────────────────────────────────
# EMAIL CONFIGURATION
# For local testing — emails print to terminal
# For production — change to SMTP settings below
# ─────────────────────────────────────────────
# ── Uncomment below for real Gmail sending in production ──
# EMAIL_BACKEND    = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST       = 'smtp.gmail.com'
# EMAIL_PORT       = 587
# EMAIL_USE_TLS    = True
# EMAIL_HOST_USER  = os.environ.get('EMAIL_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')  # Gmail App Password
# DEFAULT_FROM_EMAIL  = 'VVITU Portal <noreply@vvitu.ac.in>'

# ---------------------------------------------
# AI CHATBOT (VBot)  Gemini API
# ---------------------------------------------
# Get a FREE key at: https://aistudio.google.com/app/apikey
# Set env var: GEMINI_API_KEY=your_key_here
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')


CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'https://*.lhr.life',
    'https://*.serveousercontent.com',
    'https://*.onrender.com',        # Render production hosting
    'https://*.up.railway.app',      # Railway production hosting
    'https://*.ngrok.io',            # ngrok tunnels for local testing
    'https://*.ngrok-free.app',      # ngrok free tier
]


