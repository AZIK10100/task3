from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.getenv("SECRET_KEY", "hello-beby-there-is-not-your-home")

DEBUG = True
# DEBUG = True
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app",
    "jsonrpcserver",
    "import_export",
    "bot",
]

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

AUTH_USER_MODEL = "app.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Security / production settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", SECRET_KEY)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
ADMIN_ALLOWED_IPS = [
    ip.strip()
    for ip in os.getenv("ADMIN_ALLOWED_IPS", "127.0.0.1,::1").split(",")
    if ip.strip()
]

REQUEST_SIGNATURE_EXEMPT_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
)

MIDDLEWARE = [
    "app.middleware.AdminIPRestrictionMiddleware",
    *MIDDLEWARE,
    "app.middleware.RequestSignatureMiddleware",
]

LOGGING = globals().get(
    "LOGGING",
    {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
)
LOGGING.setdefault("filters", {})["sensitive_data"] = {
    "()": "app.security.SensitiveDataFilter",
}
for handler in LOGGING.get("handlers", {}).values():
    filters = handler.setdefault("filters", [])
    if "sensitive_data" not in filters:
        filters.append("sensitive_data")

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

AUTH_USER_MODEL = "app.User"
STATIC_URL = "static/"


REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "TIMEOUT": 30,
    }
}


CELERY_BROKER_URL = f"{REDIS_URL}/0"
CELERY_RESULT_BACKEND = f"{REDIS_URL}/0"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "hourly-stats": {
        "task": "app.tasks.send_stats_report",
        "schedule": crontab(minute=0),         
    },
    "daily-stats": {
        "task": "app.tasks.send_stats_report",
        "schedule": crontab(hour=9, minute=0), 
    },
}
import os

from dotenv import load_dotenv

load_dotenv()
