from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

import boto3
import logging

from .models import S3Upload
from .forms import UploadDestinationForm, UpdateUploadStatusForm


logger = logging.getLogger("django")


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

    response = {}

    # Bucket name
    s3_bucket = settings.AWS_STORAGE_BUCKET_NAME

    # Get file name and type
    try:
        file_name = request.GET["file_name"]
        file_type = request.GET["file_type"]
        file_size = request.GET["file_size"]
        overwrite = request.GET["overwrite"]
    except KeyError:
        file_name = ""
        file_type = ""
        file_size = ""
        overwrite = ""
        logger.error("Unable to retrieve file information from GET.")

    try:
        # Connect to bucket
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_ACCESS_SECRET
        )
    except:
        s3 = None
        logger.error("Boto3 unable to connect to S3 bucket.")

    # Check if the file is already on s3
    match_results = check_if_file_already_on_s3(
        request.user.email,
        file_name,
        file_size)

    if (not match_results[0] or overwrite == "true") and s3:
        # Path and name on bucket
        key = "user_data/{0}/{1}".format(
            request.user.id,
            file_name
        )

        try:
            # Generate presigned post to be sent back to client
            presigned_post = s3.generate_presigned_post(
                Bucket=s3_bucket,
                Key=key,
                Fields={
                    "acl": "public-read",
                    "Content-Type": file_type},
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

            # Json response to request
            response = {
                "data": presigned_post,
                "url": url
            }

            # Track in session
            request.session["on_s3"] = {
                request.session.get("unique_directory_name"): (
                    file_name, file_size)
            }
        except:
            presigned_post = None
            url = ""
            logger.error("Unable to generate presigned post for S3.")

        try:
            if presigned_post:
                # Add file to database
                s3_upload = S3Upload.objects.create(
                    user_id=request.user.id,
                    email=request.user.email,
                    file_name=file_name,
                    task_id=request.session.get("unique_directory_name"),
                    data_type="swat",
                    file_size=file_size,
                    s3_url=url,
                    status=0,
                    time_uploaded=timezone.datetime.now(),
                )
                s3_upload.save()
        except ValidationError:
            logger.warning("Unable to save S3 object to database.")
    else:
        response = {
            "data": "exists",
            "url": match_results[1]
        }

        request.session["on_s3"] = {
            request.session.get("unique_directory_name"): (
                file_name, file_size)
        }

    return JsonResponse(response)


def check_if_file_already_on_s3(email, file_name, file_size):
    """
    This method checks the S3Upload table for any records matching the
    incoming file's name and size. If a match is found True is returned,
    otherwise False is returned to indicate no match.

    Parameters
    ----------
    email: User's email address.
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
    s3_objs = S3Upload.objects.filter(
        email=email,
        file_name=file_name,
        file_size=file_size,
        status=1
    )

    # If at least one record was found
    if s3_objs:
        file_exists = True
        matching_file_url = s3_objs[0].s3_url

    return file_exists, matching_file_url


@login_required
def update_upload_status(request):
    """
    This method updates the upload status in the database to indicate if
    the upload was a success or an error was encountered.

    Parameters
    ----------
    request

    Returns
    -------
    None
    """

    response = {}
    if request.is_ajax():
        form = UpdateUploadStatusForm(request.POST)

        if form.is_valid():
            # Query table for matching file
            s3_obj = S3Upload.objects.filter(
                email=request.user.email,
                file_name=form.cleaned_data["file_name"],
                file_size=form.cleaned_data["file_size"]
            )

            if s3_obj:
                try:
                    # Update matching file's status to match posted status
                    s3_obj[0].status = int(form.cleaned_data["status"])
                    s3_obj[0].save()
                    response["status"] = "success"
                except (ValueError, ValidationError):
                    response["status"] = "fail"

    return JsonResponse(response)


@login_required
def determine_upload_destination(request):
    """
    This method uses the user's upload speed and size of the file to
    determine whether or not the file should be uploaded to S3 or
    through nginx and Apache.

    Parameters
    ----------
    request: Contains metadata about the http request.

    Returns
    -------
    use_s3: Boolean value, if true send file to S3.
    """

    # When set to true the uploaded file will be sent to S3
    use_s3 = "false"

    if request.is_ajax():
        # Set form with posted values
        form = UploadDestinationForm(request.POST)

        # Check if form is valid
        if form.is_valid():
            # Get file size
            file_size = form.cleaned_data["file_size"]

            # Overhead (%) reduces upload speed to reflect more real
            # world internet usage
            overhead = 0

            # Convert lower threshold upload speeds to bytes
            # Keys correspond to setting on the Internet Speed form
            upload_speed_threshold = {
                0: (1000 * 1024) / 8,
                1: (56 * 1024) / 8,
                2: (256 * 1024) / 8,
                3: (1000 * 1024) / 8,
                4: (10000 * 1024) / 8,
                5: (25000 * 1024) / 8
            }

            # Get users set upload speed range
            upload_speed = request.user.upload_speed

            # User upload speed in bytes (per sec)
            user_threshold = upload_speed_threshold[upload_speed]

            # Reduce by overhead %
            user_threshold = user_threshold * ((100 - overhead) * .01)

            # Determine how many minutes the upload would take
            time_to_upload = (file_size / user_threshold) / 60

            # If more than 20 minutes use S3 as the destination
            # or file larger than 950 megabytes
            if time_to_upload > 20 or file_size > 950000000:
                use_s3 = "true"

    return JsonResponse({"status": use_s3})
