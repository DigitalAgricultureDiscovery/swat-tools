"""
Django settings for swatapps project.

Generated by 'django-admin startproject' using Django 1.11.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

from logging.config import dictConfig
from unipath import Path
import os

from .aws_settings import *
from .settings_secret import *

# Admins (name, email)
ADMINS = get_admins()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(__file__).ancestor(3)
SETTINGS_DIR = os.path.dirname(__file__)
UPLOAD_DIR = "/tmp/user_data/"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret_key()

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap3',
    'swatusers',
    'swatluu',
    'luuchecker',
    'uncertainty',
    'fieldswat',
    's3upload'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'swatapps.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates').replace('\\', '/'),
                 os.path.join(PROJECT_DIR, 's3direct/templates').replace('\\', '/')],
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

WSGI_APPLICATION = 'swatapps.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'read_default_file': SETTINGS_DIR + '/my.cnf',
        },
    }
}

# Celery
BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_HIJACK_ROOT_LOGGER = False

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'debug_logger': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/debug.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'info_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/info.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'error_logger': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/error.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'fieldswat_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/fieldswat.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'luuchecker_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/luuchecker.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        's3upload_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/s3upload.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'swatluu_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/swatluu.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'swatusers_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/swatusers.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
        'uncertainty_logger': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'log/uncertainty.log'),
            'formatter': 'verbose',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 20,
            'encoding': 'utf8',
        },
    },
    'loggers': {
        'django': {
            'handlers': [
                'console',
                'debug_logger',
                'info_logger',
                'error_logger',
                'mail_admins'
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        'fieldswat.tasks': {
            'handlers': [
                'console',
                'fieldswat_logger',
                'mail_admins',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        'luuchecker.tasks': {
            'handlers': [
                'console',
                'luuchecker_logger',
                'mail_admins',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        's3upload.tasks': {
            'handlers': [
                'console',
                'mail_admins',
                's3upload_logger',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        'swatluu.tasks': {
            'handlers': [
                'console',
                'mail_admins',
                'swatluu_logger',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        'swatusers.tasks': {
            'handlers': [
                'console',
                'mail_admins',
                'swatusers_logger',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
        'uncertainty.tasks': {
            'handlers': [
                'console',
                'mail_admins',
                'uncertainty_logger',
            ],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Necessary or Celery interfere with Django logging
dictConfig(LOGGING)

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Media files

MEDIA_ROOT = PROJECT_DIR.child("user_data")
MEDIA_URL = '/media/'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_ROOT = PROJECT_DIR + '/static/'
STATIC_URL = '/static/'
STATIC_PATH = '/static/'
STATIC_PATH_DIR = os.path.join(PROJECT_DIR, 'static')
STATICFILES_DIRS = (
    os.path.join(PROJECT_DIR, 'static_storage'),
)

# User model
AUTH_USER_MODEL = 'swatusers.SwatUser'

AUTHENTICATION_BACKENDS = (
    'swatusers.backends.EmailAuthBackend',
)

# File upload settings
FILE_UPLOAD_TEMP_DIR = '/tmp'
FILE_UPLOAD_DIRECTORY_PERMISSIONS = '0o664'
FILE_UPLOAD_PERMISSIONS = '0o664'
MAX_UPLOAD_SIZE = '2684354560'

# Login url
LOGIN_URL = '/login'

# Google recaptcha site/secret keys
NORECAPTCHA_SITE_KEY = get_norecaptcha_site_key()
NORECAPTCHA_SECRET_KEY = get_norecaptcha_secret_key()

# Email
EMAIL_USE_TLS = True
EMAIL_HOST = get_email_host()
EMAIL_HOST_USER = get_email_user()
EMAIL_HOST_PASSWORD = get_email_password()
EMAIL_PORT = get_email_port()
DEFAULT_FROM_EMAIL = get_email_user()


# API key
APIKEY = get_apikey()
