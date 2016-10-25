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
#
# Requires Python 2.7+
#

import inspect
import os
import re
import sys

from time import sleep
from OSEncryptionState import *

class PrereqState(OSEncryptionState):
    def __init__(self, context):
        super(PrereqState, self).__init__('PrereqState', context)

    def should_enter(self):
        self.context.logger.log("Verifying if machine should enter prereq state")

        if not super(PrereqState, self).should_enter():
            return False
        
        self.context.logger.log("Performing enter checks for prereq state")
                
        return True

    def enter(self):
        if not self.should_enter():
            return

        self.context.logger.log("Entering prereq state")

        distro_info = self.context.distro_patcher.distro_info
        self.context.logger.log("Distro info: {0}".format(distro_info))

        if distro_info[0] == 'Ubuntu' and distro_info[1] == '14.04':
            self.context.logger.log("Enabling OS volume encryption on {0} {1}".format(distro_info[0],
                                                                                      distro_info[1]))
        else:
            raise Exception("Ubuntu1404EncryptionStateMachine called for distro {0} {1}".format(distro_info[0],
                                                                                                distro_info[1]))

        self.context.distro_patcher.install_extras()

        self.command_executor.Execute('telinit u', True)

        self._copy_key_script()

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit prereq state")

        return super(PrereqState, self).should_exit()

    def _copy_key_script(self):
        scriptdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        encryptscriptsdir = os.path.join(scriptdir, '../encryptscripts')
        keyscriptpath = os.path.join(encryptscriptsdir, 'azure_crypt_key.sh')

        if not os.path.exists(keyscriptpath):
            message = "Key script not found at path: {0}".format(keyscriptpath)
            self.context.logger.log(message)
            raise Exception(message)
        else:
            self.context.logger.log("Key script found at path: {0}".format(keyscriptpath))

        self.command_executor.Execute('cp {0} /usr/sbin/azure_crypt_key.sh'.format(keyscriptpath), True)
