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

# CORS — scoped to the mobile REST API only (CORS_URLS_REGEX below); the
# cookie/session-based web app never needs cross-origin requests and stays
# fully closed. The mobile app's web target (Expo `expo start --web` / the
# static `expo export --platform web` bundle) runs on its own origin/port
# and calls the API on Django's origin, which browsers (unlike native
# iOS/Android) block by default without these headers. Token auth via
# `Authorization: Bearer <token>` is used here, not cookies, so
# CORS_ALLOW_CREDENTIALS stays off — no cross-origin cookie exposure.
_cors_allowed_origins_env = os.environ.get('CORS_ALLOWED_ORIGINS')
CORS_ALLOWED_ORIGINS = (
    [o.strip() for o in _cors_allowed_origins_env.split(',') if o.strip()]
    if _cors_allowed_origins_env else [
        # Metro's `expo start --web` dev server default port.
        'http://localhost:8081', 'http://127.0.0.1:8081',
        # Legacy Expo web dev port (pre-SDK 50 default), kept for older docs/muscle memory.
        'http://localhost:19006', 'http://127.0.0.1:19006',
        # `npx serve`/`python -m http.server` etc. serving a static
        # `expo export --platform web` bundle — no fixed port, so 4173
        # (Vite's preview default, commonly reused for this) is a
        # reasonable dev default; override via CORS_ALLOWED_ORIGINS for
        # anything else.
        'http://localhost:4173', 'http://127.0.0.1:4173',
    ]
)
CORS_URLS_REGEX = r'^/api/v1/.*$'

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
    'corsheaders',
    'manufacturing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Must stay immediately after SecurityMiddleware (whitenoise's own
    # requirement) — serves collected static files directly from the app
    # process, so it works whether or not nginx ends up in front of it.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # Must come before CommonMiddleware (django-cors-headers' own
    # requirement) so CORS headers make it onto every response, including
    # ones CommonMiddleware itself can short-circuit.
    'corsheaders.middleware.CorsMiddleware',
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

# ---------------------------------------------------------------------------
# Error tracking (Phase 3) — opt-in via SENTRY_DSN, same pattern as
# EMAIL_BACKEND/DJANGO_HTTPS_ENABLED above: unset by default, so local dev and
# CI never talk to Sentry at all. A real deployment sets SENTRY_DSN in .env.
# ---------------------------------------------------------------------------
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        # This app already has payroll/HR/PII data in scope (see the
        # deployment scoping doc's compliance-decision callout) — never send
        # request/user PII to a third-party service by default. Someone
        # explicitly deciding compliance scope allows it, not this default.
        send_default_pii=False,
        # Performance tracing samples real request timings/bodies; off by
        # default (0.0) until there's a reason — and a compliance answer —
        # to turn it on. Override via SENTRY_TRACES_SAMPLE_RATE if needed.
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0')),
    )

# ---------------------------------------------------------------------------
# SSO (OpenID Connect) — opt-in, same pattern as SENTRY_DSN above: unset by
# default, so local dev/CI never attempt an SSO round-trip and the login
# page shows password-only. Works against any spec-compliant OIDC provider
# (Azure AD/Entra ID, Google Workspace, Okta, or a local test IdP).
#
# Multiple providers can be configured at once via OIDC_PROVIDERS, a JSON
# list of {"key", "label", "client_id", "client_secret", "discovery_url",
# "auto_provision", "default_dept_key"} objects — "key" is a short
# URL-safe slug used in /sso/login/<key>/ and /sso/callback/<key>/, and
# must be registered as that provider's own callback URL on the IdP's
# side. auto_provision (bool, default false) + default_dept_key opt a
# provider into creating a new account on first login instead of
# requiring one to already exist — see accounts.provision_sso_user().
# Example:
#   OIDC_PROVIDERS=[{"key":"azure","label":"Azure AD","client_id":"...",
#     "client_secret":"...","discovery_url":"https://login.microsoftonline
#     .com/<tenant>/v2.0/.well-known/openid-configuration",
#     "auto_provision":true,"default_dept_key":"sales"}, {"key":"google",
#     "label":"Google Workspace", ...}]
#
# The single-provider OIDC_CLIENT_ID/OIDC_CLIENT_SECRET/OIDC_DISCOVERY_URL
# vars are kept as a fallback for existing deployments that set those
# instead — sso_core.get_providers() only falls back to them when
# OIDC_PROVIDERS is unset, and assigns that provider the key "default"
# (never auto-provisioning). See sso_core.py for the client itself.
# ---------------------------------------------------------------------------
OIDC_PROVIDERS = os.environ.get('OIDC_PROVIDERS', '')
OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID', '')
OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET', '')
OIDC_DISCOVERY_URL = os.environ.get('OIDC_DISCOVERY_URL', '')

# ---------------------------------------------------------------------------
# SSO (SAML 2.0) — same opt-in pattern as OIDC_PROVIDERS above, for
# identity providers/IT departments that specifically require SAML rather
# than OIDC. A JSON list of {"key", "label", "idp_entity_id",
# "idp_sso_url", "idp_x509_cert", "auto_provision", "default_dept_key"}
# objects — "key" is a short URL-safe slug used in /sso/saml/login/<key>/,
# /sso/saml/acs/<key>/, and /sso/saml/metadata/<key>/ (the SP metadata XML
# an IdP admin imports to configure the trust relationship).
# idp_x509_cert is the IdP's public signing certificate (PEM, without the
# ----BEGIN/END CERTIFICATE---- lines) — required, since that's what
# proves an assertion actually came from the IdP. Example:
#   SAML_PROVIDERS=[{"key":"okta","label":"Okta","idp_entity_id":"http://
#     www.okta.com/<app-id>","idp_sso_url":"https://<org>.okta.com/app/
#     <app-id>/sso/saml","idp_x509_cert":"MIIDpDCCAoyg...",
#     "auto_provision":true,"default_dept_key":"sales"}]
# See saml_core.py for the client itself.
# ---------------------------------------------------------------------------
SAML_PROVIDERS = os.environ.get('SAML_PROVIDERS', '')
