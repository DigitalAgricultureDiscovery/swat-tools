import os
import shutil
import unittest

from django.core.files.uploadedfile import UploadedFile

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
        # Missing "workspace" key
        uploaded_file = UploadedFile
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
