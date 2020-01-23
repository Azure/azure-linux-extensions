import unittest
import mock

from main.Common import CryptItem
from main.EncryptionEnvironment import EncryptionEnvironment
from main.CryptMountConfigUtil import CryptMountConfigUtil
from console_logger import ConsoleLogger
from test_utils import MockDistroPatcher


class Test_crypt_mount_config_util(unittest.TestCase):
    """ unit tests for functions in the CryptMountConfig module """
    def setUp(self):
        self.logger = ConsoleLogger()
        self.crypt_mount_config_util = CryptMountConfigUtil(self.logger, EncryptionEnvironment(None, self.logger), None)

    def _mock_open_with_read_data_dict(self, open_mock, read_data_dict):
        open_mock.content_dict = read_data_dict

        def _open_side_effect(filename, mode, *args, **kwargs):
            read_data = open_mock.content_dict.get(filename)
            mock_obj = mock.mock_open(read_data=read_data)
            handle = mock_obj.return_value

            def write_handle(data, *args, **kwargs):
                if 'a' in mode:
                    open_mock.content_dict[filename] += data
                else:
                    open_mock.content_dict[filename] = data

            def write_lines_handle(data, *args, **kwargs):
                if 'a' in mode:
                    open_mock.content_dict[filename] += "".join(data)
                else:
                    open_mock.content_dict[filename] = "".join(data)
            handle.write.side_effect = write_handle
            handle.writelines.side_effect = write_lines_handle
            return handle

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

        self.crypt_mount_config_util.disk_util = disk_util_mock
        disk_util_mock.get_encryption_status.return_value = "{\"os\" : \"Encrypted\"}"
        acm_contents = """
        osencrypt /dev/dev_path None / ext4 True 0
        """
        mock.mock_open(open_mock, acm_contents)
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
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
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="osencrypt",
                                                               dev_path="/dev/dev_path",
                                                               mount_point="/",
                                                               file_system="ext4")],
                             crypt_items)

        use_acm_mock.return_value = False  # Now, use the /etc/crypttab file
        exists_mock.return_value = True  # Crypttab file found
        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/osencrypt / ext4 defaults,nofail 0 0",
                                                        "/etc/crypttab": "osencrypt /dev/sda1 /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
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
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
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
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
        self.assertListEqual([],
                             crypt_items)

        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/encrypteddatadisk /mnt/datadisk auto defaults,nofail 0 0",
                                                        "/etc/crypttab": "encrypteddatadisk /dev/disk/azure/scsi1/lun0 /someplainfile luks"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
        self.assertListEqual([],
                             crypt_items)

        self._mock_open_with_read_data_dict(open_mock, {"/etc/fstab": "/dev/mapper/encrypteddatadisk /mnt/datadisk auto defaults,nofail 0 0",
                                                        "/etc/crypttab": "encrypteddatadisk /dev/disk/azure/scsi1/lun0 /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,discard,header=/headerfile"})
        crypt_items = self.crypt_mount_config_util.get_crypt_items()
        self.assertListEqual([self._create_expected_crypt_item(mapper_name="encrypteddatadisk",
                                                               dev_path="/dev/disk/azure/scsi1/lun0",
                                                               file_system="auto",
                                                               luks_header_path="/headerfile",
                                                               mount_point="/mnt/datadisk")],
                             crypt_items)

    @mock.patch('shutil.copy2', return_value=True)
    @mock.patch('os.rename', return_value=True)
    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('__builtin__.open')
    @mock.patch('main.CryptMountConfigUtil.CryptMountConfigUtil.should_use_azure_crypt_mount', return_value=True)
    @mock.patch('main.DiskUtil.DiskUtil', autospec=True)
    @mock.patch('main.CryptMountConfigUtil.CryptMountConfigUtil.add_bek_to_default_cryptdisks', return_value=None)
    def test_migrate_crypt_items(self, bek_to_crypt_mock, disk_util_mock, use_acm_mock, open_mock, exists_mock, rename_mock, shutil_mock):

        def rename_side_effect(name1, name2):
            use_acm_mock.return_value = False
            return True
        rename_mock.side_effect = rename_side_effect
        self.crypt_mount_config_util.disk_util = disk_util_mock
        disk_util_mock.get_encryption_status.return_value = "{\"os\" : \"NotEncrypted\"}"
        disk_util_mock.distro_patcher = MockDistroPatcher('Ubuntu', '14.04', '4.15')
        disk_util_mock.get_azure_data_disk_controller_and_lun_numbers.return_value = [(1, 0)]
        disk_util_mock.get_device_path.return_value = "/dev/mapper/mapper_name"

        # Test 1: migrate an entry (BEK not in fstab)
        open_mock.reset_mock()
        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": "mapper_name /dev/dev_path None /mnt/point ext4 False 0",
                                                        "/etc/fstab": "",
                                                        "/etc/crypttab": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/crypttab_line": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/fstab_line": ""})
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 9)
        self.assertTrue("LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/etc/crypttab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/fstab_line"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/crypttab_line"])

        # Test 2: migrate an entry (BEK in fstab)
        open_mock.reset_mock()
        use_acm_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": "mapper_name /dev/dev_path None /mnt/point ext4 False 0",
                                                        "/etc/fstab": "LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0",
                                                        "/etc/crypttab": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/crypttab_line": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/fstab_line": ""})
        print(open_mock.content_dict["/etc/fstab"])
        print(open_mock.content_dict["/etc/crypttab"])
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 8)
        self.assertTrue("/dev/mapper/mapper_name /mnt/point auto defaults,nofail,discard 0 0" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/etc/crypttab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/fstab_line"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/crypttab_line"])

        # Test 3: migrate no entry
        open_mock.reset_mock()
        use_acm_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": "",
                                                        "/etc/fstab": "LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0",
                                                        "/etc/crypttab": ""})
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 2)
        self.assertTrue("LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0" == open_mock.content_dict["/etc/fstab"].strip())
        self.assertTrue("" == open_mock.content_dict["/etc/crypttab"].strip())

        # Test 4: skip migrating the OS entry
        open_mock.reset_mock()
        use_acm_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": "osencrypt /dev/dev_path None / ext4 False 0",
                                                        "/etc/fstab": "LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0",
                                                        "/etc/crypttab": ""})
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 2)
        self.assertTrue("LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0" == open_mock.content_dict["/etc/fstab"].strip())
        self.assertTrue("" == open_mock.content_dict["/etc/crypttab"].strip())

        # Test 5: migrate many entries
        open_mock.reset_mock()
        use_acm_mock.return_value = True
        acm_contents = """
        mapper_name /dev/dev_path None /mnt/point ext4 False 0
        mapper_name2 /dev/dev_path2 None /mnt/point2 ext4 False 0
        """

        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": acm_contents,
                                                        "/etc/fstab": "",
                                                        "/etc/crypttab": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/crypttab_line": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/fstab_line": "",
                                                        "/mnt/point2/.azure_ade_backup_mount_info/crypttab_line": "",
                                                        "/mnt/point2/.azure_ade_backup_mount_info/fstab_line": ""})
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 15)
        self.assertTrue("/dev/mapper/mapper_name /mnt/point auto defaults,nofail,discard 0 0\n" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("/dev/mapper/mapper_name2 /mnt/point2 auto defaults,nofail,discard 0 0" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("\nmapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0" in open_mock.content_dict["/etc/crypttab"])
        self.assertTrue("\nmapper_name2 /dev/dev_path2 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0" in open_mock.content_dict["/etc/crypttab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point auto defaults,nofail,discard 0 0" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/fstab_line"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/crypttab_line"])
        self.assertTrue("/dev/mapper/mapper_name2 /mnt/point2 auto defaults,nofail,discard 0 0" in open_mock.content_dict["/mnt/point2/.azure_ade_backup_mount_info/fstab_line"])
        self.assertTrue("mapper_name2 /dev/dev_path2 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" in open_mock.content_dict["/mnt/point2/.azure_ade_backup_mount_info/crypttab_line"])

        # Test 6: skip if mapperpath not found
        open_mock.reset_mock()
        use_acm_mock.return_value = True
        disk_util_mock.get_device_path.return_value = None

        open_mock.reset_mock()
        self._mock_open_with_read_data_dict(open_mock, {"/var/lib/azure_disk_encryption_config/azure_crypt_mount": "mapper_name /dev/dev_path None /mnt/point ext4 False 0",
                                                        "/etc/fstab": "",
                                                        "/etc/crypttab": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/crypttab_line": "",
                                                        "/mnt/point/.azure_ade_backup_mount_info/fstab_line": ""})
        self.crypt_mount_config_util.migrate_crypt_items()
        self.assertEqual(open_mock.call_count, 3)
        self.assertTrue("LABEL=BEK\\040VOLUME /mnt/azure_bek_disk auto defaults,discard,nobootwait 0 0" in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point" not in open_mock.content_dict["/etc/fstab"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" not in open_mock.content_dict["/etc/crypttab"])
        self.assertTrue("/dev/mapper/mapper_name /mnt/point" not in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/fstab_line"])
        self.assertTrue("mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail" not in open_mock.content_dict["/mnt/point/.azure_ade_backup_mount_info/crypttab_line"])

