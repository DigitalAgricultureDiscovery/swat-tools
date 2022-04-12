from tkFileDialog import askdirectory, askopenfilename
from tkMessageBox import showwarning
from subprocess import check_call
import glob
import os
import shutil
import Tkinter


def get_realization_filepaths(cwd):
    """
    Check current working directory for realization .dat files using glob. Exclude
    the lup.dat file from the results.

    Parameters
    ----------
    cwd: string
        Current working directory

    Returns
    -------
    realization_files: list
        List of the filepaths to the realization files
    """

    # get realization files filepaths (*.dat - be sure to exclude lup.dat)
    realization_files = []
    for dat_file in glob.glob(os.path.join(cwd, '*.dat')):
        if os.path.basename(dat_file) != 'lup.dat':
            realization_files.append(dat_file)

    return realization_files


def run_swatexe_with_realizations(cwd, realization_files, swatexe_filepath):
    """
    Loop through each realization file, rename it to file1.dat, and
    run the swatexe. After it finishes rename the realization from
    file1.dat to something more meaningful and copy it along with
    the output results to a new directory.

    Parameters
    ----------
    cwd: string
        Directory path to the current working directory

    realization_files: list of strings
        List of filepaths to the realization files

    swatexe_filepath: string
        Filepath to the swat exe

    Returns
    -------
    None
    """

    # get the swat exe directory
    swatexe_dir = os.path.dirname(swatexe_filepath)

    # loop through each realization file
    for realization in realization_files:

        # rename to file1.dat and copy to swatexe directory
        shutil.copy(realization, os.path.join(swatexe_dir, 'file1.dat'))

        # temporarily change working directory to swat exe directory
        os.chdir(swatexe_dir)

        # run the swatexe
        call_status = check_call([os.path.basename(swatexe_filepath)])

        # switch back to original working directory
        os.chdir(cwd)

        # if call successful
        if call_status is 0:

            # create new directory for file1.dat and output files
            output_directory = os.path.join(cwd, os.path.splitext(realization)[0])

            # check if it already exists, if so remove it
            if os.path.exists(output_directory):
                shutil.rmtree(output_directory)

            # create the new directory
            os.makedirs(output_directory)

            # copy realization .dat file to the new directory
            shutil.copy(realization, output_directory)

            # copy output files to new directory
            shutil.copy(os.path.join(swatexe_dir, 'output.std'), output_directory)
            shutil.copy(os.path.join(swatexe_dir, 'output.rch'), output_directory)
            shutil.copy(os.path.join(swatexe_dir, 'output.sub'), output_directory)
            shutil.copy(os.path.join(swatexe_dir, 'output.hru'), output_directory)


def main():
    """
    Directs workflow for copying realization files to the directory
    containing the SWAT executable, processing the realization files
    (sequentially) and putting the output results in a new directory.

    Returns
    -------
    None
    """

    # for later drawing dialog that asks for the SWAT exe directory
    root = Tkinter.Tk()
    root.withdraw()

    # go back one directory and set it as the current working
    # directory (should be output's root directory)
    os.chdir('..')
    cwd = os.getcwd()

    # get realization files
    realization_files = get_realization_filepaths(cwd)

    # check if realization files were found
    if not realization_files:

        # warn user about missing files
        showwarning(
            'Can\'t find',
            'Unable to locate realization files. Please select the directory containing ' +
            'your LUU Uncertainty output. The output directory should have the realization ' +
            '.dat files inside it.'
        )

        # ask user to select folder containing their LUU Uncertainty output (realization .dat files)
        dialog_title = 'Please select the folder containing your realization .dat files'
        cwd = askdirectory(
            initialdir=cwd,
            parent=root,
            title=dialog_title,
            mustexist=True,
        )

        # get realization files from selected folder
        realization_files = get_realization_filepaths(cwd)

        # check if we were able to find the files
        if not realization_files:
            # warn user that we still cannot locate the files and terminate program
            showwarning(
                'Can\'t find',
                'Still unable to locate realization files. Please make sure you have ' +
                'downloaded and extracted your LUU Uncertainty results. This program ' +
                'will now close.'
            )
            return

    # ask user for path to Swat2009.exe in their Scenarios/Default/TxtInOut folder
    dialog_title = 'Choose the SWAT executable from your Scenarios/Default/TxtInOut folder'
    swatexe_filepath = askopenfilename(
        filetypes=[('SWAT executable file', '*.exe')],
        initialdir=cwd,
        parent=root,
        title=dialog_title)

    # copy lup.dat to the swat exe directory
    shutil.copy(os.path.join(cwd, 'lup.dat'), os.path.dirname(swatexe_filepath))

    # copy each realization to the swatexe_dir and run the swatexe
    run_swatexe_with_realizations(cwd, realization_files, swatexe_filepath)


if __name__ == '__main__':
    main()
