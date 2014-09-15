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

class Backuplogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.hutil = hutil

    """description of class"""
    def log(self, msg, local=False):
        self.msg+=msg
        if(local):
            self.hutil.log(msg)

    def commit(self, logbloburi):
        sasuri_obj = urlparse(logbloburi)
        connection = httplib.HTTPSConnection(sasuri_obj.hostname)
        body_content = self.msg
        connection.request('PUT', logbloburi, body_content)
        result = connection.getresponse()
        connection.close()



