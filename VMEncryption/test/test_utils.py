import mock
import unittest


class MockDistroPatcher:
    def __init__(self, name, version, kernel):
        self.distro_info = [None] * 2
        self.distro_info[0] = name
        self.distro_info[1] = version
        self.kernel_version = kernel


def mock_dir_structure(artificial_dir_structure, isdir_mock, listdir_mock, exists_mock):
    """
    Takes in an artificial directory structure dict and adds side_effects to mocks which are hooked to that directory
    example:
        artificial_dir_structure = {
            "/dev/disk/azure": ["root", "root-part1", "root-part2", "scsi1"],
            os.path.join("/dev/disk/azure", "scsi1"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1"]
            }

    any string that has an entry in this dict is mocked as a directory. So, /dev/disk/azure and /dev/disk/azure/scsi1 are dicts.
    Everything else that is implied to exist is a file (e.g. /dev/disk/azure/root, /dev/disk/azure/root-part1, etc)

    For an example look at test_disk_util.test_get_controller_and_lun_numbers method
    NOTE: this method just modifies supplied mocks, it doesn't return anything.
    """
    def mock_isdir(string):
        return string in artificial_dir_structure
    isdir_mock.side_effect = mock_isdir

    def mock_listdir(string):
        dir_content = artificial_dir_structure[string]
        return dir_content
    listdir_mock.side_effect = mock_listdir

    def mock_exists(string):
        if string in artificial_dir_structure:
            return True

        for dir in artificial_dir_structure:
            listing = artificial_dir_structure[dir]
            for entry in listing:
                entry_full_path = os.path.join(dir, entry)
                if string == entry_full_path:
                    return True

        return string in artificial_dir_structure
    exists_mock.side_effect = mock_exists

