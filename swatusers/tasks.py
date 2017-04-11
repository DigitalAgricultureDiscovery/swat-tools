from __future__ import absolute_import

from django.conf import settings
from django.utils import timezone
from swatusers.models import UserTask
from celery import shared_task

import os
import shutil


@shared_task
def check_for_expired_data():
    expire_date = (timezone.date.today() - timezone.timedelta(days=2)).strftime("%Y-%m-%d 00:00:00")
    expired_data = UserTask.objects.filter(time_started__lt=expire_date)

    for task in expired_data:
        task_data_folder = settings.PROJECT_DIR + '/user_data/' + task.user_email + '/' + task.task_id
        # Delete user's uploaded input data
        if os.path.exists(task_data_folder):
            shutil.rmtree(task_data_folder)

        task.delete()

