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
import traceback 

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

    def generate_passphrase(self):
        if TestHooks.use_hard_code_passphrase:
            return TestHooks.hard_code_passphrase
        else:
            with open("/dev/urandom", "rb") as _random_source:
                bytes = _random_source.read(127)
                passphrase_generated = base64.b64encode(bytes)
            return passphrase_generated

    def store_bek_passphrase(self, encryption_config, passphrase):

        # convert filename to string for consistency across python2 python3+
        bek_filename = str(encryption_config.get_bek_filename().encode('utf-8'))

        try:
            self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
            self.mount_bek_volume()

            # ensure base64 encoded passphrase string is encoded as utf-8 in both
            # python2 and python3 environments for consistency in output format
            with open(os.path.join(self.bek_filesystem_mount_point, bek_filename), "wb") as f:
                f.write(str(passphrase).encode('utf-8'))
            for bek_file in os.listdir(self.bek_filesystem_mount_point):
                if bek_filename in bek_file and bek_filename != bek_file:
                    with open(os.path.join(self.bek_filesystem_mount_point, bek_file), "wb") as f:
                        f.write(str(passphrase).encode('utf-8'))
        except Exception as e:
            message = "Failed to store BEK in BEK VOLUME with error: {0}".format(traceback.format_exc(e))
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

            for filename in os.listdir(self.bek_filesystem_mount_point):
                if bek_filename in filename:
                    return os.path.join(self.bek_filesystem_mount_point, filename)

        except Exception as e:
            # use traceback to convert exception to string on both python2 and python3+
            message = "Failed to get BEK from BEK VOLUME with error: {0}".format(traceback.format_exc(e))
            self.logger.log(message)

        return None

    def mount_bek_volume(self):
        self.disk_util.mount_by_label(self.bek_label, self.bek_filesystem_mount_point, "fmask=077")

    def umount_azure_passhprase(self, encryption_config, force=False):
        passphrase_file = self.get_bek_passphrase_file(encryption_config)
        if force or (passphrase_file and os.path.exists(passphrase_file)):
            self.disk_util.umount(self.bek_filesystem_mount_point)

    def delete_bek_passphrase_file(self, encryption_config):
        bek_filename = encryption_config.get_bek_filename()
        bek_file = self.get_bek_passphrase_file(encryption_config)
        if not bek_file:
            return
        bek_dir = os.path.dirname(bek_file)
        for file in os.listdir(bek_dir):
            if bek_filename in file:
                os.remove(os.path.join(bek_dir, file))
