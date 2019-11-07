import unittest
import mock
import os.path
import json

from main.DiskUtil import DiskUtil
from main.EncryptionEnvironment import EncryptionEnvironment
from main.Common import DeviceItem

from console_logger import ConsoleLogger
from test_utils import mock_dir_structure, MockDistroPatcher


class Test_Disk_Util(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.disk_util = DiskUtil(None, MockDistroPatcher('Ubuntu', '14.04', '4.15'), self.logger, EncryptionEnvironment(None, self.logger))

    def _create_device_item(self, name, mount_point=None, file_system=None, device_id="", type=""):
        device_item = DeviceItem()
        device_item.name = name
        device_item.mount_point = mount_point
        device_item.file_system = file_system
        device_item.device_id = device_id
        device_item.type = type
        return device_item

    @mock.patch("os.path.isdir")
    @mock.patch("os.listdir")
    @mock.patch("os.path.exists")
    def test_get_controller_and_lun_numbers(self, exists_mock, listdir_mock, isdir_mock):

        artifical_dir_structure = {
            "/dev/disk/azure": ["root", "root-part1", "root-part2", "scsi1"],
            os.path.join("/dev/disk/azure", "scsi1"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1"]
            }

        mock_dir_structure(artifical_dir_structure, isdir_mock, listdir_mock, exists_mock)

        controller_and_lun_numbers = self.disk_util.get_all_azure_data_disk_controller_and_lun_numbers()
        self.assertListEqual([(1, 0), (1, 1)], controller_and_lun_numbers)

        artifical_dir_structure[os.path.join("/dev/disk/azure", "scsi1")].append("lun2")
        controller_and_lun_numbers = self.disk_util.get_all_azure_data_disk_controller_and_lun_numbers()
        self.assertListEqual([(1, 0), (1, 1), (1, 2)], controller_and_lun_numbers)

        artifical_dir_structure[os.path.join("/dev/disk/azure", "scsi1")].append("random file")
        controller_and_lun_numbers = self.disk_util.get_all_azure_data_disk_controller_and_lun_numbers()
        self.assertListEqual([(1, 0), (1, 1), (1, 2)], controller_and_lun_numbers)

        artifical_dir_structure[os.path.join("/dev/disk/azure", "scsi1")] = []
        controller_and_lun_numbers = self.disk_util.get_all_azure_data_disk_controller_and_lun_numbers()
        self.assertListEqual([], controller_and_lun_numbers)

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("main.DiskUtil.EncryptionMarkConfig.config_file_exists", return_value=False)
    @mock.patch("main.DiskUtil.DecryptionMarkConfig.config_file_exists", return_value=False)
    @mock.patch("main.DiskUtil.DiskUtil.get_azure_devices")
    @mock.patch("main.DiskUtil.DiskUtil.is_os_disk_lvm", return_value=False)
    @mock.patch("main.DiskUtil.DiskUtil.get_mount_items")
    @mock.patch("main.DiskUtil.DiskUtil.get_device_items")
    def test_get_encryption_status(self, get_device_items_mock, get_mount_items_mock, is_os_disk_lvm_mock, get_azure_devices_mock, decryption_mark_config, encryption_mark_config, exists_mock):

        # First test with just a special device
        get_azure_devices_mock.return_value = [self._create_device_item(name="special_azure_device", mount_point="/mnt/sad", file_system="ext4")]
        get_device_items_mock.return_value = [self._create_device_item(name="special_azure_device", mount_point="/mnt/sad", file_system="ext4")]
        get_mount_items_mock.return_value = [{"src": "/dev/special_azure_device", "dest": "/mnt/sad", "fs": "ext4"}]
        status = self.disk_util.get_encryption_status()
        self.assertDictEqual({u"os": u"NotEncrypted", u"data": u"NotMounted"}, json.loads(status))

        # Let's add a data disk not mounted and not encrypted
        get_device_items_mock.return_value.append(self._create_device_item(name="sdd1", mount_point="/mnt/disk1", file_system="ext4"))
        status = self.disk_util.get_encryption_status()
        self.assertDictEqual({u"os": u"NotEncrypted", u"data": u"NotMounted"}, json.loads(status))

        # Let's mount the data disk now but keep it non-encrypted
        get_mount_items_mock.return_value.append({"src": "/dev/sdd1", "dest": "/mnt/disk1", "fs": "ext4"})
        self.assertDictEqual({u"os": u"NotEncrypted", u"data": u"NotEncrypted"}, json.loads(status))

        # Let's make it encrypted now
        get_mount_items_mock.return_value.pop()
        get_mount_items_mock.return_value.append({"src": "/dev/mapper/sdd1-enc", "dest": "/mnt/disk1", "fs": "ext4"})
        get_device_items_mock.return_value.pop()
        get_device_items_mock.return_value.append(self._create_device_item(name="sdd1-enc", mount_point="/mnt/disk1", file_system="ext4", type="crypt"))
        get_device_items_mock.return_value.append(self._create_device_item(name="sdd1", file_system="CRYPTO_LUKS"))
        status = self.disk_util.get_encryption_status()
        self.assertDictEqual({u"os": u"NotEncrypted", u"data": u"Encrypted"}, json.loads(status))

        # Let's add an encrypted OS disk to the outputs
        get_mount_items_mock.return_value.append({"src": "/dev/mapper/osmapper", "dest": "/", "fs": "ext4"})
        get_device_items_mock.return_value.append(self._create_device_item(name="osmapper", mount_point="/", file_system="ext4", type="crypt"))

        status = self.disk_util.get_encryption_status()
        self.assertDictEqual({u"os": u"Encrypted", u"data": u"Encrypted"}, json.loads(status))
