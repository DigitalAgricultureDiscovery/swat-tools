from django.core.mail import send_mail
from django.utils import timezone
from swatusers.models import UserTask
from subprocess import check_call
from swatluu import geotools

import numpy as np
import os
import shutil


class LUUCheckerProcess(object):
    def __init__(self, logger, data=""):
        """
        A LUU Checker process requested by a user. It contains the core
        variables and methods for creating the new composite landuse layer.
        """

        # set initial paths for the input data
        if data == '':
            self.subbasin_shapefile_filepath = ''
            self.subbasin_shapefile_filename = ''
            self.base_landuse_raster_filepath = ''
            self.base_landuse_raster_adf_filepath = ''
            self.base_landuse_raster_filename = ''
            self.new_landuse_raster_filepaths = ''
            self.new_landuse_raster_filenames = ''
            self.landuse_percent = ''
            self.process_root_dir = ''
            self.output_dir = ''
            self.output_directory = ''
            self.temp_output_directory = ''
            self.task_id = ''
            self.user_email = ''
            self.user_first_name = ''
            self.error_log = ''
            self.subbasin_count = ''
            self.base_raster_array = ''
            self.base_raster_mask = ''
            self.status = [0, 'Everything checks out.']
            self.new_landuse_layer = ''
        else:
            self.subbasin_shapefile_filepath = data[
                'subbasin_shapefile_filepath']
            self.subbasin_shapefile_filename = data[
                'subbasin_shapefile_filename']
            self.base_landuse_raster_filepath = data[
                'base_landuse_raster_filepath']
            self.base_landuse_raster_adf_filepath = data[
                'base_landuse_raster_adf_filepath']
            self.base_landuse_raster_filename = data[
                'base_landuse_raster_filename']
            self.new_landuse_raster_filepaths = data[
                'new_landuse_raster_filepaths']
            self.new_landuse_raster_filenames = data[
                'new_landuse_raster_filenames']
            self.landuse_percent = data['landuse_percent']
            self.process_root_dir = data['process_root_dir']
            self.output_dir = data['output_dir']
            self.output_directory = data['output_directory']
            self.temp_output_directory = data['temp_output_directory']
            self.task_id = data['task_id']
            self.user_email = data['user_email']
            self.user_first_name = data['user_first_name']
            self.error_log = []
            self.subbasin_count = ''
            self.base_raster_array = []
            self.base_raster_mask = []
            self.status = [0, 'Everything checks out.']
            self.new_landuse_layer = ''

        self.tool_name = 'LUU Checker'
        self.logger = logger

    def start(self):
        """
        Directs the work flow of the LUU Checker task. Essentially these steps
        are taken:
        1) Create output and temporary output directory structure
        2) Convert base landuse raster to geotiff
        3) Read base landuse raster into numpy array
        4) Convert subbasin shapefile into geotiff
        5) Create Emerging LULC (EL) Report
        6) Loop through each new landuse raster
            L1a) Update EL Report with new entry for current new landuse raster
            L1b) Convert new landuse raster to geotiff
            L1c) Read new landuse raster into numpy array
            L1d) Loop through each subbasin
                L2a) Compare (for current subbasin) lulc codes in base landuse
                     raster and new landuse raster
                L2b) Isolate lulc codes that are emerging in new landuse raster
                L2c) Update EL Report with emerging lulc codes
                L2d) Loop through each emerging lulc code
                    L3a) Randomize the indicies in a copy of the base landuse
                         raster that correspond with the current subbasin
                    L3b) Calculate how many pixels should be reclassified to
                         the new lulc code by using the subbasin size and the
                         user provided percentage value
                    L3c) Use the randomized indicies to inject the new lulc
                         into the base landuse raster
        7) Create composite landuse raster using the updated base landuse raster
        8) Close the EL Report
        9) Remove temporary output directory

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        try:
            self.setup_logger()
            self.logger.info('Processing started.')
            # create output directory structure
            self.create_output_dir()
        except Exception as e:
            print(e)
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to initialize logger.')

        # convert base landuse raster from .adf to .tif
        try:
            output_filepath = self.temp_output_directory + '/' + os.path.basename(
                self.base_landuse_raster_filepath) + '.tif'
            geotools.convert_adf_to_tif(
                self.base_landuse_raster_filepath,
                output_filepath)
        except Exception:
            self.logger.error('Unable to convert raster from .adf to .tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to convert raster from .adf to .tif.')

        self.logger.info('Converting base raster geotiff into numpy array.')

        try:
            # read base landuse raster (.tif) into numpy array
            base_raster_array = geotools.read_raster(
                self.temp_output_directory + '/' + \
                self.base_landuse_raster_filename + '.tif')[0]

            # construct shapefile layer information
            rows = str(len(base_raster_array))
            cols = str(len(base_raster_array[0]))
            layer_info = {
                "attribute_name": "Subbasin",
                "extent": [cols, rows],
                "layername": "subs1",
            }
        except Exception:
            self.logger.error('Unable to read the base landuse raster.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to read the base landuse raster.')

        self.logger.info(
            'Getting count of subbasins from the subbasin shapefile.')

        try:
            # get number of subbasins in shapefile
            total_subbasin_count = len(
                geotools.read_shapefile(self.subbasin_shapefile_filepath))
        except Exception:
            self.logger.error('Unable to read the subbasin shapefile.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to read the subbasin shapefile.')

        # path and filename for the soon to be created subbasin geotiff
        output_tif_filepath = self.temp_output_directory + '/subbasin.tif'

        # create geotiff raster of the subbasin shapefile
        self.logger.info('Converting subbasin .shp to .tif.')
        try:
            # convert shapefile to raster
            geotools.rasterize_shapefile(layer_info,
                                         self.subbasin_shapefile_filepath,
                                         output_tif_filepath)
        except Exception:
            self.logger.error(
                'Error converting shapefile to raster. Please make ' + \
                'sure you uploaded file.shp.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'Error converting shapefile to raster. Please make ' + \
                'sure you uploaded file.shp.')

        self.logger.info('Converting subbasin geotiff into numpy array.')

        try:
            # read rasterized shapefile into numpy array
            rasterized_shapefile = \
            geotools.read_raster(self.temp_output_directory + '/subbasin.tif')[
                0]
        except Exception:
            self.logger.error(
                'Unable to read the rasterized subbasin geotiff.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to read the rasterized subbasin geotiff.')

        self.logger.info('Opening Emerging_LULC_Report for writing.')

        try:
            # remove emerging lulcs report if it already exists
            if os.path.isfile(self.output_directory + '/Emerging_LULCs.txt'):
                os.remove(self.output_directory + '/Emerging_LULCs.txt')
            # create emerging_lulcs text file to store new landuse information
            emerging_lulc_report = open(
                self.output_directory + '/Emerging_LULC_Report.txt', 'w')
        except Exception:
            self.logger.error(
                'Unable to create emerging_lulcs text file to store new landuse information.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'Unable to create emerging_lulcs text file to store new landuse information.')

        self.logger.info('Begin looping through new landuse layers.\n\n')

        try:
            # loop through each new landuse layer selected by the user
            for landuse_layer in self.new_landuse_raster_filepaths:
                self.logger.info(
                    'LANDUSE LAYER:' + os.path.basename(landuse_layer))
                # write the landuse layer name to report
                emerging_lulc_report.write(landuse_layer + '\n')

                # convert the new landuse layer raster to array
                geotools.convert_adf_to_tif(landuse_layer,
                                            self.temp_output_directory + '/' + os.path.basename(
                                                landuse_layer) + '.tif')
                self.logger.info(
                    'Converting new landuse geotiff into numpy array.')
                self.logger.info(
                    self.temp_output_directory + '/' + os.path.basename(
                        landuse_layer) + '.tif')
                # read new landuse raster (.tif) into numpy array
                new_landuse_raster = geotools.read_raster(
                    self.temp_output_directory + '/' + \
                    os.path.basename(landuse_layer) + '.tif')[0]
                self.logger.info('Begin looping through subbasins.')
                # create feature layers based off the FID field & then use as mask
                # to extract subbasin landuse information
                for i in range(0, total_subbasin_count):
                    self.logger.info('SUBBASIN #' + str(i + 1) + ':')

                    # write the subbasin number to report
                    emerging_lulc_report.write('Subbasin ' + str(i + 1) + '\n')

                    self.logger.info('Finding indicies in base raster array ' +
                                     'that correspond with current subbasin.')
                    # find indicies where the value < 255 (remove the NoData)
                    idx = np.nonzero(rasterized_shapefile == i + 1)

                    # find lulc codes in the new layer that aren't in the base layer
                    new_lulc_codes = self.find_unique_lulc_codes(
                        idx,
                        base_raster_array,
                        new_landuse_raster)

                    # write the emerging lulc to report
                    emerging_lulc_report.write(str(new_lulc_codes) + '\n\n')

                    # inject new lulc codes into the base raster array
                    base_raster_array = self.inject_new_lulc_codes(
                        idx,
                        new_lulc_codes,
                        base_raster_array)

                self.logger.info('End looping through subbasins.')
        except:
            self.logger.error(
                'An error occurred while creating the emerging lulc report.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while creating the emerging lulc report.')

        self.logger.info('End looping through new landuse layers.\n\n')

        try:
            # convert the updated base raster array (composite) to geotiff
            self.create_composite_raster(
                base_raster_array,
                self.base_landuse_raster_adf_filepath,
                self.temp_output_directory + '/base_new1.tif')
        except:
            self.logger.error(
                'An error occurred while creating the composite raster.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while creating the composite raster.')

        self.logger.info('Closing Emerging_LULC_Report for writing.')
        # close emerging lulc report
        emerging_lulc_report.close()

        self.logger.info('Removing temporary output directories.')
        # remove temporary output directory
        if os.path.exists(self.temp_output_directory):
            shutil.rmtree(self.temp_output_directory)

        self.logger.info('Processing completed.\n\n')

    def setup_logger(self):
        # Initialize logger for requested process and set header

        self.logger.info('Task ID: ' + self.task_id)
        self.logger.info('User: ' + self.user_email)
        self.logger.info('Task started.')
        self.logger.info('Initializing variables.')

    def create_output_dir(self):
        """
        Create output directory and its sub-folders. Remove any
        pre-existing output directory. Set up output directory.
        """
        self.logger.info('Creating output directory structure.')
        # create temporary and output folders
        if os.path.exists(self.output_directory):
            shutil.rmtree(self.output_directory)
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

        if os.path.exists(self.temp_output_directory):
            shutil.rmtree(self.temp_output_directory)
        if not os.path.exists(self.temp_output_directory):
            os.makedirs(self.temp_output_directory)

    def find_unique_lulc_codes(self, idx, base_raster_array,
                               new_landuse_raster):
        """
        Finds the unique landuse/landcover values in the base landuse raster
        array and the new landuse raster array. Then it identifies any
        landuse/landcover values present in the new landuse raster array that
        are not in the base landuse raster array.

        Parameters
        ----------
        idx: tuple
            Contains row and column indicies for the subbasin

        base_raster_array: array
            Base landuse raster as numpy array

        new_landuse_raster: array
            New landuse raster as numpy array

        Returns
        -------
        new_lulc_codes: array
            Single dimensional array containing landuse/landcover values
            completely unique to the new landuse raster array
        """
        self.logger.info(
            'Finding the landuse/landcover values unique to the new landuse raster.')

        # parse the idx to separate variables
        row, col = idx
        # find unique LULC in base landuse array
        base_raster_lulc_codes = np.unique(base_raster_array[row, col])
        # find unique LULC in new landuse array
        new_raster_lulc_codes = np.unique(new_landuse_raster[row, col])
        # now compare new landuse raster's lulc codes with base raster's lulc codes
        new_lulc_codes = np.setdiff1d(new_raster_lulc_codes,
                                      base_raster_lulc_codes)

        return new_lulc_codes

    def inject_new_lulc_codes(self, idx, new_lulc_codes, base_raster_array):
        """
        Takes the lulc codes that emerged in the new landuse raster and then
        injects instances of each code into the base landuse raster. The
        number of pixels to be reclassified to the new lulc codes is determined
        by the size of the subbasin and the percentage value chosen by the user.

        Parameters
        ----------
        idx: tuple
            Contains row and column indicies for the subbasin

        new_lulc_codes: array
            Single dimensional array containing landuse/landcover values
            completely unique (emerging) to the new landuse raster array

        base_raster_array: array
            Original base landuse raster as numpy array

        Returns
        -------
        base_raster_array: array
            Base landuse raster updated with emerging lulcs
        """
        self.logger.info(
            'Injecting emerging lulc codes into base raster array.')
        # if newLULC > 0, this implies landuses are present in the new LULC
        if np.size(new_lulc_codes, axis=0) > 0:
            # this implies that an alternative LULC is required containing few cells with additional landuses
            base_raster_array_temp = base_raster_array
            row, col = idx
            # this makes sure we don't overwrite one of our landuses in the base raster array
            # it checks if the number of unique lulc codes in the updated base raster array
            # matches the sum of the original base raster array plus new_lulc_codes
            # if they don't match, that means we erased a landuse so we reshuffle and try again
            # while len(valBase) + len(new_lulc_codes) != len(np.unique(base_raster_array[row, col])):
            index_array = list(range(0, np.shape(idx)[1]))
            np.random.shuffle(index_array)
            previous_new_lulc_ending_index = 0
            for j in range(0, len(new_lulc_codes)):
                number_of_new_lulc_cells = int(round(
                    (float(self.landuse_percent) / 100.0) * np.shape(idx)[1]))
                newLULC_idx = index_array[
                              previous_new_lulc_ending_index:number_of_new_lulc_cells + previous_new_lulc_ending_index]
                previous_new_lulc_ending_index = previous_new_lulc_ending_index + number_of_new_lulc_cells
                base_raster_array[row[newLULC_idx], col[newLULC_idx]] = \
                new_lulc_codes[j]

        return base_raster_array

    def create_composite_raster(self, base_raster_array,
                                base_landuse_raster_adf_filepath,
                                composite_raster_filepath):
        self.logger.info('Creating composite landuse raster.')

        geotools.create_raster(base_raster_array,
                               base_landuse_raster_adf_filepath,
                               composite_raster_filepath)
        try:
            check_call(
                ['gdal_translate', '-co', 'compress=lzw', '-a_nodata', '255',
                 '-of', 'GTiff',
                 self.temp_output_directory + '/base_new1.tif',
                 self.output_directory + '/base_new.tif'])
        except Exception:
            self.logger.error(
                'Error converting new base raster to geotiff.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

    def copy_results_to_depot(self):
        """
        Copies output from process over to web directory for user's consumption.
        """
        self.logger.info('Copying output directory to user directory on depot.')

        # If output directory already exists in web directory, remove it
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

        # Copy output over to web directory
        shutil.copytree(self.output_directory, self.output_dir)

    def clean_up_input_data(self):
        """ Removes input data from tmp directory. """
        self.logger.info('Removing input files from tmp.')
        shutil.rmtree(self.process_root_dir)

    def email_user_link_to_results(self):
        """
        Emails the user a link to their data that just finished processing. The
        user is informed their data will expire at midnight three days from the
        present date.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.logger.info('Sending user email with link to their data.')
        subject = self.tool_name + ' data is ready'
        message = 'Hi ' + self.user_first_name + ',<br><br>'
        message += 'Your data has finished processing. Please sign in to '
        message += 'the SWAT Tools website and go to the '
        message += '<strong>Task Status</strong> page (found in the navigation menu). '
        message += 'There you will find a record of your completed '
        message += 'task and a link to download the results data. '
        message += 'The link will expire on ' + self.get_expiration_date()
        message += ' (48 hours).<br><br>Sincerely,<br>SWAT Tools'
        try:
            send_mail(
                subject,
                "",
                'SWAT Tools User',
                [self.user_email],
                fail_silently=False,
                html_message=message)
        except Exception:
            self.logger.error('Unable to convert raster from .adf to .tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to convert raster from .adf to .tif.')

    def email_error_alert_to_user(self):
        """
            Emails the user when an error occurs that prevents their data from
            being processed.
            Parameters
            ----------
            None

            Returns
            -------
            None
            """
        self.logger.info(
            'Sending user email informing them an error has occurred.')
        subject = self.tool_name + ' error'
        message = 'An error has occurred within ' + self.tool_name + ' while processing your data. '
        message += 'Please verify your inputs are not missing any required files. '
        message += 'If the problem persists, please sign in to SWAT Tools and use '
        message += 'the Contact Us form to request assistance from the SWAT Tools '
        message += 'Admins.'
        message += '<br><br>Sincerely,<br>SWAT Tools'
        try:
            send_mail(
                subject,
                "",
                'SWAT Tools User',
                [self.user_email],
                fail_silently=False,
                html_message=message)
        except Exception:
            self.logger.error(
                'Error sending the user the email informing ' +
                'them of an error occurrence while processing their data.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            raise Exception('Error sending the user the email informing ' +
                            'them of an error occurrence while processing their data.')

    def get_expiration_date(self):
        """
        Uses Python's datetime to calculate expiration date for processed data.

        Parameters
        ----------
        None

        Returns
        -------
        date_string: string
            Date (mm-dd-YYYY) three days from the present in string format.
        """
        self.logger.info('Calculating the date three days from now.')
        return (
            timezone.datetime.now() + timezone.timedelta(hours=48)).strftime(
            "%m-%d-%Y %H:%M:%S %Z")

    def update_task_status_in_database(self):
        """
        Adds current task to the database. Helps with removal of task's data
        after it expires (3 days from completion date).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.logger.info('Updating the user\'s task status.')
        UserTask.objects.filter(
            task_id=self.task_id).update(
            task_status=1,
            time_completed=timezone.datetime.now())
