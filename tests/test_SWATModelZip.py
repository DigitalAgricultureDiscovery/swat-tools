import os
import shutil
import unittest

from django.core.files.uploadedfile import UploadedFile

from common.SWATModelZip import NotAZipError
from common.SWATModelZip import SWATModelZip


class TestSWATModelZip(unittest.TestCase):
    def setUp(self):
        self.workspace = "./tests/data/tmp"
        self.swat_model_zip = "./tests/data/SWAT_Model.zip"
        self.swat_model_missing_reqs_zip = "./tests/data/SWAT_Model_Missing_Reqs.zip"

        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)

        os.makedirs(self.workspace)
        shutil.copy(self.swat_model_zip, self.workspace)
        shutil.copy(self.swat_model_missing_reqs_zip, self.workspace)

    def tearDown(self):
        """
        Remove SWAT Model directory if the zip was extracted.
        """
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)

    def test_missing_keys(self):
        """
        Test that missing keys in the upload dictionary are detected.
        """
        # Missing "workspace" key
        upload = {
            "local": {"file": UploadedFile(name="test_file.zip")},
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
            "workspace": "./wrong_directory",
            "local": {"file": UploadedFile(name="SWAT_Model.zip")},
            "aws": {}
        }

        with self.assertRaises(FileNotFoundError):
            SWATModelZip(upload)

    def test_file_is_not_a_zip(self):
        """
        Test that the uploaded file has the .zip extension.
        """
        upload = {
            "workspace": "./tests/data",
            "local": {"file": UploadedFile(name="SWAT_Model.tar.gz")},
            "aws": {}
        }

        with self.assertRaises(NotAZipError):
            SWATModelZip(upload)

    def test_validate_model_returns_status_code_0_when_no_errors_detected(self):
        upload = {
            "workspace": self.workspace,
            "local": {"file": UploadedFile(name="SWAT_Model.zip")},
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 0)

    def test_validate_model_returns_status_code_1_when_errors_detected(self):
        upload = {
            "workspace": self.workspace,
            "local": {"file": UploadedFile(name="SWAT_Model_Missing_Reqs.zip")},
            "aws": {}
        }

        model = SWATModelZip(upload)
        validation_results = model.validate_model()

        self.assertEqual(validation_results["status"], 1)
        self.assertEqual(len(validation_results["errors"]), 3)
