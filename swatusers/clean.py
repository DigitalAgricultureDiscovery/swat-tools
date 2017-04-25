import datetime
import os
import shutil
from django.utils import timezone

from .models import UserTask
from swatusers.mytools.mylogger import MyLogger


def remove_expired_process_folders(proj_path, email_addr, task_id, log=""):
    """ Removes directory for an expired process from the user_data folder. """
    errors = False

    task_path = "{0}/{1}/{2}".format(
        proj_path + "/user_data/",
        email_addr,
        task_id)

    try:
        if os.path.exists(task_path):
            shutil.rmtree(task_path)
            if log:
                log.logger.info("Removed process folder from user_data.")
    except:
        errors = True
        if log:
            log.logger.info("Unable to remove record {0}/{1}.".format(
                email_addr,
                task_id))

    return errors


def remove_unfinished_process_folders(path, log=""):
    """ Removes unfinished processes (ones not found in database). """
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            if log:
                log.logger.info("Removed unfinished process.")
    except:
        if log:
            log.logger.info("Unable to remove unfinished process " + path + ".")


def archive_log(proj_path):
    """ If this is the first entry for the month, back up the previous
        log and create a fresh copy for the current month. """
    # Backup log
    try:
        current_datetime = datetime.datetime.now()
        if current_datetime.day == 1 and current_datetime.hour == 0:
            past_month = datetime.datetime.now() - datetime.timedelta(days=5)
            shutil.copy(
                proj_path + "swatapps/log/cron/clean.log",
                proj_path + "swatapps/log/cron/clean." + str(past_month.month) + "." + str(past_month.year) + ".log")
            # Create empty copy of clean.log
            os.remove(proj_path + "swatapps/log/cron/clean.log")
            open(proj_path + "swatapps/log/cron/clean.log", "w").close()
    except:
        return False
    return True


def clean_up_user_data():
    """ 
    Finds expired processes and removes their 
    folders and database records. 
    """

    # Paths to user data
    tmp_path = "/tmp/"
    proj_path = "/depot/saraswat/web/swatapps/"

    # Start logger
    archive_status = archive_log(proj_path)

    log = MyLogger(logpath=proj_path + "swatapps/log/cron/clean.log")

    if not archive_status:
        log.logger.info("Error while trying to create archive log.")

    # Remove 48 hour old processes
    log.logger.info("Checking for tasks over 48 hours old.")

    # Find records older than 48 hours old
    expired_objs = UserTask.objects.filter(
        time_completed__lte=timezone.now() - timezone.timedelta(days=2))

    if expired_objs:
        for obj in expired_objs:
            email_addr = obj["email"]
            task_id = obj["taskid"]
            remove_expired_process_folders(proj_path, email_addr, task_id, log)
            obj.delete()

    # Get user directories in tmp folder
    try:
        root_user_directories = next(os.walk(tmp_path + 'user_data'))[1]

        # Loop through task folders in each user directory
        for user in root_user_directories:
            # Get task directories
            user_tasks = next(os.walk(tmp_path + 'user_data/' + user))[1]
            # Loop through each task in the user directory
            for task in user_tasks:
                # Check if task id matches record in the database
                # and if it is over 48 hours old
                obj = UserTask.objects.filter(task_id=task)

                if not obj:
                    # Check if task is older than 48 hours
                    last_modified = os.stat(tmp_path + 'user_data/' + user + '/' + task).st_mtime
                    task_last_modified_time = timezone.datetime.fromtimestamp(last_modified)
                    server_current_time = timezone.datetime.now()
                    time_diff = server_current_time - task_last_modified_time

                    # If the folder has not been modified in over 48 hours
                    if divmod(time_diff.days * 86400 + time_diff.seconds, 60)[0] / (60*24*2) > 1:
                        remove_unfinished_process_folders(tmp_path + 'user_data/' + user + '/' + task, log)
    except:
        log.logger.info("Unable to remove expired /tmp/user_data.")
        return
