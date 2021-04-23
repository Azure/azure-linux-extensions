import unittest
import os.path
import json

from DiskUtil import DiskUtil
from EncryptionEnvironment import EncryptionEnvironment
from Common import DeviceItem
from Common import CommonVariables
from CommandExecutor import CommandExecutor

from .console_logger import ConsoleLogger
from .test_utils import mock_dir_structure, MockDistroPatcher
try:
    import unittest.mock as mock  # python 3+
except ImportError:
    import mock  # python2


class Test_Disk_Util(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.disk_util = DiskUtil(None, MockDistroPatcher('Ubuntu', '14.04', '4.15'), self.logger, EncryptionEnvironment(None, self.logger))
        try:
            self.assertCountEqual([1],[1])
        except AttributeError:
            self.assertCountEqual = self.assertItemsEqual

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
    def test_get_scsi0_device_names(self, exists_mock, listdir_mock, isdir_mock):
        artifical_dir_structure = {
            "/dev/disk/azure": ["root", "root-part1", "root-part2", "scsi1", "scsi0"],
            os.path.join("/dev/disk/azure", "scsi1"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1"],  # These devices should get ignored for this method
            os.path.join("/dev/disk/azure", "scsi0"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1", "lun2", "lun2-par1"]
            }

        mock_dir_structure(artifical_dir_structure, isdir_mock, listdir_mock, exists_mock)
        scsi0_path = os.path.join("/dev/disk/azure", "scsi0")

        device_names_actual = self.disk_util.get_scsi0_device_names()
        device_names_expected = [
            os.path.join(scsi0_path, "lun0"),
            os.path.join(scsi0_path, "lun1"),
            os.path.join(scsi0_path, "lun2")
        ]
        self.assertListEqual(device_names_expected, device_names_actual)

        artifical_dir_structure[os.path.join("/dev/disk/azure", "scsi0")].append("random file")  # this should not change expected result
        device_names_actual = self.disk_util.get_scsi0_device_names()
        self.assertListEqual(device_names_expected, device_names_actual)

        artifical_dir_structure[os.path.join("/dev/disk/azure", "scsi0")] = []
        device_names_actual = self.disk_util.get_scsi0_device_names()
        self.assertListEqual([], device_names_actual)

    @mock.patch("os.path.isdir")
    @mock.patch("os.listdir")
    @mock.patch("os.path.exists")
    def test_get_azure_symlinks_root_dir_devices(self, exists_mock, listdir_mock, isdir_mock):
        CommonVariables.azure_symlinks_dir
        artifical_dir_structure = {
            CommonVariables.azure_symlinks_dir: ["root", "root-part1", "root-part2", "scsi0"],
            os.path.join(CommonVariables.azure_symlinks_dir, "scsi0"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1", "lun2", "lun2-par1"]
            }

        mock_dir_structure(artifical_dir_structure, isdir_mock, listdir_mock, exists_mock)

        device_names_actual = self.disk_util.get_azure_symlinks_root_dir_devices()
        device_names_expected = [
            os.path.join(CommonVariables.azure_symlinks_dir, "root")
        ]
        self.assertListEqual(device_names_expected, device_names_actual)

        artifical_dir_structure[CommonVariables.azure_symlinks_dir] = ["scsi0"]  # no more stuff in here
        artifical_dir_structure[CommonVariables.cloud_symlinks_dir] = ["azure_root", "azure_root-part1", "azure_resource"]  # move it to the cloud dir
        device_names_actual = self.disk_util.get_azure_symlinks_root_dir_devices()
        device_names_expected = [
            os.path.join(CommonVariables.cloud_symlinks_dir, "azure_root"),
            os.path.join(CommonVariables.cloud_symlinks_dir, "azure_resource")
        ]
        self.assertListEqual(device_names_expected, device_names_actual)

    @mock.patch("os.path.isdir")
    @mock.patch("os.listdir")
    @mock.patch("os.path.exists")
    def test_get_controller_and_lun_numbers(self, exists_mock, listdir_mock, isdir_mock):

        artifical_dir_structure = {
            "/dev/disk/azure": ["root", "root-part1", "root-part2", "scsi1", "scsi0"],
            os.path.join("/dev/disk/azure", "scsi1"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1"],
            os.path.join("/dev/disk/azure", "scsi0"): ["lun0", "lun0-part1", "lun0-part2", "lun1-part1", "lun1"]  # These devices should get ignored for this method
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

    @mock.patch("DiskUtil.DiskUtil.get_device_items")
    @mock.patch("os.path.realpath")
    @mock.patch("DiskUtil.DiskUtil.get_ide_devices")
    @mock.patch("DiskUtil.DiskUtil.get_scsi0_device_names")
    @mock.patch("DiskUtil.DiskUtil.get_azure_symlinks_root_dir_devices")
    def test_get_azure_devices(self, get_symlink_root_devs_mock, get_scsi0_mock, get_ide_mock, realpath_mock, get_device_items_mock):
        realpath_mock.side_effect = lambda x: x
        get_symlink_root_devs_mock.return_value = ["/dev/sda"]
        get_scsi0_mock.return_value = ["/dev/sdb"]
        get_ide_mock.return_value = ["sdc"]

        get_device_items_dict = {
            "/dev/sda": [self._create_device_item(name="sda")],
            "/dev/sdb": [self._create_device_item(name="sdb")],
            "/dev/sdc": [self._create_device_item(name="sdc")],
        }
        get_device_items_mock.side_effect = lambda x: get_device_items_dict[x]

        azure_devices = self.disk_util.get_azure_devices()
        self.assertCountEqual(["sda", "sdb", "sdc"], map(lambda x: x.name, azure_devices))

        # add a partition to sdb
        get_device_items_dict["/dev/sdb"].append(self._create_device_item(name="sdb1"))

        azure_devices = self.disk_util.get_azure_devices()
        self.assertCountEqual(["sda", "sdb", "sdb1", "sdc"], map(lambda x: x.name, azure_devices))

        # change ide device to also be sda
        get_ide_mock.return_value = ["sda"]

        azure_devices = self.disk_util.get_azure_devices()
        # There should only be one SDA, not two
        self.assertCountEqual(["sda", "sdb", "sdb1"], map(lambda x: x.name, azure_devices))

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("DiskUtil.EncryptionMarkConfig.config_file_exists", return_value=False)
    @mock.patch("DiskUtil.DecryptionMarkConfig.config_file_exists", return_value=False)
    @mock.patch("DiskUtil.DiskUtil.get_azure_devices")
    @mock.patch("DiskUtil.DiskUtil.is_os_disk_lvm", return_value=False)
    @mock.patch("DiskUtil.DiskUtil.get_mount_items")
    @mock.patch("DiskUtil.DiskUtil.get_device_items")
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
        status = self.disk_util.get_encryption_status()
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

    @mock.patch("CommandExecutor.CommandExecutor.Execute", return_value=0)
    def test_mount_all(self, cmd_exc_mock):
        self.disk_util.mount_all()
        self.assertEqual(cmd_exc_mock.call_count, 2)

    @mock.patch("DiskUtil.DiskUtil.get_device_items_property")
    def test_is_device_mounted(self, dev_item_prop_mock):
        dev_item_prop_mock.return_value = "/mount"
        device_mounted = self.disk_util.is_device_mounted("deviceName")
        self.assertEqual(device_mounted, True)

        dev_item_prop_mock.reset_mock()
        dev_item_prop_mock.return_value = ""
        device_mounted = self.disk_util.is_device_mounted("deviceName")
        self.assertEqual(device_mounted, False)

        dev_item_prop_mock.reset_mock()
        dev_item_prop_mock.side_effect = Exception("Dummy Exception")
        device_mounted = self.disk_util.is_device_mounted("deviceName")
        self.assertEqual(device_mounted, False)

    @mock.patch("os.path.exists")
    @mock.patch("CommandExecutor.CommandExecutor.Execute", return_value=0)
    def test_make_sure_path_exists(self, cmd_exc_mock, exists_mock):
        exists_mock.return_value = True
        path_exists = self.disk_util.make_sure_path_exists('/test/path')
        self.assertEqual(path_exists, 0)
        self.assertEqual(cmd_exc_mock.call_count, 0)

        cmd_exc_mock.reset_mock()
        exists_mock.return_value = False
        path_exists = self.disk_util.make_sure_path_exists('/test/path')
        self.assertEqual(path_exists, 0)
        self.assertEqual(cmd_exc_mock.call_count, 1)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    def test_luks_dump_keyslots(self, get_luks_header_mock):
        get_luks_header_mock.return_value = """
LUKS header information
Version:        2
Epoch:          46
Metadata area:  16384 [bytes]
Keyslots area:  16744448 [bytes]
UUID:           9d6914e8-769e-4138-8c06-169c249d19d7
Requirements:   online-reencrypt

Keyslots:
  0: luks2
        Key:        512 bits
        Priority:   normal
        Cipher:     aes-xts-plain64
        Cipher key: 512 bits
        PBKDF:      pbkdf2
        Hash:       sha256
        Iterations: 2048000
        Salt:       06 e3 15 36 b2 4b 71 7a ad 0d e3 46 0a 72 c1 6b
                    dc 5c ae ef 91 7c f3 1c ed 7e 96 fd a5 25 5a 42
        AF stripes: 4000
        AF hash:    sha256
        Area offset:32768 [bytes]
        Area length:258048 [bytes]
        Digest ID:  0
  1: reencrypt (unbound)
        Key:        8 bits
        Priority:   ignored
        Mode:       encrypt
        Direction:  forward
        Resilience: checksum
        Hash:       sha256
        Hash data:  512 [bytes]
        Area offset:290816 [bytes]
        Area length:16486400 [bytes]
Tokens:
Digests:
        """
        keyslots = self.disk_util.luks_dump_keyslots("/dev/path", "/path/to/header")
        self.assertEqual(keyslots, [True, True, False])

        get_luks_header_mock.reset_mock()
        # Smaller chunks to make the test more readable
        get_luks_header_mock.return_value = """
LUKS header information
Version:        2
Keyslots:
  1: luks2
        Key:        512 bits
  3: reencrypt (unbound)
        Key:        8 bits
Tokens:
"""
        keyslots = self.disk_util.luks_dump_keyslots("/dev/path", "/path/to/header")
        self.assertEqual(keyslots, [False, True, False, True, False])

    @mock.patch("DiskUtil.DiskUtil._get_cryptsetup_version")
    def test_get_luks_header_size_v202(self, ver_mock):
        # simulate distros with cryptsetup versions earlier than 2.1.0 (eg., Ubuntu 18.04)
        ver_mock.return_value = "cryptsetup 2.0.2"
        header_size = self.disk_util.get_luks_header_size()
        self.assertEqual(header_size, CommonVariables.luks_header_size)

    @mock.patch("DiskUtil.DiskUtil._get_cryptsetup_version")
    def test_get_luks_header_size_v210(self, ver_mock):
        # simulate cryptsetup 2.1.0 (first version of cryptsetup defaulting to LUKS2)
        ver_mock.return_value = "cryptsetup 2.1.0"
        header_size = self.disk_util.get_luks_header_size()
        self.assertEqual(header_size, CommonVariables.luks_header_size_v2)

    @mock.patch("DiskUtil.DiskUtil._get_cryptsetup_version")
    def test_get_luks_header_size_v222(self, ver_mock):
        # versions of distros with cryptsetup later than 2.1.0 (eg., Ubuntu 20.04)
        ver_mock.return_value = "cryptsetup 2.2.2"
        header_size = self.disk_util.get_luks_header_size()
        self.assertEqual(header_size, CommonVariables.luks_header_size_v2)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    def test_get_luks_header_size_luks1(self, lghd_mock):
        lghd_mock.return_value = """
LUKS header information for /dev/sdd

Version:        1
Cipher name:    aes
Cipher mode:    xts-plain64
Hash spec:      sha256
Payload offset: 4096
MK bits:        256
MK digest:      14 99 43 09 07 b0 aa 29 f2 1a dc 91 b2 e9 48 4a f1 0e c9 ff
MK salt:        88 f5 b8 f5 9a 23 8e 66 00 8a 64 5a c0 dc ee a7
                92 47 13 5f ea 13 28 21 4a 63 e6 94 3b 70 be e6
MK iterations:  158490
UUID:           fd29764c-a935-4702-b2d5-4f4ff70438d9

Key Slot 0: ENABLED
        Iterations:             2535854
        Salt:                   30 44 f7 f6 8b f0 80 e9 a4 3f 0e 0d 65 72 a6 af
                                6d 16 56 6e 77 1b 2c 81 75 82 ba 0b 8c 79 13 29
        Key material offset:    8
        AF stripes:             4000
Key Slot 1: DISABLED
Key Slot 2: DISABLED
Key Slot 3: DISABLED
Key Slot 4: DISABLED
Key Slot 5: DISABLED
Key Slot 6: DISABLED
Key Slot 7: DISABLED"""
        header_size = self.disk_util.get_luks_header_size("/mocked/device/path")
        self.assertEqual(header_size, CommonVariables.luks_header_size)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    def test_get_luks_header_size_luks2(self, lghd_mock):
        lghd_mock.return_value = """
LUKS header information
Version:        2
Epoch:          3
Metadata area:  16384 [bytes]
Keyslots area:  16744448 [bytes]
UUID:           580ebe05-308f-4437-a5e4-133e3e6e756b
Label:          (no label)
Subsystem:      (no subsystem)
Flags:          (no flags)

Data segments:
    0: crypt
        offset: 16777216 [bytes]
        length: (whole device)
        cipher: aes-xts-plain64
        sector: 512 [bytes]

Keyslots:
    0: luks2
        Key:        512 bits
        Priority:   normal
        Cipher:     aes-xts-plain64
        Cipher key: 512 bits
        PBKDF:      argon2i
        Time cost:  4
        Memory:     543393
        Threads:    2
        Salt:       9d 5d ba 40 57 8b 41 fc 68 90 7b 5a a6 fa ef 06
                    ae b9 d8 27 01 55 1d d4 32 c9 a0 1e ee a8 81 22
        AF stripes: 4000
        AF hash:    sha256
        Area offset:32768 [bytes]
        Area length:258048 [bytes]
        Digest ID:  0
Tokens:
Digests:
    0: pbkdf2
        Hash:       sha256
        Iterations: 100054
        Salt:       5b 28 b9 bd fc 4d 47 7f e5 a7 d7 b8 a7 dd d5 99
                    4c 3a a5 91 02 52 74 46 48 10 2e 1f 51 25 1a 8f
        Digest:     fc 5d 6f 20 2c 6c 89 7e 79 eb d6 3b 46 19 0f 0a
                5e 62 0d a3 48 77 a2 19 22 56 a9 ad 5a 94 e3 62"""
        header_size = self.disk_util.get_luks_header_size("/mocked/device/path")
        self.assertEqual(header_size, CommonVariables.luks_header_size_v2)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    @mock.patch("DiskUtil.DiskUtil._extract_luks_version_from_dump")
    def test_get_luks_header_size_bad_version(self, ver_mock, dump_mock):
        # log error, return None if LUKS version is outside of supported {1,2}
        ver_mock.return_value = "4"
        dump_mock.return_value = ""
        header_size = self.disk_util.get_luks_header_size("/mocked/device/path")
        self.assertEqual(header_size, None)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    @mock.patch("DiskUtil.DiskUtil._extract_luks_version_from_dump")
    def test_get_luks_header_size_luks1_badoffset(self, ver_mock, dump_mock):
        # log error, return None if LUKS1 offset is not found in header dump
        ver_mock.return_value = "1"
        dump_mock.return_value = ""
        header_size = self.disk_util.get_luks_header_size("/mocked/device/path")
        self.assertEqual(header_size, None)

    @mock.patch("DiskUtil.DiskUtil._luks_get_header_dump")
    @mock.patch("DiskUtil.DiskUtil._extract_luks_version_from_dump")
    def test_get_luks_header_size_luks2_badoffset(self, ver_mock, dump_mock):
        # log error, return None if LUKS2 offset is not found in header dump
        ver_mock.return_value = "2"
        dump_mock.return_value = ""
        header_size = self.disk_util.get_luks_header_size("/mocked/device/path")
        self.assertEqual(header_size, None)
