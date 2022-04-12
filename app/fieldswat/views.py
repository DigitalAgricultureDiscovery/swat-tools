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

import glob
import jaydebeapi
import logging
import io
import os
import pandas as pd
import shutil
import subprocess
import zipfile


logger = logging.getLogger('django')


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
        request.session['error_field_shp'] = []
        request.session['error_agg_out'] = []

        # Set user's unique directory that will hold their uploaded files
        unique_directory_name = "uid_{0}_{1}_{2}".format(
            str(request.user.id),
            "fieldswat",
            timezone.datetime.now().strftime("%Y%m%dT%H%M%S"))
        unique_path = "{0}{1}/{2}".format(
            settings.UPLOAD_DIR,
            request.user.email,
            unique_directory_name)
        request.session['directory'] = unique_path
        request.session['on_s3'] = {}
        request.session['unique_directory_name'] = unique_directory_name
        # Render main FieldSWAT view
        return render(request, 'fieldswat/index.html')


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
            return render(request, 'fieldswat/index.html')

        validation_results = swat_model.validate_model()
        if validation_results["status"] == 1:
            request.session['error'] = validation_results['errors']
            request.session['error_swat_model'] = validation_results['errors']
            return render(request, 'fieldswat/index.html')
        try:
            # fetch data from SWATOutput.mdb
            swatoutput_mdb_data = get_unique_years_from_mdb(
                swat_model.get_directory())

            request.session['swatoutput_years'] = swatoutput_mdb_data['years']
            request.session['swatoutput_runoff'] = swatoutput_mdb_data['runoff']
            request.session['swatoutput_sediment'] = swatoutput_mdb_data['sediment']

            # get unique_years
            unique_years = list(set(swatoutput_mdb_data['years']))
            unique_years.sort()
        except Exception as e:
            logger.error(str(e))
            logger.error("{0}: Missing .hru file or unique year in database.".format(
                request.session.get('unique_directory_name')))
            error_msg = 'You are either missing a .hru file or unique ' \
                        'year in your database. Please compare your ' \
                        'database with the example data to assess ' \
                        'its compatibility with the Field_SWAT tool. ' \
                        'If the issue persists then use the ' \
                        '"Contact Us" option to report your issue to ' \
                        'the Site Administrator.'
            request.session['error'] = error_msg
            request.session['error_swat_model'] = error_msg
            return render(request, 'fieldswat/index.html')

        request.session['swatoutput_unique_years'] = unique_years

        # add unique years to context
        context = {
            'fieldswat_unique_years': [year for year in unique_years]
        }

        # Update relevant session variables
        request.session['fieldswat_swat_model_filename'] = swat_model.get_filename()
        request.session['fieldswat_swat_model_dir'] = swat_model.get_directory()

        request.session['progress_message'].append(
            'Swat Model zip folder uploaded.')

        # Render the main page
        return render(request, 'fieldswat/index.html', context)
    else:
        # Nothing was posted, reload main page
        return render(request, 'fieldswat/index.html')


def calculate_annual_means_from_mdb(records):
    """
    Calculates annual sediment and runoff means for monthly data.

    Parameters
    ----------
    records: list
        Data fetched from SWAT mdb

    Returns
    -------
    updated_records: list
        SWAT mdb data with annual means
    """
    # Convert records from list of tuples to Pandas DataFrame
    df = pd.DataFrame.from_records(records)

    # Calculate runoff (3) and sediment (4) means based on year (0) and hru (2)
    return df.groupby([0, 2], as_index=False)[3, 4].mean()


def get_unique_years_from_mdb(swat_model_dir):
    """
    Reads SWATOutput.mdb and queries all of the runoff and sediment data.

    Parameters
    ----------
    swat_model_dir: string
        Path to uploaded swat model's directory

    Returns
    -------
    swat_mdb_data: list of lists
        List of years, runoff, and sediment data stored in their own lists
    """
    # java jdbc driver for reading access databases
    ucanaccess_jars = [
        "/opt/UCanAccess/ucanaccess-4.0.4.jar",
        "/opt/UCanAccess/lib/commons-lang-2.6.jar",
        "/opt/UCanAccess/lib/commons-logging-1.1.3.jar",
        "/opt/UCanAccess/lib/hsqldb.jar",
        "/opt/UCanAccess/lib/jackcess-2.1.11.jar",
    ]
    classpath = ":".join(ucanaccess_jars)

    # create path to SWATOutput.mdb
    swat_mdb_filepath = os.path.join(
        swat_model_dir,
        'Scenarios/Default/TablesOut/SWATOutput.mdb'
    )

    # open SWATOutput.mdb using pyodbc and MDBTools driver
    dbcon = jaydebeapi.connect(
        "net.ucanaccess.jdbc.UcanaccessDriver",
        f"jdbc:ucanaccess://{swat_mdb_filepath};",
        ["", ""],
        classpath
    )
    cursor = dbcon.cursor()

    # construct sql query and execute
    sql_query = 'SELECT YEAR, MON, HRU, SURQ_GENmm, SYLDt_ha FROM hru'
    cursor.execute(sql_query)

    # fetch query results
    query_records = cursor.fetchall()

    # close database connection
    dbcon.close()

    # check if data is at annual or monthly intervals
    # we will assume if the first MON value is less
    # than 4 digits that we have monthly data
    if len(str(query_records[0][1])) < 4:
        query_records = calculate_annual_means_from_mdb(query_records)
        return {
            'years': query_records[0].values.tolist(),
            'runoff': query_records[3].values.tolist(),
            'sediment': query_records[4].values.tolist()
        }
    else:
        # store query results in list objects
        years = []
        runoff = []
        sediment = []

        # loop through records and append to lists
        for record in query_records:
            years.append(record[0])
            runoff.append(record[3])
            sediment.append(record[4])

        # convert lists to numpy arrays
        return {
            'years': years,
            'runoff': runoff,
            'sediment': sediment
        }


@login_required
def select_year(request):
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is selecting a year
    if request.method == 'POST':

        # Get the year
        try:
            fieldswat_selected_year = int(request.POST.get('fieldswat_year'))
        except Exception as e:
            logger.error(str(e))
            request.session['error'] = 'Please select one of the year radio buttons.'
            return render(request, 'fieldswat/index.html')

        if fieldswat_selected_year not in request.session['swatoutput_unique_years']:
            request.session['error'] = 'Please select one of the year radio buttons.'
            return render(request, 'fieldswat/index.html')
        else:
            request.session['fieldswat_selected_year'] = fieldswat_selected_year
            # Render the main page
            return render(request, 'fieldswat/index.html')

    return render(request, 'fieldswat/index.html')


@login_required
def upload_fields_shapefile_zip(request):
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_field_shp'] = []

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        if 'fields_shapefile_zip' in request.FILES:
            try:
                # Get the uploaded file and store the name of the zip
                file = request.FILES['fields_shapefile_zip']
                filename = file.name
                fields_shapefile_foldername, fields_shapefile_ext = os.path.splitext(
                    filename)
            except Exception as e:
                logger.error(str(e))
                logger.error("{0}: Unable to receive the uploaded shapefile.".format(
                    request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please ' \
                            'try again. If the issue persists please use ' \
                            'the Contact Us form to request further ' \
                            'assistance from the site admins.'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')

            # Set up the working directory
            unique_path = request.session.get("directory")

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + fields_shapefile_foldername):
                    shutil.rmtree(unique_path + '/input/' +
                                  fields_shapefile_foldername)
            except Exception as e:
                logger.error(str(e))
                logger.error("{0}: Unable to remove previously uploaded shapefile.".format(
                    request.session.get('unique_directory_name')))
                error_msg = 'Unable to remove previously uploaded file, ' \
                            'please use the Reset button to reset the tool. ' \
                            'If the issue persists please use the Contact Us ' \
                            'form to request further assistance from the ' \
                            'site admins.'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')

            try:
                # Copy compressed data to the working directory
                with open(unique_path + '/input/' + filename, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except Exception as e:
                logger.error(str(e))
                logger.error("{0}: Unable to write uploaded shapefile to disk.".format(
                    request.session.get('unique_directory_name')))
                error_msg = 'Unable to receive the uploaded file, please try ' \
                            'again. If the issue persists please use the ' \
                            'Contact Us form to request further assistance ' \
                            'from the site admins.'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')

            # Make sure the file has the .zip extension
            if fields_shapefile_ext != ".zip":
                logger.error(
                    "{0}: Uploaded shapefile does not have .zip extension.".format(
                        request.session.get("unique_directory_name")))
                error_msg = "The file you are uploading does not have a .zip " \
                            "extension. Make sure the file you are uploading " \
                            "is a compressed zipfile. Please refer to the " \
                            "user manual if you need help creating a zipfile."
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, "fieldswat/index.html")

            # Uncompress the data
            try:
                filepath = "{0}/input/{1}".format(
                    unique_path,
                    fields_shapefile_foldername
                )
                subprocess.call([
                    "unzip",
                    "-qq", "-o",
                    filepath,
                    "-d",
                    unique_path + "/input/"
                ])

                # Set permissions for unzipped data
                fix_file_permissions(
                    unique_path + '/input/' + fields_shapefile_foldername)

                # Remove landuse zip
                os.remove(unique_path + '/input/' + filename)
            except Exception as e:
                logger.error(str(e))
                logger.error("{0}: Unable to extract zipped shapefile.".format(
                    request.session.get('unique_directory_name')))
                error_msg = 'Could not unzip the folder. Please contact ' \
                            'administrator'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')

            if not os.path.exists(unique_path + '/input/' + fields_shapefile_foldername):
                logger.error("{0}: Unable to locate extracted shapefile's directory.".format(
                    request.session.get('unique_directory_name')))
                error_msg = 'Could not extract the folder "{0}". Please ' \
                            'check if the file is compressed in zip format ' \
                            'and has the same name as compressed ' \
                            'folder.'.format(fields_shapefile_foldername)
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')

            # directory path for the unzipped shapefile folder
            fields_shapefile_filepath = unique_path + \
                '/input/' + fields_shapefile_foldername

            # loop through folder and grab any file ending with the .shp
            shapefiles = []
            for shapefile in glob.glob(fields_shapefile_filepath + '/*.shp'):
                shapefiles.append(shapefile)

            # too many .shp present
            if len(shapefiles) > 1:
                error_msg = 'More than one shapefile found in the zipped ' \
                            'folder. Please re-upload with only one shapefile.'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')
            # no .shp present
            elif len(shapefiles) < 1:
                error_msg = 'No shapefiles found in the zipped folder. ' \
                            'Please re-upload with a single shapefile.'
                request.session['error'] = error_msg
                request.session['error_field_shp'] = error_msg
                return render(request, 'fieldswat/index.html')
            # single .shp present
            else:
                fields_shapefile_filename = shapefiles[0]

            # Update relevant session variables
            request.session['fieldswat_fields_shapefile_filename'] = fields_shapefile_filename
            request.session['fieldswat_fields_shapefile_filepath'] = fields_shapefile_filepath
            request.session['progress_message'].append(
                'Fields shapefile uploaded.')

            # Render the main page
            return render(request, 'fieldswat/index.html')
        else:
            logger.error("{0}: Unable to find uploaded shapefile.".format(
                request.session.get('unique_directory_name')))
            error_msg = 'Unable to receive the uploaded file, please try ' \
                        'again. If the issue persists please use the ' \
                        'Contact Us form to request further assistance from ' \
                        'the site admins.'
            request.session['error'] = error_msg
            request.session['error_field_shp'] = error_msg
            return render(request, 'fieldswat/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'fieldswat/index.html')


@login_required
def confirm_output_and_agg(request):
    """
    Confirms which Output and Aggregation Method radio buttons were selected
    by the user in Step 3. After validating the radio button value, the
    selected values are added to their own session variables.
    """
    # clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []
    request.session['error_agg_out'] = []

    # if user is submitting a zipped SWAT Model
    if request.method == 'POST':
        try:
            # retrieve posted values
            output_type = request.POST.get('fieldswat_output')
            aggregation_method = request.POST.get('fieldswat_agg')
        except Exception as e:
            logger.error(str(e))
            error_msg = 'Unable to find selected output and aggregation ' \
                        'methods. Please make sure you have selected an ' \
                        'option for both of these methods and then try again.'
            request.session['error'] = error_msg
            request.session['error_agg_out'] = error_msg
            return render(request, 'fieldswat/index.html')

        # verify the value matches what we would expect
        if output_type != u'runoff' and output_type != u'sediment':
            error_msg = 'Output type is not recognized. Please make sure a ' \
                        'radio button is selected under Output.'
            request.session['error'] = error_msg
            request.session['error_agg_out'] = error_msg
            return render(request, 'fieldswat/index.html')

        # verify the value matches what we would expect
        if aggregation_method != 'mean' and aggregation_method != 'mode' and \
                aggregation_method != 'geomean' and aggregation_method != 'area_weighted_mean':
            error_msg = 'Aggregation method is not recognized. Please make ' \
                        'sure a radio button is selected under ' \
                        'Aggregation method.'
            request.session['error'] = error_msg
            request.session['error_agg_out'] = error_msg
            return render(request, 'fieldswat/index.html')

        # add selected values to session variables
        request.session['fieldswat_output_type'] = output_type
        request.session['fieldswat_aggregation_method'] = aggregation_method

    return render(request, 'fieldswat/index.html')


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
        'results_dir': os.path.join(settings.USER_RESULT_DIR, request.user.email, request.session['unique_directory_name'], 'Output'),
        'output_dir': os.path.join(request.session.get('directory'), 'Output'),
        'hrus1_dir': os.path.join(request.session.get('fieldswat_swat_model_dir'), 'Watershed', 'Grid', 'hrus1'),
        'fieldswat_swat_model_dir': request.session['fieldswat_swat_model_dir'],
        'fieldswat_fields_shapefile_filename': request.session.get('fieldswat_fields_shapefile_filename'),
        'fieldswat_fields_shapefile_filepath': request.session.get('fieldswat_fields_shapefile_filepath'),
        'fieldswat_output_type': request.session['fieldswat_output_type'],
        'fieldswat_aggregation_method': request.session['fieldswat_aggregation_method'],
        'swatoutput_years': request.session['swatoutput_years'],
        'swatoutput_runoff': request.session['swatoutput_runoff'],
        'swatoutput_sediment': request.session['swatoutput_sediment'],
        'fieldswat_selected_year': request.session['fieldswat_selected_year'],
    }

    if not request.session['error']:
        # run task
        process_task.delay(data)

        # add task id to database
        add_task_id_to_database(
            data['user_id'], data['user_email'], data['task_id'])

        request.session['progress_message'].append(
            'Job successfully added to queue. You will receive an email with ' +
            'a link to your files once the processing has completed.')

    return render(request, 'fieldswat/index.html')


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
    refreshes the FieldSWAT home page.
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

    return HttpResponseRedirect(resolve_url('fieldswat'))


@login_required
def download_data(request):
    task_id = request.GET.get('id', '')
    if task_id != '':
        user_id = task_id.split('_')[1]
        if int(user_id) == int(request.user.id):
            if os.path.exists(os.path.join(settings.USER_RESULT_DIR, request.user.email, task_id, '/output')):
                file = io.BytesIO()

                dir_to_zip = os.path.exists(os.path.join(settings.USER_RESULT_DIR, request.user.email, task_id, '/output'))

                dir_to_zip_len = len(dir_to_zip.rstrip(os.sep)) + 1

                with zipfile.ZipFile(file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.external_attr = 0o0770
                    for dirname, subdirs, files in os.walk(dir_to_zip):
                        for filename in files:
                            path = os.path.join(dirname, filename)
                            entry = path[dir_to_zip_len:]
                            zf.write(path, entry)
                zf.close()

                response = HttpResponse(
                    file.getvalue(), content_type="application/zip")
                response['Content-Disposition'] = 'attachment; filename=' + \
                    task_id + '.zip'
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
