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

import traceback
from AbstractBekUtilImpl import AbstractBekUtilImpl
import sys
import os

class BekUtilFileImpl(AbstractBekUtilImpl):
    """
    Utility class to store passphrase in a keyfilepath.
    """
    def __init__(self,disk_util,logger):
        self.keyfilePath = "/var/lib/azure_disk_encryption_config/"
        self.logger = logger
        self.disk_util=disk_util
        self.keyPathNotFound = "Keyfile path is not valid, path: {0}".format(self.keyfilePath)
    
    def store_bek_passphrase(self, encryption_config, passphrase):
        bek_filename = encryption_config.get_bek_filename()
        try:
            self.disk_util.make_sure_path_exists(self.keyfilePath)
            self.store_passphrase(key_File_Path=self.keyfilePath,
                                  bek_filename=bek_filename,
                                  passphrase=passphrase)            
        except Exception as e:
            message = "Failed to store BEK in KeyPath {1} with error: {0}".format(traceback.format_exc(),self.keyfilePath)
            self.logger.log(message)
            raise e
        else:
            self.logger.log("Stored BEK in the KeyPath {0} successfully".format(self.keyfilePath))
            return

    def get_bek_passphrase_file(self, encryption_config):
        """
        Returns the LinuxPassPhraseFileName path
        """
        bek_filename = encryption_config.get_bek_filename()
        try:
            self.disk_util.make_sure_path_exists(self.keyfilePath)

            if os.path.exists(os.path.join(self.keyfilePath, bek_filename)):
                return os.path.join(self.keyfilePath, bek_filename)

            for filename in os.listdir(self.keyfilePath):
                if bek_filename in filename:
                    return os.path.join(self.keyfilePath, filename)

        except Exception as e:
            # use traceback to convert exception to string on both python2 and python3+
            message = "Failed to get BEK from KeyPath {1} with error: {0}".format(traceback.format_exc(),self.keyfilePath)
            self.logger.log(message)

        return None