#!/usr/bin/env python
#
# Copyright (C) Microsoft Corporation
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

        if distro_info[0].lower() == 'ubuntu' and distro_info[1] in ['20.04', '22.04']:
            self.context.logger.log("Enabling OS volume encryption on {0} {1}".format(distro_info[0],
                                                                                      distro_info[1]))
        else:
            raise Exception("Ubuntu2004EncryptionStateMachine called for distro {0} {1}".format(distro_info[0],
                                                                                                distro_info[1]))

        self.context.distro_patcher.install_extras()

        self._patch_walinuxagent()
        self.command_executor.Execute('systemctl daemon-reload', True)

        self._snap_stop()

    def should_exit(self):
        self.context.logger.log("Verifying if machine should exit prereq state")

        return super(PrereqState, self).should_exit()

    def _patch_walinuxagent(self):
        self.context.logger.log("Patching walinuxagent")

        contents = None

        with open('/lib/systemd/system/walinuxagent.service', 'r') as f:
            contents = f.read()

        contents = re.sub(r'\[Service\]\n', '[Service]\nKillMode=process\n', contents)

        with open('/lib/systemd/system/walinuxagent.service', 'w') as f:
            f.write(contents)

        self.context.logger.log("walinuxagent patched successfully")

    def _snap_stop(self):
        self.context.logger.log('stop snaps and unmount')

        # stop all snapd services until next system restart to release file handles
        self.command_executor.ExecuteInBash("for line in `systemctl list-unit-files | grep snap | grep -Eo '^[^ ]+'`; do printf 'stopping %s\n' $line; systemctl stop $line; done");
        self.command_executor.ExecuteInBash("for line in `systemctl list-unit-files | grep snap | grep -Eo '^[^ ]+'`; do printf '%s ' $line; systemctl is-active $line; done");

        # unmount default snap created mountpoints in base image
        self.command_executor.ExecuteInBash('for MP in `lsblk -r -o MOUNTPOINT | grep /snap/lxd`;do umount "$MP";done',False)
        self.command_executor.ExecuteInBash('for MP in `lsblk -r -o MOUNTPOINT | grep /snap/core18`;do umount "$MP";done',False)
        self.command_executor.ExecuteInBash('for MP in `lsblk -r -o MOUNTPOINT | grep /snap/snapd`;do umount "$MP";done',False)
