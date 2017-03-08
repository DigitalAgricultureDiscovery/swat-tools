from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, resolve_url
from django.template import RequestContext
from django.template.response import TemplateResponse
from swatusers.models import UserTask
from fieldswat.tasks import process_task
import datetime
import glob
import io
import os
import pypyodbc
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
        unique_directory_name = 'uid_' + str(request.user.id) + '_fieldswat_' + \
                                datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        unique_path = settings.TMP_DIR + '/user_data/' + request.user.email + \
              '/' + unique_directory_name
        request.session['directory'] = unique_path
        request.session['unique_directory_name'] = unique_directory_name
        # Render main FieldSWAT view
        return render(request, 'fieldswat/index.html')


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

    if not os.path.exists(settings.TMP_DIR + '/user_data/' + request.user.email):
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
    """
    This view uploads and extracts the SWAT model zip
    in to the input directory.
    """
    # Clear any previous progress or error messages
    request.session['progress_complete'] = []
    request.session['progress_message'] = []
    request.session['error'] = []

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        if 'swat_model_zip' in request.FILES:
            try:
                # Get the uploaded file and store the name of the zip
                file = request.FILES['swat_model_zip']
                filename = file.name
                swat_model_filename = os.path.splitext(filename)[0]
            except:
                request.session['error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            try:
                # Set up the working directory
                create_working_directory(request)
                unique_path = request.session.get("directory")
            except:
                request.session['error'] = 'Unable to set up user workspace, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            try:
                # If the shapefile directory already exists, remove it to make way for new upload
                if os.path.exists(unique_path + '/input/' + swat_model_filename):
                    shutil.rmtree(unique_path + '/input/' + swat_model_filename)
            except:
                request.session['error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                                           'to reset the tool. If the issue persists please use the Contact Us ' + \
                                           'form to request further assistance from the site admins.'
                return render(request, 'fieldswat/index.html')

            try:
                # Copy compressed data to the working directory
                with open(unique_path + '/input/' + filename, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except:
                request.session['error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # Uncompress the data
            try:
                unzip_command = 'unzip -qq ' + unique_path + '/input/' + \
                                swat_model_filename + ' -d ' + unique_path + '/input/'
                os.system(unzip_command)

                # Set permissions for unzipped data
                fix_file_permissions(unique_path + '/input/' + swat_model_filename)

                # Remove uploaded zip file
                os.remove(unique_path + '/input/' + filename)
            except:
                request.session['error'] = 'Unable to unzip the uploaded file, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # Check if decompression completed or failed (no folder if failed)
            if not os.path.exists(unique_path + '/input/' + swat_model_filename):
                request.session['error'] = 'Could not extract the folder "' + \
                                           swat_model_filename + '". ' + \
                                           'Please check if the file is ' + \
                                           'compressed in zip format and ' + \
                                           'has the same name as ' + \
                                           'compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # Check if the required files/folders exist
            loc = unique_path + '/input/' + swat_model_filename + \
                '/Watershed/Grid/hrus1/w001001.adf'
            shapeloc = unique_path + '/input/' + swat_model_filename + \
                '/Watershed/Shapes/hru1.shp'
            scenarioloc = unique_path + '/input/' + swat_model_filename + \
                '/Scenarios/Default/TxtInOut/*.hru'
            swatoutputdbloc = unique_path + '/input/' + swat_model_filename + \
                '/Scenarios/Default/TablesOut/SWATOutput.mdb'

            # Check if the zip was extracted
            if not os.path.exists(unique_path + '/input/' + swat_model_filename):
                request.session['error'] = 'Could not extract the folder "' + \
                                           swat_model_filename + '". Please ' + \
                                           'check if the file is compressed ' + \
                                           'in zip format and has the same ' + \
                                           'name as compressed folder. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

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
                return render(request, 'fieldswat/index.html')

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
                return render(request, 'fieldswat/index.html')
            if not glob.glob(swatoutputdbloc):
                request.session['error'] = 'Could not find the folder or ' + \
                                           'SWATOutput.mdb access file in ' + \
                                           swat_model_filename + \
                                           '/Scenarios/Default/TablesOut.' + \
                                           'Please check for files in ' + \
                                           'folder and re-upload the zip file. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # If there were no issues finding the required SWAT Model paths
            if os.path.exists(loc):
                # Update relevant session variables
                request.session['fieldswat_swat_model_filename'] = filename
                request.session['fieldswat_swat_model_dir'] = unique_path + '/input/' + \
                    swat_model_filename
                request.session['progress_message'].append(
                    'Swat Model zip folder uploaded.')

                try:
                    # fetch data from SWATOutput.mdb
                    swatoutput_mdb_data = get_unique_years_from_mdb(request.session['fieldswat_swat_model_dir'])

                    request.session['swatoutput_years'] = swatoutput_mdb_data[0]
                    request.session['swatoutput_runoff'] = swatoutput_mdb_data[1]
                    request.session['swatoutput_sediment'] = swatoutput_mdb_data[2]

                    # get unique_years
                    unique_years = list(set(swatoutput_mdb_data[0]))
                    unique_years.sort()
                except:
                    request.session['error'] = 'Either you are missing .hru ' + \
                                               'file or unique year in your ' + \
                                               'database. Please compare your ' + \
                                               'database with the example data '+ \
                                               'to assess its compatibility ' + \
                                               'with the Field_SWAT tool. If ' + \
                                               'the issue persists then use ' + \
                                               'the "Contact Us" option to ' + \
                                               'report your issue to the Site ' + \
                                               'Administrator.'
                    return render(request, 'fieldswat/index.html')

                request.session['swatoutput_unique_years'] = unique_years

                # add unique years to context
                context = RequestContext(request)
                context.push({
                    'fieldswat_unique_years': [year for year in unique_years]
                })

                # Render the main page
                return render(request, 'fieldswat/index.html', context)
            else:
                # Couldn't find a required SWAT Model folder, return error msg
                request.session['error'] = 'Could not find the folder ' + \
                                           swat_model_filename + \
                                           '/Watershed/Grid/hrus1/w001001.adf.' + \
                                           ' Please check for files in folder ' + \
                                           'and re-upload the zip file. If the issue ' + \
                                           'persists please use the Contact Us ' + \
                                           'form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')
        else:
            # Couldn't find a required SWAT Model folder, return error msg
            request.session['error'] = 'Please select your zipped SWAT Model before clicking the Upload button.'
            return render(request, 'fieldswat/index.html')
    else:
        # Nothing was posted, reload main page
        return render(request, 'fieldswat/index.html')


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

    # create path to SWATOutput.mdb
    swat_mdb_filepath = swat_model_dir + '/Scenarios/Default/TablesOut/SWATOutput.mdb'

    # open SWATOutput.mdb using pyodbc and MDBTools driver
    dbcon = pypyodbc.connect('DRIVER={MDBTools};DBQ=' + swat_mdb_filepath + ';')
    cursor = dbcon.cursor()

    # construct sql query and execute
    sql_query = 'SELECT YEAR, SURQ_GENmm, SYLDt_ha FROM hru'
    cursor.execute(sql_query)

    # fetch query results
    query_records = cursor.fetchall()

    # close database connection
    dbcon.close()

    # store query results in list objects
    years = []
    runoff = []
    sediment = []

    # loop through records and append to lists
    for record in query_records:
        years.append(record[0])
        runoff.append(record[1])
        sediment.append(record[2])

    # convert lists to numpy arrays
    swat_mdb_data = [years, runoff, sediment]

    return swat_mdb_data


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
        except:
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

    # If user is submitting a zipped SWAT Model
    if request.method == 'POST':
        if 'fields_shapefile_zip' in request.FILES:
            try:
                # Get the uploaded file and store the name of the zip
                file = request.FILES['fields_shapefile_zip']
                filename = file.name
                fields_shapefile_foldername = os.path.splitext(filename)[0]
            except:
                request.session['error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # Set up the working directory
            unique_path = request.session.get("directory")

            try:
                # If an input directory already exists, remove it
                if os.path.exists(unique_path + '/input/' + fields_shapefile_foldername):
                    shutil.rmtree(unique_path + '/input/' + fields_shapefile_foldername)
            except:
                request.session['error'] = 'Unable to remove previously uploaded file, please use the Reset button ' + \
                                           'to reset the tool. If the issue persists please use the Contact Us ' + \
                                           'form to request further assistance from the site admins.'
                return render(request, 'fieldswat/index.html')

            try:
                # Copy compressed data to the working directory
                with open(unique_path + '/input/' + filename, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
            except:
                request.session['error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                                           'persists please use the Contact Us form to request further assistance ' + \
                                           'from the site admins.'
                return render(request, 'fieldswat/index.html')

            # Uncompress the data
            try:
                unzip_command = 'unzip -qq ' + unique_path + '/input/' + \
                                fields_shapefile_foldername + ' -d ' + unique_path + '/input/'
                os.system(unzip_command)

                # Set permissions for unzipped data
                fix_file_permissions(unique_path + '/input/' + fields_shapefile_foldername)

                # Remove landuse zip
                os.remove(unique_path + '/input/' + filename)
            except:
                request.session['error'] = 'Could not unzip the folder. ' + \
                                           'Please contact administrator'
                return render(request, 'fieldswat/index.html')

            if not os.path.exists(unique_path + '/input/' + fields_shapefile_foldername):
                request.session['error'] = 'Could not extract the folder "' + \
                                           fields_shapefile_foldername + '". ' + \
                                           'Please check if the file is ' + \
                                           'compressed in zip format and ' + \
                                           'has the same name as ' + \
                                           'compressed folder.'
                return render(request, 'fieldswat/index.html')

            # directory path for the unzipped shapefile folder
            fields_shapefile_filepath = unique_path + '/input/' + fields_shapefile_foldername

            # loop through folder and grab any file ending with the .shp extension
            shapefiles = []
            for shapefile in glob.glob(fields_shapefile_filepath + '/*.shp'):
                shapefiles.append(shapefile)

            # too many .shp present
            if len(shapefiles) > 1:
                request.session['error'] = 'More than one shapefile found ' + \
                                           'in the zipped folder. Please ' + \
                                           're-upload with only one shapefile.'
                return render(request, 'fieldswat/index.html')
            # no .shp present
            elif len(shapefiles) < 1:
                request.session['error'] = 'No shapefiles found in the ' + \
                                           'zipped folder. Please ' + \
                                           're-upload with a single shapefile.'
                return render(request, 'fieldswat/index.html')
            # single .shp present
            else:
                fields_shapefile_filename = shapefiles[0]

            # Update relevant session variables
            request.session['fieldswat_fields_shapefile_filename'] = fields_shapefile_filename
            request.session['fieldswat_fields_shapefile_filepath'] = fields_shapefile_filepath
            request.session['progress_message'].append('Fields shapefile uploaded.')

            # Render the main page
            return render(request, 'fieldswat/index.html')
        else:
            request.session['error'] = 'Unable to receive the uploaded file, please try again. If the issue ' + \
                                       'persists please use the Contact Us form to request further assistance ' + \
                                       'from the site admins.'
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

    # if user is submitting a zipped SWAT Model
    if request.method == 'POST':
        try:
            # retrieve posted values
            output_type = request.POST.get('fieldswat_output')
            aggregation_method = request.POST.get('fieldswat_agg')
        except:
            request.session['error'] = 'Unable to find selected output and aggregation methods. ' + \
                                       'Please make sure you have selected an option for both of these ' + \
                                       'methods and then try again.'
            return render(request, 'fieldswat/index.html')

        # verify the value matches what we would expect
        if output_type != u'runoff' and output_type != u'sediment':
            request.session['error'] = 'Output type is not recognized. ' + \
                                       'Please make sure a radio button ' + \
                                       'is selected under Output.'
            return render(request, 'fieldswat/index.html')

        # verify the value matches what we would expect
        if aggregation_method != 'mean' and aggregation_method != 'mode' and \
                aggregation_method != 'geomean' and aggregation_method != 'area_weighted_mean':
            request.session['error'] = 'Aggregation method is not recognized. ' + \
                                       'Please make sure a radio button ' + \
                                       'is selected under Aggregation method.'
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
        'output_dir': settings.BASE_DIR + '/user_data/' + request.user.email + '/' + request.session['unique_directory_name'] + '/output',
        'results_dir': request.session.get('directory') + '/output',
        'hrus1_dir': request.session.get('fieldswat_swat_model_dir') + '/Watershed/Grid/hrus1',
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
        add_task_id_to_database(data['user_id'], data['user_email'], data['task_id'])

        request.session['progress_message'].append(
            'Job successfully added to queue. You will receive an email with ' + \
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
        time_completed=datetime.datetime.now(),
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
    for key in request.session.keys():
        if key not in keys_to_keep:
            del request.session[key]

    return HttpResponseRedirect(resolve_url('fieldswat'))


@login_required
def download_data(request):
    task_id = request.GET.get('id', '')
    if task_id != '':
        user_id = task_id.split('_')[1]
        if int(user_id) == int(request.user.id):
            if os.path.exists(settings.BASE_DIR + '/user_data/' + request.user.email + '/' + task_id + '/output'):
                file = io.BytesIO()

                dir_to_zip = settings.BASE_DIR + '/user_data/' + request.user.email + \
                             '/' + task_id + '/output'

                dir_to_zip_len = len(dir_to_zip.rstrip(os.sep)) + 1

                with zipfile.ZipFile(file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.external_attr = 0o0770
                    for dirname, subdirs, files in os.walk(dir_to_zip):
                        for filename in files:
                            path = os.path.join(dirname, filename)
                            entry = path[dir_to_zip_len:]
                            zf.write(path, entry)
                zf.close()

                response = HttpResponse(file.getvalue(), content_type="application/zip")
                response['Content-Disposition'] = 'attachment; filename=' + task_id + '.zip'
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
