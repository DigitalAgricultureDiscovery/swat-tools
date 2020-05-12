import os
import shutil
import unittest

from common.utils import find_objectid_and_hru_id_indexes


class TestCommonUtils(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = "./tests/data/tmp"
        self.workspace = os.path.join(
            os.getcwd(), "tests", "data", "tmp", "email", "taskid")
        self.hru1_directory = "./tests/data/hru1"

        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)

        os.makedirs(os.path.join(self.workspace, "input"))
        shutil.copytree(self.hru1_directory,
                        os.path.join(self.workspace, "input", "hru1"))

    def tearDown(self):
        """
        Remove SWAT Model directory if the zip was extracted.
        """
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    def test_correct_index_positions_returned_for_objectid_and_hru_id(self):
        """
        Test that the correct index positions for OBJECTID and HRU_ID 
        are returned from the fields list in hru1.shp.
        """
        hru1_path = os.path.join(self.workspace, "input", "hru1", "hru1.shp")
        hru1_field_positions = find_objectid_and_hru_id_indexes(hru1_path)

        self.assertEqual(hru1_field_positions["objectid"], 0)
        self.assertEqual(hru1_field_positions["hru_id"], 1)
