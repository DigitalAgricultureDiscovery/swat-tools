import os

from django.conf import settings
import fiona


def create_working_directory(workspace: str) -> None:
    """ Creates the directory structure that all inputs/outputs will be
        placed for this current process. """
    if os.environ.get("TEST_FLAG"):
        upload_dir = "./tests/data/tmp"
    else:
        upload_dir = settings.USER_UPLOAD_DIR

    # Create main directory for storing user data if it does not exist
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        os.chmod(upload_dir, 0o775)

    # Construct data directory for specific user (email) if it does not exist
    email = workspace.split(os.path.sep)[-2]
    user_directory = os.path.join(upload_dir, email)

    if not os.path.exists(user_directory):
        os.makedirs(user_directory)
        os.chmod(user_directory, 0o775)

    # Set up the working directory for this specific process
    if not os.path.exists(workspace):
        os.makedirs(workspace)
    if not os.path.exists(os.path.join(workspace, "input")):
        os.makedirs(os.path.join(workspace, "input"))

    # Set folder permissions
    fix_file_permissions(workspace)


def fix_file_permissions(path: str) -> None:
    """ Starts at a base directory and moves through all of its
        files changing the directory permissions to 775 and file
        permissions to 664. """

    # Change directory and file permissions for "path"
    # to 775 and 664 respectively
    if os.path.isfile(path):
        os.chmod(path, 0o664)
    else:
        os.chmod(path, 0o775)
        for root, directory, file in os.walk(path):
            for d in directory:
                os.chmod(os.path.join(root, d), 0o775)
            for f in file:
                os.chmod(os.path.join(root, f), 0o664)


def find_objectid_and_hru_id_indexes(shp_path: str) -> dict:
    """
    Checks a shapefile for OBJECTID and HRU_ID fields 
    and returns index position of both fields if found.

    Parameters
    ----------
    shp_path: str
        Path to shapefile.

    Returns
    -------
    dict
        Dictionary containing index position for OBJECTID and HRU_ID.
    """
    sf = fiona.open(shp_path, "r")
    fields = list(sf[1]["properties"])

    fields_lower = [field.lower() for field in fields]

    if "objectid" in fields_lower and "hru_id" in fields_lower:
        return {
            "objectid": fields_lower.index("objectid"),
            "hru_id": fields_lower.index("hru_id")
        }
    else:
        return None
