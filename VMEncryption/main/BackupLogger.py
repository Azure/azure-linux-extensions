#!/usr/bin/env python
#
# VM Backup extension
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
#
# Requires Python 2.7+
#
import time
import datetime
import traceback
import urlparse
import httplib

class BackupLogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.hutil = hutil
        self.__StorageVersion = "2014-02-14"

    """description of class"""
    def log(self, msg, local=True, level='Info'):
        log_msg = (str(datetime.datetime.now()) + '   ' + level + '   ' + msg )
        self.msg += log_msg
        if(local):
            self.hutil.log(log_msg)

    def commit(self, logbloburi):
        try:
            self.log("committing the log")
            self.hutil.log(self.msg)
            # get the blob type
            if(logbloburi is not None):
                sasuri_obj = urlparse.urlparse(logbloburi)
                connection = httplib.HTTPSConnection(sasuri_obj.hostname)

                #Check blob type
                timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                headers = {}
                headers["x-ms-date"] = timestamp
                headers["x-ms-version"] = self.__StorageVersion

                connection.request('GET', sasuri_obj.path + '?' + sasuri_obj.query, headers = headers)
                result = connection.getresponse()
                blobType = result.getheader("x-ms-blob-type")

                if blobType == "BlockBlob":
                    body_content = self.msg
                    headers = {}
                    headers["x-ms-blob-type"] = 'BlockBlob'
                    self.log(str(headers))
                    connection = httplib.HTTPSConnection(sasuri_obj.hostname)
                    connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query, body_content, headers = headers)

                    result = connection.getresponse()
                    connection.close()
                    return True

                elif blobType == "PageBlob":
                    body_content = self.msg
                    total_len = len(body_content)
                    size_in_page = ((total_len + 511) / 512) 

                    buf = bytearray(size_in_page * 512)
                    buf[0 : total_len - 1] = body_content[0 : total_len - 1]
                    headers["x-ms-blob-type"] = 'PageBlob'
                    headers["x-ms-page-write"] = "update"
                    headers["x-ms-range"] = "bytes={0}-{1}".format(0, size_in_page * 512 - 1)
                    headers["Content-Length"] = str(size_in_page * 512)
                    self.log(str(headers))
                    connection = httplib.HTTPSConnection(sasuri_obj.hostname)                    
                    connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query + '&comp=page',buf, headers = headers)
                    result = connection.getresponse()
                    connection.close()
                    return True
                else:
                    self.hutil.log("blobType is " + str(blobType))
                    return False
            else:
                self.hutil.log("logbloburi is None")
                return False
        except Exception as e:
            self.hutil.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            return False
