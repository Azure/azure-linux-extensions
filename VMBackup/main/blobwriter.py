#!/usr/bin/env python
#
# VM Backup extension
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

import time
import datetime
import traceback
import urlparse
import httplib
from common import CommonVariables
from HttpUtil import HttpUtil

class BlobWriter(object):
    """description of class"""
    def __init__(self, hutil):
        self.hutil = hutil
    """
    network call should have retry.
    """
    def WriteBlob(self,msg,blobUri):
        retry_times = 3
        while(retry_times > 0):
            try:
                # get the blob type
                if(blobUri is not None):
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri)
                    headers = {}
                    headers["x-ms-blob-type"] = 'BlockBlob'
                    self.hutil.log(str(headers))
                    result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = msg, headers = headers, fallback_to_curl = True)
                    if(result == CommonVariables.success):
                        self.hutil.log("blob written succesfully to:"+str(blobUri))
                        retry_times = 0
                    else:
                        self.hutil.log("blob failed to write")
                else:
                    self.hutil.log("logbloburi is None")
                    retry_times = 0
            except Exception as e:
                self.hutil.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            self.hutil.log("retry times is " + str(retry_times))
            retry_times = retry_times - 1