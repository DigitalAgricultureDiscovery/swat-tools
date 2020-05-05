import glob
import os
import shutil
import subprocess
from django.core.files.uploadedfile import UploadedFile

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
        check_upload_keys(upload)

        workspace = upload["workspace"]

        if upload["local"]:
            self.filename = upload["local"]["file"].name
        else:
            self.filename = upload["aws"]["file"]["name"]

        self.model_directory = os.path.join(
            upload["workspace"],
            os.path.splitext(self.filename)[0])

        if not os.environ.get("TEST_FLAG"):
            remove_existing_upload(workspace, self.filename)

        if not os.environ.get("TEST_FLAG"):
            if upload.local:
                write_file_to_disk(workspace, upload["local"]["file"])
            else:
                download_file_to_server(workspace, upload["on_s3"]["url"])

        check_if_file_exists(os.path.join(workspace, self.filename))
        check_if_file_is_zip(os.path.join(workspace, self.filename))

        unzip_file(workspace, self.filename)

        self.errors = {
            "raster": False,     # hrus1 raster grid
            "shapefile": False,  # hru1 shapefile
            "hrus": False        # hru files in TxtInOut
        }

        self.errors["raster"] = check_for_hrus1_raster(
            self.model_directory)
        self.errors["shapefile"] = check_for_hru1_shp(
            self.model_directory)
        self.errors["hrus"] = check_for_hrus(self.model_directory)

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
                    get_error_message(self.model_directory, key))

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


def get_error_message(model_directory: str, error: str) -> str:
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
        "raster": f"Could not find hrus1/w001001.adf in {model_directory}/Watershed/Grid/. See manual for further help.",
        "shapefile": f"Could not find hru1.shp in {model_directory}/Watershed/Shapes/. See manual for further help.",
        "hrus": f"Could not find hru files (.hru) in {model_directory}/Scenarios/Default/TxtInOut/. See manual for further help."
    }.get(error, "")
