from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

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
    file_size = request.GET["file_size"]

    # Connect to bucket
    s3 = boto3.client("s3")

    # Check if the file is already on s3
    match_results = check_if_file_already_on_s3(file_name, file_size)

    if not match_results[0]:
        # Path and name on bucket
        key = "user_data/{0}/{1}".format(
            request.user.id,
            file_name
        )

        # Generate presigned post to be sent back to client
        presigned_post = s3.generate_presigned_post(
            Bucket=s3_bucket,
            Key=key,
            Fields={"acl": "public-read", "Content-Type": file_type},
            Conditions=[
                {"acl": "public-read"},
                {"Content-Type": file_type}
            ],
            ExpiresIn=3600
        )

        # S3 url
        url = "https://{0}.s3.amazonaws.com/user_data/{1}/{2}".format(
            s3_bucket,
            request.user.id,
            file_name)

        # Add file to database
        s3_upload = S3Upload.objects.create(
            user_id=request.user.id,
            email=request.user.email,
            file_name=file_name,
            task_id=request.session.get("unique_directory_name"),
            data_type="swat",
            file_size=file_size,
            s3_url=url,
            time_uploaded=timezone.datetime.now(),
        )
        s3_upload.save()

        response = {
            "data": presigned_post,
            "url": url
        }
    else:
        response = {
            "data": "exists",
            "url": match_results[1]
        }

    return JsonResponse(response)


def check_if_file_already_on_s3(file_name, file_size):
    """
    This method checks the S3Upload table for any records matching the
    incoming file's name and size. If a match is found True is returned,
    otherwise False is returned to indicate no match.
    
    Parameters
    ----------
    file_name: Name of the file the user is uploading.
    file_size: File size (bytes) for the file the user is uploading.

    Returns
    -------
    file_exists: Boolean set to True if file already on S3.
    """

    # Switch to true if matching file found in S3Upload table
    file_exists = False
    matching_file_url = ""

    # Fetch all records with a matching file name
    s3_objs = S3Upload.objects.filter(file_name=file_name, file_size=file_size)

    # If at least one record was found
    if s3_objs:
        file_exists = True
        matching_file_url = s3_objs[0].s3_url

    return file_exists, matching_file_url
