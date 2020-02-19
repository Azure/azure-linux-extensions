import unittest
import os
import main.BuildVersion

class TestBuildVersion(unittest.TestCase):
    def test_build_version_from_file(self):
        build_version = main.BuildVersion.get_build_version_from_file()
        expected_build_version = self.__get_expected_build_version_from_file()
        self.assertEquals(expected_build_version, build_version)

    def __get_expected_build_version_from_file(self):
        # note, version.txt file is expected to be in the same folder as BuildVersion module.
        version_file_path = os.path.join(os.path.dirname(main.BuildVersion.__file__), 'version.txt')
        with open(version_file_path) as text_file:
            return text_file.read()        
