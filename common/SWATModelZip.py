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

        self.workspace = upload["workspace"]

        if upload["local"]:
            self.filename = upload["local"]["file"].name
        else:
            self.filename = upload["aws"]["file"]["name"]

        self.model_filepath = os.path.join(
            upload["workspace"],
            os.path.splitext(self.filename)[0])

        if not os.environ.get("TEST_FLAG"):
            remove_existing_upload(self.workspace, self.filename)

        if not os.environ.get("TEST_FLAG"):
            if upload.local:
                write_file_to_disk(self.workspace, upload["local"]["file"])
            else:
                download_file_to_server(self.workspace, upload["on_s3"]["url"])

        check_if_file_exists(os.path.join(self.workspace, self.filename))
        check_if_file_is_zip(os.path.join(self.workspace, self.filename))

        unzip_file(self.workspace, self.filename)

        self.valid_model = {
            'raster': False,     # hrus1 raster grid
            'shapefile': False,  # hru1 shapefile
            'hrus': False        # hru files in TxtInOut
        }

    def validate_model(self) -> dict:
        return {
            "status": 0,
            "errors": []
        }


def check_upload_keys(upload: dict) -> None:
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
    directory = os.path.join(workspace, os.path.splitext(filename)[0])

    subprocess.call(["unzip", "-qq", "-o", filepath, "-d", directory])
