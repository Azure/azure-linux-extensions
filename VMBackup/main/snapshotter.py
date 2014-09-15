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

class Snapshotter(object):
    """description of class"""
    def snapshot(self, sasuri):
        sasuri_obj = urlparse(sasuri)
        connection = httplib.HTTPSConnection(sasuri_obj.hostname)
        body_content = ''
        connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query + '&comp=snapshot', body_content)
        result = connection.getresponse()
        connection.close()

    def snapshotall(self, blobs):
        try:
            for blob in blobs:
                snapshot(blob)
        except Exception, e:
            print(e)
        print('snapshotall')

