from __future__ import absolute_import

from celery import shared_task
from celery.utils.log import get_task_logger

from .clean import clean_up_user_data


logger = get_task_logger(__name__)


@shared_task
def remove_expired_data():
    clean_up_user_data(logger)
