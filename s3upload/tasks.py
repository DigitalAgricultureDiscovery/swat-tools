from __future__ import absolute_import

from django.utils import timezone
from .models import S3Upload
from celery import shared_task


@shared_task
def clean_up_database():
    # Get date from exactly two dates ago
    two_days_ago = timezone.datetime.now() - timezone.timedelta(days=2)

    # Remove objects 48 hours or older in S3Upload database table
    S3Upload.objects.filter(time_uploaded__lte=two_days_ago).delete()
