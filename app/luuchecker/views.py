from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template.response import TemplateResponse
from django.utils import timezone

from common.utils import create_working_directory, fix_file_permissions
from .tasks import process_task
from swatusers.models import UserTask

import io
import logging
import os
import shutil
import subprocess
import zipfile


logger = logging.getLogger('luuchecker')


@login_required
def index(request):
    # Check whether or not user is authenticated, if not return to login page
    if not request.user.is_authenticated:
        return HttpResponseRedirect(resolve_url('login'))
    else:
        # Clear progress message
        request.session['progress_message'] = []
        # Set user's unique directory that will hold their uploaded files
        unique_directory_name = "uid_{0}_{1}_{2}".format(
            str(request.user.id),
            "luuchecker",
            timezone.datetime.now().strftime("%Y%m%dT%H%M%S"))
        unique_path = os.path.join(settings.USER_UPLOAD_DIR, request.user.email, unique_directory_name)
        request.session['unique_directory_name'] = unique_directory_name
        request.session['directory'] = unique_path
        # Render main LUU Checker view
        return render(request, 'luuchecker/index.html')


@login_required
def upload_subbasin_shapefile_zip(request):
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_subbasin'] = []

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        logger.info('Receiving the subbasin shapefile zip')
        if 'subbasin_shapefile_zip' in request.FILES:
            try:
                # Get the uploaded file and store the name of the zip
                file = request.FILES['subbasin_shapefile_zip']
                filename = file.name
                subbasin_shapefile_file = os.path.splitext(filename)
                subbasin_shapefile_filename = subbasin_shapefile_file[0]
                subbasin_shapefile_file_ext = subbasin_shapefile_file[1]
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to receive uploaded shapefile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded ' \
                            'file, please try again. If the ' \
                            'issue persists please use the ' \
                            'Contact Us form to request ' \
                            'further assistance from the ' \
                            'site admins.'
                request.session['error'] = error_msg
                request.session['error_subbasin'] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            if subbasin_shapefile_file_ext != ".zip":
                logger.error(
                    "{0}: Uploaded shapefile does not have .zip "
                    "extension.".format(
                        request.session.get("unique_directory_name")))
                error_msg = "The file you are uploading does not have a .zip " \
                            "extension. Make sure the file you are uploading " \
                            "is a compressed zipfile. Please refer to the " \
                            "user manual if you need help creating a zipfile."
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url("luuchecker"))

            try:
                # Set up the working directory
                unique_path = request.session.get("directory")
                create_working_directory(unique_path)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to create working directory.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to set up user workspace, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            try:
                # If the shapefile directory already exists,
                # remove it to make way for new upload
                shp_path = os.path.join(unique_path, 'input', subbasin_shapefile_filename)
                if os.path.exists(shp_path):
                    shutil.rmtree(shp_path)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to remove previously uploaded file.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the tool. ' \
                            'If the issue persists please use the Contact Us ' \
                            'form to request further assistance from the ' \
                            'site admins.'
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            try:
                # Copy compressed data to the working directory
                with open(os.path.join(unique_path, 'input', filename),
                          'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to write uploaded shapefile to disk.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            # Uncompress the data
            logger.info('Unzipping the uploaded file')
            try:
                filepath = os.path.join(unique_path, 'input', subbasin_shapefile_filename)
                subprocess.call([
                    "unzip",
                    "-qq", "-o",
                    filepath,
                    "-d",
                    unique_path + "/input/"
                ])

                # Set permissions for unzipped data
                fix_file_permissions(filepath)

                # Remove uploaded zip file
                os.remove(filepath + subbasin_shapefile_file_ext)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to unzip uploaded shapefile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to unzip the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            if not os.path.exists(filepath):
                logger.error(
                    "{0}: Unable to extract subbasin shapefile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not extract the folder ' \
                            '"subbasin_shapefile_filename + '". Please check " \
                            "if the file is compressed in zip format and has " \
                            "the same name as compressed folder. If the " \
                            "issue persists please use the Contact Us form " \
                            "to request further assistance from the site " \
                            "admins."
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            subbasin_shapefile_filepath = f'{unique_path}/input/{subbasin_shapefile_filename}/{subbasin_shapefile_filename}.shp'

            if not os.path.exists(subbasin_shapefile_filepath):
                logger.error(
                    "{0}: Unable upload subbasin shapefile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not find the folder ' + \
                            subbasin_shapefile_filename + '/' + subbasin_shapefile_filename + '.shp. ' \
                            'Please check for files in folder and re-upload ' \
                            'the zip file. If the issue persists please use ' \
                            'the Contact Us form to request further ' \
                            'assistance from the site admins.'
                request.session["error"] = error_msg
                request.session["error_subbasin"] = error_msg
                return HttpResponseRedirect(resolve_url('luuchecker'))

            # Update relevant session variables
            request.session[
                'luuc_subbasin_shapefile_filename'] = subbasin_shapefile_filename
            request.session[
                'luuc_subbasin_shapefile_filepath'] = subbasin_shapefile_filepath
            request.session['progress_message'].append(
                'Subbasin shapefile uploaded.')
            logger.info('Subbasin shapefile successfully uploaded and extracted from zip')

            # Render the main page
            return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find a required subbasin shapefile, return error msg
            request.session['error'] = 'Please select your zipped subbasin ' \
                                       'shapefile before clicking the Upload ' \
                                       'button.'
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
    request.session['error_landuse'] = []

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        logger.info('Receiving the landuse zip')
        if 'landuse_folder_zip' in request.FILES:
            try:
                # Get uploaded file and store the name of the zip
                file = request.FILES['landuse_folder_zip']
                filename = file.name
                landuse_filename, landuse_ext = os.path.splitext(filename)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable receive uploaded landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')

            # Set up the working directory
            unique_path = request.session.get('directory')

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + landuse_filename):
                    shutil.rmtree(unique_path + '/input/' + landuse_filename)
            except Exception as e:
                logger.error(str(e))
                logger.error(
                    "{0}: Unable to remove previously uploaded landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the tool. ' \
                            'If the issue persists please use the Contact Us ' \
                            'form to request further assistance from the ' \
                            'site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')

            try:
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
                return render(request, 'luuchecker/index.html')

            if landuse_ext != ".zip":
                logger.error(
                    "{0}: Uploaded landuse file does not have .zip "
                    "extension.".format(
                        request.session.get("unique_directory_name")))
                error_msg = "The file you are uploading does not have a .zip " \
                            "extension. Make sure the file you are uploading " \
                            "is a compressed zipfile. Please refer to the " \
                            "user manual if you need help creating a zipfile."
                request.session["error"] = error_msg
                request.session["error_landuse"] = error_msg
                return render(request, "luuchecker/index.html")

            # Uncompress the zip
            logger.info('Unzipping the uploaded file')
            try:
                filepath = "{0}/input/{1}".format(
                    unique_path,
                    landuse_filename
                )
                subprocess.call([
                    "unzip",
                    "-qq", "-o",
                    filepath,
                    "-d",
                    unique_path + "/input/"
                ])

                # Set permissions for unzipped data
                fix_file_permissions(os.path.join(unique_path, 'input', landuse_filename))

                # Remove landuse zip
                os.remove(os.path.join(unique_path, 'input', filename))
            except Exception as e:
                logger.error(str(e))
                # Create error message if unzip failed
                logger.error(
                    "{0}: Unable to unzip the landuse zipfile.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not unzip the folder. If the issue ' \
                            'persists please use the Contact Us form to ' \
                            'request further assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')

            # Check if unzipped folder exists
            if not os.path.exists(os.path.join(unique_path, 'input', landuse_filename)):
                logger.error(
                    "{0}: Unable to find unzipped landuse folder.".format(
                        request.session.get('unique_directory_name')))
                error_msg = 'Could not unzip the folder "' + \
                            landuse_filename + '". Please check if the file ' \
                            'is compressed in zip format and has the same '  \
                            'name as compressed folder. If the issue ' \
                            'persists please use the Contact Us ' \
                            'form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')

            # Update relevant session variables
            request.session['luuc_landuse_filename'] = filename
            request.session['luuc_landuse_dir'] = os.path.join(unique_path, 'input', landuse_filename)
            request.session['progress_message'].append(
                'Landuse zip folder uploaded.')
            logger.info('Landuse rasters successfully uploaded and extracted from zip')
            return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find the required zipped landuse folder, return error msg
            error_msg = 'Please select your zipped landuse folder ' \
                        'before clicking the Upload button.'
            request.session['error'] = error_msg
            request.session['error_landuse'] = error_msg
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
    request.session['error_base_landuse'] = []

    # If user is submitting a zipped landuse folder
    if request.method == 'POST':
        logger.info('Receiving base landuse raster file')
        if 'base_landuse_raster_file' in request.FILES:
            # Get uploaded file and store the name of the zip
            base_landuse_raster = request.FILES['base_landuse_raster_file']

            if not base_landuse_raster:
                error_msg = 'Please select the base raster.'
                request.session['error'] = error_msg
                request.session['error_base_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')

            try:
                base_landuse_raster_filename, base_landuse_layer_ext = os.path.splitext(base_landuse_raster.name)
                # Check for .xml extension
                if base_landuse_layer_ext == ".xml":
                    base_landuse_raster_filename = os.path.splitext(base_landuse_raster_filename)[0]

                base_landuse_raster_location = request.session.get(
                    'luuc_landuse_dir') + '/' + base_landuse_raster_filename + '/w001001.adf'
            except Exception as e:
                logger.error(str(e))
                error_msg = 'Unable to match selected layer with layers ' \
                            'uploaded in the zipped landuse folder. Make ' \
                            'sure you are selecting the .aux files.'
                request.session['error'] = error_msg
                request.session['error_base_landuse'] = error_msg

            request.session['progress_message'] = []
            request.session['error'] = []
            request.session['error_base_landuse'] = []

            if os.path.exists(base_landuse_raster_location):
                request.session[
                    'luuc_base_landuse_raster_filename'] = base_landuse_raster_filename
                request.session[
                    'luuc_base_landuse_raster_filepath'] = request.session.get(
                    'luuc_landuse_dir') + '/' + base_landuse_raster_filename
                request.session['progress_message'].append(
                    'Landuse file\'s name taken.')
                logger.info('Base landuse raster successfully uploaded')
                return render(request, 'luuchecker/index.html')
            else:
                error_msg = 'Could not find the location ' + \
                            base_landuse_raster_filename + '/w001001.adf in ' \
                            'the landuse folder previously uploaded in ' \
                            'step 2. Please check if the folder exists ' \
                            'inside the zipped landuse folder and upload ' \
                            'the zipped landuse folder again.'
                request.session['error'] = error_msg
                request.session['error_base_landuse'] = error_msg
                return render(request, 'luuchecker/index.html')
        else:
            # Couldn't find the required base landuse layer, return error msg
            error_msg = 'Please select your base landuse layer before ' \
                        'clicking the Upload button.'
            request.session['error'] = error_msg
            request.session['error_base_landuse'] = error_msg
            return render(request, 'luuchecker/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'luuchecker/index.html')


@login_required
def select_number_of_landuse_layers(request):
    """ This view gets the number of landuse layers in the
    landuse zip other than the base layer """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_num_of_new_layers'] = []

    # If user made a post request
    if request.method == 'POST':
        logger.info('Receiving number of landuse layers to analyze')
        # Get the posted landuse layer count value
        landuse_layer_count = request.POST.get('luuc_landuse_layer_count')
        try:
            # Try converting the count to an integer
            landuse_layer_count = int(landuse_layer_count)
        except ValueError as e:
            logger.error(str(e))
            # If it fails, display error
            error_msg = 'Please enter a number.'
            request.session['error'] = error_msg
            request.session['error_num_of_new_layers'] = error_msg
            return render(request, 'luuchecker/index.html')

        # If no value was posted, display error
        if not landuse_layer_count:
            error_msg = 'Please enter a value greater than 0.'
            request.session['error'] = error_msg
            request.session['error_num_of_new_layers'] = error_msg
            return render(request, 'luuchecker/index.html')

        # If value posted, but less than 1, display error
        if landuse_layer_count < 1:
            error_msg = 'Please enter a value greater than 0.'
            request.session['error'] = error_msg
            request.session['error_num_of_new_layers'] = error_msg
            return render(request, 'luuchecker/index.html')

        # Update relevant session variable
        request.session['luuc_landuse_layer_count'] = landuse_layer_count

        # Create numerical list starting with 1 to count value submitted
        # and add it to context
        context = {
            'luuc_loop_times': [i + 1 for i in range(landuse_layer_count)]
        }
        logger.info('Landuse layer count validated')
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
    request.session['error_new_layer'] = []

    if request.method == 'GET':
        return render(request, 'luuchecker/index.html')

    # If user made a post request
    if request.method == 'POST':
        logger.info('Receiving selected landuse layers for analysis')
        try:
            landuse_layer_files = request.FILES.getlist('luuc_landuse_layers')
        except:
            error_msg = 'Unable to receive the uploaded file, please try ' \
                        'again. If the issue persists please use the ' \
                        'Contact Us form to request further assistance ' \
                        'from the site admins.'
            request.session['error'] = error_msg
            request.session['error_new_layer'] = error_msg
            return render(request, 'luuchecker/index.html')

        if request.session['luuc_landuse_layer_count'] != len(landuse_layer_files):
            error_msg = 'Please select ' + str(request.session['luuc_landuse_layer_count']) + \
                        ' landuse layers. If you would like to select a different number of ' + \
                        'new landuse layers, go back to the previous step and enter the number desired.'
            request.session['error'] = error_msg
            request.session['error_new_layer'] = error_msg
            return render(request, 'luuchecker/index.html')

        for landuse_layer in landuse_layer_files:
            if not landuse_layer:
                error_msg = 'Please select ' + str(
                    request.session['luuc_landuse_layer_count']) + \
                                           ' landuse layers. If you would like to select a different number of ' + \
                                           'new landuse layers, go back to the previous step and enter the number desired.'
                request.session['error'] = error_msg
                request.session['error_new_layer'] = error_msg
                request.session['luuc_landuse_layers_filenames'] = []
                request.session['luuc_landuse_layers_filepaths'] = []
                return render(request, 'luuchecker/index.html')

            filename = landuse_layer.name
            landuse_layer_filename, landuse_layer_ext = os.path.splitext(
                landuse_layer.name)
            # Check for .xml extension
            if landuse_layer_ext == ".xml":
                landuse_layer_filename = \
                os.path.splitext(landuse_layer_filename)[0]
            landuse_layer_filepath = request.session.get(
                'luuc_landuse_dir') + '/' + landuse_layer_filename + '/w001001.adf'

            request.session['progress_message'] = []
            request.session['error'] = []
            request.session['error_new_layer'] = []

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
                error_msg = 'Could not find the location of folder ' + \
                            landuse_layer_filename + '/w001001.adf in the ' \
                            'landuse folder previously uploaded in step 2. ' \
                            'Please check if the folder exists inside the ' \
                            'landuse folder and upload the zipped landuse ' \
                            'folder again.'
                request.session['error'] = error_msg
                request.session['error_new_layer'] = error_msg
                return render(request, 'luuchecker/index.html')
        logger.info('Selected landuse layers successfully processed')
    return render(request, 'luuchecker/index.html')


@login_required
def select_percentage(request):
    """ This view uploads the percentage information """
    # Clear any existing progress messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_lulc_perc'] = []

    # If user made a post request
    if request.method == 'GET':
        return render(request, 'luuchecker/index.html')

    if request.method == 'POST':
        logger.info('Receiving landuse percentage')
        try:
            landuse_percent = request.POST.get('luuc_landuse_percentage')
        except Exception as e:
            logger.error(str(e))
            error_msg = 'Unable to retrieve submitted percentage value, ' \
                        'please try again. If the issue persists please ' \
                        'use the Contact Us form to request further ' \
                        'assistance from the site admins.'
            request.session['error'] = error_msg
            request.session['error_lulc_perc'] = error_msg
            return render(request, 'luuchecker/index.html')

    if not landuse_percent:
        error_msg = 'Please enter some percentage value.'
        request.session['error'] = error_msg
        request.session['error_lulc_perc'] = error_msg
        return render(request, 'luuchecker/index.html')

    if not float(landuse_percent):
        error_msg = 'Please enter some percentage value in decimal number.'
        request.session['error'] = error_msg
        request.session['error_lulc_perc'] = error_msg
        return render(request, 'luuchecker/index.html')

    request.session['luuc_landuse_percentage'] = landuse_percent
    request.session['progress_message'].append('Percentage value taken.')
    logger.info('Landuse percentage validated')
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
    logger.info('Preparing process request for Celery task')
    # put all necessary path info for processing into single dictionary
    data = {
        'user_id': request.user.id,
        'user_email': request.user.email,
        'user_first_name': request.user.first_name,
        'task_id': os.path.basename(request.session.get('directory')),
        'process_root_dir': request.session.get('directory'),
        'results_directory': os.path.join(settings.USER_RESULT_DIR, request.user.email, request.session['unique_directory_name'], 'Output'),
        'output_directory': os.path.join(request.session.get('directory'), 'Output'),
        'temp_output_directory': os.path.join(request.session.get('directory'), 'TempOutput'),
        'subbasin_shapefile_filepath': request.session.get('luuc_subbasin_shapefile_filepath'),
        'subbasin_shapefile_filename': request.session.get('luuc_subbasin_shapefile_filename'),
        'base_landuse_raster_filepath': request.session.get('luuc_base_landuse_raster_filepath'),
        'base_landuse_raster_adf_filepath': os.path.join(request.session.get('luuc_base_landuse_raster_filepath'), 'w001001.adf'),
        'base_landuse_raster_filename': request.session.get('luuc_base_landuse_raster_filename'),
        'new_landuse_raster_filepaths': request.session.get('luuc_landuse_layers_filepaths'),
        'new_landuse_raster_filenames': request.session.get('luuc_landuse_layers_filenames'),
        'landuse_percent': request.session.get('luuc_landuse_percentage'),
    }

    if not request.session['error']:
        # run task
        logger.info('Sending task to Celery worker')
        process_task.delay(data)
        logger.info('Task received by Celery worker')

        # add task id to database
        logger.info('Adding task to database to track progress')
        add_task_id_to_database(
            data['user_id'],
            data['user_email'],
            data['task_id'])
        logger.info('Task added to database')

        request.session['progress_message'].append(
            'Job successfully added to queue. You will receive an email '
            'with a link to your files once the processing has completed.')

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
            if os.path.exists(os.path.join(settings.USER_RESULT_DIR, request.user.email, task_id, 'output')):
                file = io.BytesIO()

                dir_to_zip = os.path.join(settings.USER_RESULT_DIR, request.user.email, task_id, 'output')

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


@login_required
def reset(request):
    """ 
    This view clears the session, deletes all existing data and
    refreshes the LUU Checker home page. 
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

    return HttpResponseRedirect(resolve_url('luuchecker'))
