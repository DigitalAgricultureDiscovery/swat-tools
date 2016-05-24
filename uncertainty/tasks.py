from __future__ import absolute_import

from swatapps.celery import app
from uncertainty.process import UncertaintyProcess


@app.task
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
    process = UncertaintyProcess(data)
    
    process.start()
    process.copy_results_to_depot()
    process.clean_up_input_data()
    process.email_user_link_to_results()
    process.update_task_status_in_database()
