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
import urlparse
import httplib
import traceback

class SnapshotError(object):
    def __init__(self):
        self.errorcode = 0
        self.path = None
    def __str__(self):
        return 'errorcode:' + str(self.errorcode) + 'path:' + str(self.path)

class SnapshotResult(object):
    def __init__(self):
        self.errors = []

    def __str__(self):
        error_str=""
        for error in self.errors:
            error_str+=(str(error)) + "\n"
        return error_str

class Snapshotter(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def snapshot(self, sasuri, meta_data):
        result = None
        snapshot_error = SnapshotError()
        if(sasuri is None):
            self.logger.log("Failed to do the snapshot because sasuri is none",False,'Error')
            snapshot_error.errorcode = -1
            snapshot_error.sasuri    = sasuri
        try:
            sasuri_obj   = urlparse.urlparse(sasuri)

            if(sasuri_obj is None or sasuri_obj.hostname is None):
                self.logger.log("Failed to parse the sasuri",False,'Error')
                snapshot_error.errorcode = -1
                snapshot_error.sasuri    = sasuri
            else:
                connection   = httplib.HTTPSConnection(sasuri_obj.hostname)
                body_content = ''
                headers      = {}
                headers["Content-Length"] = 0
                if(meta_data is not None):
                    for meta in meta_data:
                        key   = meta['Key']
                        value = meta['Value']
                        headers["x-ms-meta-" + key] = value
                self.logger.log(str(headers))
                connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query + '&comp=snapshot', body_content, headers = headers)
                result = connection.getresponse()
                self.logger.log(str(result.getheaders()))
                connection.close()
                if(result.status != 201):
                    snapshot_error.errorcode = result.status
                    snapshot_error.sasuri = sasuri
        except Exception as e:
            errorMsg = "Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            snapshot_error.errorcode = -1
            snapshot_error.sasuri    = sasuri
        return snapshot_error

    def snapshotall(self, paras):
        self.logger.log("doing snapshotall now...")
        snapshot_result = SnapshotResult()
        blobs = paras.blobs
        for blob in blobs:
            snapshotError = self.snapshot(blob, paras.backup_metadata)
            if(snapshotError.errorcode != 0):
                snapshot_result.errors.append(snapshotError)
        return snapshot_result
