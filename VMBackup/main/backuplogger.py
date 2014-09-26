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
import datetime
import traceback
import urlparse
import httplib

class Backuplogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.hutil = hutil

    """description of class"""
    def log(self, msg, local = False, level = 'Info'):
        log_msg = (str(datetime.datetime.now())+'   ' + level + '   '+ msg + '\n')
        #print(log_msg);
        self.msg += log_msg
        if(local):
            self.hutil.log(log_msg)

    def commit(self, logbloburi):
        try:
            self.log("committing the log")
            sasuri_obj = urlparse.urlparse(logbloburi)
            connection = httplib.HTTPSConnection(sasuri_obj.hostname)
            body_content = self.msg
            #print('logbloburi==' + logbloburi)
            headers={}
            headers["x-ms-blob-type" ] = 'BlockBlob'
            self.log(str(headers))
            connection.request('PUT', sasuri_obj.path + '?' + sasuri_obj.query, body_content, headers = headers)

            result = connection.getresponse()
            #print('result=='+str(result.status));
            connection.close()
            return True
        except Exception, e:
            self.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            return False