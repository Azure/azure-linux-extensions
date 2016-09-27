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

import os.path

from collections import namedtuple

from Common import *
from CommandExecutor import *
from BekUtil import *
from DiskUtil import *
from EncryptionConfig import *

class OSEncryptionState(object):
    def __init__(self, state_name, context):
        super(OSEncryptionState, self).__init__()

        self.state_name = state_name
        self.context = context
        self.state_executed = False
        self.state_marker = os.path.join(self.context.encryption_environment.os_encryption_markers_path, self.state_name)

        self.command_executor = CommandExecutor(self.context.logger)

        self.disk_util = DiskUtil(hutil=self.context.hutil,
                                  patching=self.context.distro_patcher,
                                  logger=self.context.logger,
                                  encryption_environment=self.context.encryption_environment)

        self.bek_util = BekUtil(disk_util=self.disk_util,
                                logger=self.context.logger)

        self.encryption_config = EncryptionConfig(encryption_environment=self.context.encryption_environment,
                                                  logger=self.context.logger)

        rootfs_mountpoint = '/'

        if self.command_executor.Execute('mountpoint /oldroot') == 0:
            rootfs_mountpoint = '/oldroot'

        rootfs_sdx_path = self._get_fs_partition(rootfs_mountpoint)[0]
        self.context.logger.log("rootfs_sdx_path: {0}".format(rootfs_sdx_path))

        self.rootfs_block_device = self.disk_util.query_dev_id_path_by_sdx_path(rootfs_sdx_path)
        if not self.rootfs_block_device.startswith('/dev'):
            distro_name = self.context.distro_patcher.distro_info[0]
            self.rootfs_block_device = '/dev/sda1' if distro_name == 'Ubuntu' else '/dev/sda2'
        self.context.logger.log("rootfs_block_device: {0}".format(self.rootfs_block_device))
        
    def should_enter(self):
        self.context.logger.log("OSEncryptionState.should_enter() called for {0}".format(self.state_name))

        if self.state_executed:
            self.context.logger.log("State {0} has already executed, not entering".format(self.state_name))
            return False

        if not os.path.exists(self.state_marker):
            self.context.logger.log("State marker {0} does not exist, state {1} can be entered".format(self.state_marker,
                                                                                                       self.state_name))

            return True
        else:
            self.context.logger.log("State marker {0} exists, state {1} has already executed".format(self.state_marker,
                                                                                                     self.state_name))
            return False

    def should_exit(self):
        self.context.logger.log("OSEncryptionState.should_exit() called for {0}".format(self.state_name))

        if not os.path.exists(self.state_marker):
            self.disk_util.make_sure_path_exists(self.context.encryption_environment.os_encryption_markers_path)
            self.context.logger.log("Creating state marker {0}".format(self.state_marker))
            self.disk_util.touch_file(self.state_marker)

        self.state_executed = True

        self.context.logger.log("state_executed for {0}: {1}".format(self.state_name, self.state_executed))

        return self.state_executed

    def _get_fs_partition(self, fs):
        result = None
        dev = os.lstat(fs).st_dev

        for line in file('/proc/mounts'):
            line = [s.decode('string_escape') for s in line.split()[:3]]
            if dev == os.lstat(line[1]).st_dev:
                result = tuple(line)

        return result

OSEncryptionStateContext = namedtuple('OSEncryptionStateContext',
                                      ['hutil',
                                       'distro_patcher',
                                       'logger',
                                       'encryption_environment'])
