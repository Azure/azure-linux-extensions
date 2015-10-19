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
#
# Requires Python 2.7+
#
import time
import datetime
import traceback
import urlparse
import httplib
from Utils.HttpUtil import HttpUtil

class BlobWriter(object):
    """description of class"""
    def __init__(self, hutil):
        self.hutil = hutil
        self.__StorageVersion = "2014-02-14"
    """
    network call should have retry.
    """
    def WriteBlob(self,msg,blobUri):
        retry_times = 3
        while(retry_times > 0):
            try:
                self.hutil.log(msg)
                # get the blob type
                if(blobUri is not None):
                    http_util = HttpUtil()
                    sasuri_obj = urlparse.urlparse(blobUri)
                    #Check blob type
                    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                    headers = {}
                    headers["x-ms-date"] = timestamp
                    headers["x-ms-version"] = self.__StorageVersion

                    result = http_util.Call('GET',sasuri_obj,None,headers)
                    blobType = result.getheader("x-ms-blob-type")

                    if blobType == "BlockBlob":
                        body_content = msg
                        headers = {}
                        headers["x-ms-blob-type"] = 'BlockBlob'
                        self.hutil.log(str(headers))
                        result = http_util.Call('PUT',sasuri_obj,body_content,headers=headers)
                        retry_times = 0

                    elif blobType == "PageBlob":
                        body_content = msg
                        total_len = len(body_content)
                        size_in_page = ((total_len + 511) / 512) 

                        buf = bytearray(size_in_page * 512)
                        buf[0 : total_len - 1] = body_content[0 : total_len - 1]
                        headers["x-ms-blob-type"] = 'PageBlob'
                        headers["x-ms-page-write"] = "update"
                        headers["x-ms-range"] = "bytes={0}-{1}".format(0, size_in_page * 512 - 1)
                        headers["Content-Length"] = str(size_in_page * 512)
                        sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
                        self.hutil.log(str(headers))
                        result = http_util.Call('PUT',sasuri_obj,buf,headers=headers)
                        retry_times = 0
                    else:
                        self.hutil.log("blobUri is " + str(blobType))
                        retry_times = 0
                else:
                    self.hutil.log("logbloburi is None")
                    retry_times = 0
            except Exception as e:
                self.hutil.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            self.hutil.log("retry times is " + str(retry_times))
            retry_times = retry_times - 1


