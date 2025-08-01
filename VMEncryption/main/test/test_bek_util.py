import unittest
try:
    import unittest.mock as mock  # python 3+
except ImportError:
    import mock  # python2

from BekUtil import BekUtil
from AbstractBekUtilImpl import BekMissingException,AbstractBekUtilImpl
from DiskUtil import DiskUtil
from Common import CommonVariables
from console_logger import ConsoleLogger

class Test_Bek_Util(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()

    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_volume_mounted_and_formatted_expected(self, disk_util_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        disk_util_mock.get_mount_items.return_value = [{"src":"/dev/sdc1", "dest":"/mnt/azure_bek_disk", "fs":"vfat"}]
        bek_expected, fault_reason = bek_util.is_bek_volume_mounted_and_formatted()
        self.assertTrue(bek_expected)

    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_volume_mounted_and_formatted_not_mounted(self, disk_util_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        disk_util_mock.get_mount_items.return_value = [{"src":"/dev/sdc1", "dest":"/nobek", "fs":"vfat"}, {"src":"/dev/sda1", "dest":"/", "fs":"ext4"}]
        bek_expected, fault_reason = bek_util.is_bek_volume_mounted_and_formatted()
        self.assertFalse(bek_expected)
        self.assertEqual(fault_reason, AbstractBekUtilImpl.not_mounted_msg)

    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_volume_mounted_and_formatted_wrong_fs(self, disk_util_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        disk_util_mock.get_mount_items.return_value = [{"src":"/dev/sdc1", "dest":"/mnt/azure_bek_disk", "fs":"wrongFS"}, {"src":"/dev/sda1", "dest":"/", "fs":"ext4"}]
        bek_expected, fault_reason = bek_util.is_bek_volume_mounted_and_formatted()
        self.assertFalse(bek_expected)
        self.assertEqual(fault_reason, AbstractBekUtilImpl.wrong_fs_msg)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_expected_gen1(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [True, True]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertTrue(bek_attached)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_not_attached_gen1(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [False, False]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertFalse(bek_attached)
        self.assertEqual(error_reason, AbstractBekUtilImpl.bek_missing_msg)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_not_partitioned_gen1(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [True, False]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertFalse(bek_attached)
        self.assertEqual(error_reason, AbstractBekUtilImpl.partition_missing_msg)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_expected_gen2(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [False, True, True]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertTrue(bek_attached)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_not_attached_gen2(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [False, False]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertFalse(bek_attached)
        self.assertEqual(error_reason, AbstractBekUtilImpl.bek_missing_msg)

    @mock.patch('os.path.exists')
    @mock.patch('DiskUtil.DiskUtil', autospec=True)
    def test_is_bek_disk_attached_and_partitioned_not_partitioned_gen2(self, disk_util_mock, exists_mock):
        bek_util = BekUtil(disk_util_mock, self.logger)
        exists_mock.side_effect = [False, True, False]
        bek_attached, error_reason = bek_util.is_bek_disk_attached_and_partitioned()
        self.assertFalse(bek_attached)
        self.assertEqual(error_reason, AbstractBekUtilImpl.partition_missing_msg)

    
