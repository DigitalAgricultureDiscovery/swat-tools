from __future__ import absolute_import

import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings


# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'swatapps')

app = Celery('swatapps')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Schedule periodic tasks (UTC is default timezone)
app.conf.beat_schedule = {
    'clean-s3upload-table': {
        'task': 's3upload.tasks.clean_up_database',
        'schedule': crontab(minute='*/30')
    },
    'clean-user-data': {
        'task': 'swatusers.tasks.remove_expired_data',
        'schedule': crontab(minute=0, hour='*/1')
    }
}
