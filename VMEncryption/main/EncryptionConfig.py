#!/usr/bin/env python
#
# VM Backup extension
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

import os
import datetime
import os.path
from Common import CommonVariables
from ConfigParser import ConfigParser
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair
class EncryptionConfig(object):
    def __init__(self, encryption_environment,logger):
        self.encryptionEnvironment = encryption_environment
        self.passphrase_file_name = None
        self.bek_filesystem = None
        self.volume_type = None
        self.secret_id = None
        self.encryption_config = ConfigUtil(encryption_environment.encryption_config_file_path,'azure_crypt_config',logger)
        self.logger = logger


    def config_file_exists(self):
        return self.encryption_config.config_file_exists()

    def get_bek_filename(self):
        return self.encryption_config.get_config(CommonVariables.PassphraseFileNameKey)

    def get_bek_filesystem(self):
        return self.encryption_config.get_config(CommonVariables.BekVolumeFileSystemKey)

    def get_secret_id(self):
        return self.encryption_config.get_config(CommonVariables.SecretUriKey)

    def commit(self):
        key_value_pairs = []
        command = ConfigKeyValuePair(CommonVariables.PassphraseFileNameKey,self.passphrase_file_name)
        key_value_pairs.append(command)
        bek_file_system = ConfigKeyValuePair(CommonVariables.BekVolumeFileSystemKey,CommonVariables.BekVolumeFileSystem)
        key_value_pairs.append(bek_file_system)
        parameters = ConfigKeyValuePair(CommonVariables.SecretUriKey,self.secret_id)
        key_value_pairs.append(parameters)
        self.encryption_config.save_configs(key_value_pairs)

    def clear_config(self):
        try:
            if(os.path.exists(self.encryptionEnvironment.encryption_config_file_path)):
                self.logger.log(msg="archiving the encryption config file: {0}".format(self.encryptionEnvironment.encryption_config_file_path))
                time_stamp = datetime.datetime.now()
                new_name = "{0}_{1}".format(self.encryptionEnvironment.encryption_config_file_path, time_stamp)
                os.rename(self.encryptionEnvironment.encryption_config_file_path, new_name)
            else:
                self.logger.log(msg=("the config file not exist: {0}".format(self.encryptionEnvironment.encryption_config_file_path)), level = CommonVariables.WarningLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive encryption config with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return False
