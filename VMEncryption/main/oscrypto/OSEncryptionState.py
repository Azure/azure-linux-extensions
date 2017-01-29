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
import re

from collections import namedtuple
from uuid import UUID

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

        if self._is_in_memfs_root():
            rootfs_mountpoint = '/oldroot'

        rootfs_sdx_path = self._get_fs_partition(rootfs_mountpoint)[0]

        if rootfs_sdx_path == "none":
            self.context.logger.log("rootfs_sdx_path is none, parsing UUID from fstab")
            rootfs_sdx_path = self._parse_uuid_from_fstab('/')
            self.context.logger.log("rootfs_uuid: {0}".format(rootfs_sdx_path))

        if rootfs_sdx_path and (rootfs_sdx_path.startswith("/dev/disk/by-uuid/") or self._is_uuid(rootfs_sdx_path)):
            rootfs_sdx_path = self.disk_util.query_dev_sdx_path_by_uuid(rootfs_sdx_path)

        self.context.logger.log("rootfs_sdx_path: {0}".format(rootfs_sdx_path))

        self.rootfs_disk = None
        self.rootfs_block_device = None
        self.bootfs_block_device = None
        
        if self.disk_util.is_os_disk_lvm():
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute('pvs', True, communicator=proc_comm)

            for line in proc_comm.stdout.split("\n"):
                if "rootvg" in line:
                    self.rootfs_block_device = line.strip().split()[0]
                    self.rootfs_disk = self.rootfs_block_device[:-1]
                    self.bootfs_block_device = self.rootfs_disk + '2'
        elif not rootfs_sdx_path:
            self.rootfs_disk = '/dev/sda'
            self.rootfs_block_device = '/dev/sda2'
            self.bootfs_block_device = '/dev/sda1'
        elif rootfs_sdx_path == '/dev/mapper/osencrypt' or rootfs_sdx_path.startswith('/dev/dm-'):
            self.rootfs_block_device = '/dev/mapper/osencrypt'
            bootfs_uuid = self._parse_uuid_from_fstab('/boot')
            self.context.logger.log("bootfs_uuid: {0}".format(bootfs_uuid))
            self.bootfs_block_device = self.disk_util.query_dev_sdx_path_by_uuid(bootfs_uuid)
        else:
            self.rootfs_block_device = self.disk_util.query_dev_id_path_by_sdx_path(rootfs_sdx_path)
            if not self.rootfs_block_device.startswith('/dev/disk/by-id/'):
                self.context.logger.log("rootfs_block_device: {0}".format(self.rootfs_block_device))
                raise Exception("Could not find rootfs block device")

            self.rootfs_disk = self.rootfs_block_device[:self.rootfs_block_device.index("-part")]
            self.bootfs_block_device = self.rootfs_disk + "-part2"

            if self._get_block_device_size(self.bootfs_block_device) > self._get_block_device_size(self.rootfs_block_device):
                self.context.logger.log("Swapping partition identifiers for rootfs and bootfs")
                self.rootfs_block_device, self.bootfs_block_device = self.bootfs_block_device, self.rootfs_block_device

        self.context.logger.log("rootfs_disk: {0}".format(self.rootfs_disk))
        self.context.logger.log("rootfs_block_device: {0}".format(self.rootfs_block_device))
        self.context.logger.log("bootfs_block_device: {0}".format(self.bootfs_block_device))
        
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

    def _is_in_memfs_root(self):
        mounts = file('/proc/mounts', 'r').read()
        return bool(re.search(r'/\s+tmpfs', mounts))

    def _parse_uuid_from_fstab(self, mountpoint):
        contents = file('/etc/fstab', 'r').read()
        matches = re.findall(r'UUID=(.*?)\s+{0}\s+'.format(mountpoint), contents)
        if matches:
            return matches[0]

    def _get_block_device_size(self, dev):
        if not os.path.exists(dev):
            return 0

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute('blockdev --getsize64 {0}'.format(dev),
                                      raise_exception_on_failure=True,
                                      communicator=proc_comm)
        return int(proc_comm.stdout.strip())

    def _is_uuid(self, s):
        try:
            UUID(s)
        except:
            return False
        else:
            return True

OSEncryptionStateContext = namedtuple('OSEncryptionStateContext',
                                      ['hutil',
                                       'distro_patcher',
                                       'logger',
                                       'encryption_environment'])
