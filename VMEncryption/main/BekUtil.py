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

from Common import TestHooks, CommonVariables
import base64
import os.path
import traceback
import sys

"""
add retry-logic to the network api call.
"""
class BekMissingException(Exception):

   def __init__(self, value):
      self.value = value

   def __str__(self):
      return(repr(self.value))

class BekUtil(object):
    """
    Utility functions related to the BEK VOLUME and BEK files
    """
    def __init__(self, disk_util, logger):
        self.disk_util = disk_util
        self.logger = logger
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'
        self.bek_label = 'BEK VOLUME'
        self.bek_filesystem = 'vfat'
        self.wrong_fs_msg = "BEK does not have vfat filesystem."
        self.not_mounted_msg = "BEK is not mounted."
        self.partition_missing_msg = "BEK disk does not expected partition."
        self.bek_missing_msg = "BEK disk is not attached."

    def generate_passphrase(self):
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

            # ensure base64 encoded passphrase string is identically encoded in
            # python2 and python3 environments for consistency in output format
            if sys.version_info[0] < 3:
                if isinstance(passphrase, str):
                    passphrase = passphrase.decode('utf-8')

            with open(os.path.join(self.bek_filesystem_mount_point, bek_filename), "wb") as f:
                f.write(passphrase)
            for bek_file in os.listdir(self.bek_filesystem_mount_point):
                if bek_filename in bek_file and bek_filename != bek_file:
                    with open(os.path.join(self.bek_filesystem_mount_point, bek_file), "wb") as f:
                        f.write(passphrase)

        except Exception as e:
            message = "Failed to store BEK in BEK VOLUME with error: {0}".format(traceback.format_exc())
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

        except BekMissingException:
            raise

        except Exception as e:
            # use traceback to convert exception to string on both python2 and python3+
            message = "Failed to get BEK from BEK VOLUME with error: {0}".format(traceback.format_exc())
            self.logger.log(message)

        return None

    def mount_bek_volume(self):
        bek_expected, fault_reason = self.is_bek_volume_mounted_and_formatted()
        if bek_expected:
            self.logger.log("BEK Volume already in expected state.")
            return
        else:
            self.logger.log("Trying to mount BEK volume.")
        self.disk_util.mount_by_label(self.bek_label, self.bek_filesystem_mount_point, "fmask=077")
        bek_expected, fault_reason = self.is_bek_volume_mounted_and_formatted()
        if not bek_expected:
            bek_attached, error_reason = self.is_bek_disk_attached_and_partitioned()
            if bek_attached:
                raise BekMissingException("BEK disk is missing or not initialized. " + fault_reason)
            else:
                raise BekMissingException("BEK disk is missing or not initialized. " + error_reason)

    def is_bek_volume_mounted_and_formatted(self):
        mount_items=self.disk_util.get_mount_items()
        for mount_item in mount_items:
            if os.path.normpath(mount_item["dest"]) == os.path.normpath(self.bek_filesystem_mount_point):
                if mount_item["fs"] == self.bek_filesystem:
                    return True, ""
                else:
                    self.logger.log("BEK has unexpected filesystem "+mount_item["fs"])
                    return False, self.wrong_fs_msg
        return False, self.not_mounted_msg

    def is_bek_disk_attached_and_partitioned(self):
        possible_bek_locations = [
            os.path.join(CommonVariables.azure_symlinks_dir, "BEK"),
            os.path.join(CommonVariables.cloud_symlinks_dir, "scsi0/lun3")
        ]
        for location in possible_bek_locations:
            if os.path.exists(location):
                if os.path.exists(os.path.join(location, "-part1")):
                    return True, ""
                else:
                    return False, self.partition_missing_msg
        return False, self.bek_missing_msg

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
