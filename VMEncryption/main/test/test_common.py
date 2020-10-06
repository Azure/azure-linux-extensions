import unittest
import os
import Common
import json

class TestCommonVariables(unittest.TestCase):
    def setUp(self):
        file_path = os.path.join(os.path.dirname(Common.__file__), "common_parameters.json")
        with open(file_path, "r") as content:
            self.expected_common_parameters = json.load(content)
    
    def test_common_variables(self):
        self.assertEqual(Common.CommonVariables.extension_name, self.expected_common_parameters["extension_name"])
        self.assertEqual(Common.CommonVariables.extension_version, self.expected_common_parameters["extension_version"])
