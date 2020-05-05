import os
import shutil
import subprocess

"""
upload = {
    "cwd": "/path/to/upload/input",
    "filename": "name_of_swat_model_zip",
    "on_s3": {"url": "http://"}
}
"""
UPLOAD_KEYS = ["cwd", "filename", "on_s3"]


class NotAZipError(Exception):
    pass


class SWATModelZip:

    def __init__(self, upload: dict) -> None:

        check_upload_keys(upload)

        self.model = f"{upload['cwd']}/{os.path.splitext(upload['filename'][0])}"
        self.valid_model = {
            'raster': False,     # hrus1 raster grid
            'shapefile': False,  # hru1 shapefile
            'hrus': False        # hru files in TxtInOut
        }

        if not os.environ.get("TEST_FLAG"):
            remove_existing_upload(upload["cwd"], upload["filename"])

        if upload["on_s3"]:
            download_file_to_server(upload["cwd"], upload["on_s3"]["url"])

        check_if_file_exists(f"{upload['cwd']}/{upload['filename']}")
        check_if_file_is_zip(f"{upload['cwd']}/{upload['filename']}")

        unzip_file(upload["cwd"], upload["filename"])

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


def remove_existing_upload(cwd: str, filename: str) -> None:
    """ 
    Checks if this file was previously uploaded and extracted. If so,
    the existing directory is removed.

    Parameters
    ----------
    cwd: str
        Current working directory for task.
    filename: str
        Name of uploaded zip file.

    Returns
    -------
    None
    """
    filepath = f"{cwd}/{os.path.splitext(filename)[0]}"

    if os.path.exists(filepath):
        shutil.rmtree(filepath)

    if os.path.exists(f"{cwd}/{filename}"):
        os.remove(f"{cwd}/{filename}")


def download_file_to_server(cwd: str, url: str) -> None:
    """ 
    Downloads uploaded zip file from a remote server.

    Parameters
    ----------
    cwd: str
        Current working directory for task.
    url: str
        URL for the uploaded zip file.

    Returns
    -------
    None
    """
    subprocess.call(["curl", "-o", cwd, url])


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


def unzip_file(cwd: str, filename: str) -> None:
    """
    Unzip uploaded zip file.

    Parameters
    ----------
    cwd: str
        Current working directory for task.
    filename: str
        Name of uploaded zip file.

    Returns
    -------
    None
    """
    filepath = f"{cwd}/{filename}"
    directory = f"{cwd}/{filename[:-4]}"

    subprocess.call(["unzip", "-qq", "-o", filepath, "-d", directory])
