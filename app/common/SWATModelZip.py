import glob
import logging
import os
import shutil
from zipfile import ZipFile

from django.core.files.uploadedfile import UploadedFile
import boto3
import fiona

from s3upload.models import S3Upload
from .utils import create_working_directory, fix_file_permissions

UPLOAD_KEYS = ["workspace", "local", "aws"]

logger = logging.getLogger('swatmodelzip')


class NotAZipError(Exception):
    pass


class SWATModelZip:

    def __init__(self, upload: dict, tool: str = None) -> None:
        self.errors = {
            "folders": False,    # model directory containing "Scenarios" and "Watershed"
            "raster": False,     # hrus1 raster grid
            "shapefile": False,  # hru1 shapefile
            "hrus": False,       # hru files in TxtInOut
            "hru_id": False,     # HRU_ID field present in hru1 shapefile
            "objectid": False,   # OBJECTID field present in hru1 shapefile
            "matching_hrus": False
        }
        self.swat_model_directory = ""

        if tool == "field":
            self.errors["swatmdb"] = False

        check_upload_keys(upload)

        # Root workspace for input and output files
        workspace = upload["workspace"]
        # Sub workspace for input files
        workspace_input = os.path.join(workspace, "input")

        if upload["local"]:
            self.filename = upload["local"].name
        else:
            self.filename = upload["aws"][0].file_name

        create_working_directory(upload["workspace"])

        if not os.environ.get("TEST_FLAG"):
            remove_existing_upload(workspace_input, self.filename)

        if not os.environ.get("TEST_FLAG"):
            if upload["local"]:
                write_file_to_disk(workspace_input, upload["local"])
            else:
                download_file_to_server(
                    os.path.join(workspace_input, self.filename), upload["aws"][0])

        check_if_file_exists(os.path.join(workspace_input, self.filename))
        check_if_file_is_zip(os.path.join(workspace_input, self.filename))

        unzip_file(workspace_input, self.filename)

        self.root_folder_name = find_root_folder(workspace_input)
        if not self.root_folder_name:
            return
        else:
            self.errors["folders"] = True

        self.swat_model_directory = os.path.join(
            workspace_input, self.root_folder_name)

        fix_file_permissions(self.swat_model_directory)

        self.errors["raster"] = check_for_hrus1_raster(
            self.swat_model_directory)
        self.errors["shapefile"] = check_for_hru1_shp(
            self.swat_model_directory)
        self.errors["hrus"] = check_for_hrus(self.swat_model_directory)

        if self.errors["shapefile"]:
            self.errors["hru_id"] = check_for_hru_id_field(
                self.swat_model_directory)
            self.errors["objectid"] = check_for_objectid_field(
                self.swat_model_directory)
            self.errors["matching_hrus"] = check_for_matching_number_of_hrus_in_hru1_and_txtinout(
                self.swat_model_directory)
        else:
            self.errors["hru_id"] = True
            self.errors["objectid"] = True
            self.errors["matching_hrus"] = True

        # Run check only for Field SWAT
        if tool == "field":
            self.errors["swatmdb"] = check_for_swatoutput_mdb(
                self.swat_model_directory
            )

    def get_filename(self) -> str:
        return self.filename

    def get_directory(self) -> str:
        return self.swat_model_directory

    def validate_model(self) -> dict:
        """
        Checks for any missing files that are required by SWAT tools.
        Returns a status code and list of error messages for any 
        missing files.

        Parameters
        ----------
        None

        Returns
        -------
        results: dict
            Status code and list of error messages (if any).
        """
        results = {"status": 0, "errors": []}

        for key in self.errors.keys():
            if self.errors[key] is False:
                results["status"] = 1
                results["errors"].append(
                    get_error_message(key, self.root_folder_name))

        return results


def check_upload_keys(upload: dict) -> None:
    """
    Checks if upload contains the three required keys: 
    workspace, local, and aws. Raises an error if one or 
    more required keys are missing.

    Parameters
    ----------
    upload: dict
        Object containing info related to uploaded SWAT model zip.

    Returns
    -------
    None
    """
    required_keys_included = [key in upload.keys() for key in UPLOAD_KEYS]
    if not all(required_keys_included):
        missing_required_keys = ""
        for index, value in enumerate(required_keys_included):
            if value is False:
                if missing_required_keys:
                    missing_required_keys += f', "{UPLOAD_KEYS[index]}"'
                else:
                    missing_required_keys += f', "{UPLOAD_KEYS[index]}"'

        raise KeyError(
            f'Parameter "upload" dictionary missing key(s): {missing_required_keys}.')


def remove_existing_upload(workspace: str, filename: str) -> None:
    """
    Checks if this file was previously uploaded and extracted. If so,
    the existing directory is removed.

    Parameters
    ----------
    workspace: str
        Current working directory for task.
    filename: str
        Name of uploaded zip file.

    Returns
    -------
    None
    """
    filepath = os.path.join(workspace, os.path.splitext(filename)[0])

    if os.path.exists(filepath):
        shutil.rmtree(filepath)

    if os.path.exists(os.path.join(workspace, filename)):
        os.remove(os.path.join(workspace, filename))


def download_file_to_server(filepath: str, upload_obj: S3Upload) -> None:
    """
    Downloads uploaded zip file from a remote server.

    Parameters
    ----------
    filepath: str
        Full filepath for file to be downloaded from S3.
    upload_obj: S3Upload
        S3Upload object for the file that will be downloaded.

    Returns
    -------
    None
    """
    # Get name of S3 bucket
    s3_bucket = os.environ['AWS_STORAGE_BUCKET_NAME']

    # Connect to S3 services w/ credentials
    s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
        )
    
    # Download file from bucket
    with open(filepath, 'wb') as file_obj:
        s3.download_fileobj(
            s3_bucket, 
            f'user_uploads/{upload_obj.user_id}/{upload_obj.file_name}', 
            file_obj
        )


def write_file_to_disk(workspace: str, local_file: UploadedFile) -> None:
    """
    Write file uploaded to server to unique workspace.

    Parameters
    ----------
    workspace: str
        Unique workspace for current task.
    local_file: UploadedFile
        Uploaded file to local server.
    """
    filepath = os.path.join(workspace, local_file.name)
    with open(filepath, "wb+") as destination:
        for chunk in local_file.chunks():
            destination.write(chunk)


def check_if_file_exists(filepath: str) -> bool:
    """
    Check if uploaded zip file exists in working directory.

    Parameters
    ----------
    filepath: str
        Full path to the uploaded zip file.

    Returns
    -------
    bool
        True if the file exists, false if it does not.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError("SWAT Model zip not in specified directory")
    else:
        return True


def check_if_file_is_zip(filepath: str) -> bool:
    """
    Check if uploaded zip file has the .zip extension.

    Parameters
    ----------
    filepath: str
        Full path to the uploaded zip file.

    Returns
    -------
    bool
        True if the file has a zip extension, false if it does not.
    """
    if not os.path.splitext(filepath)[1] == ".zip":
        raise NotAZipError("Uploaded file does not have the .zip extension")


def unzip_file(workspace: str, filename: str) -> None:
    """
    Unzip uploaded zip file.

    Parameters
    ----------
    workspace: str
        Current working directory for task.
    filename: str
        Name of uploaded zip file.

    Returns
    -------
    None
    """
    filepath = os.path.join(workspace, filename)
    with ZipFile(filepath, "r") as zf:
        zf.extractall(workspace)

    # Remove zip file after extraction finishes
    os.remove(filepath)


def find_root_folder(workspace) -> str:
    """
    Find folder containing SWAT Model sub-directories "Watershed"
    and "Scenarios".

    Parameters
    ----------
    workspace: str
        Current working directory for task.

    Returns
    -------
    root_folder: str
        Name of folder containing SWAT Model sub-directories.
    """
    root_folder = ""

    workspace_directories = next(os.walk(workspace))[1]

    if "Watershed" in workspace_directories and "Scenarios" in workspace_directories:
        root_folder = workspace
    else:
        for directory in next(os.walk(workspace))[1]:
            sub_directories = next(
                os.walk(os.path.join(workspace, directory)))[1]
            if "Watershed" in sub_directories and "Scenarios" in sub_directories:
                root_folder = directory

    return root_folder


def check_for_hrus1_raster(model_directory: str) -> bool:
    """
    Checks for the hrus1 raster in the Grid directory.

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if hrus1 raster found, False otherwise.
    """
    return os.path.exists(os.path.join(
        model_directory,
        "Watershed",
        "Grid",
        "hrus1",
        "w001001.adf"))


def check_for_hru1_shp(model_directory: str) -> bool:
    """
    Checks for the hru1 shapefile in the Shapes directory.

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if hru1 shapefile found, False otherwise.
    """
    return os.path.exists(os.path.join(
        model_directory,
        "Watershed",
        "Shapes",
        "hru1.shp"
    ))


def check_for_hrus(model_directory: str) -> bool:
    """
    Checks for the .hru files in the TxtInOut directory. 

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if more than 1 .hru found, False otherwise.
    """
    return len(glob.glob(os.path.join(
        model_directory,
        "Scenarios",
        "Default",
        "TxtInOut",
        "*.hru"
    ))) > 0


def check_for_swatoutput_mdb(model_directory: str) -> bool:
    """
    Checks for the SWATOutput.mdb database in the TablesOut directory. 

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if SWATOutput.mdb found, False otherwise.
    """
    return os.path.exists(os.path.join(
        model_directory,
        "Scenarios",
        "Default",
        "TablesOut",
        "SWATOutput.mdb"
    ))


def check_for_hru_id_field(model_directory: str) -> bool:
    """
    Checks for the HRU_ID field in hru1 shapefile.

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if HRU_ID field found, False otherwise.
    """
    hru1_shp = os.path.join(model_directory, "Watershed", "Shapes", "hru1.shp")
    sf = fiona.open(hru1_shp, "r")
    fields = list(sf[1]["properties"])

    for field in fields:
        if field.lower() == "hru_id":
            return True

    sf.close()

    return False


def check_for_objectid_field(model_directory: str) -> bool:
    """
    Checks for the OBJECTID field in hru1 shapefile.

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if OBJECTID field found, False otherwise.
    """
    hru1_shp = os.path.join(model_directory, "Watershed", "Shapes", "hru1.shp")
    sf = fiona.open(hru1_shp, "r")
    fields = list(sf[1]["properties"])

    for field in fields:
        if field.lower() == "objectid":
            return True

    sf.close()

    return False


def check_for_matching_number_of_hrus_in_hru1_and_txtinout(model_directory: str) -> bool:
    """
    Checks if the number of unique hrus in the hru1 shapefile matches
    the number of .hru files in the TxtInOut directory. Any .hru files 
    that do not have an integer as a filename are excluded from the count
    (e.g. output.hru, outputb.hru, etc.).

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.

    Returns
    -------
    bool
        True if number of hrus in hru1 are less than or equal to number of .hru files, False otherwise.
    """
    hru1_shp = os.path.join(model_directory, "Watershed", "Shapes", "hru1.shp")
    hru_dir = os.path.join(model_directory, "Scenarios", "Default", "TxtInOut")

    hru_files = glob.glob(os.path.join(hru_dir, "*.hru"))

    # Only count hru files that have integers as filenames
    number_of_hru_files = 0
    for hru in hru_files:
        try:
            int(os.path.splitext(os.path.basename(hru))[0])
            number_of_hru_files += 1
        except ValueError:
            pass

    sf = fiona.open(hru1_shp, "r")
    number_of_hrus_in_hru1 = len(sf)

    sf.close()

    return number_of_hru_files == number_of_hrus_in_hru1


def get_error_message(error: str, model_directory: str = None) -> str:
    """
    Returns detailed error message for the provided error name.

    Parameters
    ----------
    model_directory: str
        Current working directory for the SWAT model.
    error: str
        Name of error.

    Returns
    -------
    str
        Error message.
    """
    return {
        "folders": f"Could not find \"Scenarios\" and \"Watershed\" directories in zip file. See manual for further help.",
        "raster": f"Could not find hrus1/w001001.adf in {model_directory}/Watershed/Grid/. See manual for further help.",
        "shapefile": f"Could not find hru1.shp in {model_directory}/Watershed/Shapes/. See manual for further help.",
        "hrus": f"Could not find hru files (.hru) in {model_directory}/Scenarios/Default/TxtInOut/. See manual for further help.",
        "swatmdb": f"Could not find SWATOutput.mdb in {model_directory}/Scenarios/Default/TablesOut/. See manual for further help.",
        "hru_id": f"Could not find field named HRU_ID in {model_directory}/Watershed/Shapes/hru1.shp.",
        "objectid": f"Could not find field named OBJECTID in {model_directory}/Watershed/Shapes/hru1.shp.",
        "matching_hrus": f"Number of hrus in {model_directory}/Watershed/Shapes/hru1.shp do not match the number of .hru files in {model_directory}/Scenarios/Default/TxtInOut."
    }.get(error, "")
