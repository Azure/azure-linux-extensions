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

import re
import os
import sys

from inspect import ismethod
from time import sleep
from OSEncryptionState import *

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

        self.context.logger.log("Resizing " + self.rootfs_block_device)

        current_rootfs_size = self._get_root_fs_size_in_sectors(sector_size=512)
        desired_rootfs_size = current_rootfs_size - 8192
        
        self.command_executor.Execute('e2fsck -yf {0}'.format(self.rootfs_block_device), True)
        self.command_executor.Execute('resize2fs {0} {1}s'.format(self.rootfs_block_device, desired_rootfs_size), True)
        
        self.command_executor.Execute('mount /boot', False)
        # self._find_bek_and_execute_action('_dump_passphrase')

        self.context.hutil.do_status_report(operation='EnableEncryptionDataVolumes',
                                            status=CommonVariables.extension_success_status,
                                            status_code=str(CommonVariables.success),
                                            message='OS disk encryption started')

        self._find_bek_and_execute_action('_luks_reencrypt')

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit encrypt_block_device state")

        if not os.path.exists('/dev/mapper/osencrypt'):
            self._find_bek_and_execute_action('_luks_open')

        self.command_executor.Execute('mount /dev/mapper/osencrypt /oldroot', True)
        self.command_executor.Execute('umount /oldroot', True)

        return super(EncryptBlockDeviceState, self).should_exit()

    def _luks_open(self, bek_path):
        self.command_executor.Execute('cryptsetup luksOpen {0} osencrypt -d {1}'.format(self.rootfs_block_device, bek_path),
                                      raise_exception_on_failure=True)

    def _luks_reencrypt(self, bek_path):
        self.command_executor.ExecuteInBash('cat {0} | cryptsetup-reencrypt -N --reduce-device-size 8192s {1} -v'.format(bek_path,
                                                                                                                         self.rootfs_block_device),
                                            raise_exception_on_failure=True)

    def _dump_passphrase(self, bek_path):
        proc_comm = ProcessCommunicator()

        self.command_executor.Execute(command_to_execute="od -c {0}".format(bek_path),
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        self.context.logger.log("Passphrase:")
        self.context.logger.log(proc_comm.stdout)

    def _find_bek_and_execute_action(self, callback_method_name):
        callback_method = getattr(self, callback_method_name)
        if not ismethod(callback_method):
            raise Exception("{0} is not a method".format(callback_method_name))

        bek_path = self.bek_util.get_bek_passphrase_file(self.encryption_config)
        callback_method(bek_path)    

    def _get_root_fs_size_in_sectors(self, sector_size):
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(command_to_execute="dumpe2fs -h {0}".format(self.rootfs_block_device),
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)

        root_fs_block_count = re.findall(r'Block count:\s*(\d+)', proc_comm.stdout)
        root_fs_block_size = re.findall(r'Block size:\s*(\d+)', proc_comm.stdout)

        if not root_fs_block_count or not root_fs_block_size:
            raise Exception("Error parsing dumpe2fs output, count={0}, size={1}".format(root_fs_block_count,
                                                                                        root_fs_block_size))

        root_fs_block_count = int(root_fs_block_count[0])
        root_fs_block_size = int(root_fs_block_size[0])

        return (root_fs_block_count * root_fs_block_size) / sector_size
