from osgeo import gdal, ogr
from subprocess import check_call

import numpy as np
import shapefile


def get_raster_coords(raster_filepath):
    """
    Opens a raster file, extracts the x,y coordinates at the
    centroid of each cell, and returns the coordinates.

    Parameters
    ----------
    raster_filepath: string
        Filepath to raster file

    Returns
    -------
    raster_data: dictionary containing raster data
    """
    # open raster with gdal
    rst = gdal.Open(raster_filepath)

    # extract columns and row sizes
    cols = rst.RasterXSize
    rows = rst.RasterYSize

    # get geotransform properties
    gt = rst.GetGeoTransform()

    # get raster origins
    xmin = gt[0]
    ymax = gt[3]

    # get raster cell size
    cell_size = gt[1]

    # create empty lists that will hold the x, y coordinates
    x_coords = [[None]] * rows
    y_coords = [[None]] * rows

    # starting with the xmin, generate the first row of x coords by
    # adding the cell size to the previous x coord. repeat this for
    # the number of columns in the raster. after the first row is
    # completed, shift to the next row and repeat the process until
    # all the rows have been completed.
    for i in range(0, rows):
        x_coords[i] = np.arange(xmin, xmin + (cols * cell_size), cell_size)

    # starting with the ymin, generate the first row of y coords by
    # adding the cell size to the previous Y coord. do this for the
    # number of columns in the raster. after the first row is completed,
    # shift to the next row and repeat the process until all the rows
    # have been completed.
    for i in range(0, rows):
        y_coords[i] = [ymax] * cols
        ymax -= cell_size

    raster_data = {
        'array': rst.ReadAsArray(),
        'cell_size': cell_size,
        'coords': (x_coords, y_coords),
        'nodata': rst.GetRasterBand(1).GetNoDataValue(),
    }

    return raster_data


def create_raster_array(hrus1_filepath, landuse_filepath):
    """
    Use the hrus1 coordinates to extract landuse values from the landuse
    raster and then create landuse numpy array with same extent as hrus1.

    Parameters
    ----------
    hrus1_filepath: string
        Filepath to hrus1 raster
    landuse_filepath: string
        Filepath to landuse raster

    Returns
    -------
    landuse_array: tuple of array and tuple
        Numpy array containing landuse values and tuple with
        cell size and no data value
    """
    # get gdal info from hrus1 raster
    hrus1_data = get_raster_coords(hrus1_filepath)

    # open landuse raster
    lulc = gdal.Open(landuse_filepath)

    # get landuse band
    lulc_band = lulc.GetRasterBand(1)

    # get geotransform info for landuse layer
    lulc_gt = lulc.GetGeoTransform()

    # get x and y origins for the landuse layer
    x_origin, y_origin = lulc_gt[0], lulc_gt[3]

    # initialize landuse array
    landuse_array = np.empty(
        (len(hrus1_data['coords'][0]), len(hrus1_data['coords'][0][0])))

    # use landuse x, y origins to find landuse values at hrus1 coordinates
    for i in range(0, len(hrus1_data['coords'][0])):
        for j in range(0, len(hrus1_data['coords'][0][0])):
            x = hrus1_data['coords'][0][i][j]
            y = hrus1_data['coords'][1][i][j]
            x_offset = int((x - x_origin) / hrus1_data['cell_size'])
            y_offset = abs(int((y - y_origin) / hrus1_data['cell_size']))
            if hrus1_data['array'][i][j] != hrus1_data['nodata']:
                landuse_array[i][j] = \
                lulc_band.ReadAsArray(x_offset, y_offset, 1, 1)[0, 0]
            else:
                landuse_array[i][j] = hrus1_data['nodata']

    return landuse_array, (hrus1_data['cell_size'], hrus1_data['nodata'])


def read_raster(raster_filepath):
    """
    Opens a geotiff and creates numpy array of the first
    band's values. Additionally collects the pixel size info.

    Parameters
    ----------
    raster_filepath: string
        Filepath to hru1.tif or a landuse layer

    Returns
    -------
    data, (pixel_size, nodata_value): tuple of array and tuple
        Numpy array of raster's first band and tuple
        of the pixel size (float) and nodata value (float)
    """
    # open raster with gdal
    rst = gdal.Open(raster_filepath)

    # extract columns and rows sizes
    cols = rst.RasterXSize
    rows = rst.RasterYSize

    # get pixel size
    pixel_size = rst.GetGeoTransform()[1]

    # pull out info for first band in raster
    band = rst.GetRasterBand(1)
    # get NoData value
    nodata_value = band.GetNoDataValue()

    # put first band info into numpy array (preserve dimensions)
    data = band.ReadAsArray(0, 0, cols, rows)

    # return numpy array and pixel size
    return data, (pixel_size, nodata_value)


def read_shapefile(shapefile_filepath):
    """
    Reads a shapefile using pyshp (imported as shapefile) and
    returns the records (OBJECTID, HRU_ID, HRU_GIS).

    Parameters
    ----------
    shapefile_filepath: string
        location of the uploaded shapefile

    Returns
    -------
    records: list_of_lists
        list containing a list of three items for each shapefile record

    """
    shp = shapefile.Reader(shapefile_filepath)
    records = shp.records()

    return records


def get_shapefile_extent(shapefile_filepath):
    """
    Opens up shapefile with GDAL/OGR and returns the
    bounding box (extent) for the shapefile.

    Parameters
    ----------
    shapefile_filepath: string
        location of the uploaded shapefile

    Returns
    -------
    extent: list
        list containing the extent (bounding box) for the shapefile

    """
    # load ESRI shapefile driver
    driver = ogr.GetDriverByName('ESRI Shapefile')

    # open the shapefile
    datasource = driver.Open(shapefile_filepath, 0)

    # get layer from shapefile
    layer = datasource.GetLayer()

    # get shapefile's extent
    extent = layer.GetExtent()

    return extent


def create_raster(array_data, original_hrus_filepath, new_hrus_filepath):
    """
    Takes the numpy array hrus, array of non-dominant hrus have
    been merged with nearby dominant hrus, and creates a new
    geotiff containing the array's values and the original hrus
    raster's spatial information (projection, extent, etc...)

    Parameters
    ----------
    array_data: array
        Array of hrus where non-dominant hrus are merged
        with nearby dominant hrus
    original_hrus_filepath: string
        Filepath to the uploaded hrus1 (w001001.adf) raster
    new_hrus_filepath: string
        Filepath for the new hrus raster this method creates

    Returns
    -------
    None
    """
    # open original hrus1 raster with gdal
    original_hrus = gdal.Open(original_hrus_filepath)
    # get rows and cols dimensions
    cols = original_hrus.RasterXSize
    rows = original_hrus.RasterYSize
    # get geotransform info (origin, pixel resolution, etc.)
    geotransform = original_hrus.GetGeoTransform()
    # get raster's projection info
    proj = original_hrus.GetProjection()
    # get raster values for first band
    band = original_hrus.GetRasterBand(1)
    # get pixel datatype for the band
    datatype = band.DataType
    # register geotiff driver
    driver = gdal.GetDriverByName("GTiff")
    driver.Register()
    # create geotiff container
    new_hrus = driver.Create(
        new_hrus_filepath,
        cols,
        rows,
        1,
        datatype,
        options=['COMPRESS=LZW'])
    # update geotransform and projection to match the original hrus raster
    new_hrus.SetGeoTransform(geotransform)
    new_hrus.SetProjection(proj)
    # write the updated hrus array to the newly created geotiff file
    new_hrus.GetRasterBand(1).WriteArray(array_data)
    # flush raster data cache - recovers memory used in this process
    new_hrus.FlushCache()


def convert_adf_to_tif(raster_filepath, output_filepath):
    """
    Convert a Esri grid raster (.adf) to geotiff (.tif) raster using
    GDAL's 'gdal_translate' utility program.

    Parameters
    ----------
    raster_filepath: string
        Filepath to the Esri grid raster (.adf)

    output_filepath: string
        Folderpath where the tif file should be written
    Returns
    -------
    None
    """
    adf_raster = raster_filepath + '/w001001.adf'

    adf_gdal = gdal.Open(raster_filepath)
    adf_band = adf_gdal.GetRasterBand(1)
    adf_nodata = adf_band.GetNoDataValue()

    # convert base raster into tif file
    check_call([
        'gdal_translate', '-co', 'compress=lzw', '-a_nodata', str(adf_nodata),
        '-of', 'GTiff', adf_raster, output_filepath])


def rasterize_shapefile(layer_info, shp_filepath, new_tif_filepath):
    """
    Takes a shapefile and converts it to a geotiff raster using
    GDAL's gdal_rasterize utility program.

    Parameters
    ----------
    layer_info: dictionary
        Contains the keys 'attribute_name', 'extent', and 'layername'

    shp_filepath: string
        Filepath for the shapefile that will be converted to a raster

    new_tif_filepath: string
        Filepath for the newly created raster

    Returns
    -------
    None
    """
    # get extent for new raster
    cols = layer_info['extent'][0]
    rows = layer_info['extent'][1]

    # use gdal_rasterize to convert shapefile into geotiff
    check_call([
        'gdal_rasterize',  # GDAL utility program
        '-of', 'Gtiff',  # format
        '-a', layer_info['attribute_name'],  # attribute name
        '-ts', cols, rows,  # width height
        '-ot', 'Byte',  # type
        '-co', 'COMPRESS=LZW',  # compression
        '-l', layer_info['layername'],  # layername
        shp_filepath, new_tif_filepath])  # shapefile, new raster


def matplotlib_pip(points, polygon):
    """
    Takes a list of points in tuples (i.e. [(x1, y1), (x2, y2), etc.] and
    uses matplotlib's Path.contains_points to determine whether or not
    a point is located in a polygon Path object. Returns a boolean list
    where True indicates the point is located in the polygon.

    Parameters
    ----------
    points: list of tuples
        List of point coordinates stored in tuples
    polygon: list
        List of points that make up a polygon

    Returns
    -------
    boolean list the same size as the points list
    """
    return polygon.contains_points(points)
