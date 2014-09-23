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
        return 'errorcode:'+self.errorcode+'path:'+self.path
        pass

class SnapshotResult(object):
    def __init__(self):
        self.errors = []

    def __str__(self):
        return 'errors' + str(self.errors)

class Snapshotter(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger

    def snapshot(self, sasuri, meta_data):
        result = None
        snapshot_error = SnapshotError()
        try:
            sasuri_obj = urlparse.urlparse(sasuri)
            connection = httplib.HTTPSConnection(sasuri_obj.hostname)
            body_content = ''
            connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query + '&comp=snapshot', body_content)
            result = connection.getresponse()
            connection.close()
            if(result.status != 201):
                snapshot_error.errorcode = result.status
                snapshot_error.sasuri = sasuri
        except Exception, e:
            self.logger.log("Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            #print("Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            snapshot_error.errorcode = -1
            snapshot_error.sasuri = sasuri
        return snapshot_error

    def snapshotall(self, paras):
        #print("doing snapshotall now...")
        snapshot_result = SnapshotResult()
        blobs = paras.blobs
        for blob in blobs:
            snapshotError = self.snapshot(blob, paras.backup_metadata)
            if(snapshotError.errorcode != 0):
                snapshot_result.errors.append(snapshotError)
        return snapshot_result