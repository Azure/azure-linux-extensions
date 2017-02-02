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

import os
import os.path
import subprocess
from subprocess import *

class EncryptionEnvironment(object):
    """description of class"""
    def __init__(self, patching, logger):
        self.patching = patching
        self.logger = logger
        self.encryption_config_path = '/var/lib/azure_disk_encryption_config/'
        self.daemon_lock_file_path = os.path.join(self.encryption_config_path, 'daemon_lock_file.lck')
        self.encryption_config_file_path = os.path.join(self.encryption_config_path, 'azure_crypt_config.ini')
        self.extension_parameter_file_path = os.path.join(self.encryption_config_path, 'azure_crypt_params.ini')
        self.azure_crypt_mount_config_path = os.path.join(self.encryption_config_path, 'azure_crypt_mount')
        self.azure_crypt_request_queue_path = os.path.join(self.encryption_config_path, 'azure_crypt_request_queue.ini')
        self.azure_decrypt_request_queue_path = os.path.join(self.encryption_config_path, 'azure_decrypt_request_queue.ini')
        self.azure_crypt_ongoing_item_config_path = os.path.join(self.encryption_config_path, 'azure_crypt_ongoing_item.ini')
        self.azure_crypt_current_transactional_copy_path = os.path.join(self.encryption_config_path, 'azure_crypt_copy_progress.ini')
        self.luks_header_base_path = os.path.join(self.encryption_config_path, 'azureluksheader')
        self.cleartext_key_base_path = os.path.join(self.encryption_config_path, 'cleartext_key')
        self.copy_header_slice_file_path = os.path.join(self.encryption_config_path, 'copy_header_slice_file')
        self.copy_slice_item_backup_file = os.path.join(self.encryption_config_path, 'copy_slice_item.bak')
        self.os_encryption_markers_path = os.path.join(self.encryption_config_path, 'os_encryption_markers')
        self.bek_backup_path = os.path.join(self.encryption_config_path, 'bek_backup')

    def get_se_linux(self):
        proc = Popen([self.patching.getenforce_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity, err = proc.communicate()
        return identity.strip().lower()

    def disable_se_linux(self):
        self.logger.log("disabling se linux")
        proc = Popen([self.patching.setenforce_path,'0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return_code = proc.wait()
        return return_code

    def enable_se_linux(self):
        self.logger.log("enabling se linux")
        proc = Popen([self.patching.setenforce_path,'1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return_code = proc.wait()
        return return_code
