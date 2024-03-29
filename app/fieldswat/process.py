import glob
import os
import shutil

from django.core.mail import send_mail
from django.utils import timezone
from matplotlib.path import Path
from osgeo import gdal, ogr
from scipy import stats
import numpy as np
import shapefile
import xlsxwriter

from common.utils import find_objectid_and_hru_id_indexes
from swatluu import geotools
from swatluu import swattools
from swatusers.models import UserTask


class FieldSWATProcess(object):

    def __init__(self, logger, data=""):

        # set initial paths for the input data
        if data == '':
            self.user_id = ''
            self.user_email = ''
            self.user_first_name = ''
            self.task_id = ''
            self.results_dir = ''
            self.output_dir = ''
            self.process_root_dir = ''
            self.hrus1_dir = ''
            self.fieldswat_swat_model_dir = ''
            self.fieldswat_fields_shapefile_filename = ''
            self.fieldswat_fields_shapefile_filepath = ''
            self.fieldswat_output_type = ''
            self.fieldswat_aggregation_method = ''
            self.swatoutput_years = ''
            self.swatoutput_runoff = ''
            self.swatoutput_sediment = ''
            self.fieldswat_selected_year = ''
        else:
            self.user_id = data['user_id']
            self.user_email = data['user_email']
            self.user_first_name = data['user_first_name']
            self.task_id = data['task_id']
            self.results_dir = data['results_dir']
            self.output_dir = data['output_dir']
            self.process_root_dir = data['process_root_dir']
            self.hrus1_dir = data['hrus1_dir']
            self.fieldswat_swat_model_dir = data['fieldswat_swat_model_dir']
            self.fieldswat_fields_shapefile_filename = data[
                'fieldswat_fields_shapefile_filename']
            self.fieldswat_fields_shapefile_filepath = data[
                'fieldswat_fields_shapefile_filepath']
            self.fieldswat_output_type = data['fieldswat_output_type']
            self.fieldswat_aggregation_method = data[
                'fieldswat_aggregation_method']
            self.swatoutput_years = data['swatoutput_years']
            self.swatoutput_runoff = data['swatoutput_runoff']
            self.swatoutput_sediment = data['swatoutput_sediment']
            self.fieldswat_selected_year = data['fieldswat_selected_year']

        self.hrus = ''
        self.dominant_hrus = ''
        self.hrus_info = ''
        self.tool_name = 'Field SWAT'
        self.logger = logger

    def setup_logger(self):
        self.logger.info('Task ID: ' + self.task_id)
        self.logger.info('User: ' + self.user_email)
        self.logger.info('Task started.')
        self.logger.info('Initializing variables.')

    def start(self):
        try:
            # start the logging
            self.setup_logger()
            self.logger.info('Processing started.')
        except Exception as e:
            self.logger.error(str(e))
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to initialize logger.')

        try:
            # create output directory structure
            self.create_output_dir()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error('Create output directory structures.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Create output directory structures.')

        # convert hrus1 grid to tif
        try:
            geotools.convert_adf_to_tif(
                self.output_dir + '/Raster/hrus1',
                self.output_dir + '/Raster/hrus1/hrus1.tif')
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error('Unable to convert raster from .adf to .tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to convert raster from .adf to .tif.')

        # copy hru1 and fields shapefiles to output directory
        try:
            self.copy_shapefile_to_output_directory()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while copying hru1 and fields shapefiles to output directory.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while copying hru1 and fields shapefiles to output directory.')

        # merge hru thresholds
        try:
            self.merge_thresholds()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while merging hru thresholds.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while merging hru thresholds.')

        try:
            # get hrus1 cols, rows, and resolution
            hrus1_info = self.get_tif_info()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while fetching the hrus1 raster details.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while fetching the hrus1 raster details.')

        try:
            grid_x_reshape, grid_y_reshape = self.set_gridx_and_gridy_matrices(
                hrus1_info)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while setting the gridx and gridy matrices.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while setting the gridx and gridy matrices.')

        try:
            clu = self.create_hru_field_workbook(
                grid_x_reshape, grid_y_reshape, hrus1_info['nodata'])
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while creating the hru field workbook.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while creating the hru field workbook.')

        try:
            field_shapefile, output_data, hru_output_data = self.update_field_info(
                hrus1_info['nodata'], clu)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while updating field info.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while updating field info.')

        try:
            self.create_new_field_shapefile(field_shapefile, output_data)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while creating the new shapefile.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while creating the new shapefile.')

        hru_shapefile = self.output_dir + '/Output/HRU_Response.shp'

        try:
            self.update_hru_shapefile(hru_shapefile, hru_output_data)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'An error occurred while updating the hru shapefile.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception(
                'An error occurred while updating the hru shapefile.')

    def create_output_dir(self):
        """
        Create output directory and its sub-folders. Remove any
        pre-existing output directory. Set up output directory.

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs
        """
        self.logger.info('Creating output directory structure.')
        # create temporary and output folders
        results_dir = self.output_dir
        if os.path.exists(results_dir):
            if os.path.exists(results_dir + '/Raster'):
                shutil.rmtree(results_dir + '/Raster')
            if os.path.exists(results_dir + '/Output'):
                shutil.rmtree(results_dir + '/Output')
            if os.path.exists(results_dir + '/Shape'):
                shutil.rmtree(results_dir + '/Shape')
            shutil.rmtree(results_dir)

        os.makedirs(results_dir, 0o775)
        os.makedirs(results_dir + '/Raster')
        os.makedirs(results_dir + '/Output')
        os.makedirs(results_dir + '/Shape')

        shutil.copytree(self.hrus1_dir, results_dir + '/Raster/hrus1')

        # copy hru1 shapefile to Output
        hru1_shapefile = []
        for hru1_shapefile_part in glob.glob(
                self.fieldswat_swat_model_dir + '/Watershed/Shapes/hru1*'):
            shutil.copy(hru1_shapefile_part,
                        results_dir + '/Output/HRU_Response' +
                        os.path.splitext(hru1_shapefile_part)[1])

    def merge_thresholds(self):
        """
        Merges non-dominant hrus into nearby dominant hrus. First it
        reads in the hrus1.tif and the hru1.shp and then finds the
        dominant hru values. The dominant hrus along with the original
        hrus raster are then used to complete the merge.

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs

        Returns
        -------
        hrus: array
            Array of the hrus array non-dominant hrus were merged with
            nearby dominant hrus

        dominant_hrus: array
            Array of the sorted dominant hrus

        hrus_info: tuple
            First value is the pixel size and the second the
            nodata value for the raster
        """
        self.logger.info('Reading hrus1.tif into numpy array.')

        hrus, hrus_info = geotools.read_raster(
            os.path.join(self.output_dir, 'Raster', 'hrus1', 'hrus1.tif'))

        self.logger.info('Reading hru1.shp into numpy array.')

        merged_hru = geotools.read_shapefile(
            os.path.join(self.fieldswat_swat_model_dir, 'Watershed', 'Shapes', 'hru1.shp'))
        merged_hru = np.array(merged_hru, dtype=int)
        # sort HRU_ID column (second column) into ascending order
        # and keep respective positions of other columns
        # for example:
        # dominant_hrus = [50, 30, 25, 70, 10]
        # new_hrus = [3, 2, 5, 1, 4]
        # old_hrus = [70, 30, 50, 10, 25]
        hru1_field_positions = find_objectid_and_hru_id_indexes(
            os.path.join(self.fieldswat_swat_model_dir, 'Watershed', 'Shapes', 'hru1.shp'))

        if not hru1_field_positions:
            Exception('Unable to find OBJECTID and HRU_ID in hru1.shp.')

        sorted_hru = merged_hru[merged_hru[:,
                                           hru1_field_positions['hru_id']].argsort()]

        self.logger.info(
            'Sorting and merging the non-dominant and dominant hrus.')
        # retrieve dominant hru values - these are the hrus that remained
        # after the threshold was applied (OBJECTID in hru1.shp)
        dominant_hrus = sorted_hru[:, 0]

        # merge non-dominant hrus into nearby dominant hrus
        hrus = swattools.merge(hrus, dominant_hrus, hrus_info[1])

        self.hrus = hrus
        self.dominant_hrus = dominant_hrus
        self.hrus_info = hrus_info

    def copy_shapefile_to_output_directory(self):
        """
        Copies the hru1 and fields shapefiles (all components of it) to the output
        directory. It also makes two new copies of hru1.prj and renames
        the copies to Field_Response.prj and HRU_Response.prj.
        """
        # copy hru1 shapefile to output directory
        hru1_dir = self.fieldswat_swat_model_dir + '/Watershed/Shapes/'
        for shapefile_part in glob.glob(hru1_dir + '/hru1.*'):
            shutil.copyfile(shapefile_part,
                            self.output_dir + '/Shape/' + os.path.basename(
                                shapefile_part))

        # copy the fields shapefile to output directory
        for shapefile_part in glob.glob(
                self.fieldswat_fields_shapefile_filename[:-4] + '*'):
            shutil.copyfile(shapefile_part,
                            self.output_dir + '/Shape/' + os.path.basename(
                                shapefile_part))

        # copy the projection file with a new name twice
        shutil.copyfile(hru1_dir + '/hru1.prj',
                        self.output_dir + '/Output/Field_Response.prj')
        shutil.copyfile(hru1_dir + '/hru1.prj',
                        self.output_dir + '/Output/HRU_Response.prj')

    def get_tif_info(self):
        """
        Fetches the rows, cols, and pixel scale information
        for the hru1 raster.
        """
        # open the tif raster with gdal
        hru1_file = gdal.Open(self.output_dir + '/Raster/hrus1/hrus1.tif')

        # get number of columns and rows for the raster
        cols = hru1_file.RasterXSize
        rows = hru1_file.RasterYSize

        # get the geo transform for hru1 (contains pixel res and origin)
        geo_transform = hru1_file.GetGeoTransform()

        # get nodata value for raster
        band = hru1_file.GetRasterBand(1)
        nodata = band.GetNoDataValue()

        # compact info into dictionary
        hrus1_info = {
            'rows': rows,
            'cols': cols,
            'pixel_resolution': geo_transform[1],
            'origin': [geo_transform[0], geo_transform[3]],
            'nodata': nodata,
        }

        return hrus1_info

    def set_gridx_and_gridy_matrices(self, hrus1_info):
        self.logger.info('Setting up grid matrices.')
        # set delta x and y to the pixel resolution
        delta_x = int(hrus1_info['pixel_resolution'])
        delta_y = int(hrus1_info['pixel_resolution'])

        # get origin for hrus1 raster file
        x_origin = float(hrus1_info['origin'][0])
        y_origin = float(hrus1_info['origin'][1])

        self.logger.info('Building grid_x.')
        # build x grid
        grid_x = np.zeros(
            (hrus1_info['rows'], hrus1_info['cols']), dtype=float)
        grid_x[0:hrus1_info['rows'], 0] = x_origin + (delta_x / 2)
        for i in range(1, hrus1_info['cols']):
            grid_x[0:hrus1_info['rows'], i] = grid_x[0:hrus1_info['rows'],
                                                     i - 1] + delta_x

        self.logger.info('Building grid_y.')
        # build y grid
        grid_y = np.zeros(
            (hrus1_info['rows'], hrus1_info['cols']), dtype=float)
        grid_y[0, 0:hrus1_info['cols']] = y_origin - (delta_y / 2)
        for i in range(1, hrus1_info['rows']):
            grid_y[i, 0:hrus1_info['cols']] = grid_y[i - 1,
                                                     :hrus1_info['cols']] - delta_y

        self.logger.info('Reshaping grid_x and grid_y.')
        # reshape the coordinates grid_x and grid_y to temporary column matrix
        grid_x_reshape = np.reshape(np.transpose(grid_x),
                                    hrus1_info['rows'] * hrus1_info['cols'])
        grid_y_reshape = np.reshape(np.transpose(grid_y),
                                    hrus1_info['rows'] * hrus1_info['cols'])

        return grid_x_reshape, grid_y_reshape

    def create_hru_field_workbook(self, grid_x_reshape, grid_y_reshape, nodata):
        self.logger.info('Creating HRU_FIELD.xlsx workbook.')

        # initialize a layer to store field ids in the next for loop
        clu = np.zeros(len(grid_x_reshape), dtype=int)

        # export HRU identified under each CLU in a separate excel file
        hru_id = np.reshape(np.transpose(self.hrus),
                            len(self.hrus) * len(self.hrus[0]))

        # open excel workbook and add new sheet titled HRU_Field
        workbook = xlsxwriter.Workbook(
            self.output_dir + '/Output/HRU_FIELD.xlsx')
        sheet = workbook.add_worksheet('HRU_Field')

        self.logger.info(
            'Adding field shapefile data to the HRU_FIELD.xlsx workbook.')

        # open field shapefile
        field_shapefile = shapefile.Reader(
            self.fieldswat_fields_shapefile_filename)

        # merge grid_x_reshape and grid_y_reshape into single list of tuples
        grid_xy_reshape = []
        for i in range(0, len(grid_x_reshape)):
            grid_xy_reshape.append((grid_x_reshape[i], grid_y_reshape[i]))

        # iterate through the field shapefile records (i.e. fields)
        sheet.write(0, 0, 'Field')
        sheet.write(0, 1, 'HRUs')
        for i in range(0, len(field_shapefile.shapes())):
            # ultimately collect hru ids that are in the current field poly
            in_list = np.zeros(len(grid_x_reshape), dtype=int)

            # construct polygon for current record
            mpoly = Path(field_shapefile.shapes()[i].points)

            # matplotlib_pip returns a boolean list - True means in the poly
            mpoly_results = geotools.matplotlib_pip(grid_xy_reshape, mpoly)

            # find index position for coordinates identified as being in the poly
            hrus_in_poly = np.where(np.array(mpoly_results) == True)

            # set any index for a coordinate found in the poly to 1
            in_list[hrus_in_poly] = 1

            # update clu with field id
            clu[np.nonzero(in_list == 1)] = i + 1

            # get unique, sorted list of hrus found in the field
            unique_hrus = list(set(hru_id[np.nonzero(in_list == 1)]))
            unique_hrus.sort()

            # remove the nodata value from the list of hrus
            try:
                unique_hrus.remove(nodata)
            except ValueError as e:
                self.logger.warning(str(e))

            # write to the spreadsheet
            sheet.write(i + 1, 0, i + 1)
            sheet.write_row(i + 1, 1, unique_hrus)  # row, col, data

        workbook.close()
        self.logger.info('Closing HRU_FIELD.xlsx workbook.')

        return clu

    def update_field_info(self, hrus1_nodata, clu):
        field_shapefile = shapefile.Reader(
            self.fieldswat_fields_shapefile_filename)

        years = np.array(self.swatoutput_years)
        runoff = np.array(self.swatoutput_runoff)
        sediment = np.array(self.swatoutput_sediment)

        # check which output type was selected by the user
        if self.fieldswat_output_type == 'runoff':
            data = runoff
        else:
            data = sediment

        # take the first year
        year = self.fieldswat_selected_year

        # find index positions in years where the first year is located
        year_index_position = np.nonzero(years == year)

        # collect data for that year
        data_for_year = data[year_index_position]

        hru_id = np.reshape(np.transpose(self.hrus), self.hrus.size)

        # Create dictionary lookup for data values {hru_id: data_value}
        # Exclude last unique hru which is the nodata value
        output_data = {}
        for idx, hru_num in enumerate(np.unique(hru_id)):
            if hru_num != hrus1_nodata:
                output_data[hru_num] = data[idx]
            else:
                output_data[hru_num] = np.nan

        # Create flat water array with appropriate runoff or sediment values
        water = np.zeros(self.hrus.size, dtype=float)
        for i in range(0, len(water)):
            water[i] = output_data[hru_id[i]]

        # Reshape grids to match hrus grid
        hru_two = np.reshape(clu, self.hrus.shape)
        hru_three = np.reshape(water, self.hrus.shape)

        # Flatten reshaped grids
        cl = np.reshape(np.transpose(hru_two), hru_two.size)
        wt = np.reshape(np.transpose(hru_three), hru_three.size)

        # Stores calculated field outputs
        field_output = np.zeros(len(field_shapefile.shapes()), dtype=float)

        if self.fieldswat_aggregation_method == 'mean':

            for i in range(0, len(field_shapefile.shapes())):
                field_output[i] = np.nanmean((wt[np.nonzero(cl == i + 1)]))

                if np.isnan(field_output[i]):
                    field_output[i] = 0

        elif self.fieldswat_aggregation_method == 'mode':

            for i in range(0, len(field_shapefile.shapes())):

                resp = wt[np.nonzero(cl == i + 1)]
                resp[np.nonzero(resp == 0)] = np.NaN
                temp = np.ma.masked_array(resp, np.isnan(resp))
                try:
                    field_output[i] = stats.mode(temp).mode[0]
                except AttributeError:
                    field_output[i] = np.nan

                if np.isnan(field_output[i]):
                    field_output[i] = 0

        elif self.fieldswat_aggregation_method == 'geomean':

            for i in range(0, len(field_shapefile.shapes())):

                index = np.nonzero(cl == i + 1)
                resp = wt[index]
                resp[np.nonzero(resp == 0)] = np.NaN
                temp = np.ma.masked_array(resp, np.isnan(resp))
                field_output[i] = stats.gmean(temp)

                if np.isnan(field_output[i]):
                    field_output[i] = 0

        elif self.fieldswat_aggregation_method == 'area_weighted_mean':

            for i in range(0, len(field_shapefile.shapes())):

                resp = wt[np.nonzero(cl == i + 1)]
                field_output[i] = np.nanmean(resp)

                if np.isnan(field_output[i]):
                    field_output[i] = 0

        return field_shapefile, field_output, data_for_year

    def create_new_field_shapefile(self, field_shapefile, output_data):

        # set up the shapefile driver
        driver = ogr.GetDriverByName('ESRI Shapefile')

        # create the data source
        data_source = driver.CreateDataSource(self.output_dir + '/Output')

        # create the layer
        layer = data_source.CreateLayer('Field_Response', None, ogr.wkbPolygon)

        # add fields
        layer.CreateField(ogr.FieldDefn('Shape_Area', ogr.OFTReal))
        layer.CreateField(
            ogr.FieldDefn(str(self.fieldswat_output_type), ogr.OFTReal))

        for i in range(0, len(field_shapefile.shapes())):

            # get the field's shape (coordinates)
            field_shape = field_shapefile.shapes()[i]

            # get the field's shape area (float)
            field_record = field_shapefile.records()[i][0]

            # create feature
            feature = ogr.Feature(layer.GetLayerDefn())

            # set the attributes
            feature.SetField('Shape_Area', field_record)
            feature.SetField(str(self.fieldswat_output_type), output_data[i])

            # create polygon ring
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for point in field_shape.points:
                ring.AddPoint(point[0], point[1])

            # create polygon
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)

            # set the feature geometry using the wkbpolygon
            feature.SetGeometry(poly)

            # create the feature in the layer
            layer.CreateFeature(feature)

            # free up resources
            feature.Destroy()

        # free up resources
        data_source.Destroy()

    def update_hru_shapefile(self, inshape, new_data):
        # open hru1.shp
        src = ogr.Open(inshape, 1)

        # get the hru1 layer
        lyr = src.GetLayer()

        # create new field we wish to append (Runoff or Sediment)
        lyr.CreateField(
            ogr.FieldDefn(str(self.fieldswat_output_type).title(), ogr.OFTReal))

        feature = lyr.GetNextFeature()

        for i in range(0, len(new_data)):
            feature.SetField(str(self.fieldswat_output_type), new_data[i])
            lyr.SetFeature(feature)
            feature = lyr.GetNextFeature()

    def copy_results_to_depot(self):
        """
        Copies output from process over to web directory for user's consumption.
        """
        self.logger.info(
            'Copying output directory to user directory on depot.')

        # If results directory already exists in web directory, remove it
        if os.path.exists(self.results_dir):
            shutil.rmtree(self.results_dir)

        # Copy output over to web directory
        shutil.copytree(self.output_dir, self.results_dir)

    def clean_up_input_data(self):
        """ Removes input data from tmp directory. """
        self.logger.info('Removing input files from tmp.')
        try:
            shutil.rmtree(self.process_root_dir)
        except PermissionError as e:
            self.logger.warning(str(e))
            self.logger.warning("Unable to remove the input data from /tmp.")

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
        message += ' (48 hours).<br /><br />'
        message += 'We would love to hear from you. Please take this '
        message += '<a title="Survey link" href="https://purdue.ca1.qualtrics.com/jfe/form/SV_9Zk54sQJ13GvnUO" target="_blank" rel="noopener noreferrer">brief survey</a> '
        message += 'to let us know how you use SWAT Tools.'
        message += '<br /><br />Sincerely,<br />SWAT Tools'
        try:
            send_mail(
                subject,
                "",
                'SWAT Tools User',
                [self.user_email],
                fail_silently=False,
                html_message=message)
        except Exception as e:
            self.logger.error(str(e))
            self.logger.error(
                'Error sending the user the email to their data.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Error sending the user the email to their data.')

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
        message = 'An error has occurred within ' + \
            self.tool_name + ' while processing your data. '
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
