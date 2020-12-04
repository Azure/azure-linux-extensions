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
from CryptMountConfigUtil import *
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

        self.crypt_mount_config_util = CryptMountConfigUtil(logger=self.context.logger,
                                                            encryption_environment=self.context.encryption_environment,
                                                            disk_util=self.disk_util)

        self.bek_util = BekUtil(disk_util=self.disk_util,
                                logger=self.context.logger)

        self.encryption_config = EncryptionConfig(encryption_environment=self.context.encryption_environment,
                                                  logger=self.context.logger)

        rootfs_mountpoint = '/'

        if self._is_in_memfs_root():
            rootfs_mountpoint = '/oldroot'

        self.rootfs_sdx_path = self._get_fs_partition(rootfs_mountpoint)

        if self.rootfs_sdx_path == "none" or self.rootfs_sdx_path == "/dev/root":
            self.context.logger.log("self.rootfs_sdx_path is none, parsing UUID from fstab")
            self.rootfs_sdx_path = self._parse_uuid_from_fstab('/')
            self.context.logger.log("rootfs_uuid: {0}".format(self.rootfs_sdx_path))

        if self.rootfs_sdx_path and (self.rootfs_sdx_path.startswith("/dev/disk/by-uuid/") or self._is_uuid(self.rootfs_sdx_path)):
            self.rootfs_sdx_path = self.disk_util.query_dev_sdx_path_by_uuid(self.rootfs_sdx_path)

        self.context.logger.log("self.rootfs_sdx_path: {0}".format(self.rootfs_sdx_path))

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
                    bootfs_uuid = self._parse_uuid_from_fstab('/boot')
                    if bootfs_uuid:
                        self.bootfs_block_device = self.disk_util.query_dev_sdx_path_by_uuid(bootfs_uuid)
        elif not self.rootfs_sdx_path:
            self.rootfs_disk = '/dev/sda'
            self.rootfs_block_device = '/dev/sda2'
            self.bootfs_block_device = '/dev/sda1'
        elif self.rootfs_sdx_path == '/dev/mapper/osencrypt' or self.rootfs_sdx_path.startswith('/dev/dm-'):
            self.rootfs_block_device = '/dev/mapper/osencrypt'
            bootfs_uuid = self._parse_uuid_from_fstab('/boot')
            self.context.logger.log("bootfs_uuid: {0}".format(bootfs_uuid))
            self.bootfs_block_device = self.disk_util.query_dev_sdx_path_by_uuid(bootfs_uuid)
        else:
            self.rootfs_block_device = self.disk_util.get_persistent_path_by_sdx_path(self.rootfs_sdx_path)
            if not self.rootfs_block_device.startswith('/dev/disk/'):
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

        # search for matching mount point item
        for mp_item in self.disk_util.get_mount_items():
            if dev == os.lstat(mp_item["dest"]).st_dev:
                result = mp_item["src"]

        return result

    def _get_root_partuuid(self):
        root_partuuid = None
        root_device_items = self.disk_util.get_device_items(self.rootfs_block_device)
        self.context.logger.log("For root_partuuid scanning: {0}".format(self.rootfs_block_device))
        for root_item in root_device_items:
            self.context.logger.log("Checking {0}".format(root_item.name))
            if self.rootfs_sdx_path.endswith(root_item.name) or os.path.realpath(self.rootfs_block_device).endswith(root_item.name):
                self.context.logger.log("Finding partuuid for {0}".format(root_item.name))
                root_partuuid = self.disk_util.get_device_items_property(root_item.name, "PARTUUID")
                if root_partuuid:
                    return root_partuuid
        return root_partuuid

    def _is_in_memfs_root(self):
        mounts = open('/proc/mounts', 'r').read()
        return bool(re.search(r'/\s+tmpfs', mounts))

    def _parse_uuid_from_fstab(self, mountpoint):
        contents = open('/etc/fstab', 'r').read()
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

    def _get_az_symlink_os_volume(self):
        realpath_rootfs_dev = os.path.realpath(self.rootfs_block_device)

        # First we check the scsi0 dir. If this dir is present we are almost guaranteed to find the rootfs device in here
        gen2_dir = os.path.join(CommonVariables.azure_symlinks_dir, "scsi0/")
        if os.path.exists(gen2_dir):
            for top_level_item in os.listdir(gen2_dir):
                dev_path = os.path.join(gen2_dir, top_level_item)
                if os.path.realpath(dev_path) == realpath_rootfs_dev:
                    return dev_path

        # Then we check the root* devices. If these are present we use them.
        # Though it's a little worrying that some Gen2 VMs don't have these links, so we take these as a second choice
        for top_level_item in os.listdir(CommonVariables.azure_symlinks_dir):
            if top_level_item.startswith("root"):
                dev_path = os.path.join(CommonVariables.azure_symlinks_dir, top_level_item)
                if os.path.realpath(dev_path) == realpath_rootfs_dev:
                    return dev_path

        return None

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
