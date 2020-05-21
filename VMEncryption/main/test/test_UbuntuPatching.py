import unittest
import mock
import os.path

from patch.UbuntuPatching import UbuntuPatching
from DiskUtil import DiskUtil
from Common import CommonVariables
from CommandExecutor import CommandExecutor
from .console_logger import ConsoleLogger
try:
    builtins_open = "builtins.open"
    import unittest.mock as mock # python3+
except ImportError:
    builtins_open = "__builtin__.open"
    import mock # python2

class Test_UbuntuPatching(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.UbuntuPatching = UbuntuPatching(self.logger, ['Ubuntu', '16.04'])

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

    @mock.patch(builtins_open)
    @mock.patch('os.path.exists')
    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_update_prereq(self, ce_mock, exists_mock, open_mock):
        # Test 1: Only osencrypt entry with /dev/sda1
        crypttab_contents="""osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh"""
        expected_crypttab_contents="""osencrypt /dev/disk/azure/root-part1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh\n"""
        exists_mock.return_value = True
        ce_mock.return_value = True
        self._mock_open_with_read_data_dict(open_mock, {"/etc/crypttab": crypttab_contents})
        self.UbuntuPatching.update_prereq()
        self.assertEquals(open_mock.content_dict["/etc/crypttab"], expected_crypttab_contents)
        self.assertEquals(open_mock.call_count, 2)
        self.assertEquals(ce_mock.call_count, 1)
        self.assertEquals(exists_mock.call_count, 2)

        # Test 2: Other Entries along with osencrypt
        crypttab_contents="mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail\n"\
        "osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh\n"\
        "mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"
        expected_crypttab_contents="mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail\n"\
        "osencrypt /dev/disk/azure/root-part1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh\n"\
        "mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"
        open_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.reset_mock()
        self._mock_open_with_read_data_dict(open_mock, {"/etc/crypttab": crypttab_contents})
        self.UbuntuPatching.update_prereq()
        self.assertEquals(open_mock.call_count, 2)
        self.assertEquals(ce_mock.call_count, 1)
        self.assertEquals(exists_mock.call_count, 2)
        self.assertEquals(expected_crypttab_contents, open_mock.content_dict["/etc/crypttab"])

        # Test 3: osencrypt already with /dev/disk/azure/root-part1
        crypttab_contents="""osencrypt /dev/disk/azure/root-part1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh
        mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail
        mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"""
        expected_crypttab_contents="""osencrypt /dev/disk/azure/root-part1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh
        mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail
        mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"""
        open_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.reset_mock()
        self._mock_open_with_read_data_dict(open_mock, {"/etc/crypttab": crypttab_contents})
        self.UbuntuPatching.update_prereq()
        self.assertEquals(open_mock.call_count, 1)
        self.assertEquals(ce_mock.call_count, 0)
        self.assertEquals(exists_mock.call_count, 1)
        self.assertEquals(expected_crypttab_contents, open_mock.content_dict["/etc/crypttab"])

        # Test 4: crypttab has comments and empty lines
        crypttab_contents="#This is mock crypttab file\n"\
        "mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail\n"\
        "osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh\n"\
        "\n"\
        "mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"
        expected_crypttab_contents="#This is mock crypttab file\n"\
        "mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail\n"\
        "osencrypt /dev/disk/azure/root-part1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh\n"\
        "\n"\
        "mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"
        open_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.reset_mock()
        self._mock_open_with_read_data_dict(open_mock, {"/etc/crypttab": crypttab_contents})
        self.UbuntuPatching.update_prereq()
        self.assertEquals(open_mock.call_count, 2)
        self.assertEquals(ce_mock.call_count, 1)
        self.assertEquals(exists_mock.call_count, 2)
        self.assertEquals(expected_crypttab_contents, open_mock.content_dict["/etc/crypttab"])

        # Test 5: /dev/disk/azure/root-part1 does not exist
        crypttab_contents="""osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh
        mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail
        mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"""
        expected_crypttab_contents="""osencrypt /dev/sda1 none luks,discard,header=/boot/luks/osluksheader,keyscript=/usr/sbin/azure_crypt_key.sh
        mapper_name /dev/dev_path /mnt/azure_bek_disk/LinuxPassPhraseFileName luks,nofail
        mapper_name1 /dev/dev_path1 /mnt/azure_bek_disk/LinuxPassPhraseFileName_1_0 luks,nofail"""
        open_mock.reset_mock()
        ce_mock.reset_mock()
        exists_mock.reset_mock()
        exists_mock.side_effect = [True, False]
        self._mock_open_with_read_data_dict(open_mock, {"/etc/crypttab": crypttab_contents})
        self.UbuntuPatching.update_prereq()
        self.assertEquals(open_mock.call_count, 1)
        self.assertEquals(ce_mock.call_count, 0)
        self.assertEquals(exists_mock.call_count, 2)
        self.assertEquals(expected_crypttab_contents, open_mock.content_dict["/etc/crypttab"])