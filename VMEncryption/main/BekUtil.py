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

from DiskUtil import *
from Common import *
import base64
import os.path
import os
import traceback

"""
add retry-logic to the network api call.
"""
class BekUtil(object):
    """description of class"""
    def __init__(self, disk_util, logger):
        self.disk_util = disk_util
        self.logger = logger
        self.passphrase_device = None
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'

    def generate_passphrase(self, algorithm):
        if TestHooks.use_hard_code_passphrase:
            return TestHooks.hard_code_passphrase
        else:
            with open("/dev/urandom", "rb") as _random_source:
                bytes = _random_source.read(127)
                passphrase_generated = base64.b64encode(bytes)
            return passphrase_generated

    def store_bek_passphrase(self, encryption_config, passphrase):
        bek_filename = encryption_config.get_bek_filename()

        if TestHooks.search_not_only_ide:
            self.logger.log("TESTHOOK: search not only ide set")
            azure_devices = self.disk_util.get_device_items(None)
        else:
            azure_devices = self.disk_util.get_azure_devices()

        for azure_device in azure_devices:
            fstype = str(azure_device.file_system).lower()
            label = str(azure_device.label).lower()
            # disk label is actually "BEK VOLUME", but due to but in lsblk parsing
            # the second word gets truncated
            if fstype in ['vfat', 'ntfs'] and label == 'bek':
                try:
                    self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
                    self.disk_util.mount_filesystem(os.path.join('/dev/', azure_device.name),
                                                    self.bek_filesystem_mount_point,
                                                    fstype)

                    with open(os.path.join(self.bek_filesystem_mount_point, bek_filename), "w") as f:
                        f.write(passphrase)
                except Exception as e:
                    message = "Failed to store BEK in {0} with error: {1}".format(azure_device, e)
                    self.logger.log(message)
                else:
                    self.logger.log("Stored BEK in {0}".format(azure_device))
                    return

        raise Exception("Did not find BEK volume to store passphrase in")

    def get_bek_passphrase_file(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()

        if TestHooks.search_not_only_ide:
            self.logger.log("TESTHOOK: search not only ide set")
            azure_devices = self.disk_util.get_device_items(None)
        else:
            azure_devices = self.disk_util.get_azure_devices()

        for azure_device in azure_devices:
            fstype = str(azure_device.file_system).lower()
            label = str(azure_device.label).lower()
            # disk label is actually "BEK VOLUME", but due to but in lsblk parsing
            # the second word gets truncated
            if fstype in ['vfat', 'ntfs'] and label == 'bek':
                try:
                    self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
                    self.disk_util.mount_filesystem(os.path.join('/dev/', azure_device.name),
                                                    self.bek_filesystem_mount_point,
                                                    fstype)

                    if os.path.exists(os.path.join(self.bek_filesystem_mount_point, bek_filename)):
                        return os.path.join(self.bek_filesystem_mount_point, bek_filename)

                    for file in os.listdir(self.bek_filesystem_mount_point):
                        if bek_filename in file:
                            return os.path.join(self.bek_filesystem_mount_point, file)

                except Exception as e:
                    message = "Failed to get BEK from {0} with error: {1}".format(azure_device, e)
                    self.logger.log(message)

        return None

    def umount_azure_passhprase(self, encryption_config, force=False):
        passphrase_file = self.get_bek_passphrase_file(encryption_config)
        if force or (passphrase_file and os.path.exists(passphrase_file)):
            self.disk_util.umount(self.bek_filesystem_mount_point)
