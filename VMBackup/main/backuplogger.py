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
from blobwriter import BlobWriter

class Backuplogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.hutil = hutil

    """description of class"""
    def log(self, msg, local=False, level='Info'):
        log_msg = (str(datetime.datetime.now()) + '   ' + level + '   ' + msg + '\n')
        self.msg += log_msg
        if(local):
            self.hutil.log(log_msg)

    def commit(self, logbloburi):
        #commit to local file system first, then commit to the network.
        self.hutil.log(self.msg)
        blobWriter = BlobWriter(self.hutil)
        blobWriter.WriteBlob(self.msg,logbloburi)
    def commit_to_local(self):
        self.hutil.log(self.msg)