#!/usr/bin/env python
#
#CustomScript extension
#
# Copyright 2014 Microsoft Corporation
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

from common import CommonVariables
import base64
import json
import sys

class ParameterParser(object):
    def __init__(self, protected_settings, public_settings, backup_logger):
        """
        TODO: we should validate the parameter first
        """
        self.blobs = []
        self.backup_metadata = None
        self.public_config_obj = None
        self.private_config_obj = None
        self.blobs = None
        self.customSettings = None
        self.snapshotTaskToken = ''

        """
        get the public configuration
        """
        self.commandToExecute = public_settings.get(CommonVariables.command_to_execute)
        self.taskId = public_settings.get(CommonVariables.task_id)
        self.locale = public_settings.get(CommonVariables.locale)
        self.logsBlobUri = public_settings.get(CommonVariables.logs_blob_uri)
        self.statusBlobUri = public_settings.get(CommonVariables.status_blob_uri)
        self.commandStartTimeUTCTicks = public_settings.get(CommonVariables.commandStartTimeUTCTicks)
        self.vmType = public_settings.get(CommonVariables.vmType)

        if(CommonVariables.customSettings in public_settings.keys() and public_settings.get(CommonVariables.customSettings) is not None and public_settings.get(CommonVariables.customSettings) != ""):
            backup_logger.log("Reading customSettings from public_settings", True)
            self.customSettings = public_settings.get(CommonVariables.customSettings)
        elif(CommonVariables.customSettings in protected_settings.keys()):
            backup_logger.log("Reading customSettings from protected_settings", True)
            self.customSettings = protected_settings.get(CommonVariables.customSettings)
            

        self.publicObjectStr = public_settings.get(CommonVariables.object_str)
        if(self.publicObjectStr is not None and self.publicObjectStr != ""):
            if sys.version_info > (3,):
                decoded_public_obj_string = base64.b64decode(self.publicObjectStr)
                decoded_public_obj_string = decoded_public_obj_string.decode('ascii')
            else:
                decoded_public_obj_string = base64.standard_b64decode(self.publicObjectStr)
            decoded_public_obj_string = decoded_public_obj_string.strip()
            decoded_public_obj_string = decoded_public_obj_string.strip('\'')
            self.public_config_obj = json.loads(decoded_public_obj_string)
            self.backup_metadata = self.public_config_obj['backupMetadata']
        if(self.logsBlobUri is None or self.logsBlobUri == ""):
            self.logsBlobUri = protected_settings.get(CommonVariables.logs_blob_uri)
        if(self.statusBlobUri is None or self.statusBlobUri == ""):
            self.statusBlobUri = protected_settings.get(CommonVariables.status_blob_uri)
        if(CommonVariables.snapshotTaskToken in self.public_config_obj.keys()):
            self.snapshotTaskToken = self.public_config_obj[CommonVariables.snapshotTaskToken]
        elif(CommonVariables.snapshotTaskToken in protected_settings.keys()):
            self.snapshotTaskToken = protected_settings.get(CommonVariables.snapshotTaskToken)

        """
        first get the protected configuration
        """
        self.privateObjectStr = protected_settings.get(CommonVariables.object_str)
        if(self.privateObjectStr is not None and self.privateObjectStr != ""):
            if sys.version_info > (3,):
                decoded_private_obj_string = base64.b64decode(self.privateObjectStr)
                decoded_private_obj_string = decoded_private_obj_string.decode('ascii')
            else:
                decoded_private_obj_string = base64.standard_b64decode(self.privateObjectStr)
            decoded_private_obj_string = decoded_private_obj_string.strip()
            decoded_private_obj_string = decoded_private_obj_string.strip('\'')
            self.private_config_obj = json.loads(decoded_private_obj_string)

            if ('diskInfoList' in self.private_config_obj.keys() and self.private_config_obj['diskInfoList'] is not None and len(self.private_config_obj['diskInfoList']) > 0):
                self.blobs = []
                backup_logger.log("Blob Sas uri from private_config_obj['diskInfoList']", True)

                for diskInfo in self.private_config_obj['diskInfoList']:
                    self.blobs.append(diskInfo['blobSASUri'])
            else:
                backup_logger.log("Blob Sas uri from private_config_obj['blobSASUri']", True)
                self.blobs = self.private_config_obj['blobSASUri']

