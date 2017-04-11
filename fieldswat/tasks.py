from __future__ import absolute_import
from celery import shared_task
from .process import FieldSWATProcess


@shared_task
def process_task(data):
    """
    Master method responsible for calling the methods required
    to complete the luu and fractional area files creation.

    Parameters
    ----------
    data: dictionary
        Contains file and directory paths for inputs

    Returns
    -------
    none
    """
    process = FieldSWATProcess(data)

    process.start()
    process.copy_results_to_depot()
    process.clean_up_input_data()
    process.email_user_link_to_results()
    process.update_task_status_in_database()
