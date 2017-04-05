from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone

from .tasks import process_task
from swatusers.models import UserTask

import io
import os
import shutil
import zipfile


@login_required
def index(request):
    # Check whether or not user is authenticated, if not return to login page
    if not request.user.is_authenticated():
        return HttpResponseRedirect(resolve_url('login'))
    else:
        # Clear progress message
        request.session['progress_message'] = []
        # Set user's unique directory that will hold their uploaded files
        unique_directory_name = 'uid_' + str(request.user.id) + '_luuchecker_' + \
                                timezone.datetime.now().strftime(
                                    "%Y%m%dT%H%M%S")
        unique_path = settings.TMP_DIR + '/user_data/' + request.user.email + \
                      '/' + unique_directory_name
        request.session['unique_directory_name'] = unique_directory_name
        request.session['directory'] = unique_path
        # Render main LUU Checker view
        return render(request, 'luuchecker/index.html')


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
def upload_subbasin_shapefile_zip(request):
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        if 'subbasin_shapefile_zip' in request.FILES:
            try:
                # Get the uploaded file and store the name of the zip
                file = request.FILES['subbasin_shapefile_zip']
                filename = file.name
                subbasin_shapefile_file = os.path.splitext(filename)
                subbasin_shapefile_filename = subbasin_shapefile_file[0]
                subbasin_shapefile_file_ext = subbasin_shapefile_file[1]
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            try:
                # Set up the working directory
                create_working_directory(request)
                unique_path = request.session.get("directory")
            except:
                request.session[
                    'error'] = 'Unable to set up user workspace, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            try:
                # If the shapefile directory already exists, remove it to make way for new upload
                if os.path.exists(
                                        unique_path + '/input/' + subbasin_shapefile_filename):
                    shutil.rmtree(
                        unique_path + '/input/' + subbasin_shapefile_filename)
            except:
                request.session[
                    'error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                               'to reset the tool. If the issue persists please use the Contact Us ' + \
                               'form to request further assistance from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            try:
                # Copy compressed data to the working directory
                with open(unique_path + '/input/' + filename,
                          'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            # Uncompress the data
            try:
                unzip_command = 'unzip -qq ' + unique_path + '/input/' + \
                                subbasin_shapefile_filename + ' -d ' + unique_path + \
                                '/input/'
                os.system(unzip_command)

                # Set permissions for unzipped data
                fix_file_permissions(
                    unique_path + '/input/' + subbasin_shapefile_filename)

                # Remove uploaded zip file
                os.remove(
                    unique_path + '/input/' + subbasin_shapefile_filename + subbasin_shapefile_file_ext)
            except:
                request.session[
                    'error'] = 'Unable to unzip the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            if not os.path.exists(
                                    unique_path + '/input/' + subbasin_shapefile_filename):
                request.session['error'] = 'Could not extract the folder "' + \
                                           subbasin_shapefile_filename + '". ' + \
                                           'Please check if the file is ' + \
                                           'compressed in zip format and ' + \
                                           'has the same name as ' + \
                                           'compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            subbasin_shapefile_filepath = unique_path + '/input/' + subbasin_shapefile_filename + '/subs1.shp'

            if not os.path.exists(subbasin_shapefile_filepath):
                request.session['error'] = 'Could not find the folder ' + \
                                           subbasin_shapefile_filename + '/subs1.shp. Please ' + \
                                           'check for files in folder and ' + \
                                           're-upload the zip file. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return HttpResponseRedirect(resolve_url('luuchecker'))

            # Update relevant session variables
            request.session[
                'luuc_subbasin_shapefile_filename'] = subbasin_shapefile_filename
            request.session[
                'luuc_subbasin_shapefile_filepath'] = subbasin_shapefile_filepath
            request.session['progress_message'].append(
                'Subbasin shapefile uploaded.')

            # Render the main page
            return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find a required subbasin shapefile, return error msg
            request.session[
                'error'] = 'Please select your zipped subbasin shapefile before clicking the Upload button.'
            return HttpResponseRedirect(resolve_url('luuchecker'))
    else:
        # Nothing was posted, reload main page
        return render(request, 'luuchecker/index.html')


@login_required
def upload_landuse_folder_zip(request):
    """ This view uploads all landuse info to the input directory. """
    # Clear progression and error session keys
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        if 'landuse_folder_zip' in request.FILES:
            try:
                # Get uploaded file and store the name of the zip
                file = request.FILES['landuse_folder_zip']
                filename = file.name
                landuse_filename = os.path.splitext(filename)[0]
            except:
                request.session[
                    'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                               'persists please use the Contact Us form to request further assistance ' + \
                               'from the site admins.'
                return render(request, 'luuchecker/index.html')

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
                return render(request, 'luuchecker/index.html')

            try:
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
                return render(request, 'luuchecker/index.html')

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
                return render(request, 'luuchecker/index.html')

            # Check if unzipped folder exists
            if not os.path.exists(unique_path + '/input/' + landuse_filename):
                request.session['error'] = 'Could not unzip the folder "' + \
                                           landuse_filename + '". Please ' + \
                                           'check if the file is compressed ' + \
                                           'in zip format and has the same ' + \
                                           'name as compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'luuchecker/index.html')

            # Update relevant session variables
            request.session['luuc_landuse_filename'] = filename
            request.session['luuc_landuse_dir'] = unique_path + '/input/' + \
                                                  landuse_filename
            request.session['progress_message'].append(
                'Landuse zip folder uploaded.')
            return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find the required zipped landuse folder, return error msg
            request.session[
                'error'] = 'Please select your zipped landuse folder before clicking the Upload button.'
            return render(request, 'luuchecker/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'luuchecker/index.html')


@login_required
def upload_base_landuse_raster_file(request):
    """ This view uploads all landuse info to the input directory. """
    # Clear progression and error session keys
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        if 'base_landuse_raster_file' in request.FILES:
            # Get uploaded file and store the name of the zip
            base_landuse_raster = request.FILES['base_landuse_raster_file']

            if not base_landuse_raster:
                request.session['error'] = 'Please select the base raster.'
                return render(request, 'luuchecker/index.html')

            filename = base_landuse_raster.name
            base_landuse_raster_filename = os.path.splitext(filename)[0]
            base_landuse_raster_location = request.session.get(
                'luuc_landuse_dir') + '/' + base_landuse_raster_filename + '/w001001.adf'

            request.session['progress_message'] = []
            request.session['error'] = []

            if os.path.exists(base_landuse_raster_location):
                request.session[
                    'luuc_base_landuse_raster_filename'] = base_landuse_raster_filename
                request.session[
                    'luuc_base_landuse_raster_filepath'] = request.session.get(
                    'luuc_landuse_dir') + '/' + base_landuse_raster_filename
                request.session['progress_message'].append(
                    'Landuse file\'s name taken.')
                return render(request, 'luuchecker/index.html')
            else:
                request.session['error'] = 'Could not find the location ' + \
                                           base_landuse_raster_filename + \
                                           '/w001001.adf in the landuse folder ' + \
                                           'previously uploaded in step 2. Please ' + \
                                           'check if the folder exists inside the ' + \
                                           'zipped landuse folder and upload ' + \
                                           'the zipped landuse folder again.'
                return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find the required base landuse layer, return error msg
            request.session[
                'error'] = 'Please select your base landuse layer before clicking the Upload button.'
            return render(request, 'luuchecker/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'luuchecker/index.html')


@login_required
def select_number_of_landuse_layers(request):
    """ This view gets the number of landuse layers in the landuse zip other than the base layer """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user made a post request
    if request.method == 'POST':
        # Get the posted landuse layer count value
        landuse_layer_count = request.POST.get('luuc_landuse_layer_count')
        try:
            # Try converting the count to an integer
            landuse_layer_count = int(landuse_layer_count)
        except ValueError:
            # If it fails, display error
            request.session['error'] = 'Please enter a number.'
            return render(request, 'luuchecker/index.html')

        # If no value was posted, display error
        if not landuse_layer_count:
            request.session['error'] = 'Please enter a value greater than 0.'
            return render(request, 'luuchecker/index.html')

        # If value posted, but less than 1, display error
        if landuse_layer_count < 1:
            request.session['error'] = 'Please enter a value greater than 0.'
            return render(request, 'luuchecker/index.html')

        # Update relevant session variable
        request.session['luuc_landuse_layer_count'] = landuse_layer_count

        # Create numerical list starting with 1 to count value submitted
        # and add it to context
        context = {
            'luuc_loop_times': [i + 1 for i in range(landuse_layer_count)]
        }
        return render(request, 'luuchecker/index.html', context)
    else:
        # No data posted, reload main page
        return render(request, 'luuchecker/index.html')


@login_required
def upload_selected_landuse_layers(request):
    """ This view gets the names of the selected landuse layers and validates
        whether or not the layers are in the uploaded landuse folder """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['luuc_landuse_layers_filenames'] = []
    request.session['luuc_landuse_layers_filepaths'] = []
    request.session['error'] = []

    if request.method == 'GET':
        return render(request, 'luuchecker/index.html')

    # If user made a post request
    if request.method == 'POST':
        try:
            landuse_layer_files = request.FILES.getlist('luuc_landuse_layers')
        except:
            request.session[
                'error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                           'persists please use the Contact Us form to request further assistance ' + \
                           'from the site admins.'
            return render(request, 'luuchecker/index.html')

        if request.session['luuc_landuse_layer_count'] != len(
                landuse_layer_files):
            request.session['error'] = 'Please select ' + str(
                request.session['luuc_landuse_layer_count']) + \
                                       ' landuse layers. If you would like to select a different number of ' + \
                                       'new landuse layers, go back to the previous step and enter the number desired.'
            return render(request, 'luuchecker/index.html')

        for landuse_layer in landuse_layer_files:
            if not landuse_layer:
                request.session['error'] = 'Please select ' + str(
                    request.session['luuc_landuse_layer_count']) + \
                                           ' landuse layers. If you would like to select a different number of ' + \
                                           'new landuse layers, go back to the previous step and enter the number desired.'
                request.session['luuc_landuse_layers_filenames'] = []
                request.session['luuc_landuse_layers_filepaths'] = []
                return render(request, 'luuchecker/index.html')

            filename = landuse_layer.name
            landuse_layer_filename = os.path.splitext(filename)[0]
            landuse_layer_filepath = request.session.get(
                'luuc_landuse_dir') + '/' + landuse_layer_filename + '/w001001.adf'

            request.session['progress_message'] = []
            request.session['error'] = []

            if os.path.exists(landuse_layer_filepath):
                request.session['luuc_landuse_layers_filenames'].append(
                    landuse_layer_filename)
                request.session['luuc_landuse_layers_filepaths'].append(
                    request.session[
                        'luuc_landuse_dir'] + '/' + landuse_layer_filename)
                request.session['progress_message'].append(
                    'Landuse file names taken.')
                return render(request, 'luuchecker/index.html')
            else:
                request.session[
                    'error'] = 'Could not find the location of folder ' + \
                               landuse_layer_filename + '/w001001.adf ' + \
                               'in the landuse folder previously uploaded ' + \
                               'in step 2. Please check if the folder exists ' + \
                               'inside the landuse folder and upload ' + \
                               'the zipped landuse folder again.'
                return render(request, 'luuchecker/index.html')
    return render(request, 'luuchecker/index.html')


@login_required
def select_percentage(request):
    """ This view uploads the percentage information """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user made a post request
    if request.method == 'GET':
        return render(request, 'luuchecker/index.html')

    if request.method == 'POST':
        try:
            landuse_percent = request.POST.get('luuc_landuse_percentage')
        except:
            request.session[
                'error'] = 'Unable to retrieve submitted percentage value, please try again. If the issue ' + \
                           'persists please use the Contact Us form to request further assistance ' + \
                           'from the site admins.'
            return render(request, 'luuchecker/index.html')

    if not landuse_percent:
        request.session['error'] = 'Please enter some percentage value.'
        return render(request, 'luuchecker/index.html')

    if not float(landuse_percent):
        request.session[
            'error'] = 'Please enter some percentage value in decimal number.'
        return render(request, 'luuchecker/index.html')

    request.session['luuc_landuse_percentage'] = landuse_percent
    request.session['progress_message'].append('Percentage value taken.')

    return render(request, 'luuchecker/index.html')


@login_required
def request_process(request):
    """
    This view is the heart of LUU_CHECKER
    LOGIC:
    1) Set up output strcture
    2) Get all directory and uploaded information through session
    3) Convert subbasin file and adf files to tiff files
    4) Check for landuses available in layers that are not present in base layer. Print this information in EMERGING_LULC.txt file
    5) modify and update that information in base layer 
    6) convert and copy the updated base layer into the output.
    """
    request.session['error'] = []
    request.session['progress_message'] = []

    # put all necessary path info for processing into single dictionary
    data = {
        'user_id': request.user.id,
        'user_email': request.user.email,
        'user_first_name': request.user.first_name,
        'task_id': os.path.basename(request.session.get('directory')),
        'process_root_dir': request.session.get('directory'),
        'output_dir': settings.BASE_DIR + '/user_data/' + request.user.email + '/' +
                      request.session['unique_directory_name'] + '/Output',
        'output_directory': request.session.get('directory') + '/Output',
        'temp_output_directory': request.session.get(
            'directory') + '/TempOutput',
        'subbasin_shapefile_filepath': request.session.get(
            'luuc_subbasin_shapefile_filepath'),
        'subbasin_shapefile_filename': request.session.get(
            'luuc_subbasin_shapefile_filename'),
        'base_landuse_raster_filepath': request.session.get(
            'luuc_base_landuse_raster_filepath'),
        'base_landuse_raster_adf_filepath': request.session.get(
            'luuc_base_landuse_raster_filepath') + '/w001001.adf',
        'base_landuse_raster_filename': request.session.get(
            'luuc_base_landuse_raster_filename'),
        'new_landuse_raster_filepaths': request.session.get(
            'luuc_landuse_layers_filepaths'),
        'new_landuse_raster_filenames': request.session.get(
            'luuc_landuse_layers_filenames'),
        'landuse_percent': request.session.get('luuc_landuse_percentage'),
    }

    if not request.session['error']:
        # run task
        process_task.delay(data)

        # add task id to database
        add_task_id_to_database(data['user_id'], data['user_email'],
                                data['task_id'])

        request.session['progress_message'].append(
            'Job successfully added to queue. You will receive an email with ' + \
            'a link to your files once the processing has completed.')

    return render(request, 'luuchecker/index.html')


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
                                                            settings.BASE_DIR + '/user_data/' + request.user.email + '/' + task_id + '/Output'):
                file = io.BytesIO()

                dir_to_zip = settings.BASE_DIR + '/user_data/' + request.user.email + \
                             '/' + task_id + '/Output'

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
        refreshes the LUU Checker home page. """

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

    return HttpResponseRedirect(resolve_url('luuchecker'))
