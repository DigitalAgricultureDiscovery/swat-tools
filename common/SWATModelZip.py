import glob
import os
import shutil
import subprocess

from django.core.files.uploadedfile import UploadedFile

from .utils import create_working_directory, fix_file_permissions

"""
upload = {
    "workspace": "/path/to/upload/input",
    "local": {file: file}
    "aws": {"url": "http://"}
}
"""
UPLOAD_KEYS = ["workspace", "local", "aws"]


class NotAZipError(Exception):
    pass


class SWATModelZip:

    def __init__(self, upload: dict) -> None:
        self.errors = {
            "folders": False,    # model directory containing "Scenarios" and "Watershed"
            "raster": False,     # hrus1 raster grid
            "shapefile": False,  # hru1 shapefile
            "hrus": False        # hru files in TxtInOut
        }
        self.swat_model_directory = ""

        check_upload_keys(upload)

        # Root workspace for input and output files
        workspace = upload["workspace"]
        # Sub workspace for input files
        workspace_input = os.path.join(workspace, "input")

        if upload["local"]:
            self.filename = upload["local"].name
        else:
            self.filename = upload["aws"]["file"]["name"]

        create_working_directory(upload["workspace"])

        if not os.environ.get("TEST_FLAG"):
            remove_existing_upload(workspace_input, self.filename)

        if not os.environ.get("TEST_FLAG"):
            if upload["local"]:
                write_file_to_disk(workspace_input, upload["local"])
            else:
                download_file_to_server(
                    workspace_input, upload["on_s3"]["url"])

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


def download_file_to_server(workspace: str, url: str) -> None:
    """
    Downloads uploaded zip file from a remote server.

    Parameters
    ----------
    workspace: str
        Current working directory for task.
    url: str
        URL for the uploaded zip file.

    Returns
    -------
    None
    """
    subprocess.call(["curl", "-o", workspace, url])


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
    if not os.path.splitext(filepath)[1] == '.zip':
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
    subprocess.call(["unzip", "-qq", "-o", filepath, "-d", workspace])

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
        'Watershed',
        'Grid',
        'hrus1',
        'w001001.adf'))


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
        'Watershed',
        'Shapes',
        'hru1.shp'
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
        'Scenarios',
        'Default',
        'TxtInOut',
        '*.hru'
    ))) > 0


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
        "hrus": f"Could not find hru files (.hru) in {model_directory}/Scenarios/Default/TxtInOut/. See manual for further help."
    }.get(error, "")
