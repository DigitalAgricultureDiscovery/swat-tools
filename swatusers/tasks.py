from __future__ import absolute_import

from celery import shared_task

from .clean import clean_up_user_data


@shared_task
def remove_expired_data():
    clean_up_user_data()
