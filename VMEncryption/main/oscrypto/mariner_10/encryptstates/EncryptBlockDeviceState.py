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
#
# Requires Python 2.7+
#

import os
import sys

from inspect import ismethod
from time import sleep
from OSEncryptionState import *
from distutils.version import LooseVersion

class EncryptBlockDeviceState(OSEncryptionState):
    def __init__(self, context):
        super(EncryptBlockDeviceState, self).__init__('EncryptBlockDeviceState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter encrypt_block_device state")

        if not super(EncryptBlockDeviceState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for encrypt_block_device state")
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering encrypt_block_device state")
        
        self.command_executor.Execute('mount /boot', False)

        self._find_bek_and_execute_action('_luks_format')
        self._find_bek_and_execute_action('_luks_open')

        self.context.hutil.do_status_report(operation='EnableEncryptionDataVolumes',
                                            status=CommonVariables.extension_success_status,
                                            status_code=str(CommonVariables.success),
                                            message='OS disk encryption started')
        
        # Enable used space encryption on RHEL 7.3 and above
        distro_info = self.context.distro_patcher.distro_info
        if LooseVersion(distro_info[1]) >= LooseVersion('7.3'):
            self.command_executor.Execute('dd if={0} of=/dev/mapper/osencrypt conv=sparse bs=64K'.format(self.rootfs_block_device), True)
        else:
            self.command_executor.Execute('dd if={0} of=/dev/mapper/osencrypt bs=52428800'.format(self.rootfs_block_device), True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit encrypt_block_device state")

        if not os.path.exists('/dev/mapper/osencrypt'):
            self._find_bek_and_execute_action('_luks_open')

        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.Execute('umount /oldroot', True)

        return super(EncryptBlockDeviceState, self).should_exit()

    def _luks_format(self, bek_path):
        self.command_executor.Execute('mkdir /boot/luks', True)
        self.command_executor.Execute('dd if=/dev/zero of=/boot/luks/osluksheader bs=33554432 count=1', True)
        self.command_executor.Execute('cryptsetup luksFormat --header /boot/luks/osluksheader -d {0} {1} -q'.format(bek_path,
                                                                                                                    self.rootfs_block_device),
                                      raise_exception_on_failure=True)

    def _luks_open(self, bek_path):
        self.command_executor.Execute('cryptsetup luksOpen --header /boot/luks/osluksheader {0} osencrypt -d {1}'.format(self.rootfs_block_device,
                                                                                                                         bek_path),
                                      raise_exception_on_failure=True)

    def _find_bek_and_execute_action(self, callback_method_name):
        callback_method = getattr(self, callback_method_name)
        if not ismethod(callback_method):
            raise Exception("{0} is not a method".format(callback_method_name))

        bek_path = self.bek_util.get_bek_passphrase_file(self.encryption_config)
        callback_method(bek_path)      