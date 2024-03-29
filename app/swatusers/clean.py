import os
import shutil

from django.conf import settings
from django.utils import timezone

from swatusers.models import UserTask


def remove_expired_process_folders(proj_path, email_addr, task_id, logger):
    """
    Removes expired user data (>48 hours) from user data location. Provided
    path for directory to be removed, verifies location exists, and walks
    through the directory removing all files.
    
    Parameters
    ----------
    proj_path (str): Path to project on server.
    email_addr (str): Email address of expired data's owner.
    task_id (str): Unique task id for task to be removed.

    Returns
    -------
    None
    """

    # Construct full path to expired task in user data dir
    task_path = os.path.join(settings.USER_UPLOAD_DIR, email_addr, task_id)

    try:
        # Verify directory exists
        if os.path.exists(task_path):
            # Recursively remove directory
            shutil.rmtree(task_path)
            logger.info("Removed process folder from user_data.")
    except:
        logger.info("Unable to remove record {0}/{1}.".format(
            email_addr,
            task_id))


def remove_unfinished_process_folders(path, logger):
    """
    Verify path exists in tmp user data directory and, if so, remove it.
    
    Parameters
    ----------
    path (str): Path to directory that needs to be removed.

    Returns
    -------
    None
    """

    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.info("Removed unfinished process.")
    except:
        logger.warning("Unable to remove unfinished process " + path + ".")


def clean_up_user_data(logger, expired_objs):
    """
    Responsible for calls to methods that will remove temporary older than 12
    hours and processed user data that is older than 48 hours. Also removes
    records of expired tasks from the database.
    
    Returns
    -------
    None
    """

    logger.info("Checking for tasks over 48 hours old.")

    # Paths to temp and processed user data
    tmp_path = settings.USER_UPLOAD_DIR
    proj_path = settings.PROJECT_DIR

    # If any expired records were found
    if expired_objs:
        # Loop through expired objects
        for obj in expired_objs:
            # Call method that deletes expired tasks' directories
            remove_expired_process_folders(
                proj_path,
                obj[0],
                obj[1],
                logger)
    else:
        logger.info("No expired objects found.")

    try:
        logger.info("Cleaning up temp directory.")
        # Get user directories in tmp folder
        root_user_directories = next(os.walk(tmp_path))[1]

        # Loop through task folders in each user directory
        for user in root_user_directories:
            # Get task directories
            user_tasks = next(os.walk(os.path.join(tmp_path, user)))[1]
            logger.info("{0} tasks found in temp directory.".format(
                len(user_tasks)))

            # Loop through each task in the user directory
            for task in user_tasks:
                # Check if task id matches record in the database
                # and if it is over 12 hours old
                obj = UserTask.objects.filter(task_id=task)

                if not obj:
                    # Check if task is older than 12 hours
                    task_path = os.path.join(tmp_path, user, task)
                    last_modified = os.stat(task_path).st_mtime
                    task_last_modified_time = timezone.datetime.fromtimestamp(last_modified)
                    server_current_time = timezone.datetime.now()
                    time_diff = server_current_time - task_last_modified_time

                    # If the folder has not been modified in over 12 (60 * 12) hours
                    if divmod(time_diff.days * 86400 + time_diff.seconds, 60)[0] / (60*12) > 1:
                        logger.info("Removing {0}.".format(task))
                        remove_unfinished_process_folders(task_path, logger)
    except:
        logger.warning("Unable to remove expired /tmp/user_data.")
        return

    logger.info("Finished cleaning up user data.")
