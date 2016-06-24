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

import datetime
import httplib
import os
import string
import time
import traceback
import urlparse
from blobwriter import BlobWriter
from Utils.WAAgentUtil import waagent

class Backuplogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.con_path = '/dev/console'
        self.hutil = hutil

    """description of class"""
    def log(self, msg, local=False, level='Info'):
        log_msg = "{0}  {1}  {2} \n".format(str(datetime.datetime.now()) , level , msg)
        self.log_to_con(log_msg)
        if(local):
            self.hutil.log(log_msg)
        else:
            self.msg += log_msg

    def log_to_con(self, msg):
        try:
            with open(self.con_path, "w") as C :
                message = filter(lambda x : x in string.printable, msg)
                C.write(message.encode('ascii','ignore'))
        except IOError as e:
            pass

    def commit(self, logbloburi):
        #commit to local file system first, then commit to the network.
        self.hutil.log(self.msg)
        blobWriter = BlobWriter(self.hutil)
        # append the wala log at the end.
        try:
            # distro information
            if(self.hutil is not None and self.hutil.patching is not None and self.hutil.patching.distro_info is not None):
                distro_str = ""
                if(len(self.hutil.patching.distro_info)>1):
                    distro_str = self.hutil.patching.distro_info[0] + " " + self.hutil.patching.distro_info[1]
                else:
                    distro_str = self.hutil.patching.distro_info[0]
                self.msg = "Distro Info:" + distro_str + "\n" + self.msg
            self.msg = "Guest Agent Version is :" + waagent.GuestAgentVersion + "\n" + self.msg
            with open("/var/log/waagent.log", 'rb') as file:
                file.seek(0, os.SEEK_END)
                length = file.tell()
                seek_len_abs = 1024 * 10
                if(length < seek_len_abs):
                    seek_len_abs = length
                file.seek(0 - seek_len_abs, os.SEEK_END)
                tail_wala_log = file.read()
                self.msg = self.msg + "Tail of WALA Log:" + tail_wala_log
        except Exception as e:
            errMsg = 'Failed to get the waagent log with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.hutil.log(errMsg)
        blobWriter.WriteBlob(self.msg, logbloburi)

    def commit_to_local(self):
        self.hutil.log(self.msg)