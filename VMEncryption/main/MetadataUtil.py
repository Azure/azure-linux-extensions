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

from Common import *

import re
import traceback
import urllib.request, urllib.error, urllib.parse
import json


class MetadataUtil(object):
    """ Utility class for accessing Azure Instance Metadata """

    metadata = None

    def __init__(self, logger):
        self.logger = logger

    def is_vmss(self):
        """ return true if the instance metadata is VMSS """
        self.request_metadata()

        # Only VMSS instances will include a placementGroupId GUID in the metadata, ie:
        # (VMSS) "placementGroupId":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        # (Non-VMSS) "placementGroupId":""
        # https://docs.microsoft.com/en-us/azure/virtual-machines/windows/instance-metadata-service
        regex_guid = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        if (
                self.metadata and
                'compute' in self.metadata and
                'placementGroupId' in self.metadata['compute'] and
                re.search(
                    regex_guid, self.metadata['compute']['placementGroupId'], flags=re.IGNORECASE)
        ):
            return True
        else:
            return False

    def request_metadata(self):
        """ initialization method to request instance metadata """
        if self.metadata is None:
            # Metadata not yet populated, try requesting from the Azure Instance Metadata Service
            # https://docs.microsoft.com/en-us/azure/virtual-machines/windows/instance-metadata-service
            try:
                all_info = "http://169.254.169.254/metadata/instance?api-version=2017-08-01"
                request = urllib.request.Request(all_info)
                request.add_header('Metadata', 'true')
                response = urllib.request.urlopen(request).read().decode('UTF-8')
                self.metadata = json.loads(response)
            except:
                message = "Metadata request failed: {0}".format(
                    traceback.format_exc())
                self.logger.log(message)
