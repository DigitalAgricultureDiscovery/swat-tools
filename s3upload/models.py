from django.conf import settings
from django.db import models


class S3Upload(models.Model):
    """ Keep track of files uploaded to S3 bucket. """

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    email = models.EmailField()
    file_name = models.CharField(max_length=100)
    task_id = models.CharField(max_length=100)
    data_type = models.CharField(max_length=4)
    file_size = models.BigIntegerField()
    s3_url = models.CharField(max_length=255)
    status = models.IntegerField()
    time_uploaded = models.DateTimeField(auto_now_add=True)
