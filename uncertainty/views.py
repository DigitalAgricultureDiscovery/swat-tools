from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone

from tasks import process_task
from swatusers.models import UserTask
from swatluu import swattools

import csv
import glob
import io
import os
import shutil
import zipfile


# Create your views here.
@login_required
def index(request):
    # Check whether or not user is authenticated, if not return to login page
    if not request.user.is_authenticated():
        return HttpResponseRedirect(resolve_url('login'))
    else:
        # Clear progress message
        request.session['progress_message'] = []
        # Set user's unique directory that will hold their uploaded files
        unique_directory_name = 'uid_' + str(
            request.user.id) + '_uncertainty_' + \
                                timezone.datetime.now().strftime(
                                    "%Y%m%dT%H%M%S")
        unique_path = settings.TMP_DIR + '/user_data/' + request.user.email + \
                      '/' + unique_directory_name
        request.session['unique_directory_name'] = unique_directory_name
        request.session['directory'] = unique_path
        # Render main LUU Uncertainty view
        return render(request, 'uncertainty/index.html')


def fix_file_permissions(path):
    """ Starts at a base directory and moves through all of its
        files changing the directory permissions to 775 and file
        permissions to 664. """

    # Change directory and file permissions for "path" to 775 and 664 respectively
    if os.path.isfile(path):
        os.chmod(path, 0o664)
    else:
        os.chmod(path, 0o775)
        for root, directory, file in os.walk(path):
            for d in directory:
                os.chmod(os.path.join(root, d), 0o775)
            for f in file:
                os.chmod(os.path.join(root, f), 0o664)


def create_working_directory(request):
    """ Creates the directory structure that all inputs/outputs will be
        placed for this current process. """
    # Create main directory for user data (e.g. ../user_data/user_email)
    if not os.path.exists(settings.TMP_DIR + '/user_data'):
        os.makedirs(settings.TMP_DIR + '/user_data')
        os.chmod(settings.TMP_DIR + '/user_data', 0o775)

    if not os.path.exists(
                            settings.TMP_DIR + '/user_data/' + request.user.email):
        os.makedirs(settings.TMP_DIR + '/user_data/' + request.user.email)
        os.chmod(settings.TMP_DIR + '/user_data/' + request.user.email, 0o775)

    # Set up the working directory for this specific process
    unique_path = request.session.get("directory")
    if not os.path.exists(unique_path):
        os.makedirs(unique_path)
    if not os.path.exists(unique_path + '/input'):
        os.makedirs(unique_path + '/input')

    # Set folder permissions
    fix_file_permissions(unique_path)


@login_required
def upload_swat_model_zip(request):
    """ This view uploads the SWAT model zip in to the input directory. """
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        if 'swat_model_zip' in request.FILES:
            # Get the uploaded file and store the name of the zip
            try:
                file = request.FILES['swat_model_zip']
                filename = file.name
                swat_model_file = os.path.splitext(filename)
                swat_model_filename = swat_model_file[0]
                swat_model_file_ext = swat_model_file[1]
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            try:
                # Set up the working directory
                create_working_directory(request)
                unique_path = request.session.get("directory")
            except:
                request.session[
                    'error'] = 'Unable to set up user workspace, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            try:
                # If the SWAT Model directory already exists, remove it to make way for new upload
                if os.path.exists(
                                        unique_path + '/input/' + swat_model_filename):
                    shutil.rmtree(unique_path + '/input/' + swat_model_filename)
            except:
                request.session[
                    'error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                               'to reset the tool. If the issue persists please use the Contact Us ' + \
                               'form to request further assistance from the site admins.'
                return render(request, 'uncertainty/index.html')

            try:
                # Read uploaded file into tmp directory
                with open(unique_path + '/input/' + filename,
                          'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            try:
                # Unzip uploaded file in tmp directory
                os.system(
                    'unzip -qq ' + unique_path + '/input/' + swat_model_filename + ' -d ' + unique_path + '/input/')

                # Set permissions for unzipped data
                fix_file_permissions(
                    unique_path + '/input/' + swat_model_filename)

                # Remove uploaded zip file
                os.remove(
                    unique_path + '/input/' + swat_model_filename + swat_model_file_ext)
            except:
                request.session[
                    'error'] = 'Unable to unzip the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Check if decompression completed or failed (no folder if failed)
            if not os.path.exists(
                                    unique_path + '/input/' + swat_model_filename):
                request.session['error'] = 'Could not extract the folder "' + \
                                           swat_model_filename + '". ' + \
                                           'Please check if the file is ' + \
                                           'compressed in zip format and ' + \
                                           'has the same name as ' + \
                                           'compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Check if the required files/folders exist
            loc = unique_path + '/input/' + swat_model_filename + \
                  '/Watershed/Grid/hrus1/w001001.adf'
            shapeloc = unique_path + '/input/' + swat_model_filename + \
                       '/Watershed/Shapes/hru1.shp'
            scenarioloc = unique_path + '/input/' + swat_model_filename + \
                          '/Scenarios/Default/TxtInOut/*.hru'

            # Check if the zip was extracted
            if not os.path.exists(
                                    unique_path + '/input/' + swat_model_filename):
                request.session['error'] = 'Could not extract the folder "' + \
                                           swat_model_filename + '". Please ' + \
                                           'check if the file is compressed ' + \
                                           'in zip format and has the same ' + \
                                           'name as compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Check if hru files were found
            if not (glob.glob(scenarioloc)):
                request.session['error'] = 'Could not find the folder or ' + \
                                           'hru files in ' + \
                                           swat_model_filename + \
                                           '/Scenarios/Default/TxtInOut/' + \
                                           '*.hru. Please check for files ' + \
                                           'in folder and re-upload the ' + \
                                           'zip file. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Check if watershed folder was found
            if not os.path.exists(shapeloc):
                request.session['error'] = 'Could not find the folder ' + \
                                           swat_model_filename + \
                                           '/Watershed/Shapes/hru1.shp. ' + \
                                           'Please check for files in ' + \
                                           'folder and re-upload the zip file. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # If there were no issues finding the required SWAT Model paths
            if os.path.exists(loc):
                # Update relevant session variables
                request.session['uncertainty_swat_model_filename'] = filename
                request.session[
                    'uncertainty_swat_model_dir'] = unique_path + '/input/' + \
                                                    swat_model_filename
                request.session['progress_message'].append(
                    'Swat Model zip folder uploaded.')
                # Render the main page
                return render(request, 'uncertainty/index.html')
            else:
                # Couldn't find a required SWAT Model folder, return error msg
                request.session['error'] = 'Could not find the folder ' + \
                                           swat_model_filename + \
                                           '/Watershed/Grid/hrus1/w001001.adf.' + \
                                           ' Please check for files in folder ' + \
                                           'and re-upload the zip file.'
                return render(request, 'uncertainty/index.html')
        else:
            # Couldn't find a required SWAT Model folder, return error msg
            request.session[
                'error'] = 'Please select your zipped SWAT Model before clicking the Upload button.'
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

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        if 'landuse_zip' in request.FILES:
            # Get uploaded file and store the name of the zip
            try:
                file = request.FILES['landuse_zip']
                filename = file.name
                landuse_filename = os.path.splitext(filename)[0]
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Set up the working directory
            unique_path = request.session.get('directory')

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + landuse_filename):
                    shutil.rmtree(unique_path + '/input/' + landuse_filename)
            except:
                request.session[
                    'error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                               'to reset the tool. If the issue persists please use the Contact Us ' + \
                               'form to request further assistance from the site admins.'
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
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Uncompress the zip
            try:
                unzip_command = 'unzip -qq ' + unique_path + '/input/' + landuse_filename + \
                                ' -d ' + unique_path + '/input'
                os.system(unzip_command)

                # Set permissions for unzipped data
                fix_file_permissions(unique_path + '/input/' + landuse_filename)

                # Remove landuse zip
                os.remove(unique_path + '/input/' + filename)
            except:
                # Create error message if unzip failed
                request.session['error'] = 'Could not unzip the folder. ' + \
                                           'If the issue ' + \
                                           'persists please use the Contact ' + \
                                           'Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'uncertainty/index.html')

            # Check if unzipped folder exists
            if not os.path.exists(unique_path + '/input/' + landuse_filename):
                request.session['error'] = 'Could not unzip the folder "' + \
                                           landuse_filename + '". Please ' + \
                                           'check if the file is compressed ' + \
                                           'in zip format and has the same ' + \
                                           'name as compressed folder. If the issue ' + \
                                           'persists please use the Contact ' + \
                                           'Us form to request further assistance ' + \
                                           'from the site admins.'
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
            request.session[
                'error'] = 'Please select your zipped landuse folder before clicking the Upload button.'
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

    # If user made a post request
    if request.method == 'POST':
        try:
            # Get the dates if available and recall the landuse layer count
            date = request.POST.getlist('dates')[0]
            day = date.split('/')
            request.session['uncertainty_year'].append(day[2])
            request.session['uncertainty_month'].append(day[0])
            request.session['uncertainty_day'].append(day[1])
        except:
            request.session['error'] = 'Please make sure you are selecting ' + \
                                       'a date for each landuse layer.'
            return render(request, 'uncertainty/index.html')

        # Collect the selected landuse layers (.aux) if they are available
        if 'landuse_layer' in request.FILES:
            # Get the selected landuse layers
            try:
                landuse_layer = request.FILES.getlist('landuse_layer')[0]
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'uncertainty/index.html')

            if not landuse_layer:
                request.session['error'] = 'Please seelct a landuse file ' + \
                                           'for each input box.'
                request.session['uncertainty_landuse_layer_filename'] = []
                return render(request, 'uncertainty/index.html')

            # Get filenames and filepaths
            landuse_layer_filename = os.path.splitext(landuse_layer.name)[0]
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
                request.session['error'] = 'Could not find the location ' + \
                                           'of folder ' + \
                                           landuse_layer_filename + \
                                           '/w001001.adf in the landuse ' + \
                                           'folder previously uploaded. ' + \
                                           'Please check if the folder ' + \
                                           'exists inside landuse folder ' + \
                                           'and upload the zipped landuse ' + \
                                           'folder again.'
                return render(request, 'uncertainty/index.html')

            # Compare landuse layers resolutions and extents to hrus1
            validated = swattools.validate_raster_properties(
                request.session.get(
                    'uncertainty_swat_model_dir') + '/Watershed/Grid/hrus1',
                request.session.get('uncertainty_landuse_dir'),
                request.session.get('uncertainty_landuse_layer_filename'))

            if validated['status'] == 'error':
                request.session['error'] = validated['msg']
                return render(request, 'uncertainty/index.html')

            # Update progres message and re-render main page
            request.session['progress_message'].append(
                'Landuse layers selected.')
            return render(request, 'uncertainty/index.html')
        else:
            # Couldn't find a required SWAT Model folder, return error msg
            request.session[
                'error'] = 'Please select your landuse layer before clicking the Upload button.'
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

    # If user made post request
    if request.method == 'POST':
        # Get lookup file if available
        if 'lookup_file' in request.FILES:
            # Get the lookup filename and set working directory
            lookup_file = request.FILES['lookup_file']
            lookup_filename = request.FILES['lookup_file'].name
            unique_path = request.session['directory']

            try:
                # Check if path to lookup file already exists and if so remove it
                if os.path.exists(unique_path + '/input/' + lookup_filename):
                    os.remove(unique_path + '/input/' + lookup_filename)
                # If the path does not exist, create it
                if not os.path.exists(unique_path):
                    os.makedirs(unique_path, 0o775)
                if not os.path.exists(unique_path + '/input'):
                    os.makedirs(unique_path + '/input', 0o775)
            except:
                request.session[
                    'error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                               'to reset the tool. If the issue persists please use the Contact Us ' + \
                               'form to request further assistance from the site admins.'
                return render(request, 'uncertainty/index.html')

            try:
                # Open the lookup file and write it to a new file
                with open(unique_path + '/input/' + lookup_filename,
                          'wb+') as destination:
                    for chunk in lookup_file.chunks():
                        destination.write(chunk)
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
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
            except:
                request.session['error'] = 'Error reading the uploaded ' + \
                                           'lookup file, ' + \
                                           lookup_filename + '. Please ' + \
                                           'check that the file is not ' + \
                                           'empty and is in the csv format.'
                return render(request, 'uncertainty/index.html')

            # Read lookup contents into list
            try:
                lookup_info = []
                for row in reader:
                    if row[:][0] == '0':
                        request.session['error'] = 'Cannot use "0" as a ' + \
                                                   'landuse value. Please ' + \
                                                   'verify it is not being ' + \
                                                   'used with your landuse ' + \
                                                   'layers and lookup file.'
                        return render(request, 'uncertainty/index.html')
                    lookup_info.append(row)
            except:
                request.session['error'] = 'Error reading the uploaded ' + \
                                           'lookup file, ' + \
                                           lookup_filename + '. Please ' + \
                                           'check that the file is not ' + \
                                           'empty and is in the csv format.'
                return render(request, 'uncertainty/index.html')

            try:
                # Split up lookup codes and lookup class names
                for i in range(len(lookup_info)):
                    lookup_info[i][0] = lookup_info[i][0].strip()
                    lookup_info[i][1] = lookup_info[i][1].strip()
            except:
                request.session[
                    'error'] = 'Error occurred while trying to find the lookup ' + \
                               'codes and class names in the uploaded file. Please ' + \
                               'make sure the lookup file is in the csv format (see ' + \
                               'guide for help).'
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

            request.session['uncertainty_lookup_loop_times'] = [i + 1 for i in
                                                                range(len(
                                                                    lookup_info))]
            return render(request, 'uncertainty/index.html', context)
        else:
            request.session[
                'error'] = 'Please select the lookup file before uploading.'
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

    # Send loop times back in case someone wants to re-update their landuse percentage errors
    context = {'uncertainty_lookup_loop_times': request.session.get(
        'uncertainty_lookup_loop_times')}

    return render(request, 'uncertainty/index.html', context)


@login_required
def request_process(request):
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
        'output_dir': settings.BASE_DIR + '/user_data/' + request.user.email + '/' +
                      request.session['unique_directory_name'] + '/output',
        'swat_dir': request.session.get('uncertainty_swat_model_dir'),
        'hrus1_dir': request.session.get(
            'uncertainty_swat_model_dir') + '/Watershed/Grid/hrus1',
        'landuse_dir': request.session.get('uncertainty_landuse_dir'),
        'lookup_filepath': request.session.get('uncertainty_lookup_filepath'),
        'landuse_year': request.session.get('uncertainty_year'),
        'landuse_month': request.session.get('uncertainty_month'),
        'landuse_day': request.session.get('uncertainty_day'),
        'landuse_layer_name': request.session.get(
            'uncertainty_landuse_layer_filename'),
        'uncertainty_error_data': request.session.get('uncertainty_error_data'),
    }

    # run task
    process_task.delay(data)

    # add task id to database
    add_task_id_to_database(data['user_id'], data['user_email'],
                            data['task_id'])

    request.session['progress_message'].append(
        'Job successfully added to queue. You will receive an email with ' + \
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

    return HttpResponseRedirect(resolve_url('uncertainty'))


@login_required
def download_data(request):
    task_id = request.GET.get('id', '')
    if task_id != '':
        user_id = task_id.split('_')[1]
        if int(user_id) == int(request.user.id):
            if os.path.exists(
                                                            settings.BASE_DIR + '/user_data/' + request.user.email + '/' + task_id + '/output/Output'):
                file = io.BytesIO()

                dir_to_zip = settings.BASE_DIR + '/user_data/' + request.user.email + \
                             '/' + task_id + '/output/Output'

                # if the folder already exists, that means the user has already used the download link
                # no need to copy the post processing files over again
                if not os.path.exists(dir_to_zip + '/dist'):
                    # copy the post processing distribution folder over
                    shutil.copytree(
                        settings.BASE_DIR + '/uncertainty/post_processing_script/dist',
                        dir_to_zip + '/dist')

                    # copy post processing script README.txt
                    shutil.copy(
                        settings.BASE_DIR + '/uncertainty/post_processing_script/README.txt',
                        dir_to_zip)

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


def errors(request):
    pass
