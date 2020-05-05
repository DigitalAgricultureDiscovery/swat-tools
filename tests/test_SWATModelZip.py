import os
import shutil
import unittest

from common.SWATModelZip import NotAZipError
from common.SWATModelZip import SWATModelZip


class TestSWATModelZip(unittest.TestCase):
    def setUp(self):
        self.swat_model_zip = "./tests/data/SWAT_Model.zip"

    def tearDown(self):
        """
        Remove SWAT Model directory if the zip was extracted.
        """
        if os.path.exists(os.path.splitext(self.swat_model_zip)[0]):
            shutil.rmtree(os.path.splitext(self.swat_model_zip)[0])

    def test_missing_keys(self):
        """
        Test that missing keys in the upload dictionary are detected.
        """
        # Missing "cwd" key
        upload = {
            "filename": "test_file.zip",
            "on_s3": {}
        }

        with self.assertRaises(KeyError):
            SWATModelZip(upload)

    def test_file_does_not_exist(self):
        """
        Test that the uploaded file exists.
        """
        # "cwd" key points to file that does not exist
        upload = {
            "cwd": "./wrong_directory",
            "filename": "SWAT_Model.zip",
            "on_s3": {}
        }

        with self.assertRaises(FileNotFoundError):
            SWATModelZip(upload)

    def test_file_is_not_a_zip(self):
        """
        Test that the uploaded file has the .zip extension.
        """
        upload = {
            "cwd": "./tests/data",
            "filename": "SWAT_Model.tar.gz",
            "on_s3": {}
        }

        with self.assertRaises(NotAZipError):
            SWATModelZip(upload)
