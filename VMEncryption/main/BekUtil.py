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

import base64
import os.path
import os

"""
add retry-logic to the network api call.
"""


class BekUtil(object):
    """description of class"""

    def __init__(self, disk_util, logger):
        self.disk_util = disk_util
        self.logger = logger
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'

    def generate_passphrase(self, algorithm):
        with open("/dev/urandom", "rb") as _random_source:
            bytes = _random_source.read(127)
            passphrase_generated = base64.b64encode(bytes)
        return passphrase_generated

    #
    # Returns the LinuxPassPhraseFileName path
    #
    def get_bek_passphrase_file(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()

        try:
            self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
            self.disk_util.mount_bek_volume("BEK VOLUME", self.bek_filesystem_mount_point, "fmask=077")

            if os.path.exists(os.path.join(self.bek_filesystem_mount_point, bek_filename)):
                return os.path.join(self.bek_filesystem_mount_point, bek_filename)

        except Exception as e:
            message = "Failed to get BEK with error: {0}".format(e)
            self.logger.log(message)

        return None

    def umount_azure_passhprase(self, encryption_config, force=False):
        passphrase_file = self.get_bek_passphrase_file(encryption_config)
        if force or (passphrase_file and os.path.exists(passphrase_file)):
            self.disk_util.umount(self.bek_filesystem_mount_point)
