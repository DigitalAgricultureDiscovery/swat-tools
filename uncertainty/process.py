from swatluu import geotools
from swatluu import swattools
from django.conf import settings
from django.core.mail import send_mail
from datetime import date, timedelta
from swatusers.models import UserTask

import csv
import datetime
import logging
import numpy as np
import os
import shutil


class UncertaintyProcess(object):

    def __init__(self, data=''):

        if data == '':
            self.results_dir = ''
            self.process_root_dir = ''
            self.output_dir = ''
            self.swat_dir = ''
            self.hrus1_dir = ''
            self.landuse_dir = ''
            self.lookup_filepath = ''
            self.landuse_year = ''
            self.landuse_month = ''
            self.landuse_day = ''
            self.landuse_layer_name = ''
            self.uncertainty_error_data = ''
            self.task_id = ''
            self.user_email = ''
            self.user_first_name = ''
        else:
            self.results_dir = data['results_dir']
            self.process_root_dir = data['process_root_dir']
            self.output_dir = data['output_dir']
            self.swat_dir = data['swat_dir']
            self.hrus1_dir = data['hrus1_dir']
            self.landuse_dir = data['landuse_dir']
            self.lookup_filepath = data['lookup_filepath']
            self.landuse_year = data['landuse_year']
            self.landuse_month = data['landuse_month']
            self.landuse_day = data['landuse_day']
            self.landuse_layer_name = data['landuse_layer_name']
            self.uncertainty_error_data = data['uncertainty_error_data']
            self.task_id = data['task_id']
            self.user_email = data['user_email']
            self.user_first_name = data['user_first_name']

        self.dominant_hrus = ''
        self.hru_indexes = ''
        self.old_hru_areas = ''
        self.unique_subbasin_ids = ''
        self.tool_name = 'LUU Uncertainty'

    def start(self):
        """
        """
        try:
            self.setup_logger()
            self.logger.info('Processing started.')
        except Exception:
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to initialize logger.')

        # create output directory structure
        try:
            self.create_output_dir()
        except Exception:
            self.logger.exception('Create output directory structures.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Create output directory structures.')

        # convert hrus1 grid to tif
        try:
            geotools.convert_adf_to_tif(
                self.results_dir + '/Raster/hrus1',
                self.results_dir + '/Raster/hrus1/hrus1.tif')
        except Exception:
            self.logger.exception('Unable to convert raster from .adf to .tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('Unable to convert raster from .adf to .tif.')

        try:
            self.create_lupdat_file()
        except Exception:
            self.logger.exception('An error occurred while creating the lup dat files.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while creating the lup dat files.')

        try:
            self.extract_lookup_info()
        except Exception:
            self.logger.exception('An error occurred while extracting lookup info.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while extracting lookup info.')

        try:
            self.merge_thresholds()
        except Exception:
            self.logger.exception('An error occurred while merging thresholds.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while merging thresholds.')

        try:
            self.create_fractional_values()
        except Exception:
            self.logger.exception('An error occurred while creating fractional values.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while creating fractional values.')

        try:
            self.extract_hru_files_data()
        except Exception:
            self.logger.exception('An error occurred while extracting hru files data.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while extracting hru files data.')

        try:
            self.apply_realization()
        except Exception:
            self.logger.exception('An error occurred while applying realization.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)
            self.email_error_alert_to_user()
            raise Exception('An error occurred while applying realization.')

    def setup_logger(self):
        # Initialize logger for requested process and set header
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(settings.BASE_DIR + '/swatapps/log/tasks/uncertainty/' + self.task_id + '.log')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info('Task ID: ' + self.task_id)
        self.logger.info('User: ' + self.user_email)
        self.logger.info('Task started.')
        self.logger.info('Initializing variables.')

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
        results_dir = self.results_dir
        if os.path.exists(results_dir):
            if os.path.exists(results_dir + '/Raster'):
                shutil.rmtree(results_dir + '/Raster')
            if os.path.exists(results_dir + '/Output'):
                shutil.rmtree(results_dir + '/Output')
            if os.path.exists(results_dir + '/Shape'):
                shutil.rmtree(results_dir + '/Shape')
            shutil.rmtree(results_dir)

        os.makedirs(results_dir + '/Raster')
        os.makedirs(results_dir + '/Output')
        os.makedirs(results_dir + '/Shape')

        # Needs extra group permissions to copy post_processing files over
        os.chmod(results_dir + '/Output', 0o775)
        
        shutil.copytree(self.hrus1_dir, results_dir + '/Raster/hrus1')

    def create_lupdat_file(self):
        """
        Creates the lup.dat file. The lup.dat file must be written
        in the following format:
            id    month   day     year    file.dat

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs   

        Examples
        --------
        1   1   1   1992    file1.dat
        2   1   1   1999    file2.dat
        3   1   1   2001    file3.dat

        Returns
        -------
        None
        """
        self.logger.info('Creating lup.dat file.')
        try:
            lup_file = open(self.results_dir + '/Output/lup.dat', 'a')
        except IOError:
            self.logger.exception('Unable to open the lup.dat file.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        self.logger.info('Extracting information about landuse layers\' dates.')
        # loop through landuse layers and pull out date information provided by user
        landuse_layers_data = []
        for layer_index in range(0, len(self.landuse_layer_name)):
            day = int(self.landuse_day[layer_index])
            month = int(self.landuse_month[layer_index])
            year = int(self.landuse_year[layer_index])
            layer_name = self.landuse_layer_name[layer_index]
            landuse_layers_data.append([month, day, year, layer_name])

            # convert landuse files to tiff files
            layer_path = self.landuse_dir + '/' + layer_name
            converted_layer_path = self.results_dir + '/Raster/' + layer_name + '.tif'
            try:
                geotools.convert_adf_to_tif(layer_path, converted_layer_path)
            except Exception:
                self.logger.exception('Unable to convert raster from .adf to .tif.')
                UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

            # write the date and file into lup.dat
            self.logger.info('Adding landuse layer, ' + layer_name + ', to lup.dat.')
            lup_file.write(
                '{0} {1} {2} {3} {4} {5}\n'.format(
                    ''.ljust(4 - len(str(layer_index + 1))),
                    str(layer_index + 1).ljust(5 - len(str(month)) + len(str(layer_index + 1)) - 1),
                    str(month).ljust(5 - len(str(day)) + len(str(month)) - 1),
                    str(day).ljust(5 - len(str(year)) + len(str(day)) - 1),
                    str(year).ljust(13 - len(str('file' + str(layer_index + 1) + '.dat'))),
                    ('file' + str(layer_index + 1) + '.dat')))
        self.logger.info('Closing lup.dat.')
        lup_file.close()

        self.landuse_layers_data = landuse_layers_data

    def extract_lookup_info(self):
        """
        Opens the uploaded lookup file and extracts the codes and values.
        An error is thrown if one of the landuse values is 0.

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs

        Returns
        -------
        lookup_info: list
            List containing lookup codes and values
        """
        self.logger.info('Extracting loopup information from uploaded lookup file.')
        try:
            lookup_file = csv.reader(open(self.lookup_filepath, 'r'), delimiter=',')
        except:
            self.logger.exception('Unable to open the lookup file.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        # append lookup codes and values to list, throw error if 0 is used
        lookup_info = []
        lookup_index = 0
        for row in lookup_file:
            if row[:][0] == '0':
                # 0 cannot be used as a landuse value, please reclassify
                pass
            lookup_info.append([row[0].strip(), row[1].strip()])

        self.lookup_info = lookup_info

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

        hru_info: tuple
            First value is the pixel size and the second the
            nodata value for the raster
        """
        self.logger.info('Reading hrus1.tif into numpy array.')
        try:
            hrus, hru_info = geotools.read_raster(self.results_dir + '/Raster/hrus1/hrus1.tif')
        except Exception:
            self.logger.exception('Unable to read hrus1.tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        self.logger.info('Reading hru1.shp into numpy array.')
        try:
            merged_hru = geotools.read_shapefile(self.swat_dir + '/Watershed/Shapes/hru1.shp')
            merged_hru = np.array(merged_hru, dtype=int)
            # sort HRU_ID column (second column) into ascending order
            # and keep respective positions of other columns
            # for example:
            # dominant_hrus = [50, 30, 25, 70, 10]
            # new_hrus = [3, 2, 5, 1, 4]
            # old_hrus = [70, 30, 50, 10, 25]
            sorted_hru = merged_hru[merged_hru[:, 1].argsort()]
        except Exception:
            self.logger.exception('Unable to open shapefile hrus1.shp')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        self.logger.info('Sorting and merging the non-dominant and dominant hrus.')
        # retrieve dominant hru values - these are the hrus that remained
        # after the threshold was applied (OBJECTID in hru1.shp)
        dominant_hrus = sorted_hru[:, 0]

        # retrieve new hru values - each dominant hru is assigned a 
        # new hru value starting at 1 (HRU_ID in hru1.shp);
        # for example, dominant hru 5838 (OBJECTID) may become hru 10 (HRU_ID)
        new_hrus = sorted_hru[:, 1]

        # merge non-dominant hrus into nearby dominant hrus
        hrus = swattools.merge(hrus, dominant_hrus, hru_info[1])

        self.logger.info('Creating final_HRU.tif from merged hrus array.')
        try:
            geotools.create_raster(
                hrus,
                self.results_dir + '/Raster/hrus1/w001001.adf',
                self.results_dir + '/Raster/final_HRU.tif')
        except Exception:
            self.logger.info('Failed to create final_HRU.tif.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        self.hrus = hrus
        self.dominant_hrus = dominant_hrus
        self.hru_info = hru_info

    def create_fractional_values(self):
        """
        Calculates the fractional area for each dominant hru. The 
        fractional areas are stored in an array and in a text
        file written to the Output folder.

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs

        hrus: array
            Array of the hrus array non-dominant hrus were merged with
            nearby dominant hrus

        dominant_hrus: array
            Array of the sorted dominant hrus

        hru_info: tuple
            First value is the pixel size and the second the
            nodata value for the raster

        Returns
        -------
        inside_watershed_indexes: array
            Array of the index positions for cells in the hrus1 raster that
            are inside the watershed

        hru_indexes: array or arrays
            Each row in the array represents a hru and each hru has
            an array of the index positions where it is located in the
            hru1 raster

        old_hru_areas: list
            Each element represents the fractional area for a hru
        """
        self.logger.info('Calculating fractional areas for each hru inside the watershed.')
        pixel_size = self.hru_info[0]
        # isolate the pixels with hru values from the nodata pixels
        inside_watershed_indexes = np.nonzero(self.hrus != self.hru_info[1])
        inside_watershed_hrus = self.hrus[inside_watershed_indexes]

        # create a text file called hru_area.txt using append mode
        hru_areas_file = open(self.results_dir + '/Output/hru_areas.txt', 'w')
        # write header for file
        hru_areas_file.write('HRU_ID, HRU_AREA')

        # put dominant hrus in set type
        dominant_hrus_set = set(self.dominant_hrus)

        # dictionary where each key is a dominant hru and
        # the value is a list containing the indexes where
        # the dominant hru appears in the watershed -
        # found in variable inside_watershed_hrus

        # initialize dictionary
        dominant_hrus_inside_watershed_indexes = {}
        for hru in dominant_hrus_set:
            dominant_hrus_inside_watershed_indexes[hru] = []

        # loop through hrus inside the watershed and append indexes (values)
        # for the dominant hrus (keys)
        for hru_index, hru_val in enumerate(inside_watershed_hrus):
            if hru_val in dominant_hrus_set:
                dominant_hrus_inside_watershed_indexes[hru_val].append(hru_index)

        old_hru_areas = np.zeros(len(self.dominant_hrus))

        # loop through dominant hrus and calculate fractional area
        hru_indexes = []
        for dominant_hru_index, dominant_hru_value in enumerate(self.dominant_hrus):
            # i don't understand why the next two lines are necessary....
            hru_index = np.array(dominant_hrus_inside_watershed_indexes[dominant_hru_value])
            hru_indexes.append(hru_index)

            # number of instances of the hru
            hru_count = len(dominant_hrus_inside_watershed_indexes[dominant_hru_value])
            # convert area from square meter to acres and multiply by count
            hru_area = (pixel_size**2 * 10**-6) * hru_count
            # store area in array
            old_hru_areas[dominant_hru_index] = hru_area

        self.logger.info('Writing fractional areas to hru_areas.txt.')
        # write fractional areas to the open file
        for hru_area_index, hru_area_value in enumerate(old_hru_areas):
            hru_areas_file.write('\n')
            hru_areas_file.write(str(hru_area_index + 1))
            hru_areas_file.write(', ')
            hru_areas_file.write(str(hru_area_value))
        self.logger.info('Closing hrus_areas.txt.')
        # close the text file
        hru_areas_file.close()

        self.inside_watershed_indexes = inside_watershed_indexes
        self.hru_indexes = hru_indexes
        self.old_hru_areas = list(old_hru_areas)

    def extract_hru_files_data(self):
        """
        Goes to the TxtInOut folder and reads through all of the .hru
        files (excluding the output.hru files) and pulls out the following
        information for each hru: hru id, subbasin id, landuse abbrev.,
        soil code, and slope range. 

        The previously extracted landuse lookup information is then used 
        to find the numerical code for each landuse abbreviation extracted 
        from the hru files. Unique soil, slope, and subbasin codes are found
        and placed into individual arrays. Ultimately these arrays are merged
        into a single array that is the same size as the dominant hrus array.
        Each row in the array represents a hru and each column an attribute
        for the hru. There are six columns (hru id, hru index range (starts
        at 0), subbasin id, landuse code, soil code, and slope range code)

        Parameters
        ----------
        data: dictionary
            Contains file and directory paths for inputs

        dominant_hrus: array
            Array of the sorted dominant hrus

        lookup_info: list
            List containing lookup codes and values

        Returns
        -------
        hru_files_data: array
            Each row represents a hru and each column a attribute associated
            with the hru - see description for more information on the columns

        unique_subbasin_ids: array
            Array of the watershed's unique subbasin ids
        """
        # collect hru information from the hru files in the TxtInOut directory
        self.logger.info('Collect hru data from hru files in TxtInOut.')
        try:
            hru_files_read = swattools.read_hru_files(
                self.swat_dir + '/Scenarios/Default/TxtInOut')
            # separate out the different attribute lists
            hru_ids_from_hru_files = hru_files_read[0]
            subbasin_ids_from_hru_files = hru_files_read[1]
            landuse_abbrevs_from_hru_files = hru_files_read[2]
            soil_codes_from_hru_files = hru_files_read[3]
            slope_ranges_from_hru_files = hru_files_read[4]
        except Exception:
            self.logger.info('Unable to read the hru files in TxtInOut.')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        # verify the length (count) of the list matches our dominant hrus
        if len(hru_ids_from_hru_files) != len(self.dominant_hrus):
            # halt function
            self.logger.info('Number of HRU ids (' + str(
                len(hru_ids_from_hru_files)) + ') found in *.hru files does not match number of dominant HRUs (' + str(
                len(self.dominant_hrus)) + ').')
            UserTask.objects.filter(task_id=self.task_id).update(task_status=2)

        self.logger.info('Collecting subbasin ids, landuse codes, soil codes, slope ranges, and subbasin ids.')
        # get each hru's landuse code
        landuse_codes = np.zeros(len(landuse_abbrevs_from_hru_files), int)
        for code_index in range(0, len(self.lookup_info) - 1):
            landuse_codes[np.nonzero(np.array(landuse_abbrevs_from_hru_files) == self.lookup_info[code_index + 1][1])] = self.lookup_info[code_index + 1][0]

        # get each hru's soil code
        unique_soil_codes = list(set(soil_codes_from_hru_files))
        soil_codes = np.zeros(len(soil_codes_from_hru_files), int)
        for i in range(0, len(unique_soil_codes)):
            soil_codes[np.nonzero(np.array(soil_codes_from_hru_files) == unique_soil_codes[i])] = i

        # get each hru's slope range
        unique_slope_ranges = list(set(slope_ranges_from_hru_files))
        slope_ranges = np.zeros(len(slope_ranges_from_hru_files), int)
        for i in range(0, len(unique_slope_ranges)):
            slope_ranges[np.nonzero(np.array(slope_ranges_from_hru_files) == unique_slope_ranges[i])] = i

        # get unique subbasin ids
        unique_subbasin_ids = list(set(subbasin_ids_from_hru_files))

        self.logger.info('Packing hru information into a single array.')
        # put all this hru info into a single array
        hru_files_data = np.transpose([
            self.dominant_hrus,
            range(0, len(hru_ids_from_hru_files)),
            subbasin_ids_from_hru_files,
            landuse_codes,
            soil_codes,
            slope_ranges])

        self.hru_files_data = hru_files_data
        self.unique_subbasin_ids = unique_subbasin_ids

    def apply_realization(self):
        # read the landuse raster into a numpy array
        landuse_lyr_name = self.landuse_layers_data[0][3]

        landuse_array, layer_info = geotools.create_raster_array(
            self.results_dir + '/Raster/hrus1',
            self.results_dir + '/Raster/' + landuse_lyr_name + '.tif')
        # get the nodata value
        landuse_nodata = layer_info[1]

        # get non-zero array indexes for landuse raster - exclude the nodata
        landuse_indexes = np.nonzero(landuse_array != landuse_nodata)

        # updated landuse numpy array with the nodata values removed
        landuse_array = landuse_array[landuse_indexes]

        # initiate a variable to store hru fractional area
        hru_subbasin_fractional_areas = np.zeros(len(list(self.old_hru_areas)))
        new_fractional_hru_areas = np.zeros(len(list(self.old_hru_areas)))
        hru_areas = np.array(list(self.old_hru_areas))

        # each element represents a hru's subbasin
        hru_subbasins = np.array(self.hru_files_data[:, -4])

        # loop through each subbasin
        for subbasin_id in self.unique_subbasin_ids:

            # find indexes in hru subbasins array matching the current subbasin
            hrus_in_sub_idx = np.nonzero(hru_subbasins == subbasin_id)

            # get area for HRUs in the subbasin
            hrus_in_sub_areas = hru_areas[hrus_in_sub_idx]

            # get total area for HRUs in the subbasin
            hrus_in_sub_total_area = sum(hru_areas[hrus_in_sub_idx])

            # calculate fractional areas
            fractional_area = hrus_in_sub_areas / hrus_in_sub_total_area
            hru_subbasin_fractional_areas[hrus_in_sub_idx] = fractional_area

        # loop through each LULC code
        for i in range(0, len(self.lookup_info) - 1):

            # collect the error and realizations
            error = self.uncertainty_error_data[i][0]
            realization = self.uncertainty_error_data[i][1]

            # check if error is specified
            if error > 0 and realization > 0:

                # we know error exists, distribute the error uniformly
                # (handle division by 0 with try/except)
                try:
                    error_range = range(-error, error + 1, int((2 * error) / (realization - 1)))
                except ZeroDivisionError:
                    error_range = range(-error, error + 1, int(2 * error))
                
                # loop through number of realization range
                for j in range(0, realization):

                    # loop through subbasins
                    for k in range(0, len(self.unique_subbasin_ids)):

                        # identify HRUs that are in subbasin k
                        hrus_in_sub = self.hru_files_data[np.where(self.hru_files_data[:, 2] == self.unique_subbasin_ids[k])]

                        # identify HRUs that have landuse i AND are located in subbasin k
                        hrus_in_sub_with_lulc = hrus_in_sub[np.where(hrus_in_sub[:, 3] == int(self.lookup_info[i + 1][0]))]

                        # fetch fractional areas for HRUs in sub with the current lulc
                        matching_hrus_fractional_areas = hru_subbasin_fractional_areas[hrus_in_sub_with_lulc[:, 1]]

                        # calculate cumulative fractional area
                        matching_hrus_cumulative_fractional_area = sum(matching_hrus_fractional_areas)

                        # calculate portion of cumulative area subject to error
                        error_area = (error_range[j] / 100.0) * matching_hrus_cumulative_fractional_area

                        # calculate each HRUs area percentage
                        matching_hrus_percentage_area = matching_hrus_fractional_areas / matching_hrus_cumulative_fractional_area

                        # increase/decrease the area of affected HRUs based on error range 
                        new_fractional_hru_areas[hrus_in_sub_with_lulc[:, 1]] = matching_hrus_fractional_areas + (error_area * matching_hrus_percentage_area)

                        # identify the unaffected HRUs (i.e. those in subbasin
                        # k that do not have lulc i)
                        hrus_in_sub_without_lulc = hrus_in_sub[np.where(hrus_in_sub[:, 3] != int(self.lookup_info[i + 1][0]))]

                        # fetch fractional areas for HRUs in sub with the current lulc
                        matching_hrus_without_lulc_fractional_areas = hru_subbasin_fractional_areas[hrus_in_sub_without_lulc[:, 1]]

                        # find how much area needs to be adjusted
                        fractional_area_diff = sum(matching_hrus_fractional_areas) - sum(new_fractional_hru_areas[hrus_in_sub_with_lulc[:, 1]])

                        # calculate each HRUs area percentage
                        matching_hrus_without_lulc_percentage_area = matching_hrus_without_lulc_fractional_areas / sum(matching_hrus_without_lulc_fractional_areas)

                        # now adjust the non-affected HRUs based on error range
                        new_fractional_hru_areas[hrus_in_sub_without_lulc[:, 1]] = matching_hrus_without_lulc_fractional_areas + (fractional_area_diff * matching_hrus_without_lulc_percentage_area)

                    # once realization is processed, write to a suitable output file
                    hru_fa_file = open(self.results_dir + '/Output/file' + str(self.lookup_info[i + 1][0]) + '_' + str(j + 1) + '_' + str(error_range[j]) + '_perc.dat', 'a')

                    # write header columns (HRU_ID are the new HRU ids assigned in hru1.shp
                    hru_fa_file.write('HRU_ID, HRU_AREA')

                    # loop through hrus and write fractional area to text file
                    for hru_idx in range(0, len(self.dominant_hrus)):
                        hru_fa_file.write('\n')
                        hru_fa_file.write(str(hru_idx + 1))
                        hru_fa_file.write(', ')
                        hru_fa_file.write('{0:.6f}'.format(round(new_fractional_hru_areas[hru_idx], 6)))

                    # add new line at end of file
                    hru_fa_file.write('\n')

                    # close the file
                    hru_fa_file.close()

    def copy_results_to_depot(self):
        """
        Copies output from process over to web directory for user's consumption.
        """
        self.logger.info('Copying output directory to user directory on depot.')

        # If output directory already exists in web directory, remove it
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

        # Copy output over to web directory
        shutil.copytree(self.results_dir, self.output_dir)

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
            self.logger.exception('Error sending the user the email to their data.')
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
        self.logger.info('Sending user email informing them an error has occurred.')
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
            self.logger.exception('Error sending the user the email informing ' +
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
        return (datetime.datetime.now() + datetime.timedelta(hours=48)).strftime("%m-%d-%Y %H:%M:%S")

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
        UserTask.objects.filter(task_id=self.task_id).update(task_status=1, time_completed=datetime.datetime.now())
