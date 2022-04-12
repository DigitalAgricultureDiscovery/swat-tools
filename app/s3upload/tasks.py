from __future__ import absolute_import

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from .models import S3Upload


logger = get_task_logger(__name__)


@shared_task
def clean_up_database():

    logger.info("Starting clean up database task.")

    # Get date from exactly two dates ago
    two_days_ago = timezone.datetime.now() - timezone.timedelta(days=2)

    logger.info("Created timestamp for exactly two days from now.")

    try:
        # Remove objects 48 hours or older in S3Upload database table
        S3Upload.objects.filter(time_uploaded__lte=two_days_ago).delete()

        logger.info("Expired records (if any) removed from database.")
    except:
        logger.error("Failed to delete expired records from database.")
