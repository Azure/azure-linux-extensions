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

from Common import TestHooks
import base64
import os.path

"""
add retry-logic to the network api call.
"""


class BekUtil(object):
    """
    Utility functions related to the BEK VOLUME and BEK files
    """
    def __init__(self, disk_util, logger):
        self.disk_util = disk_util
        self.logger = logger
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'
        self.bek_label = 'BEK VOLUME'

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

        try:
            self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
            self.mount_bek_volume()

            with open(os.path.join(self.bek_filesystem_mount_point, bek_filename), "w") as f:
                f.write(passphrase)
        except Exception as e:
            message = "Failed to store BEK in BEK VOLUME with error: {0}".format(str(e))
            self.logger.log(message)
            raise e
        else:
            self.logger.log("Stored BEK in the BEK VOLUME successfully")
            return

    def get_bek_passphrase_file(self, encryption_config):
        """
        Returns the LinuxPassPhraseFileName path
        """

        bek_filename = encryption_config.get_bek_filename()

        try:
            self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
            self.mount_bek_volume()

            if os.path.exists(os.path.join(self.bek_filesystem_mount_point, bek_filename)):
                return os.path.join(self.bek_filesystem_mount_point, bek_filename)

            for file in os.listdir(self.bek_filesystem_mount_point):
                if bek_filename in file:
                    return os.path.join(self.bek_filesystem_mount_point, file)

        except Exception as e:
            message = "Failed to get BEK from BEK VOLUME with error: {0}".format(str(e))
            self.logger.log(message)

        return None

    def mount_bek_volume(self):
        self.disk_util.mount_by_label(self.bek_label, self.bek_filesystem_mount_point, "fmask=077")

    def umount_azure_passhprase(self, encryption_config, force=False):
        passphrase_file = self.get_bek_passphrase_file(encryption_config)
        if force or (passphrase_file and os.path.exists(passphrase_file)):
            self.disk_util.umount(self.bek_filesystem_mount_point)
