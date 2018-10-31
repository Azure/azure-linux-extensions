import unittest
import mock
import main
from main import check_util
from main import Common
from StringIO import StringIO
import console_logger

class TestCheckUtil(unittest.TestCase):
    """ unit tests for functions in the check_util module """
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.cutil = check_util.CheckUtil(self.logger)

    def get_mock_filestream(self, somestring):
        stream = StringIO()
        stream.write(somestring)
        stream.seek(0)
        return stream

    @mock.patch('os.path.isfile', return_value = False)
    @mock.patch('os.path.isdir', return_value = False)
    def test_appcompat(self, os_path_isdir, os_path_isfile):
        self.assertFalse(self.cutil.is_app_compat_issue_detected())

    @mock.patch('os.popen')
    def test_memory(self, os_popen):
        output = "8000000"
        os_popen.return_value = self.get_mock_filestream(output)
        self.assertFalse(self.cutil.is_insufficient_memory())

    @mock.patch('os.popen')
    def test_memory_low_memory(self, os_popen):
        output = "6000000"
        os_popen.return_value = self.get_mock_filestream(output)
        self.assertTrue(self.cutil.is_insufficient_memory())

    def test_is_kv_url(self):
        dns_suffix_list = ["vault.azure.net", "vault.azure.cn", "vault.usgovcloudapi.net", "vault.microsoftazure.de"]

        for dns_suffix in dns_suffix_list:
            self.cutil.check_kv_url("https://testkv." + dns_suffix + "/", "")
            self.cutil.check_kv_url("https://test-kv2." + dns_suffix + "/", "")
            self.cutil.check_kv_url("https://test-kv2." + dns_suffix + ":443/", "")
            self.cutil.check_kv_url("https://test-kv2." + dns_suffix + ":443/keys/kekname/kekversion", "")
            self.assertRaises(Exception, self.cutil.check_kv_url, "http://testkv." + dns_suffix + "/", "")
            # self.assertRaises(Exception, self.cutil.check_kv_url, "https://https://testkv." + dns_suffix + "/", "")
            # self.assertRaises(Exception, self.cutil.check_kv_url, "https://testkv.testkv." + dns_suffix + "/", "")
        # self.assertRaises(Exception, self.cutil.check_kv_url, "https://testkv.vault.azure.com/", "")
        self.assertRaises(Exception, self.cutil.check_kv_url, "https://", "")

    def test_validate_volume_type(self):
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "DATA"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "ALL"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "all"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "Os"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "OS"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "os"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "Data"})
        self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: "data"})
        for vt in Common.CommonVariables.SupportedVolumeTypes:
            self.cutil.validate_volume_type({Common.CommonVariables.VolumeTypeKey: vt})

        self.assertRaises(Exception, self.cutil.validate_volume_type, {Common.CommonVariables.VolumeTypeKey: "NON-OS"})
        self.assertRaises(Exception, self.cutil.validate_volume_type, {Common.CommonVariables.VolumeTypeKey: ""})
        self.assertRaises(Exception, self.cutil.validate_volume_type, {Common.CommonVariables.VolumeTypeKey: "123"})

    def test_fatal_checks(self):
        self.cutil.precheck_for_fatal_failures({
            Common.CommonVariables.VolumeTypeKey: "ALL",
            Common.CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            })
        self.cutil.precheck_for_fatal_failures({
            Common.CommonVariables.VolumeTypeKey: "ALL",
            Common.CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            Common.CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            })
        self.cutil.precheck_for_fatal_failures({
            Common.CommonVariables.VolumeTypeKey: "ALL",
            Common.CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            Common.CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            Common.CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-256'
            })
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {})
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {Common.CommonVariables.VolumeTypeKey: "123"})
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {
            Common.CommonVariables.VolumeTypeKey: "ALL",
            Common.CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            Common.CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            Common.CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600'
            })

    def test_mount_scheme(self):
        proc_mounts_output = """
        sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
        proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
        udev /dev devtmpfs rw,relatime,size=4070564k,nr_inodes=1017641,mode=755 0 0
        devpts /dev/pts devpts rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
        tmpfs /run tmpfs rw,nosuid,noexec,relatime,size=815720k,mode=755 0 0
        /dev/sda1 / ext4 rw,relatime,discard,data=ordered 0 0
        none /sys/fs/cgroup tmpfs rw,relatime,size=4k,mode=755 0 0
        none /sys/fs/fuse/connections fusectl rw,relatime 0 0
        none /sys/kernel/debug debugfs rw,relatime 0 0
        none /sys/kernel/security securityfs rw,relatime 0 0
        none /run/lock tmpfs rw,nosuid,nodev,noexec,relatime,size=5120k 0 0
        none /run/shm tmpfs rw,nosuid,nodev,relatime 0 0
        none /run/user tmpfs rw,nosuid,nodev,noexec,relatime,size=102400k,mode=755 0 0
        none /sys/fs/pstore pstore rw,relatime 0 0
        systemd /sys/fs/cgroup/systemd cgroup rw,nosuid,nodev,noexec,relatime,name=systemd 0 0
        /dev/mapper/fee16d98-9c18-4e7d-af70-afd7f3dfb2d9 /mnt/resource ext4 rw,relatime,data=ordered 0 0
        /dev/mapper/vg0-lv0 /data ext4 rw,relatime,discard,data=ordered 0 0
        """
        with mock.patch("__builtin__.open", mock.mock_open(read_data=proc_mounts_output)) as mock_open:
            self.assertFalse(self.cutil.is_unsupported_mount_scheme())

    @mock.patch("os.system", return_value=0)
    def test_lvm_os_lvm_present(self, os_system):
        # if there is LVM
        self.assertFalse(self.cutil.is_invalid_lvm_os())

    @mock.patch("os.system", return_value=-1)
    def test_lvm_os_lvm_absent(self, os_system):
        # if there is no LVM
        self.assertFalse(self.cutil.is_invalid_lvm_os())

    @mock.patch("os.system", side_effect=[0, -1, 0, 0, 0, 0, 0, 0])
    def test_lvm_os_lvm_faulty(self, os_system):
        # if there is faulty LVM
        self.assertTrue(self.cutil.is_invalid_lvm_os())
