#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2015 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import xml.parsers.expat

from DiskUtil import DiskUtil
from BekUtil import BekUtil
from EncryptionConfig import EncryptionConfig
from Utils import HandlerUtil
from Common import *
from ConfigParser import ConfigParser
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair

# parameter format should be like this:
#{"command":"enableencryption","query":[{"source_scsi_number":"[5:0:0:0]","target_scsi_number":"[5:0:0:2]"},{"source_scsi_number":"[5:0:0:1]","target_scsi_number":"[5:0:0:3]"}],
#"force":"true", "passphrase":"User@123"}
class ExtensionParameter(object):
    def __init__(self, hutil, logger, distro_patcher, encryption_environment, protected_settings, public_settings):
        """
        TODO: we should validate the parameter first
        """
        self.hutil = hutil
        self.logger = logger
        self.distro_patcher = distro_patcher
        self.encryption_environment = encryption_environment

        self.disk_util = DiskUtil(hutil=hutil, patching=distro_patcher, logger=logger, encryption_environment=encryption_environment)
        self.bek_util = BekUtil(self.disk_util, logger)
        self.encryption_config = EncryptionConfig(encryption_environment, logger)

        self.command = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        self.KeyEncryptionKeyURL = public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        self.KeyVaultURL = public_settings.get(CommonVariables.KeyVaultURLKey)
        self.AADClientID = public_settings.get(CommonVariables.AADClientIDKey)
        self.AADClientCertThumbprint = public_settings.get(CommonVariables.AADClientCertThumbprintKey)

        keyEncryptionAlgorithm = public_settings.get(CommonVariables.KeyEncryptionAlgorithmKey)
        if keyEncryptionAlgorithm is not None and keyEncryptionAlgorithm !="":
            self.KeyEncryptionAlgorithm = keyEncryptionAlgorithm
        else:
            self.KeyEncryptionAlgorithm = 'RSA-OAEP'

        self.VolumeType = public_settings.get(CommonVariables.VolumeTypeKey)
        self.DiskFormatQuery = public_settings.get(CommonVariables.DiskFormatQuerykey)

        """
        private settings
        """
        self.AADClientSecret = protected_settings.get(CommonVariables.AADClientSecretKey)

        if self.AADClientSecret is None:
            self.AADClientSecret = ''

        self.passphrase = protected_settings.get(CommonVariables.PassphraseKey)

        self.DiskEncryptionKeyFileName = "LinuxPassPhraseFileName"
        # parse the query from the array

        self.params_config = ConfigUtil(encryption_environment.extension_parameter_file_path,
                                        'azure_extension_params',
                                        logger)

    def config_file_exists(self):
        return self.params_config.config_file_exists()

    def get_command(self):
        return self.params_config.get_config(CommonVariables.EncryptionEncryptionOperationKey)

    def get_kek_url(self):
        return self.params_config.get_config(CommonVariables.KeyEncryptionKeyURLKey)

    def get_keyvault_url(self):
        return self.params_config.get_config(CommonVariables.KeyVaultURLKey)

    def get_aad_client_id(self):
        return self.params_config.get_config(CommonVariables.AADClientIDKey)

    def get_aad_client_secret(self):
        return self.params_config.get_config(CommonVariables.AADClientSecretKey)

    def get_aad_client_cert(self):
        return self.params_config.get_config(CommonVariables.AADClientCertThumbprintKey)

    def get_kek_algorithm(self):
        return self.params_config.get_config(CommonVariables.KeyEncryptionAlgorithmKey)

    def get_volume_type(self):
        return self.params_config.get_config(CommonVariables.VolumeTypeKey)

    def get_disk_format_query(self):
        return self.params_config.get_config(CommonVariables.DiskFormatQuerykey)

    def get_bek_filename(self):
        return self.DiskEncryptionKeyFileName

    def commit(self):
        key_value_pairs = []

        command = ConfigKeyValuePair(CommonVariables.EncryptionEncryptionOperationKey, self.command)
        key_value_pairs.append(command)

        KeyEncryptionKeyURL = ConfigKeyValuePair(CommonVariables.KeyEncryptionKeyURLKey, self.KeyEncryptionKeyURL)
        key_value_pairs.append(KeyEncryptionKeyURL)

        KeyVaultURL = ConfigKeyValuePair(CommonVariables.KeyVaultURLKey, self.KeyVaultURL)
        key_value_pairs.append(KeyVaultURL)

        AADClientID = ConfigKeyValuePair(CommonVariables.AADClientIDKey, self.AADClientID)
        key_value_pairs.append(AADClientID)

        AADClientSecret = ConfigKeyValuePair(CommonVariables.AADClientSecretKey, hashlib.sha256(self.AADClientSecret.encode("utf-8")).hexdigest())
        key_value_pairs.append(AADClientSecret)

        AADClientCertThumbprint = ConfigKeyValuePair(CommonVariables.AADClientCertThumbprintKey, self.AADClientCertThumbprint)
        key_value_pairs.append(AADClientCertThumbprint)

        KeyEncryptionAlgorithm = ConfigKeyValuePair(CommonVariables.KeyEncryptionAlgorithmKey, self.KeyEncryptionAlgorithm)
        key_value_pairs.append(KeyEncryptionAlgorithm)

        VolumeType = ConfigKeyValuePair(CommonVariables.VolumeTypeKey, self.VolumeType)
        key_value_pairs.append(VolumeType)

        DiskFormatQuery = ConfigKeyValuePair(CommonVariables.DiskFormatQuerykey, self.DiskFormatQuery)
        key_value_pairs.append(DiskFormatQuery)

        self.params_config.save_configs(key_value_pairs)

    def clear_config(self):
        try:
            if os.path.exists(self.encryption_environment.encryption_config_file_path):
                self.logger.log(msg="archiving the encryption config file: {0}".format(self.encryption_environment.encryption_config_file_path))
                time_stamp = datetime.datetime.now()
                new_name = "{0}_{1}".format(self.encryption_environment.encryption_config_file_path, time_stamp)
                os.rename(self.encryption_environment.encryption_config_file_path, new_name)
            else:
                self.logger.log(msg=("the config file not exist: {0}".format(self.encryption_environment.encryption_config_file_path)), level = CommonVariables.WarningLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive encryption config with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return False

    def config_changed(self):
        if (self.command or self.get_command()) and \
           (self.command != self.get_command()):
            self.logger.log('Current config command {0} differs from effective config command {1}'.format(self.command, self.get_command()))
            return True

        if (self.KeyEncryptionKeyURL or self.get_kek_url()) and \
           (self.KeyEncryptionKeyURL != self.get_kek_url()):
            self.logger.log('Current config KeyEncryptionKeyURL {0} differs from effective config KeyEncryptionKeyURL {1}'.format(self.KeyEncryptionKeyURL, self.get_kek_url()))
            return True

        if (self.KeyVaultURL or self.get_keyvault_url()) and \
           (self.KeyVaultURL != self.get_keyvault_url()):
            self.logger.log('Current config KeyVaultURL {0} differs from effective config KeyVaultURL {1}'.format(self.KeyVaultURL, self.get_keyvault_url()))
            return True

        if (self.AADClientID or self.get_aad_client_id()) and \
           (self.AADClientID != self.get_aad_client_id()):
            self.logger.log('Current config AADClientID {0} differs from effective config AADClientID {1}'.format(self.AADClientID, self.get_aad_client_id()))
            return True

        if (self.AADClientSecret or self.get_aad_client_secret()) and \
           (hashlib.sha256(self.AADClientSecret.encode("utf-8")).hexdigest() != self.get_aad_client_secret()):
            self.logger.log('Current config AADClientSecret {0} differs from effective config AADClientSecret {1}'.format(hashlib.sha256(self.AADClientSecret.encode("utf-8")).hexdigest(),
                                                                                                                          self.get_aad_client_secret()))
            return True

        if (self.AADClientCertThumbprint or self.get_aad_client_cert()) and \
           (self.AADClientCertThumbprint != self.get_aad_client_cert()):
            self.logger.log('Current config AADClientCertThumbprint {0} differs from effective config AADClientCertThumbprint {1}'.format(self.AADClientCertThumbprint, self.get_aad_client_cert()))
            return True

        if (self.KeyEncryptionAlgorithm or self.get_kek_algorithm()) and \
           (self.KeyEncryptionAlgorithm != self.get_kek_algorithm()):
            self.logger.log('Current config KeyEncryptionAlgorithm {0} differs from effective config KeyEncryptionAlgorithm {1}'.format(self.KeyEncryptionAlgorithm, self.get_kek_algorithm()))
            return True

        if (self.DiskFormatQuery or self.get_disk_format_query()) and \
           (self.DiskFormatQuery != self.get_disk_format_query()):
            self.logger.log('Current config DiskFormatQuery {0} differs from effective config DiskFormatQuery {1}'.format(self.DiskFormatQuery, self.get_disk_format_query()))
            return True

        bek_passphrase_file = self.bek_util.get_bek_passphrase_file(self.encryption_config)
        bek_passphrase = file(bek_passphrase_file).read()

        if (self.passphrase and bek_passphrase) and \
           (self.passphrase != bek_passphrase):
            self.logger.log('Current config passphrase differs from effective config passphrase')
            return True
   
        self.logger.log('Current config is not different from effective config')
        return False
