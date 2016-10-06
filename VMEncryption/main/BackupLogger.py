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
import time
import datetime
import traceback
import urlparse
import httplib
import os
import string

class BackupLogger(object):
    def __init__(self, hutil):
        self.hutil = hutil
        self.current_process_id = os.getpid()

    """description of class"""
    def log(self, msg, level='Info'):
        log_msg = "{0}: [{1}] {2}".format(self.current_process_id, level, msg)
        log_msg = filter(lambda c: c in string.printable, log_msg)
        log_msg = log_msg.encode('ascii', 'ignore')

        self.hutil.log(log_msg)
        self.log_to_console(log_msg)
 
    def log_to_console(self, msg):
        try:
            with open('/dev/console', 'w') as f:
                msg = filter(lambda c: c in string.printable, msg)
                f.write('[AzureDiskEncryption] ' + msg + '\n')
        except IOError as e:
            pass
