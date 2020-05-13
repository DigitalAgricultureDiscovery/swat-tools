import os
import shutil
import unittest

from django.core.files.uploadedfile import UploadedFile

from common.SWATModelZip import NotAZipError
from common.SWATModelZip import SWATModelZip


class TestSWATModelZip(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = "./tests/data/tmp"
        self.workspace = os.path.join(
            os.getcwd(), "tests", "data", "tmp", "email", "taskid")
        self.swat_model_zip = "./tests/data/SWAT_Model.zip"
        self.swat_model_missing_reqs_zip = "./tests/data/SWAT_Model_Missing_Reqs.zip"
        self.swat_model_wrong_ext = "./tests/data/SWAT_Model.tar.gz"
        self.swat_model_missing_root = "./tests/data/SWAT_Model_No_Root_Folder.zip"
        self.swat_model_missing_swat_folders = "./tests/data/SWAT_Model_Missing_SWAT_Folders.zip"
        self.swat_model_missing_swatoutput_database = "./tests/data/SWAT_Model_Missing_SWATOutput_database.zip"
        self.swat_model_missing_hru_id_field = "./tests/data/SWAT_Model_Missing_HRU_ID_Field.zip"
        self.swat_model_missing_objectid_field = "./tests/data/SWAT_Model_Missing_OBJECTID_Field.zip"
        self.swat_model_mismatching_hrus = "./tests/data/SWAT_Model_Mismatching_HRUs.zip"

        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)

        os.makedirs(os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_zip,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_reqs_zip,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_wrong_ext,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_root,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_swat_folders,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_swatoutput_database,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_hru_id_field,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_missing_objectid_field,
                    os.path.join(self.workspace, "input"))
        shutil.copy(self.swat_model_mismatching_hrus,
                    os.path.join(self.workspace, "input"))

    def tearDown(self):
        """
        Remove SWAT Model directory if the zip was extracted.
        """
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_missing_keys(self):
        """
        Test that missing keys in the upload dictionary are detected.
        """
        # Missing "workspace" key
        upload = {
            "local": UploadedFile(name="test_file.zip"),
            "aws": {}
        }

        with self.assertRaises(KeyError):
            SWATModelZip(upload)

    def test_file_does_not_exist(self):
        """
        Test that the uploaded file exists.
        """
        # "workspace" key points to file that does not exist
        upload = {
            "workspace": os.path.join(self.workspace),
            "local": UploadedFile(name="SWAT_Model_Does_Not_Exist.zip"),
            "aws": {}
        }

        with self.assertRaises(FileNotFoundError):
            SWATModelZip(upload)

    def test_file_is_not_a_zip(self):
        """
        Test that the uploaded file has the .zip extension.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model.tar.gz"),
            "aws": {}
        }

        with self.assertRaises(NotAZipError):
            SWATModelZip(upload)

    def test_validate_model_returns_status_code_0_when_no_errors_detected(self):
        """
        Test validate_model returns a 0 status code when no errors are detected.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 0)

    def test_validate_model_returns_status_code_1_when_errors_detected(self):
        """
        Test validate_model returns a 1 status code when errors are found.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Missing_Reqs.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertFalse(model.errors["raster"])
        self.assertFalse(model.errors["shapefile"])
        self.assertFalse(model.errors["hrus"])

    def test_handles_missing_root_folder(self):
        """
        Test that a missing root folder does not cause an error
        as long as the Watershed and Scenarios folders are found.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_No_Root_Folder.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 0)
        self.assertTrue(os.path.exists(model.swat_model_directory))

    def test_validate_model_returns_folders_error_when_required_swat_folders_missing(self):
        """
        Test that the "folders" error is returned by validate_model when the
        "Watershed" and/or "Scenarios" folders are missing.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Missing_SWAT_Folders.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertFalse(model.errors["folders"])

    def test_validate_model_detects_missing_swatoutput_database(self):
        """
        Test that validate model checks for SWATOutput.mdb and toggles
        the appropriate error flag if it is not found.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Missing_SWATOutput_database.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload, "field")
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertFalse(model.errors["swatmdb"])

    def test_missing_hru_id_field_detected(self):
        """
        Test that the appropriate error is thrown when the
        hru1 shapefile is missing a field named "HRU_ID".
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Missing_HRU_ID_Field.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertFalse(model.errors["hru_id"])

    def test_missing_objectid_field_detected(self):
        """
        Test that the appropriate error is thrown when the
        hru1 shapefile is missing a field named "OBJECTID".
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Missing_OBJECTID_Field.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertFalse(model.errors["objectid"])

    def test_that_number_of_hrus_in_hru1_match_hru_files(self):
        """
        Test that the number of unique hrus in the hru1 shapefile
        match the number of .hru files in the TxtInOut directory.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 0)
        self.assertEqual(len(validation_results["errors"]), 0)
        self.assertTrue(model.errors["matching_hrus"])

    def test_validate_model_detects_mismatching_number_of_hrus_in_hru1_and_txtinout(self):
        """
        Test that the correct errors is thrown when the number of hrus in
        hru1 shapefile and the number .hru files in the TxtInOut directory
        do not match.
        """
        upload = {
            "workspace": self.workspace,
            "local": UploadedFile(name="SWAT_Model_Mismatching_HRUs.zip"),
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertEqual(len(validation_results["errors"]), 1)
        self.assertFalse(model.errors["matching_hrus"])
