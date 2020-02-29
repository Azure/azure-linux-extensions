import unittest
import os
import main.Common
import json

class TestCommonVariables(unittest.TestCase):
    
    def test_common_variables(self):
        self.assertEqual(main.Common.CommonVariables.extension_name, "AzureDiskEncryptionForLinux")
        self.assertEqual(main.Common.CommonVariables.extension_version, "1.1.0.47")

