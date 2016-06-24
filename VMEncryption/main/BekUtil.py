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

from DiskUtil import *
from Common import *
import base64
import os.path
import os
"""
add retry-logic to the network api call.
"""
class BekUtil(object):
    """description of class"""
    def __init__(self,disk_util,logger):
        self.disk_util = disk_util
        self.logger = logger
        self.passphrase_device = None
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'

    def generate_passphrase(self,algorithm):
        if(TestHooks.use_hard_code_passphrase):
            return TestHooks.hard_code_passphrase
        else:
            with open("/dev/urandom", "rb") as _random_source:
                bytes = _random_source.read(127)
                passphrase_generated = base64.b64encode(bytes)
            return passphrase_generated

    def get_bek_passphrase_file(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()
        bek_filesystem = encryption_config.get_bek_filesystem()
        pass_phrase = None
        if TestHooks.search_not_only_ide:
            self.logger.log("TESTHOOK: search not only ide set")
            azure_devices = self.disk_util.get_device_items(None)
        else:
            azure_devices = self.disk_util.get_azure_devices()

        for i in range(0,len(azure_devices)):
            azure_device = azure_devices[i]
            if(str(azure_device.file_system).lower() == str(bek_filesystem).lower()):
                #TODO handle the failure case
                self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
                self.disk_util.mount_filesystem(os.path.join('/dev/', azure_device.name), self.bek_filesystem_mount_point, bek_filesystem)
                #search for the passphrase file.
                if(os.path.exists(os.path.join(self.bek_filesystem_mount_point, bek_filename))):
                    return os.path.join(self.bek_filesystem_mount_point, bek_filename)
        return None

    def umount_azure_passhprase(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()
        bek_filesystem = encryption_config.get_bek_filesystem()
        pass_phrase = None
        if TestHooks.search_not_only_ide:
            self.logger.log("TESTHOOK: search not only ide set")
            azure_devices = self.disk_util.get_device_items(None)
        else:
            azure_devices = self.disk_util.get_azure_devices()

        for i in range(0,len(azure_devices)):
            azure_device = azure_devices[i]
            if(str(azure_device.file_system).lower() == str(bek_filesystem).lower()):
                #TODO handle the failure case
                self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
                self.disk_util.mount_filesystem(os.path.join('/dev/', azure_device.name), self.bek_filesystem_mount_point, bek_filesystem)
                #search for the passphrase file.
                if(os.path.exists(os.path.join(self.bek_filesystem_mount_point,bek_filename))):
                    self.disk_util.umount(self.bek_filesystem_mount_point)