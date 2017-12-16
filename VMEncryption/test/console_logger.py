#!/usr/bin/env python
#
# *********************************************************
# Copyright (c) Microsoft. All rights reserved.
#
# Apache 2.0 License
#
# You may obtain a copy of the License at
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# *********************************************************

import os
import string

class ConsoleLogger(object):
    def __init__(self):
        self.current_process_id = os.getpid()

    def log(self, msg, level='Info'):
        """ simple logging mechanism to print to stdout """
        log_msg = "{0}: [{1}] {2}".format(self.current_process_id, level, msg)
        print(log_msg)

    def error(self, msg):
        log(msg,'Error')
