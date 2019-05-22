import unittest
import mock

from main.check_util import CheckUtil
from main.Common import CommonVariables
from StringIO import StringIO
from console_logger import ConsoleLogger

class MockDistroPatcher:
    def __init__(self, name, version, kernel):
        self.distro_info = [None] * 2
        self.distro_info[0] = name
        self.distro_info[1] = version
        self.kernel_version = kernel

class TestCheckUtil(unittest.TestCase):
    """ unit tests for functions in the check_util module """
    def setUp(self):
        self.logger = ConsoleLogger()
        self.cutil = CheckUtil(self.logger)

    def get_mock_filestream(self, somestring):
        stream = StringIO()
        stream.write(somestring)
        stream.seek(0)
        return stream

    @mock.patch('os.path.isfile', return_value=False)
    @mock.patch('os.path.isdir', return_value=False)
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
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "DATA"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "ALL"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "all"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "Os"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "OS"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "os"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "Data"})
        self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: "data"})
        for vt in CommonVariables.SupportedVolumeTypes:
            self.cutil.validate_volume_type({CommonVariables.VolumeTypeKey: vt})

        self.assertRaises(Exception, self.cutil.validate_volume_type, {CommonVariables.VolumeTypeKey: "NON-OS"})
        self.assertRaises(Exception, self.cutil.validate_volume_type, {CommonVariables.VolumeTypeKey: ""})
        self.assertRaises(Exception, self.cutil.validate_volume_type, {CommonVariables.VolumeTypeKey: "123"})

    @mock.patch('main.check_util.CheckUtil.validate_memory_os_encryption')
    @mock.patch('main.CommandExecutor.CommandExecutor.Execute', return_value=0)
    def test_fatal_checks(self, mock_exec, mock_validate_memory):
        mock_distro_patcher = MockDistroPatcher('Ubuntu', '14.04', '4.15')
        self.cutil.precheck_for_fatal_failures({
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.QueryEncryptionStatus
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.cutil.precheck_for_fatal_failures({
            CommonVariables.VolumeTypeKey: "DATA",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.DisableEncryption
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.cutil.precheck_for_fatal_failures({
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.cutil.precheck_for_fatal_failures({
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormat
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.cutil.precheck_for_fatal_failures({
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-256',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {})
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-256',
            CommonVariables.AADClientIDKey: "INVALIDKEY",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, mock_distro_patcher)
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {
            CommonVariables.VolumeTypeKey: "123",
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "NotEncrypted" }, mock_distro_patcher)
        mock_distro_patcher = MockDistroPatcher('Ubuntu', '14.04', '4.4')
        self.assertRaises(Exception, self.cutil.precheck_for_fatal_failures, {
            CommonVariables.VolumeTypeKey: "ALL"
            }, { "os": "NotEncrypted" }, mock_distro_patcher)

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
        with mock.patch("__builtin__.open", mock.mock_open(read_data=proc_mounts_output)):
            self.assertFalse(self.cutil.is_unsupported_mount_scheme())

    # Skip LVM OS validation when OS volume is not being targeted
    def test_skip_lvm_os_check_if_data_only_enable(self):
        # skip lvm detection if data only 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "DATA", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption})

    def test_skip_lvm_os_check_if_data_only_ef(self):
        # skip lvm detection if data only 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "DATA", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormat})

    def test_skip_lvm_os_check_if_data_only_efa(self):
        # skip lvm detection if data only 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "DATA", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll})

    def test_skip_lvm_os_check_if_data_only_disable(self):
        # skip lvm detection if data only 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "DATA", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.DisableEncryption})

    def test_skip_lvm_os_check_if_query(self):
        # skip lvm detection if query status operation is invoked without volume type
        self.cutil.validate_lvm_os({CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.QueryEncryptionStatus})

    def test_skip_lvm_no_encryption_operation(self):
        # skip lvm detection if no encryption operation 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "ALL"})

    def test_skip_lvm_no_volume_type(self):
        # skip lvm detection if no volume type specified
        self.cutil.validate_lvm_os({CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll})

    @mock.patch("os.system", return_value=-1)
    def test_no_lvm_no_config(self, os_system):
        # simulate no LVM OS, no config 
        self.cutil.validate_lvm_os({})

    @mock.patch("os.system", return_value=0)
    def test_lvm_no_config(self, os_system):
        # simulate valid LVM OS, no config
        self.cutil.validate_lvm_os({})

    @mock.patch("os.system", side_effect=[0, -1])
    def test_invalid_lvm_no_config(self, os_system):
        # simulate invalid LVM naming scheme, but no config setting to encrypt OS
        self.cutil.validate_lvm_os({})

    @mock.patch("os.system", return_value=-1)
    def test_lvm_os_lvm_absent(self, os_system):
        # using patched return value of -1, simulate no LVM OS 
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "ALL", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption})

    @mock.patch("os.system", return_value=0)
    def test_lvm_os_valid(self, os_system):
        # simulate a valid LVM OS and a valid naming scheme by always returning 0
        self.cutil.validate_lvm_os({CommonVariables.VolumeTypeKey: "ALL", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption})

    @mock.patch("os.system", side_effect=[0, -1])
    def test_lvm_os_lv_missing_expected_name(self, os_system):
        # using patched side effects, first simulate LVM OS present, then simulate not finding the expected LV name 
        self.assertRaises(Exception, self.cutil.validate_lvm_os, {CommonVariables.VolumeTypeKey: "ALL", CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption})

    @mock.patch("main.CommandExecutor.CommandExecutor.Execute", return_value=0)
    def test_vfat(self, os_system):
        # simulate call to modprobe vfat that succeeds and returns cleanly from execute 
        self.cutil.validate_vfat()

    @mock.patch("main.CommandExecutor.CommandExecutor.Execute", side_effect=Exception("Test"))
    def test_no_vfat(self, os_system):
        # simulate call to modprobe vfat that fails and raises exception from execute 
        self.assertRaises(Exception, self.cutil.validate_vfat) 

    def test_validate_aad(self):
        # positive tests
        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = "00000000-0000-0000-0000-000000000000"
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryption
        self.cutil.validate_aad(test_settings)

        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = "00000000-0000-aaaa-0000-000000000000"
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryptionFormat
        self.cutil.validate_aad(test_settings)

        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = "00000000-0000-AAAA-0000-000000000000"
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryptionFormatAll
        self.cutil.validate_aad(test_settings)

        test_settings = {} 
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.DisableEncryption
        self.cutil.validate_aad(test_settings)

        test_settings = {} 
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.QueryEncryptionStatus
        self.cutil.validate_aad(test_settings)

        # negative tests
        # settings file that does not include AAD client ID field
        test_settings = {} 
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryption
        self.assertRaises(Exception, self.cutil.validate_aad, test_settings)

        # invalid characters in the client ID
        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = "BORKED"
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryption
        self.assertRaises(Exception, self.cutil.validate_aad, test_settings)

        # empty string
        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = ""
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryption
        self.assertRaises(Exception, self.cutil.validate_aad, test_settings)

        # unicode left and right double quotes (simulating a copy-paste error)
        test_settings = {} 
        test_settings[CommonVariables.AADClientIDKey] = u'\u201c' + "00000000-0000-0000-0000-000000000000" + u'\u201d'
        test_settings[CommonVariables.EncryptionEncryptionOperationKey] = CommonVariables.EnableEncryption
        self.assertRaises(Exception, self.cutil.validate_aad, test_settings)

    @mock.patch('os.popen')
    def test_minimum_memory(self, os_popen):
        output = "6000000"
        os_popen.return_value = self.get_mock_filestream(output)
        self.assertRaises(Exception, self.cutil.validate_memory_os_encryption, {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "NotEncrypted" })
        try:
            self.cutil.validate_memory_os_encryption( {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "Encrypted" })
        except Exception:
            self.fail("validate_memory_os_encryption threw unexpected exception\nException message was:\n" + str(e))
        try:
            output = "8000000"
            os_popen.return_value = self.get_mock_filestream(output)
            self.cutil.validate_memory_os_encryption( {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "Encrypted" })
        except Exception:
            self.fail("validate_memory_os_encryption threw unexpected exception\nException message was:\n" + str(e))
        try:
            output = "8000000"
            os_popen.return_value = self.get_mock_filestream(output)
            self.cutil.validate_memory_os_encryption( {
            CommonVariables.VolumeTypeKey: "ALL",
            CommonVariables.KeyVaultURLKey: "https://vaultname.vault.azure.net/",
            CommonVariables.KeyEncryptionKeyURLKey: "https://vaultname.vault.azure.net/keys/keyname/ver",
            CommonVariables.KeyEncryptionAlgorithmKey: 'rsa-OAEP-25600',
            CommonVariables.AADClientIDKey: "00000000-0000-0000-0000-000000000000",
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll
            }, { "os": "NotEncrypted" })
        except Exception:
            self.fail("validate_memory_os_encryption threw unexpected exception\nException message was:\n" + str(e))

    def test_supported_os(self):
        # test exception is raised for Ubuntu 14.04 kernel version
        self.assertRaises(Exception, self.cutil.is_supported_os, {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('Ubuntu', '14.04', '4.4'), {"os" : "NotEncrypted"})
        # test exception is not raised for Ubuntu 14.04 kernel version 4.15
        try:
            self.cutil.is_supported_os( {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('Ubuntu', '14.04', '4.15'), {"os" : "NotEncrypted"})
        except Exception as e:
            self.fail("is_unsupported_os threw unexpected exception.\nException message was:\n" + str(e))
        # test exception is not raised for already encrypted OS volume
        try:
            self.cutil.is_supported_os( {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('Ubuntu', '14.04', '4.4'), {"os" : "Encrypted"})
        except Exception as e:
            self.fail("is_unsupported_os threw unexpected exception.\nException message was:\n" + str(e))
        # test exception is raised for unsupported OS
        self.assertRaises(Exception, self.cutil.is_supported_os, {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('Ubuntu', '12.04', ''), {"os" : "NotEncrypted"})
        self.assertRaises(Exception, self.cutil.is_supported_os, {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('redhat', '6.7', ''), {"os" : "NotEncrypted"})
        self.assertRaises(Exception, self.cutil.is_supported_os, {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('centos', '7.9', ''), {"os" : "NotEncrypted"})
        # test exception is not raised for supported OS
        try:
            self.cutil.is_supported_os( {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('Ubuntu', '18.04', ''), {"os" : "NotEncrypted"})
        except Exception as e:
            self.fail("is_unsupported_os threw unexpected exception.\nException message was:\n" + str(e))
        try:
            self.cutil.is_supported_os( {
            CommonVariables.VolumeTypeKey: "ALL"
            }, MockDistroPatcher('centos', '7.2.1511', ''), {"os" : "NotEncrypted"})
        except Exception as e:
            self.fail("is_unsupported_os threw unexpected exception.\nException message was:\n" + str(e))
        # test exception is not raised for DATA volume
        try:
            self.cutil.is_supported_os( {
            CommonVariables.VolumeTypeKey: "DATA"
            }, MockDistroPatcher('SuSE', '12.4', ''), {"os" : "NotEncrypted"})
        except Exception as e:
            self.fail("is_unsupported_os threw unexpected exception.\nException message was:\n" + str(e))
