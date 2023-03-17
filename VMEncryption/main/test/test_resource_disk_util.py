#!/usr/bin/env python
#
# *********************************************************
# Copyright (c) Microsoft. All rights reserved.
#
# Apache 2.0 License
#
# You may obtain a copy of the License at
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# *********************************************************

""" Unit tests for the ResourceDiskUtil module """

import unittest
import os

from ResourceDiskUtil import ResourceDiskUtil
from DiskUtil import DiskUtil
from CryptMountConfigUtil import CryptMountConfigUtil
from Common import CommonVariables
from .console_logger import ConsoleLogger
try:
    import unittest.mock as mock  # python3+
except ImportError:
    import mock  # python2


class TestResourceDiskUtil(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.mock_disk_util = mock.create_autospec(DiskUtil)
        self.mock_crypt_mount_config_util = mock.create_autospec(CryptMountConfigUtil)
        self.mock_passphrase_filename = "mock_passphrase_filename"
        mock_public_settings = {}
        self.resource_disk = ResourceDiskUtil(self.logger, self.mock_disk_util, self.mock_crypt_mount_config_util, self.mock_passphrase_filename, mock_public_settings, ["ubuntu", "16"],False)

    def _test_resource_disk_partition_dependant_method(self, method, mock_partition_exists, mock_execute):
        """
        A lot of methods have a common pattern [ if (partition_exists()): return execute_something() else return False ]
        This is a generic method which accepts the mock objects and the method pointer and tests the method.
        NOTE: make sure its a fresh instance of the mocked Executor (mock_execute)
        """
        # case 1: partition doesn't exist
        mock_partition_exists.return_value = False
        self.assertEqual(method(), False)
        self.assertEqual(mock_execute.call_count, 0)

        # case 2: partition exists but call fails
        mock_partition_exists.return_value = True
        mock_execute.return_value = 1  # simulate that the internal execute call failed.
        self.assertEqual(method(), False)

        # case 3: partition exists and call succeeds
        mock_partition_exists.return_value = True
        mock_execute.return_value = CommonVariables.process_success  # simulate that the internal execute call succeeded
        self.assertEqual(method(), True)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._resource_disk_partition_exists')
    def test_is_luks_device(self, mock_partition_exists, mock_execute):
        self._test_resource_disk_partition_dependant_method(self.resource_disk._is_luks_device, mock_partition_exists, mock_execute)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_configure_waagent(self, mock_execute):
        mock_execute.side_effect = [-1,
                                    0,
                                    0]
        self.assertEqual(self.resource_disk._configure_waagent(), False)
        self.assertEqual(mock_execute.call_count, 1)
        self.assertEqual(self.resource_disk._configure_waagent(), True)

    def test_is_plain_mounted(self):
        self.resource_disk.disk_util.get_mount_items.return_value = []
        self.assertEqual(self.resource_disk._is_plain_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/dm-0", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_plain_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/mapper/something", "dest": "/mnt/"}]
        self.assertEqual(self.resource_disk._is_plain_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/sdcx", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_plain_mounted(), True)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/sdb2", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_plain_mounted(), True)

    def test_is_crypt_mounted(self):
        self.resource_disk.disk_util.get_mount_items.return_value = []
        self.assertEqual(self.resource_disk._is_crypt_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/dm-0", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_crypt_mounted(), True)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/mapper/something", "dest": "/mnt/"}]
        self.assertEqual(self.resource_disk._is_crypt_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/mapper/something", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_crypt_mounted(), True)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/sdcx", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_crypt_mounted(), False)

        self.resource_disk.disk_util.get_mount_items.return_value = [{"src": "/dev/sdb2", "dest": "/mnt/resource"}]
        self.assertEqual(self.resource_disk._is_crypt_mounted(), False)

    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.add_resource_disk_to_crypttab')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._get_rd_base_dev_path')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._resource_disk_partition_exists')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_luks_device')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_crypt_mounted')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_plain_mounted')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._mount_resource_disk')
    def test_try_remount(self, mock_mount, mock_plain_mounted, mock_crypt_mounted, mock_is_luks, mock_partition_exists, mock_get_rd_base, mock_add_rd_to_crypttab):

        mock_rd_base_path = "mock_rd_path"
        mock_rd_part_path = "mock_rd_path-part1"
        mock_get_rd_base.return_value = mock_rd_base_path

        # Case 1, when there is a passphrase and the resource disk is not already encrypted and mounted.
        mock_partition_exists.return_value = True
        mock_is_luks.return_value = False
        mock_crypt_mounted.return_value = False
        mock_mount.return_value = True
        self.resource_disk.passphrase_filename = self.mock_passphrase_filename

        self.assertEqual(self.resource_disk.try_remount(), False)
        self.assertEqual(mock_mount.call_count, 0)
        self.assertEqual(mock_add_rd_to_crypttab.call_count, 0)

        # Case 2, resource disk is encrypted but not mounted
        mock_is_luks.return_value = True

        self.assertEqual(self.resource_disk.try_remount(), True)

        mock_mount.assert_called_with(ResourceDiskUtil.RD_MAPPER_PATH)
        self.mock_disk_util.luks_open.assert_called_with(passphrase_file=self.mock_passphrase_filename,
                                                         dev_path=mock_rd_part_path,
                                                         mapper_name=ResourceDiskUtil.RD_MAPPER_NAME,
                                                         header_file=None,
                                                         uses_cleartext_key=False)
        self.assertEqual(mock_add_rd_to_crypttab.call_count, 1)

        # Case 2, when the resource disk mount fails
        mock_mount.return_value = False
        self.assertEqual(self.resource_disk.try_remount(), False)
        mock_mount.assert_called_with(ResourceDiskUtil.RD_MAPPER_PATH)

        # Case 3, The RD is encrypted and mounted.
        mock_crypt_mounted.return_value = True
        mock_mount.reset_mock()
        mock_add_rd_to_crypttab.reset_mock()
        mock_mount.return_value = True
        self.assertEqual(self.resource_disk.try_remount(), True)
        self.assertEqual(mock_mount.call_count, 0)
        self.assertEqual(mock_add_rd_to_crypttab.call_count, 1)

        # Case 4, The RD is plain mounted already and there is no passphrase
        mock_plain_mounted.return_value = True
        self.resource_disk.passphrase_filename = None
        self.assertEqual(self.resource_disk.try_remount(), True)

        # Case 5, The RD is not plain mounted but the mount fails for some reason.
        mock_mount.return_value = False
        mock_plain_mounted.return_value = False
        self.assertEqual(self.resource_disk.try_remount(), False)
        mock_mount.assert_called_once_with(mock_rd_part_path)

        # Case 6, The RD is not plain mounted and mount succeeds
        mock_mount.return_value = True
        self.assertEqual(self.resource_disk.try_remount(), True)
        mock_mount.assert_called_with(mock_rd_part_path)

    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_crypt_mounted', return_value=False)
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_plain_mounted', return_value=True)
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.encrypt_format_mount')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.try_remount')
    def test_automount(self, mock_try_remount, mock_encrypt_format_mount, mock_is_plain_mounted, mock_is_crypt_mounted):
        # Case 1: try_remount succeds
        mock_try_remount.return_value = True
        self.assertEqual(self.resource_disk.automount(), True)
        self.assertEqual(mock_try_remount.call_count, 1)

        # Case 2: try_remount fails and public settings is non-EFA:
        mock_try_remount.return_value = False

        # Case 2.x: these are basically gonna be a bunch of tests for "is_encrypt_format"
        self.resource_disk.public_settings = {}
        self.assertEqual(self.resource_disk.automount(), True)
        self.assertEqual(mock_encrypt_format_mount.call_count, 0)

        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption}
        self.assertEqual(self.resource_disk.automount(), True)
        self.assertEqual(mock_encrypt_format_mount.call_count, 0)

        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.DisableEncryption}
        self.assertEqual(self.resource_disk.automount(), True)
        self.assertEqual(mock_encrypt_format_mount.call_count, 0)

        # Case 3: EFA case. A try remount failure should lead to a hard encrypt_format_mount.
        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll}
        mock_encrypt_format_mount.return_value = True
        self.assertEqual(self.resource_disk.automount(), True)
        self.assertEqual(mock_encrypt_format_mount.call_count, 1)

        # case 4: EFA case, but EFA fails for some reason
        mock_encrypt_format_mount.reset_mock()
        mock_encrypt_format_mount.return_value = False
        self.assertEqual(self.resource_disk.automount(), False)
        self.assertEqual(mock_encrypt_format_mount.call_count, 1)

    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._is_crypt_mounted')
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.encrypt_format_mount')
    def test_encrypt_resource_disk(self, mock_efm, mock_icm):
        # Case 1: RD is not crypt mounted and encrypt_format_mount succeeds
        mock_efm.return_value = True
        mock_icm.return_value = False
        rd_mounted = self.resource_disk.encrypt_resource_disk()
        self.assertTrue(rd_mounted)

        # Case 2: RD is crypt mounted
        mock_efm.return_value = False
        mock_icm.return_value = True
        rd_mounted = self.resource_disk.encrypt_resource_disk()
        self.assertTrue(rd_mounted)

        # Case 3: RD is not crypt mounted and encrypt_format_mount fails
        mock_efm.return_value = False
        mock_icm.return_value = False
        rd_mounted = self.resource_disk.encrypt_resource_disk()
        self.assertFalse(rd_mounted)

    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._resource_disk_exists', return_value=True)
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.prepare')
    def test_encrypt_format_mount_resource_disk_exists(self, mock_prepare, mock_resource_disk_exists):
        self.resource_disk.encrypt_format_mount()
        self.assertEqual(mock_prepare.call_count, 1)

    @mock.patch('ResourceDiskUtil.ResourceDiskUtil._resource_disk_exists', return_value=False)
    @mock.patch('ResourceDiskUtil.ResourceDiskUtil.prepare')
    def test_encrypt_format_mount_resource_disk_does_not_exist(self, mock_prepare, mock_resource_disk_exists):
        self.assertEqual(self.resource_disk.encrypt_format_mount(), True)
        self.assertEqual(mock_prepare.call_count, 0)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_try_unmount_lxd_exists_true(self, mock_execute):
        mock_execute.side_effect = [0, 0]
        self.assertEqual(self.resource_disk._try_unmount_lxd(), True)
        self.assertEqual(mock_execute.call_count, 2)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_try_unmount_lxd_exists_false(self, mock_execute):
        mock_execute.side_effect = [0, 1]
        self.assertEqual(self.resource_disk._try_unmount_lxd(), False)
        self.assertEqual(mock_execute.call_count, 2)

    @mock.patch('CommandExecutor.CommandExecutor.Execute')
    def test_try_unmount_lxd_does_not_exist(self, mock_execute):
        mock_execute.side_effect = [1]
        self.assertEqual(self.resource_disk._try_unmount_lxd(), True)
        self.assertEqual(mock_execute.call_count, 1)

    @mock.patch('os.path.exists')
    def test_get_rd_base_dev_path(self, exists_mock):
        dev_path_options = [
            os.path.join(CommonVariables.azure_symlinks_dir, 'resource'),
            os.path.join(CommonVariables.cloud_symlinks_dir, 'azure_resource'),
            os.path.join(CommonVariables.azure_symlinks_dir, 'scsi0/lun1')
        ]

        exists_mock.side_effect = [True]
        self.resource_disk._RD_BASE_DEV_PATH_CACHE = ""
        rd_base_path = self.resource_disk._get_rd_base_dev_path()
        self.assertEqual(dev_path_options[0], rd_base_path)

        exists_mock.side_effect = [False, True]
        self.resource_disk._RD_BASE_DEV_PATH_CACHE = ""
        rd_base_path = self.resource_disk._get_rd_base_dev_path()
        self.assertEqual(dev_path_options[1], rd_base_path)

        exists_mock.side_effect = [False, False, True]
        self.resource_disk._RD_BASE_DEV_PATH_CACHE = ""
        rd_base_path = self.resource_disk._get_rd_base_dev_path()
        self.assertEqual(dev_path_options[2], rd_base_path)

        exists_mock.side_effect = [False, False, False]
        self.resource_disk._RD_BASE_DEV_PATH_CACHE = ""
        rd_base_path = self.resource_disk._get_rd_base_dev_path()
        self.assertEqual("", rd_base_path)

        exists_mock.side_effect = [False, False, False]
        self.resource_disk._RD_BASE_DEV_PATH_CACHE = "test_base_dev_path"
        rd_base_path = self.resource_disk._get_rd_base_dev_path()
        self.assertEqual("test_base_dev_path", rd_base_path)
