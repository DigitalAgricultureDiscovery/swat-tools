from osgeo import gdal
from scipy import ndimage
from numpy.core.fromnumeric import nonzero
import glob


def merge(hrus, dominant_hrus, nodata_value):
    """
    Non-dominant HRUs are merged into neighboring dominant HRUs
    using a Euclidean allocation method. 

    Parameters
    ----------
    hrus: array
        original hru1 raster pre-threshold
    dominant_hrus: array
        dominant hrus obtained from hru1.shp post-threshold
    nodata_value: float
        nodata_value for hru1.tif (carried over from original raster)

    Returns
    -------
    hrus: array
        hru raster with non-dominant hrus merged into dominant hrus
    """
    # inside_watershed will have values for which merging step is carried
    inside_watershed_indexes = nonzero(hrus != nodata_value)
    outside_watershed_indexes = nonzero(hrus == nodata_value)

    # copy hru values
    hrus_test = hrus.copy()
    # change the default nodata value to 1
    hrus_test[outside_watershed_indexes] = 1
    # set type increases following loop's performance
    dominant_hrus_set = set(dominant_hrus)

    # set dominant hrus to 0 and non-dominant to 1
    for i in range(0, len(inside_watershed_indexes[0])):
        if hrus_test[inside_watershed_indexes[0][i]][
            inside_watershed_indexes[1][i]] in dominant_hrus_set:
            hrus_test[inside_watershed_indexes[0][i]][
                inside_watershed_indexes[1][i]] = 0
        else:
            hrus_test[inside_watershed_indexes[0][i]][
                inside_watershed_indexes[1][i]] = 1

    # perform eclidean allocation, returns the indexes
    # of the nearest dominant hru
    indexes = ndimage.distance_transform_edt(hrus_test, return_indices=True)[1]
    # rows and columns of the indexes
    rows = indexes[0]
    cols = indexes[1]

    # use indexes to update non-dominant hrus with nearest dominant hru
    for i in range(0, len(rows)):
        for j in range(0, len(rows[0])):
            hrus[i][j] = hrus[rows[i][j]][cols[i][j]]

    # reset nodata now that merging is complete
    hrus[outside_watershed_indexes] = nodata_value

    return hrus


def read_hru_files(txt_in_out_dir):
    """
    Opens the .hru files (excluding output.hru and outputb.hru) and
    finds the index position for our attributes of interest:
        hru ids
        subbasin ids
        landuse codes
        soil codes
        slope ranges
    Once the indexes are found we can use them to find the actual
    values for each attribute and store them in their respective lists.
    One large list wraps around our individual lists for each
    attribute and returned.

    Parameters
    ----------
    txt_in_out_dir: string
        Location of the TxtInOut directory

    Returns
    -------
    hru_files_attribute_values: list of lists
        One large list containing a list of each attribute. Each 
        attribute list contains a value for each hru file.
    """

    # loop through all hru files in TxtInOut directory -
    # do NOT include output.hru and outputb.hru in the list
    hru_filepaths = []
    for hru_file in glob.glob(txt_in_out_dir + '/*.hru'):
        if (hru_file != txt_in_out_dir + '/output.hru') and \
                (hru_file != txt_in_out_dir + '/outputb.hru'):
            hru_filepaths.append(hru_file)
    # sort filepaths
    hru_filepaths.sort()

    hru_ids = []
    subbasin_ids = []
    soil_codes = []
    slope_ranges = []
    landuse_abbrevs = []
    # loop through hru files
    for hru_filepath in hru_filepaths:
        # open the hru file, read the first line and close the file
        hru_file = open(hru_filepath, 'r', errors="surrogateescape")
        first_line = hru_file.readline()
        hru_file.close()

        # collect the indexes in the first line where our
        # attributes of interest appear
        hru_index = first_line.index('HRU:')
        subbasin_index = first_line.index('Subbasin:')
        last_hru_index = first_line.rindex('HRU:')
        landuse_index = first_line.index('Luse:')
        soil_index = first_line.index('Soil:')
        slope_index = first_line.index('Slope')

        # while testing we noticed that while most .hru files used
        # '/'s for the date, some used '-'s - this will catch that case
        try:
            slash_index = first_line.index('/')
        except ValueError:
            slash_index = first_line.index('-')

        # use the indexes to find the values
        hru_id = int(float(first_line[hru_index + 4: subbasin_index - 1]))
        subbasin_id = int(
            float(first_line[subbasin_index + 9: last_hru_index - 1]))
        landuse_abbrev = first_line[landuse_index + 5: soil_index - 1]
        soil_code = first_line[soil_index + 6: slope_index - 1]
        slope_range = first_line[slope_index + 6: slash_index - 2]

        # append values from each hru to one list per attribute
        hru_ids.append(hru_id)
        subbasin_ids.append(subbasin_id)
        landuse_abbrevs.append(landuse_abbrev)
        soil_codes.append(soil_code)
        slope_ranges.append(slope_range)

    # pack all the lists into one large list
    hru_files_attribute_values = [
        hru_ids,
        subbasin_ids,
        landuse_abbrevs,
        soil_codes,
        slope_ranges
    ]

    return hru_files_attribute_values


def validate_raster_properties(hrus1_path, lu_path, lu_layers):
    """
    Checks whether the hrus1 raster and landuse rasters have the
    same resolution and same extent (row/cols). If the landuse rasters
    have a larger extent than hrus1 a warning will be issued. If the
    landuse rasters have a smaller extent than hrus1, an error is issued.

    Parameters
    ----------
    hrus1_path: string
        path to the hrus1 raster (swatmodel/Watershed/Grid/hrus1)
    lu_path: string
        path to the landuse directory
    lu_layers: list of strings
        list of landuse layer names

    Returns
    -------
    validated: dictionary
        status key either 'pass', 'warn', 'error'
    """
    # open hrus1 raster with gdal
    hrus1 = gdal.Open(hrus1_path)

    # get hrus1 geoproperties
    hrus1_gt = hrus1.GetGeoTransform()

    # get hrus1 pixel resolution
    hrus1_pres = hrus1_gt[1]

    # get hrus1 (rows,cols) extent
    hrus1_extent = hrus1.RasterYSize, hrus1.RasterXSize

    # validation flag
    validated = {
        'status': 'pass',
        'msg': 'Passed all tests.'
    }

    # repeat above steps for each landuse layer
    for layer_name in lu_layers:
        lu = gdal.Open(lu_path + '/' + layer_name)
        lu_pres = lu.GetGeoTransform()[1]
        lu_extent = lu.RasterYSize, lu.RasterXSize

        # test if pixel resolution matches hrus1 (only compare to hundredths)
        if round(hrus1_pres, 2) != round(lu_pres, 2):
            validated['status'] = 'error'
            validated[
                'msg'] = 'The resolution of hrus1 and ' + layer_name + ' do not match. ' + \
                         'Your landuse layers must have the same resolution as hrus1. ' + \
                         'Please refer to the manual for more information on this subject.'

        # test if rows,cols matches hrus1
        if hrus1_extent != lu_extent:
            if hrus1_extent[0] > lu_extent[0] or hrus1_extent[1] > lu_extent[1]:
                validated['status'] = 'error'
                validated[
                    'msg'] = layer_name + '\'s extent is smaller than hrus1\'s extent. ' + \
                             'Your landuse layers must have an extent equal to or greater than that of hrus1. ' + \
                             'Please refer to the manual for more information on this subject.'

    return validated
