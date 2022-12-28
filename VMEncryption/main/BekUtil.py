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

from Common import CommonVariables
from IMDSUtil import IMDSStoredResults
from BekUtilVolumeImpl import BekUtilVolumeImpl
from BekUtilFileImpl import BekUtilFileImpl

class BekUtil(object):
    """
    Utility functions related to the BEK VOLUME and BEK files
    """
    def __init__(self, disk_util, logger, encryption_environment=None):
        security_type = CommonVariables.Standard
        try:
            imds_Stored_Results=IMDSStoredResults(logger=logger,encryption_environment=encryption_environment)
            security_type = imds_Stored_Results.get_security_type()
        except Exception as ex:
            logger.log("Failure in retriving security type from IMDS, Following BEK Volume Path.")
        finally:
            logger.log("BEK util path is followed according to VM security type {0}".format(security_type))
                
        if security_type != CommonVariables.ConfidentialVM:
           self.bekUtilImpl = BekUtilVolumeImpl(disk_util,logger)
        else:
            self.bekUtilImpl = BekUtilFileImpl(disk_util,logger)

    def generate_passphrase(self):
        return self.bekUtilImpl.generate_passphrase()

    def store_bek_passphrase(self, encryption_config, passphrase):
        return self.bekUtilImpl.store_bek_passphrase(encryption_config,passphrase)

    def get_bek_passphrase_file(self, encryption_config):
        return self.bekUtilImpl.get_bek_passphrase_file(encryption_config)

    def mount_bek_volume(self):
        self.bekUtilImpl.mount_bek_volume()

    def is_bek_volume_mounted_and_formatted(self):
        return self.bekUtilImpl.is_bek_volume_mounted_and_formatted()

    def is_bek_disk_attached_and_partitioned(self):
        return self.bekUtilImpl.is_bek_disk_attached_and_partitioned()

    def umount_azure_passhprase(self, encryption_config, force=False):
        self.bekUtilImpl.umount_azure_passhprase(encryption_config,force)

    def delete_bek_passphrase_file(self, encryption_config):
        self.bekUtilImpl.delete_bek_passphrase_file(encryption_config)