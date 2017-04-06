from __future__ import absolute_import
from celery.task import periodic_task
from celery.task.schedules import crontab

from django.conf import settings
from django.utils import timezone
from swatusers.models import UserTask
from swatapps.celery import app
import os
import shutil


@app.task
def check_for_expired_data():
    expire_date = (timezone.date.today() - timezone.timedelta(days=2)).strftime("%Y-%m-%d 00:00:00")
    expired_data = UserTask.objects.filter(time_started__lt=expire_date)

    for task in expired_data:
        task_data_folder = settings.PROJECT_DIR + '/user_data/' + task.user_email + '/' + task.task_id
        # Delete user's uploaded input data
        if os.path.exists(task_data_folder):
            shutil.rmtree(task_data_folder)

        task.delete()


@periodic_task(run_every=crontab(minute="0", hour="0"))
def test_periodic():
    f = open(settings.PROJECT_DIR + '/user_data/periodic_test.log', 'a')
    f.write(timezone.datetime.now().time().strftime("%H:%M:%S") + "\n")
    f.close()
