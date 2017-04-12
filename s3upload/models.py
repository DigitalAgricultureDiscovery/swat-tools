from django.conf import settings
from django.db import models


class UserTask(models.Model):
    """ Keep track of files uploaded to S3 bucket. """

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    email = models.EmailField()
    task_id = models.CharField(max_length=100)
    type = models.CharField(max_length=2)
    s3_url = models.CharField(max_length=255)
    time_started = models.DateTimeField(auto_now_add=True)
