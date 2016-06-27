#!/usr/bin/env python
#
# VMEncryption extension
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

import xml.parsers.expat
from Utils import HandlerUtil
from Common import *

# parameter format should be like this:
#{"command":"enableencryption","query":[{"source_scsi_number":"[5:0:0:0]","target_scsi_number":"[5:0:0:2]"},{"source_scsi_number":"[5:0:0:1]","target_scsi_number":"[5:0:0:3]"}],
#"force":"true", "passphrase":"User@123"}
class ExtensionParameter(object):
    def __init__(self, hutil, protected_settings, public_settings):
        """
        TODO: we should validate the parameter first
        """
        self.hutil = hutil
        self.devpath = None
        self.command = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        self.KeyEncryptionKeyURL = public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        self.KeyVaultURL = public_settings.get(CommonVariables.KeyVaultURLKey)
        self.AADClientID = public_settings.get(CommonVariables.AADClientIDKey)
        keyEncryptionAlgorithm = public_settings.get(CommonVariables.KeyEncryptionAlgorithmKey)
        if keyEncryptionAlgorithm is not None and keyEncryptionAlgorithm !="":
            self.KeyEncryptionAlgorithm = keyEncryptionAlgorithm
        else:
            self.KeyEncryptionAlgorithm = 'RSA-OAEP'
        self.VolumeType = public_settings.get(CommonVariables.VolumeTypeKey)
        self.DiskFormatQuery = public_settings.get(CommonVariables.DiskFormatQuerykey)

        """
        private settings
        """
        self.AADClientSecret = protected_settings.get(CommonVariables.AADClientSecretKey)
        self.passphrase = protected_settings.get(CommonVariables.PassphraseKey)

        self.DiskEncryptionKeyFileName = "LinuxPassPhraseFileName"
        # parse the query from the array
