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

from OSEncryptionState import *
from pprint import pprint

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

        if ((distro_info[0] == 'redhat' and distro_info[1] == '7.2') or
            (distro_info[0] == 'redhat' and distro_info[1] == '7.3') or
            (distro_info[0] == 'redhat' and distro_info[1] == '7.4') or
            (distro_info[0] == 'centos' and distro_info[1] == '7.3.1611') or
            (distro_info[0] == 'centos' and distro_info[1] == '7.2.1511')):
            self.context.logger.log("Enabling OS volume encryption on {0} {1}".format(distro_info[0],
                                                                                      distro_info[1]))
        else:
            raise Exception("RHEL72EncryptionStateMachine called for distro {0} {1}".format(distro_info[0],
                                                                                            distro_info[1]))

        self.context.distro_patcher.install_extras()

        self._patch_waagent()
        self.command_executor.Execute('systemctl daemon-reload', True)

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit prereq state")

        return super(PrereqState, self).should_exit()

    def _patch_waagent(self):
        self.context.logger.log("Patching waagent")

        contents = None

        with open('/usr/lib/systemd/system/waagent.service', 'r') as f:
            contents = f.read()

        contents = re.sub(r'\[Service\]\n', '[Service]\nKillMode=process\n', contents)

        with open('/usr/lib/systemd/system/waagent.service', 'w') as f:
            f.write(contents)

        self.context.logger.log("waagent patched successfully")
