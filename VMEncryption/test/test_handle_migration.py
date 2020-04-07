import unittest
import mock
import sys
import json

from main.Common import CryptItem,DeviceItem, CommonVariables
from main import handle
from main.DiskUtil import DiskUtil
from console_logger import ConsoleLogger
from test_utils import MockDistroPatcher
from main.Utils.HandlerUtil import HandlerUtility

class TestHandleMigration(unittest.TestCase):
    def setup(self):
        return

    def _create_device_item(self, name=None, mount_point=None, file_system=None, device_id="", type=""):
        device_item = DeviceItem()
        device_item.name = name
        device_item.mount_point = mount_point
        device_item.file_system = file_system
        device_item.device_id = device_id
        device_item.type = type
        return device_item

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

    def _get_mock_crypt_device_items(self, os=False, data_with_ath_header=[], data_with_dth_header=[]):
        crypt_items = []
        device_items_map = {}
        data_counter = 0
        if os:
            crypt_item = self._create_expected_crypt_item(mapper_name='osencrypt', dev_path="/osdisk", luks_header_path="/os/header", mount_point='/')
            crypt_items.append(crypt_item)
        for x in range(0,len(data_with_ath_header)):
            device_items = []
            crypt_item = self._create_expected_crypt_item(mapper_name='guid'+str(data_counter), mount_point='/data'+str(data_counter), dev_path="/datadisk"+str(data_counter))
            crypt_items.append(crypt_item)
            device_item = self._create_device_item(file_system=data_with_ath_header[x])
            device_items.append(device_item)
            device_items_map.update({crypt_item.dev_path : device_items})
            data_counter += 1
        for x in range(0,len(data_with_dth_header)):
            device_items = []
            crypt_item = self._create_expected_crypt_item(mapper_name='guid'+str(data_counter), mount_point='/data'+str(data_counter), dev_path="/datadisk"+str(data_counter), luks_header_path='/data/header'+str(data_counter))
            crypt_items.append(crypt_item)
            device_item = self._create_device_item(file_system=data_with_dth_header[x])
            device_items.append(device_item)
            device_items_map.update({crypt_item.dev_path : device_items})
            data_counter += 1
        return crypt_items, device_items_map

    @mock.patch("main.DiskUtil.DiskUtil")
    def test_is_migration_allowed(self, mock_disk_util):

        def _get_device_items_side_effect(dev_path):
            return mock_device_items[dev_path]

        
        handle.logger = ConsoleLogger()
        mock_disk_util.distro_patcher = MockDistroPatcher('Ubuntu', '14.04', '4.15')

        # Case 1: Os Disk + 2 data disk with attached header
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(True, ['xfs', 'ext4'], [])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.return_value = 0
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertTrue(migration_allowed, msg='Migration should be allowed')
        self.assertIsNone(error_msg, msg='Error message should be None')

        # Case 2: Os Disk + 1 data disk with attached header + 1 data disk with detached header
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(True, ['ext4'], ['xfs'])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.return_value = 0
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertFalse(migration_allowed, msg='Migration should not be allowed')
        self.assertEquals(error_msg, CommonVariables.migration_detached_header_xfs)

        # Case 3: Os disk and wrong passphrase
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(True, [], [])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.return_value = 1
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertFalse(migration_allowed, msg='Migration should not be allowed')
        self.assertEquals(error_msg, CommonVariables.migration_wrong_passphrase)

        # Case 4: 2 data disks with detached header
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(False, [], ['ext4', 'ext4'])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.return_value = 0
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertFalse(migration_allowed, msg='Migration should not be allowed')
        self.assertEquals(error_msg, CommonVariables.migration_detached_header)

        # Case 5: Os disk + 2 data disk with attached header and wrong passphrase for 2nd data disk
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(True, ['xfs', 'ext4'], [])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.side_effect = [0, 0, 1]
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertFalse(migration_allowed, msg='Migration should not be allowed')
        self.assertEquals(error_msg, CommonVariables.migration_wrong_passphrase)

        # Case 6: No disk encrypted
        mock_crypt_items, mock_device_items = self._get_mock_crypt_device_items(False, [], [])
        mock_disk_util.get_device_items.side_effect = _get_device_items_side_effect
        mock_disk_util.get_crypt_items.return_value = mock_crypt_items
        mock_disk_util.luks_test_passphrase.return_value = 0
        migration_allowed, error_msg = handle.is_migration_allowed(mock_disk_util, "mock_passphrase_file")
        self.assertTrue(migration_allowed, msg='Migration should be allowed')
        self.assertIsNone(error_msg, msg='Error message should be None')

    @mock.patch("main.handle.is_migration_allowed")
    @mock.patch("main.handle.stamp_disks_with_settings", return_value=None)
    @mock.patch("main.DiskUtil.DiskUtil")
    @mock.patch("main.handle.exit_without_status_report", return_value=None)
    @mock.patch("main.Utils.HandlerUtil.HandlerUtility")
    def test_perform_migration(self, mock_handler_util, mock_exit, mock_disk_util, mock_stamp, mock_mig_allow):

        def _do_exit_side_effect(exit_code, operation, status, code, message):
            _do_exit_side_effect.exit_message = message
            return None
        
        handle.logger = ConsoleLogger()
        handle.hutil = mock_handler_util
        mock_handler_util.save_seq.return_value = None
        mock_handler_util.do_exit.side_effect = _do_exit_side_effect

        # Case 1: is_migration_allowed returns True
        mock_mig_allow.return_value = True, None
        # An exception will be considered test failure
        handle.perform_migration(mock_disk_util, "mock_passphrase_file", None)

        # Case 2: is_migration_allowed returns False
        mock_mig_allow.return_value = False, "Dummy Error"
        handle.perform_migration(mock_disk_util, "mock_passphrase_file", None)
        self.assertEquals(_do_exit_side_effect.exit_message, "Dummy Error")

        # Case 3: disk stamping throws exception
        mock_mig_allow.return_value = True, None
        mock_stamp.side_effect = Exception("Dummy Exception")
        handle.perform_migration(mock_disk_util, "mock_passphrase_file", None)
        self.assertEquals(_do_exit_side_effect.exit_message, "Dummy Exception")