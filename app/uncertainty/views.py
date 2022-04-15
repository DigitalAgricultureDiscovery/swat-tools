from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone

from .tasks import process_task
from common.utils import fix_file_permissions
from common.SWATModelZip import SWATModelZip
from s3upload.models import S3Upload
from swatusers.models import UserTask
from swatluu import swattools

import csv
import glob
import logging
import io
import os
import shutil
import subprocess
import zipfile


logger = logging.getLogger('uncertainty')


# Create your views here.
@login_required
def index(request):
    # Check whether or not user is authenticated, if not return to login page
    if not request.user.is_authenticated:
        return HttpResponseRedirect(resolve_url('login'))
    else:
        # Clear progress message
        request.session['progress_complete'] = []
        request.session['progress_message'] = []
        request.session['error'] = []
        request.session['error_swat_model'] = []
        request.session['error_landuse'] = []
        request.session['error_landuse_layers'] = []
        request.session['error_lookup'] = []

        # Set user's unique directory that will hold their uploaded files
        unique_directory_name = 'uid_' + str(request.user.id) + '_uncertainty_' + timezone.datetime.now().strftime('%Y%m%dT%H%M%S')
        unique_path = os.path.join(settings.USER_UPLOAD_DIR, request.user.email, unique_directory_name)
        request.session['unique_directory_name'] = unique_directory_name
        request.session['on_s3'] = {}
        request.session['directory'] = unique_path

        # Render main LUU Uncertainty view
        return render(request, 'uncertainty/index.html')


@login_required
def upload_swat_model_zip(request):
    """ This view uploads the SWAT model zip in to the input directory. """
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        upload = {
            'workspace': request.session.get('directory'),
            'local': request.FILES.get('swat_model_zip', None),
            'aws': None
        }

        # Check if the uploaded zip is on the aws s3 server
        task_id = request.session.get('unique_directory_name')
        if task_id in request.session.get('on_s3').keys():
            file_name, file_size = request.session.get('on_s3')[task_id]
            upload['aws'] = S3Upload.objects.filter(
                email=request.user.email,
                file_name=file_name,
                file_size=file_size
            )

        try:
            swat_model = SWATModelZip(upload)
        except Exception as e:
            logger.error(str(e))
            error_msg = 'An unexpected error has occurred, ' \
                        'please try again. If the issue persists ' \
                        'please use the Contact Us form to request ' \
                        'further assistance from the site admins.'
            request.session['error'] = error_msg
            request.session['error_swat_model'] = error_msg
            return render(request, 'uncertainty/index.html')

        validation_results = swat_model.validate_model()
        if validation_results["status"] == 1:
            request.session['error'] = validation_results['errors']
            request.session['error_swat_model'] = validation_results['errors']
            return render(request, 'uncertainty/index.html')

        # Update relevant session variables
        request.session['uncertainty_swat_model_filename'] = swat_model.get_filename()
        request.session['uncertainty_swat_model_dir'] = swat_model.get_directory()

        request.session['progress_message'].append(
            'Swat Model zip folder uploaded.')
        # Render the main page
        return render(request, 'uncertainty/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'uncertainty/index.html')


@login_required
def upload_landuse_zip(request):
    """
    This view uploads all landuse info to the input directory.
    """
    # Clear progression and error session keys
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_landuse'] = []

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        if 'landuse_zip' in request.FILES:
            # Get uploaded file and store the name of the zip
            try:
                file = request.FILES['landuse_zip']
                filename = file.name
                landuse_filename, landuse_ext = os.path.splitext(filename)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable upload landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Set up the working directory
            unique_path = request.session.get('directory')

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + landuse_filename):
                    shutil.rmtree(unique_path + '/input/' + landuse_filename)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to remove existing landuse directory.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the tool. ' \
                            'If the issue persists please use the Contact Us ' \
                            'form to request further assistance from the ' \
                            'site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'uncertainty/index.html')

            try:
                # Set up the input directory
                if not os.path.exists(unique_path):
                    os.makedirs(unique_path, 0o775)
                if not os.path.exists(unique_path + '/input'):
                    os.makedirs(unique_path + '/input', 0o775)

                # Copy the data to the path
                with open(unique_path + '/input/' + filename,
                          'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to write landuse zipfile to disk.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Make sure the file has the .zip extension
            if landuse_ext != ".zip":
                logger.error(
                    "{0}: Uploaded landuse file does not have .zip extension.".format(
                        request.session.get("unique_directory_name")))
                error_msg = "The file you are uploading does not have a .zip " \
                            "extension. Make sure the file you are uploading " \
                            "is a compressed zipfile. Please refer to the " \
                            "user manual if you need help creating a zipfile."
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, "uncertainty/index.html")

            # Uncompress the zip
            try:
                filepath = "{0}/input/{1}".format(
                    unique_path,
                    landuse_filename)
                subprocess.call([
                    "unzip",
                    "-qq", "-o",
                    filepath,
                    "-d",
                    unique_path + "/input/"
                ])

                # Set permissions for unzipped data
                fix_file_permissions(filepath)

                # Remove landuse zip
                os.remove(unique_path + '/input/' + filename)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable extract landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                # Create error message if unzip failed
                error_msg = 'Could not unzip the folder. If the issue ' \
                            'persists please use the Contact Us form to ' \
                            'request further assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Check if unzipped folder exists
            if not os.path.exists(filepath):
                logger.error(
                    "{0}: Unable to find extracted landuse directory.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not unzip the folder "{0}". Please check ' \
                            'if the file is compressed in zip format and has ' \
                            'the same name as compressed folder. If the ' \
                            'issue persists please use the Contact Us form ' \
                            'to request further assistance from the site ' \
                            'admins.'.format(landuse_filename)
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Update relevant session variables
            request.session['uncertainty_landuse_filename'] = filename
            request.session[
                'uncertainty_landuse_dir'] = unique_path + '/input/' + \
                landuse_filename
            request.session['progress_message'].append(
                'Landuse zip folder uploaded.')
            return render(request, 'uncertainty/index.html')
        else:
            # Couldn't find a required landuse zip, return error msg
            error_msg = 'Please select your zipped landuse folder before ' \
                        'clicking the Upload button.'
            request.session['error'] = error_msg
            request.session['error_landuse'] = error_msg
            return render(request, 'uncertainty/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'uncertainty/index.html')


@login_required
def upload_landuse_layer(request):
    """ This view gets the names of the selected landuse layers and validates
        whether or not the layers are in the uploaded landuse folder """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['uncertainty_year'] = []
    request.session['uncertainty_month'] = []
    request.session['uncertainty_day'] = []
    request.session['uncertainty_landuse_layer_filename'] = []
    request.session['error'] = []
    request.session['error_landuse_layers'] = []

    # If user made a post request
    if request.method == 'POST':
        try:
            # Get the dates if available and recall the landuse layer count
            date = request.POST.getlist('dates')[0]
            day = date.split('/')
            request.session['uncertainty_year'].append(day[2])
            request.session['uncertainty_month'].append(day[0])
            request.session['uncertainty_day'].append(day[1])
        except Exception as e:
            logger.error(str(e))
            error_msg = 'Please make sure you are selecting a date ' \
                        'for each landuse layer.'
            request.session['error'] = error_msg
            request.session['error_landuse_layers'] = error_msg
            return render(request, 'uncertainty/index.html')

        # Collect the selected landuse layers (.aux) if they are available
        if 'landuse_layer' in request.FILES:
            # Get the selected landuse layers
            try:
                landuse_layer = request.FILES.getlist('landuse_layer')[0]
            except:
                error_msg = 'Unable to receive the uploaded file, please ' \
                            'try again. If the issue persists please use ' \
                            'the Contact Us form to request further ' \
                            'assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse_layers'] = error_msg
                return render(request, 'uncertainty/index.html')

            if not landuse_layer:
                error_msg = 'Please seelct a landuse file for each input box.'
                request.session['error'] = error_msg
                request.session['error_landuse_layers'] = error_msg
                request.session['uncertainty_landuse_layer_filename'] = []
                return render(request, 'uncertainty/index.html')

            # Get filenames and filepaths
            landuse_layer_filename, landuse_layer_ext = os.path.splitext(
                landuse_layer.name)
            # Check for .xml extension
            if landuse_layer_ext == ".xml":
                landuse_layer_filename = \
                    os.path.splitext(landuse_layer_filename)[0]
            landuse_layer_filepath = request.session.get(
                'uncertainty_landuse_dir') + '/' + landuse_layer_filename \
                + '/w001001.adf'

            # Reset progress messages
            request.session['progress_message'] = []
            request.session['error'] = []

            # If landuse layers were found, add them to session variables
            if os.path.exists(landuse_layer_filepath):
                request.session['uncertainty_landuse_layer_filename'].append(
                    landuse_layer_filename)
            else:
                error_msg = 'Could not find the location of folder ' \
                            '{0}/w001001.adf in the landuse folder ' \
                            'previously uploaded. Please check if the ' \
                            'folder exists inside landuse folder and upload ' \
                            'the zipped landuse folder again.'.format(
                                landuse_layer_filename)
                request.session['error'] = error_msg
                request.session['error_landuse_layers'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Compare landuse layers resolutions and extents to hrus1
            validated = swattools.validate_raster_properties(
                request.session.get(
                    'uncertainty_swat_model_dir') + '/Watershed/Grid/hrus1',
                request.session.get('uncertainty_landuse_dir'),
                request.session.get('uncertainty_landuse_layer_filename'))

            if validated['status'] == 'error':
                error_msg = validated['msg']
                request.session['error'] = error_msg
                request.session['error_landuse_layers'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Update progres message and re-render main page
            request.session['progress_message'].append(
                'Landuse layers selected.')
            return render(request, 'uncertainty/index.html')
        else:
            # Couldn't find a required SWAT Model folder, return error msg
            error_msg = 'Please select your landuse layer before ' \
                        'clicking the Upload button.'
            request.session['error'] = error_msg
            request.session['error_landuse_layers'] = error_msg
            return render(request, 'uncertainty/index.html')
    else:
        return render(request, 'uncertainty/index.html')


@login_required
def upload_lookup_file(request):
    """ This view gets the contents of the uploaded landuse lookup file """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_lookup'] = []

    # If user made post request
    if request.method == 'POST':
        # Get lookup file if available
        if 'lookup_file' in request.FILES:
            # Get the lookup filename and set working directory
            lookup_file = request.FILES['lookup_file']
            lookup_filename = request.FILES['lookup_file'].name
            unique_path = request.session['directory']

            try:
                # If path to lookup file already exists remove it
                if os.path.exists(unique_path + '/input/' + lookup_filename):
                    os.remove(unique_path + '/input/' + lookup_filename)
                # If the path does not exist, create it
                if not os.path.exists(unique_path):
                    os.makedirs(unique_path, 0o775)
                if not os.path.exists(unique_path + '/input'):
                    os.makedirs(unique_path + '/input', 0o775)
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the ' \
                            'tool. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'uncertainty/index.html')

            try:
                # Open the lookup file and write it to a new file
                with open(unique_path + '/input/' + lookup_filename,
                          'wb+') as destination:
                    for chunk in lookup_file.chunks():
                        destination.write(chunk)
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Unable to receive the uploaded file, please ' \
                            'try again. If the issue persists please use ' \
                            'the Contact Us form to request further ' \
                            'assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'uncertainty/index.html')

            fix_file_permissions(unique_path + '/input/' + lookup_filename)

            # Set session variables for the lookup file and update progress
            request.session['uncertainty_lookup_file'] = lookup_filename
            request.session[
                'uncertainty_lookup_filepath'] = unique_path + '/input/' + \
                lookup_filename
            request.session['progress_message'] = []
            request.session['progress_message'].append('Lookup file uploaded.')

            # Try opening the lookup file with csv reader
            try:
                reader = csv.reader(
                    open(unique_path + '/input/' + lookup_filename, 'r'),
                    delimiter=',')
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Error reading the uploaded lookup file, {0}. ' \
                            'Please check that the file is not empty and is ' \
                            'in the csv format.'.format(lookup_filename)
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Read lookup contents into list
            try:
                lookup_info = []
                for row in reader:
                    if row[:][0] == '0':
                        error_msg = 'Cannot use "0" as a landuse value. ' \
                                    'Please verify it is not being used with ' \
                                    'your landuse layers and lookup file.'
                        request.session['error'] = error_msg
                        request.session['error_lookup'] = error_msg
                        return render(request, 'uncertainty/index.html')
                    lookup_info.append(row)
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Error reading the uploaded lookup file, {0}. ' \
                            'Please check that the file is not empty and is ' \
                            'in the csv format. Remove any empty lines from ' \
                            'the bottom of the file'.format(lookup_filename)
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'uncertainty/index.html')

            try:
                # Split up lookup codes and lookup class names
                for i in range(len(lookup_info)):
                    lookup_info[i][0] = lookup_info[i][0].strip()
                    lookup_info[i][1] = lookup_info[i][1].strip()
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Error occurred while trying to find the lookup ' \
                            'codes and class names in the uploaded file. ' \
                            'Please make sure the lookup file is in the csv ' \
                            'format (see guide for help).'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'uncertainty/index.html')

            # Add lookup content to session variable
            request.session['uncertainty_lookup_file_data'] = lookup_info

            # Create numerical list starting with 1 to count value submitted
            # and add it to context
            context = {
                'uncertainty_lookup_loop_times': [i + 1 for i in
                                                  range(len(lookup_info))],
                'uncertainty_error_range': [i for i in range(101)],
            }

            request.session['uncertainty_lookup_loop_times'] = [
                i + 1 for i in range(len(lookup_info))]

            return render(request, 'uncertainty/index.html', context)
        else:
            error_msg = 'Please select the lookup file before uploading.'
            request.session['error'] = error_msg
            request.session['error_lookup'] = error_msg
            return render(request, 'uncertainty/index.html')
    else:
        return render(request, 'uncertainty/index.html')


@login_required
def update_error_percentage(request):
    """
    Collects the updated error and realization percentages from the
    Update Error box that appears after the lookup file is uploaded.
    """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # Will store the user submitted error and realization percentages
    original_errors = []
    realized_errors = []
    request.session['uncertainty_error_data'] = []

    # If values have been posted
    if request.method == 'POST':

        # Get posted error and realization percentages
        posted_errors = request.POST.getlist('errors')
        posted_realizations = request.POST.getlist('realizations')

        # Loop through error percentages and append to our list
        for error in posted_errors:
            original_errors.append(error)

        # Loop through realization percentages and append to our list
        for realization in posted_realizations:
            realized_errors.append(realization)

        # Pack error and realizaiton percentages into session variable
        for i in range(0, len(original_errors)):
            request.session['uncertainty_error_data'].append(
                [int(original_errors[i]), int(realized_errors[i])])

        request.session['progress_message'].append(
            'Errors and realizations selected.')

    # Send loop times back in case someone wants to
    # re-update their landuse percentage errors
    context = {'uncertainty_lookup_loop_times': request.session.get(
        'uncertainty_lookup_loop_times')}

    return render(request, 'uncertainty/index.html', context)


@login_required
def request_process(request):
    # clear previous progress message
    request.session['progress_message'] = []

    proc_dir = os.path.join(settings.PROJECT_DIR, 'uncertainty', 'post_processing_script')

    # put all necessary path info for processing into single dictionary
    data = {
        'user_id': request.user.id,
        'user_email': request.user.email,
        'user_first_name': request.user.first_name,
        'task_id': os.path.basename(request.session.get('directory')),
        'process_root_dir': request.session.get('directory'),
        'post_processing_dir': proc_dir,
        'results_dir': os.path.join(request.session.get('directory'), 'output'),
        'output_dir': os.path.join(settings.USER_RESULT_DIR, request.user.email, request.session['unique_directory_name'], 'Output'),
        'swat_dir': request.session.get('uncertainty_swat_model_dir'),
        'hrus1_dir': os.path.join(request.session.get('uncertainty_swat_model_dir'), 'Watershed', 'Grid', 'hrus1'),
        'landuse_dir': request.session.get('uncertainty_landuse_dir'),
        'lookup_filepath': request.session.get('uncertainty_lookup_filepath'),
        'landuse_year': request.session.get('uncertainty_year'),
        'landuse_month': request.session.get('uncertainty_month'),
        'landuse_day': request.session.get('uncertainty_day'),
        'landuse_layer_name': request.session.get('uncertainty_landuse_layer_filename'),
        'uncertainty_error_data': request.session.get('uncertainty_error_data'),
    }

    # run task
    process_task.delay(data)

    # add task id to database
    add_task_id_to_database(data['user_id'], data['user_email'],
                            data['task_id'])

    request.session['progress_message'].append(
        'Job successfully added to queue. You will receive an email with ' +
        'a link to your files once the processing has completed.')

    return render(request, 'uncertainty/index.html')


def add_task_id_to_database(user_id, user_email, task_id):
    """
    Adds the unique user id, task id, task status, and timestamp to
    the database. This table will be periodically checked to clean up
    expired user data.
    """
    user_task = UserTask.objects.create(
        user_id=user_id,
        email=user_email,
        task_id=task_id,
        task_status=0,
        time_completed=timezone.datetime.now(),
    )
    user_task.save()


@login_required
def reset(request):
    """
    This view clears the session, deletes all existing data and
    refreshes the LUU Uncertainty home page.
    """

    # If we delete these session keys, the user will be
    # automatically signed out
    keys_to_keep = [
        '_auth_user_id',
        '_auth_user_backend',
        '_auth_user_hash',
        'False',
        'name',
    ]

    # Cycle through keys and delete the ones not in our keep list
    session_keys = list(request.session.keys())
    for key in session_keys:
        if key not in keys_to_keep:
            del request.session[key]

    return HttpResponseRedirect(resolve_url('uncertainty'))


@login_required
def download_data(request):
    # Get task id from the url
    task_id = request.GET.get("id", "")
    # If a task id was found
    if task_id != "":
        # Separate user id from task id
        user_id = task_id.split("_")[1]
        # Verify user making request is allowed to download the data
        if int(user_id) == int(request.user.id):
            # Construct path to output data
            output_data = os.path.join(settings.USER_RESULT_DIR, request.user.email, task_id, 'output')
            # Check if path to output exist
            if os.path.exists(output_data):
                # Length of path
                dir_to_zip_len = len(output_data.rstrip(os.sep)) + 1
                # Open byte stream
                file = io.BytesIO()
                # Compression method
                cmethod = zipfile.ZIP_DEFLATED
                # Start zipping file
                with zipfile.ZipFile(file, mode='w', compression=cmethod) as zf:
                    # Permissions for zip
                    zf.external_attr = 0o0770
                    # Walk through directory and add files to zip archive
                    for dirname, subdirs, files in os.walk(output_data):
                        for filename in files:
                            path = os.path.join(dirname, filename)
                            entry = path[dir_to_zip_len:]
                            zf.write(path, entry)
                # Close the zip archive
                zf.close()
                # Prepare response to download request
                response = HttpResponse(
                    file.getvalue(),
                    content_type="application/zip"
                )
                response["Content-Disposition"] = "attachment; filename=" + \
                    task_id + ".zip"
            else:
                context = {"title": "File does not exist error."}
                return TemplateResponse(
                    request,
                    "swatusers/file_does_not_exist.html",
                    context
                )
        else:
            context = {"title": "File permission error."}
            return TemplateResponse(
                request,
                "swatusers/permission_error.html",
                context
            )
    else:
        context = {"title": "File permission error."}
        return TemplateResponse(
            request,
            "swatusers/permission_error.html",
            context
        )
    return response


def errors(request):
    pass
