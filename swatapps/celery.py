from __future__ import absolute_import

import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swatapps.settings.production')

app = Celery('swatapps')

# Using a string here means the worker will not have to
# pickle the object when using Windows
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Schedule periodic tasks (UTC is default timezone)
app.conf.beat_schedule = {
    'update-iclimate-table': {
        'task': 's3upload.tasks.clean_up_database',
        'schedule': crontab(minute=5)  #
    }
}
