from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

import os
import boto3

from s3upload.models import S3Upload


@login_required
def sign_s3(request):
    """
    This method is responsible for generating and returning the signature
    the client requires before sending the file selected for upload to S3. A
    unique name is assigned to the user file to prevent it from being 
    overwritten by other users or the same user. Also saves info about 
    uploaded file to database table S3Upload.
    
    Parameters
    ----------
    request: Contains metadata about the http request.

    Returns
    -------
    JsonResponse: JSON object containing the presigned post and S3 url.
    """

    # Bucket name
    s3_bucket = settings.AWS_STORAGE_BUCKET_NAME

    # Get file name and type
    file_name = request.GET["file_name"]
    file_type = request.GET["file_type"]

    # Connect to bucket
    s3 = boto3.client("s3")

    # Get file extension
    ext = os.path.splitext(file_name)[1]

    # Generate presigned post to be sent back to client
    presigned_post = s3.generate_presigned_post(
        Bucket=s3_bucket,
        Key=request.session['unique_directory_name'] + '_swatmodel' + ext,
        Fields={"acl": "public-read", "Content-Type": file_type},
        Conditions=[
            {"acl": "public-read"},
            {"Content-Type": file_type}
        ],
        ExpiresIn=3600
    )

    # S3 url
    url = "https://{0}.s3.amazonaws.com/{1}".format(
        s3_bucket,
        request.session['unique_directory_name'] + '_swatmodel' + ext)

    # Add file to database
    s3_upload = S3Upload.objects.create(
        user_id=request.user.id,
        email=request.user.email,
        task_id=request.session.get("unique_directory_name"),
        data_type="swat",
        s3_url=url,
        time_uploaded=timezone.datetime.now(),
    )
    s3_upload.save()

    return JsonResponse({
        "data": presigned_post,
        "url": "https://{0}.s3.amazonaws.com/{1}".format(s3_bucket, file_name)
    })
