import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load DB credentials (and other settings) from a local .env file. In a real
# deployment these env vars should come from the platform's secrets manager
# (not a .env file on disk) — .env/.env.local are already gitignored and
# exist only for local dev convenience.
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# This fallback is only ever used when DJANGO_SECRET_KEY isn't set, which is
# fine for local dev/CI (DEBUG defaults to True there) — production deploys
# must set a real DJANGO_SECRET_KEY, enforced below once DEBUG is False.
_DEV_INSECURE_SECRET_KEY = 'django-insecure-((^v*$u%ktah0%)58)b&8u1a_1q^(*&wr_47m00&2g__esq+9y'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', _DEV_INSECURE_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
# Defaults to True (today's behavior) so existing dev/CI usage is unchanged;
# set DJANGO_DEBUG=False for any real deployment.
DEBUG = _env_bool('DJANGO_DEBUG', True)

_allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS')
ALLOWED_HOSTS = (
    [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
    if _allowed_hosts_env else
    ['localhost', '127.0.0.1', '192.168.0.239']
)

_csrf_trusted_origins_env = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS')
CSRF_TRUSTED_ORIGINS = (
    [o.strip() for o in _csrf_trusted_origins_env.split(',') if o.strip()]
    if _csrf_trusted_origins_env else []
)

if not DEBUG:
    if SECRET_KEY == _DEV_INSECURE_SECRET_KEY:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY must be set to a real secret when DJANGO_DEBUG=False.'
        )

# HTTPS enforcement is intentionally independent of DEBUG. DEBUG=False alone
# (e.g. the Phase 1 docker-compose stack, whose nginx has no TLS cert yet)
# must still let cookie-based login work over plain HTTP — SESSION_COOKIE_SECURE
# would silently break every login if forced on before TLS actually exists.
# Set DJANGO_HTTPS_ENABLED=True once a real TLS terminator (nginx with a cert,
# a managed platform's load balancer) sits in front of the app. That same flag
# gates SECURE_PROXY_SSL_HEADER: trusting X-Forwarded-Proto is only safe once
# there's a specific, trusted proxy in front of Django that's known to set it
# on every request (nginx/app.conf does) — a client can't reach gunicorn directly
# to spoof it, since nginx is the only service with a published port.
if _env_bool('DJANGO_HTTPS_ENABLED', False):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'manufacturing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Must stay immediately after SecurityMiddleware (whitenoise's own
    # requirement) — serves collected static files directly from the app
    # process, so it works whether or not nginx ends up in front of it.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'manufacture.middleware.AuditUserMiddleware',
]

ROOT_URLCONF = 'manufacture.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'manufacture.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'company_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation'
                '.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

# Where `manage.py collectstatic` gathers files for whitenoise/nginx to serve
# in production. Must run at container *start* (docker-entrypoint.sh), not at
# `docker build` time — collecting static files populates the full app
# registry, which triggers manufacturing.apps.ManufacturingConfig.ready() and
# needs a live Postgres connection that doesn't exist during an image build.
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Uploaded files (Document Control module, P2-F) — the first feature in this
# app to accept file uploads. Deliberately not wired up for direct static
# serving under MEDIA_URL — files are only ever served through the
# authenticated manufacturing.views.document_download view, so access
# control matches every other page in the app.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Logging
# Mirrors manufacturing/log_utils.py: honours the LOG_LEVEL and LOG_FILE
# environment variables and uses the same line format, so the Django web
# process and the standalone desktop tools log consistently. Set LOG_FILE to
# also write to a file; set DJANGO_LOG_LEVEL to tune Django's own verbosity.

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.environ.get('LOG_FILE')

_LOG_HANDLER_DEFS = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'standard',
    },
}
if LOG_FILE:
    _LOG_HANDLER_DEFS['file'] = {
        'class': 'logging.FileHandler',
        'filename': LOG_FILE,
        'formatter': 'standard',
    }
_LOG_HANDLERS = list(_LOG_HANDLER_DEFS)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)-8s %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': _LOG_HANDLER_DEFS,
    'root': {
        'handlers': _LOG_HANDLERS,
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': _LOG_HANDLERS,
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO').upper(),
            'propagate': False,
        },
        'manufacturing': {
            'handlers': _LOG_HANDLERS,
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------------
# Email — configure via env vars for production SMTP; defaults to console
# backend so development prints emails to the runserver stdout.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'manufacturing@company.local'
)
