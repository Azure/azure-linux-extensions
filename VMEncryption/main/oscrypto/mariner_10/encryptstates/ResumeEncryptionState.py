#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2020 Microsoft Corporation
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
#
# Requires Python 2.7+
#

import os

from OSEncryptionState import OSEncryptionState
from OnlineEncryptionResumer import OnlineEncryptionResumer
from Common import CryptItem


class ResumeEncryptionState(OSEncryptionState):
    def __init__(self, context):
        super(ResumeEncryptionState, self).__init__('ResumeEncryptionState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter resume_encryption state")

        if not super(ResumeEncryptionState, self).should_enter():
            return False

        self.context.logger.log("Performing enter checks for resume_encryption state")
        if not os.path.exists('/dev/mapper/osencrypt'):
            self.context.logger.log("osencrypt device mapper does not exist. Cannot do a resume.")
            return False

        return self.disk_util.luks_check_reencryption(self.rootfs_block_device, '/boot/luks/osluksheader')

    def enter(self):
        if not self.should_enter():
            return

        bek_path = self.bek_util.get_bek_passphrase_file(self.encryption_config)

        crypt_item = CryptItem()
        crypt_item.dev_path = self.rootfs_block_device
        crypt_item.mapper_name = "osencrypt"
        crypt_item.mount_point = "/"
        crypt_item.uses_cleartext_key = False
        crypt_item.luks_header_path = "/boot/luks/osluksheader"

        OnlineEncryptionResumer(crypt_item, self.disk_util, bek_path, self.context.logger, self.context.hutil).begin_resume()

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit resume_encryption state")

        if self.disk_util.luks_check_reencryption(self.rootfs_block_device, '/boot/luks/osluksheader'):
            return False
        super(ResumeEncryptionState, self).should_exit()
        return True
