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
import os
import string
import time
import traceback
from blobwriter import BlobWriter
from Utils.WAAgentUtil import waagent
import sys

class Backuplogger(object):
    def __init__(self, hutil):
        self.msg = ''
        self.con_path = '/dev/console'
        self.enforced_local_flag_value = True
        self.hutil = hutil
        self.prev_log = ''
        self.logging_off = False

    def enforce_local_flag(self, enforced_local):
        if (self.hutil.get_intvalue_from_configfile('LoggingOff', 0) == 1):
            self.logging_off = True
        if (self.enforced_local_flag_value != False and enforced_local == False and self.logging_off == True):
            pass
        elif (self.enforced_local_flag_value != False and enforced_local == False):
            self.msg = self.msg + "================== Logs during Freeze Start ==============" + "\n"
        elif (self.enforced_local_flag_value == False and enforced_local == True):
            self.msg = self.msg + "================== Logs during Freeze End ==============" + "\n"
            self.commit_to_local()
        self.enforced_local_flag_value = enforced_local

    """description of class"""
    def log(self, msg, local=False, level='Info'):
        if(self.enforced_local_flag_value == False and self.logging_off == True):
            return
        WriteLog = self.hutil.get_strvalue_from_configfile('WriteLog','True')
        if (WriteLog == None or WriteLog == 'True'):
            log_msg = ""
            if sys.version_info > (3,):
                log_msg = self.log_to_con_py3(msg, level)
            else:
                log_msg = "{0}  {1}  {2} \n".format(str(datetime.datetime.now()) , level , msg)
                if(self.enforced_local_flag_value != False):
                    self.log_to_con(log_msg)
            if(self.enforced_local_flag_value == False):
                self.msg += log_msg
            else:
                self.hutil.log(str(msg),level)

    def log_to_con(self, msg):
        try:
            with open(self.con_path, "wb") as C :
                message = "".join(list(filter(lambda x : x in string.printable, msg)))
                C.write(message.encode('ascii','ignore'))
        except IOError as e:
            pass
        except Exception as e:
            pass

    def log_to_con_py3(self, msg, level='Info'):
        log_msg = ""
        try:
            if type(msg) is not str:
                msg = str(msg, errors="backslashreplace")
            time = datetime.datetime.now().strftime(u'%Y/%m/%d %H:%M:%S.%f')
            log_msg = u"{0}  {1}  {2} \n".format(time , level , msg)
            log_msg= str(log_msg.encode('ascii', "backslashreplace"), 
                         encoding="ascii")
            if(self.enforced_local_flag_value != False):
                with open(self.con_path, "w") as C :
                    C.write(log_msg)
        except IOError:
            pass
        except Exception as e:
            log_msg = "###### Exception in log_to_con_py3"
        return log_msg

    def commit(self, logbloburi):
        #commit to local file system first, then commit to the network.
        try:
            self.hutil.log(self.msg)
            self.msg = ''
        except Exception as e:
            pass 
        try:
            self.commit_to_blob(logbloburi)
        except Exception as e:
            self.hutil.log('commit to blob failed')

    def commit_to_local(self):
        self.hutil.log(self.msg)
        self.msg = ''

    def commit_to_blob(self, logbloburi):
        UploadStatusAndLog = self.hutil.get_strvalue_from_configfile('UploadStatusAndLog','True')
        if (UploadStatusAndLog == None or UploadStatusAndLog == 'True'):
            log_to_blob = ""
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
                    log_to_blob = str(self.hutil.fetch_log_message()) + "Tail of previous logs:" + str(self.prev_log) + "Tail of WALA Log:" + str(tail_wala_log) + "Tail of shell script log:" + str(self.hutil.get_shell_script_log())
            except Exception as e:
                errMsg = 'Failed to get the waagent log with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
                self.hutil.log(errMsg)
            blobWriter.WriteBlob(log_to_blob, logbloburi)

    def set_prev_log(self):
        self.prev_log = self.hutil.get_prev_log()
