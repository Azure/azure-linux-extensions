import unittest
import mock

from main.Common import CryptItem
from main.EncryptionEnvironment import EncryptionEnvironment
from main.CryptMountConfigUtil import CryptMountConfigUtil
from console_logger import ConsoleLogger


class Test_crypt_mount_config_util(unittest.TestCase):
    """ unit tests for functions in the CryptMountConfig module """
    def setUp(self):
        self.logger = ConsoleLogger()
        self.crypt_mount_config_util = CryptMountConfigUtil(self.logger, EncryptionEnvironment(None, self.logger), None)

    def _mock_open_with_read_data_dict(self, open_mock, read_data_dict):
        def _open_side_effect(filename, mode, *args, **kwargs):
            read_data = read_data_dict.get(filename)
            mock_obj = mock.mock_open(read_data=read_data)
            return mock_obj.return_value

        open_mock.side_effect = _open_side_effect

    def _create_expected_crypt_item(self,
                                    mapper_name=None,
                                    dev_path=None,
                                    uses_cleartext_key=None,
                                    luks_header_path=None,
                                    mount_point=None,
                                    file_system=None,
                                    current_luks_slot=None):
        crypt_item = CryptItem()
        crypt_item.mapper_name = mapper_name
        crypt_item.dev_path = dev_path
        crypt_item.uses_cleartext_key = uses_cleartext_key
        crypt_item.luks_header_path = luks_header_path
        crypt_item.mount_point = mount_point
        crypt_item.file_system = file_system
        crypt_item.current_luks_slot = current_luks_slot
        return crypt_item

    def test_parse_crypttab_line(self):
        # empty line
        line = ""
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(None, crypt_item)

        # line with not enough entries
        line = "mapper_name dev_path"
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(None, crypt_item)

        # commented out line
        line = "# mapper_name dev_path"
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(None, crypt_item)

        # An unfamiliar key_file_path implies that we shouln't be processing this crypttab line
        line = "mapper_name /dev/dev_path /non_managed_key_file_path"
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(None, crypt_item)

        # a bare bones crypttab line
        line = "mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks"
        expected_crypt_item = self._create_expected_crypt_item(mapper_name="mapper_name",
                                                               dev_path="/dev/dev_path")
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(str(expected_crypt_item), str(crypt_item))

        # a line that implies a cleartext key
        line = "mapper_name /dev/dev_path /var/lib/azure_disk_encryption_config/cleartext_key_mapper_name luks"
        expected_crypt_item = self._create_expected_crypt_item(mapper_name="mapper_name",
                                                               dev_path="/dev/dev_path",
                                                               uses_cleartext_key=True)
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(str(expected_crypt_item), str(crypt_item))

        # a line that implies a luks header
        line = "mapper_name /dev/dev_path /var/lib/azure_disk_encryption_config/cleartext_key_mapper_name luks,header=headerfile"
        expected_crypt_item = self._create_expected_crypt_item(mapper_name="mapper_name",
                                                               dev_path="/dev/dev_path",
                                                               uses_cleartext_key=True,
                                                               luks_header_path="headerfile")
        crypt_item = self.crypt_mount_config_util.parse_crypttab_line(line)
        self.assertEquals(str(expected_crypt_item), str(crypt_item))

    @mock.patch('__builtin__.open')
    @mock.patch('os.path.exists', return_value=True)
    def test_should_use_azure_crypt_mount(self, exists_mock, open_mock):
        # if the acm file exists and has only a root disk
        acm_contents = """
        osencrypt /dev/dev_path None / ext4 False 0
        """
        mock.mock_open(open_mock, acm_contents)
        self.assertFalse(self.crypt_mount_config_util.should_use_azure_crypt_mount())

        # if the acm file exists and has a data disk
        acm_contents = """
        mapper_name /dev/dev_path None /mnt/point ext4 False 0
        mapper_name2 /dev/dev_path2 None /mnt/point2 ext4 False 0
        """
        mock.mock_open(open_mock, acm_contents)
        self.assertTrue(self.crypt_mount_config_util.should_use_azure_crypt_mount())

        # empty file
        mock.mock_open(open_mock, "")
        self.assertFalse(self.crypt_mount_config_util.should_use_azure_crypt_mount())

        # no file
        exists_mock.return_value = False
        open_mock.reset_mock()
        self.assertFalse(self.crypt_mount_config_util.should_use_azure_crypt_mount())
        open_mock.assert_not_called()

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('main.CryptMountConfigUtil.ProcessCommunicator')
    @mock.patch('main.CommandExecutor.CommandExecutor', autospec=True)
    @mock.patch('__builtin__.open')
    @mock.patch('main.CryptMountConfigUtil.CryptMountConfigUtil.should_use_azure_crypt_mount')
    @mock.patch('main.DiskUtil.DiskUtil', autospec=True)
    def test_get_crypt_items(self, disk_util_mock, use_acm_mock, open_mock, ce_mock, pc_mock, exists_mock):

        self.crypt_mount_config_util.command_executor = ce_mock

        use_acm_mock.return_value = True  # Use the Azure_Crypt_Mount file

        disk_util_mock.get_encryption_status.return_value = "{\"os\" : \"Encrypted\"}"
        acm_contents = """
        osencrypt /dev/dev_path None / ext4 True 0
        """
        mock.mock_open(open_mock, acm_contents)
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="osencrypt",
                                                               dev_path="/dev/dev_path",
                                                               uses_cleartext_key=True,
                                                               mount_point="/",
                                                               file_system="ext4",
                                                               current_luks_slot=0)],
                             crypt_items)

        ce_mock.ExecuteInBash.return_value = 0  # The grep on cryptsetup succeeds
        pc_mock.return_value.stdout = "osencrypt /dev/dev_path"  # The grep find this line in there
        mock.mock_open(open_mock, "")  # No content in the azure crypt mount file
        disk_util_mock.get_mount_items.return_value = [{"src": "/dev/mapper/osencrypt", "dest": "/", "fs": "ext4"}]
        exists_mock.return_value = False  # No luksheader file found
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="osencrypt",
                                                               dev_path="/dev/dev_path",
                                                               mount_point="/",
                                                               file_system="ext4")],
                             crypt_items)

        use_acm_mock.return_value = False  # Now, use the /etc/crypttab file
        exists_mock.return_value = True  # Crypttab file found
        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/osencrypt / ext4 defaults,nofail 0 0",
                                                        "/etc/crypttab": "osencrypt /dev/sda1 /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="osencrypt",
                                                               dev_path="/dev/sda1",
                                                               file_system="ext4",
                                                               mount_point="/")],
                             crypt_items)

        # if there was no crypttab entry for osencrypt
        exists_mock.side_effect = [True, False]  # Crypttab file found but luksheader not found
        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/osencrypt / ext4 defaults,nofail 0 0", "/etc/crypttab": ""})
        ce_mock.ExecuteInBash.return_value = 0  # The grep on cryptsetup succeeds
        pc_mock.return_value.stdout = "osencrypt /dev/sda1"  # The grep find this line in there
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="osencrypt",
                                                               dev_path="/dev/sda1",
                                                               file_system="ext4",
                                                               mount_point="/")],
                             crypt_items)

        exists_mock.side_effect = None  # Crypttab file found
        exists_mock.return_value = True  # Crypttab file found
        disk_util_mock.get_encryption_status.return_value = "{\"os\" : \"NotEncrypted\"}"
        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "",
                                                        "/etc/crypttab": ""})
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([],
                             crypt_items)

        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/encrypteddatadisk /mnt/datadisk auto defaults,nofail 0 0",
                                                        "/etc/crypttab": "encrypteddatadisk /dev/disk/azure/scsi1/lun0 /someplainfile luks"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([],
                             crypt_items)

        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/encrypteddatadisk /mnt/datadisk auto defaults,nofail 0 0",
                                                        "/etc/crypttab": "encrypteddatadisk /dev/disk/azure/scsi1/lun0 /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard,header=/headerfile"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items(disk_util_mock)
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="encrypteddatadisk",
                                                               dev_path="/dev/disk/azure/scsi1/lun0",
                                                               file_system="auto",
                                                               luks_header_path="/headerfile",
                                                               mount_point="/mnt/datadisk")],
                             crypt_items)
