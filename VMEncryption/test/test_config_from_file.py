import unittest
import os
import main.ConfigFromFile

class TestConfigFromFile(unittest.TestCase):
    def test_build_version(self):
        build_version = main.ConfigFromFile.get_build_version()
        expected_build_version = self.__get_expected_config_value_from_file('version.txt')
        self.assertEquals(expected_build_version, build_version)

    def test_extension_name(self):
        extension_name = main.ConfigFromFile.get_extension_name()
        expected_extension_name = self.__get_expected_config_value_from_file('extension_name.txt')
        self.assertEquals(expected_extension_name, extension_name)

    def __get_expected_config_value_from_file(self, file_name):
        # note, the config text file is expected to be in the same folder as ConfigFromFile module.
        config_file_path = os.path.join(os.path.dirname(main.ConfigFromFile.__file__), file_name)
        with open(config_file_path) as text_file:
            return text_file.read()        
