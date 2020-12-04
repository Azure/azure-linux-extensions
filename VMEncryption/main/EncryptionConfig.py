#!/usr/bin/env python
#
# Azure Disk Encryption For Linux extension
#
# Copyright 2016 Microsoft Corporation
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

import os
import datetime
import os.path
import sys
import traceback

from Common import CommonVariables
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair


class EncryptionConfig(object):
    def __init__(self, encryption_environment, logger):
        self.encryption_environment = encryption_environment
        self.passphrase_file_name = None
        self.volume_type = None
        self.secret_id = None
        self.secret_seq_num = None
        self.encryption_config = ConfigUtil(encryption_environment.encryption_config_file_path,
                                            'azure_crypt_config',
                                            logger)
        self.logger = logger

    def config_file_exists(self):
        return self.encryption_config.config_file_exists()

    def get_bek_filename(self):
        bek_filename = self.encryption_config.get_config(CommonVariables.PassphraseFileNameKey)

        return bek_filename if bek_filename else self.encryption_environment.default_bek_filename

    def get_volume_type(self):
        return self.encryption_config.get_config(CommonVariables.VolumeTypeKey)

#    def get_secret_id(self):
#        return self.encryption_config.get_config(CommonVariables.SecretUriKey)

    def get_secret_seq_num(self):
        return self.encryption_config.get_config(CommonVariables.SecretSeqNum)

    def get_cfg_val(self, s):
        # return a string type that is compatible with the version of config parser that is in use
        if s is None:
            return ""

        if (sys.version_info > (3, 0)):
            return s  # python 3+ , preserve unicode
        else:
            if isinstance(s, unicode):
                # python2 ConfigParser does not properly support unicode, convert to ascii
                return s.encode('ascii', 'ignore')
            else:
                return s

    def commit(self):
        key_value_pairs = []

        u_pfn_key = CommonVariables.PassphraseFileNameKey
        u_pfn_val = self.get_cfg_val(self.passphrase_file_name)
        u_vol_key = CommonVariables.VolumeTypeKey
        u_vol_val = self.get_cfg_val(self.volume_type)
        u_seq_key = CommonVariables.SecretSeqNum
        u_seq_val = self.get_cfg_val(self.secret_seq_num)

        # construct kvp collection
        command = ConfigKeyValuePair(u_pfn_key, u_pfn_val)
        key_value_pairs.append(command)
        volume_type = ConfigKeyValuePair(u_vol_key, u_vol_val)
        key_value_pairs.append(volume_type)
        parameters = ConfigKeyValuePair(u_seq_key, u_seq_val)
        key_value_pairs.append(parameters)

        # save settings in the configuration file
        self.encryption_config.save_configs(key_value_pairs)

    def clear_config(self, clear_parameter_file=False):
        try:
            if os.path.exists(self.encryption_environment.encryption_config_file_path):
                self.logger.log(msg="archiving the encryption config file: {0}".format(self.encryption_environment.encryption_config_file_path))
                time_stamp = datetime.datetime.now()
                new_name = "{0}_{1}".format(self.encryption_environment.encryption_config_file_path, time_stamp)
                os.rename(self.encryption_environment.encryption_config_file_path, new_name)
            else:
                self.logger.log(msg=("the config file not exist: {0}".format(self.encryption_environment.encryption_config_file_path)), level=CommonVariables.WarningLevel)
            if clear_parameter_file:
                if os.path.exists(self.encryption_environment.extension_parameter_file_path):
                    self.logger.log(msg="archiving the encryption parameter file: {0}".format(self.encryption_environment.extension_parameter_file_path))
                    time_stamp = datetime.datetime.now()
                    new_name = "{0}_{1}".format(self.encryption_environment.extension_parameter_file_path, time_stamp)
                    os.rename(self.encryption_environment.extension_parameter_file_path, new_name)
                else:
                    self.logger.log(msg=("the parameter file not exist: {0}".format(self.encryption_environment.extension_parameter_file_path)), level=CommonVariables.InfoLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive encryption config with error: {0}, stack trace: {1}".format(printable(e), traceback.format_exc()))
            return False
