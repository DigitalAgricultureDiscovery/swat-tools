import os


def get_logging_config(logs_dir):

    # Logging
    logging_config = {
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
                'filename': os.path.join(logs_dir, 'debug.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'info_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'info.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'error_logger': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'error.log'),
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
                'filename': os.path.join(logs_dir, 'fieldswat.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'luuchecker_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'luuchecker.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            's3upload_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 's3upload.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'swatluu_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'swatluu.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'swatusers_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'swatusers.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'swatmodelzip_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'swatmodelzip.log'),
                'formatter': 'verbose',
                'maxBytes': 1024 * 1024 * 100,
                'backupCount': 20,
                'encoding': 'utf8',
            },
            'uncertainty_logger': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(logs_dir, 'uncertainty.log'),
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
            'fieldswat': {
                'handlers': [
                    'console',
                    'fieldswat_logger',
                    'mail_admins',
                ],
                'level': 'DEBUG',
                'propagate': True,
            },
            'luuchecker': {
                'handlers': [
                    'console',
                    'luuchecker_logger',
                    'mail_admins',
                ],
                'level': 'DEBUG',
                'propagate': True,
            },
            's3upload': {
                'handlers': [
                    'console',
                    'mail_admins',
                    's3upload_logger',
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
            'swatluu': {
                'handlers': [
                    'console',
                    'mail_admins',
                    'swatluu_logger',
                ],
                'level': 'DEBUG',
                'propagate': True,
            },
            'swatmodelzip': {
                'handlers': [
                    'console',
                    'mail_admins',
                    'swatmodelzip_logger'
                ],
                'level': 'DEBUG',
                'propagate': True
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
            'uncertainty': {
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
    return logging_config
