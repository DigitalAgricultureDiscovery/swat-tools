from __future__ import absolute_import

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .clean import clean_up_user_data
from .models import UserTask

logger = get_task_logger(__name__)


@shared_task
def remove_expired_data():

    # Find records in database that are at least 48 hours old
    expired_objs = UserTask.objects.filter(
        time_completed__lte=timezone.now() - timezone.timedelta(days=2))

    # Create list of tuples (email, task_id)
    expired_objs_list = []
    if expired_objs:
        for obj in expired_objs:
            expired_objs_list.append((obj.email, obj.taskid))

    clean_up_user_data(logger, expired_objs_list)
