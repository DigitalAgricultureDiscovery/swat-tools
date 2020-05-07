from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone

from common.SWATModelZip import SWATModelZip
from common.utils import fix_file_permissions
from s3upload.models import S3Upload
from swatusers.models import UserTask
from .tasks import process_task

import csv
import glob
import logging
import io
import os
import shutil
import subprocess
import swattools
import zipfile


logger = logging.getLogger('django')


@login_required
def index(request):
    """ Renders view for main SWAT LUU page. """
    # Check whether or not user is authenticated, if not return to login page
    if not request.user.is_authenticated():
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
        unique_directory_name = 'uid_' + str(request.user.id) + '_swatluu_' + \
                                timezone.datetime.now().strftime(
                                    "%Y%m%dT%H%M%S")
        unique_path = settings.UPLOAD_DIR + request.user.email + \
            '/' + unique_directory_name
        request.session['unique_directory_name'] = unique_directory_name
        request.session['on_s3'] = {}
        request.session['directory'] = unique_path

        # Render main SWAT LUU view
        return render(request, 'swatluu/index.html')


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
            logger.error(e)
            error_msg = 'An unexpected error has occurred, ' \
                        'please try again. If the issue persists ' \
                        'please use the Contact Us form to request ' \
                        'further assistance from the site admins.'
            request.session['error'] = error_msg
            request.session['error_swat_model'] = error_msg
            return render(request, 'swatluu/index.html')

        validation_results = swat_model.validate_model()
        if validation_results["status"] == 1:
            request.session['error'] = validation_results['errors']
            request.session['error_swat_model'] = validation_results['errors']
            return render(request, 'swatluu/index.html')

        # Update relevant session variables
        request.session['swat_model_filename'] = swat_model.get_filename()
        request.session['swat_model_filepath'] = swat_model.get_directory()

        request.session['progress_message'].append(
            'Swat Model zip folder uploaded.')
        # Render the main page
        return render(request, 'swatluu/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'swatluu/index.html')


@login_required
def upload_landuse_zip(request):
    """ This view uploads all landuse info to the input directory. """
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
            except:
                logger.error(
                    "{0}: Unable upload landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'swatluu/index.html')

            # Set up the working directory
            unique_path = request.session.get('directory')

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + landuse_filename):
                    shutil.rmtree(unique_path + '/input/' + landuse_filename)
            except:
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
                return render(request, 'swatluu/index.html')

            # Copy the data to the path
            try:
                with open(unique_path + '/input/' + filename,
                          'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except:
                logger.error(
                    "{0}: Unable to write landuse zipfile to disk.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please ' \
                            'try again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'swatluu/index.html')

            # Make sure the file has the .zip extension
            if landuse_ext != ".zip":
                logger.error(
                    "{0}: Uploaded landuse file does not have .zip extension.".format(
                        request.session.get("unique_directory_name")))
                error_msg = "The file you are uploading does not have a " \
                            ".zip extension. Make sure the file you are " \
                            "uploading is a compressed zipfile. Please refer " \
                            "to the user manual if you need help creating " \
                            "a zipfile."
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, "swatluu/index.html")

            try:
                # Unzip the landuse data
                subprocess.call([
                    'unzip',
                    '-qq', '-o',
                    unique_path + '/input/' + landuse_filename,
                    '-d',
                    unique_path + '/input'
                ])

                # Set permissions for unzipped data
                fix_file_permissions(
                    unique_path + '/input/' + landuse_filename)

                # Remove landuse zip
                os.remove(unique_path + '/input/' + filename)
            except:
                logger.error(
                    "{0}: Unable extract landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                # Create error message if unzip failed
                error_msg = 'Could not unzip the folder. If the issue ' \
                            'persists please use the Contact Us form to ' \
                            'request further assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'swatluu/index.html')

            # Check if unzipped folder exists
            if not os.path.exists(unique_path + '/input/' + landuse_filename):
                logger.error(
                    "{0}: Unable to find extracted landuse directory.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not unzip the folder "{0}". Please check ' \
                            'if the file is compressed in zip format and has ' \
                            'the same name as compressed folder. If the ' \
                            'issue persists please use the Contact Us form ' \
                            'to request further assistance from the ' \
                            'site admins.'.format(landuse_filename)
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'swatluu/index.html')

            # Update relevant session variables
            request.session['landuse_filename'] = filename
            request.session['landuse_filepath'] = unique_path + '/input/' + \
                landuse_filename
            request.session['progress_message'].append(
                'Landuse zip folder uploaded.')
            return render(request, 'swatluu/index.html')
        else:
            # Couldn't find the required zipped landuse folder, return error msg
            error_msg = 'Please select your zipped landuse folder before ' \
                        'clicking the Upload button.'
            request.session['error'] = error_msg
            request.session['error_landuse'] = error_msg
            return render(request, 'swatluu/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'swatluu/index.html')


@login_required
def select_number_of_landuse_layers(request):
    """ This view gets the number of landuse layers in the landuse zip """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_no_of_landuse'] = []

    # If user made a post request
    if request.method == 'POST':
        try:
            # Get the posted landuse layer count value
            landuse_layer_count = request.POST.get('landuse_layer_count')
        except:
            error_msg = 'Error with submitted value, please try again. If ' \
                        'the issue persists please use the Contact Us form ' \
                        'to request further assistance from the site admins.'
            request.session['error'] = error_msg
            request.session['error_no_of_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        try:
            # Try converting the count to an integer
            landuse_layer_count = int(landuse_layer_count)
        except ValueError:
            # If it fails, display error
            error_msg = 'Please enter an integer.'
            request.session['error'] = error_msg
            request.session['error_no_of_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        # If no value was posted, display error
        if landuse_layer_count < 1:
            error_msg = 'Please enter an integer greater than 0.'
            request.session['error'] = error_msg
            request.session['error_no_of_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        # Update relevant session variable
        request.session['landuse_layer_count'] = landuse_layer_count

        # Create numerical list starting with 1 to count value submitted
        # and add it to context

        context = {
            'loop_times': [i + 1 for i in range(landuse_layer_count)]
        }

        return render(request, 'swatluu/index.html', context)
    else:
        # No data posted, reload main page
        return render(request, 'swatluu/index.html')


@login_required
def validate_selected_landuse_layers(request):
    """ This view gets the names of the selected landuse layers and validates
        whether or not the layers are in the uploaded landuse folder """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['years'] = []
    request.session['months'] = []
    request.session['day'] = []
    request.session['landuse_layers_names'] = []
    request.session['error_validate_landuse'] = []

    # If user made a post request
    if request.method == 'POST':
        try:
            # Get the dates if available and recall the landuse layer count
            dates = request.POST.getlist('dates')
            landuse_layer_count = request.session.get('landuse_layer_count')
        except:
            error_msg = 'Unable to receive the dates, please try again. If ' \
                        'the issue persists please use the Contact Us form ' \
                        'to request further assistance from the site admins.'
            request.session['error'] = error_msg
            request.session['error_validate_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        # Confirm that the number of submitted dates matches the
        # number of selected landuse layers
        if landuse_layer_count != len(dates):
            error_msg = 'Please select a date for each landuse layer.'
            request.session['error'] = error_msg
            request.session['error_validate_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        # Split dates into years, months, and days
        try:
            for date in dates:
                day = date.split('/')
                if (timezone.datetime.now() - timezone.datetime(
                        int(day[2]),
                        int(day[0]),
                        int(day[1]))).days < 0:

                    error_msg = 'Please do not select a date that has not ' \
                                'occurred yet. The selected date should be ' \
                                'the start date for the corresponding ' \
                                'landuse layer.'
                    request.session['error'] = error_msg
                    request.session['error_validate_landuse'] = error_msg
                    return render(request, 'swatluu/index.html')
                else:
                    request.session['years'].append(day[2])
                    request.session['months'].append(day[0])
                    request.session['day'].append(day[1])
        except IndexError:
            error_msg = 'Please make sure the date you are entering is in ' \
                        'the required format: MM/DD/YYYY. Click the calendar ' \
                        'icon and select your date from the popup calendar ' \
                        'to guarantee the correct format is used.'
            request.session['error'] = error_msg
            request.session['error_validate_landuse'] = error_msg
            return render(request, 'swatluu/index.html')

        # Collect the selected landuse layers (.aux) if they are available
        if 'landuse_layers' in request.FILES:
            # Get the selected landuse layers
            landuse_layer_files = request.FILES.getlist('landuse_layers')

            # Make sure the number of uploaded landuse layer files matches
            # the previously provided landuse layer count
            if landuse_layer_count != len(landuse_layer_files):
                error_msg = 'Please select a landuse file for each input box.'
                request.session['error'] = error_msg
                request.session['error_validate_landuse'] = error_msg
                return render(request, 'swatluu/index.html')

            # Loop through each landuse layer file
            for landuse_layer in landuse_layer_files:
                if not landuse_layer:
                    error_msg = 'Please select a landuse file ' \
                                'for each input box.'
                    request.session['error'] = error_msg
                    request.session['error_validate_landuse'] = error_msg
                    request.session['landuse_layers_names'] = []
                    return render(request, 'swatluu/index.html')

                # Get filenames and filepaths
                try:
                    landuse_layer_filename, landuse_layer_ext = os.path.splitext(
                        landuse_layer.name)
                    # Check for .xml extension
                    if landuse_layer_ext == ".xml":
                        landuse_layer_filename = os.path.splitext(
                            landuse_layer_filename)[0]
                    landuse_layer_filepath = request.session.get(
                        'landuse_filepath') + '/' + landuse_layer_filename + \
                        '/w001001.adf'
                except:
                    error_msg = 'Unable to match selected layers with layers ' \
                                'uploaded in the Landuse Folder input. Make ' \
                                'sure you are selecting the .aux files.'
                    request.session['error'] = error_msg
                    request.session['error_validate_landuse'] = error_msg
                # Reset progress messages
                request.session['progress_message'] = []
                request.session['error'] = []

                # If landuse layers were found, add them to session variables
                if os.path.exists(landuse_layer_filepath):
                    request.session['landuse_layers_names'].append(
                        landuse_layer_filename)
                else:
                    request.session['error'] = 'Could not find the location ' + \
                                               'of folder ' + \
                                               landuse_layer_filename + \
                                               '/w001001.adf in the landuse ' + \
                                               'folder previously uploaded. ' + \
                                               'Please check if the folder ' + \
                                               'exists inside landuse folder ' + \
                                               'and upload the zipped landuse ' + \
                                               'folder again.'
                    return render(request, 'swatluu/index.html')

            # Compare landuse layers resolutions and extents to hrus1
            try:
                validated = swattools.validate_raster_properties(
                    request.session.get(
                        'swat_model_filepath') + '/Watershed/Grid/hrus1',
                    request.session.get('landuse_filepath'),
                    request.session.get('landuse_layers_names'))
            except:
                validated = {
                    'status': 'error',
                    'msg': 'Unable to validate landuse layers. Refer to '
                           'the manual for help with this issue. If the '
                           'problem persists, please contact us so we may '
                           'offer further assistance.'
                }

            if validated['status'] == 'error':
                request.session['error'] = validated['msg']
                return render(request, 'swatluu/index.html')

            # Update progres message and re-render main page
            request.session['progress_message'].append(
                'Landuse layers selected.')
            return render(request, 'swatluu/index.html')
        else:
            error_msg = 'Please select landuse layers before continuing.'
            request.session['error'] = error_msg
            return render(request, 'swatluu/index.html')
    else:
        return render(request, 'swatluu/index.html')


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
                # Check if path to lookup file already exists
                # and if so remove it
                if os.path.exists(unique_path + '/input/' + lookup_filename):
                    os.remove(unique_path + '/input/' + lookup_filename)
            except:
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the tool. ' \
                            'If the issue persists please use the Contact Us ' \
                            'form to request further assistance from the ' \
                            'site admins.'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'swatluu/index.html')

            try:
                # Open the lookup file and write it to a new file
                with open(unique_path + '/input/' + lookup_filename,
                          'wb+') as destination:
                    for chunk in lookup_file.chunks():
                        destination.write(chunk)
            except:
                error_msg = 'Unable to receive the uploaded file, please ' \
                            'try again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'swatluu/index.html')

            # Set file permissions
            fix_file_permissions(unique_path + '/input/' + lookup_filename)

            # Set session variables for the lookup file and update progress
            request.session['lookup_file'] = lookup_filename
            request.session[
                'lookup_filepath'] = unique_path + '/input/' + lookup_filename
            request.session['progress_message'] = []
            request.session['progress_message'].append('Lookup file uploaded.')

            # Try opening the lookup file with csv reader
            try:
                reader = csv.reader(
                    open(unique_path + '/input/' + lookup_filename, 'r'),
                    delimiter=',')
            except:
                error_msg = 'Error reading the uploaded lookup file, "{0}". ' \
                            'Please check that the file is not empty and is ' \
                            'in the csv format.'.format(lookup_filename)
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'swatluu/index.html')

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
                        return render(request, 'swatluu/index.html')
                    lookup_info.append(row)
            except:
                error_msg = 'Error reading the uploaded lookup file, "{0}". ' \
                            'Please check that the file is not empty and is ' \
                            'in the csv format. Remove any empty lines from ' \
                            'the bottom of the file'.format(lookup_filename)
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'swatluu/index.html')

            try:
                # Split up lookup codes and lookup class names
                for i in range(len(lookup_info)):
                    lookup_info[i][0] = lookup_info[i][0].strip()
                    if i > 0:
                        int(lookup_info[i][0].strip())
                    lookup_info[i][1] = lookup_info[i][1].strip()
            except:
                error_msg = 'Error occurred while trying to find the lookup ' \
                            'codes and class names in the uploaded file. ' \
                            'Please make sure the lookup file is in the csv ' \
                            'format (see guide for help).'
                request.session['error'] = error_msg
                request.session['error_lookup'] = error_msg
                return render(request, 'swatluu/index.html')

            # Add lookup content to session variable
            request.session['lookup_file_data'] = lookup_info
            return render(request, 'swatluu/index.html')
        else:
            error_msg = 'Please selet a file before uploading.'
            request.session['error'] = error_msg
            request.session['error_lookup'] = error_msg
            return render(request, 'swatluu/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'swatluu/index.html')


@login_required
def runit(request):
    """ This view is executed after all input information is uploaded 
    successfully. This is the heart of the SWAT tool. It creates the output 
    directory and saves all the output information in to it.
        LOGIC:
    1) Create the output structure. Structure has OUTPUT, Raster folders.
    2) Save some input information and convert all adf files into tiff files
    3) Check if thresholds are applied and if yes, then merge non-dominant 
       hrus with dominant hrus in the base raster
    4) Get the area of each hru and save it in hru_area.txt file
    5) Generate a combination of old hru id, new hru id, lanuse, 
       subbasin id, soil, slope
    6) Read each landuse file and for each landuse file get the fractional 
       area of each hru in comparison with base raster.
    7) Save all area value in .dat files
    8) Copy all files into OUTPUT folder
    9) END """

    # clear previous progress message
    request.session['progress_message'] = []

    # put all necessary path info for processing into single dictionary
    data = {
        'user_id': request.user.id,
        'user_email': request.user.email,
        'user_first_name': request.user.first_name,
        'task_id': os.path.basename(request.session.get('directory')),
        'process_root_dir': request.session.get('directory'),
        'results_dir': request.session.get('directory') + '/output',
        'output_dir': settings.PROJECT_DIR + '/user_data/' + request.user.email + '/' +
        request.session['unique_directory_name'] + '/output',
        'swat_dir': request.session.get('swat_model_filepath'),
        'hrus1_dir': request.session.get(
            'swat_model_filepath') + '/Watershed/Grid/hrus1',
        'landuse_dir': request.session.get('landuse_filepath'),
        'lookup_filepath': request.session.get('lookup_filepath'),
        'landuse_years': request.session.get('years'),
        'landuse_months': request.session.get('months'),
        'landuse_days': request.session.get('day'),
        'landuse_layers_names': request.session.get('landuse_layers_names'),
    }
    if not request.session['error']:
        # run task
        process_task.delay(data)

        # add task id to database
        add_task_id_to_database(data['user_id'], data['user_email'],
                                data['task_id'])

        request.session['progress_message'].append(
            'Job successfully added to queue. You will receive an email with ' +
            'a link to your files once the processing has completed.')

    return render(request, 'swatluu/index.html')


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
def download_data(request):
    task_id = request.GET.get('id', '')

    if task_id != '':
        user_id = task_id.split('_')[1]
        if int(user_id) == int(request.user.id):
            if os.path.exists(
                    settings.PROJECT_DIR + '/user_data/' + request.user.email + '/' + task_id + '/output'):
                file = io.BytesIO()

                dir_to_zip = settings.PROJECT_DIR + '/user_data/' + request.user.email + \
                    '/' + task_id + '/output'

                dir_to_zip_len = len(dir_to_zip.rstrip(os.sep)) + 1

                with zipfile.ZipFile(file, mode='w',
                                     compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.external_attr = 0o0770
                    for dirname, subdirs, files in os.walk(dir_to_zip):
                        for filename in files:
                            path = os.path.join(dirname, filename)
                            entry = path[dir_to_zip_len:]
                            zf.write(path, entry)
                zf.close()

                response = HttpResponse(file.getvalue(),
                                        content_type="application/zip")
                response[
                    'Content-Disposition'] = 'attachment; filename=' + task_id + '.zip'
            else:
                context = {'title': ('File does not exist error')}
                return TemplateResponse(
                    request,
                    'swatusers/file_does_not_exist.html',
                    context)
        else:
            context = {'title': ('File permission error')}
            return TemplateResponse(
                request,
                'swatusers/permission_error.html',
                context)
    else:
        context = {'title': ('File permission error')}
        return TemplateResponse(
            request,
            'swatusers/permission_error.html',
            context)
    return response


def delete_user_data(request):
    """ This view delete's the signed in user's data. """
    unique_path = request.session.get('directory')
    if (unique_path is not None):
        # Delete user's uploaded input data
        if os.path.exists(unique_path + '/input'):
            shutil.rmtree(unique_path + '/input')
        # Delete user's output data
        if os.path.exists(unique_path + '/output'):
            shutil.rmtree(unique_path + '/output')


@login_required
def reset(request):
    """ This view clears the session, deletes all existing data and
        refreshes the SWAT LUU home page. """

    # Delete all data
    # delete_user_data(request)

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

    return HttpResponseRedirect(resolve_url('swatluu'))
