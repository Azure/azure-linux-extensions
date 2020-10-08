#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2020 Microsoft Corporation
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
import os
import string
import io
import sys

class BackupLogger(object):
    def __init__(self, hutil):
        self.hutil = hutil
        self.current_process_id = os.getpid()

    """description of class"""
    def log(self, msg, level='Info'):
        escaped_msg = msg.replace('"', "'") # Replace " with ' as agent telemetry cannot process double quotes
        log_msg = "{0}: [{1}] {2}".format(self.current_process_id, level, escaped_msg)
        log_msg = [c for c in log_msg if c in string.printable]
        log_msg = ''.join(log_msg)

        self.hutil.log(log_msg)
        self.log_to_console(log_msg)
 
    def log_to_console(self, msg):
        try:
            with io.open('/dev/console', 'w') as f:
                msg = [c for c in msg if c in string.printable]
                msg = ''.join(msg)

                # Python 3.x strings are Unicode by default and do not use decode
                if sys.version_info[0] < 3:
                    if isinstance(msg, str):
                        msg = msg.decode('utf-8')

                f.write(u'[AzureDiskEncryption] ' + msg + u'\n')
        except IOError:
            pass
