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
import os.path
import traceback
from ConfigUtil import *
from Common import CommonVariables

class DecryptionMarkConfig(object):
    def __init__(self, logger, encryption_environment):
        self.logger = logger
        self.encryption_environment = encryption_environment
        self.command = None
        self.volume_type = None
        self.decryption_mark_config = ConfigUtil(self.encryption_environment.azure_decrypt_request_queue_path,
                                                 'decryption_request_queue',
                                                 self.logger)

    def get_current_command(self):
        return self.decryption_mark_config.get_config(CommonVariables.EncryptionEncryptionOperationKey)

    def config_file_exists(self):
        return self.decryption_mark_config.config_file_exists()
    
    def commit(self):
        key_value_pairs = []

        command = ConfigKeyValuePair(CommonVariables.EncryptionEncryptionOperationKey, self.command)
        key_value_pairs.append(command)

        volume_type = ConfigKeyValuePair(CommonVariables.EncryptionVolumeTypeKey, self.volume_type)
        key_value_pairs.append(volume_type)

        self.decryption_mark_config.save_configs(key_value_pairs)

    def clear_config(self):
        try:
            if(os.path.exists(self.encryption_environment.azure_decrypt_request_queue_path)):
                os.remove(self.encryption_environment.azure_decrypt_request_queue_path)
            return True
        except OSError as e:
            self.logger.log("Failed to clear_queue with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return False
