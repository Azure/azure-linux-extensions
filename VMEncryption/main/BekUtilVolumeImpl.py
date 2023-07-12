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
from AbstractBekUtilImpl import AbstractBekUtilImpl,BekMissingException


class BekUtilVolumeImpl(AbstractBekUtilImpl):
    """
    Utility functions related to the BEK VOLUME and BEK files
    """
    def __init__(self, disk_util, logger):
        self.disk_util = disk_util
        self.logger = logger
        self.bek_filesystem_mount_point = '/mnt/azure_bek_disk'
        self.bek_label = 'BEK VOLUME'
        self.bek_filesystem = 'vfat'


    def store_bek_passphrase(self, encryption_config, passphrase):
        bek_filename = encryption_config.get_bek_filename()
        try:
            self.disk_util.make_sure_path_exists(self.bek_filesystem_mount_point)
            self.mount_bek_volume()
            self.store_passphrase(key_File_Path=self.bek_filesystem_mount_point,
                                  bek_filename=bek_filename,
                                  passphrase=passphrase)
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
                    return False, AbstractBekUtilImpl.wrong_fs_msg
        return False, AbstractBekUtilImpl.not_mounted_msg

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
                    return False, AbstractBekUtilImpl.partition_missing_msg
        return False, AbstractBekUtilImpl.bek_missing_msg

    def umount_azure_passhprase(self, encryption_config, force=False):
        passphrase_file = self.get_bek_passphrase_file(encryption_config)
        if force or (passphrase_file and os.path.exists(passphrase_file)):
            self.disk_util.umount(self.bek_filesystem_mount_point)