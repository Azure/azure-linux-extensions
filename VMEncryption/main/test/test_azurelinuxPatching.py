import unittest
import os.path

from patch.azurelinuxPatching import azurelinuxPatching
from console_logger import ConsoleLogger

try:
    builtins_open = "builtins.open"
    import unittest.mock as mock # python3+
except ImportError:
    builtins_open = "__builtin__.open"
    import mock # python2


class Test_azurelinuxPatching(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.azl_patching = azurelinuxPatching(self.logger, ['azurelinux', '3.0'])

    def test_online_enc_candidate_30(self):
        azl_patching = azurelinuxPatching(self.logger, ['azurelinux', '3.0'])
        self.assertTrue(azl_patching.support_online_encryption)

    def test_online_enc_candidate_29(self):
        azl_patching = azurelinuxPatching(self.logger, ['azurelinux', '2.9'])
        self.assertFalse(azl_patching.support_online_encryption)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_cryptsetup_already_installed(self, ce_mock):
        """Test that install_cryptsetup doesn't attempt installation when package is already installed"""
        # Mock rpm -q to return 0 (success) indicating package is installed
        ce_mock.return_value = 0
        
        result = self.azl_patching.install_cryptsetup()
        
        # Should return 0 (success) without attempting installation
        self.assertEqual(result, 0)
        # Should only call rpm -q once to check if package is installed
        self.assertEqual(ce_mock.call_count, 1)
        # Should call rpm -q cryptsetup
        ce_mock.assert_called_with("rpm -q cryptsetup")

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_cryptsetup_not_installed(self, ce_mock):
        """Test that install_cryptsetup attempts installation when package is missing"""
        # First call (rpm -q) returns 1 (failure) indicating package is not installed
        # Second call (tdnf install) returns 0 (success)
        ce_mock.side_effect = [1, 0]
        
        result = self.azl_patching.install_cryptsetup()
        
        # Should return 0 (success) after installation
        self.assertEqual(result, 0)
        # Should call rpm -q once, then tdnf install once
        self.assertEqual(ce_mock.call_count, 2)
        # Check the calls were made correctly
        expected_calls = [
            mock.call("rpm -q cryptsetup"),
            mock.call("tdnf install -y cryptsetup", timeout=100)
        ]
        ce_mock.assert_has_calls(expected_calls)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_cryptsetup_timeout(self, ce_mock):
        """Test that install_cryptsetup handles timeout correctly"""
        # First call (rpm -q) returns 1 (failure) indicating package is not installed
        # Second call (tdnf install) returns -9 (timeout)
        ce_mock.side_effect = [1, -9]
        
        with self.assertRaises(Exception) as context:
            self.azl_patching.install_cryptsetup()
        
        # Should raise exception with timeout message
        self.assertIn("tdnf install timed out", str(context.exception))
        # Should call rpm -q once, then tdnf install once
        self.assertEqual(ce_mock.call_count, 2)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_extras_all_installed(self, ce_mock):
        """Test that install_extras doesn't attempt installation when all packages are installed"""
        # Mock rpm -q to return 0 (success) for all packages
        ce_mock.return_value = 0
        
        self.azl_patching.install_extras()
        
        # Get the actual package list (depends on online encryption support)
        if self.azl_patching.support_online_encryption:
            expected_packages = ['cryptsetup', 'lsscsi', 'lvm2', 'util-linux', 'nvme-cli']
        else:
            expected_packages = ['cryptsetup', 'lsscsi', 'psmisc', 'lvm2', 'uuid', 'at', 'patch', 'procps-ng', 'util-linux']
        
        self.assertEqual(ce_mock.call_count, len(expected_packages))
        
        # Verify it checked each expected package
        for package in expected_packages:
            self.assertIn(mock.call("rpm -q " + package), ce_mock.call_args_list)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_extras_some_missing(self, ce_mock):
        """Test that install_extras only installs missing packages"""
        # Mock responses for online encryption enabled scenario (default for azurelinux 3.0)
        def mock_execute(command, **kwargs):
            if "rpm -q cryptsetup" in command:
                return 0  # installed
            elif "rpm -q lsscsi" in command:
                return 1  # missing
            elif "rpm -q lvm2" in command:
                return 1  # missing  
            elif "rpm -q util-linux" in command:
                return 0  # installed
            elif "rpm -q nvme-cli" in command:
                return 0  # installed
            elif "tdnf install" in command:
                return 0  # successful installation
            else:
                return 1
                
        ce_mock.side_effect = mock_execute
        
        self.azl_patching.install_extras()
        
        # With online encryption enabled, we check 5 packages + 1 installation call = 6 total
        expected_calls = 6 if self.azl_patching.support_online_encryption else 10
        self.assertEqual(ce_mock.call_count, expected_calls)
        
        # Last call should be the installation of missing packages
        last_call = ce_mock.call_args_list[-1]
        install_command = last_call[0][0]  # First positional argument
        self.assertIn("tdnf install -y", install_command)
        # Should only install the missing packages
        self.assertIn("lsscsi", install_command)
        self.assertIn("lvm2", install_command)
        # Should not install already present packages
        self.assertNotIn("cryptsetup", install_command)
        self.assertNotIn("util-linux", install_command)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_extras_online_encryption_supported(self, ce_mock):
        """Test that install_extras modifies package list when online encryption is supported"""
        # Mock online encryption support
        self.azl_patching.support_online_encryption = True
        
        # Mock all packages as missing to see the full installation command
        ce_mock.side_effect = lambda cmd, **kwargs: 0 if "tdnf install" in cmd else 1
        
        self.azl_patching.install_extras()
        
        # Find the installation command
        install_command = None
        for call in ce_mock.call_args_list:
            if "tdnf install" in call[0][0]:
                install_command = call[0][0]
                break
        
        self.assertIsNotNone(install_command)
        
        # Should include nvme-cli when online encryption is supported
        self.assertIn("nvme-cli", install_command)
        
        # Should exclude certain packages when online encryption is supported
        excluded_packages = ['psmisc', 'uuid', 'at', 'patch', 'procps-ng']
        for package in excluded_packages:
            self.assertNotIn(package, install_command)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_install_extras_online_encryption_not_supported(self, ce_mock):
        """Test that install_extras uses standard package list when online encryption is not supported"""
        # Mock online encryption not supported
        self.azl_patching.support_online_encryption = False
        
        # Mock all packages as missing to see the full installation command
        ce_mock.side_effect = lambda cmd, **kwargs: 0 if "tdnf install" in cmd else 1
        
        self.azl_patching.install_extras()
        
        # Find the installation command
        install_command = None
        for call in ce_mock.call_args_list:
            if "tdnf install" in call[0][0]:
                install_command = call[0][0]
                break
        
        self.assertIsNotNone(install_command)
        
        # Should not include nvme-cli when online encryption is not supported
        self.assertNotIn("nvme-cli", install_command)
        
        # Should include all standard packages
        standard_packages = ['cryptsetup', 'lsscsi', 'psmisc', 'lvm2', 'uuid', 'at', 'patch', 'procps-ng', 'util-linux']
        for package in standard_packages:
            self.assertIn(package, install_command)

    def test_grub_cfg_paths(self):
        """Test that grub configuration paths are set correctly for Azure Linux"""
        expected_paths = [
            ("/boot/grub2/grub.cfg", "/boot/grub2/grubenv")
        ]
        self.assertEqual(self.azl_patching.grub_cfg_paths, expected_paths)

    def test_min_version_online_encryption(self):
        """Test that minimum version for online encryption is set correctly"""
        self.assertEqual(self.azl_patching.min_version_online_encryption, '3.0')


if __name__ == '__main__':
    unittest.main()
