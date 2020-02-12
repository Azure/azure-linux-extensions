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

""" Unit tests for the HandlerUtil module """

import unittest
import os
from . import console_logger
import glob
from Utils import HandlerUtil
from tempfile import mkstemp
try:
    import patch #python3+
except ImportError:
    from mock import patch # python2

class TestHandlerUtil(unittest.TestCase):
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.distro_patcher = patch.GetDistroPatcher(self.logger)
        self.hutil = HandlerUtil.HandlerUtility(self.logger.log, self.logger.error, "AzureDiskEncryptionForLinux")
        self.hutil.patching = self.distro_patcher
        # invoke unit test from within main for setup (to avoid having to change dependencies)
        handlerPath = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        handlerEnvPath = os.path.join(handlerPath, "HandlerEnvironment.json")
        handlerManPath = os.path.join(handlerPath, "HandlerManifest.json")
        configPath = os.path.join(handlerPath, "config")
        settingsFilePath = os.path.join(configPath,"0.settings")
        handlerEnvJson = '[{"handlerEnvironment":{"statusFolder":"/tmp","logFolder":"/tmp","configFolder":"' + configPath + '","heartbeatFile":"/tmp/heartbeat.log"},"version":1.0,"name":"Microsoft.Azure.Security.AzureDiskEncryptionForLinux"}]'
        handlerManJson = '[{"handlerManifest":{"disableCommand":"disable","enableCommand":"enable","installCommand":"install","rebootAfterInstall":false,"reportHeartbeat":false,"uninstallCommand":"uninstall","updateCommand":"update"},"name":"AzureDiskEncryptionForLinux","version":"1.0"}]'
        settingsFileJson = '{"runtimeSettings": [{"handlerSettings": {"protectedSettings": null, "publicSettings": {"VolumeType": "OS", "KeyEncryptionKeyURL": "", "KekVaultResourceId": "", "KeyEncryptionAlgorithm": "RSA-OAEP", "KeyVaultURL": "https://testkv.vault.azure.net/", "KeyVaultResourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/testrg/providers/Microsoft.KeyVault/vaults/testkv", "EncryptionOperation": "EnableEncryption"}, "protectedSettingsCertThumbprint": null} }]}'
        if not os.path.isfile(handlerEnvPath):
            with open(handlerEnvPath, "w") as outfile:
                outfile.write(handlerEnvJson)
        if not os.path.isfile(handlerManPath):
            with open(handlerManPath, "w") as outfile:
                outfile.write(handlerManJson)
        if not os.path.isdir(configPath):
            os.mkdir(configPath)
        if not os.path.isfile(settingsFilePath):
            with open(settingsFilePath, "w") as outfile:
                outfile.write(settingsFileJson)
        self.hutil._context._seq_no = 0
        self.hutil._context._settings_file = settingsFilePath
        self.hutil._context._config_dir = configPath
            
    def test_parse_config_sp(self):
        # test 0.1 sp config syntax
        test_sp = '{"runtimeSettings": [{"handlerSettings": {"protectedSettings": null, "publicSettings": {"VolumeType": "OS", "KeyEncryptionKeyURL": "", "KekVaultResourceId": "", "KeyEncryptionAlgorithm": "RSA-OAEP", "KeyVaultURL": "https://testkv.vault.azure.net/", "KeyVaultResourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/testrg/providers/Microsoft.KeyVault/vaults/testkv", "EncryptionOperation": "EnableEncryption"}, "protectedSettingsCertThumbprint": null} }]}'
        self.assertIsNotNone(self.hutil._parse_config(test_sp))

    def test_do_parse_context_install(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Install'))

    def test_do_parse_context_enable(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))

    def test_do_parse_context_enable_encryption(self):
        self.assertIsNotNone(self.hutil.do_parse_context('EnableEncryption'))
        
    def test_do_parse_context_disable(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Disable'))

    def test_do_parse_context_disable_nosettings(self):
        # simulate missing settings file by adding .bak extension
        config_dir = os.path.join(os.getcwd(), 'config')
        settings_files = glob.glob(os.path.join(config_dir, '*.settings'))
        for settings_file in settings_files:
            os.rename(settings_file, settings_file + '.bak')
        try:
            # test to simulate disable when no settings are available
            self.hutil.do_parse_context('Disable')
            self.hutil.archive_old_configs()
        finally:
            # restore settings files back to original name
            for settings_file in settings_files:
                os.rename(settings_file + '.bak', settings_file)

    def test_do_parse_context_uninstall(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Uninstall'))

    def test_do_parse_context_disable_encryption(self):
        self.assertIsNotNone(self.hutil.do_parse_context('DisableEncryption'))

    def test_do_parse_context_update_encryption_settings(self):
        self.assertIsNotNone(self.hutil.do_parse_context('UpdateEncryptionSettings'))

    def test_do_parse_context_update(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Update'))

    def test_do_parse_context_executing(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Executing'))

    def test_try_parse_context(self):
        self.assertIsNotNone(self.hutil.try_parse_context())

    def test_is_valid_nonquery_true(self):
        nonquery_settings = '{"runtimeSettings": [{"handlerSettings": {"protectedSettingsCertThumbprint": null, "publicSettings": {"VolumeType": "DATA", "KekVaultResourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/testrg/providers/Microsoft.KeyVault/vaults/testkv", "EncryptionOperation": "EnableEncryption", "KeyEncryptionAlgorithm": "RSA-OAEP", "KeyEncryptionKeyURL": "https://testkv.vault.azure.net/keys/testkek/805291e00028474a87e302ce507ed049", "KeyVaultURL": "https://testkv.vault.azure.net", "KeyVaultResourceId": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/testrg/providers/Microsoft.KeyVault/vaults/testkv", "SequenceVersion": "c8608bb5-df18-43a7-9f0e-dbe09a57fd0b"}, "protectedSettings": null} }]}'

        # use a temp file path for this test, not the config folder
        tmp_fd, tmp_path = mkstemp(text=True)
        with os.fdopen(tmp_fd,'w') as f:
            f.write(nonquery_settings)
        test_result = self.hutil.is_valid_nonquery(tmp_path)
        os.remove(tmp_path)

        # assert true, this is not a QueryEncryptionStatus operation
        self.assertTrue(test_result)

    def test_is_valid_nonquery_false(self):
        query_settings = '{"runtimeSettings": [{"handlerSettings": {"protectedSettings": "MIIBsAYJKoZIhvcNAQcDoIIBoTCCAZ0CAQAxggFpMIIBZQIBADBNMDkxNzA1BgoJkiaJk/IsZAEZFidXaW5kb3dzIEF6dXJlIENSUCBDZXJ0aWZpY2F0ZSBHZW5lcmF0b3ICEG5XyHr6J9qxRLVe/RzaobIwDQYJKoZIhvcNAQEBBQAEggEAE92LccPctK0h52F+WOjKPWat5O3nxjQpsLKquMtwiKsc5BMot8dLEAE1h7V7SJJ8kiGRLS232mwvVbOA+nOs3l1lCUNDnckbzvvuu/rgz+if1sHvYIn0Xd/kXHSMNm9loh9lTLagGblEFxGupcBcsAEptcjL0f7zUG1NrlnKPVDGceOw7I3dQK6X8rPrMHJ8m6wiHpTvjpa/xmG0mrVyOGjJv7cEDnJ0A8pvRHUrZGGuqi/4WeGPGDKQzmVc6O5oGFfke3bAOd9GJxFWhLwZ1lb1XrKNImVDT2vnWWFiy2lKDwUvKSdqRpaqRNr6f7tZcDWiB+v+vZ6V4GC33kT0mDArBgkqhkiG9w0BBwEwFAYIKoZIhvcNAwcECJeXx+KpPZqdgAgiUsAz+Acz6A==", "publicSettings": {"SequenceVersion": "3838692e-4827-4175-8286-86828d199f85", "EncryptionOperation": "QueryEncryptionStatus"}, "protectedSettingsCertThumbprint": "45E4EC25EECAD03EC81F8177CEF16CD3CAF6297A"} }]}'

        # use a temp file path for this test, not the config folder
        tmp_fd, tmp_path = mkstemp(text=True)
        with os.fdopen(tmp_fd,'w') as f:
            f.write(query_settings)
        test_result = self.hutil.is_valid_nonquery(tmp_path)
        os.remove(tmp_path)
        
        # assert false, this is a QueryEncryptionStatus operation
        self.assertFalse(test_result)

    def test_get_last_nonquery_config_path(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))
        self.assertIsNotNone(self.hutil.get_last_nonquery_config_path())

    def test_get_last_config(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))
        self.assertIsNotNone(self.hutil.get_last_config(nonquery=False))

    def test_get_last_nonquery_config(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))
        config = self.hutil.get_last_config(nonquery=True)
        self.assertIsNotNone(config)        

    def test_get_handler_env(self):
        self.assertIsNotNone(self.hutil.get_handler_env())

    def test_archive_old_configs(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))
        self.hutil.archive_old_configs()

    def test_archive_old_configs_overwrite_lnq(self):
        self.assertIsNotNone(self.hutil.do_parse_context('Enable'))

        # this test ensures that the archive_old_configs method will properly overwrite an existing lnq.settings file
        # with any newer non query settings file that might exist on the system 

        # stuff a bogus lnq.settings file in the archived settings folder
        # and backdate the file time to older than current settings prior to testing
        tmpstr = 'test_archive_old_configs_overwrite_lnq : the contents of this file are intended to be overwritten and never used'
        if not os.path.exists(self.hutil.config_archive_folder):
            os.makedirs(self.hutil.config_archive_folder)
        dest = os.path.join(self.hutil.config_archive_folder, 'lnq.settings')
        with open(dest,'w') as f:
            f.write(tmpstr)

        # backdate
        os.utime(dest,(0,0))

        # run the test 
        self.hutil.archive_old_configs()

        # ensure the new lnq.settings file in the folder has the expected content 
