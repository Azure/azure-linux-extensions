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
import mock

from main.ResourceDiskUtil import ResourceDiskUtil
from main.DiskUtil import DiskUtil
from main.Common import CommonVariables
from console_logger import ConsoleLogger


class TestResourceDiskUtil(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.mock_disk_util = mock.create_autospec(DiskUtil)
        self.mock_passhprase_filename = "mock_passphrase_filename"
        mock_public_settings = {}
        self.resource_disk = ResourceDiskUtil(self.logger, self.mock_disk_util, self.mock_passhprase_filename, mock_public_settings, ["ubuntu", "16"])

    def _test_resource_disk_partition_dependant_method(self, method, mock_partition_exists, mock_execute):
        """
        A lot of methods have a common pattern [ if (partition_exists()): return execute_something() else return False ]
        This is a generic method which accepts the mock objects and the method pointer and tests the method.
        NOTE: make sure its a fresh instance of the mocked Executor (mock_execute)
        """
        # case 1: partition doesn't exist
        mock_partition_exists.return_value = False
        self.assertEqual(method(), False)
        mock_execute.assert_not_called()

        # case 2: partition exists but call fails
        mock_partition_exists.return_value = True
        mock_execute.return_value = -1  # simulate that the internal execute call failed.
        self.assertEqual(method(), False)

        # case 3: partition exists and call succeeds
        mock_partition_exists.return_value = True
        mock_execute.return_value = CommonVariables.process_success  # simulate that the internal execute call succeeded
        self.assertEqual(method(), True)

    @mock.patch('main.CommandExecutor.CommandExecutor.Execute')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._resource_disk_partition_exists')
    def test_is_luks_device(self, mock_partition_exists, mock_execute):
        self._test_resource_disk_partition_dependant_method(self.resource_disk._is_luks_device, mock_partition_exists, mock_execute)

    @mock.patch('main.CommandExecutor.CommandExecutor.Execute')
    def test_configure_waagent(self, mock_execute):
        mock_execute.side_effect = [-1,
                                    0,
                                    0]
        self.assertEqual(self.resource_disk._configure_waagent(), False)
        mock_execute.assert_called_once()
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

    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil.add_resource_disk_to_crypttab')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._resource_disk_partition_exists')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._is_luks_device')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._is_crypt_mounted')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._is_plain_mounted')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._mount_resource_disk')
    def test_try_remount(self, mock_mount, mock_plain_mounted, mock_crypt_mounted, mock_is_luks, mock_partition_exists, mock_add_rd_to_crypttab):

        # Case 1, when there is a passphrase and the resource disk is not already encrypted and mounted.
        mock_partition_exists.return_value = True
        mock_is_luks.return_value = False
        mock_crypt_mounted.return_value = False
        mock_mount.return_value = True
        self.resource_disk.passphrase_filename = self.mock_passhprase_filename

        self.assertEqual(self.resource_disk.try_remount(), False)

        mock_mount.assert_not_called()
        mock_add_rd_to_crypttab.assert_not_called()

        # Case 2, resource disk is encrypted but not mounted
        mock_is_luks.return_value = True

        self.assertEqual(self.resource_disk.try_remount(), True)

        mock_mount.assert_called_with(ResourceDiskUtil.RD_MAPPER_PATH)
        self.mock_disk_util.luks_open.assert_called_with(passphrase_file=self.mock_passhprase_filename,
                                                         dev_path=ResourceDiskUtil.RD_DEV_PATH,
                                                         mapper_name=ResourceDiskUtil.RD_MAPPER_NAME,
                                                         header_file=None,
                                                         uses_cleartext_key=False)
        mock_add_rd_to_crypttab.assert_called()

        # Case 2, when the resoure disk mount fails
        mock_mount.return_value = False
        self.assertEqual(self.resource_disk.try_remount(), False)

        mock_mount.assert_called_with(ResourceDiskUtil.RD_MAPPER_PATH)

        # Case 3, The RD is encyrpted and mounted.
        mock_crypt_mounted.return_value = True
        mock_mount.reset_mock()
        mock_add_rd_to_crypttab.reset_mock()
        mock_mount.return_value = True
        self.assertEqual(self.resource_disk.try_remount(), True)
        mock_mount.assert_not_called()
        mock_add_rd_to_crypttab.assert_not_called()

        # Case 4, The RD is plain mounted already and there is no passphrase
        mock_plain_mounted.return_value = True
        self.resource_disk.passphrase_filename = None
        self.assertEqual(self.resource_disk.try_remount(), True)

        # Case 5, The RD is not plain mounted but the mount fails for some reason.
        mock_mount.return_value = False
        mock_plain_mounted.return_value = False
        self.assertEqual(self.resource_disk.try_remount(), False)
        mock_mount.assert_called_once_with(ResourceDiskUtil.RD_DEV_PATH)

        # Case 6, The RD is not plain mounted and mount succeeds
        mock_mount.return_value = True
        self.assertEqual(self.resource_disk.try_remount(), True)
        mock_mount.assert_called_with(ResourceDiskUtil.RD_DEV_PATH)

    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._is_crypt_mounted', return_value=False)
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil._is_plain_mounted', return_value=True)
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil.encrypt_format_mount')
    @mock.patch('main.ResourceDiskUtil.ResourceDiskUtil.try_remount')
    def test_automount(self, mock_try_remount, mock_encrypt_format_mount, mock_is_plain_mounted, mock_is_crypt_mounted):
        # Case 1: try_remount succeds
        mock_try_remount.return_value = True
        self.assertEqual(self.resource_disk.automount(), True)
        mock_try_remount.assert_called_once()

        # Case 2: try_remount fails and public settings is non-EFA:
        mock_try_remount.return_value = False

        # Case 2.x: these are basically gonna be a bunch of tests for "is_encrypt_format"
        self.resource_disk.public_settings = {}
        self.assertEqual(self.resource_disk.automount(), True)
        mock_encrypt_format_mount.assert_not_called()

        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryption}
        self.assertEqual(self.resource_disk.automount(), True)
        mock_encrypt_format_mount.assert_not_called()

        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.DisableEncryption}
        self.assertEqual(self.resource_disk.automount(), True)
        mock_encrypt_format_mount.assert_not_called()

        # Case 3: EFA case. A try remount failure should lead to a hard encrypt_format_mount.
        self.resource_disk.public_settings = {
            CommonVariables.EncryptionEncryptionOperationKey: CommonVariables.EnableEncryptionFormatAll}
        mock_encrypt_format_mount.return_value = True
        self.assertEqual(self.resource_disk.automount(), True)
        mock_encrypt_format_mount.assert_called_once()

        # case 4: EFA case, but EFA fails for some reason
        mock_encrypt_format_mount.reset_mock()
        mock_encrypt_format_mount.return_value = False
        self.assertEqual(self.resource_disk.automount(), False)
        mock_encrypt_format_mount.assert_called_once()
