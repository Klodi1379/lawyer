# settings.py - Django Settings për Legal Case Manager
import os
from pathlib import Path
from django.core.management.utils import get_random_secret_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==========================================
# SECURITY SETTINGS
# ==========================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', get_random_secret_key())

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_REDIRECT_EXEMPT = []
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'

# ==========================================
# APPLICATION DEFINITION
# ==========================================

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_celery_beat',
    'django_celery_results',
]

# Add optional apps if available
try:
    import drf_yasg
    THIRD_PARTY_APPS.append('drf_yasg')
except ImportError:
    pass

try:
    import django_extensions
    THIRD_PARTY_APPS.append('django_extensions')
except ImportError:
    pass

LOCAL_APPS = [
    'legal_manager',  # Main app
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ==========================================
# MIDDLEWARE CONFIGURATION
# ==========================================

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ==========================================
# URL CONFIGURATION
# ==========================================

ROOT_URLCONF = 'legal_manager.urls'

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

WSGI_APPLICATION = 'legal_manager.wsgi.application'

# ==========================================
# DATABASE CONFIGURATION
# ==========================================

# Default to SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# PostgreSQL for production (configured via environment variables)
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(os.environ.get('DATABASE_URL'))
elif os.environ.get('DB_ENGINE') == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'legal_manager'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
            },
        }
    }

# ==========================================
# AUTHENTICATION & AUTHORIZATION
# ==========================================

AUTH_USER_MODEL = 'legal_manager.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Session settings
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ==========================================
# REST FRAMEWORK CONFIGURATION
# ==========================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'EXCEPTION_HANDLER': 'legal_manager.utils.custom_exception_handler',
}

# ==========================================
# CORS CONFIGURATION
# ==========================================

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React development server
    "http://127.0.0.1:3000",
    "http://localhost:8080",  # Vue development server
    "http://127.0.0.1:8080",
]

CORS_ALLOW_CREDENTIALS = True

# For development only
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# ==========================================
# INTERNATIONALIZATION
# ==========================================

LANGUAGE_CODE = 'sq'  # Albanian
TIME_ZONE = 'Europe/Tirane'
USE_I18N = True
USE_TZ = True

# ==========================================
# STATIC FILES CONFIGURATION
# ==========================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ==========================================
# MEDIA FILES CONFIGURATION
# ==========================================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644

# ==========================================
# CELERY CONFIGURATION
# ==========================================

# Celery Configuration Options
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Celery settings
CELERY_TIMEZONE = TIME_ZONE
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Task routing
CELERY_TASK_ROUTES = {
    'legal_manager.tasks.send_deadline_reminder': {'queue': 'notifications'},
    'legal_manager.tasks.generate_document_from_template': {'queue': 'documents'},
    'legal_manager.tasks.audit_cleanup': {'queue': 'maintenance'},
}

# ==========================================
# EMAIL CONFIGURATION
# ==========================================

EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

if EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@legalmanager.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ==========================================
# LOGGING CONFIGURATION
# ==========================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'legal_manager.log',
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'legal_manager': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# ==========================================
# CACHE CONFIGURATION
# ==========================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'legal_manager',
        'TIMEOUT': 300,  # 5 minutes default timeout
    }
} if not DEBUG else {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'legal-manager-cache',
    }
}

# ==========================================
# CRISPY FORMS CONFIGURATION
# ==========================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==========================================
# CUSTOM SETTINGS
# ==========================================

# Legal Manager specific settings
LEGAL_MANAGER = {
    'DOCUMENT_RETENTION_DAYS': int(os.environ.get('DOCUMENT_RETENTION_DAYS', '2555')),  # 7 years
    'AUDIT_LOG_RETENTION_DAYS': int(os.environ.get('AUDIT_LOG_RETENTION_DAYS', '1095')),  # 3 years
    'MAX_DOCUMENT_SIZE_MB': int(os.environ.get('MAX_DOCUMENT_SIZE_MB', '50')),
    'ALLOWED_DOCUMENT_TYPES': [
        'pdf', 'doc', 'docx', 'txt', 'rtf',
        'xls', 'xlsx', 'ppt', 'pptx',
        'jpg', 'jpeg', 'png', 'gif',
        'zip', 'rar', '7z'
    ],
    'DEFAULT_PAGINATION_SIZE': 20,
    'SEARCH_RESULTS_LIMIT': 100,
}

# LLM Integration settings
LLM_SETTINGS = {
    'PROVIDER': os.environ.get('LLM_PROVIDER', 'openai'),  # openai, anthropic, etc.
    'API_KEY': os.environ.get('LLM_API_KEY', ''),
    'API_ENDPOINT': os.environ.get('LLM_API_ENDPOINT', ''),
    'MODEL': os.environ.get('LLM_MODEL', 'gpt-4o-mini'),
    'MAX_TOKENS': int(os.environ.get('LLM_MAX_TOKENS', '1024')),
    'TEMPERATURE': float(os.environ.get('LLM_TEMPERATURE', '0.0')),
    'ENABLE_FINE_TUNING': os.environ.get('LLM_ENABLE_FINE_TUNING', 'False').lower() == 'true',
}

# ==========================================
# STORAGE CONFIGURATION (S3/MinIO)
# ==========================================

if os.environ.get('USE_S3', 'False').lower() == 'true':
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_S3_FILE_OVERWRITE = False
    
    # Use S3 for media files
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
    else:
        MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'

# ==========================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# ==========================================

# Development settings
if DEBUG:
    # Django Debug Toolbar
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1', 'localhost']
    except ImportError:
        pass
    
    # Less strict CORS for development
    CORS_ALLOW_ALL_ORIGINS = True
    
    # Email to console in development
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Production settings
else:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True
    
    # Additional security headers
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Disable browsable API in production
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
        'rest_framework.renderers.JSONRenderer',
    ]

# ==========================================
# DEFAULT AUTO FIELD
# ==========================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# TEST SETTINGS
# ==========================================

if 'test' in sys.argv or os.environ.get('TESTING'):
    # Use in-memory database for tests
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
    
    # Disable migrations for faster tests
    class DisableMigrations:
        def __contains__(self, item):
            return True
        def __getitem__(self, item):
            return None
    
    MIGRATION_MODULES = DisableMigrations()
    
    # Use dummy cache
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
    
    # Disable celery for tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Import sys at the top if using test settings
import sys
